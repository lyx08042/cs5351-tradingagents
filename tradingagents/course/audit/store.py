"""SQLite-backed append-only audit store with a single global hash chain.

Anchors: FR-005, INV-005, NFR-004. Design: ADR-003 §2.1-§2.7.

One global chain ordered by the SQLite autoincrement ``sequence``. Writes run in
``BEGIN IMMEDIATE`` so concurrent connections serialise "read head then append".
``BEFORE UPDATE``/``BEFORE DELETE`` triggers reject mutation, so ``append`` is
the only write path.
"""
from __future__ import annotations

import json
import sqlite3
from typing import Any

from .records import (
    AuditError,
    AuditRecord,
    canonical_json,
    compute_record_hash,
    make_record,
    payload_ref,
    validate_append_inputs,
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS audit_records (
    sequence            INTEGER PRIMARY KEY AUTOINCREMENT,
    record_id           TEXT NOT NULL UNIQUE,
    run_id              TEXT NOT NULL,
    timestamp           TEXT NOT NULL,
    entry_type          TEXT NOT NULL,
    payload_ref         TEXT NOT NULL,
    rules_version       TEXT NOT NULL,
    previous_record_id  TEXT,
    previous_hash       TEXT,
    record_hash         TEXT NOT NULL,
    supersedes          TEXT,
    payload             TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_audit_run ON audit_records (run_id);
CREATE UNIQUE INDEX IF NOT EXISTS ux_audit_single_decision
    ON audit_records (run_id)
    WHERE entry_type = 'decision';
CREATE UNIQUE INDEX IF NOT EXISTS ux_audit_single_supersede
    ON audit_records (supersedes)
    WHERE supersedes IS NOT NULL;

CREATE TRIGGER IF NOT EXISTS audit_no_update
    BEFORE UPDATE ON audit_records
BEGIN
    SELECT RAISE(ABORT, 'audit records are append-only: UPDATE rejected');
END;

CREATE TRIGGER IF NOT EXISTS audit_no_delete
    BEFORE DELETE ON audit_records
BEGIN
    SELECT RAISE(ABORT, 'audit records are append-only: DELETE rejected');
END;
"""

_COLUMNS = (
    "sequence",
    "record_id",
    "run_id",
    "timestamp",
    "entry_type",
    "payload_ref",
    "rules_version",
    "previous_record_id",
    "previous_hash",
    "record_hash",
    "supersedes",
    "payload",
)
_SELECT = f"SELECT {', '.join(_COLUMNS)} FROM audit_records ORDER BY sequence"


class VerificationResult:
    """Outcome of chain verification (FR-005, INV-005).

    ``ok`` is True only when the whole chain is internally consistent and its
    decision/revision semantics hold. ``reason`` names the first failure code and
    ``position`` the offending ``sequence`` when known.
    """

    __slots__ = ("ok", "reason", "detail", "position")

    def __init__(self, ok: bool, reason: str = "ok", detail: str = "", position: int | None = None) -> None:
        self.ok = ok
        self.reason = reason
        self.detail = detail
        self.position = position

    def to_dict(self) -> dict:
        """Return a plain dict view of the verification result (INV-005 / ADR-003)."""
        return {"ok": self.ok, "reason": self.reason, "detail": self.detail, "position": self.position}

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return f"VerificationResult(ok={self.ok}, reason={self.reason!r}, position={self.position})"


def _row_to_record(row: sqlite3.Row) -> AuditRecord:
    """Build an :class:`AuditRecord` from a stored row, preserving all persisted fields.

    Unlike :func:`make_record` (used on append to *generate* ``payload_ref``),
    materialising a stored row must keep the raw persisted ``payload_ref`` and
    ``record_hash`` verbatim. Recomputing them here would silently "repair" a
    tampered row during read, hiding corruption from verify/replay.
    """
    return AuditRecord(
        record_id=row["record_id"],
        run_id=row["run_id"],
        timestamp=row["timestamp"],
        entry_type=row["entry_type"],
        payload_ref=row["payload_ref"],
        rules_version=row["rules_version"],
        previous_record_id=row["previous_record_id"],
        previous_hash=row["previous_hash"],
        record_hash=row["record_hash"],
        supersedes=row["supersedes"],
        sequence=row["sequence"],
        _payload_json=row["payload"],
    )


class AuditStore:
    """Append-only audit store over one SQLite file with one global chain.

    Public API (ADR-003 §2.6): :meth:`open`, :meth:`append`, :meth:`get`,
    :meth:`iter_run`, :meth:`verified_records`, :meth:`project`,
    :meth:`final_decision`, :meth:`head`, :meth:`verify_chain`. No update/delete
    methods exist; triggers reject such SQL. Anchors: FR-005, INV-005.
    """

    def __init__(self, path: str, *, timeout: float = 30.0) -> None:
        self._path = path
        self._conn = sqlite3.connect(path, timeout=timeout, isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.executescript(_SCHEMA)

    @classmethod
    def open(cls, path: str, *, timeout: float = 30.0) -> AuditStore:
        """Open (or create) an audit store; idempotent for reopen (FR-005 / INV-005 / ADR-003)."""
        return cls(path, timeout=timeout)

    def close(self) -> None:
        """Close the underlying connection (FR-005 / INV-005 / ADR-003)."""
        self._conn.close()

    def __enter__(self) -> AuditStore:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    # -- snapshot + verification -------------------------------------------
    def _snapshot(self) -> list[sqlite3.Row]:
        """Read the whole chain in one SELECT (single consistent snapshot)."""
        return self._conn.execute(_SELECT).fetchall()

    def _verify_rows(self, rows: list[sqlite3.Row]) -> VerificationResult:
        """Verify a full ordered snapshot (FR-005, INV-005, ADR-003 §2.3).

        Checks, walking from the root in ``sequence`` order: strictly increasing
        and continuous sequence, per-row field validity, payload parse and
        ``payload_ref`` match, recomputed ``record_hash``, predecessor link
        continuity, and decision/revision semantics via a per-run
        ``current_terminal`` cursor.
        """
        prev_id: str | None = None
        prev_hash: str | None = None
        expected_seq = 1
        for row in rows:
            seq = row["sequence"]
            if not isinstance(seq, int) or seq != expected_seq:
                return VerificationResult(
                    False, "chain_broken",
                    f"sequence gap: expected {expected_seq} at position {seq}", seq,
                )
            expected_seq += 1

            try:
                payload = json.loads(row["payload"])
            except (ValueError, TypeError) as exc:
                return VerificationResult(
                    False, "malformed_payload", f"cannot parse payload JSON at {row['record_id']!r}: {exc}", seq,
                )

            try:
                validate_append_inputs(
                    record_id=row["record_id"],
                    run_id=row["run_id"],
                    timestamp=row["timestamp"],
                    entry_type=row["entry_type"],
                    payload=payload,
                    rules_version=row["rules_version"],
                    supersedes=row["supersedes"],
                )
            except AuditError as exc:
                return VerificationResult(False, exc.code, f"invalid field at {row['record_id']!r}: {exc.message}", seq)

            try:
                if row["payload_ref"] != payload_ref(payload):
                    return VerificationResult(
                        False, "payload_tampered", f"payload_ref mismatch at {row['record_id']!r}", seq,
                    )
                record = _row_to_record(row)
            except AuditError as exc:
                return VerificationResult(False, exc.code, f"invalid payload at {row['record_id']!r}: {exc.message}", seq)

            if row["previous_record_id"] != prev_id or row["previous_hash"] != prev_hash:
                reason = "orphan_record" if expected_seq == 2 and row["previous_record_id"] is not None else "chain_broken"
                return VerificationResult(
                    False, reason, f"predecessor link mismatch at {row['record_id']!r}", seq,
                )
            if record.recompute_hash() != row["record_hash"]:
                return VerificationResult(
                    False, "chain_broken", f"record_hash mismatch at {row['record_id']!r}", seq,
                )
            prev_id = row["record_id"]
            prev_hash = row["record_hash"]

        return self._verify_semantics(rows)

    @staticmethod
    def _verify_semantics(rows: list[sqlite3.Row]) -> VerificationResult:
        """Decision/revision semantics using a per-run current-terminal cursor.

        Rules (INV-005): at most one initial decision per run; a revision must
        point at the *currently reached* terminal (no future/self/cycle); a run
        cannot revise before its initial decision exists; non-revisions must not
        carry ``supersedes``.
        """
        current_terminal: dict[str, str] = {}
        has_initial: dict[str, bool] = {}
        seen_ids: set[str] = set()
        for row in rows:
            run_id = row["run_id"]
            rid = row["record_id"]
            entry = row["entry_type"]
            supersedes = row["supersedes"]

            if entry == "decision":
                if has_initial.get(run_id):
                    return VerificationResult(
                        False, "invariant_violation", f"run {run_id!r} has multiple initial decisions", row["sequence"],
                    )
                has_initial[run_id] = True
                current_terminal[run_id] = rid
            elif entry == "revision":
                if not has_initial.get(run_id):
                    return VerificationResult(
                        False, "invariant_violation", f"run {run_id!r} revision precedes any initial decision", row["sequence"],
                    )
                if supersedes == rid:
                    return VerificationResult(
                        False, "invariant_violation", f"revision {rid!r} supersedes itself", row["sequence"],
                    )
                if supersedes not in seen_ids:
                    # Future reference or missing record: not yet reached.
                    return VerificationResult(
                        False, "invariant_violation", f"revision {rid!r} supersedes an unreached/unknown record {supersedes!r}", row["sequence"],
                    )
                if current_terminal.get(run_id) != supersedes:
                    return VerificationResult(
                        False, "invariant_violation", f"revision {rid!r} does not supersede the current terminal", row["sequence"],
                    )
                current_terminal[run_id] = rid
            else:
                if supersedes is not None:
                    return VerificationResult(
                        False, "invariant_violation", f"non-revision {rid!r} must not carry supersedes", row["sequence"],
                    )
            seen_ids.add(rid)
        return VerificationResult(True)

    def verify_chain(self) -> VerificationResult:
        """Traverse the entire chain from a single snapshot (FR-005, INV-005)."""
        return self._verify_rows(self._snapshot())

    def _verified_rows(self) -> list[sqlite3.Row]:
        """Return the single snapshot if healthy, else raise ``AuditError``.

        The returned rows are the *same* snapshot that was verified, so callers
        never re-query and risk a split between verification and reads (FR-005).
        """
        rows = self._snapshot()
        result = self._verify_rows(rows)
        if not result.ok:
            # Only invariant_violation keeps its own code; every other failure
            # (malformed payload, sequence gap, tampering...) surfaces as
            # chain_broken, with the precise reason kept in message/context so
            # authoritative reads never look valid on a damaged chain.
            code = "invariant_violation" if result.reason == "invariant_violation" else "chain_broken"
            raise AuditError(
                code,
                f"audit chain is not consistent: {result.reason} ({result.detail})",
                context=result.to_dict(),
            )
        return rows

    @staticmethod
    def _rows_to_records(rows: list[sqlite3.Row], run_id: str | None = None) -> list[AuditRecord]:
        records: list[AuditRecord] = []
        for row in rows:
            if run_id is not None and row["run_id"] != run_id:
                continue
            records.append(_row_to_record(row))
        return records

    def verified_records(self, run_id: str | None = None) -> list[AuditRecord]:
        """Return records from one verified snapshot (FR-005, INV-005).

        Verification and the returned records come from the same SELECT, so the
        event set cannot drift between check and use. Raises ``AuditError`` on a
        broken chain. Used by :func:`replay_run` and authoritative reads.
        """
        return self._rows_to_records(self._verified_rows(), run_id)

    # -- append -------------------------------------------------------------
    def append(
        self,
        *,
        record_id: str,
        run_id: str,
        timestamp: str,
        entry_type: str,
        payload: Any,
        rules_version: str,
        supersedes: str | None = None,
    ) -> AuditRecord:
        """Append one record and return it (FR-005, INV-005).

        ``record_id``/``run_id``/``timestamp``/``payload``/``rules_version`` are
        caller inputs; ``payload_ref``, predecessor links and ``record_hash`` are
        generated here inside the transaction so predecessors cannot be forged.
        The existing chain is verified first; a broken chain refuses the write.
        Any failure rolls back with no partial row.
        """
        validate_append_inputs(
            record_id=record_id,
            run_id=run_id,
            timestamp=timestamp,
            entry_type=entry_type,
            payload=payload,
            rules_version=rules_version,
            supersedes=supersedes,
        )
        # Canonicalise the payload exactly once, then derive an immutable
        # snapshot from that text so later caller mutations cannot affect the
        # computed ref/hash, the inserted row, or the returned record.
        payload_text = canonical_json(payload).decode("utf-8")
        payload_snapshot = json.loads(payload_text)
        pref = payload_ref(payload_snapshot)

        self._conn.execute("BEGIN IMMEDIATE")
        try:
            rows = self._snapshot()
            result = self._verify_rows(rows)
            if not result.ok:
                raise AuditError(
                    "chain_broken",
                    f"refusing append on broken chain: {result.reason} ({result.detail})",
                    context=result.to_dict(),
                )

            if self._conn.execute(
                "SELECT 1 FROM audit_records WHERE record_id = ?", (record_id,)
            ).fetchone() is not None:
                raise AuditError("duplicate_record_id", f"record_id {record_id!r} already exists")

            if entry_type == "decision":
                if self._conn.execute(
                    "SELECT 1 FROM audit_records WHERE run_id = ? AND entry_type = 'decision'", (run_id,)
                ).fetchone() is not None:
                    raise AuditError(
                        "duplicate_decision",
                        f"run {run_id!r} already has an initial decision; use a revision",
                    )
            elif entry_type == "revision":
                self._check_revision_target(run_id=run_id, supersedes=supersedes)

            prev_id = rows[-1]["record_id"] if rows else None
            prev_hash = rows[-1]["record_hash"] if rows else None

            fields = {
                "record_id": record_id,
                "run_id": run_id,
                "timestamp": timestamp,
                "entry_type": entry_type,
                "payload_ref": pref,
                "rules_version": rules_version,
                "previous_record_id": prev_id,
                "previous_hash": prev_hash,
                "supersedes": supersedes,
                "payload": payload_snapshot,
            }
            record_hash = compute_record_hash(fields)
            cursor = self._conn.execute(
                f"INSERT INTO audit_records ({', '.join(_COLUMNS[1:])}) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    record_id, run_id, timestamp, entry_type, pref, rules_version,
                    prev_id, prev_hash, record_hash, supersedes, payload_text,
                ),
            )
            sequence = int(cursor.lastrowid)
            self._conn.execute("COMMIT")
        except Exception:
            self._conn.execute("ROLLBACK")
            raise

        return make_record(
            record_id=record_id,
            run_id=run_id,
            timestamp=timestamp,
            entry_type=entry_type,
            payload=payload_snapshot,
            rules_version=rules_version,
            previous_record_id=prev_id,
            previous_hash=prev_hash,
            record_hash=record_hash,
            supersedes=supersedes,
            sequence=sequence,
        )

    def _check_revision_target(self, *, run_id: str, supersedes: str) -> None:
        target = self._conn.execute(
            "SELECT record_id, run_id, entry_type FROM audit_records WHERE record_id = ?", (supersedes,)
        ).fetchone()
        if target is None:
            raise AuditError("invalid_supersede", f"supersedes target {supersedes!r} does not exist")
        if target["run_id"] != run_id:
            raise AuditError("invalid_supersede", "revision must supersede a record in the same run")
        if target["entry_type"] not in ("decision", "revision"):
            raise AuditError("invalid_supersede", "revision must supersede a decision, not an event")
        if self._conn.execute(
            "SELECT 1 FROM audit_records WHERE supersedes = ?", (supersedes,)
        ).fetchone() is not None:
            raise AuditError(
                "invalid_supersede",
                f"{supersedes!r} is not the current terminal decision (already superseded)",
            )

    # -- read API -----------------------------------------------------------
    def get(self, record_id: str) -> AuditRecord | None:
        """Return the record with ``record_id`` or None (FR-005 / INV-005 / ADR-003)."""
        row = self._conn.execute(
            f"SELECT {', '.join(_COLUMNS)} FROM audit_records WHERE record_id = ?", (record_id,)
        ).fetchone()
        return _row_to_record(row) if row is not None else None

    def iter_run(self, run_id: str) -> list[AuditRecord]:
        """Return records for ``run_id`` in global sequence order (FR-005, NFR-004, INV-005 / ADR-003)."""
        rows = self._conn.execute(
            f"SELECT {', '.join(_COLUMNS)} FROM audit_records WHERE run_id = ? ORDER BY sequence", (run_id,)
        ).fetchall()
        return [_row_to_record(row) for row in rows]

    def project(self, run_id: str) -> dict:
        """Return a projection with derived ``superseded_by`` (FR-005, INV-005).

        Built from one verified snapshot; a broken chain raises
        ``AuditError(code=chain_broken)``. ``superseded_by`` is derived from
        successor revisions, never written back.
        """
        records = self.verified_records(run_id)
        superseded_by: dict[str, str] = {}
        for record in records:
            if record.entry_type == "revision" and record.supersedes is not None:
                superseded_by[record.supersedes] = record.record_id
        projected = []
        for record in records:
            item = record.to_dict()
            item["superseded_by"] = superseded_by.get(record.record_id)
            projected.append(item)
        return {
            "run_id": run_id,
            "records": projected,
            "final_decision_id": self._terminal_id(records),
        }

    @staticmethod
    def _terminal_id(records: list[AuditRecord]) -> str | None:
        decisions = [r for r in records if r.entry_type in ("decision", "revision")]
        if not decisions:
            return None
        superseded = {r.supersedes for r in decisions if r.supersedes is not None}
        leaves = [r.record_id for r in decisions if r.record_id not in superseded]
        if len(leaves) != 1:
            raise AuditError(
                "invariant_violation",
                f"run has {len(leaves)} terminal decision leaves, expected exactly 1",
            )
        return leaves[0]

    def final_decision(self, run_id: str) -> AuditRecord:
        """Return the unique terminal decision for ``run_id`` (FR-005, INV-005).

        Uses one verified snapshot; returns the single leaf, else raises.
        """
        records = self.verified_records(run_id)
        terminal_id = self._terminal_id(records)
        if terminal_id is None:
            raise AuditError("invariant_violation", f"run {run_id!r} has no decision")
        for record in records:
            if record.record_id == terminal_id:
                return record
        raise AuditError("invariant_violation", "terminal decision not found")  # pragma: no cover

    def head(self) -> dict:
        """Return ``{record_id, record_hash, count}`` from one snapshot (FR-005 / INV-005 / ADR-003).

        The last row and the count come from the same read, so concurrent appends
        cannot make them inconsistent.
        """
        rows = self._snapshot()
        if not rows:
            return {"record_id": None, "record_hash": None, "count": 0}
        last = rows[-1]
        return {"record_id": last["record_id"], "record_hash": last["record_hash"], "count": len(rows)}


__all__ = ["AuditStore", "VerificationResult"]

"""Offline, versioned gate replay against the audit chain.

Anchors: FR-005, NFR-003 (determinism), INV-005. Design: ADR-003 §2.8.

Replay never imports C/D/B leaf modules. The caller supplies a versioned gate
registry ``{gate_id: {rules_version: callable(inputs) -> observed}}``; replay
re-executes the callback on a deep copy of the recorded inputs and compares
canonical JSON with the recorded ``observed``.
"""
from __future__ import annotations

import copy
from collections.abc import Callable
from typing import Any

from .records import AuditError, AuditRecord, canonical_json, payload_ref
from .store import AuditStore, VerificationResult

GateCallback = Callable[[Any], Any]
GateRegistry = dict[str, dict[str, GateCallback]]

#: ``pass`` = re-executed gate matched; ``review`` = any failure; ``inconclusive``
#: = no gate records to replay (never reported as a 100% pass).
STATUS_PASS = "pass"
STATUS_REVIEW = "review"
STATUS_INCONCLUSIVE = "inconclusive"


class ReplayResult:
    """Outcome of replaying one record (FR-005, NFR-003, INV-005 / ADR-003).

    ``reason`` names the cause (``ok``, ``gate_missing``, ``version_unknown``,
    ``missing_key``, ``rules_version_mismatch``, ``input_tampered``,
    ``non_json_result``, ``callback_error``, ``observed_mismatch``,
    ``malformed_payload``). ``count`` is 1 for a gate replay, 0 for an excluded
    non-gate record.
    """

    __slots__ = ("record_id", "gate_id", "rules_version", "status", "reason", "detail", "count")

    def __init__(
        self, *, record_id: str, gate_id: str | None, rules_version: str | None,
        status: str, reason: str, detail: str = "", count: int,
    ) -> None:
        self.record_id = record_id
        self.gate_id = gate_id
        self.rules_version = rules_version
        self.status = status
        self.reason = reason
        self.detail = detail
        self.count = count

    def to_dict(self) -> dict:
        """Return a plain dict for this single-record replay result (INV-005 / ADR-003)."""
        return {
            "record_id": self.record_id, "gate_id": self.gate_id,
            "rules_version": self.rules_version, "status": self.status,
            "reason": self.reason, "detail": self.detail, "count": self.count,
        }

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return f"ReplayResult(record_id={self.record_id!r}, status={self.status!r}, reason={self.reason!r})"


class ReplayRunResult:
    """Aggregate outcome of :func:`replay_run` (FR-005, NFR-003, INV-005 / ADR-003).

    ``gate_total`` counts only gate records; ``inconclusive`` is True when
    ``gate_total == 0``. ``status`` is ``pass`` only when there was at least one
    gate and all passed; otherwise ``review`` (or ``inconclusive``). It never
    reports a pass with an empty denominator.
    """

    __slots__ = ("run_id", "status", "results", "gate_total", "passed", "reviewed", "inconclusive", "detail")

    def __init__(self, *, run_id: str, results: list[ReplayResult], detail: str = "") -> None:
        self.run_id = run_id
        self.results = results
        self.gate_total = sum(r.count for r in results)
        self.passed = sum(1 for r in results if r.status == STATUS_PASS)
        self.reviewed = sum(1 for r in results if r.status == STATUS_REVIEW)
        self.inconclusive = self.gate_total == 0
        if self.inconclusive:
            self.status = STATUS_INCONCLUSIVE
        elif self.reviewed > 0:
            self.status = STATUS_REVIEW
        else:
            self.status = STATUS_PASS
        self.detail = detail

    def _force_review(self) -> ReplayRunResult:
        """Overwrite the aggregate status to review for a pre-replay failure."""
        self.status = STATUS_REVIEW
        self.inconclusive = False
        return self

    def to_dict(self) -> dict:
        """Return a plain dict for this run-level replay result (INV-005 / ADR-003)."""
        return {
            "run_id": self.run_id, "status": self.status, "gate_total": self.gate_total,
            "passed": self.passed, "reviewed": self.reviewed, "inconclusive": self.inconclusive,
            "detail": self.detail, "results": [r.to_dict() for r in self.results],
        }

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return (
            f"ReplayRunResult(run_id={self.run_id!r}, status={self.status!r}, "
            f"gate_total={self.gate_total}, passed={self.passed})"
        )


def _review(record_id: str, reason: str, *, gate_id: str | None = None, rules_version: str | None = None,
            detail: str = "", count: int = 1) -> ReplayResult:
    return ReplayResult(
        record_id=record_id, gate_id=gate_id, rules_version=rules_version,
        status=STATUS_REVIEW, reason=reason, detail=detail, count=count,
    )


def replay_record(record: AuditRecord, registry: GateRegistry) -> ReplayResult:
    """Replay a single record against ``registry`` (FR-005, NFR-003, INV-005 / ADR-003).

    Verifies this record's own ``record_hash`` and ``payload_ref``, not whole-chain
    integrity (use :func:`replay_run`). The callback receives a deep copy of
    ``inputs``; any mutation, exception, non-JSON result or mismatch yields
    ``review``. A malformed registry (non-dict) or payload yields ``review``
    instead of raising. A record carrying any replay field (gate_id/inputs/
    observed) is treated as gate intent and reviewed if incomplete; a pure
    narrative record is ``inconclusive`` with ``count == 0``.
    """
    try:
        # Check the payload content digest first: a tampered payload_ref must
        # surface as payload_ref_mismatch even though it also breaks the overall
        # record_hash. Invalid JSON still yields a review without escaping.
        payload = record.payload
        if record.payload_ref != payload_ref(payload):
            return _review(record.record_id, "payload_ref_mismatch",
                           detail="stored payload_ref does not match the payload")
        if record.recompute_hash() != record.record_hash:
            return _review(record.record_id, "record_hash_mismatch")
    except (AuditError, ValueError, TypeError) as exc:
        return _review(record.record_id, "malformed_payload", detail=str(exc))

    # Treat a record as gate intent if it carries ANY replay-specific field. A
    # malformed gate missing only ``gate_id`` must be reviewed, not silently
    # excluded from the agreement denominator. Pure narrative records
    # (action/outcome/note only) stay inconclusive; a payload with none of the
    # three replay fields cannot be auto-inferred as a gate (see README).
    if not isinstance(payload, dict):
        return ReplayResult(
            record_id=record.record_id, gate_id=None, rules_version=None,
            status=STATUS_INCONCLUSIVE, reason="not_a_gate_record", count=0,
        )
    replay_fields = {"gate_id", "inputs", "observed"}
    present = replay_fields & payload.keys()
    if not present:
        return ReplayResult(
            record_id=record.record_id, gate_id=None, rules_version=None,
            status=STATUS_INCONCLUSIVE, reason="not_a_gate_record", count=0,
        )

    gate_id = payload.get("gate_id")
    if not isinstance(gate_id, str) or not gate_id:
        return _review(record.record_id, "missing_key", rules_version=record.rules_version,
                       detail="gate record is missing a non-empty gate_id")

    for key in ("inputs", "observed"):
        if key not in payload:
            return _review(record.record_id, "missing_key", gate_id=gate_id,
                           rules_version=record.rules_version, detail=f"payload missing {key!r}")

    payload_version = payload.get("rules_version")
    if payload_version is not None and payload_version != record.rules_version:
        return _review(record.record_id, "rules_version_mismatch", gate_id=gate_id,
                       rules_version=record.rules_version,
                       detail=f"payload.rules_version {payload_version!r} != record {record.rules_version!r}")

    if not isinstance(registry, dict):
        return _review(record.record_id, "gate_missing", gate_id=gate_id,
                       rules_version=record.rules_version, detail="registry is not a mapping")
    versions = registry.get(gate_id)
    if not isinstance(versions, dict):
        return _review(record.record_id, "gate_missing", gate_id=gate_id,
                       rules_version=record.rules_version, detail=f"gate {gate_id!r} is not registered")
    callback = versions.get(record.rules_version)
    if not callable(callback):
        return _review(record.record_id, "version_unknown", gate_id=gate_id,
                       rules_version=record.rules_version,
                       detail=f"gate {gate_id!r} has no version {record.rules_version!r}")

    recorded_inputs = payload["inputs"]
    recorded_observed = payload["observed"]
    inputs_copy = copy.deepcopy(recorded_inputs)
    try:
        produced = callback(inputs_copy)
    except Exception as exc:  # callback failure -> review, never pass
        return _review(record.record_id, "callback_error", gate_id=gate_id,
                       rules_version=record.rules_version, detail=f"{type(exc).__name__}: {exc}")

    try:
        if canonical_json(inputs_copy) != canonical_json(recorded_inputs):
            return _review(record.record_id, "input_tampered", gate_id=gate_id,
                           rules_version=record.rules_version, detail="callback mutated its input copy")
        produced_bytes = canonical_json(produced)
        expected_bytes = canonical_json(recorded_observed)
    except AuditError as exc:
        return _review(record.record_id, "non_json_result", gate_id=gate_id,
                       rules_version=record.rules_version, detail=str(exc))

    if produced_bytes != expected_bytes:
        return _review(record.record_id, "observed_mismatch", gate_id=gate_id,
                       rules_version=record.rules_version,
                       detail="re-executed gate result differs from recorded observed")

    return ReplayResult(
        record_id=record.record_id, gate_id=gate_id, rules_version=record.rules_version,
        status=STATUS_PASS, reason="ok", count=1,
    )


def verify_against_trusted_head(store: AuditStore, trusted_head: Any) -> VerificationResult:
    """Compare the current head with an externally stored head (FR-005, INV-005).

    Malformed input (non-dict, missing keys, empty dict, non-int count) returns
    ``head_mismatch`` (review) rather than raising. The whole chain is verified
    first, so an equal head over a corrupted middle still fails. Inequality is not
    proof of tampering: legitimate appends also change the head, so it yields
    ``head_mismatch`` for human confirmation only.
    """
    if not isinstance(trusted_head, dict):
        return VerificationResult(False, "head_mismatch", "trusted head must be a mapping")

    required = ("record_id", "record_hash", "count")
    if any(key not in trusted_head for key in required):
        return VerificationResult(False, "head_mismatch", "trusted head missing required fields")
    count = trusted_head["count"]
    if not isinstance(count, int) or isinstance(count, bool):
        return VerificationResult(False, "head_mismatch", "trusted head count must be an int")

    chain = store.verify_chain()
    if not chain.ok:
        return VerificationResult(False, "chain_broken", f"chain not consistent: {chain.reason} ({chain.detail})")

    current = store.head()
    expected = {
        "record_id": trusted_head["record_id"],
        "record_hash": trusted_head["record_hash"],
        "count": count,
    }
    if current != expected:
        return VerificationResult(False, "head_mismatch", f"current head {current} != trusted head {expected}")
    return VerificationResult(True, "ok", "head matches trusted snapshot")


def replay_run(
    store: AuditStore,
    run_id: str,
    registry: GateRegistry,
    trusted_head: dict | None = None,
) -> ReplayRunResult:
    """Replay all gate records of ``run_id`` from one verified snapshot (FR-005, NFR-003, INV-005 / ADR-003).

    Order: verify the whole chain, then (if given) compare the trusted head, then
    replay each gate record from the *same* verified snapshot. A broken chain or
    head mismatch aborts to an overall review without replaying. Non-gate records
    are excluded from the agreement denominator; zero gate records yields
    ``inconclusive``, not a 100% pass. Replay never mutates stored records.
    """
    try:
        records = store.verified_records(run_id)
    except AuditError as exc:
        return ReplayRunResult(
            run_id=run_id, results=[], detail=f"chain not consistent: {exc.message}",
        )._force_review()

    if trusted_head is not None:
        head_result = verify_against_trusted_head(store, trusted_head)
        if not head_result.ok:
            return ReplayRunResult(
                run_id=run_id, results=[],
                detail=f"trusted head check failed: {head_result.reason}",
            )._force_review()

    results = [replay_record(record, registry) for record in records]
    return ReplayRunResult(run_id=run_id, results=results)

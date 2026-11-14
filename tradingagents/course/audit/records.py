"""Immutable audit records, canonical JSON, and hashing helpers.

Anchors: FR-005, INV-005, NFR-003 (deterministic replay), ADR-003 §3.5/§3.6.
Standard library only.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

#: Allowed ``entry_type`` values (ADR-003 §2.6). ``review`` is expressed as a
#: ``rejection`` whose payload carries ``outcome == "review"``.
ENTRY_TYPES = ("decision", "rejection", "abstain", "revision")

#: ISO-8601 timestamps must carry a UTC offset; we do not read the system clock.
_TIMESTAMP_FORMAT_ERROR = "timestamp must be a non-empty ISO-8601 string with timezone offset"


class AuditError(Exception):
    """Single error type carrying a stable ``code`` (ADR-003 §2.6).

    ``code`` names the failure reason so tests assert one exact outcome without
    a large class hierarchy. Anchors: FR-005, INV-005.
    """

    def __init__(self, code: str, message: str = "", *, context: dict | None = None) -> None:
        self.code = code
        self.message = message or code
        self.context = context or {}
        super().__init__(f"{code}: {self.message}")


def _check_json_value(value: Any, *, seen: set[int] | None = None) -> None:
    """Reject non-JSON values without silent conversion (ADR-003 §3.6).

    Allowed: dict[str, ...], list, str, bool, int, finite float, None.
    Rejected: non-string dict keys, NaN/Infinity, tuple, set, bytes, cycles,
    custom objects. Anchors: FR-005, NFR-003.
    """
    if seen is None:
        seen = set()
    if isinstance(value, bool) or value is None or isinstance(value, str):
        return
    if isinstance(value, int):
        return
    if isinstance(value, float):
        if value != value or value in (float("inf"), float("-inf")):
            raise AuditError("non_finite_number", f"non-finite float not allowed: {value!r}")
        return
    if isinstance(value, dict):
        marker = id(value)
        if marker in seen:
            raise AuditError("invalid_json", "cyclic structure not allowed")
        seen.add(marker)
        try:
            for key, item in value.items():
                if not isinstance(key, str):
                    raise AuditError(
                        "non_string_key",
                        f"JSON object keys must be str, got {type(key).__name__}",
                    )
                _check_json_value(item, seen=seen)
        finally:
            seen.discard(marker)
        return
    if isinstance(value, tuple):
        raise AuditError("invalid_json", "tuple is not a JSON type; use list")
    if isinstance(value, list):
        marker = id(value)
        if marker in seen:
            raise AuditError("invalid_json", "cyclic structure not allowed")
        seen.add(marker)
        try:
            for item in value:
                _check_json_value(item, seen=seen)
        finally:
            seen.discard(marker)
        return
    raise AuditError("invalid_json", f"unsupported JSON value type: {type(value).__name__}")


def canonical_json(obj: Any) -> bytes:
    """Serialize ``obj`` to canonical UTF-8 JSON bytes (ADR-003 §3.6).

    Keys sorted, compact separators, ``ensure_ascii=False``, NaN off. Invalid
    inputs raise :class:`AuditError` and are never silently coerced.
    Anchors: FR-005, NFR-003.
    """
    try:
        _check_json_value(obj)
    except RecursionError as exc:
        raise AuditError("invalid_json", "structure too deep / cyclic") from exc
    try:
        text = json.dumps(
            obj,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
        return text.encode("utf-8")
    except (TypeError, ValueError, UnicodeEncodeError, RecursionError) as exc:
        # Lone surrogates fail utf-8 encoding; excessive nesting hits the
        # recursion limit. Both must surface as a single AuditError, never leak
        # as UnicodeEncodeError/RecursionError (e.g. from a replay callback).
        raise AuditError("invalid_json", f"cannot serialize to canonical JSON: {exc}") from exc


def payload_ref(payload: Any) -> str:
    """Return ``"sha256:<hex>"`` of the canonical JSON of ``payload`` (FR-005, INV-005)."""
    digest = hashlib.sha256(canonical_json(payload)).hexdigest()
    return f"sha256:{digest}"


def _validate_timestamp(timestamp: str) -> None:
    """Require a non-empty ISO-8601 string with an explicit UTC offset (ADR-003 §3.5)."""
    if not isinstance(timestamp, str) or not timestamp.strip():
        raise AuditError("invalid_timestamp", _TIMESTAMP_FORMAT_ERROR)
    try:
        parsed = datetime.fromisoformat(timestamp)
    except ValueError as exc:
        raise AuditError("invalid_timestamp", _TIMESTAMP_FORMAT_ERROR) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise AuditError("invalid_timestamp", _TIMESTAMP_FORMAT_ERROR)


def _require_non_empty(value: Any, *, field_name: str, code: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise AuditError(code, f"{field_name} must be a non-empty string")
    return value


def compute_record_hash(fields: dict[str, Any]) -> str:
    """Hash canonical JSON of all persisted fields except ``record_hash`` (FR-005, INV-005).

    ``sequence`` is excluded: it is a storage ordinal for continuity checks, not
    part of a record's logical identity (ADR-003 §2.3).
    """
    hashed = {k: v for k, v in fields.items() if k != "record_hash"}
    return hashlib.sha256(canonical_json(hashed)).hexdigest()


def _store_sequence(data: Any) -> None:
    """dataclass ``post_init`` hook: reject non-integer sequence."""
    if not isinstance(data.sequence, int) or isinstance(data.sequence, bool):
        raise AuditError("invalid_sequence", "sequence must be an int")


@dataclass(frozen=True, slots=True)
class AuditRecord:
    """Immutable audit record returned by the store (FR-005, INV-005).

    Frozen dataclass with ``__slots__``: attribute assignment and deletion raise.
    The constructor's ``record_id`` is supplied explicitly by the *caller* of
    :meth:`AuditStore.append`, not generated by the store. Predecessor links and
    hashes, however, are generated by the store (ADR-003 §2.6).

    ``payload`` is stored as canonical JSON text; the :attr:`payload` property and
    :meth:`to_dict` return fresh decoded structures, so mutating them cannot
    change the record's internal state.
    """

    record_id: str
    run_id: str
    timestamp: str
    entry_type: str
    payload_ref: str
    rules_version: str
    previous_record_id: str | None
    previous_hash: str | None
    record_hash: str
    supersedes: str | None
    sequence: int
    _payload_json: str = field(repr=False)

    def __post_init__(self) -> None:
        _store_sequence(self)

    @property
    def payload(self) -> Any:
        """Fresh decoded payload value; mutating it cannot affect the record."""
        return json.loads(self._payload_json)

    def to_dict(self) -> dict:
        """Return a plain dict; ``payload`` is a fresh structure (INV-005)."""
        return {
            "record_id": self.record_id,
            "run_id": self.run_id,
            "timestamp": self.timestamp,
            "entry_type": self.entry_type,
            "payload_ref": self.payload_ref,
            "rules_version": self.rules_version,
            "previous_record_id": self.previous_record_id,
            "previous_hash": self.previous_hash,
            "record_hash": self.record_hash,
            "supersedes": self.supersedes,
            "sequence": self.sequence,
            "payload": self.payload,
        }

    def hash_fields(self) -> dict:
        """Return exactly the fields that :func:`compute_record_hash` hashes."""
        return {
            "record_id": self.record_id,
            "run_id": self.run_id,
            "timestamp": self.timestamp,
            "entry_type": self.entry_type,
            "payload_ref": self.payload_ref,
            "rules_version": self.rules_version,
            "previous_record_id": self.previous_record_id,
            "previous_hash": self.previous_hash,
            "supersedes": self.supersedes,
            "payload": self.payload,
        }

    def recompute_hash(self) -> str:
        """Recompute the record hash from current fields (FR-005, INV-005)."""
        return compute_record_hash(self.hash_fields())


def make_record(
    *,
    record_id: str,
    run_id: str,
    timestamp: str,
    entry_type: str,
    payload: Any,
    rules_version: str,
    previous_record_id: str | None,
    previous_hash: str | None,
    record_hash: str,
    supersedes: str | None,
    sequence: int,
) -> AuditRecord:
    """Build a frozen :class:`AuditRecord`, deriving ``payload_ref`` from payload.

    The store calls this after it has generated the links/hash; ``payload_ref`` is
    computed from the canonical payload so it always matches ``_payload_json``.
    Anchors: FR-005, INV-005.
    """
    text = canonical_json(payload).decode("utf-8")
    ref = "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()
    return AuditRecord(
        record_id=record_id,
        run_id=run_id,
        timestamp=timestamp,
        entry_type=entry_type,
        payload_ref=ref,
        rules_version=rules_version,
        previous_record_id=previous_record_id,
        previous_hash=previous_hash,
        record_hash=record_hash,
        supersedes=supersedes,
        sequence=sequence,
        _payload_json=text,
    )


def validate_append_inputs(
    *,
    record_id: str,
    run_id: str,
    timestamp: str,
    entry_type: str,
    payload: Any,
    rules_version: str,
    supersedes: str | None,
) -> None:
    """Validate caller-supplied append inputs before any DB work (ADR-003 §3.5).

    Also used by chain verification on each persisted row, so field errors are
    detected consistently. Anchors: FR-005, INV-005, NFR-004.
    """
    _require_non_empty(record_id, field_name="record_id", code="empty_id")
    _require_non_empty(run_id, field_name="run_id", code="empty_id")
    _require_non_empty(rules_version, field_name="rules_version", code="empty_id")
    if entry_type not in ENTRY_TYPES:
        raise AuditError(
            "invalid_entry_type",
            f"entry_type must be one of {ENTRY_TYPES}, got {entry_type!r}",
        )
    _validate_timestamp(timestamp)
    _check_json_value(payload)
    if entry_type == "revision":
        if not isinstance(supersedes, str) or not supersedes.strip():
            raise AuditError("invalid_supersede", "revision requires a non-empty supersedes id")
    elif supersedes is not None:
        raise AuditError("invalid_supersede", "supersedes is only allowed for entry_type=revision")


__all__ = [
    "AuditError",
    "AuditRecord",
    "ENTRY_TYPES",
    "canonical_json",
    "compute_record_hash",
    "make_record",
    "payload_ref",
    "validate_append_inputs",
]

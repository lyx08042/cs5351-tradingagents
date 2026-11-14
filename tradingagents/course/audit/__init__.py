"""E leaf module: verifiable audit, decision revisions, offline gate replay.

Anchors: FR-005, INV-005, NFR-003, NFR-004, NFR-005. Design: ADR-003.

Public API (import with relative imports inside the package so the module can
run standalone as ``python -S -m audit --demo`` from ``tradingagents/course``):

- :class:`AuditRecord`, :class:`AuditStore`, :class:`AuditError`
- :func:`canonical_json`, :func:`payload_ref`
- :func:`replay_record`, :func:`replay_run`, :func:`verify_against_trusted_head`
- result types :class:`VerificationResult`, :class:`ReplayResult`, :class:`ReplayRunResult`

This package must not import other course leaf modules (evidence/budget/safety/
data_quality) and uses only the standard library (NFR-005). Run the demo with
``python -S -m audit --demo`` from this package's parent directory.
"""
from __future__ import annotations

from .records import (
    ENTRY_TYPES,
    AuditError,
    AuditRecord,
    canonical_json,
    compute_record_hash,
    payload_ref,
)
from .replay import (
    ReplayResult,
    ReplayRunResult,
    replay_record,
    replay_run,
    verify_against_trusted_head,
)
from .store import AuditStore, VerificationResult

__all__ = [
    "AuditError",
    "AuditRecord",
    "AuditStore",
    "ENTRY_TYPES",
    "ReplayResult",
    "ReplayRunResult",
    "VerificationResult",
    "canonical_json",
    "compute_record_hash",
    "payload_ref",
    "replay_record",
    "replay_run",
    "verify_against_trusted_head",
]

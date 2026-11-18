"""Shared CDE integration pipeline: D -> original AI graph -> C -> E.

Anchors: FR-003, FR-004, FR-005, INV-003, INV-004, INV-005, NFR-003, NFR-004,
NFR-005 and ADR-004. This module is a thin orchestrator, not a leaf: it may
import the data-quality (D), safety (C) and audit (E) leaves. The leaves never
import each other or this module, and ``tradingagents.course.__init__`` stays a
side-effect-free package marker.

The pipeline never contacts a broker, network or credential store. All inputs
are caller-supplied JSON-compatible values; the model is only asked for an
optional structured simulation proposal and is never an authority on balances,
snapshots, rule versions or approvals.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from decimal import Decimal
from types import MappingProxyType
from typing import Any

from tradingagents.course.audit import (
    AuditError,
    AuditStore,
    canonical_json,
)
from tradingagents.course.audit.records import validate_append_inputs
from tradingagents.course.data_quality.admission import admit
from tradingagents.course.safety import RuleSet, SafetyContext, validate_proposal

#: The only trusted rule catalogue entry. A request naming any other version is
#: not silently upgraded into a supported rule set; C rejects it as unknown. The
#: mapping is read-only so a caller cannot mutate the process-wide policy.
V1_RULE_VERSION = "cde-long-only-v1"
RULE_CATALOG: Mapping[str, RuleSet] = MappingProxyType(
    {V1_RULE_VERSION: RuleSet(version=V1_RULE_VERSION, long_only=True)}
)

#: Stable E gate id whose callback is registered below (ADR-004 §2.7).
GATE_ID = "cde.pipeline.final"

_REQUIRED_REQUEST_FIELDS = (
    "run_id",
    "timestamp",
    "analysis_cutoff",
    "observations",
    "holdings_snapshot",
    "instrument",
    "instrument_currency",
    "rule_version",
    "audit_path",
)


class CourseIntegrationError(Exception):
    """Base class for fail-closed CDE integration errors (ADR-004 §2.8)."""


class CourseRequestError(CourseIntegrationError):
    """A course request is structurally invalid; the model must not be called."""


class CourseConflictError(CourseIntegrationError):
    """The same run id already has a different terminal record (ADR-004 §2.8)."""


class CourseAuditError(CourseIntegrationError):
    """E could not persist the aggregate gate record; nothing is published."""


class CourseExecutionError(CourseIntegrationError):
    """The original AI graph failed; the failure is never reported as success."""


class CourseCheckpointUnsupported(CourseIntegrationError):
    """Course mode cannot resume a checkpoint built without course context."""


def _require_text(data: Mapping[str, Any], field: str) -> str:
    value = data.get(field)
    if not isinstance(value, str) or not value.strip():
        raise CourseRequestError(f"{field} must be a non-empty string")
    return value


def _json_clone(value: Any) -> Any:
    """Return a JSON-native copy, rejecting values E cannot store verbatim."""
    if isinstance(value, Decimal):
        return str(value)
    if value is None or isinstance(value, str | bool | int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise CourseRequestError("non-finite floats are not valid course inputs")
        return value
    if isinstance(value, tuple):
        return [_json_clone(item) for item in value]
    if isinstance(value, list):
        return [_json_clone(item) for item in value]
    if isinstance(value, Mapping):
        cloned: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise CourseRequestError("course input object keys must be strings")
            cloned[key] = _json_clone(item)
        return cloned
    raise CourseRequestError(f"unsupported course input type: {type(value).__name__}")


def _amount_string(value: Any) -> Any:
    """Money/quantity values are stored as decimal strings (ADR-004 §2.8)."""
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, int | float):
        return str(value)
    return value


@dataclass(frozen=True)
class CourseRequest:
    """Explicit trusted inputs for one course run (ADR-004 §2.2).

    All fields come from the caller. The holdings snapshot and rule version are
    the only authority for balances and rules; the model never supplies them.
    ``analysis_cutoff`` is also the run date used by the graph in course mode.
    """

    run_id: str
    timestamp: str
    analysis_cutoff: str
    observations: tuple[Mapping[str, Any], ...]
    holdings_snapshot: Mapping[str, Any]
    instrument: str
    instrument_currency: str
    rule_version: str
    audit_path: str

    @classmethod
    def from_mapping(cls, data: Any) -> CourseRequest:
        """Parse a caller mapping, failing closed on missing or invalid fields."""
        if not isinstance(data, Mapping):
            raise CourseRequestError("course request must be a JSON object")
        missing = [field for field in _REQUIRED_REQUEST_FIELDS if field not in data]
        if missing:
            raise CourseRequestError(f"course request missing fields: {', '.join(missing)}")

        observations_raw = data["observations"]
        if not isinstance(observations_raw, list | tuple):
            raise CourseRequestError("observations must be a list")
        observations: list[Mapping[str, Any]] = []
        for item in observations_raw:
            if not isinstance(item, Mapping):
                raise CourseRequestError("each observation must be an object")
            observations.append(_json_clone(dict(item)))

        snapshot_raw = data["holdings_snapshot"]
        if not isinstance(snapshot_raw, Mapping):
            raise CourseRequestError("holdings_snapshot must be a JSON object")

        return cls(
            run_id=_require_text(data, "run_id"),
            timestamp=_require_text(data, "timestamp"),
            analysis_cutoff=_require_text(data, "analysis_cutoff"),
            observations=tuple(observations),
            holdings_snapshot=_json_clone(dict(snapshot_raw)),
            instrument=_require_text(data, "instrument"),
            instrument_currency=_require_text(data, "instrument_currency"),
            rule_version=_require_text(data, "rule_version"),
            audit_path=_require_text(data, "audit_path"),
        )

    def to_dict(self) -> dict[str, Any]:
        """Return the JSON-native request form (amounts stay as supplied)."""
        return {
            "run_id": self.run_id,
            "timestamp": self.timestamp,
            "analysis_cutoff": self.analysis_cutoff,
            "observations": [_json_clone(dict(item)) for item in self.observations],
            "holdings_snapshot": _json_clone(dict(self.holdings_snapshot)),
            "instrument": self.instrument,
            "instrument_currency": self.instrument_currency,
            "rule_version": self.rule_version,
            "audit_path": self.audit_path,
        }

    def frozen_copy(self) -> CourseRequest:
        """Re-validate and deep-copy before the model can run (ADR-004 §2.8).

        A mutable mapping handed to :func:`run_course` must not let the model
        callback change the snapshot or observations that C and E will judge
        and record. The copy is built from the JSON-native form and passed
        through the same structural validation as a fresh request.
        """
        return CourseRequest.from_mapping(self.to_dict())


@dataclass(frozen=True)
class CourseResult:
    """Deterministic outcome of one course run (ADR-004 §2.6-§2.7).

    ``published`` is true only for a C-accepted, non-Hold proposal. ``signal``
    is derived from the safety outcome, never from the model's prose rating.
    """

    run_id: str
    outcome: str
    entry_type: str
    published: bool
    proposal: dict[str, Any] | None
    admission: dict[str, Any]
    safety: dict[str, Any] | None
    audit_record_id: str
    signal: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "outcome": self.outcome,
            "entry_type": self.entry_type,
            "published": self.published,
            "proposal": self.proposal,
            "admission": self.admission,
            "safety": self.safety,
            "audit_record_id": self.audit_record_id,
            "signal": self.signal,
        }


def _snapshot_input(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    """JSON-native trusted snapshot with money/quantity as decimal strings."""
    cloned = _json_clone(dict(snapshot))
    if "cash" in cloned:
        cloned["cash"] = _amount_string(cloned["cash"])
    positions = cloned.get("positions")
    if isinstance(positions, Mapping):
        cloned["positions"] = {
            str(symbol): _amount_string(quantity) for symbol, quantity in positions.items()
        }
    return cloned


def _normalise_candidate(candidate: Mapping[str, Any] | None) -> dict[str, Any] | None:
    """Keep model fields, including extra intent C must inspect (ADR-004 §2.8).

    Only the trusted reference fields are dropped: the orchestrator binds the
    real snapshot id and rule version. Unknown/extras such as ``execution_mode``
    or ``real_execution`` are preserved so C can reject real-execution intent
    instead of having this layer silently erase it.
    """
    if not isinstance(candidate, Mapping):
        return None
    trusted_fields = {"holdings_snapshot", "rule_version"}
    normalised: dict[str, Any] = {}
    for key, value in candidate.items():
        if key in trusted_fields:
            continue
        if not isinstance(key, str):
            raise CourseRequestError("candidate object keys must be strings")
        normalised[key] = _json_clone(value)
    normalised["action"] = candidate.get("action")
    normalised["units"] = _amount_string(candidate.get("units"))
    normalised["price"] = _amount_string(candidate.get("price"))
    normalised["currency"] = candidate.get("currency")
    return normalised


def build_gate_inputs(
    request: CourseRequest, candidate: Mapping[str, Any] | None = None
) -> dict[str, Any]:
    """Build the E replay inputs from trusted request data and the candidate.

    Anchors: FR-003, FR-004, FR-005, NFR-003, ADR-004 §2.7. The snapshot stays
    the caller's trusted one; the candidate contributes only action/units/price/
    currency. Snapshot id and rule version are bound by this orchestrator.
    """
    return {
        "analysis_cutoff": request.analysis_cutoff,
        "observations": [_json_clone(dict(item)) for item in request.observations],
        "holdings_snapshot": _snapshot_input(request.holdings_snapshot),
        "instrument": request.instrument,
        "instrument_currency": request.instrument_currency,
        "rule_version": request.rule_version,
        "candidate": _normalise_candidate(candidate),
    }


def _snapshot_id(inputs: Mapping[str, Any]) -> str | None:
    snapshot = inputs.get("holdings_snapshot")
    if isinstance(snapshot, Mapping):
        value = snapshot.get("snapshot_id")
        if isinstance(value, str) and value.strip():
            return value
    return None


def _holdings_for_context(snapshot: Any) -> Any:
    """Pass the trusted snapshot through; C owns parsing and missing-field rules.

    In particular, a missing ``positions`` key must stay missing: filling it
    with ``{}`` would turn an incomplete snapshot into a declared flat account.
    """
    return snapshot if isinstance(snapshot, Mapping) else None


def _context_from_inputs(inputs: Mapping[str, Any]) -> SafetyContext | None:
    """Rebuild C's trusted context; an invalid shape is rejected by C, not raised."""
    try:
        return SafetyContext(
            instrument=inputs.get("instrument"),
            instrument_currency=inputs.get("instrument_currency"),
            holdings_snapshot=_holdings_for_context(inputs.get("holdings_snapshot")),
            rule_set=RULE_CATALOG.get(inputs.get("rule_version")),
            available_rule_versions=frozenset(RULE_CATALOG),
        )
    except (TypeError, ValueError):
        return None


def _proposal_from_inputs(inputs: Mapping[str, Any]) -> dict[str, Any]:
    candidate = inputs.get("candidate")
    if not isinstance(candidate, Mapping):
        candidate = {}
    proposal = {key: _json_clone(value) for key, value in candidate.items()}
    proposal.update(
        {
            "action": candidate.get("action"),
            "units": candidate.get("units"),
            "price": candidate.get("price"),
            "currency": candidate.get("currency"),
            "holdings_snapshot": _snapshot_id(inputs),
            "rule_version": inputs.get("rule_version"),
        }
    )
    return proposal


def _published_proposal(
    inputs: Mapping[str, Any], safety: Any
) -> dict[str, Any]:
    candidate = inputs.get("candidate")
    if not isinstance(candidate, Mapping):
        candidate = {}
    return {
        "action": safety.action,
        "units": _amount_string(candidate.get("units")),
        "price": _amount_string(candidate.get("price")),
        "currency": candidate.get("currency"),
        "holdings_snapshot": safety.snapshot_id,
        "rule_version": safety.rule_version,
    }


def _signal_for(observed: Mapping[str, Any]) -> str:
    """Derive the returned rating from the deterministic outcome (ADR-004 §2.6)."""
    outcome = observed.get("outcome")
    if outcome == "hold":
        return "Hold"
    if outcome == "accepted":
        proposal = observed.get("proposal")
        action = proposal.get("action") if isinstance(proposal, Mapping) else None
        return {"buy": "Buy", "sell": "Sell"}.get(action, "REVIEW")
    return "REVIEW"


def _evaluate(inputs: Mapping[str, Any]) -> tuple[str, dict[str, Any]]:
    """Pure D+C evaluation shared by live runs and E replay (ADR-004 §2.7).

    Returns ``(entry_type, observed)``. It never calls the model or reads the
    store, so the same inputs reproduce the same observed payload.
    """
    admission = admit(list(inputs.get("observations") or []), inputs.get("analysis_cutoff", ""))
    admission_dict = admission.to_dict()

    if admission.decision != "proceed":
        outcome = "abstain" if admission.decision == "abstain" else "review"
        entry_type = "abstain" if admission.decision == "abstain" else "rejection"
        return entry_type, {
            "outcome": outcome,
            "data_quality": admission_dict,
            "safety": None,
            "published": False,
            "proposal": None,
        }

    safety = validate_proposal(
        _proposal_from_inputs(inputs), context=_context_from_inputs(inputs)
    )
    safety_dict = safety.to_dict()
    if not safety.accepted:
        return "rejection", {
            "outcome": "rejected",
            "data_quality": admission_dict,
            "safety": safety_dict,
            "published": False,
            "proposal": None,
        }

    if safety.is_noop:
        return "decision", {
            "outcome": "hold",
            "data_quality": admission_dict,
            "safety": safety_dict,
            "published": False,
            "proposal": None,
        }

    return "decision", {
        "outcome": "accepted",
        "data_quality": admission_dict,
        "safety": safety_dict,
        "published": True,
        "proposal": _published_proposal(inputs, safety),
    }


def _replay_callback(inputs: Any) -> dict[str, Any]:
    """E registry callback: recompute D+C from inputs, without model or store."""
    if not isinstance(inputs, Mapping):
        raise CourseRequestError("replay inputs must be an object")
    _entry_type, observed = _evaluate(inputs)
    return observed


def gate_registry() -> dict[str, dict[str, Callable[[Any], Any]]]:
    """Return the program-fixed E replay registry (ADR-004 §2.7).

    Anchors: FR-005, INV-005, NFR-003. Only the trusted v1 rule version is
    registered; any other recorded version replayed by E becomes ``review``.
    """
    return {GATE_ID: {V1_RULE_VERSION: _replay_callback}}


def course_context(request: CourseRequest) -> str:
    """Prompt context for the PM candidate, with no authoritative balances."""
    return (
        "Course simulation mode (deterministic CDE pipeline).\n"
        f"Instrument: {request.instrument}; quote currency: {request.instrument_currency}; "
        f"analysis cutoff: {request.analysis_cutoff}.\n"
        "Also fill simulation_proposal using action (buy/sell/hold), units "
        "(an absolute positive decimal string; 0 only for hold), price (an absolute "
        "decimal string), and currency. Do not read, state or infer account "
        "balances or holdings: they are not authoritative and are supplied "
        "separately by the caller. Do not include snapshot ids, rule versions or "
        "any approval/release flag."
    )


def _is_memory_audit_path(path: str) -> bool:
    """True for SQLite in-memory targets, which cannot persist a verifiable record."""
    value = path.strip().lower()
    if value == ":memory:":
        return True
    if value.startswith("file::memory:"):
        return True
    return value.startswith("file:") and "mode=memory" in value


def _validate_request_audit_fields(request: CourseRequest) -> None:
    """Reject invalid audit metadata before the model is called (ADR-004 §2.8)."""
    if _is_memory_audit_path(request.audit_path):
        raise CourseRequestError(
            "audit_path must be a persistent file path, not an in-memory SQLite database"
        )
    try:
        validate_append_inputs(
            record_id=f"cde:{request.run_id}",
            run_id=request.run_id,
            timestamp=request.timestamp,
            entry_type="rejection",
            payload={},
            rules_version=request.rule_version,
            supersedes=None,
        )
    except AuditError as exc:
        raise CourseRequestError(f"invalid audit metadata: {exc.message}") from exc


def _append_gate(
    request: CourseRequest,
    entry_type: str,
    inputs: Mapping[str, Any],
    observed: Mapping[str, Any],
) -> str:
    """Persist the single aggregate gate record; failure never becomes success."""
    payload = {
        "gate_id": GATE_ID,
        "rules_version": request.rule_version,
        "inputs": _json_clone(dict(inputs)),
        "observed": _json_clone(dict(observed)),
    }
    record_id = f"cde:{request.run_id}"
    try:
        store = AuditStore.open(request.audit_path)
    except Exception as exc:  # noqa: BLE001 - fail closed at the audit boundary.
        raise CourseAuditError(f"could not open audit store: {type(exc).__name__}") from exc

    try:
        try:
            record = store.append(
                record_id=record_id,
                run_id=request.run_id,
                timestamp=request.timestamp,
                entry_type=entry_type,
                payload=payload,
                rules_version=request.rule_version,
            )
            return record.record_id
        except AuditError as exc:
            if exc.code not in {"duplicate_record_id", "duplicate_decision"}:
                raise CourseAuditError(f"audit append failed: {exc.code}") from exc
            existing = store.get(record_id)
            if existing is not None and canonical_json(existing.payload) == canonical_json(payload):
                return existing.record_id
            raise CourseConflictError(
                f"run {request.run_id!r} already has a different terminal record"
            ) from exc
        except Exception as exc:  # noqa: BLE001 - storage failure is fail-closed.
            raise CourseAuditError(f"audit append failed: {type(exc).__name__}") from exc
    finally:
        store.close()


def _result(
    request: CourseRequest, entry_type: str, observed: Mapping[str, Any], record_id: str
) -> CourseResult:
    return CourseResult(
        run_id=request.run_id,
        outcome=str(observed["outcome"]),
        entry_type=entry_type,
        published=bool(observed["published"]),
        proposal=observed.get("proposal"),
        admission=observed["data_quality"],
        safety=observed.get("safety"),
        audit_record_id=record_id,
        signal=_signal_for(observed),
    )


def run_course(
    request: CourseRequest | Mapping[str, Any],
    invoke_ai: Callable[[str], Mapping[str, Any]],
) -> CourseResult:
    """Run D -> AI candidate -> C -> E for one course request (ADR-004 §2.2).

    Anchors: FR-003, FR-004, FR-005, INV-003, INV-004, INV-005, NFR-003,
    NFR-004, NFR-005. D runs before the model; a D non-proceed result ends the
    run with an audit record and zero model calls. C is the only publish gate.
    The audit record is written before any result is returned; a write failure
    raises and publishes nothing.
    """
    if isinstance(request, CourseRequest):
        request = request.frozen_copy()
    else:
        request = CourseRequest.from_mapping(request)
    _validate_request_audit_fields(request)

    pre_admission = admit(list(request.observations), request.analysis_cutoff)
    candidate: Mapping[str, Any] | None = None
    if pre_admission.decision == "proceed":
        try:
            final_state = invoke_ai(course_context(request))
        except Exception as exc:  # noqa: BLE001 - never report a model failure as a result.
            raise CourseExecutionError(
                f"course analysis failed before C: {type(exc).__name__}"
            ) from exc
        raw = final_state.get("simulation_proposal") if isinstance(final_state, Mapping) else None
        candidate = raw if isinstance(raw, Mapping) else None

    inputs = build_gate_inputs(request, candidate)
    entry_type, observed = _evaluate(inputs)
    record_id = _append_gate(request, entry_type, inputs, observed)
    return _result(request, entry_type, observed, record_id)


__all__ = [
    "GATE_ID",
    "RULE_CATALOG",
    "V1_RULE_VERSION",
    "CourseAuditError",
    "CourseCheckpointUnsupported",
    "CourseConflictError",
    "CourseExecutionError",
    "CourseIntegrationError",
    "CourseRequest",
    "CourseRequestError",
    "CourseResult",
    "build_gate_inputs",
    "course_context",
    "gate_registry",
    "run_course",
]

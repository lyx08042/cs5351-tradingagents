"""Evidence-to-debate integration helpers (FR-001 / INV-001 / ADR-005 / ADR-006).

This module is the M3 boundary between the trusted, run-scoped M2 evidence leaf and
the bull/bear debate. It validates a JSON evidence snapshot, builds a read-only
admissible catalog for the model prompt, and turns a model ``{"claims": [...]}``
response into sanitized debate history plus a plain-JSON audit record. The model is
never trusted as an evidence source, and no raw model text reaches accepted
projection or abstention output.
"""

from __future__ import annotations

import json
import math
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date

from .claims import (
    EVIDENCE_SUPPORTS_FACTUAL_CLAIM,
    FORECAST_REQUIRES_HYPOTHESIS_LABEL,
    NO_REFERENCE,
    NO_STRUCTURED_FACT,
    UNCLASSIFIED,
    UNRELATED,
    Claim,
    ClaimVerdict,
    RejectedRef,
    verify_claim,
)
from .contracts import (
    ACCEPT,
    CONFLICTING_ID,
    FOREIGN_REFERENCE,
    FUTURE_LEAKAGE,
    INVALID_AS_OF,
    INVALID_DATE,
    INVALID_POLICY,
    INVALID_STATUS,
    MALFORMED,
    MISSING_DATE,
    NEUTRAL_STATUS,
    NON_FINITE_VALUE,
    POLICY_MISMATCH,
    STALE,
    UNAVAILABLE_STATUS,
    UNKNOWN_REFERENCE,
    UNKNOWN_STATUS,
    UNSUPPORTED_VALUE_TYPE,
    UNTRUSTED,
    EvidenceRegistry,
    Fact,
    FreshnessPolicy,
)

PROCEED = "proceed"
REVIEW = "REVIEW"
ACCEPT_FACTUAL = "accept_factual"
HYPOTHESIS = "hypothesis"
ABSTAIN = "abstain"

INVALID_CONTEXT = "invalid_context"
CONTEXT_DATE_MISMATCH = "context_date_mismatch"
NON_PROCEED = "non_proceed"
DUPLICATE_KEY = "duplicate_key"
UNKNOWN_FIELD = "unknown_field"
MALFORMED_RESPONSE = "malformed_response"
NO_CLAIMS = "no_claims"
INVALID_CLAIM_ID = "invalid"

SPEAKERS = {"bull": "Bull Analyst", "bear": "Bear Analyst"}

_ENVELOPE_KEYS = frozenset({"as_of", "registry", "policy"})
_OPTIONAL_KEYS = frozenset({"data_admission_decision"})
_CLAIM_KEYS = frozenset({"claim_id", "text", "classification", "fact", "evidence_refs"})
_CLAIM_REQUIRED = frozenset({"claim_id", "text", "classification", "evidence_refs"})
_REGISTRY_REQUIRED = frozenset({"run_id", "as_of", "units"})
_REGISTRY_KEYS = frozenset({"run_id", "as_of", "units", "quarantine"})
_UNIT_REQUIRED = frozenset({"evidence_id", "run_id", "source", "content_ref", "status", "fact"})
_UNIT_KEYS = frozenset(
    {
        "evidence_id",
        "run_id",
        "source",
        "content_ref",
        "status",
        "published_at",
        "available_as_of",
        "fact",
        "freshness_policy",
    }
)
_QUARANTINE_KEYS = frozenset({"conflicted", "foreign", "malformed"})
_POLICY_KEYS = frozenset({"name", "max_age_days"})
_AUDIT_KEYS = frozenset({"speaker", "round", "verdicts", "rejected_refs", "as_of", "run_id"})
_ALLOWED_VERDICTS = frozenset({ACCEPT_FACTUAL, HYPOTHESIS, ABSTAIN})
_SAFE_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,63}\Z")
_DATE_RE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}\Z")
_SAFE_REASONS = frozenset(
    {
        CONFLICTING_ID,
        FOREIGN_REFERENCE,
        FUTURE_LEAKAGE,
        INVALID_AS_OF,
        INVALID_DATE,
        INVALID_POLICY,
        INVALID_STATUS,
        MALFORMED,
        MISSING_DATE,
        NEUTRAL_STATUS,
        NON_FINITE_VALUE,
        POLICY_MISMATCH,
        STALE,
        UNAVAILABLE_STATUS,
        UNKNOWN_REFERENCE,
        UNKNOWN_STATUS,
        UNSUPPORTED_VALUE_TYPE,
        UNTRUSTED,
        EVIDENCE_SUPPORTS_FACTUAL_CLAIM,
        FORECAST_REQUIRES_HYPOTHESIS_LABEL,
        NO_REFERENCE,
        NO_STRUCTURED_FACT,
        UNCLASSIFIED,
        UNRELATED,
        INVALID_CONTEXT,
        CONTEXT_DATE_MISMATCH,
        NON_PROCEED,
        DUPLICATE_KEY,
        UNKNOWN_FIELD,
        MALFORMED_RESPONSE,
        NO_CLAIMS,
    }
)

_PROMPT_INSTRUCTIONS = (
    "Cite only evidence_id values from the admissible evidence list. Return exactly one "
    "JSON object: {\"claims\": [...]}, with no prose. Each claim may contain only "
    "claim_id, text, classification, fact and evidence_refs; never include evidence "
    "records or any other field."
)


def _safe_reason(value: object) -> str:
    """Return a controlled reason code for FR-001 / INV-001 / ADR-005 / ADR-006."""
    if type(value) is str and value in _SAFE_REASONS:
        return value
    return MALFORMED


def _safe_reasons(values: object) -> list[str]:
    """Normalize a reason collection for FR-001 / INV-001 / ADR-005 / ADR-006."""
    if not isinstance(values, (list, tuple)):
        return [MALFORMED]
    result = [_safe_reason(item) for item in values]
    return result or [MALFORMED]


def _canonical_date(value: object) -> str | None:
    """Return a strict YYYY-MM-DD date for FR-001 / INV-001 / ADR-005 / ADR-006."""
    if type(value) is not str or _DATE_RE.fullmatch(value) is None:
        return None
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        return None
    if parsed.isoformat() != value:
        return None
    return value


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    """Reject duplicate JSON object keys for FR-001 / INV-001 / ADR-005 / ADR-006."""
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(DUPLICATE_KEY)
        result[key] = value
    return result


def _reject_constant(_token: str) -> object:
    """Reject NaN and Infinity JSON constants for FR-001 / INV-001 / ADR-005 / ADR-006."""
    raise ValueError(MALFORMED)


def _strict_json_loads(text: str) -> object:
    """Parse strict JSON for FR-001 / INV-001 / ADR-005 / ADR-006."""
    return json.loads(
        text,
        object_pairs_hook=_reject_duplicate_keys,
        parse_constant=_reject_constant,
    )


def _plain_json_problem(value: object, active: set[int] | None = None) -> str | None:
    """Return a stable reason when value is not plain JSON (FR-001 / INV-001 / ADR-005 / ADR-006)."""
    if active is None:
        active = set()
    if value is None or type(value) is bool or type(value) is int:
        return None
    if type(value) is float:
        return None if math.isfinite(value) else NON_FINITE_VALUE
    if type(value) is str:
        try:
            value.encode("utf-8")
        except UnicodeEncodeError:
            return MALFORMED
        return None
    if type(value) is list:
        marker = id(value)
        if marker in active:
            return MALFORMED
        active.add(marker)
        try:
            for item in value:
                problem = _plain_json_problem(item, active)
                if problem is not None:
                    return problem
        finally:
            active.discard(marker)
        return None
    if type(value) is dict:
        marker = id(value)
        if marker in active:
            return MALFORMED
        active.add(marker)
        try:
            for key, item in value.items():
                if type(key) is not str:
                    return MALFORMED
                try:
                    key.encode("utf-8")
                except UnicodeEncodeError:
                    return MALFORMED
                problem = _plain_json_problem(item, active)
                if problem is not None:
                    return problem
        finally:
            active.discard(marker)
        return None
    return MALFORMED


def _dump_json(value: object) -> str:
    """Serialize deterministic plain JSON for FR-001 / INV-001 / ADR-005 / ADR-006."""
    return json.dumps(value, sort_keys=True, allow_nan=False, separators=(",", ":"))


def _plain_json(value: object) -> dict:
    """Round-trip a value to strict plain JSON for FR-001 / INV-001 / ADR-005 / ADR-006."""
    return json.loads(_dump_json(value))


def _response_text(response: object) -> str | None:
    """Return model response text only for FR-001 / INV-001 / ADR-005 / ADR-006."""
    if type(response) is str:
        return response
    content = getattr(response, "content", None)
    if type(content) is str:
        return content
    return None


def _generated_claim_id(index: int) -> str:
    """Return a deterministic safe id for FR-001 / INV-001 / ADR-005 / ADR-006."""
    return f"claim-{index:04d}"


def _sanitise_claim_id(raw: object, index: int) -> str:
    """Constrain or replace a claim id for FR-001 / INV-001 / ADR-005 / ADR-006."""
    if type(raw) is str and _SAFE_ID_RE.fullmatch(raw) is not None:
        return raw
    return _generated_claim_id(index)


def _safe_history_id(raw: object) -> str:
    """Return an id safe for debate history for FR-001 / INV-001 / ADR-005 / ADR-006."""
    if type(raw) is str and _SAFE_ID_RE.fullmatch(raw) is not None:
        return raw
    return INVALID_CLAIM_ID


def _valid_registry_shape(data: Mapping) -> bool:
    """Check the serialized registry keys for FR-001 / INV-001 / ADR-005 / ADR-006."""
    keys = set(data.keys())
    if not keys.issuperset(_REGISTRY_REQUIRED) or not keys.issubset(_REGISTRY_KEYS):
        return False
    units = data.get("units")
    if type(units) is not list:
        return False
    for unit in units:
        if not isinstance(unit, Mapping):
            return False
        unit_keys = set(unit.keys())
        if not unit_keys.issuperset(_UNIT_REQUIRED) or not unit_keys.issubset(_UNIT_KEYS):
            return False
    quarantine = data.get("quarantine", {})
    if not isinstance(quarantine, Mapping):
        return False
    return set(quarantine.keys()).issubset(_QUARANTINE_KEYS)


def _safe_evidence_id(value: object) -> str:
    """Return an audit evidence id for FR-001 / INV-001 / ADR-005 / ADR-006."""
    if type(value) is not str:
        return ""
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        return ""
    return value


def _reason_from_exception(exc: BaseException) -> str:
    """Map a validation failure to a controlled code for FR-001 / INV-001 / ADR-005 / ADR-006."""
    if exc.args:
        candidate = exc.args[0]
        if type(candidate) is str and candidate in _SAFE_REASONS:
            return candidate
    return MALFORMED_RESPONSE


@dataclass(frozen=True)
class EvidenceContext:
    """Immutable accepted evidence snapshot for FR-001 / INV-001 / ADR-005 / ADR-006."""

    as_of: str
    trade_date: str
    registry: EvidenceRegistry
    policy: FreshnessPolicy
    decision: str | None = None

    @property
    def run_id(self) -> str:
        """Return the run id of the evidence snapshot (FR-001 / INV-001 / ADR-005 / ADR-006)."""
        return self.registry.run_id

    def to_dict(self) -> dict:
        """Return a plain JSON snapshot for FR-001 / INV-001 / ADR-005 / ADR-006."""
        payload = {
            "as_of": self.as_of,
            "registry": self.registry.to_dict(),
            "policy": self.policy.to_dict(),
        }
        if self.decision is not None:
            payload["data_admission_decision"] = self.decision
        return _plain_json(payload)


@dataclass(frozen=True)
class CatalogEntry:
    """One read-only admissible prompt record for FR-001 / INV-001 / ADR-005 / ADR-006."""

    evidence_id: str
    as_of: str
    source: str
    content_ref: str
    fact: Fact

    def to_dict(self) -> dict:
        """Return a plain JSON catalog item for FR-001 / INV-001 / ADR-005 / ADR-006."""
        return _plain_json(
            {
                "as_of": self.as_of,
                "content_ref": self.content_ref,
                "evidence_id": self.evidence_id,
                "fact": self.fact.to_dict(),
                "source": self.source,
            }
        )


@dataclass(frozen=True)
class ContextResolution:
    """Outcome of evidence-context validation for FR-001 / INV-001 / ADR-005 / ADR-006."""

    context: EvidenceContext | None
    allowed: bool
    reason: str | None = None

    def to_dict(self) -> dict:
        """Return a plain JSON resolution for FR-001 / INV-001 / ADR-005 / ADR-006."""
        return _plain_json(
            {
                "allowed": self.allowed,
                "reason": self.reason,
            }
        )

    @property
    def decision(self) -> str:
        """Return the graph decision for FR-001 / INV-001 / ADR-005 / ADR-006."""
        return PROCEED if self.allowed else REVIEW


@dataclass(frozen=True)
class ResearcherTurn:
    """One sanitized researcher turn for FR-001 / INV-001 / ADR-005 / ADR-006."""

    speaker: str
    round_index: int
    history: str
    verdicts: tuple[ClaimVerdict, ...]
    rejected_refs: tuple[RejectedRef, ...] = ()
    as_of: str = ""
    run_id: str = ""

    @property
    def speaker_label(self) -> str:
        """Return the fixed speaker label for FR-001 / INV-001 / ADR-005 / ADR-006."""
        return SPEAKERS.get(self.speaker, "")

    @property
    def response(self) -> str:
        """Return prefixed debate text for FR-001 / INV-001 / ADR-005 / ADR-006."""
        label = self.speaker_label
        if not label:
            return self.history
        return f"{label}: {self.history}"

    def audit_record(self) -> dict:
        """Return a strict plain-JSON audit record for FR-001 / INV-001 / ADR-005 / ADR-006."""
        payload = {
            "as_of": self.as_of,
            "rejected_refs": [
                {
                    "evidence_id": _safe_evidence_id(item.to_dict().get("evidence_id")),
                    "reasons": _safe_reasons(item.to_dict().get("reasons")),
                }
                for item in self.rejected_refs
            ],
            "round": self.round_index,
            "run_id": self.run_id,
            "speaker": self.speaker,
            "verdicts": [_verdict_record(item) for item in self.verdicts],
        }
        return _plain_json(payload)

    def audit_json(self) -> str:
        """Return the audit record as strict JSON for FR-001 / INV-001 / ADR-005 / ADR-006."""
        return _dump_json(self.audit_record())


class EvidenceContextError(ValueError):
    """Raised with a controlled reason for FR-001 / INV-001 / ADR-005 / ADR-006."""

    def __init__(self, reason: str) -> None:
        """Store the controlled reason for FR-001 / INV-001 / ADR-005 / ADR-006."""
        self.reason = _safe_reason(reason)
        super().__init__(self.reason)


def _verdict_record(verdict: ClaimVerdict) -> dict:
    """Sanitize one M2 verdict for FR-001 / INV-001 / ADR-005 / ADR-006."""
    record = verdict.to_dict()
    record["claim_id"] = _safe_history_id(record.get("claim_id"))
    record["reasons"] = _safe_reasons(record.get("reasons"))
    verdict_name = record.get("verdict")
    if type(verdict_name) is not str or verdict_name not in _ALLOWED_VERDICTS:
        record["verdict"] = ABSTAIN
    refs = record.get("rejected_refs")
    clean_refs = []
    if isinstance(refs, list):
        for item in refs:
            if isinstance(item, Mapping):
                clean_refs.append(
                    {
                        "evidence_id": _safe_evidence_id(item.get("evidence_id")),
                        "reasons": _safe_reasons(item.get("reasons")),
                    }
                )
    record["rejected_refs"] = clean_refs
    return record


def resolve_evidence_context(
    evidence_context: object,
    *,
    trade_date: object,
) -> ContextResolution:
    """Validate a JSON evidence snapshot for FR-001 / INV-001 / ADR-005 / ADR-006."""
    canonical = _canonical_date(trade_date)
    if canonical is None:
        return ContextResolution(None, False, CONTEXT_DATE_MISMATCH)
    if not isinstance(evidence_context, Mapping):
        return ContextResolution(None, False, INVALID_CONTEXT)
    if "data_admission_decision" in evidence_context:
        raw_decision = evidence_context.get("data_admission_decision")
        if type(raw_decision) is not str or raw_decision != PROCEED:
            return ContextResolution(None, False, NON_PROCEED)
    keys = frozenset(evidence_context.keys())
    if not keys.issuperset(_ENVELOPE_KEYS) or not keys.issubset(
        _ENVELOPE_KEYS | _OPTIONAL_KEYS
    ):
        return ContextResolution(None, False, INVALID_CONTEXT)
    try:
        problem = _plain_json_problem(evidence_context)
    except RecursionError:
        return ContextResolution(None, False, INVALID_CONTEXT)
    if problem is not None:
        return ContextResolution(None, False, INVALID_CONTEXT)
    as_of = _canonical_date(evidence_context.get("as_of"))
    if as_of is None or as_of != canonical:
        return ContextResolution(None, False, CONTEXT_DATE_MISMATCH)
    registry_data = evidence_context.get("registry")
    if not isinstance(registry_data, Mapping) or not _valid_registry_shape(registry_data):
        return ContextResolution(None, False, INVALID_CONTEXT)
    if _canonical_date(registry_data.get("as_of")) != canonical:
        return ContextResolution(None, False, CONTEXT_DATE_MISMATCH)
    try:
        registry = EvidenceRegistry.from_dict(registry_data)
    except (KeyError, ValueError, TypeError):
        return ContextResolution(None, False, INVALID_CONTEXT)
    if not isinstance(registry, EvidenceRegistry):
        return ContextResolution(None, False, INVALID_CONTEXT)
    if _canonical_date(registry.as_of) != canonical:
        return ContextResolution(None, False, CONTEXT_DATE_MISMATCH)
    policy_data = evidence_context.get("policy")
    if not isinstance(policy_data, Mapping) or set(policy_data.keys()) != _POLICY_KEYS:
        return ContextResolution(None, False, INVALID_CONTEXT)
    try:
        policy = FreshnessPolicy.from_record(policy_data)
        policy.to_dict()
    except (KeyError, ValueError, TypeError):
        return ContextResolution(None, False, INVALID_CONTEXT)
    decision: str | None = None
    if "data_admission_decision" in evidence_context:
        raw_decision = evidence_context.get("data_admission_decision")
        if raw_decision != PROCEED:
            return ContextResolution(None, False, NON_PROCEED)
        decision = PROCEED
    context = EvidenceContext(
        as_of=as_of,
        trade_date=canonical,
        registry=registry,
        policy=policy,
        decision=decision,
    )
    return ContextResolution(context, True, None)


def validate_evidence_context(
    evidence_context: object,
    *,
    trade_date: object,
) -> EvidenceContext:
    """Return the accepted context or raise a controlled error for FR-001 / INV-001 / ADR-005 / ADR-006."""
    resolution = resolve_evidence_context(evidence_context, trade_date=trade_date)
    if not resolution.allowed or resolution.context is None:
        raise EvidenceContextError(resolution.reason or INVALID_CONTEXT)
    return resolution.context


def preflight_turn(
    evidence_context: object,
    *,
    trade_date: object,
    speaker: str,
    round_index: int,
) -> tuple[EvidenceContext | None, ResearcherTurn | None]:
    """Return context or a sanitized abstention for FR-001 / INV-001 / ADR-005 / ADR-006."""
    resolution = resolve_evidence_context(evidence_context, trade_date=trade_date)
    if resolution.allowed and resolution.context is not None:
        return resolution.context, None
    canonical = _canonical_date(trade_date) or ""
    reason = resolution.reason or INVALID_CONTEXT
    return None, abstention_turn(
        speaker,
        round_index,
        reason,
        as_of=canonical,
        run_id="",
    )


def build_evidence_catalog(context: EvidenceContext) -> tuple[CatalogEntry, ...]:
    """Return only registry-admissible evidence for FR-001 / INV-001 / ADR-005 / ADR-006."""
    entries: list[CatalogEntry] = []
    for unit in context.registry.units:
        try:
            admission = context.registry.admissibility(unit.evidence_id, context.policy)
        except (KeyError, ValueError, TypeError):
            continue
        if admission.status != ACCEPT:
            continue
        entries.append(
            CatalogEntry(
                evidence_id=unit.evidence_id,
                as_of=context.as_of,
                source=unit.source,
                content_ref=unit.content_ref,
                fact=unit.fact,
            )
        )
    return tuple(sorted(entries, key=lambda entry: entry.evidence_id))


def prepare_prompt_section(context: EvidenceContext) -> str:
    """Build a delimited JSON prompt section for FR-001 / INV-001 / ADR-005 / ADR-006."""
    catalog = build_evidence_catalog(context)
    payload = {
        "admissible_as_of": context.as_of,
        "claim_fields": sorted(_CLAIM_KEYS),
        "evidence": [entry.to_dict() for entry in catalog],
        "instructions": _PROMPT_INSTRUCTIONS,
        "reference_field": "evidence_refs",
        "response_envelope": {"claims": "list"},
        "run_id": context.run_id,
    }
    return "EVIDENCE_CONTEXT_JSON\n" + _dump_json(payload) + "\nEND_EVIDENCE_CONTEXT_JSON"


def _parse_claims(text: str | None) -> tuple[list[Claim | ClaimVerdict], str | None]:
    """Parse the exact claims envelope for FR-001 / INV-001 / ADR-005 / ADR-006."""
    if text is None:
        return [], MALFORMED_RESPONSE
    stripped = text.strip()
    if not stripped:
        return [], MALFORMED_RESPONSE
    try:
        payload = _strict_json_loads(stripped)
        problem = _plain_json_problem(payload)
    except (ValueError, RecursionError) as exc:
        return [], _reason_from_exception(exc)
    if problem is not None:
        return [], problem
    if not isinstance(payload, Mapping):
        return [], MALFORMED_RESPONSE
    keys = set(payload.keys())
    if keys - {"claims"}:
        return [], UNKNOWN_FIELD
    if keys != {"claims"}:
        return [], MALFORMED_RESPONSE
    raw_claims = payload.get("claims")
    if type(raw_claims) is not list:
        return [], MALFORMED_RESPONSE
    if not raw_claims:
        return [], NO_CLAIMS
    items: list[Claim | ClaimVerdict] = []
    for index, record in enumerate(raw_claims):
        if not isinstance(record, Mapping):
            items.append(
                ClaimVerdict(_generated_claim_id(index), ABSTAIN, (MALFORMED,), (), ())
            )
            continue
        record_keys = set(record.keys())
        if not record_keys <= _CLAIM_KEYS:
            items.append(
                ClaimVerdict(
                    _sanitise_claim_id(record.get("claim_id"), index),
                    ABSTAIN,
                    (UNKNOWN_FIELD,),
                    (),
                    (),
                )
            )
            continue
        if not record_keys.issuperset(_CLAIM_REQUIRED):
            items.append(
                ClaimVerdict(
                    _sanitise_claim_id(record.get("claim_id"), index),
                    ABSTAIN,
                    (MALFORMED,),
                    (),
                    (),
                )
            )
            continue
        raw_id = record.get("claim_id")
        if type(raw_id) is not str or _SAFE_ID_RE.fullmatch(raw_id) is None:
            items.append(
                ClaimVerdict(_generated_claim_id(index), ABSTAIN, (UNTRUSTED,), (), ())
            )
            continue
        try:
            items.append(Claim.from_record(record))
        except ValueError as exc:
            items.append(
                ClaimVerdict(
                    _sanitise_claim_id(raw_id, index),
                    ABSTAIN,
                    (_reason_from_exception(exc),),
                    (),
                    (),
                )
            )
        except TypeError:
            items.append(
                ClaimVerdict(
                    _sanitise_claim_id(raw_id, index),
                    ABSTAIN,
                    (MALFORMED,),
                    (),
                    (),
                )
            )
    return items, None


def _history_line(verdict: ClaimVerdict) -> str:
    """Render one sanitized verdict line for FR-001 / INV-001 / ADR-005 / ADR-006."""
    claim_id = _safe_history_id(verdict.claim_id)
    if verdict.verdict == ACCEPT_FACTUAL:
        references = [item for item in verdict.evidence_refs if type(item) is str]
        projection = [item.to_dict() for item in verdict.projection if isinstance(item, Fact)]
        return (
            "[FACT | claim_id="
            + claim_id
            + " | evidence_refs="
            + _dump_json(references)
            + " | projection="
            + _dump_json(projection)
            + "]"
        )
    reasons = _safe_reasons(verdict.reasons)
    if verdict.verdict == HYPOTHESIS:
        return "[HYPOTHESIS]"
    return "[ABSTAIN | claim_id=" + claim_id + " | reasons=" + _dump_json(reasons) + "]"


def _synthetic_verdict(reason: str) -> ClaimVerdict:
    """Build a controlled abstain verdict for FR-001 / INV-001 / ADR-005 / ADR-006."""
    return ClaimVerdict(INVALID_CLAIM_ID, ABSTAIN, (_safe_reason(reason),), (), ())


def _validate_turn_args(speaker: object, round_index: object) -> None:
    """Validate internal turn arguments for FR-001 / INV-001 / ADR-005 / ADR-006."""
    if speaker not in SPEAKERS:
        raise ValueError(INVALID_CONTEXT)
    if type(round_index) is not int or round_index < 1:
        raise ValueError(INVALID_CONTEXT)


def evaluate_researcher_turn(
    context: EvidenceContext,
    *,
    speaker: str,
    round_index: int,
    response: object,
) -> ResearcherTurn:
    """Sanitize one model response into debate history for FR-001 / INV-001 / ADR-005 / ADR-006."""
    _validate_turn_args(speaker, round_index)
    text = _response_text(response)
    items, reason = _parse_claims(text)
    if reason is not None:
        verdicts: tuple[ClaimVerdict, ...] = (_synthetic_verdict(reason),)
    else:
        collected: list[ClaimVerdict] = []
        for item in items:
            if isinstance(item, ClaimVerdict):
                collected.append(item)
                continue
            try:
                collected.append(
                    verify_claim(item, registry=context.registry, policy=context.policy)
                )
            except (KeyError, ValueError, TypeError):
                collected.append(_synthetic_verdict(MALFORMED))
        verdicts = tuple(collected) or (_synthetic_verdict(NO_CLAIMS),)
    rejected = tuple(item for verdict in verdicts for item in verdict.rejected_refs)
    history = "\n".join(_history_line(verdict) for verdict in verdicts)
    return ResearcherTurn(
        speaker=speaker,
        round_index=round_index,
        history=history,
        verdicts=verdicts,
        rejected_refs=rejected,
        as_of=context.as_of,
        run_id=context.run_id,
    )


def abstention_turn(
    speaker: str,
    round_index: int,
    reason: str,
    *,
    as_of: str = "",
    run_id: str = "",
) -> ResearcherTurn:
    """Build a model-free abstention turn for FR-001 / INV-001 / ADR-005 / ADR-006."""
    _validate_turn_args(speaker, round_index)
    verdict = _synthetic_verdict(reason)
    safe_as_of = as_of if _canonical_date(as_of) is not None else ""
    safe_run_id = run_id if type(run_id) is str else ""
    return ResearcherTurn(
        speaker=speaker,
        round_index=round_index,
        history=_history_line(verdict),
        verdicts=(verdict,),
        rejected_refs=(),
        as_of=safe_as_of,
        run_id=safe_run_id,
    )


def run_evidence_turn(
    state: Mapping,
    invoke,
    speaker: str,
    language_instruction: str,
) -> dict:
    """Run one evidence-mode researcher turn (FR-001 / INV-001 / ADR-005 / ADR-006)."""
    if speaker not in SPEAKERS:
        raise ValueError(INVALID_CONTEXT)
    if not isinstance(state, Mapping):
        state = {}
    debate = state.get("investment_debate_state")
    if not isinstance(debate, Mapping):
        debate = {}
    supplied_count = debate.get("count")
    count = supplied_count if type(supplied_count) is int and supplied_count >= 0 else 0
    round_index = count // 2 + 1
    context, rejection = preflight_turn(
        state.get("evidence_context"),
        trade_date=state.get("trade_date", ""),
        speaker=speaker,
        round_index=round_index,
    )
    history = ""
    bull_history = ""
    bear_history = ""
    valid_records: list[dict] = []
    if context is not None:
        raw_records = state.get("evidence_verdicts")
        if type(raw_records) is list:
            for record in raw_records:
                if not isinstance(record, Mapping):
                    continue
                if set(record.keys()) != _AUDIT_KEYS:
                    continue
                if type(record.get("as_of")) is not str or record.get("as_of") != context.as_of:
                    continue
                if type(record.get("run_id")) is not str or record.get("run_id") != context.run_id:
                    continue
                if record.get("speaker") not in SPEAKERS:
                    continue
                if type(record.get("round")) is not int or record["round"] < 1:
                    continue
                if type(record.get("verdicts")) is not list:
                    continue
                if type(record.get("rejected_refs")) is not list:
                    continue
                try:
                    problem = _plain_json_problem(record)
                except RecursionError:
                    continue
                if problem is not None:
                    continue
                valid_records.append(dict(record))
        if valid_records:
            count = max(count, len(valid_records))
            candidate_history = debate.get("history")
            candidate_bull = debate.get("bull_history")
            candidate_bear = debate.get("bear_history")
            if (
                isinstance(candidate_history, str)
                and isinstance(candidate_bull, str)
                and isinstance(candidate_bear, str)
            ):
                history = candidate_history
                bull_history = candidate_bull
                bear_history = candidate_bear
            else:
                valid_records = []
        round_index = count // 2 + 1
    if context is None:
        turn = rejection or abstention_turn(
            speaker,
            round_index,
            INVALID_CONTEXT,
            as_of=state.get("trade_date", ""),
        )
    else:
        prompt = (
            f"You are a {SPEAKERS[speaker]} arguing from admissible evidence only. "
            "Use the catalog below and cite only its evidence_id values.\n\n"
            + prepare_prompt_section(context)
            + "\n\nTrusted debate history:\n"
            + (history or "(no trusted history yet)")
            + '\n\nReturn exactly one JSON object {"claims": [...]} and no prose.'
            + (language_instruction if isinstance(language_instruction, str) else "")
        )
        response = invoke(prompt)
        turn = evaluate_researcher_turn(
            context,
            speaker=speaker,
            round_index=round_index,
            response=response,
        )
    argument = turn.response
    new_investment_debate_state = {
        "history": history + "\n" + argument,
        "bull_history": bull_history + "\n" + argument if speaker == "bull" else bull_history,
        "bear_history": bear_history + "\n" + argument if speaker == "bear" else bear_history,
        "current_response": argument,
        "count": count + 1,
    }
    return {
        "investment_debate_state": new_investment_debate_state,
        "evidence_verdicts": valid_records + [turn.audit_record()],
    }


__all__ = [
    "ABSTAIN",
    "ACCEPT_FACTUAL",
    "CONTEXT_DATE_MISMATCH",
    "DUPLICATE_KEY",
    "HYPOTHESIS",
    "INVALID_CLAIM_ID",
    "INVALID_CONTEXT",
    "MALFORMED_RESPONSE",
    "NO_CLAIMS",
    "NON_PROCEED",
    "PROCEED",
    "REVIEW",
    "SPEAKERS",
    "UNKNOWN_FIELD",
    "CatalogEntry",
    "ContextResolution",
    "EvidenceContext",
    "EvidenceContextError",
    "ResearcherTurn",
    "abstention_turn",
    "build_evidence_catalog",
    "evaluate_researcher_turn",
    "preflight_turn",
    "prepare_prompt_section",
    "resolve_evidence_context",
    "run_evidence_turn",
    "validate_evidence_context",
]

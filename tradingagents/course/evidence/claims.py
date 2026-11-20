"""Claim classification and verification for FR-001 / INV-001 / ADR-005.

This module is the claim layer of the evidence leaf. The model may supply claim
text, an optional structured fact candidate, and evidence *references* only. The
trusted, run-scoped :class:`~.contracts.EvidenceRegistry` is built separately from
collector-supplied evidence; a reference is only trusted when the registry admits
it and the claim's structured fact matches the evidence fact on every dimension.

A claim always resolves to one of ``accept_factual`` / ``hypothesis`` / ``abstain``
with stable reason codes. Free text is never accepted as a fact: acceptance emits
only the trusted, normalized evidence fact, never the model's prose.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass

from .contracts import (
    ACCEPT,
    MALFORMED,
    UNTRUSTED,
    EvidenceRegistry,
    Fact,
    FreshnessPolicy,
    fact_matches,
)

# Claim-layer reason codes (stable public contract; do not rename without an ADR).
EVIDENCE_SUPPORTS_FACTUAL_CLAIM = "evidence_supports_factual_claim"
FORECAST_REQUIRES_HYPOTHESIS_LABEL = "forecast_requires_hypothesis_label"
NO_REFERENCE = "no_reference"
NO_STRUCTURED_FACT = "no_structured_fact"
UNCLASSIFIED = "unclassified"
UNRELATED = "unrelated"

_VERDICTS = ("accept_factual", "hypothesis", "abstain")
_CLASSES = ("factual", "predictive", "unknown")
_UNTRUSTED_TOKENS = frozenset(
    {"none", "null", "nan", "n/a", "na", "nil", "undefined", "todo", "tbd", "unknown", "missing"}
)

_EN_FORECAST_WORDS = re.compile(r"\b(?:will|won't|would|should|likely)\b", re.IGNORECASE)
_EN_FORECAST_PREFIXES = re.compile(
    r"\b(?:forecast|predict|project|expect|outlook)\w*",
    re.IGNORECASE,
)
_DIRECTIONAL_VERB = r"(?:rise|fall|climb|drop|surge|tumble|rebound|rally|plunge|soar)"
_EN_FORECAST_MODAL = re.compile(
    rf"\b(?:will|would|should|may|might|could)\s+(?:\w+\s+)?{_DIRECTIONAL_VERB}\b",
    re.IGNORECASE,
)
_EN_FORECAST_PHRASES = re.compile(
    r"\bgoing to\b"
    rf"|\b(?:likely|expected|set|about)\s+to\s+(?:\w+\s+)?{_DIRECTIONAL_VERB}\b"
    rf"|\bto\s+(?:\w+\s+)?{_DIRECTIONAL_VERB}\b"
    r"|\b(?:target price|price target)\b"
    r"|\btomorrow\b|\bnext week\b",
    re.IGNORECASE,
)
_ZH_FORECAST_MARKERS = (
    "必涨",
    "必跌",
    "将涨",
    "将跌",
    "将上涨",
    "将下跌",
    "会上涨",
    "会下跌",
    "预测",
    "预计",
    "看涨",
    "看跌",
    "有望",
    "未来",
    "后市",
    "明天",
    "下周",
    "将会",
    "将要",
    "必然上涨",
    "必然下跌",
    "目标价",
    "即将",
    "大概率",
    "可能上涨",
    "可能下跌",
    "涨停",
    "跌停",
)


def _clean_identifier(value: object) -> str:
    """Return a stripped identifier, or raise a stable reason for untrusted input."""
    if not isinstance(value, str):
        raise ValueError(MALFORMED)
    token = value.strip()
    if not token or token.lower() in _UNTRUSTED_TOKENS or "{{" in token or "}}" in token:
        raise ValueError(UNTRUSTED)
    return token


def _reason(exc: BaseException) -> str:
    """Return a stable reason code from a validation error."""
    text = str(exc)
    return text or MALFORMED


def _dedupe(values: list[str]) -> tuple[str, ...]:
    """Return values in first-seen order without duplicates."""
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            ordered.append(value)
    return tuple(ordered)


def _safe_claim_id(claim: object) -> str:
    """Best-effort claim id for a malformed claim record."""
    if isinstance(claim, Mapping):
        candidate = claim.get("claim_id")
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
    return "<invalid>"


def _is_forecast_text(text: str) -> bool:
    """Return True for obvious English or Chinese forward-looking language."""
    if not isinstance(text, str) or not text:
        return False
    if any(marker in text for marker in _ZH_FORECAST_MARKERS):
        return True
    return bool(
        _EN_FORECAST_WORDS.search(text)
        or _EN_FORECAST_PREFIXES.search(text)
        or _EN_FORECAST_MODAL.search(text)
        or _EN_FORECAST_PHRASES.search(text)
    )


@dataclass(frozen=True)
class Claim:
    """One model-supplied atomic assertion for a single run (FR-001 / INV-001 / ADR-005).

    A claim carries text, an optional declared classification, an optional
    structured fact candidate, and evidence id references. It never carries
    evidence records; the trusted registry is supplied separately.
    """

    claim_id: str
    text: str
    classification: str | None
    fact: Fact | None
    evidence_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        claim_id = _clean_identifier(self.claim_id)
        if not isinstance(self.text, str):
            raise ValueError(MALFORMED)
        if self.classification is not None and self.classification not in _CLASSES:
            raise ValueError(MALFORMED)
        if self.fact is not None and not isinstance(self.fact, Fact):
            raise ValueError(MALFORMED)
        refs = self.evidence_refs
        if not isinstance(refs, (tuple, list)) or any(not isinstance(ref, str) for ref in refs):
            raise ValueError(MALFORMED)
        object.__setattr__(self, "claim_id", claim_id)
        object.__setattr__(self, "evidence_refs", tuple(refs))

    @classmethod
    def from_record(cls, record: object) -> Claim:
        """Build a claim from a plain mapping, rejecting smuggled payloads (FR-001 / INV-001 / ADR-005)."""
        if not isinstance(record, Mapping):
            raise ValueError(MALFORMED)
        allowed = {"claim_id", "text", "classification", "fact", "evidence_refs"}
        if not set(record.keys()) <= allowed:
            raise ValueError(UNTRUSTED)
        claim_id = record.get("claim_id")
        _clean_identifier(claim_id)
        text = record.get("text", "")
        if not isinstance(text, str):
            raise ValueError(MALFORMED)
        classification = record.get("classification")
        if classification is not None and classification not in _CLASSES:
            raise ValueError(MALFORMED)
        fact_record = record.get("fact")
        if fact_record is None:
            fact = None
        elif isinstance(fact_record, Fact):
            fact = fact_record
        else:
            fact = Fact.from_record(fact_record)
        raw_refs = record.get("evidence_refs", ())
        if raw_refs is None:
            raw_refs = ()
        if not isinstance(raw_refs, (tuple, list)) or any(not isinstance(ref, str) for ref in raw_refs):
            raise ValueError(MALFORMED)
        return cls(
            claim_id=claim_id,
            text=text,
            classification=classification,
            fact=fact,
            evidence_refs=tuple(raw_refs),
        )

    def to_dict(self) -> dict:
        """Return a plain JSON-safe dict of the claim input (FR-001 / INV-001 / ADR-005)."""
        return {
            "claim_id": self.claim_id,
            "text": self.text,
            "classification": self.classification,
            "fact": None if self.fact is None else self.fact.to_dict(),
            "evidence_refs": list(self.evidence_refs),
        }


def classify_claim(claim: object) -> str:
    """Classify a claim as ``factual``, ``predictive`` or ``unknown`` (FR-001 / INV-001 / ADR-005).

    Obvious English or Chinese forecast language wins over any declared class, so a
    prediction stays a hypothesis even when a valid fact and reference are present.
    An explicitly declared ``factual`` claim is ``factual`` even without a structured
    fact, so ``verify_claim`` reports ``NO_STRUCTURED_FACT``; a claim with no
    declaration or an explicit ``unknown`` and no structured fact is ``unknown``
    (``UNCLASSIFIED``). Free text is never treated as a fact.
    """
    if not isinstance(claim, Claim):
        return "unknown"
    if _is_forecast_text(claim.text):
        return "predictive"
    if claim.classification == "predictive":
        return "predictive"
    if claim.classification == "unknown":
        return "unknown"
    if claim.classification == "factual":
        return "factual"
    if claim.fact is not None:
        return "factual"
    return "unknown"


@dataclass(frozen=True)
class RejectedRef:
    """A factual reference that failed admission or exact support (FR-001 / INV-001 / ADR-005).

    ``evidence_id`` is the reference text as evaluated (it may be blank or untrusted
    text); ``reasons`` is the per-reference stable reason tuple. Instances are
    immutable so serialized verdicts cannot be mutated through a shared payload.
    """

    evidence_id: str
    reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        if type(self.evidence_id) is not str:
            raise ValueError(MALFORMED)
        reasons = self.reasons
        if not isinstance(reasons, (tuple, list)) or any(type(item) is not str for item in reasons):
            raise ValueError(MALFORMED)
        object.__setattr__(self, "reasons", tuple(reasons))

    def to_dict(self) -> dict:
        """Return fresh plain JSON for this rejection (FR-001 / INV-001 / ADR-005)."""
        return {"evidence_id": self.evidence_id, "reasons": list(self.reasons)}


@dataclass(frozen=True)
class ClaimVerdict:
    """The claim-layer verdict for one claim (FR-001 / INV-001 / ADR-005).

    ``verdict`` is ``accept_factual``, ``hypothesis`` or ``abstain``. ``reasons``
    holds stable top-level reason codes; ``evidence_refs`` and ``projection`` are
    populated only for admitted support. ``projection`` stores immutable evidence
    :class:`~.contracts.Fact` records. ``rejected_refs`` records every evaluated
    reference that failed admission or exact support, so each :meth:`to_dict` call
    emits fresh JSON.
    """

    claim_id: str
    verdict: str
    reasons: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    projection: tuple[Fact, ...]
    rejected_refs: tuple[RejectedRef, ...] = ()

    def __post_init__(self) -> None:
        if type(self.verdict) is not str or self.verdict not in _VERDICTS:
            raise ValueError(MALFORMED)
        reasons = self.reasons
        if not isinstance(reasons, (tuple, list)) or any(type(item) is not str for item in reasons):
            raise ValueError(MALFORMED)
        refs = self.evidence_refs
        if not isinstance(refs, (tuple, list)) or any(
            type(item) is not str or not item.strip() for item in refs
        ):
            raise ValueError(MALFORMED)
        projection = self.projection
        if not isinstance(projection, (tuple, list)) or any(
            not isinstance(item, Fact) for item in projection
        ):
            raise ValueError(MALFORMED)
        rejected = self.rejected_refs
        if not isinstance(rejected, (tuple, list)) or any(
            not isinstance(item, RejectedRef) for item in rejected
        ):
            raise ValueError(MALFORMED)
        if type(self.claim_id) is not str or not self.claim_id.strip():
            raise ValueError(MALFORMED)
        object.__setattr__(self, "reasons", tuple(reasons))
        object.__setattr__(self, "evidence_refs", tuple(refs))
        object.__setattr__(self, "projection", tuple(projection))
        object.__setattr__(self, "rejected_refs", tuple(rejected))

    def to_dict(self) -> dict:
        """Return a plain, deterministically ordered JSON-safe verdict (FR-001 / INV-001 / ADR-005)."""
        return {
            "claim_id": self.claim_id,
            "verdict": self.verdict,
            "reasons": list(self.reasons),
            "evidence_refs": list(self.evidence_refs),
            "projection": [item.to_dict() for item in self.projection],
            "rejected_refs": [item.to_dict() for item in self.rejected_refs],
        }


def _abstain(claim_id: str, reasons: tuple[str, ...]) -> ClaimVerdict:
    """Build an abstain verdict with no refs or projection."""
    return ClaimVerdict(claim_id, "abstain", reasons, (), ())


def verify_claim(claim: object, *, registry: object, policy: object) -> ClaimVerdict:
    """Verify one claim against a trusted registry and policy (FR-001 / INV-001 / ADR-005).

    Accepts a :class:`Claim` or a plain claim mapping and always returns a
    :class:`ClaimVerdict`. Acceptance requires a structured fact that exactly
    matches an admitted evidence unit; conflicted, foreign, malformed, stale,
    future, unrelated or missing references fail closed.
    """
    if isinstance(claim, Mapping):
        try:
            claim = Claim.from_record(claim)
        except ValueError as exc:
            return _abstain(_safe_claim_id(claim), (_reason(exc),))
    if not isinstance(claim, Claim):
        return _abstain("<invalid>", (MALFORMED,))
    if not isinstance(registry, EvidenceRegistry) or not isinstance(policy, FreshnessPolicy):
        return _abstain(claim.claim_id, (MALFORMED,))

    kind = classify_claim(claim)
    if kind == "predictive":
        return ClaimVerdict(
            claim.claim_id,
            "hypothesis",
            (FORECAST_REQUIRES_HYPOTHESIS_LABEL,),
            (),
            (),
        )
    if kind == "unknown":
        return _abstain(claim.claim_id, (UNCLASSIFIED,))
    if claim.fact is None:
        return _abstain(claim.claim_id, (NO_STRUCTURED_FACT,))
    if not claim.evidence_refs:
        return _abstain(claim.claim_id, (NO_REFERENCE,))

    reasons: list[str] = []
    matched: list[str] = []
    projection: list[Fact] = []
    rejected: list[RejectedRef] = []
    for reference in claim.evidence_refs:
        if not isinstance(reference, str):
            reasons.append(UNTRUSTED)
            rejected.append(RejectedRef(str(reference), (UNTRUSTED,)))
            continue
        admission = registry.admissibility(reference, policy)
        if admission.status != ACCEPT:
            audit_id = admission.evidence_id if admission.evidence_id is not None else reference
            rejected.append(RejectedRef(audit_id, admission.reasons))
            reasons.extend(admission.reasons)
            continue
        evidence_id = admission.evidence_id
        if evidence_id is None:
            reasons.append(MALFORMED)
            rejected.append(RejectedRef(reference, (MALFORMED,)))
            continue
        if evidence_id in matched:
            continue
        if admission.unit is not None and fact_matches(claim.fact, admission.unit.fact):
            matched.append(evidence_id)
            projection.append(admission.unit.fact)
        else:
            reasons.append(UNRELATED)
            rejected.append(RejectedRef(evidence_id, (UNRELATED,)))

    if matched:
        return ClaimVerdict(
            claim.claim_id,
            "accept_factual",
            (EVIDENCE_SUPPORTS_FACTUAL_CLAIM,),
            tuple(matched),
            tuple(projection),
            tuple(rejected),
        )
    reasons_out = _dedupe(reasons)
    return ClaimVerdict(
        claim.claim_id,
        "abstain",
        reasons_out or (UNRELATED,),
        (),
        (),
        tuple(rejected),
    )

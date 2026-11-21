# Inspecting data_quality directory contents

**Session ID:** ses_e0280512bffe8oeIRbaEhoEt75
**Created:** 11/21/2026, 5:46:05 PM
**Updated:** 11/21/2026, 6:40:15 PM

---

## User

pwd && ls tradingagents/course/data_quality/


---

## Assistant (Build · CS5351/DeepSeek-V4-Flash · 13.5s)

**Tool: bash**

**Input:**
```json
{
  "command": "pwd && ls tradingagents/course/data_quality/"
}
```

**Output:**
```
/mnt/d/projects/cs5351-tradingagents
__init__.py
__pycache__
admission.py
classifier.py
contracts.py

```

---

## Assistant (Build · CS5351/DeepSeek-V4-Flash · 2.2s)

/mnt/d/projects/cs5351-tradingagents
tradingagents/course/data_quality/: `__init__.py`, `admission.py`, `classifier.py`, `contracts.py`

---

## User

You are the coding agent for role D (FR-004 global data sufficiency admission leaf module). Work only inside the D scope listed below. Reproduce each reported scenario before fixing it, and report actual command output — do not fabricate test results, approvals, session metadata, or identities.

## Scope (editable)
- tradingagents/course/data_quality/contracts.py
- tradingagents/course/data_quality/classifier.py
- tradingagents/course/data_quality/admission.py (only if a narrow admission-side change is required)
- test/offline/test_data_quality.py
- tasks/plans/D/FR-004-test-plan.md

## Frozen — do not touch
docs/approvals/**, .opencode/**, .github/**, scripts/**, other leaf modules (evidence/, budget/, safety/, audit/), governance files (AGENTS.md, Prompt.md, opencode.json), requirements*.txt, Dockerfile, docker-compose.yml, pyproject.toml, and any unrelated existing source. Make narrow, scoped edits; do not replace the baseline wholesale. The docs/approvals/** retention question is being handled separately with the team lead — do not write or edit anything there.

## Background
Non-author reviewer C ran test/offline/test_data_quality.py on PR #1 at commit bd3a853: 20 passed; this round C independently re-ran only the D test file. The normal path behaves as expected: a sourced explicit-zero observation with value_present=True yields proceed, and boolean False yields review. Two boundary defects were found.

Contract anchors:
- Domains: news, social, macro, price, fundamentals.
- Statuses: available, unavailable, unknown. neutral is not a status; it is an explicit sentiment=0 backed by a valid source.
- Decisions: proceed, abstain, review.
- Keep decision events JSON-serializable. The module is fail-closed; unavailable/unknown must never be coerced to neutral/0.

## Finding 1 — value_present is not type-checked (Boolean coercion bug)
classify() currently relies on Python truthiness. With the same observation set, changing value_present from the boolean False to the string "false" changes the admission decision from review to proceed, because a non-empty string is truthy.

Required behavior:
- value_present must be a strict bool. A non-bool value (e.g. the string "false") must not be coerced by truthiness; classify it as unknown (fail-closed). Do not raise an exception for this input.
- A legal True backed by a valid source, with an explicit zero value, must still reach proceed.

Add a regression test: a value observation with value_present="false" → classify returns unknown; admit returns review; that domain appears in insufficient_domains.

## Finding 2 — a direct DomainLabel with available status and no source passes
admit() accepts caller-supplied DomainLabel objects directly. A news label with status="available", source=None, sentiment=0, a valid date and reason, and the other four domains valid, currently yields proceed. A source-less available claim must not be treated as evidence-backed neutral data.

The direct-label entry is part of the public contract (existing tests already pass DomainLabel directly), so keep the entry and validate the label instead of restricting the path. If you find evidence that this path is intended to be internal-only, do not silently restrict it — stop and report that finding first:
- validate_label must reject an available label whose source is None or blank/whitespace. Record a violation with code available_without_source, and the decision must be review.
- unavailable and unknown labels are not required to carry a source; keep the existing behavior for them.
- A direct available label with a valid non-empty source and sentiment=0 must still proceed.

Add regression tests for both source=None and source=""; add a positive test for a direct available label with a valid source that proceeds.

## Validation — run these and report the real output
venv/bin/python -m pytest test/offline/test_data_quality.py -q
venv/bin/python -m pytest test/offline/ -q
venv/bin/ruff check tradingagents/course/data_quality/ test/offline/test_data_quality.py

Also update tasks/plans/D/FR-004-test-plan.md: add the new positive case and the two negative cases to the existing tables, following the current table format. Do not edit historical entries in docs/ai-use-log.yaml; the human member records the log entry after the session. 

---

## Assistant (Build · CS5351/DeepSeek-V4-Flash · 59.7s)

**Tool: bash**

**Input:**
```json
{
  "command": "cat tradingagents/course/data_quality/contracts.py tradingagents/course/data_quality/classifier.py tradingagents/course/data_quality/admission.py"
}
```

**Output:**
```
"""Contracts for F4 global data sufficiency.

Anchors: FR-004, INV-004, ADR-001. All structures here are JSON-serializable and
carry no behavior beyond validation and normalization. Neutral is *not* a status:
it is an explicit data semantic (e.g. a sentiment value of exactly 0) backed by
valid source data, and a neutral observation is still ``status == "available"``.

INV-004: unavailable/unknown must never be coerced to neutral/0.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

DOMAINS: tuple[str, ...] = ("news", "social", "macro", "price", "fundamentals")
REQUIRED_DOMAINS: tuple[str, ...] = DOMAINS

STATUSES: tuple[str, ...] = ("available", "unavailable", "unknown")

DECISIONS: tuple[str, ...] = ("proceed", "abstain", "review")

KINDS: tuple[str, ...] = ("value", "no_data", "missing")


class ContractError(ValueError):
    """Raised when a contract value is structurally invalid (fail-closed)."""


def parse_iso_date(value: Any) -> date:
    """Parse a strict ``YYYY-MM-DD`` ISO date.

    Raises ContractError on anything that is not a valid calendar date in that
    exact format (INV-004 fail-closed: an unparseable date is not assumed valid).
    """
    if not isinstance(value, str):
        raise ContractError(f"date must be a string, got {type(value).__name__}")
    # Strict calendar validation without relying on strptime leniency.
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise ContractError(f"invalid ISO date: {value!r}") from exc
    if parsed.isoformat() != value:
        raise ContractError(f"date must be exactly YYYY-MM-DD: {value!r}")
    return parsed


@dataclass(frozen=True)
class RawObservation:
    """A single raw domain observation, before classification.

    Field existence and source validity are modeled explicitly so an explicit
    zero is distinguishable from a missing value (INV-004):

    - ``kind == "missing"`` or ``value_present is False``: the field is absent.
    - ``kind == "no_data"``: the source was valid but had no data for the date.
    - ``kind == "value"`` with ``value_present is True``: a real observation; an
      explicit ``value == 0`` is valid data, not a placeholder.
    """

    domain: str
    kind: str
    source: str | None = None
    observed_as_of: str | None = None
    value: Any = None
    value_present: bool = False
    sentiment: float | int | None = None
    probe_error: str | None = None

    def source_valid(self) -> bool:
        return isinstance(self.source, str) and self.source.strip() != ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "domain": self.domain,
            "kind": self.kind,
            "source": self.source,
            "observed_as_of": self.observed_as_of,
            "value": self.value,
            "value_present": self.value_present,
            "sentiment": self.sentiment,
            "probe_error": self.probe_error,
        }


@dataclass(frozen=True)
class DomainLabel:
    """Domain status label (FR-004 contract).

    ``status`` is one of available/unavailable/unknown. ``sentiment`` is an
    optional explicit semantic value (e.g. 0) carried for downstream auditing;
    ``status == "neutral"`` is never valid.
    """

    domain: str
    status: str
    as_of: str
    reason: str
    source: str | None = None
    sentiment: float | int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "domain": self.domain,
            "status": self.status,
            "as_of": self.as_of,
            "reason": self.reason,
            "source": self.source,
            "sentiment": self.sentiment,
        }


@dataclass(frozen=True)
class LabelViolation:
    """A recorded contract/violation event (NFR-004 searchable fields)."""

    domain: str | None
    code: str
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {"domain": self.domain, "code": self.code, "reason": self.reason}


@dataclass(frozen=True)
class AdmissionDecision:
    """Global sufficiency decision (FR-004 / INV-004).

    ``proceed`` is emitted only when all required domains are valid and
    available. ``abstain`` flags unavailable data; ``review`` covers unknown
    data and any invalid/uncertain input (default-deny).
    """

    decision: str
    insufficient_domains: list[str] = field(default_factory=list)
    labels: list[DomainLabel] = field(default_factory=list)
    reason: str = ""
    violations: list[LabelViolation] = field(default_factory=list)
    analysis_cutoff: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision,
            "insufficient_domains": list(self.insufficient_domains),
            "labels": [label.to_dict() for label in self.labels],
            "reason": self.reason,
            "violations": [violation.to_dict() for violation in self.violations],
            "analysis_cutoff": self.analysis_cutoff,
        }


def validate_label(label: DomainLabel) -> list[LabelViolation]:
    """Validate a domain label; return violations (empty list == valid).

    Rejects unknown domains, statuses outside available/unavailable/unknown,
    any ``status == "neutral"`` (INV-004: neutral is not an availability state),
    invalid dates, and empty reasons. Never raises: this is an interception
    point, so invalid labels are reported rather than propagated.
    """
    violations: list[LabelViolation] = []

    if label.domain not in DOMAINS:
        violations.append(
            LabelViolation(label.domain, "invalid_domain", f"unknown domain {label.domain!r}")
        )

    if label.status == "neutral":
        violations.append(
            LabelViolation(
                label.domain,
                "neutral_status_forbidden",
                "status 'neutral' is not an availability state "
                "(INV-004: missing/unknown must not be relabeled neutral)",
            )
        )
    elif label.status not in STATUSES:
        violations.append(
            LabelViolation(
                label.domain, "invalid_status", f"unknown status {label.status!r}"
            )
        )

    try:
        parse_iso_date(label.as_of)
    except ContractError as exc:
        violations.append(LabelViolation(label.domain, "invalid_date", str(exc)))

    if not isinstance(label.reason, str) or label.reason.strip() == "":
        violations.append(
            LabelViolation(label.domain, "empty_reason", "label reason must be non-empty")
        )

    return violations


__all__ = [
    "DOMAINS",
    "REQUIRED_DOMAINS",
    "STATUSES",
    "DECISIONS",
    "KINDS",
    "ContractError",
    "parse_iso_date",
    "RawObservation",
    "DomainLabel",
    "LabelViolation",
    "AdmissionDecision",
    "validate_label",
]
"""Raw domain observation -> available | unavailable | unknown.

Anchors: FR-004, INV-004, ADR-001. Classification is deterministic and never
raises on bad raw input; anything uncertain becomes ``unknown`` so that
downstream admission defaults to denial (default-deny unknown).

Explicit neutral: a valid observation whose sentiment is exactly 0 is still
``available`` (neutral is a data semantic, not an availability state).
"""

from __future__ import annotations

from .contracts import ContractError, DomainLabel, RawObservation, parse_iso_date


def _is_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def classify(observation: RawObservation) -> DomainLabel:
    """Classify a single raw observation into a domain status label (FR-004).

    Resolution order (deterministic, fail-closed):

    1. ``probe_error`` set -> ``unknown`` (probe inconclusive).
    2. ``kind == "no_data"`` with a valid source -> ``unavailable``.
    3. ``kind == "value"`` needing ``value_present`` + valid source + valid date
       -> ``available``; otherwise ``unknown`` (never filled in as 0/neutral).
    4. Anything else (``kind == "missing"`` or unknown kinds) -> ``unknown``.
    """
    domain = observation.domain
    as_of = observation.observed_as_of if observation.observed_as_of is not None else ""

    # 1. Inconclusive probe -> unknown regardless of other fields.
    if observation.probe_error:
        return DomainLabel(
            domain=domain,
            status="unknown",
            as_of=as_of,
            reason=f"probe_error: {observation.probe_error}",
            source=observation.source,
            sentiment=None,
        )

    # 2. Source explicitly reported no data for the date.
    if observation.kind == "no_data":
        if not observation.source_valid():
            return DomainLabel(
                domain=domain,
                status="unknown",
                as_of=as_of,
                reason="no_data without a valid source; cannot confirm unavailability",
                source=observation.source,
            )
        return DomainLabel(
            domain=domain,
            status="unavailable",
            as_of=as_of,
            reason="source reported no data for the analysis window",
            source=observation.source,
            sentiment=None,
        )

    # 3. A real value observation.
    if observation.kind == "value":
        if not observation.value_present or observation.value is None:
            return DomainLabel(
                domain=domain,
                status="unknown",
                as_of=as_of,
                reason="value field missing; refusing to default to 0/neutral",
                source=observation.source,
            )
        if not observation.source_valid():
            return DomainLabel(
                domain=domain,
                status="unknown",
                as_of=as_of,
                reason="value present but source is missing/invalid",
                source=observation.source,
            )
        try:
            parse_iso_date(observation.observed_as_of)
        except ContractError as exc:
            return DomainLabel(
                domain=domain,
                status="unknown",
                as_of=as_of,
                reason=f"observation date undeterminable: {exc}",
                source=observation.source,
            )
        if (
            observation.sentiment is not None
            and not _is_number(observation.sentiment)
        ):
            return DomainLabel(
                domain=domain,
                status="unknown",
                as_of=as_of,
                reason="sentiment present but not numeric",
                source=observation.source,
            )
        sentiment = observation.sentiment
        if sentiment is not None and float(sentiment) == 0.0:
            reason = "explicit neutral (sentiment == 0) from valid source data"
        else:
            reason = "valid source data present for the analysis window"
        return DomainLabel(
            domain=domain,
            status="available",
            as_of=as_of,
            reason=reason,
            source=observation.source,
            sentiment=sentiment,
        )

    # 4. Missing field / unknown kind.
    reason = (
        "field absent; refusing to default to 0/neutral"
        if observation.kind == "missing"
        else f"unknown observation kind {observation.kind!r}"
    )
    return DomainLabel(
        domain=domain,
        status="unknown",
        as_of=as_of,
        reason=reason,
        source=observation.source,
    )


__all__ = ["classify"]
"""Global data sufficiency admission decision (proceed / abstain / review).

Anchors: FR-004, INV-004, NFR-004, ADR-001. Deterministic and fail-closed.

Decision priority (first match wins):

1. invalid analysis cutoff                          -> review
2. any label violation (incl. neutral relabel)      -> review
3. empty / missing required / duplicate conflict    -> review
4. any future evidence (as_of > cutoff)             -> review
5. any required domain ``unknown``                  -> review
6. any required domain ``unavailable``              -> abstain
7. all five required domains valid and available    -> proceed

INV-004: unknown maps to review (default-deny), never abstain and never
neutral; unavailable maps to abstain. Unknown domains are listed in
``insufficient_domains``. Any exception at the boundary becomes ``review``; the
result is never silently degraded.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from typing import Any

from .classifier import classify
from .contracts import (
    REQUIRED_DOMAINS,
    AdmissionDecision,
    ContractError,
    DomainLabel,
    LabelViolation,
    RawObservation,
    parse_iso_date,
    validate_label,
)


def _label_or_violation(raw: Any) -> tuple[DomainLabel | None, LabelViolation | None]:
    """Coerce a raw observation into a label, or report why it could not be."""
    if isinstance(raw, DomainLabel):
        return raw, None
    if isinstance(raw, RawObservation):
        return classify(raw), None
    if isinstance(raw, dict):
        try:
            observation = RawObservation(**raw)
        except TypeError as exc:
            return (
                None,
                LabelViolation(
                    raw.get("domain") if isinstance(raw, dict) else None,
                    "invalid_observation",
                    f"observation is not constructible: {exc}",
                ),
            )
        return classify(observation), None
    return (
        None,
        LabelViolation(None, "invalid_observation", f"unsupported observation type {type(raw).__name__}"),
    )


def admit(
    observations: Iterable[Any] | None,
    analysis_cutoff: str,
) -> AdmissionDecision:
    """Decide global data sufficiency from domain observations (FR-004)."""
    try:
        return _admit(observations, analysis_cutoff)
    except Exception as exc:  # noqa: BLE001 - fail-closed boundary, never propagate.
        return AdmissionDecision(
            decision="review",
            insufficient_domains=list(REQUIRED_DOMAINS),
            labels=[],
            reason=f"exception:{type(exc).__name__}",
            violations=[
                LabelViolation(None, "exception", f"{type(exc).__name__}: {exc}")
            ],
            analysis_cutoff=analysis_cutoff if isinstance(analysis_cutoff, str) else None,
        )


def _admit(observations: Iterable[Any] | None, analysis_cutoff: str) -> AdmissionDecision:
    violations: list[LabelViolation] = []

    # 1. Analysis cutoff must be a valid ISO date.
    try:
        cutoff = parse_iso_date(analysis_cutoff)
    except ContractError as exc:
        return AdmissionDecision(
            decision="review",
            insufficient_domains=list(REQUIRED_DOMAINS),
            labels=[],
            reason=f"invalid_cutoff: {exc}",
            violations=[LabelViolation(None, "invalid_cutoff", str(exc))],
            analysis_cutoff=analysis_cutoff if isinstance(analysis_cutoff, str) else None,
        )

    if observations is None:
        observations = []

    labels: list[DomainLabel] = []
    for raw in observations:
        label, violation = _label_or_violation(raw)
        if violation is not None:
            violations.append(violation)
            continue
        assert label is not None
        labels.append(label)

    # 2. Label violations (unknown domain/status, neutral relabel, bad date/reason).
    for label in labels:
        violations.extend(validate_label(label))

    # 3. Required-domain coverage and duplicate conflicts.
    grouped: dict[str, list[DomainLabel]] = defaultdict(list)
    for label in labels:
        grouped[label.domain].append(label)

    missing_domains = [domain for domain in REQUIRED_DOMAINS if domain not in grouped]
    for domain in missing_domains:
        violations.append(
            LabelViolation(domain, "missing_domain", f"required domain {domain!r} absent")
        )

    for domain in REQUIRED_DOMAINS:
        group = grouped.get(domain, [])
        if len(group) > 1:
            statuses = {label.status for label in group}
            as_ofs = {label.as_of for label in group}
            if len(statuses) > 1 or len(as_ofs) > 1:
                violations.append(
                    LabelViolation(
                        domain,
                        "duplicate_conflict",
                        f"conflicting labels for domain {domain!r}",
                    )
                )

    # 3b. Empty input is explicitly insufficient.
    if not labels:
        violations.append(
            LabelViolation(None, "empty_input", "no domain observations supplied")
        )

    # Deterministic label ordering for the returned decision.
    ordered_labels = _order_labels(labels)

    if violations:
        return AdmissionDecision(
            decision="review",
            insufficient_domains=_ordered_unique(
                [v.domain for v in violations if v.domain] + missing_domains
            ),
            labels=ordered_labels,
            reason="label/contract violations; default-deny review",
            violations=violations,
            analysis_cutoff=analysis_cutoff,
        )

    # 4. Future evidence (as_of later than the cutoff).
    future = [label for label in labels if parse_iso_date(label.as_of) > cutoff]
    if future:
        return AdmissionDecision(
            decision="review",
            insufficient_domains=_ordered_unique([label.domain for label in future]),
            labels=ordered_labels,
            reason="evidence dated after the analysis cutoff",
            violations=[
                LabelViolation(
                    label.domain,
                    "future_date",
                    f"as_of {label.as_of} is after cutoff {analysis_cutoff}",
                )
                for label in future
            ],
            analysis_cutoff=analysis_cutoff,
        )

    # 5. Unknown -> review (default-deny), never abstain/neutral.
    unknown = [label for label in labels if label.status == "unknown"]
    if unknown:
        return AdmissionDecision(
            decision="review",
            insufficient_domains=_ordered_unique([label.domain for label in unknown]),
            labels=ordered_labels,
            reason="unknown domain data; default-deny (INV-004)",
            violations=[
                LabelViolation(label.domain, "unknown_domain", label.reason)
                for label in unknown
            ],
            analysis_cutoff=analysis_cutoff,
        )

    # 6. Unavailable -> abstain.
    unavailable = [label for label in labels if label.status == "unavailable"]
    if unavailable:
        return AdmissionDecision(
            decision="abstain",
            insufficient_domains=_ordered_unique([label.domain for label in unavailable]),
            labels=ordered_labels,
            reason="unavailable domain data; abstain",
            analysis_cutoff=analysis_cutoff,
        )

    # 7. All required domains available (and, by construction, only those five).
    return AdmissionDecision(
        decision="proceed",
        insufficient_domains=[],
        labels=ordered_labels,
        reason="all required domains available",
        analysis_cutoff=analysis_cutoff,
    )


def _order_labels(labels: Iterable[DomainLabel]) -> list[DomainLabel]:
    order = {domain: index for index, domain in enumerate(REQUIRED_DOMAINS)}
    return sorted(
        labels,
        key=lambda label: (order.get(label.domain, len(order)), label.domain, label.status, label.as_of),
    )


def _ordered_unique(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result


__all__ = ["admit"]

```

**Tool: bash**

**Input:**
```json
{
  "command": "cat test/offline/test_data_quality.py; cat tasks/plans/D/FR-004-test-plan.md"
}
```

**Output:**
```
"""Offline tests for F4 global data sufficiency (FR-004 / INV-004).

Deterministic, fixed-date fixtures; no network, no LLM/API, no system clock.
"""

from __future__ import annotations

import json

import pytest

from tradingagents.course.data_quality.admission import admit
from tradingagents.course.data_quality.classifier import classify
from tradingagents.course.data_quality.contracts import (
    REQUIRED_DOMAINS,
    AdmissionDecision,
    DomainLabel,
    RawObservation,
    validate_label,
)

CUTOFF = "2026-11-05"
EARLY = "2026-10-06"


def _value(domain: str, value=1.0, as_of: str = CUTOFF, sentiment=None) -> RawObservation:
    """A valid value observation (explicit zero allowed via value=0)."""
    return RawObservation(
        domain=domain,
        kind="value",
        source=f"{domain}-src",
        observed_as_of=as_of,
        value=value,
        value_present=True,
        sentiment=sentiment,
    )


def _unavailable(domain: str, as_of: str = CUTOFF) -> RawObservation:
    return RawObservation(
        domain=domain, kind="no_data", source=f"{domain}-src", observed_as_of=as_of
    )


def _unknown(domain: str, as_of: str = CUTOFF) -> RawObservation:
    return RawObservation(
        domain=domain,
        kind="missing",
        source=f"{domain}-src",
        observed_as_of=as_of,
        value_present=False,
    )


def _all_available() -> list[RawObservation]:
    return [_value(domain) for domain in REQUIRED_DOMAINS]


def _exception_placeholders() -> list[str]:
    return list(REQUIRED_DOMAINS)


# ---------------------------------------------------------------- positive


@pytest.mark.unit
def test_pt1_all_available_proceeds():
    decision = admit(_all_available(), CUTOFF)
    assert decision.decision == "proceed"
    assert decision.insufficient_domains == []
    assert {label.domain for label in decision.labels} == set(REQUIRED_DOMAINS)


@pytest.mark.unit
def test_pt2_explicit_zero_neutral_is_available():
    obs = [
        _value("news"),
        _value("social", value=0, sentiment=0),
        _value("macro"),
        _value("price"),
        _value("fundamentals"),
    ]
    decision = admit(obs, CUTOFF)
    assert decision.decision == "proceed"
    social = [label for label in decision.labels if label.domain == "social"][0]
    assert social.status == "available"
    assert social.sentiment == 0
    assert social.source == "social-src"
    assert "neutral" in social.reason


@pytest.mark.unit
def test_pt3_one_unavailable_abstains():
    obs = [_unavailable("news")] + [
        _value(domain) for domain in REQUIRED_DOMAINS if domain != "news"
    ]
    decision = admit(obs, CUTOFF)
    assert decision.decision == "abstain"
    assert decision.insufficient_domains == ["news"]
    assert decision.reason


@pytest.mark.unit
def test_pt_early_evidence_is_accepted():
    obs = [_value(domain, as_of=EARLY) for domain in REQUIRED_DOMAINS]
    decision = admit(obs, CUTOFF)
    assert decision.decision == "proceed"


# ---------------------------------------------------------------- negative


@pytest.mark.unit
def test_nt1_unknown_domain_reviews_not_abstains():
    obs = [_unknown("macro")] + [
        _value(domain) for domain in REQUIRED_DOMAINS if domain != "macro"
    ]
    decision = admit(obs, CUTOFF)
    assert decision.decision == "review"
    assert "macro" in decision.insufficient_domains
    assert decision.decision not in ("proceed", "abstain")


@pytest.mark.unit
def test_nt2_unavailable_relabeled_neutral_rejected():
    label = DomainLabel(domain="news", status="neutral", as_of=CUTOFF, reason="labelled neutral")
    violations = validate_label(label)
    assert any(v.code == "neutral_status_forbidden" for v in violations)

    decision = admit([label] + [
        _value(domain) for domain in REQUIRED_DOMAINS if domain != "news"
    ], CUTOFF)
    assert decision.decision == "review"
    assert any(v.code == "neutral_status_forbidden" for v in decision.violations)


@pytest.mark.unit
def test_nt3_missing_field_defaulted_to_zero_intercepted():
    # Missing field but value=0 supplied as a placeholder -> must not be trusted.
    placeholder = RawObservation(
        domain="news",
        kind="missing",
        source="news-src",
        observed_as_of=CUTOFF,
        value=0,
        value_present=False,
        sentiment=0,
    )
    decision = admit([placeholder] + [
        _value(domain) for domain in REQUIRED_DOMAINS if domain != "news"
    ], CUTOFF)
    assert decision.decision == "review"
    assert "news" in decision.insufficient_domains
    assert decision.decision != "proceed"


@pytest.mark.unit
def test_nt4_unknown_relabeled_neutral_rejected():
    label = DomainLabel(domain="macro", status="neutral", as_of=CUTOFF, reason="labelled neutral")
    violations = validate_label(label)
    assert violations
    assert all(v.code != "ok" for v in violations)

    decision = admit([label] + [
        _value(domain) for domain in REQUIRED_DOMAINS if domain != "macro"
    ], CUTOFF)
    assert decision.decision == "review"
    assert "macro" in decision.insufficient_domains


@pytest.mark.unit
def test_nt5_empty_input_reviews_all_domains():
    decision = admit([], CUTOFF)
    assert decision.decision == "review"
    assert set(decision.insufficient_domains) == set(REQUIRED_DOMAINS)


@pytest.mark.unit
def test_nt6_missing_required_domain_reviews():
    obs = [_value(domain) for domain in REQUIRED_DOMAINS if domain != "fundamentals"]
    decision = admit(obs, CUTOFF)
    assert decision.decision == "review"
    assert "fundamentals" in decision.insufficient_domains


@pytest.mark.unit
def test_nt7_duplicate_conflicting_domain_reviews():
    obs = _all_available()
    obs.append(_unavailable("price"))
    decision = admit(obs, CUTOFF)
    assert decision.decision == "review"
    assert any(v.code == "duplicate_conflict" for v in decision.violations)


@pytest.mark.unit
def test_nt8_invalid_domain_reviews():
    obs = _all_available() + [_value("weather")]
    decision = admit(obs, CUTOFF)
    assert decision.decision == "review"
    assert any(v.code == "invalid_domain" for v in decision.violations)


@pytest.mark.unit
def test_nt9_invalid_status_reviews():
    label = DomainLabel(domain="news", status="partial", as_of=CUTOFF, reason="partial data")
    decision = admit([label] + [
        _value(domain) for domain in REQUIRED_DOMAINS if domain != "news"
    ], CUTOFF)
    assert decision.decision == "review"
    assert any(v.code == "invalid_status" for v in decision.violations)


@pytest.mark.unit
def test_nt10_invalid_date_reviews():
    label = DomainLabel(domain="news", status="available", as_of="2026-13-40", reason="bad date")
    decision = admit([label] + [
        _value(domain) for domain in REQUIRED_DOMAINS if domain != "news"
    ], CUTOFF)
    assert decision.decision == "review"
    assert any(v.code == "invalid_date" for v in decision.violations)


@pytest.mark.unit
def test_nt11_future_date_reviews():
    obs = [_value("news", as_of="2026-11-06")] + [
        _value(domain) for domain in REQUIRED_DOMAINS if domain != "news"
    ]
    decision = admit(obs, CUTOFF)
    assert decision.decision == "review"
    assert any(v.code == "future_date" for v in decision.violations)


@pytest.mark.unit
def test_nt12_invalid_cutoff_reviews():
    decision = admit(_all_available(), "not-a-date")
    assert decision.decision == "review"
    assert any(v.code == "invalid_cutoff" for v in decision.violations)


# ---------------------------------------------------------------- extended


@pytest.mark.unit
def test_explicit_zero_vs_missing_distinction():
    zero_label = classify(_value("price", value=0))
    missing_label = classify(
        RawObservation(domain="price", kind="missing", source="price-src",
                       observed_as_of=CUTOFF, value=None, value_present=False)
    )
    assert zero_label.status == "available"
    assert missing_label.status == "unknown"


@pytest.mark.unit
def test_deterministic_decisions():
    first = admit(_all_available(), CUTOFF).to_dict()
    second = admit(_all_available(), CUTOFF).to_dict()
    assert first == second

    unavailable_first = admit(
        [_unavailable("social")] + [
            _value(domain) for domain in REQUIRED_DOMAINS if domain != "social"
        ],
        CUTOFF,
    ).to_dict()
    unavailable_second = admit(
        [_value(domain) for domain in REQUIRED_DOMAINS if domain != "social"]
        + [_unavailable("social")],
        CUTOFF,
    ).to_dict()
    assert unavailable_first == unavailable_second


@pytest.mark.unit
def test_refusal_event_fields_complete_and_serializable():
    cases = [
        admit(_all_available(), CUTOFF),
        admit([_unavailable("news")] + [
            _value(domain) for domain in REQUIRED_DOMAINS if domain != "news"
        ], CUTOFF),
        admit([_unknown("macro")] + [
            _value(domain) for domain in REQUIRED_DOMAINS if domain != "macro"
        ], CUTOFF),
    ]
    for decision in cases:
        payload = decision.to_dict()
        assert payload["decision"] in ("proceed", "abstain", "review")
        assert isinstance(payload["insufficient_domains"], list)
        assert isinstance(payload["reason"], str) and payload["reason"]
        assert payload["analysis_cutoff"] == CUTOFF
        for label in payload["labels"]:
            assert set(label) >= {"domain", "status", "as_of", "reason"}
        # Must be JSON-serializable.
        json.dumps(payload)


@pytest.mark.unit
def test_admission_decision_requires_no_extra_dependency():
    # Sanity: the module is importable without heavy runtime deps and has no
    # side effects at import time.
    assert AdmissionDecision(decision="review").decision == "review"
    assert _exception_placeholders() == list(REQUIRED_DOMAINS)
# Test Plan: FR-004

- 作者：编码代理（role D）— 成员姓名未知，不虚构
- 评审人（非作者）：C（计划，未评审）
- 状态：DRAFT（工作文档，非批准门）
- 批准引用（可选，历史）：`docs/approvals/test-plan-FR-004.md`（PENDING，仅作设计输入）

## 范围

- 功能：FR-004（available / unavailable / unknown 区分，default-deny unknown）
- 不变量：INV-004（unavailable、unknown 不得当作 neutral）
- 关联 NFR：NFR-004（拒绝/abstain/review 事件含可检索字段；持久化归 E）
- 路径：`tradingagents/course/data_quality/`（新增）；测试 `test/offline/test_data_quality.py`（新增）
- 全离线：无网络、无 LLM/API；固定日期 fixture（`CUTOFF = "2026-11-05"`），不读系统时间。

## 固定 fixture 约定

- 基准日 `CUTOFF = "2026-11-05"`；早于/等于为合法，晚于为未来（future）。
- 五域：`news, social, macro, price, fundamentals`。
- 「显式 0」：`kind="value", value_present=True, value=0`；「缺失」：`kind="missing", value=None, value_present=False`。

## 判定优先级（与 approval record clarification 4 一致）

1. 非法输入 / 缺必需域 / 重复冲突域 / 标签违规 / 非法或未来日期 / 任一 `unknown` -> `review`
2. 否则任一 `unavailable` -> `abstain`
3. 仅当五域全部有效且 `available` -> `proceed`

> `unknown` 一律 `review`（不映射为 abstain），并记入 `insufficient_domains`；
> `unavailable` 一律 `abstain`。

## 正向测试

| 用例 | 输入 | 预期 |
|---|---|---|
| PT-1 全可用 | 五域 `available`，`as_of` 均 `<= CUTOFF` | `decision=proceed`；`insufficient_domains=[]` |
| PT-2 显式 0/neutral | social 显式 `sentiment=0`（`value=0, value_present=True`），其余 available | `proceed`；social 标签 `status=available`、`sentiment=0`、含 `source` |
| PT-3 一域 unavailable | news=unavailable，其余 available | `abstain`（或 review），`insufficient_domains=["news"]`，含 reason |
| PT-early 早于截止的合法证据 | 某域 `as_of=CUTOFF-30d` | 与 PT-1 同样 `proceed`（证据日可早于分析日） |

## 负向测试

| 用例 | 输入 | 预期（fail-closed） |
|---|---|---|
| NT-1 域 unknown | macro=unknown，其余 available | `review`；`insufficient_domains` 含 macro；不得 `available`/`proceed` |
| NT-2 unavailable 改标 neutral | 把 news unavailable 的标签 `status="neutral"` | 标签校验拒绝（`violations` 记录）；`decision=review`；不 release |
| NT-3 缺失默认填 0/neutral | news `kind="missing"` 但 `value=0`（或 placeholder neutral） | 拦截并记 `violations`；视为不足 -> `abstain`/`review`；不 `proceed` |
| NT-4 unknown 改标 neutral | 把 macro unknown 的标签 `status="neutral"` | 拒绝标签；`review`；按不足处理 |
| NT-5 空输入 | `[]` | `review`，列出全部五域为不足 |
| NT-6 缺必需域 | 只给 4 域 | `review`，缺域记入 `insufficient_domains` |
| NT-7 重复冲突域 | news 出现两次且状态冲突 | `review`，记录冲突 |
| NT-8 非法 domain | `domain="weather"` | `review`（未知域 fail-closed） |
| NT-9 非法 status | `status="partial"` | `review` |
| NT-10 非法日期 | `as_of="2026-13-40"` | `review`（invalid_date） |
| NT-11 未来日期 | `as_of > CUTOFF` | `review`（future_date） |
| NT-12 非法 cutoff | `analysis_cutoff="not-a-date"` | `review`（invalid_cutoff） |

## 扩展/一致性

- 显式 0 与缺失的区分：同一域 `value=0,value_present=True` -> available；`value=None,value_present=False` -> 不足。
- 确定性：同一输入连续两次 `admit()`，`to_dict()` 相等。
- 留痕完整性：任何 `abstain`/`review` 的 `labels` 均含 domain/status/as_of/reason，
  `decision`、`insufficient_domains`、`reason` 均存在且 JSON 可序列化。

## 回归

- [ ] `python scripts/check_course.py --root .`
- [ ] 定向 `pytest -o testpaths=test/offline test/offline/test_data_quality.py`
- [ ] 上游 `pytest`（BASE-002）
- [ ] `ruff check .`
- [ ] 不修改 `tests/`、`tradingagents/**`（除新增 course/）、`pyproject.toml`

## 判定标准

- 来自 requirements.yaml fit：`unavailable/unknown 被误标为 neutral 的次数 = 0` -> 上述负向用例全部拦截。
- 每个 `abstain`/`review`/`proceed` 事件均带域、状态、日期、原因、不足域清单（NFR-004 可检索字段）。

```

---

## Assistant (Build · CS5351/DeepSeek-V4-Flash · 51.0s)

Both findings confirmed by reading code. Let me reproduce them first.

**Tool: bash**

**Input:**
```json
{
  "command": "venv/bin/python - <<'EOF'\nfrom tradingagents.course.data_quality.classifier import classify\nfrom tradingagents.course.data_quality.admission import admit\nfrom tradingagents.course.data_quality.contracts import RawObservation, DomainLabel, REQUIRED_DOMAINS\nCUTOFF=\"2026-11-05\"\ndef v(d,**kw):\n    base=dict(domain=d,kind=\"value\",source=f\"{d}-src\",observed_as_of=CUTOFF,value=1.0,value_present=True)\n    base.update(kw); return RawObservation(**base)\n\n# Finding 1\nobs=[v(\"news\",value_present=\"false\")]+[v(d) for d in REQUIRED_DOMAINS if d!=\"news\"]\nprint(\"F1 label:\", classify(v(\"news\",value_present=\"false\")))\nprint(\"F1 decision:\", admit(obs,CUTOFF).decision, admit(obs,CUTOFF).insufficient_domains)\nprint(\"F1 bool False baseline:\", admit([v(\"news\",value_present=False)]+[v(d) for d in REQUIRED_DOMAINS if d!=\"news\"],CUTOFF).decision)\n\n# Finding 2\nlab=DomainLabel(domain=\"news\",status=\"available\",source=None,sentiment=0,as_of=CUTOFF,reason=\"ok\")\nother=[DomainLabel(domain=d,status=\"available\",as_of=CUTOFF,reason=\"ok\",source=f\"{d}-src\",sentiment=0) for d in REQUIRED_DOMAINS if d!=\"news\"]\ndec=admit([lab]+other,CUTOFF)\nprint(\"F2 decision:\", dec.decision, [x.code for x in dec.violations])\nEOF"
}
```

**Output:**
```
F1 label: DomainLabel(domain='news', status='available', as_of='2026-11-05', reason='valid source data present for the analysis window', source='news-src', sentiment=None)
F1 decision: proceed []
F1 bool False baseline: review
F2 decision: proceed []

```

---

## Assistant (Build · CS5351/DeepSeek-V4-Flash · 3.2s)

Both reproduced. Now fixing.

**Finding 1** — strict bool check in classifier:

**Tool: edit**

**Input:**
```json
{
  "filePath": "/mnt/d/projects/cs5351-tradingagents/tradingagents/course/data_quality/classifier.py",
  "oldString": "    # 3. A real value observation.\n    if observation.kind == \"value\":\n        if not observation.value_present or observation.value is None:",
  "newString": "    # 3. A real value observation.\n    if observation.kind == \"value\":\n        if not isinstance(observation.value_present, bool):\n            return DomainLabel(\n                domain=domain,\n                status=\"unknown\",\n                as_of=as_of,\n                reason=\"value_present is not a boolean; refusing truthiness coercion\",\n                source=observation.source,\n            )\n        if not observation.value_present or observation.value is None:"
}
```

**Output:**
```
Edit applied successfully.
```

---

## Assistant (Build · CS5351/DeepSeek-V4-Flash · 3.4s)

**Finding 2** — reject available label without source in `validate_label`:

**Tool: edit**

**Input:**
```json
{
  "filePath": "/mnt/d/projects/cs5351-tradingagents/tradingagents/course/data_quality/contracts.py",
  "oldString": "    elif label.status not in STATUSES:\n        violations.append(\n            LabelViolation(\n                label.domain, \"invalid_status\", f\"unknown status {label.status!r}\"\n            )\n        )\n\n    try:",
  "newString": "    elif label.status not in STATUSES:\n        violations.append(\n            LabelViolation(\n                label.domain, \"invalid_status\", f\"unknown status {label.status!r}\"\n            )\n        )\n\n    if label.status == \"available\" and not (\n        isinstance(label.source, str) and label.source.strip() != \"\"\n    ):\n        violations.append(\n            LabelViolation(\n                label.domain,\n                \"available_without_source\",\n                \"available label requires a valid non-empty source\",\n            )\n        )\n\n    try:"
}
```

**Output:**
```
Edit applied successfully.
```

---

## Assistant (Build · CS5351/DeepSeek-V4-Flash · 5.5s)

Now add regression tests:

**Tool: edit**

**Input:**
```json
{
  "filePath": "/mnt/d/projects/cs5351-tradingagents/test/offline/test_data_quality.py",
  "oldString": "@pytest.mark.unit\ndef test_nt1_unknown_domain_reviews_not_abstains():",
  "newString": "@pytest.mark.unit\ndef test_nt0_value_present_string_not_coerced():\n    bad = RawObservation(\n        domain=\"news\",\n        kind=\"value\",\n        source=\"news-src\",\n        observed_as_of=CUTOFF,\n        value=1.0,\n        value_present=\"false\",\n    )\n    label = classify(bad)\n    assert label.status == \"unknown\"\n\n    obs = [bad] + [_value(domain) for domain in REQUIRED_DOMAINS if domain != \"news\"]\n    decision = admit(obs, CUTOFF)\n    assert decision.decision == \"review\"\n    assert \"news\" in decision.insufficient_domains\n\n\n@pytest.mark.unit\ndef test_nt1_unknown_domain_reviews_not_abstains():"
}
```

**Output:**
```
Edit applied successfully.
```

---

## Assistant (Build · CS5351/DeepSeek-V4-Flash · 3.1s)

**Tool: edit**

**Input:**
```json
{
  "filePath": "/mnt/d/projects/cs5351-tradingagents/test/offline/test_data_quality.py",
  "oldString": "@pytest.mark.unit\ndef test_nt12_invalid_cutoff_reviews():",
  "newString": "@pytest.mark.unit\ndef test_nt13_available_label_without_source_reviews():\n    for bad_source in (None, \"\"):\n        label = DomainLabel(\n            domain=\"news\",\n            status=\"available\",\n            source=bad_source,\n            sentiment=0,\n            as_of=CUTOFF,\n            reason=\"available claim without source\",\n        )\n        violations = validate_label(label)\n        assert any(v.code == \"available_without_source\" for v in violations)\n\n        decision = admit([label] + [\n            _value(domain) for domain in REQUIRED_DOMAINS if domain != \"news\"\n        ], CUTOFF)\n        assert decision.decision == \"review\"\n        assert any(v.code == \"available_without_source\" for v in decision.violations)\n        assert \"news\" in decision.insufficient_domains\n\n\n@pytest.mark.unit\ndef test_nt12_invalid_cutoff_reviews():"
}
```

**Output:**
```
Edit applied successfully.
```

---

## Assistant (Build · CS5351/DeepSeek-V4-Flash · 4.5s)

**Tool: edit**

**Input:**
```json
{
  "filePath": "/mnt/d/projects/cs5351-tradingagents/test/offline/test_data_quality.py",
  "oldString": "@pytest.mark.unit\ndef test_pt_early_evidence_is_accepted():",
  "newString": "@pytest.mark.unit\ndef test_pt_direct_available_label_with_source_proceeds():\n    news = DomainLabel(\n        domain=\"news\",\n        status=\"available\",\n        source=\"news-src\",\n        sentiment=0,\n        as_of=CUTOFF,\n        reason=\"explicit neutral from valid source\",\n    )\n    others = [\n        DomainLabel(\n            domain=domain, status=\"available\", source=f\"{domain}-src\",\n            sentiment=0, as_of=CUTOFF, reason=\"valid source data\",\n        )\n        for domain in REQUIRED_DOMAINS\n        if domain != \"news\"\n    ]\n    decision = admit([news] + others, CUTOFF)\n    assert decision.decision == \"proceed\"\n    assert decision.insufficient_domains == []\n\n\n@pytest.mark.unit\ndef test_pt_early_evidence_is_accepted():"
}
```

**Output:**
```
Edit applied successfully.
```

---

## Assistant (Build · CS5351/DeepSeek-V4-Flash · 73.9s)

**Tool: bash**

**Input:**
```json
{
  "command": "venv/bin/python -m pytest test/offline/test_data_quality.py -q 2>&1 | tail -20"
}
```

**Output:**
```
.......................                                                  [100%]
23 passed in 0.32s

```

---

## Assistant (Build · CS5351/DeepSeek-V4-Flash · 45.6s)

**Tool: bash**

**Input:**
```json
{
  "command": "venv/bin/python -m pytest test/offline/ -q 2>&1 | tail -10; echo \"---RUFF---\"; venv/bin/ruff check tradingagents/course/data_quality/ test/offline/test_data_quality.py"
}
```

**Output:**
```
...........................................                              [100%]
43 passed in 2.51s
---RUFF---
All checks passed!

```

---

## Assistant (Build · CS5351/DeepSeek-V4-Flash · 3.2s)

All green. Now update the test plan tables.

**Tool: edit**

**Input:**
```json
{
  "filePath": "/mnt/d/projects/cs5351-tradingagents/tasks/plans/D/FR-004-test-plan.md",
  "oldString": "| PT-early 早于截止的合法证据 | 某域 `as_of=CUTOFF-30d` | 与 PT-1 同样 `proceed`（证据日可早于分析日） |",
  "newString": "| PT-early 早于截止的合法证据 | 某域 `as_of=CUTOFF-30d` | 与 PT-1 同样 `proceed`（证据日可早于分析日） |\n| PT-direct 直接可用标签（含有效 source） | news 直接给 `DomainLabel(status=\"available\", source=\"news-src\", sentiment=0)`，其余四域直接 `available` 且各有 source | `proceed`；`insufficient_domains=[]` |"
}
```

**Output:**
```
Edit applied successfully.
```

---

## Assistant (Build · CS5351/DeepSeek-V4-Flash · 3.2s)

**Tool: edit**

**Input:**
```json
{
  "filePath": "/mnt/d/projects/cs5351-tradingagents/tasks/plans/D/FR-004-test-plan.md",
  "oldString": "| NT-12 非法 cutoff | `analysis_cutoff=\"not-a-date\"` | `review`（invalid_cutoff） |",
  "newString": "| NT-12 非法 cutoff | `analysis_cutoff=\"not-a-date\"` | `review`（invalid_cutoff） |\n| NT-0 value_present 非布尔 | value 观测 `value_present=\"false\"`（字符串） | `classify` 返回 `unknown`；`review`；`insufficient_domains` 含该域（不做真值强转） |\n| NT-13 直接可用标签无 source | `DomainLabel(status=\"available\", source=None)` 与 `source=\"\"` 各一例，其余 available | 校验记录 `available_without_source`；`review`；该域入 `insufficient_domains` |"
}
```

**Output:**
```
Edit applied successfully.
```

---

## Assistant (Build · CS5351/DeepSeek-V4-Flash · 66.7s)

**Tool: bash**

**Input:**
```json
{
  "command": "venv/bin/python -m pytest test/offline/test_data_quality.py -q 2>&1 | tail -3"
}
```

**Output:**
```
.......................                                                  [100%]
23 passed in 0.26s

```

---

## Assistant (Build · CS5351/DeepSeek-V4-Flash · 3.6s)

Both findings reproduced and fixed.

**Finding 1** (`classifier.py`): `value_present` is now type-checked strictly; non-bool (e.g. `"false"`) → `unknown` (fail-closed), no exception. Legal `True` with explicit zero still reaches `proceed`.

**Finding 2** (`contracts.py` `validate_label`): available label with `source` None or blank/whitespace → `available_without_source` violation, decision `review`. unavailable/unknown unchanged. Direct-label entry preserved.

**Tests added** (`test/offline/test_data_quality.py`): `test_nt0_value_present_string_not_coerced`, `test_nt13_available_label_without_source_reviews` (None + ""), and `test_pt_direct_available_label_with_source_proceeds`.

Validation output:
- `pytest test/offline/test_data_quality.py -q` → `23 passed in 0.26s`
- `pytest test/offline/ -q` → `43 passed in 2.51s`
- `ruff check ...` → `All checks passed!`

Test plan tables updated with PT-direct, NT-0, NT-13. No frozen paths touched; ai-use-log left for the human member.

---

## User

Rename two offline test cases and sync their IDs in the test plan. Do NOT touch any business source (classifier.py, contracts.py, admission.py).

1. test/offline/test_data_quality.py:
   - test_nt13_available_label_without_source_reviews -> test_nt14_available_label_without_source_reviews
   - test_nt0_value_present_string_not_coerced -> test_nt13_value_present_string_not_coerced

2. tasks/plans/D/FR-004-test-plan.md:
   - "NT-13 直接可用标签无 source" -> "NT-14 直接可用标签无 source"
   - "NT-0 value_present 非布尔" -> "NT-13 value_present 非布尔"

Order matters: rename the old nt13 to nt14 first, then nt0 to nt13. Then run:
venv/bin/python -m pytest test/offline/test_data_quality.py -q
and report the pass count. 

---

## Assistant (Build · CS5351/DeepSeek-V4-Flash · 64.8s)

**Tool: bash**

**Input:**
```json
{
  "command": "cd /mnt/d/projects/cs5351-tradingagents && sed -i 's/test_nt13_available_label_without_source_reviews/test_nt14_available_label_without_source_reviews/; s/test_nt0_value_present_string_not_coerced/test_nt13_value_present_string_not_coerced/' test/offline/test_data_quality.py && grep -n \"def test_nt1[34]\\|def test_nt0\" test/offline/test_data_quality.py"
}
```

**Output:**
```
137:def test_nt13_value_present_string_not_coerced():
276:def test_nt14_available_label_without_source_reviews():

```

---

## Assistant (Build · CS5351/DeepSeek-V4-Flash · 60.7s)

Order was correct (old nt13→nt14 first, then nt0→nt13, both in the same sed so no collision). Now the plan.

**Tool: bash**

**Input:**
```json
{
  "command": "cd /mnt/d/projects/cs5351-tradingagents && sed -i 's/| NT-13 直接可用标签无 source/| NT-14 直接可用标签无 source/; s/| NT-0 value_present 非布尔/| NT-13 value_present 非布尔/' tasks/plans/D/FR-004-test-plan.md && grep -n \"NT-1[34] \\|NT-0 \" tasks/plans/D/FR-004-test-plan.md"
}
```

**Output:**
```
57:| NT-13 value_present 非布尔 | value 观测 `value_present="false"`（字符串） | `classify` 返回 `unknown`；`review`；`insufficient_domains` 含该域（不做真值强转） |
58:| NT-14 直接可用标签无 source | `DomainLabel(status="available", source=None)` 与 `source=""` 各一例，其余 available | 校验记录 `available_without_source`；`review`；该域入 `insufficient_domains` |

```

---

## Assistant (Build · CS5351/DeepSeek-V4-Flash · 40.3s)

**Tool: bash**

**Input:**
```json
{
  "command": "cd /mnt/d/projects/cs5351-tradingagents && venv/bin/python -m pytest test/offline/test_data_quality.py -q 2>&1 | tail -3"
}
```

**Output:**
```
.......................                                                  [100%]
23 passed in 0.34s

```

---

## Assistant (Build · CS5351/DeepSeek-V4-Flash · 3.1s)

Done. Renames applied: `test_nt14_...` (was nt13) and `test_nt13_value_present_...` (was nt0); plan rows updated to NT-14 (available-without-source) and NT-13 (value_present). No business source touched.

`pytest test/offline/test_data_quality.py -q` → **23 passed**.

---


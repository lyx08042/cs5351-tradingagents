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

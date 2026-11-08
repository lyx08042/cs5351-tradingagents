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

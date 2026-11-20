"""Evidence contracts and admissibility layer for FR-001 / INV-001 / ADR-005.

This module is the standalone M2 core of role A. It defines immutable, JSON-only
contracts for a single analysis run: a canonical typed fact, a trusted evidence
unit, a deterministic freshness policy, and a run-scoped evidence registry that
admits or rejects a referenced evidence id with stable reason codes.

Design constraints (ADR-005):
- Python 3.11 standard library only; no clock/RNG; no imports of other course
  leaf modules or the orchestrator.
- Provenance dates come only from the collector. The analysis cutoff is never
  used to fill a missing publication/availability date.
- Values keep ``bool``/``int``/``float``/``str`` distinct and compare exactly
  (no rounding), so ``True`` never matches ``1``.
"""

from __future__ import annotations

import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date

# --- reason codes (stable public contract; do not rename without an ADR) -------

OK = "ok"
ACCEPT = "accept"
REJECT = "reject"

UNAVAILABLE_STATUS = "unavailable_status"
UNKNOWN_STATUS = "unknown_status"
NEUTRAL_STATUS = "neutral_status"
INVALID_STATUS = "invalid_status"
MISSING_DATE = "missing_date"
INVALID_DATE = "invalid_date"
FUTURE_LEAKAGE = "future_leakage"
STALE = "stale"
POLICY_MISMATCH = "policy_mismatch"
INVALID_POLICY = "invalid_policy"
INVALID_AS_OF = "invalid_as_of"
MALFORMED = "malformed"
UNTRUSTED = "untrusted"
UNKNOWN_REFERENCE = "unknown_reference"
FOREIGN_REFERENCE = "foreign_reference"
CONFLICTING_ID = "conflicting_id"
NON_FINITE_VALUE = "non_finite_value"
UNSUPPORTED_VALUE_TYPE = "unsupported_value_type"

SOURCE_STATUSES = ("available", "unavailable", "unknown")
VALUE_KIND_BOOL = "bool"
VALUE_KIND_INT = "int"
VALUE_KIND_FLOAT = "float"
VALUE_KIND_STR = "str"
_VALUE_KINDS = (VALUE_KIND_BOOL, VALUE_KIND_INT, VALUE_KIND_FLOAT, VALUE_KIND_STR)

_UNTRUSTED_TOKENS = frozenset(
    {
        "none",
        "null",
        "nan",
        "n/a",
        "na",
        "nil",
        "undefined",
        "todo",
        "tbd",
        "unknown",
        "missing",
    }
)
_CANONICAL_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")


def _clean_token(value: object) -> str:
    """Return a stripped token, or raise a stable reason for untrusted input."""
    if not isinstance(value, str):
        raise ValueError(MALFORMED)
    token = value.strip()
    if not token or token.lower() in _UNTRUSTED_TOKENS or "{{" in token or "}}" in token:
        raise ValueError(UNTRUSTED)
    return token


def _parse_canonical_date(value: object) -> date | None:
    """Parse a strict, unpadded ``YYYY-MM-DD`` date, or return None for anything else."""
    if not isinstance(value, str):
        return None
    if not _CANONICAL_DATE_RE.fullmatch(value):
        return None
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        return None
    if parsed.isoformat() != value:
        return None
    return parsed


def _string_list(value: object) -> list[str]:
    """Return a validated list of strings, or raise a stable reason."""
    if not isinstance(value, (list, tuple)):
        raise ValueError(MALFORMED)
    result: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise ValueError(MALFORMED)
        result.append(item)
    return result


def _pair_list(value: object) -> list[tuple[str, str]]:
    """Return a validated list of ``(str, str)`` pairs, or raise a stable reason."""
    if not isinstance(value, (list, tuple)):
        raise ValueError(MALFORMED)
    result: list[tuple[str, str]] = []
    for item in value:
        if not isinstance(item, (list, tuple)) or len(item) != 2:
            raise ValueError(MALFORMED)
        identifier, reason = item
        if not isinstance(identifier, str) or not isinstance(reason, str):
            raise ValueError(MALFORMED)
        result.append((identifier, reason))
    return result


def _replay_id(value: str) -> str:
    """Strip a replayed quarantine id, rejecting whitespace-only ids."""
    stripped = value.strip()
    if not stripped:
        raise ValueError(MALFORMED)
    return stripped


def _policy_error(policy: object) -> str | None:
    """Return a stable reason when a freshness policy is invalid, else None."""
    if not isinstance(policy, FreshnessPolicy):
        return INVALID_POLICY
    try:
        _clean_token(policy.name)
    except ValueError:
        return INVALID_POLICY
    age = policy.max_age_days
    if age is not None and (type(age) is not int or age < 0):
        return INVALID_POLICY
    return None


@dataclass(frozen=True)
class CanonicalValue:
    """A typed scalar that never collapses bool/int/float/str (FR-001 / INV-001 / ADR-005).

    ``kind`` is one of ``bool``, ``int``, ``float`` or ``str`` and always agrees
    with the exact Python type of ``value``. ``float`` values must be finite.
    """

    kind: str
    value: object

    def __post_init__(self) -> None:
        kind = self.kind
        value = self.value
        if kind == VALUE_KIND_BOOL:
            if type(value) is not bool:
                raise ValueError(MALFORMED)
        elif kind == VALUE_KIND_INT:
            if type(value) is not int:
                raise ValueError(MALFORMED)
        elif kind == VALUE_KIND_FLOAT:
            if type(value) is not float:
                raise ValueError(MALFORMED)
            if not math.isfinite(value):
                raise ValueError(NON_FINITE_VALUE)
        elif kind == VALUE_KIND_STR:
            if type(value) is not str:
                raise ValueError(MALFORMED)
        else:
            raise ValueError(MALFORMED)

    @classmethod
    def from_value(cls, raw: object) -> CanonicalValue:
        """Canonicalize one JSON-style scalar, preserving exact type (FR-001 / INV-001 / ADR-005)."""
        if type(raw) is bool:
            return cls(VALUE_KIND_BOOL, raw)
        if type(raw) is int:
            return cls(VALUE_KIND_INT, raw)
        if type(raw) is float:
            if not math.isfinite(raw):
                raise ValueError(NON_FINITE_VALUE)
            return cls(VALUE_KIND_FLOAT, raw)
        if type(raw) is str:
            return cls(VALUE_KIND_STR, raw)
        raise ValueError(UNSUPPORTED_VALUE_TYPE)

    @classmethod
    def from_record(cls, record: object) -> CanonicalValue:
        """Rebuild a typed scalar from its ``{"kind", "value"}`` form (FR-001 / INV-001 / ADR-005)."""
        if not isinstance(record, Mapping) or set(record.keys()) != {"kind", "value"}:
            raise ValueError(MALFORMED)
        kind = record["kind"]
        if not isinstance(kind, str) or kind not in _VALUE_KINDS:
            raise ValueError(MALFORMED)
        return cls(kind=kind, value=record["value"])

    def to_dict(self) -> dict:
        """Return a plain JSON-safe ``{"kind", "value"}`` dict (FR-001 / INV-001 / ADR-005)."""
        return {"kind": self.kind, "value": self.value}


def values_equal(left: object, right: object) -> bool:
    """Compare two typed scalars exactly, never rounding or coercing (FR-001 / INV-001 / ADR-005)."""
    if not isinstance(left, CanonicalValue) or not isinstance(right, CanonicalValue):
        return False
    if left.kind != right.kind:
        return False
    return left.value == right.value


@dataclass(frozen=True)
class Fact:
    """A canonical, comparable assertion about one subject at one period (FR-001 / INV-001 / ADR-005).

    A fact carries either a typed ``value`` or a categorical ``relation``, never
    both. ``subject``, ``metric``, ``unit`` and ``period`` are part of identity, so
    an evidence id alone can never substitute for a real fact comparison.
    """

    subject: str
    metric: str
    value: CanonicalValue | None
    relation: str | None
    unit: str | None
    period: str | None

    def __post_init__(self) -> None:
        subject = _clean_token(self.subject)
        metric = _clean_token(self.metric)
        relation = None if self.relation is None else _clean_token(self.relation)
        unit = None if self.unit is None else _clean_token(self.unit)
        period = self.period
        if period is not None and (
            not isinstance(period, str) or _parse_canonical_date(period) is None
        ):
            raise ValueError(INVALID_DATE)
        if (self.value is None) == (relation is None):
            raise ValueError(MALFORMED)
        if self.value is not None and not isinstance(self.value, CanonicalValue):
            raise ValueError(MALFORMED)
        object.__setattr__(self, "subject", subject.upper())
        object.__setattr__(self, "metric", metric.lower())
        object.__setattr__(self, "relation", None if relation is None else relation.lower())
        object.__setattr__(self, "unit", None if unit is None else unit.lower())
        object.__setattr__(self, "period", period)

    @classmethod
    def from_record(cls, record: object) -> Fact:
        """Build a canonical fact from a plain mapping, validating every field (FR-001 / INV-001 / ADR-005)."""
        if not isinstance(record, Mapping):
            raise ValueError(MALFORMED)
        allowed = {"subject", "metric", "value", "relation", "unit", "period"}
        if not set(record.keys()) <= allowed:
            raise ValueError(MALFORMED)
        subject = record.get("subject")
        metric = record.get("metric")
        if not isinstance(subject, str) or not isinstance(metric, str):
            raise ValueError(MALFORMED)
        raw_value = record.get("value")
        if raw_value is None:
            value = None
        elif isinstance(raw_value, CanonicalValue):
            value = raw_value
        elif isinstance(raw_value, Mapping):
            value = CanonicalValue.from_record(raw_value)
        else:
            value = CanonicalValue.from_value(raw_value)
        return cls(
            subject=subject,
            metric=metric,
            value=value,
            relation=record.get("relation"),
            unit=record.get("unit"),
            period=record.get("period"),
        )

    def to_dict(self) -> dict:
        """Return a plain JSON-safe dict of the canonical fact (FR-001 / INV-001 / ADR-005)."""
        return {
            "subject": self.subject,
            "metric": self.metric,
            "value": None if self.value is None else self.value.to_dict(),
            "relation": self.relation,
            "unit": self.unit,
            "period": self.period,
        }


def fact_matches(claim_fact: object, evidence_fact: object) -> bool:
    """Return True only when every fact dimension matches exactly (FR-001 / INV-001 / ADR-005)."""
    if not isinstance(claim_fact, Fact) or not isinstance(evidence_fact, Fact):
        return False
    if claim_fact.subject != evidence_fact.subject:
        return False
    if claim_fact.metric != evidence_fact.metric:
        return False
    if claim_fact.unit != evidence_fact.unit:
        return False
    if claim_fact.period != evidence_fact.period:
        return False
    if claim_fact.value is not None and evidence_fact.value is not None:
        return values_equal(claim_fact.value, evidence_fact.value)
    if claim_fact.relation is not None and evidence_fact.relation is not None:
        return claim_fact.relation == evidence_fact.relation
    return False


@dataclass(frozen=True)
class FreshnessPolicy:
    """A deterministic, configurable evidence age policy (FR-001 / INV-001 / ADR-005).

    Freshness is measured from ``published_at`` (the original publication date),
    not the availability date, so a fresher recapture does not reset it. The age
    is ``(as_of - published_at).days`` and ``max_age_days`` is an inclusive upper
    bound: 0 accepts same-day evidence and a boundary-aged unit is admitted. Both
    provenance dates are required, with no fallback when either is missing.
    ``None`` means no age bound beyond future-leakage and inversion checks.
    """

    name: str
    max_age_days: int | None

    @classmethod
    def from_record(cls, record: object) -> FreshnessPolicy:
        """Build a policy from a ``{"name", "max_age_days"}`` mapping (FR-001 / INV-001 / ADR-005)."""
        if not isinstance(record, Mapping):
            raise ValueError(MALFORMED)
        if not {"name", "max_age_days"} <= set(record.keys()):
            raise ValueError(MALFORMED)
        return cls(name=record["name"], max_age_days=record["max_age_days"])

    def to_dict(self) -> dict:
        """Return a validated, plain JSON-safe policy dict (FR-001 / INV-001 / ADR-005)."""
        if _policy_error(self) is not None:
            raise ValueError(INVALID_POLICY)
        return {"name": self.name.strip(), "max_age_days": self.max_age_days}


@dataclass(frozen=True)
class EvidenceUnit:
    """One immutable, run-scoped evidence record from the collector (FR-001 / INV-001 / ADR-005).

    The id, run id, content pointer, status and provenance dates are supplied by
    the run's collector, never by the model. ``published_at``/``available_as_of``
    are stored verbatim and validated at admission; a missing date is never filled
    from the analysis cutoff.
    """

    evidence_id: str
    run_id: str
    source: str
    content_ref: str
    status: str
    published_at: str | None
    available_as_of: str | None
    fact: Fact
    freshness_policy: str | None

    def __post_init__(self) -> None:
        evidence_id = _clean_token(self.evidence_id)
        run_id = _clean_token(self.run_id)
        content_ref = _clean_token(self.content_ref)
        if not isinstance(self.source, str):
            raise ValueError(MALFORMED)
        source = self.source.strip().lower()
        if source not in {"tool", "report"}:
            raise ValueError(MALFORMED)
        if not isinstance(self.status, str):
            raise ValueError(MALFORMED)
        status = self.status.strip()
        if status == "neutral":
            raise ValueError(NEUTRAL_STATUS)
        if status not in SOURCE_STATUSES:
            raise ValueError(INVALID_STATUS)
        for raw in (self.published_at, self.available_as_of):
            if raw is not None and not isinstance(raw, str):
                raise ValueError(MALFORMED)
        if not isinstance(self.fact, Fact):
            raise ValueError(MALFORMED)
        policy = self.freshness_policy
        if policy is not None:
            policy = _clean_token(policy)
        object.__setattr__(self, "evidence_id", evidence_id)
        object.__setattr__(self, "run_id", run_id)
        object.__setattr__(self, "source", source)
        object.__setattr__(self, "content_ref", content_ref)
        object.__setattr__(self, "status", status)
        object.__setattr__(self, "freshness_policy", policy)

    @classmethod
    def from_record(cls, record: object) -> EvidenceUnit:
        """Build a trusted evidence unit from a plain collector mapping (FR-001 / INV-001 / ADR-005)."""
        if not isinstance(record, Mapping):
            raise ValueError(MALFORMED)
        required = {"evidence_id", "run_id", "source", "content_ref", "status", "fact"}
        if not required <= set(record.keys()):
            raise ValueError(MALFORMED)
        fact_record = record.get("fact")
        fact = fact_record if isinstance(fact_record, Fact) else Fact.from_record(fact_record)
        return cls(
            evidence_id=record["evidence_id"],
            run_id=record["run_id"],
            source=record["source"],
            content_ref=record["content_ref"],
            status=record["status"],
            published_at=record.get("published_at"),
            available_as_of=record.get("available_as_of"),
            fact=fact,
            freshness_policy=record.get("freshness_policy"),
        )

    def to_dict(self) -> dict:
        """Return a plain JSON-safe dict of the evidence unit (FR-001 / INV-001 / ADR-005)."""
        return {
            "evidence_id": self.evidence_id,
            "run_id": self.run_id,
            "source": self.source,
            "content_ref": self.content_ref,
            "status": self.status,
            "published_at": self.published_at,
            "available_as_of": self.available_as_of,
            "fact": self.fact.to_dict(),
            "freshness_policy": self.freshness_policy,
        }


@dataclass(frozen=True)
class Admissibility:
    """The evidence-layer verdict: admit a referenced unit or reject it (FR-001 / INV-001 / ADR-005).

    ``status`` is ``accept`` or ``reject``; ``reasons`` holds stable reason codes
    (``future_leakage`` for EVAL-009). On accept, ``unit`` is the trusted unit.
    """

    status: str
    reasons: tuple[str, ...]
    evidence_id: str | None
    unit: EvidenceUnit | None = None

    def __post_init__(self) -> None:
        if type(self.status) is not str or self.status not in (ACCEPT, REJECT):
            raise ValueError(MALFORMED)
        reasons = self.reasons
        if not isinstance(reasons, (tuple, list)) or any(type(item) is not str for item in reasons):
            raise ValueError(MALFORMED)
        if self.evidence_id is not None and (
            type(self.evidence_id) is not str or not self.evidence_id.strip()
        ):
            raise ValueError(MALFORMED)
        if self.unit is not None and not isinstance(self.unit, EvidenceUnit):
            raise ValueError(MALFORMED)
        object.__setattr__(self, "reasons", tuple(reasons))

    def to_dict(self) -> dict:
        """Return a plain JSON-safe admissibility dict, omitting the unit (FR-001 / INV-001 / ADR-005)."""
        return {
            "status": self.status,
            "reasons": list(self.reasons),
            "evidence_id": self.evidence_id,
        }


def _unit_reasons(unit: EvidenceUnit, as_of: str, policy: FreshnessPolicy) -> tuple[str, ...]:
    """Return the stable reasons a trusted unit is not admissible, or ()."""
    as_of_date = _parse_canonical_date(as_of)
    if as_of_date is None:
        return (INVALID_AS_OF,)
    if unit.freshness_policy is not None and unit.freshness_policy != policy.name.strip():
        return (POLICY_MISMATCH,)
    if unit.status == "unavailable":
        return (UNAVAILABLE_STATUS,)
    if unit.status == "unknown":
        return (UNKNOWN_STATUS,)
    # A known future date (provenance or fact period) wins over a missing date.
    for raw in (unit.published_at, unit.available_as_of, unit.fact.period):
        parsed = _parse_canonical_date(raw)
        if parsed is not None and parsed > as_of_date:
            return (FUTURE_LEAKAGE,)
    if unit.published_at is None or unit.available_as_of is None:
        return (MISSING_DATE,)
    published = _parse_canonical_date(unit.published_at)
    available = _parse_canonical_date(unit.available_as_of)
    if published is None or available is None:
        return (INVALID_DATE,)
    if available < published:
        return (INVALID_DATE,)
    age_days = (as_of_date - published).days
    if policy.max_age_days is not None and age_days > policy.max_age_days:
        return (STALE,)
    return ()


@dataclass(frozen=True, init=False)
class EvidenceRegistry:
    """A deterministic, immutable, run-scoped index of trusted evidence (FR-001 / INV-001 / ADR-005).

    Create it only through :meth:`build` (collector records) or :meth:`from_dict`
    (replay); the generated constructor is disabled so callers cannot bypass the
    quarantine computation. The model never supplies units; it may only cite ids,
    which :meth:`admissibility` resolves against this index.
    """

    run_id: str
    as_of: str
    units: tuple[EvidenceUnit, ...]
    _conflicted_ids: frozenset[str] = field(default_factory=frozenset)
    _foreign_ids: frozenset[str] = field(default_factory=frozenset)
    _malformed: tuple[tuple[str, str], ...] = ()

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError(
            "EvidenceRegistry must be created with EvidenceRegistry.build(...) or from_dict(...)"
        )

    @classmethod
    def _from_parts(
        cls,
        *,
        run_id: str,
        as_of: str,
        units: tuple[EvidenceUnit, ...],
        conflicted_ids: frozenset[str],
        foreign_ids: frozenset[str],
        malformed: tuple[tuple[str, str], ...],
    ) -> EvidenceRegistry:
        """Internal factory for build/from_dict; not part of the public API."""
        instance = object.__new__(cls)
        object.__setattr__(instance, "run_id", run_id)
        object.__setattr__(instance, "as_of", as_of)
        object.__setattr__(instance, "units", units)
        object.__setattr__(instance, "_conflicted_ids", conflicted_ids)
        object.__setattr__(instance, "_foreign_ids", foreign_ids)
        object.__setattr__(instance, "_malformed", malformed)
        return instance

    @classmethod
    def build(cls, *, run_id: object, as_of: object, candidates: object) -> EvidenceRegistry:
        """Build the index, quarantining malformed, foreign and conflicting ids (FR-001 / INV-001 / ADR-005)."""
        clean_run = _clean_token(run_id)
        if _parse_canonical_date(as_of) is None:
            raise ValueError(INVALID_AS_OF)
        if isinstance(candidates, (str, bytes)) or not isinstance(candidates, Sequence):
            raise ValueError(MALFORMED)
        parsed: dict[str, dict] = {}
        all_units: list[EvidenceUnit] = []
        for candidate in candidates:
            if isinstance(candidate, EvidenceUnit):
                candidate = candidate.to_dict()
            if not isinstance(candidate, Mapping):
                raise ValueError(MALFORMED)
            raw_id = candidate.get("evidence_id")
            if not isinstance(raw_id, str):
                continue
            try:
                clean_id = _clean_token(raw_id)
            except ValueError:
                continue
            bucket = parsed.setdefault(clean_id, {"units": [], "reasons": []})
            try:
                unit = EvidenceUnit.from_record(candidate)
            except ValueError as exc:
                bucket["reasons"].append(str(exc) or MALFORMED)
                continue
            bucket["units"].append(unit)
            all_units.append(unit)
        conflicted: set[str] = set()
        foreign: set[str] = set()
        malformed: list[tuple[str, str]] = []
        for evidence_id, bucket in parsed.items():
            units = bucket["units"]
            reasons = bucket["reasons"]
            if reasons and units:
                conflicted.add(evidence_id)
                continue
            if reasons and not units:
                malformed.append((evidence_id, reasons[0]))
                continue
            trusted = [unit for unit in units if unit.run_id == clean_run]
            others = [unit for unit in units if unit.run_id != clean_run]
            if others and trusted:
                conflicted.add(evidence_id)
                continue
            if others and not trusted:
                foreign.add(evidence_id)
                continue
            first = trusted[0]
            if any(unit != first for unit in trusted[1:]):
                conflicted.add(evidence_id)
                continue
        return cls._from_parts(
            run_id=clean_run,
            as_of=as_of,
            units=tuple(all_units),
            conflicted_ids=frozenset(conflicted),
            foreign_ids=frozenset(foreign),
            malformed=tuple(sorted(malformed)),
        )

    def _find(self, evidence_id: str) -> EvidenceUnit | None:
        """Return the unique trusted unit for this id, or None."""
        for unit in self.units:
            if unit.run_id == self.run_id and unit.evidence_id == evidence_id:
                return unit
        return None

    def admissibility(self, evidence_id: object, policy: FreshnessPolicy) -> Admissibility:
        """Admit or reject one evidence reference with stable reasons (FR-001 / INV-001 / ADR-005)."""
        if not isinstance(evidence_id, str):
            return Admissibility(REJECT, (UNTRUSTED,), None)
        try:
            clean_id = _clean_token(evidence_id)
        except ValueError:
            cleaned = evidence_id.strip()
            return Admissibility(REJECT, (UNTRUSTED,), cleaned or None)
        policy_error = _policy_error(policy)
        if policy_error is not None:
            return Admissibility(REJECT, (policy_error,), clean_id)
        malformed = dict(self._malformed)
        if clean_id in malformed:
            return Admissibility(REJECT, (malformed[clean_id],), clean_id)
        if clean_id in self._conflicted_ids:
            return Admissibility(REJECT, (CONFLICTING_ID,), clean_id)
        if clean_id in self._foreign_ids:
            return Admissibility(REJECT, (FOREIGN_REFERENCE,), clean_id)
        unit = self._find(clean_id)
        if unit is None:
            return Admissibility(REJECT, (UNKNOWN_REFERENCE,), clean_id)
        reasons = _unit_reasons(unit, self.as_of, policy)
        if reasons:
            return Admissibility(REJECT, reasons, clean_id)
        return Admissibility(ACCEPT, (OK,), clean_id, unit=unit)

    def to_dict(self) -> dict:
        """Return a plain JSON-safe dict including deterministic quarantine metadata (FR-001 / INV-001 / ADR-005)."""
        return {
            "run_id": self.run_id,
            "as_of": self.as_of,
            "units": [unit.to_dict() for unit in self.units],
            "quarantine": {
                "conflicted": sorted(self._conflicted_ids),
                "foreign": sorted(self._foreign_ids),
                "malformed": [[evidence_id, reason] for evidence_id, reason in self._malformed],
            },
        }

    @classmethod
    def from_dict(cls, data: object) -> EvidenceRegistry:
        """Rebuild a registry from :meth:`to_dict` including quarantine state (FR-001 / INV-001 / ADR-005)."""
        if not isinstance(data, Mapping):
            raise ValueError(MALFORMED)
        units = data.get("units")
        if not isinstance(units, list):
            raise ValueError(MALFORMED)
        recomputed = cls.build(run_id=data.get("run_id"), as_of=data.get("as_of"), candidates=units)
        quarantine = data.get("quarantine", {})
        if not isinstance(quarantine, Mapping):
            raise ValueError(MALFORMED)
        conflicted = set(recomputed._conflicted_ids)
        foreign = set(recomputed._foreign_ids)
        malformed = dict(recomputed._malformed)
        for evidence_id in _string_list(quarantine.get("conflicted", [])):
            conflicted.add(_replay_id(evidence_id))
        for evidence_id in _string_list(quarantine.get("foreign", [])):
            foreign.add(_replay_id(evidence_id))
        for evidence_id, reason in _pair_list(quarantine.get("malformed", [])):
            malformed.setdefault(_replay_id(evidence_id), reason)
        return cls._from_parts(
            run_id=recomputed.run_id,
            as_of=recomputed.as_of,
            units=recomputed.units,
            conflicted_ids=frozenset(conflicted),
            foreign_ids=frozenset(foreign),
            malformed=tuple(sorted(malformed.items())),
        )

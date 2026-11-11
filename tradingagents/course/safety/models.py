"""Data models for deterministic simulation safety (FR-003, INV-003, SEC-001).

Authority split
---------------
The candidate (normally LLM output) only *proposes* an action, quantity, price,
currency and references to a holdings snapshot and rule version. Those claims
are untrusted. ``SafetyContext`` carries the independently trusted snapshot and
rule set. The validator compares the candidate references against the trusted
sources and computes only on the trusted values.

Amount handling
---------------
All money and quantity values are ``Decimal``. Floats are converted through
their shortest decimal string form (``Decimal(str(value))``) so binary-float
boundary errors cannot decide a verdict.

This module never contacts a broker, network or credential store.
"""
from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from types import MappingProxyType
from typing import Any


# INV-003: the only actions in the current simulation scope.
class Action(StrEnum):
    """Simulation actions. A real execution action is never represented here."""

    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"

    @classmethod
    def parse(cls, value: Any) -> Action | None:
        if isinstance(value, Action):
            return value
        if not isinstance(value, str):
            return None
        try:
            return cls(value.strip().lower())
        except ValueError:
            return None


class ProposalStatus(StrEnum):
    """Status is assigned by deterministic code, never by the candidate."""

    ACCEPTED = "accepted"
    REJECTED = "rejected"


class ReasonCode(StrEnum):
    """Stable, machine-readable verdict reasons (NFR-003)."""

    ACCEPTED = "accepted"

    INVALID_PROPOSAL = "invalid_proposal"
    VALIDATION_ERROR = "validation_error"
    REAL_EXECUTION_REQUESTED = "real_execution_requested"

    MISSING_ACTION = "missing_action"
    UNSUPPORTED_ACTION = "unsupported_action"

    MISSING_UNITS = "missing_units"
    INVALID_UNITS = "invalid_units"
    NEGATIVE_UNITS = "negative_units"
    NON_POSITIVE_UNITS = "non_positive_units"
    HOLD_UNITS_NOT_ZERO = "hold_units_not_zero"

    MISSING_PRICE = "missing_price"
    INVALID_PRICE = "invalid_price"
    NON_FINITE_PRICE = "non_finite_price"
    NON_POSITIVE_PRICE = "non_positive_price"

    MISSING_CURRENCY = "missing_currency"
    INVALID_CURRENCY = "invalid_currency"
    CURRENCY_MISMATCH = "currency_mismatch"

    MISSING_HOLDINGS_SNAPSHOT = "missing_holdings_snapshot"
    INVALID_HOLDINGS_SNAPSHOT_REFERENCE = "invalid_holdings_snapshot_reference"
    UNRESOLVED_HOLDINGS_SNAPSHOT = "unresolved_holdings_snapshot"
    HOLDINGS_SNAPSHOT_MISMATCH = "holdings_snapshot_mismatch"
    INVALID_HOLDINGS_SNAPSHOT = "invalid_holdings_snapshot"
    NEGATIVE_HOLDINGS = "negative_holdings"
    UNDECLARED_FLAT = "undeclared_flat"
    MISSING_CASH = "missing_cash"
    INVALID_CASH = "invalid_cash"

    MISSING_RULE_VERSION = "missing_rule_version"
    UNKNOWN_RULE_VERSION = "unknown_rule_version"
    RULE_VERSION_MISMATCH = "rule_version_mismatch"
    INVALID_RULE_SET = "invalid_rule_set"
    UNSUPPORTED_RULE_POLICY = "unsupported_rule_policy"

    AMOUNT_PRECISION_UNSUPPORTED = "amount_precision_unsupported"
    INSUFFICIENT_CASH = "insufficient_cash"
    INSUFFICIENT_HOLDINGS = "insufficient_holdings"


def parse_decimal(value: Any) -> tuple[Decimal | None, str | None]:
    """Return ``(finite_decimal, None)`` or ``(None, "invalid"|"non_finite")``.

    Booleans are rejected because ``bool`` is a subclass of ``int``. Floats are
    converted through ``str`` to avoid binary expansion such as
    ``0.30000000000000004``.
    """
    if isinstance(value, bool) or value is None:
        return None, "invalid"
    if isinstance(value, Decimal):
        number = value
    elif isinstance(value, int):
        number = Decimal(value)
    elif isinstance(value, float):
        if not math.isfinite(value):
            return None, "non_finite"
        number = Decimal(str(value))
    elif isinstance(value, str):
        text = value.strip()
        if not text:
            return None, "invalid"
        try:
            number = Decimal(text)
        except InvalidOperation:
            return None, "invalid"
    else:
        return None, "invalid"
    if not number.is_finite():
        return None, "non_finite"
    return number, None


@dataclass(frozen=True)
class RuleSet:
    """A trusted rule-catalog entry (ADR-001, INV-003).

    Only the explicitly chosen long-only policy is implemented. Unknown policy
    variants fail closed instead of being silently approximated. Reference-price
    deviation limits, fees and extra position caps are deliberately absent:
    they are pending policy inputs and must not be invented.
    """

    version: str
    long_only: bool = True

    def __post_init__(self) -> None:
        if not isinstance(self.version, str) or not self.version.strip():
            raise ValueError("rule version must be a non-empty string")
        if not isinstance(self.long_only, bool):
            raise ValueError("long_only must be a boolean")


@dataclass(frozen=True)
class HoldingsSnapshot:
    """A trusted account snapshot (INV-003, SEC-001).

    ``positions`` is keyed by instrument symbol. An empty position mapping is
    only authoritative when ``flat_declared`` is true; missing data is never
    defaulted to an empty account.
    """

    snapshot_id: str
    as_of: str
    currency: str
    cash: Decimal
    positions: Mapping[str, Decimal] = field(default_factory=dict)
    flat_declared: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.snapshot_id, str) or not self.snapshot_id.strip():
            raise ValueError("snapshot_id must be a non-empty string")
        if not isinstance(self.as_of, str) or not self.as_of.strip():
            raise ValueError("as_of must be a non-empty string")
        if not isinstance(self.currency, str) or not self.currency.strip():
            raise ValueError("currency must be a non-empty string")
        if not isinstance(self.flat_declared, bool):
            raise ValueError("flat_declared must be a boolean")

        cash, cash_error = parse_decimal(self.cash)
        if cash is None:
            raise ValueError(f"cash must be a finite decimal ({cash_error})")
        object.__setattr__(self, "cash", cash)

        normalized: dict[str, Decimal] = {}
        for symbol, quantity in self.positions.items():
            if not isinstance(symbol, str) or not symbol.strip():
                raise ValueError("position symbols must be non-empty strings")
            parsed, quantity_error = parse_decimal(quantity)
            if parsed is None:
                raise ValueError(f"position {symbol!r} must be a finite decimal ({quantity_error})")
            normalized[symbol] = parsed
        object.__setattr__(self, "positions", MappingProxyType(normalized))

    def is_same_as(self, other: HoldingsSnapshot) -> bool:
        """Content equality against the trusted snapshot (anti-forgery)."""
        return (
            self.snapshot_id == other.snapshot_id
            and self.as_of == other.as_of
            and self.currency.strip().upper() == other.currency.strip().upper()
            and self.cash == other.cash
            and dict(self.positions) == dict(other.positions)
            and self.flat_declared == other.flat_declared
        )

    def to_dict(self) -> dict[str, Any]:
        """JSON-serialisable form (Decimal values become strings)."""
        return {
            "snapshot_id": self.snapshot_id,
            "as_of": self.as_of,
            "currency": self.currency,
            "cash": str(self.cash),
            "positions": {symbol: str(quantity) for symbol, quantity in self.positions.items()},
            "flat_declared": self.flat_declared,
        }


def parse_holdings_snapshot(
    value: Any,
) -> tuple[HoldingsSnapshot | None, ReasonCode | None]:
    """Parse a candidate or trusted snapshot mapping without trusting it."""
    if isinstance(value, HoldingsSnapshot):
        return value, None
    if not isinstance(value, Mapping):
        return None, ReasonCode.INVALID_HOLDINGS_SNAPSHOT

    snapshot_id = value.get("snapshot_id")
    as_of = value.get("as_of")
    currency = value.get("currency")
    if not isinstance(snapshot_id, str) or not snapshot_id.strip():
        return None, ReasonCode.INVALID_HOLDINGS_SNAPSHOT
    if not isinstance(as_of, str) or not as_of.strip():
        return None, ReasonCode.INVALID_HOLDINGS_SNAPSHOT
    if not isinstance(currency, str) or not currency.strip():
        return None, ReasonCode.INVALID_HOLDINGS_SNAPSHOT

    cash, cash_error = parse_decimal(value.get("cash"))
    if cash is None:
        if value.get("cash") is None:
            return None, ReasonCode.MISSING_CASH
        return None, ReasonCode.INVALID_CASH

    positions_raw = value.get("positions")
    if not isinstance(positions_raw, Mapping):
        return None, ReasonCode.INVALID_HOLDINGS_SNAPSHOT
    positions: dict[str, Decimal] = {}
    for symbol, quantity in positions_raw.items():
        parsed, _ = parse_decimal(quantity)
        if parsed is None or not isinstance(symbol, str) or not symbol.strip():
            return None, ReasonCode.INVALID_HOLDINGS_SNAPSHOT
        positions[symbol] = parsed

    flat_declared = value.get("flat_declared", False)
    if not isinstance(flat_declared, bool):
        return None, ReasonCode.INVALID_HOLDINGS_SNAPSHOT

    try:
        return (
            HoldingsSnapshot(
                snapshot_id=snapshot_id,
                as_of=as_of,
                currency=currency,
                cash=cash,
                positions=positions,
                flat_declared=flat_declared,
            ),
            None,
        )
    except ValueError:
        return None, ReasonCode.INVALID_HOLDINGS_SNAPSHOT


PROPOSAL_FIELDS = frozenset(
    {
        "action",
        "units",
        "price",
        "currency",
        "holdings_snapshot",
        "rule_version",
        "status",
    }
)


@dataclass(frozen=True)
class SimulationProposal:
    """Structured simulation proposal (FR-003).

    The fixed contract fields are ``action``, ``units``, ``price``,
    ``currency``, ``holdings_snapshot``, ``rule_version`` and ``status``.
    ``extra`` keeps unknown candidate keys so the validator can detect and
    reject real-execution intent and record ignored self-authorisation claims.
    """

    action: Any = None
    units: Any = None
    price: Any = None
    currency: Any = None
    holdings_snapshot: Any = None
    rule_version: Any = None
    status: Any = None
    extra: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> SimulationProposal:
        if not isinstance(data, Mapping):
            raise TypeError("proposal data must be a mapping")
        extra = {key: value for key, value in data.items() if key not in PROPOSAL_FIELDS}
        return cls(
            action=data.get("action"),
            units=data.get("units"),
            price=data.get("price"),
            currency=data.get("currency"),
            holdings_snapshot=data.get("holdings_snapshot"),
            rule_version=data.get("rule_version"),
            status=data.get("status"),
            extra=extra,
        )

    def __post_init__(self) -> None:
        object.__setattr__(self, "extra", MappingProxyType(dict(self.extra)))


@dataclass(frozen=True)
class SafetyContext:
    """Independent trusted inputs for validation (FR-003, SEC-001).

    ``holdings_snapshot`` and ``rule_set`` must come from the caller's trusted
    account source and rule catalog, not from the candidate. ``instrument``
    identifies which position entry is relevant.
    """

    instrument: str
    instrument_currency: str
    holdings_snapshot: HoldingsSnapshot | None
    rule_set: RuleSet | None
    available_rule_versions: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        if not isinstance(self.instrument, str) or not self.instrument.strip():
            raise ValueError("instrument must be a non-empty string")
        if not isinstance(self.instrument_currency, str) or not self.instrument_currency.strip():
            raise ValueError("instrument_currency must be a non-empty string")
        if not isinstance(self.available_rule_versions, frozenset):
            object.__setattr__(
                self, "available_rule_versions", frozenset(self.available_rule_versions)
            )


@dataclass(frozen=True)
class SafetyVerdict:
    """Deterministic outcome of ``validate_proposal`` (INV-003, NFR-003)."""

    accepted: bool
    reason_code: ReasonCode
    message: str
    status: ProposalStatus
    action: str | None
    rule_version: str | None
    snapshot_id: str | None
    instrument: str | None
    is_noop: bool
    ignored_claims: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "accepted": self.accepted,
            "reason_code": self.reason_code.value,
            "message": self.message,
            "status": self.status.value,
            "action": self.action,
            "rule_version": self.rule_version,
            "snapshot_id": self.snapshot_id,
            "instrument": self.instrument,
            "is_noop": self.is_noop,
            "ignored_claims": list(self.ignored_claims),
        }

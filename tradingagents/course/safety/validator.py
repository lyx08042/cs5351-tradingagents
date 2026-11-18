"""Deterministic validation of simulation proposals (FR-003, INV-003, SEC-001).

The validator is the authoritative gate. Candidate-provided status, safety text,
balance, holdings or rule version are never trusted. The caller supplies a
``SafetyContext`` built from independent sources: the trusted account snapshot,
the trusted rule catalog and the instrument quote currency. The verdict is a
pure function of those inputs, so the same proposal/snapshot/rule version
replays identically (NFR-003).

Out of scope this session (do not invent): reference-price deviation limits,
fees and extra position caps. They are pending policy inputs.

No broker, network or credential access is performed here.
"""
from __future__ import annotations

from collections.abc import Mapping
from decimal import (
    MAX_EMAX,
    MIN_EMIN,
    ROUND_HALF_EVEN,
    Clamped,
    Context,
    Decimal,
    DecimalException,
    Inexact,
    InvalidOperation,
    Overflow,
    Rounded,
    Subnormal,
    Underflow,
    getcontext,
    localcontext,
)
from typing import Any

from .models import (
    Action,
    HoldingsSnapshot,
    ProposalStatus,
    ReasonCode,
    RuleSet,
    SafetyContext,
    SafetyVerdict,
    SimulationProposal,
    parse_decimal,
    parse_holdings_snapshot,
)

# NFR-003: an explicit, caller-independent precision budget for exact amounts.
MAX_EXACT_DECIMAL_PRECISION = 64
_EXACTNESS_SIGNALS = (
    Clamped,
    Inexact,
    InvalidOperation,
    Overflow,
    Rounded,
    Subnormal,
    Underflow,
)

REAL_EXECUTION_ACTIONS = frozenset(
    {
        "execute",
        "executed",
        "place_order",
        "submit_order",
        "real_order",
        "live_order",
        "broker_order",
    }
)
REAL_EXECUTION_MODES = frozenset({"live", "real", "broker", "production", "execute"})
REAL_EXECUTION_FLAGS = (
    "real_execution",
    "live",
    "live_trading",
    "submit_order",
    "place_order",
    "execute_now",
    "broker",
    "broker_order",
    "broker_order_id",
)
SELF_AUTHORIZATION_KEYS = (
    "status",
    "safe",
    "is_safe",
    "approved",
    "authorized",
    "authorization",
    "verdict",
    "safety_verdict",
)


def _string_or_none(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _trusted_rule_version(context: SafetyContext | None) -> str | None:
    if isinstance(context, SafetyContext) and isinstance(context.rule_set, RuleSet):
        return context.rule_set.version
    return None


def _exact_product(left: Decimal, right: Decimal) -> Decimal | None:
    """Multiply exactly without depending on the caller's Decimal context.

    The caller may run under any precision, range, rounding, clamp or trap
    settings. This helper builds an explicit ``Context`` (no inherited state)
    and returns ``None`` when an operand is out of range or the exact product
    does not fit. Callers must then fail closed rather than accept a rounded or
    subnormal amount that could understate the cost.
    """
    exact_context = Context(
        prec=MAX_EXACT_DECIMAL_PRECISION,
        rounding=ROUND_HALF_EVEN,
        Emin=MIN_EMIN,
        Emax=MAX_EMAX,
        capitals=1,
        clamp=0,
        traps=[],
    )
    with localcontext(exact_context):
        active = getcontext()
        if not active.is_normal(left) or not active.is_normal(right):
            return None
        try:
            product = left * right
        except DecimalException:
            return None
        unsafe = any(active.flags[signal] for signal in _EXACTNESS_SIGNALS)
        finite = product.is_finite()
    if unsafe or not finite:
        return None
    return product


def _trusted_snapshot_id(context: SafetyContext | None) -> str | None:
    if not isinstance(context, SafetyContext):
        return None
    snapshot = context.holdings_snapshot
    if isinstance(snapshot, HoldingsSnapshot):
        return snapshot.snapshot_id
    if isinstance(snapshot, Mapping):
        raw = snapshot.get("snapshot_id")
        if isinstance(raw, str) and raw.strip():
            return raw.strip()
    return None


def _reject(
    reason: ReasonCode,
    message: str,
    candidate: SimulationProposal | None = None,
    context: SafetyContext | None = None,
    ignored: tuple[str, ...] = (),
) -> SafetyVerdict:
    return SafetyVerdict(
        accepted=False,
        reason_code=reason,
        message=message,
        status=ProposalStatus.REJECTED,
        action=_string_or_none(getattr(candidate, "action", None)),
        rule_version=_trusted_rule_version(context),
        snapshot_id=_trusted_snapshot_id(context),
        instrument=context.instrument if isinstance(context, SafetyContext) else None,
        is_noop=False,
        ignored_claims=ignored,
    )


def _accept(
    candidate: SimulationProposal,
    context: SafetyContext,
    action: Action,
    ignored: tuple[str, ...],
) -> SafetyVerdict:
    return SafetyVerdict(
        accepted=True,
        reason_code=ReasonCode.ACCEPTED,
        message="proposal accepted by deterministic safety rules",
        status=ProposalStatus.ACCEPTED,
        action=action.value,
        rule_version=_trusted_rule_version(context),
        snapshot_id=_trusted_snapshot_id(context),
        instrument=context.instrument,
        is_noop=action is Action.HOLD,
        ignored_claims=ignored,
    )


def _ignored_claims(candidate: SimulationProposal) -> tuple[str, ...]:
    claims: set[str] = set()
    if candidate.status is not None:
        claims.add("status")
    for key in SELF_AUTHORIZATION_KEYS:
        if key != "status" and key in candidate.extra:
            claims.add(key)
    return tuple(sorted(claims))


def _is_real_execution(candidate: SimulationProposal) -> bool:
    action = _string_or_none(candidate.action)
    if action is not None and action.lower() in REAL_EXECUTION_ACTIONS:
        return True

    status = _string_or_none(candidate.status)
    if status is not None and status.lower() in REAL_EXECUTION_ACTIONS:
        return True

    extra = candidate.extra
    mode = extra.get("execution_mode")
    if isinstance(mode, str) and mode.strip().lower() in REAL_EXECUTION_MODES:
        return True

    for key in REAL_EXECUTION_FLAGS:
        if key in extra and extra[key] not in (None, False, "", 0):
            return True
    return False


def _resolve_trusted_snapshot(
    context: SafetyContext,
) -> tuple[HoldingsSnapshot | None, ReasonCode | None]:
    trusted = context.holdings_snapshot
    if trusted is None:
        return None, ReasonCode.UNRESOLVED_HOLDINGS_SNAPSHOT
    if isinstance(trusted, HoldingsSnapshot):
        return trusted, None
    parsed, error = parse_holdings_snapshot(trusted)
    if parsed is None:
        return None, ReasonCode.UNRESOLVED_HOLDINGS_SNAPSHOT
    return parsed, error


def _check_candidate_snapshot(
    candidate: SimulationProposal,
    trusted: HoldingsSnapshot,
) -> ReasonCode | None:
    reference = candidate.holdings_snapshot
    if reference is None:
        return ReasonCode.MISSING_HOLDINGS_SNAPSHOT
    if isinstance(reference, str):
        if reference.strip() != trusted.snapshot_id:
            return ReasonCode.HOLDINGS_SNAPSHOT_MISMATCH
        return None
    if not isinstance(reference, Mapping) and not isinstance(reference, HoldingsSnapshot):
        return ReasonCode.INVALID_HOLDINGS_SNAPSHOT_REFERENCE
    parsed, error = parse_holdings_snapshot(reference)
    if parsed is None:
        return error or ReasonCode.INVALID_HOLDINGS_SNAPSHOT
    if not parsed.is_same_as(trusted):
        return ReasonCode.HOLDINGS_SNAPSHOT_MISMATCH
    return None


def _validate(candidate: SimulationProposal, context: SafetyContext) -> SafetyVerdict:
    ignored = _ignored_claims(candidate)

    # SEC-001: real execution is permanently rejected, before any other field.
    if _is_real_execution(candidate):
        return _reject(
            ReasonCode.REAL_EXECUTION_REQUESTED,
            "real broker execution is permanently rejected",
            candidate,
            context,
            ignored,
        )

    if candidate.action is None or (
        isinstance(candidate.action, str) and not candidate.action.strip()
    ):
        return _reject(ReasonCode.MISSING_ACTION, "missing action", candidate, context, ignored)
    action = Action.parse(candidate.action)
    if action is None:
        return _reject(
            ReasonCode.UNSUPPORTED_ACTION,
            "unsupported action; only buy/sell/hold are simulated",
            candidate,
            context,
            ignored,
        )

    if candidate.units is None:
        return _reject(ReasonCode.MISSING_UNITS, "missing units", candidate, context, ignored)
    units, _ = parse_decimal(candidate.units)
    if units is None:
        return _reject(
            ReasonCode.INVALID_UNITS,
            "units must be a finite number",
            candidate,
            context,
            ignored,
        )
    if units < 0:
        return _reject(
            ReasonCode.NEGATIVE_UNITS,
            "negative units are outside the explicit long-only policy",
            candidate,
            context,
            ignored,
        )
    if action is Action.HOLD:
        if units != 0:
            return _reject(
                ReasonCode.HOLD_UNITS_NOT_ZERO,
                "hold requires units == 0",
                candidate,
                context,
                ignored,
            )
    elif units == 0:
        return _reject(
            ReasonCode.NON_POSITIVE_UNITS,
            "buy/sell requires units > 0",
            candidate,
            context,
            ignored,
        )

    if candidate.price is None:
        return _reject(ReasonCode.MISSING_PRICE, "missing price", candidate, context, ignored)
    price, price_error = parse_decimal(candidate.price)
    if price is None:
        if price_error == "non_finite":
            return _reject(
                ReasonCode.NON_FINITE_PRICE,
                "price must be finite",
                candidate,
                context,
                ignored,
            )
        return _reject(
            ReasonCode.INVALID_PRICE,
            "price must be numeric",
            candidate,
            context,
            ignored,
        )
    if price <= 0:
        return _reject(
            ReasonCode.NON_POSITIVE_PRICE,
            "price must be greater than zero",
            candidate,
            context,
            ignored,
        )

    if candidate.currency is None or (
        isinstance(candidate.currency, str) and not candidate.currency.strip()
    ):
        return _reject(ReasonCode.MISSING_CURRENCY, "missing currency", candidate, context, ignored)
    if not isinstance(candidate.currency, str):
        return _reject(
            ReasonCode.INVALID_CURRENCY,
            "currency must be a string",
            candidate,
            context,
            ignored,
        )
    if candidate.currency.strip().upper() != context.instrument_currency.strip().upper():
        return _reject(
            ReasonCode.CURRENCY_MISMATCH,
            "candidate currency does not match the instrument quote currency",
            candidate,
            context,
            ignored,
        )

    trusted, snapshot_error = _resolve_trusted_snapshot(context)
    if trusted is None:
        return _reject(
            snapshot_error or ReasonCode.UNRESOLVED_HOLDINGS_SNAPSHOT,
            "trusted holdings snapshot is unavailable or invalid",
            candidate,
            context,
            ignored,
        )

    candidate_snapshot_error = _check_candidate_snapshot(candidate, trusted)
    if candidate_snapshot_error is not None:
        return _reject(
            candidate_snapshot_error,
            "candidate holdings snapshot is missing, malformed or not the trusted snapshot",
            candidate,
            context,
            ignored,
        )

    if trusted.currency.strip().upper() != context.instrument_currency.strip().upper():
        return _reject(
            ReasonCode.CURRENCY_MISMATCH,
            "trusted snapshot currency does not match the instrument quote currency",
            candidate,
            context,
            ignored,
        )
    if trusted.cash < 0:
        return _reject(
            ReasonCode.INVALID_CASH,
            "trusted cash must not be negative",
            candidate,
            context,
            ignored,
        )
    if any(quantity < 0 for quantity in trusted.positions.values()):
        return _reject(
            ReasonCode.NEGATIVE_HOLDINGS,
            "negative holdings are outside the explicit long-only policy",
            candidate,
            context,
            ignored,
        )
    if not trusted.positions and not trusted.flat_declared:
        return _reject(
            ReasonCode.UNDECLARED_FLAT,
            "empty holdings require an explicit flat declaration",
            candidate,
            context,
            ignored,
        )

    if candidate.rule_version is None or (
        isinstance(candidate.rule_version, str) and not candidate.rule_version.strip()
    ):
        return _reject(
            ReasonCode.MISSING_RULE_VERSION,
            "missing rule version",
            candidate,
            context,
            ignored,
        )
    if not isinstance(candidate.rule_version, str):
        return _reject(
            ReasonCode.UNKNOWN_RULE_VERSION,
            "rule version must be a string",
            candidate,
            context,
            ignored,
        )
    claimed_rule = candidate.rule_version.strip()
    trusted_rules = context.rule_set
    if trusted_rules is None:
        return _reject(
            ReasonCode.UNKNOWN_RULE_VERSION,
            "trusted rule set is unavailable",
            candidate,
            context,
            ignored,
        )
    if not isinstance(trusted_rules, RuleSet):
        return _reject(
            ReasonCode.INVALID_RULE_SET,
            "trusted rule set has an invalid type",
            candidate,
            context,
            ignored,
        )
    if not trusted_rules.long_only:
        return _reject(
            ReasonCode.UNSUPPORTED_RULE_POLICY,
            "only the explicit long-only policy is implemented",
            candidate,
            context,
            ignored,
        )
    available = context.available_rule_versions or frozenset({trusted_rules.version})
    if claimed_rule not in available:
        return _reject(
            ReasonCode.UNKNOWN_RULE_VERSION,
            "candidate rule version is not in the trusted rule catalog",
            candidate,
            context,
            ignored,
        )
    if claimed_rule != trusted_rules.version:
        return _reject(
            ReasonCode.RULE_VERSION_MISMATCH,
            "candidate rule version does not match the pinned trusted rule version",
            candidate,
            context,
            ignored,
        )

    if action is Action.BUY:
        cost = _exact_product(units, price)
        if cost is None:
            return _reject(
                ReasonCode.AMOUNT_PRECISION_UNSUPPORTED,
                "buy cost cannot be computed exactly within the safety precision budget",
                candidate,
                context,
                ignored,
            )
        if cost > trusted.cash:
            return _reject(
                ReasonCode.INSUFFICIENT_CASH,
                "buy cost exceeds trusted cash",
                candidate,
                context,
                ignored,
            )
    elif action is Action.SELL:
        held = trusted.positions.get(context.instrument, Decimal("0"))
        if held < units:
            return _reject(
                ReasonCode.INSUFFICIENT_HOLDINGS,
                "sell units exceed trusted holdings",
                candidate,
                context,
                ignored,
            )

    return _accept(candidate, context, action, ignored)


def validate_proposal(proposal: Any, *, context: SafetyContext) -> SafetyVerdict:
    """Return a deterministic accept/reject verdict for a simulation proposal.

    ``proposal`` may be a ``SimulationProposal`` or a mapping with the fixed
    contract fields. ``context`` must contain the independently trusted snapshot
    and rule set. Any unexpected error fails closed with ``VALIDATION_ERROR``.
    """
    candidate: SimulationProposal | None = None
    try:
        if not isinstance(context, SafetyContext):
            return _reject(
                ReasonCode.VALIDATION_ERROR,
                "a trusted SafetyContext is required",
            )
        if isinstance(proposal, SimulationProposal):
            candidate = proposal
        elif isinstance(proposal, Mapping):
            candidate = SimulationProposal.from_mapping(proposal)
        else:
            return _reject(
                ReasonCode.INVALID_PROPOSAL,
                "proposal must be a mapping or SimulationProposal",
                None,
                context,
            )
        return _validate(candidate, context)
    except Exception:
        return _reject(
            ReasonCode.VALIDATION_ERROR,
            "unexpected validation failure; failing closed",
            candidate,
            context if isinstance(context, SafetyContext) else None,
        )

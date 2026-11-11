"""Offline deterministic safety tests for FR-003 / INV-003 / SEC-001 / NFR-003.

No network, no broker, no LLM call. Every fixture uses a fixed account snapshot,
fixed quote and fixed rule version so verdicts are reproducible.

The tests deliberately treat the candidate (LLM output) as untrusted: the
trusted snapshot/rules are supplied separately through ``SafetyContext``.
"""
from __future__ import annotations

from decimal import MIN_EMIN, Decimal, Subnormal, localcontext

import pytest

from tradingagents.course.safety import (
    Action,
    HoldingsSnapshot,
    ProposalStatus,
    ReasonCode,
    RuleSet,
    SafetyContext,
    validate_proposal,
)

INSTRUMENT = "AAPL"
SNAPSHOT = HoldingsSnapshot(
    snapshot_id="snap-001",
    as_of="2026-01-02T15:00:00Z",
    currency="USD",
    cash=Decimal("1000"),
    positions={"AAPL": Decimal("5")},
    flat_declared=False,
)
RULES = RuleSet(version="v1")


def make_context(**overrides) -> SafetyContext:
    values = {
        "instrument": INSTRUMENT,
        "instrument_currency": "USD",
        "holdings_snapshot": SNAPSHOT,
        "rule_set": RULES,
        "available_rule_versions": frozenset({"v1"}),
    }
    values.update(overrides)
    return SafetyContext(**values)


def make_proposal(**overrides) -> dict:
    values = {
        "action": "buy",
        "units": 2,
        "price": "100",
        "currency": "USD",
        "holdings_snapshot": SNAPSHOT.to_dict(),
        "rule_version": "v1",
        "status": "pending",
    }
    values.update(overrides)
    return values


def verdict_for(**overrides):
    return validate_proposal(make_proposal(**overrides), context=make_context())


def assert_rejected(reason: ReasonCode, **overrides):
    verdict = verdict_for(**overrides)
    assert verdict.accepted is False
    assert verdict.reason_code is reason
    assert verdict.status is ProposalStatus.REJECTED
    return verdict


@pytest.mark.unit
def test_accepts_legal_buy():
    verdict = verdict_for(units=2, price="100")
    assert verdict.accepted is True
    assert verdict.reason_code is ReasonCode.ACCEPTED
    assert verdict.status is ProposalStatus.ACCEPTED
    assert verdict.is_noop is False
    assert verdict.snapshot_id == "snap-001"
    assert verdict.rule_version == "v1"
    assert verdict.instrument == INSTRUMENT


@pytest.mark.unit
def test_accepts_legal_sell():
    verdict = verdict_for(action="sell", units=5, price="100")
    assert verdict.accepted is True
    assert verdict.reason_code is ReasonCode.ACCEPTED
    assert verdict.is_noop is False


@pytest.mark.unit
def test_accepts_legal_hold_as_noop():
    verdict = verdict_for(action="hold", units=0, price="150")
    assert verdict.accepted is True
    assert verdict.reason_code is ReasonCode.ACCEPTED
    assert verdict.is_noop is True


@pytest.mark.unit
def test_hold_with_nonzero_units_is_rejected():
    assert_rejected(ReasonCode.HOLD_UNITS_NOT_ZERO, action="hold", units=1)


@pytest.mark.unit
def test_explicit_flat_snapshot_allows_buy():
    flat = HoldingsSnapshot(
        snapshot_id="snap-flat",
        as_of="2026-01-02T15:00:00Z",
        currency="USD",
        cash=Decimal("1000"),
        positions={},
        flat_declared=True,
    )
    context = make_context(holdings_snapshot=flat)
    verdict = validate_proposal(
        make_proposal(holdings_snapshot=flat.to_dict()), context=context
    )
    assert verdict.accepted is True
    assert verdict.reason_code is ReasonCode.ACCEPTED


@pytest.mark.unit
def test_empty_holdings_without_flat_declaration_is_rejected():
    undeclared = HoldingsSnapshot(
        snapshot_id="snap-empty",
        as_of="2026-01-02T15:00:00Z",
        currency="USD",
        cash=Decimal("1000"),
        positions={},
        flat_declared=False,
    )
    context = make_context(holdings_snapshot=undeclared)
    verdict = validate_proposal(
        make_proposal(holdings_snapshot=undeclared.to_dict()), context=context
    )
    assert verdict.accepted is False
    assert verdict.reason_code is ReasonCode.UNDECLARED_FLAT


@pytest.mark.unit
def test_missing_candidate_snapshot_is_rejected():
    assert_rejected(ReasonCode.MISSING_HOLDINGS_SNAPSHOT, holdings_snapshot=None)


@pytest.mark.unit
def test_missing_trusted_snapshot_is_not_defaulted_to_flat():
    verdict = validate_proposal(make_proposal(), context=make_context(holdings_snapshot=None))
    assert verdict.accepted is False
    assert verdict.reason_code is ReasonCode.UNRESOLVED_HOLDINGS_SNAPSHOT


@pytest.mark.unit
def test_forged_snapshot_contents_are_rejected():
    forged = {
        "snapshot_id": "snap-001",
        "as_of": "2026-01-02T15:00:00Z",
        "currency": "USD",
        "cash": "999999",
        "positions": {"AAPL": "5"},
        "flat_declared": False,
    }
    verdict = assert_rejected(ReasonCode.HOLDINGS_SNAPSHOT_MISMATCH, holdings_snapshot=forged)
    # The verdict must report the trusted source, never the forged candidate.
    assert verdict.snapshot_id == "snap-001"


@pytest.mark.unit
def test_candidate_snapshot_reference_by_id_is_accepted():
    verdict = verdict_for(holdings_snapshot="snap-001")
    assert verdict.accepted is True
    assert verdict.snapshot_id == "snap-001"


@pytest.mark.unit
def test_buy_exceeding_trusted_cash_is_rejected():
    # 11 * 100 = 1100 > trusted cash 1000.
    assert_rejected(ReasonCode.INSUFFICIENT_CASH, units=11)


@pytest.mark.unit
def test_sell_exceeding_trusted_holdings_is_rejected():
    # Trusted position is 5.
    assert_rejected(ReasonCode.INSUFFICIENT_HOLDINGS, action="sell", units=6)


@pytest.mark.unit
@pytest.mark.parametrize("action", ["buy", "sell"])
def test_zero_units_on_buy_or_sell_is_rejected(action):
    assert_rejected(ReasonCode.NON_POSITIVE_UNITS, action=action, units=0)


@pytest.mark.unit
@pytest.mark.parametrize("action", ["buy", "sell"])
def test_negative_units_are_rejected_under_long_only_policy(action):
    assert_rejected(ReasonCode.NEGATIVE_UNITS, action=action, units=-1)


@pytest.mark.unit
def test_negative_holdings_are_rejected():
    negative = HoldingsSnapshot(
        snapshot_id="snap-negative",
        as_of="2026-01-02T15:00:00Z",
        currency="USD",
        cash=Decimal("1000"),
        positions={"AAPL": Decimal("-1")},
        flat_declared=False,
    )
    context = make_context(holdings_snapshot=negative)
    verdict = validate_proposal(
        make_proposal(holdings_snapshot=negative.to_dict()), context=context
    )
    assert verdict.accepted is False
    assert verdict.reason_code is ReasonCode.NEGATIVE_HOLDINGS


@pytest.mark.unit
def test_negative_trusted_cash_is_rejected():
    negative = HoldingsSnapshot(
        snapshot_id="snap-negative-cash",
        as_of="2026-01-02T15:00:00Z",
        currency="USD",
        cash=Decimal("-1"),
        positions={"AAPL": Decimal("5")},
        flat_declared=False,
    )
    context = make_context(holdings_snapshot=negative)
    verdict = validate_proposal(
        make_proposal(holdings_snapshot=negative.to_dict()), context=context
    )
    assert verdict.accepted is False
    assert verdict.reason_code is ReasonCode.INVALID_CASH


@pytest.mark.unit
@pytest.mark.parametrize("price", [0, "-1", Decimal("-0.01")])
def test_non_positive_price_is_rejected(price):
    assert_rejected(ReasonCode.NON_POSITIVE_PRICE, price=price)


@pytest.mark.unit
@pytest.mark.parametrize(
    "price",
    [float("nan"), float("inf"), float("-inf"), Decimal("NaN"), Decimal("Infinity"), "NaN"],
)
def test_non_finite_price_is_rejected(price):
    assert_rejected(ReasonCode.NON_FINITE_PRICE, price=price)


@pytest.mark.unit
def test_unparseable_price_is_rejected():
    assert_rejected(ReasonCode.INVALID_PRICE, price="not-a-number")


@pytest.mark.unit
def test_currency_mismatch_is_rejected():
    assert_rejected(ReasonCode.CURRENCY_MISMATCH, currency="EUR")


@pytest.mark.unit
def test_trusted_snapshot_currency_mismatch_is_rejected():
    eur = HoldingsSnapshot(
        snapshot_id="snap-eur",
        as_of="2026-01-02T15:00:00Z",
        currency="EUR",
        cash=Decimal("1000"),
        positions={"AAPL": Decimal("5")},
        flat_declared=False,
    )
    context = make_context(holdings_snapshot=eur)
    verdict = validate_proposal(make_proposal(holdings_snapshot=eur.to_dict()), context=context)
    assert verdict.accepted is False
    assert verdict.reason_code is ReasonCode.CURRENCY_MISMATCH


@pytest.mark.unit
def test_missing_rule_version_is_rejected():
    assert_rejected(ReasonCode.MISSING_RULE_VERSION, rule_version=None)


@pytest.mark.unit
def test_unknown_rule_version_is_rejected():
    assert_rejected(ReasonCode.UNKNOWN_RULE_VERSION, rule_version="v9")


@pytest.mark.unit
def test_rule_version_mismatch_is_rejected():
    context = make_context(
        rule_set=RuleSet(version="v1"),
        available_rule_versions=frozenset({"v1", "v2"}),
    )
    verdict = validate_proposal(make_proposal(rule_version="v2"), context=context)
    assert verdict.accepted is False
    assert verdict.reason_code is ReasonCode.RULE_VERSION_MISMATCH


@pytest.mark.unit
def test_missing_trusted_rule_set_is_rejected():
    context = make_context(rule_set=None, available_rule_versions=frozenset({"v1"}))
    verdict = validate_proposal(make_proposal(rule_version="v1"), context=context)
    assert verdict.accepted is False
    assert verdict.reason_code is ReasonCode.UNKNOWN_RULE_VERSION


@pytest.mark.unit
def test_invalid_rule_set_is_rejected_without_secondary_exception():
    context = SafetyContext(
        instrument=INSTRUMENT,
        instrument_currency="USD",
        holdings_snapshot=SNAPSHOT,
        rule_set={},  # type: ignore[arg-type]
        available_rule_versions=frozenset({"v1"}),
    )
    verdict = validate_proposal(make_proposal(rule_version="v1"), context=context)
    assert verdict.accepted is False
    assert verdict.reason_code is ReasonCode.INVALID_RULE_SET
    # The rejection path must not try to read ``rule_set.version`` from a dict.
    assert verdict.rule_version is None


@pytest.mark.unit
def test_invalid_rule_set_does_not_break_earlier_reject_path():
    context = SafetyContext(
        instrument=INSTRUMENT,
        instrument_currency="USD",
        holdings_snapshot=SNAPSHOT,
        rule_set={},  # type: ignore[arg-type]
        available_rule_versions=frozenset({"v1"}),
    )
    verdict = validate_proposal(make_proposal(action=None), context=context)
    assert verdict.accepted is False
    assert verdict.reason_code is ReasonCode.MISSING_ACTION
    assert verdict.rule_version is None


@pytest.mark.unit
@pytest.mark.parametrize(
    "overrides",
    [
        {"action": "execute"},
        {"action": "place_order"},
        {"status": "execute"},
        {"execution_mode": "live"},
        {"execution_mode": "broker"},
        {"real_execution": True},
        {"live": True},
        {"broker_order_id": "order-1"},
    ],
)
def test_real_execution_requests_are_permanently_rejected(overrides):
    verdict = assert_rejected(ReasonCode.REAL_EXECUTION_REQUESTED, **overrides)
    assert verdict.accepted is False


@pytest.mark.unit
def test_llm_self_reported_safety_cannot_override_failed_rules():
    verdict = assert_rejected(
        ReasonCode.INSUFFICIENT_CASH,
        units=11,
        status="accepted",
        safe=True,
        approved=True,
        authorized=True,
    )
    assert verdict.status is ProposalStatus.REJECTED
    assert {"status", "safe", "approved", "authorized"} <= set(verdict.ignored_claims)


@pytest.mark.unit
def test_llm_self_reported_safety_does_not_replace_code_verdict_on_accept():
    verdict = verdict_for(units=2, status="accepted", safe=True)
    assert verdict.accepted is True
    assert verdict.reason_code is ReasonCode.ACCEPTED
    assert "safe" in verdict.ignored_claims
    assert "status" in verdict.ignored_claims


@pytest.mark.unit
def test_missing_required_fields_have_stable_reason_codes():
    assert_rejected(ReasonCode.MISSING_ACTION, action=None)
    assert_rejected(ReasonCode.MISSING_UNITS, units=None)
    assert_rejected(ReasonCode.MISSING_PRICE, price=None)
    assert_rejected(ReasonCode.MISSING_CURRENCY, currency=None)


@pytest.mark.unit
def test_unknown_action_is_rejected_without_treating_it_as_buy():
    assert_rejected(ReasonCode.UNSUPPORTED_ACTION, action="short")


@pytest.mark.unit
def test_malformed_proposal_is_rejected():
    verdict = validate_proposal("not-a-proposal", context=make_context())
    assert verdict.accepted is False
    assert verdict.reason_code is ReasonCode.INVALID_PROPOSAL


@pytest.mark.unit
def test_decimal_amounts_avoid_binary_float_boundary_errors():
    # 3 * 0.1 is exactly 0.3 in decimal arithmetic, but not in binary floats.
    account = HoldingsSnapshot(
        snapshot_id="snap-decimal",
        as_of="2026-01-02T15:00:00Z",
        currency="USD",
        cash=Decimal("0.30"),
        positions={},
        flat_declared=True,
    )
    context = make_context(holdings_snapshot=account)

    accepted = validate_proposal(
        make_proposal(units=3, price=0.1, holdings_snapshot=account.to_dict()),
        context=context,
    )
    assert accepted.accepted is True

    rejected = validate_proposal(
        make_proposal(units=4, price=0.1, holdings_snapshot=account.to_dict()),
        context=context,
    )
    assert rejected.accepted is False
    assert rejected.reason_code is ReasonCode.INSUFFICIENT_CASH


@pytest.mark.unit
def test_buy_cost_is_independent_of_caller_decimal_precision():
    proposal = make_proposal(units="10.004", price="100")

    default_verdict = validate_proposal(proposal, context=make_context())
    with localcontext() as ctx:
        ctx.prec = 3
        low_precision_verdict = validate_proposal(proposal, context=make_context())

    assert default_verdict.accepted is False
    assert low_precision_verdict.accepted is False
    assert default_verdict.reason_code is ReasonCode.INSUFFICIENT_CASH
    assert low_precision_verdict.reason_code is ReasonCode.INSUFFICIENT_CASH


@pytest.mark.unit
def test_extreme_precision_cost_is_blocked_instead_of_rounded():
    # 100 significant digits exceed the validator's explicit exactness budget.
    high_precision_units = "0." + "1" * 100
    verdict = validate_proposal(
        make_proposal(units=high_precision_units, price="3"),
        context=make_context(),
    )
    assert verdict.accepted is False
    assert verdict.reason_code is ReasonCode.AMOUNT_PRECISION_UNSUPPORTED


@pytest.mark.unit
def test_buy_cost_ignores_caller_subnormal_trap_and_clamp():
    # An exponent below the explicit context's Emin is out of range; trap and
    # clamp settings inherited from the caller must not change the verdict.
    proposal = make_proposal(units=f"1e{MIN_EMIN - 1}", price="1")

    with localcontext() as ctx:
        ctx.traps[Subnormal] = False
        untrapped = validate_proposal(proposal, context=make_context())

    with localcontext() as ctx:
        ctx.traps[Subnormal] = True
        trapped = validate_proposal(proposal, context=make_context())

    with localcontext() as ctx:
        ctx.clamp = 1
        clamped = validate_proposal(proposal, context=make_context())

    assert untrapped.accepted is False
    assert trapped.accepted is False
    assert clamped.accepted is False
    assert untrapped.reason_code is ReasonCode.AMOUNT_PRECISION_UNSUPPORTED
    assert trapped.reason_code is ReasonCode.AMOUNT_PRECISION_UNSUPPORTED
    assert clamped.reason_code is ReasonCode.AMOUNT_PRECISION_UNSUPPORTED


@pytest.mark.unit
def test_replay_is_deterministic_and_does_not_mutate_input():
    proposal = make_proposal(units=11)
    context = make_context()
    before = dict(proposal)

    first = validate_proposal(proposal, context=context)
    second = validate_proposal(proposal, context=context)

    assert first == second
    assert first.to_dict() == second.to_dict()
    assert proposal == before


@pytest.mark.unit
def test_reason_codes_are_stable_strings():
    assert ReasonCode.ACCEPTED.value == "accepted"
    assert ReasonCode.MISSING_HOLDINGS_SNAPSHOT.value == "missing_holdings_snapshot"
    assert ReasonCode.INSUFFICIENT_CASH.value == "insufficient_cash"
    assert ReasonCode.REAL_EXECUTION_REQUESTED.value == "real_execution_requested"


@pytest.mark.unit
def test_action_enum_only_contains_simulation_actions():
    assert {action.value for action in Action} == {"buy", "sell", "hold"}

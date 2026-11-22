"""Offline tests for the FR-002 budget ledger.

No network, no model call, no API key: the clock, the id factory and the
estimate table are injected, so every assertion is deterministic.

Each test names the requirement it verifies (course D4).
"""

from __future__ import annotations

import threading

import pytest

from tradingagents.course.budget.context import (
    REQUIRED_MARKERS,
    SAFETY_BLOCK,
    SECTIONS,
    assemble_context,
    assert_manifest,
    budget_for_section,
    compact,
    count_tokens,
    reinject,
    should_compact,
)
from tradingagents.course.budget.contracts import (
    STAGES,
    BudgetDenied,
    ContractError,
    LedgerConfig,
    LevelRegression,
)
from tradingagents.course.budget.ledger import BudgetLedger
from tradingagents.course.budget.policy import DegradationPolicy

ESTIMATE = 1_000


class SeqIds:
    """Deterministic call ids: call-1, call-2, ..."""

    def __init__(self) -> None:
        self._n = 0

    def __call__(self) -> str:
        self._n += 1
        return f"call-{self._n}"


def fake_clock():
    """Deterministic ISO timestamps, one per emitted event."""
    state = {"n": 0}

    def now() -> str:
        state["n"] += 1
        return f"2026-11-15T00:00:{state['n']:02d}Z"

    return now


def make_ledger(
    limit_tokens: int = 100_000,
    limit_calls: int = 100,
    *,
    quota: dict[str, float] | None = None,
    ids: SeqIds | None = None,
) -> BudgetLedger:
    config = LedgerConfig(
        limit_tokens=limit_tokens,
        limit_calls=limit_calls,
        estimate_margin=1.0,
        **({"stage_quota": quota} if quota else {}),
    )
    estimates = {(None, stage): ESTIMATE for stage in STAGES}
    return BudgetLedger(
        config,
        clock=fake_clock(),
        id_factory=ids or SeqIds(),
        stage_estimates=estimates,
    )


def event_types(ledger: BudgetLedger) -> list[str]:
    return [event.type for event in ledger.events()]


# --------------------------------------------------------------------- positive


def test_pt1_reserve_within_budget() -> None:
    """FR-002: a reservation inside the budget succeeds and charges the pool."""
    ledger = make_ledger()
    reservation = ledger.reserve("market_analyst", "analyst", "quick", "c1")

    assert reservation.estimated == ESTIMATE
    assert reservation.remaining_global_after == 99_000
    assert ledger.remaining("global") == 99_000
    assert event_types(ledger) == ["reserve"]


def test_pt2_settle_exactly_at_estimate() -> None:
    """INV-002: settling at the estimate refunds nothing and charges nothing extra."""
    ledger = make_ledger()
    ledger.reserve("market_analyst", "analyst", "quick", "c1")
    settlement = ledger.settle("c1", 600, 400)

    assert settlement.actual == ESTIMATE
    assert settlement.refunded == 0
    assert settlement.overrun == 0
    assert ledger.remaining("global") == 99_000


def test_pt3_settle_below_estimate_refunds() -> None:
    """INV-002: unused reservation is returned to the pool after settlement."""
    ledger = make_ledger()
    ledger.reserve("market_analyst", "analyst", "quick", "c1")
    settlement = ledger.settle("c1", 500, 300)

    assert settlement.actual == 800
    assert settlement.refunded == 200
    assert ledger.remaining("global") == 99_200


def test_pt4_stage_quota_is_not_consumed_by_another_stage() -> None:
    """FR-002: spending in one stage leaves the protected stage's quota intact."""
    ledger = make_ledger()
    for index in range(40):
        ledger.reserve("market_analyst", "analyst", "quick", f"c{index}")

    assert ledger.remaining("analyst") == 0
    assert ledger.remaining("portfolio_manager") == 5_000
    ledger.reserve("portfolio_manager", "portfolio_manager", "deep", "pm-1")


def test_pt5_borrowing_from_an_unspent_stage() -> None:
    """FR-002: a stage short of quota may borrow from another stage and records it."""
    ledger = make_ledger(limit_tokens=10_000)
    reservation = ledger.reserve("portfolio_manager", "portfolio_manager", "deep", "c1")

    assert reservation.estimated == ESTIMATE
    borrow_events = [event for event in ledger.events() if event.type == "borrow"]
    assert borrow_events
    assert borrow_events[0].reason.startswith("borrow:")
    assert "->portfolio_manager" in borrow_events[0].reason


def test_pt6_identical_scripts_produce_identical_traces() -> None:
    """AC-7: the same call script yields the same events and snapshot."""
    def run() -> tuple[list[dict], dict]:
        ledger = make_ledger(ids=SeqIds())
        ledger.reserve("market_analyst", "analyst", "quick")
        ledger.reserve("bull_researcher", "debate", "quick")
        ledger.settle("call-1", 700, 200)
        ledger.apply_level(2)
        return [event.to_dict() for event in ledger.events()], ledger.snapshot()

    first_events, first_snapshot = run()
    second_events, second_snapshot = run()

    assert first_events == second_events
    assert first_snapshot == second_snapshot


def test_pt7_release_before_execution() -> None:
    """FR-002: an abandoned call returns its full reservation."""
    ledger = make_ledger()
    ledger.reserve("market_analyst", "analyst", "quick", "c1")
    ledger.release("c1", "caller_cancelled")

    assert ledger.remaining("global") == 100_000
    assert event_types(ledger) == ["reserve", "release"]


# --------------------------------------------------------------------- negative


def test_nt1_reserve_beyond_total_budget_is_denied() -> None:
    """FR-002 / INV-002: the call after exhaustion is refused, fail-closed."""
    ledger = make_ledger(limit_tokens=10_000, quota={"analyst": 1.0})
    for index in range(10):
        ledger.reserve("market_analyst", "analyst", "quick", f"c{index}")

    with pytest.raises(BudgetDenied) as excinfo:
        ledger.reserve("market_analyst", "analyst", "quick", "c11")

    assert excinfo.value.reason == "global_exhausted"
    assert ledger.state == "exhausted"
    assert "exhausted" in event_types(ledger)


def test_nt2_reserve_beyond_call_limit_is_denied() -> None:
    """FR-002: the call-count cap is enforced independently of tokens."""
    ledger = make_ledger(limit_tokens=100_000, limit_calls=2, quota={"analyst": 1.0})
    ledger.reserve("market_analyst", "analyst", "quick", "c1")
    ledger.reserve("market_analyst", "analyst", "quick", "c2")

    with pytest.raises(BudgetDenied) as excinfo:
        ledger.reserve("market_analyst", "analyst", "quick", "c3")

    assert excinfo.value.reason == "call_limit"
    assert ledger.remaining("global") == 98_000


def test_nt3_settle_is_idempotent() -> None:
    """INV-002: settling the same call twice must not charge twice."""
    ledger = make_ledger()
    ledger.reserve("market_analyst", "analyst", "quick", "c1")
    first = ledger.settle("c1", 600, 400)
    events_after_first = len(ledger.events())
    second = ledger.settle("c1", 600, 400)

    assert first == second
    assert len(ledger.events()) == events_after_first
    assert ledger.snapshot()["spent"] == ESTIMATE


def test_nt4_settle_above_reservation_is_recorded_and_closes_the_ledger() -> None:
    """INV-002: an overrun is recorded explicitly and stops further calls."""
    ledger = make_ledger(limit_tokens=10_000, quota={"analyst": 1.0})
    ledger.reserve("market_analyst", "analyst", "quick", "c1")
    settlement = ledger.settle("c1", 9_000, 6_000)

    assert settlement.overrun == 14_000
    assert "over_budget" in event_types(ledger)
    assert ledger.state == "exhausted"

    with pytest.raises(BudgetDenied):
        ledger.reserve("market_analyst", "analyst", "quick", "c2")


def test_nt5_parallel_analysts_never_oversell() -> None:
    """AC-2: 16 threads against a 10-call budget admit exactly 10 calls."""
    ledger = make_ledger(limit_tokens=1_000_000, limit_calls=10, quota={"analyst": 1.0})
    granted: list[str] = []
    denied: list[str] = []
    guard = threading.Lock()

    def worker(index: int) -> None:
        try:
            ledger.reserve("market_analyst", "analyst", "quick", f"c{index}")
        except BudgetDenied as exc:
            with guard:
                denied.append(exc.reason)
        else:
            with guard:
                granted.append(f"c{index}")

    threads = [threading.Thread(target=worker, args=(index,)) for index in range(16)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert len(granted) == 10
    assert len(denied) == 6
    assert ledger.snapshot()["reservations"] == 10


def test_nt6_degradation_level_cannot_regress() -> None:
    """INV-006: lowering the level is rejected and leaves the level unchanged."""
    ledger = make_ledger()
    ledger.apply_level(3)

    with pytest.raises(LevelRegression):
        ledger.apply_level(2)

    assert ledger.level == 3


def test_nt7_each_level_change_emits_exactly_one_event() -> None:
    """INV-006: a jump forward is allowed but still leaves one event per change."""
    ledger = make_ledger()
    ledger.apply_level(2)
    ledger.apply_level(5)

    degraded = [event for event in ledger.events() if event.type == "degraded"]
    assert [event.level for event in degraded] == [2, 5]


def test_nt8_invalid_configuration_fails_closed() -> None:
    """FR-002: an invalid configuration is rejected at construction time."""
    with pytest.raises(ContractError):
        LedgerConfig(limit_tokens=0)
    with pytest.raises(ContractError):
        LedgerConfig(stage_quota={"analyst": 0.5})
    with pytest.raises(ContractError):
        LedgerConfig(l3_threshold=0.1, l4_threshold=0.2)


def test_nt9_releasing_a_settled_call_changes_nothing() -> None:
    """INV-002: a settled call cannot be refunded a second time."""
    ledger = make_ledger()
    ledger.reserve("market_analyst", "analyst", "quick", "c1")
    ledger.settle("c1", 600, 400)
    events_before = ledger.events()

    ledger.release("c1")

    assert ledger.events() == events_before
    assert ledger.remaining("global") == 99_000


def test_nt10_events_are_json_serialisable() -> None:
    """NFR-004 readiness: emitted events carry only primitive JSON values."""
    import json

    ledger = make_ledger()
    ledger.reserve("market_analyst", "analyst", "quick", "c1")
    ledger.settle("c1", 600, 400)
    ledger.apply_level(1)

    for event in ledger.events():
        json.dumps(event.to_dict())


# ----------------------------------------------------------------- degradation


def test_pt8_l1_when_the_stage_is_close_to_exhausted() -> None:
    """FR-006: a stage with less than 1.5 calls left triggers L1."""
    ledger = make_ledger(limit_tokens=100_000, quota={"analyst": 0.10, "debate": 0.90})
    for index in range(9):
        ledger.reserve("market_analyst", "analyst", "quick", f"c{index}")

    policy = DegradationPolicy(ledger.config)
    assert policy.evaluate(ledger, "analyst") == 1


def test_pt9_l2_when_the_stage_cannot_fund_one_call() -> None:
    """FR-006: a stage with less than one call left triggers L2."""
    ledger = make_ledger(limit_tokens=10_500, quota={"analyst": 0.10, "debate": 0.90})
    ledger.reserve("market_analyst", "analyst", "quick", "c1")

    policy = DegradationPolicy(ledger.config)
    assert policy.evaluate(ledger, "analyst") == 2


def test_pt10_l3_when_the_global_pool_crosses_the_threshold() -> None:
    """FR-006: the global pool below 15% forces the cheap model tier (L3)."""
    ledger = make_ledger(limit_tokens=100_000, quota={"analyst": 1.0})
    for index in range(86):
        ledger.reserve("market_analyst", "analyst", "quick", f"c{index}")

    policy = DegradationPolicy(ledger.config)
    assert policy.evaluate(ledger, "analyst") == 3


def test_pt11_l4_when_the_global_pool_crosses_the_lower_threshold() -> None:
    """FR-006: the global pool below 10% drops optional agents (L4)."""
    ledger = make_ledger(limit_tokens=100_000, quota={"analyst": 1.0})
    for index in range(91):
        ledger.reserve("market_analyst", "analyst", "quick", f"c{index}")

    policy = DegradationPolicy(ledger.config)
    assert policy.evaluate(ledger, "analyst") == 4


def test_pt12_l5_when_the_global_pool_cannot_fund_one_call() -> None:
    """FR-006: less than one call of headroom means a degraded verdict (L5)."""
    ledger = make_ledger(limit_tokens=10_000, quota={"analyst": 1.0})
    for index in range(10):
        ledger.reserve("market_analyst", "analyst", "quick", f"c{index}")

    policy = DegradationPolicy(ledger.config)
    assert policy.evaluate(ledger, "analyst") == 5


def test_pt13_policy_returns_none_when_the_level_already_applies() -> None:
    """INV-006: the policy never proposes a level at or below the current one."""
    ledger = make_ledger(limit_tokens=100_000, quota={"analyst": 1.0})
    for index in range(86):
        ledger.reserve("market_analyst", "analyst", "quick", f"c{index}")
    policy = DegradationPolicy(ledger.config)
    ledger.apply_level(3)

    assert policy.evaluate(ledger, "analyst") is None


def test_pt14_level_effects_are_derived_from_the_level() -> None:
    """FR-006: each level maps to one concrete behaviour, not to a model judgement."""
    ledger = make_ledger()
    policy = DegradationPolicy(ledger.config)

    assert policy.debate_rounds(1, 3) == 3
    assert policy.debate_rounds(2, 3) == 2
    assert policy.debate_rounds(5, 1) == 1
    assert policy.forced_tier(2, "deep") == "deep"
    assert policy.forced_tier(3, "deep") == "quick"
    assert policy.skipped_agents(3) == ()
    assert policy.skipped_agents(4) == ("sentiment", "news")
    assert policy.pm_verdict(4) == "any"
    assert policy.pm_verdict(5) == "hold_only"


# -------------------------------------------------------------------- context


def test_pt15_section_budgets_stay_within_the_available_total() -> None:
    """FR-002 / D2.2: the section budget never exceeds the call's allowance."""
    available = 10_000
    total = sum(budget_for_section(section, available) for section in SECTIONS)

    assert total <= available
    assert all(budget_for_section(section, available) > 0 for section in SECTIONS)


def test_pt16_compaction_triggers_above_the_threshold() -> None:
    """AC-5: compaction is decided by the threshold, not by a model."""
    assert should_compact(12_001, 12_000) is True
    assert should_compact(12_000, 12_000) is False


def test_pt17_compaction_keeps_the_newest_messages() -> None:
    """AC-5: compaction bounds the context and preserves the current turn."""
    messages = [f"message {index} " + "word " * 20 for index in range(40)]
    result = compact(messages, 60)

    assert sum(count_tokens(message) for message in result) <= 60
    assert result[-1] == messages[-1]
    assert result[0].startswith("[COMPACTED]")


def test_nt11_compaction_requires_a_positive_target() -> None:
    """AC-5: an invalid compaction target fails closed."""
    with pytest.raises(ContractError):
        compact(["a b c"], 0)


def test_pt18_reinjection_carries_all_four_blocks() -> None:
    """AC-5: the four constraint blocks are present after re-injection."""
    result = reinject(["hello"], identity="NVDA 2026-09-01", level=3, remaining_fraction=0.12)
    joined = "\n".join(result)

    for marker in REQUIRED_MARKERS:
        assert marker in joined
    assert "NVDA 2026-09-01" in joined


def test_nt12_missing_constraint_block_fails_closed() -> None:
    """AC-5: an assembly missing a constraint block is rejected."""
    with pytest.raises(ContractError):
        assert_manifest([SAFETY_BLOCK, "[IDENTITY] NVDA"])


def test_pt19_full_assembly_compacts_and_keeps_constraints() -> None:
    """AC-5: the pipeline compacts a long context and still carries the blocks."""
    messages = [f"turn {index} " + "word " * 30 for index in range(60)]
    before = sum(count_tokens(message) for message in messages)

    assembled = assemble_context(
        messages,
        identity="NVDA 2026-09-01",
        level=2,
        remaining_fraction=0.08,
        compact_threshold=200,
        compact_target=80,
    )

    after = sum(count_tokens(message) for message in assembled)
    assert after < before
    for marker in REQUIRED_MARKERS:
        assert any(marker in message for message in assembled)


def test_nt13_assembly_rejects_an_invalid_target() -> None:
    """AC-5: a compaction target above the threshold is a configuration error."""
    with pytest.raises(ContractError):
        assemble_context(
            ["hello"],
            identity="NVDA",
            level=0,
            remaining_fraction=0.9,
            compact_threshold=100,
            compact_target=200,
        )


# ----------------------------------------------------------------- structure


def test_budget_module_does_not_import_sibling_leaf_modules() -> None:
    """NFR-005: the budget leaf module must not depend on A, C, D or E."""
    from pathlib import Path

    root = Path(__file__).resolve().parents[2] / "tradingagents" / "course" / "budget"
    sources = sorted(root.glob("*.py"))
    assert sources, "budget package not found"

    forbidden = ("evidence", "safety", "data_quality", "audit")
    for path in sources:
        text = path.read_text(encoding="utf-8")
        for name in forbidden:
            assert f"course.{name}" not in text, f"{path.name} imports course.{name}"
            assert f"from ..{name}" not in text, f"{path.name} imports ..{name}"


def test_nt14_duplicate_id_is_rejected_before_any_charge() -> None:
    """INV-002: a duplicate call id must not mutate a quota on its way out."""
    ledger = make_ledger(limit_tokens=1_000, quota={"analyst": 1.0})
    ledger.reserve("market_analyst", "analyst", "quick", "same")
    before_budget = dict(ledger.snapshot()["stage_budget"])
    before_events = len(ledger.events())

    with pytest.raises(ContractError):
        ledger.reserve("market_analyst", "trader", "quick", "same")

    assert ledger.snapshot()["stage_budget"] == before_budget
    assert len(ledger.events()) == before_events


def test_nt15_reusing_a_settled_id_leaks_no_outstanding() -> None:
    """INV-002: a settled call id cannot be reused, and nothing stays reserved."""
    ledger = make_ledger(limit_tokens=1_000, quota={"analyst": 1.0})
    reservation = ledger.reserve("market_analyst", "analyst", "quick", "same")
    ledger.settle(reservation.call_id, 30, 10)

    with pytest.raises(ContractError):
        ledger.reserve("market_analyst", "analyst", "quick", "same")

    assert ledger.snapshot()["outstanding"] == 0

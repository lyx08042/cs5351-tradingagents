"""Offline tests for the FR-002 budget ledger.

No network, no model call, no API key: the clock, the id factory and the
estimate table are injected, so every assertion is deterministic.

Each test names the requirement it verifies (course D4).
"""

from __future__ import annotations

import threading

import pytest

from tradingagents.course.budget.contracts import (
    STAGES,
    BudgetDenied,
    ContractError,
    LedgerConfig,
    LevelRegression,
)
from tradingagents.course.budget.ledger import BudgetLedger

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

"""Offline tests for the budget proxy at the model-client boundary (M4).

The fake model mimics the two methods the graph actually uses, so these tests
prove the accounting without a provider, a network call or an API key.
"""

from __future__ import annotations

import pytest

from tradingagents.course.budget.contracts import STAGES, LedgerConfig
from tradingagents.course.budget.integration import (
    BudgetedChatModel,
    BudgetExhausted,
    stage_for_node,
    wrap_models,
)
from tradingagents.course.budget.ledger import BudgetLedger

ESTIMATE = 1_000


class FakeResponse:
    def __init__(self, usage: tuple[int, int] | None) -> None:
        if usage is not None:
            self.usage_metadata = {"input_tokens": usage[0], "output_tokens": usage[1]}


class FakeModel:
    """Stands in for a chat model: counts calls, returns a usage payload."""

    def __init__(self, usage: tuple[int, int] | None = (100, 50), fail: bool = False) -> None:
        self.usage = usage
        self.fail = fail
        self.calls = 0

    def invoke(self, input, config=None, **kwargs):
        self.calls += 1
        if self.fail:
            raise RuntimeError("provider exploded")
        return FakeResponse(self.usage)

    def bind_tools(self, tools, **kwargs):
        return FakeModel(self.usage, self.fail)

    def with_structured_output(self, schema, **kwargs):
        return FakeModel(self.usage, self.fail)


def make_ledger(limit_tokens: int = 100_000, limit_calls: int = 100) -> BudgetLedger:
    config = LedgerConfig(
        limit_tokens=limit_tokens,
        limit_calls=limit_calls,
        estimate_margin=1.0,
    )
    estimates = {(None, stage): ESTIMATE for stage in STAGES}
    return BudgetLedger(config, stage_estimates=estimates)


def test_pt20_invoke_reserves_then_settles_the_reported_usage() -> None:
    """FR-002: one model call produces exactly one reserve and one settle."""
    ledger = make_ledger()
    proxy = BudgetedChatModel(FakeModel(usage=(100, 50)), ledger, model_tier="quick")

    proxy.invoke("hello")

    assert [event.type for event in ledger.events()] == ["reserve", "settle"]
    assert ledger.snapshot()["spent"] == 150
    assert ledger.remaining("global") == 99_850


def test_pt21_unreported_usage_consumes_the_whole_reservation() -> None:
    """FR-002: a provider that hides its counters cannot defeat the budget."""
    ledger = make_ledger()
    proxy = BudgetedChatModel(FakeModel(usage=None), ledger, model_tier="quick")

    proxy.invoke("hello")

    assert ledger.snapshot()["spent"] == ESTIMATE
    assert ledger.remaining("global") == 99_000


def test_pt22_bound_tools_stay_metered() -> None:
    """FR-002: tool-bound calls are still charged to the same ledger."""
    ledger = make_ledger()
    proxy = BudgetedChatModel(FakeModel(), ledger, model_tier="quick")
    bound = proxy.bind_tools([])

    assert isinstance(bound, BudgetedChatModel)
    bound.invoke("hello")
    assert ledger.snapshot()["spent"] > 0


def test_pt23_structured_output_stays_metered() -> None:
    """FR-002: structured agents (managers, trader) are metered too."""
    ledger = make_ledger()
    proxy = BudgetedChatModel(FakeModel(), ledger, model_tier="deep")
    structured = proxy.with_structured_output(dict)

    assert isinstance(structured, BudgetedChatModel)
    structured.invoke("hello")
    assert ledger.snapshot()["spent"] > 0


def test_pt24_stage_is_taken_from_the_langgraph_node() -> None:
    """FR-002: the node name decides which stage quota is charged."""
    ledger = make_ledger()
    proxy = BudgetedChatModel(FakeModel(), ledger, model_tier="quick")
    before = ledger.remaining("debate")

    proxy.invoke("hello", config={"metadata": {"langgraph_node": "Bull Researcher"}})

    assert ledger.remaining("debate") < before


def test_pt25_stage_mapping_covers_the_graph_nodes() -> None:
    """FR-002: node names map onto ledger stages."""
    assert stage_for_node("Market Analyst") == "analyst"
    assert stage_for_node("Bull Researcher") == "debate"
    assert stage_for_node("Research Manager") == "research_manager"
    assert stage_for_node("Trader") == "trader"
    assert stage_for_node("Aggressive Risk Analyst") == "risk_debate"
    assert stage_for_node("Portfolio Manager") == "portfolio_manager"
    assert stage_for_node(None) == "analyst"


def test_pt26_wrap_models_returns_both_tiers() -> None:
    """FR-002: both model tiers are wrapped by one call."""
    ledger = make_ledger()
    quick, deep = wrap_models(FakeModel(), FakeModel(), ledger)

    quick.invoke("a")
    deep.invoke("b")

    tiers = [event.model_tier for event in ledger.events() if event.type == "reserve"]
    assert tiers == ["quick", "deep"]


def test_nt14_failed_call_releases_the_reservation() -> None:
    """INV-002: a provider error must not consume budget."""
    ledger = make_ledger()
    proxy = BudgetedChatModel(FakeModel(fail=True), ledger, model_tier="quick")

    with pytest.raises(RuntimeError):
        proxy.invoke("hello")

    assert [event.type for event in ledger.events()] == ["reserve", "release"]
    assert ledger.remaining("global") == 100_000


def test_nt15_exhausted_ledger_blocks_the_call_entirely() -> None:
    """FR-002: a denied call never reaches the provider."""
    ledger = make_ledger(limit_calls=1)
    ledger.reserve("graph", "analyst", "quick", "c1")
    model = FakeModel()
    proxy = BudgetedChatModel(model, ledger, model_tier="quick")

    with pytest.raises(BudgetExhausted) as excinfo:
        proxy.invoke("hello")

    assert excinfo.value.reason == "call_limit"
    assert model.calls == 0

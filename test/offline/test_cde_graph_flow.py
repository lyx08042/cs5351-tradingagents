"""Real-graph CDE course flow: compiled LangGraph, scripted model, offline vendors.

Anchors: FR-003, FR-004, FR-005, INV-003, INV-004, INV-005, ADR-004. These
tests intentionally do not replace ``propagate``, ``_run_graph``, the compiled
graph or the Portfolio Manager node. The real graph runs every analyst, debate,
manager and PM step; only the model client and market-data vendors are scripted.
No network, credentials or .env access is used, and all SQLite/cache paths live
under ``tmp_path``.
"""

from __future__ import annotations

import copy
import json
import socket

import pandas as pd
import pytest
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.runnables import RunnableLambda
from pydantic import Field
from typer.testing import CliRunner

import cli.main as cli_main
from cli.main import app
from tradingagents.agents import context, schemas
from tradingagents.agents.analysts import sentiment_analyst
from tradingagents.course.audit import AuditStore, replay_run
from tradingagents.course.pipeline import (
    V1_RULE_VERSION,
    CourseRequest,
    gate_registry,
)
from tradingagents.dataflows import router
from tradingagents.dataflows.vendors.yahoo import market as yahoo_market, snapshot
from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.graph import trading_graph

TRADE_DATE = "2026-01-09"
TEXT = "Report.\n\n**Rating**: Buy\n\nFINAL TRANSACTION PROPOSAL: **BUY**"
ARGS = {
    "symbol": "NVDA",
    "ticker": "NVDA",
    "curr_date": TRADE_DATE,
    "start_date": "2026-01-02",
    "end_date": TRADE_DATE,
    "indicator": "rsi",
    "topic": "Fed rate cut",
    "freq": "quarterly",
}

STRUCTURED = {
    schemas.ResearchPlan: schemas.ResearchPlan(
        recommendation=schemas.PortfolioRating.BUY,
        rationale="r",
        strategic_actions="a",
    ),
    schemas.TraderProposal: schemas.TraderProposal(
        action=schemas.TraderAction.BUY, reasoning="r"
    ),
    schemas.SentimentReport: schemas.SentimentReport(
        overall_band=schemas.SentimentBand.NEUTRAL,
        overall_score=5.0,
        confidence="low",
        narrative="n",
    ),
}


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    """Make an accidental network attempt fail loudly in this offline file."""

    def blocked(*args, **kwargs):
        raise AssertionError("offline CDE graph test attempted network access")

    monkeypatch.setattr(socket, "create_connection", blocked)
    monkeypatch.setattr(socket, "getaddrinfo", blocked)


@pytest.fixture
def offline(monkeypatch):
    """Every vendor answers offline; returns the router methods actually called."""
    called: set[str] = set()
    for method, vendors in router.VENDOR_METHODS.items():
        for vendor in vendors:
            monkeypatch.setitem(
                vendors,
                vendor,
                lambda *a, _m=method, **k: called.add(_m) or f"{_m} data",
            )
    prices = pd.DataFrame(
        {
            "Date": pd.bdate_range(end=TRADE_DATE, periods=60),
            "Open": 100.0,
            "High": 101.0,
            "Low": 99.0,
            "Close": 100.5,
            "Volume": 1_000_000,
        }
    )
    monkeypatch.setattr(
        snapshot, "load_ohlcv", lambda *a, **k: called.add("ohlcv") or prices.copy()
    )
    monkeypatch.setattr(
        sentiment_analyst, "fetch_stocktwits_messages", lambda *a, **k: "no posts"
    )
    monkeypatch.setattr(
        sentiment_analyst, "fetch_reddit_posts", lambda *a, **k: "no posts"
    )
    monkeypatch.setattr(
        yahoo_market.yf,
        "Ticker",
        lambda s: type("T", (), {"info": {"longName": "NVIDIA"}})(),
    )
    context._identity.cache_clear()
    return called


class CourseScriptedModel(BaseChatModel):
    """Scripted model that returns a PM SimulationCandidate in course mode."""

    structured: bool = True
    tools: tuple = ()
    units: str = "5"
    price: str = "100"
    calls: list = Field(default_factory=list)
    prompts: list = Field(default_factory=list)

    @property
    def _llm_type(self) -> str:
        return "course-scripted"

    def bind_tools(self, tools, **kwargs):
        return self.model_copy(update={"tools": tuple(tools)})

    def with_structured_output(self, schema, **kwargs):
        if not self.structured:
            raise NotImplementedError
        if schema is schemas.PortfolioDecision:
            payload = schemas.PortfolioDecision(
                rating=schemas.PortfolioRating.BUY,
                executive_summary="s",
                investment_thesis="thesis",
                simulation_proposal=schemas.SimulationCandidate(
                    action="buy",
                    units=self.units,
                    price=self.price,
                    currency="USD",
                ),
            )
        else:
            payload = STRUCTURED[schema]

        def invoke(prompt):
            self.prompts.append(str(prompt))
            self.calls.append(1)
            return payload

        return RunnableLambda(invoke)

    def _generate(self, messages, stop=None, run_manager=None, **kwargs) -> ChatResult:
        self.calls.append(1)
        self.prompts.append("\n".join(str(message.content) for message in messages))
        if self.tools and not isinstance(messages[-1], ToolMessage):
            calls = [
                {
                    "name": tool.name,
                    "id": f"call_{index}",
                    "args": {
                        key: value
                        for key, value in ARGS.items()
                        if key in tool.tool_call_schema.model_json_schema()["properties"]
                    },
                }
                for index, tool in enumerate(self.tools)
            ]
            message = AIMessage(content="", tool_calls=calls)
        else:
            message = AIMessage(content=TEXT)
        return ChatResult(generations=[ChatGeneration(message=message)])


class _Client:
    def __init__(self, model):
        self.model = model

    def get_llm(self):
        return self.model


def _config(tmp_path):
    cfg = copy.deepcopy(DEFAULT_CONFIG)
    cfg.update(
        results_dir=str(tmp_path / "results"),
        data_cache_dir=str(tmp_path / "cache"),
        memory_log_path=str(tmp_path / "memory.md"),
    )
    return cfg


def _graph(tmp_path, monkeypatch, model):
    monkeypatch.setattr(
        trading_graph,
        "create_tier_client",
        lambda config, tier, **k: _Client(model),
    )
    return trading_graph.TradingAgentsGraph(config=_config(tmp_path))


def _observations():
    return [
        {
            "domain": domain,
            "kind": "value",
            "source": "fixture",
            "observed_as_of": TRADE_DATE,
            "value": 1,
            "value_present": True,
        }
        for domain in ("news", "social", "macro", "price", "fundamentals")
    ]


def _request(tmp_path, units="5", price="100", run_id="cde-e2e-1"):
    data = {
        "run_id": run_id,
        "timestamp": "2026-01-09T15:00:00+00:00",
        "analysis_cutoff": TRADE_DATE,
        "observations": _observations(),
        "holdings_snapshot": {
            "snapshot_id": "acct-e2e-20260109",
            "as_of": TRADE_DATE,
            "currency": "USD",
            "cash": "1000.00",
            "positions": {"NVDA": "10"},
            "flat_declared": False,
        },
        "instrument": "NVDA",
        "instrument_currency": "USD",
        "rule_version": V1_RULE_VERSION,
        "audit_path": str(tmp_path / "audit.sqlite"),
    }
    return CourseRequest.from_mapping(data)


@pytest.mark.unit
@pytest.mark.parametrize(
    "units, out_of_cash, expected_signal, expected_entry, expected_reason",
    [
        ("5", False, "Buy", "decision", "accepted"),
        ("20", True, "REVIEW", "rejection", "insufficient_cash"),
    ],
    ids=["accepted-buy", "over-cash"],
)
def test_real_graph_course_flow_publishes_only_c_accepted_candidates(
    tmp_path, monkeypatch, offline, units, out_of_cash, expected_signal,
    expected_entry, expected_reason,
):
    model = CourseScriptedModel(units=units, price="100")
    graph = _graph(tmp_path, monkeypatch, model)
    request = _request(tmp_path, units=units)

    final_state, signal = graph.propagate(
        "NVDA", TRADE_DATE, course_request=request
    )

    assert signal == expected_signal
    assert final_state["final_rating"] == "Buy"
    for key in (
        "market_report",
        "sentiment_report",
        "news_report",
        "fundamentals_report",
        "investment_plan",
        "trader_investment_plan",
        "final_trade_decision",
    ):
        assert final_state[key].strip(), key
    assert final_state["risk_debate_state"]["history"].strip()
    assert final_state["simulation_proposal"]["action"] == "buy"
    assert any("Course simulation mode" in prompt for prompt in model.prompts)
    assert {"get_stock_data", "get_indicators", "get_news", "get_fundamentals", "ohlcv"} <= offline

    result = final_state["course_result"]
    assert result["outcome"] == ("rejected" if out_of_cash else "accepted")
    assert result["published"] is (not out_of_cash)
    assert result["safety"]["reason_code"] == expected_reason
    if out_of_cash:
        assert result["proposal"] is None
    else:
        assert result["proposal"]["action"] == "buy"
        assert result["proposal"]["units"] == "5"

    with AuditStore.open(request.audit_path) as store:
        record = store.get(f"cde:{request.run_id}")
        assert record is not None
        assert record.entry_type == expected_entry
        replay = replay_run(store, request.run_id, gate_registry())
        assert replay.status == "pass"
        assert replay.gate_total == 1


@pytest.mark.unit
def test_cli_course_inputs_uses_the_real_graph_and_audits_the_result(
    tmp_path, monkeypatch, offline
):
    model = CourseScriptedModel(units="5", price="100")
    monkeypatch.setattr(
        trading_graph,
        "create_tier_client",
        lambda config, tier, **k: _Client(model),
    )
    monkeypatch.setattr(cli_main, "DEFAULT_CONFIG", _config(tmp_path))
    request = _request(tmp_path, units="5", run_id="cde-cli-1")
    input_path = tmp_path / "course-input.json"
    input_path.write_text(json.dumps(request.to_dict()), encoding="utf-8")

    result = CliRunner().invoke(
        app,
        [
            "--ticker",
            "NVDA",
            "--date",
            TRADE_DATE,
            "--course-inputs",
            str(input_path),
            "--no-save",
            "--no-show",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Course outcome: accepted" in result.output
    assert "Verified simulation proposal" in result.output
    assert any("Course simulation mode" in prompt for prompt in model.prompts)

    with AuditStore.open(request.audit_path) as store:
        record = store.get(f"cde:{request.run_id}")
        assert record is not None
        assert record.entry_type == "decision"
        replay = replay_run(store, request.run_id, gate_registry())
        assert replay.status == "pass"
        assert replay.gate_total == 1

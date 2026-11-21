"""Offline, deterministic end-to-end tests for evidence-mode debate (FR-001 M3).

These tests run the real graph setup and the real evidence-mode nodes with scripted
models and no network. A14 full B/C/D/E interoperability remains **PENDING** until
PRs #3/#4/#5/M3 share one baseline.
"""

from __future__ import annotations

import copy
import json
import math
import sys
from pathlib import Path

import pandas as pd
import pytest
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import Field

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tradingagents.agents import context  # noqa: E402
from tradingagents.agents.analysts import sentiment_analyst  # noqa: E402
from tradingagents.agents.researchers.bear_researcher import create_bear_researcher  # noqa: E402
from tradingagents.agents.researchers.bull_researcher import create_bull_researcher  # noqa: E402
from tradingagents.course import evidence as EV  # noqa: E402
from tradingagents.course.evidence import integration as I  # noqa: E402
from tradingagents.dataflows import router  # noqa: E402
from tradingagents.dataflows.vendors.yahoo import market as yahoo_market, snapshot  # noqa: E402
from tradingagents.default_config import DEFAULT_CONFIG  # noqa: E402
from tradingagents.graph import trading_graph  # noqa: E402

TRADE_DATE = "2026-01-09"
TEXT = "Report.\n\n**Rating**: Overweight\n\nFINAL TRANSACTION PROPOSAL: **BUY**"
PLAN = "Plan.\n\n**Rating**: Overweight\n\nFINAL TRANSACTION PROPOSAL: **BUY**"
_MISSING = object()


def assert_strict_json(value):
    """Assert plain JSON: no tuples, sets, non-finite floats or lone surrogates."""
    if value is None or isinstance(value, bool):
        return
    if type(value) is int:
        return
    if isinstance(value, str):
        value.encode("utf-8")
        return
    if isinstance(value, float):
        assert math.isfinite(value)
        return
    if isinstance(value, list):
        for item in value:
            assert_strict_json(item)
        return
    assert isinstance(value, dict)
    for key, item in value.items():
        assert type(key) is str
        key.encode("utf-8")
        assert_strict_json(item)


class EvidenceScriptedModel(BaseChatModel):
    """A scripted chat model: claims for evidence prompts, TEXT/PLAN elsewhere."""

    replies: list[str] = Field(default_factory=list)
    prompts: list[str] = Field(default_factory=list)
    plan: str = PLAN

    @property
    def _llm_type(self) -> str:
        return "evidence-scripted"

    def bind_tools(self, tools, **kwargs):
        return self

    def with_structured_output(self, schema, **kwargs):
        raise NotImplementedError

    def _generate(self, messages, stop=None, run_manager=None, **kwargs) -> ChatResult:
        prompt = messages[-1].content if messages else ""
        if not isinstance(prompt, str):
            prompt = str(prompt)
        self.prompts.append(prompt)
        if "EVIDENCE_CONTEXT_JSON" in prompt:
            text = self.replies.pop(0) if self.replies else json.dumps({"claims": []})
        elif "**Debate History:**" in prompt:
            text = self.plan
        else:
            text = TEXT
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=text))])


class _Client:
    def __init__(self, model):
        self.model = model

    def get_llm(self):
        return self.model


@pytest.fixture
def offline(monkeypatch):
    """Every vendor answers offline; identity is a deterministic fake."""
    for _method, vendors in router.VENDOR_METHODS.items():
        for vendor in vendors:
            monkeypatch.setitem(vendors, vendor, lambda *a, **k: "offline")
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
    monkeypatch.setattr(snapshot, "load_ohlcv", lambda *a, **k: prices.copy())
    monkeypatch.setattr(sentiment_analyst, "fetch_stocktwits_messages", lambda *a, **k: "no posts")
    monkeypatch.setattr(sentiment_analyst, "fetch_reddit_posts", lambda *a, **k: "no posts")
    monkeypatch.setattr(
        yahoo_market.yf,
        "Ticker",
        lambda s: type("T", (), {"info": {"longName": "NVIDIA"}})(),
    )
    context._identity.cache_clear()


def _graph(tmp_path, monkeypatch, model, **config):
    cfg = copy.deepcopy(DEFAULT_CONFIG)
    cfg.update(
        results_dir=str(tmp_path / "results"),
        data_cache_dir=str(tmp_path / "cache"),
        memory_log_path=str(tmp_path / "log.md"),
        max_debate_rounds=2,
        **config,
    )
    monkeypatch.setattr(
        trading_graph, "create_tier_client", lambda config, tier, **k: _Client(model)
    )
    return trading_graph.TradingAgentsGraph(config=cfg, selected_analysts=("market",))


def _fact(metric, value, subject="NVDA", unit="USD"):
    return EV.Fact.from_record(
        {
            "subject": subject,
            "metric": metric,
            "value": {"kind": "float", "value": value},
            "relation": None,
            "unit": unit,
            "period": TRADE_DATE,
        }
    )


def _unit(
    evidence_id,
    fact,
    *,
    status="available",
    run_id="run-a10",
    published_at=TRADE_DATE,
    available_as_of=TRADE_DATE,
    policy="test",
):
    return {
        "evidence_id": evidence_id,
        "run_id": run_id,
        "source": "tool",
        "content_ref": f"snapshot:NVDA:{evidence_id}",
        "status": status,
        "published_at": published_at,
        "available_as_of": available_as_of,
        "fact": fact.to_dict(),
        "freshness_policy": policy,
    }


def _registry(run_id, units):
    return EV.EvidenceRegistry.build(
        run_id=run_id,
        as_of=TRADE_DATE,
        candidates=[{**unit, "run_id": run_id} for unit in units],
    )


def _context(registry, *, decision=_MISSING, as_of=TRADE_DATE, policy=None):
    policy = policy if policy is not None else EV.FreshnessPolicy(name="test", max_age_days=10)
    payload = {
        "as_of": as_of,
        "registry": registry.to_dict(),
        "policy": policy.to_dict(),
    }
    if decision is not _MISSING:
        payload["data_admission_decision"] = decision
    return payload


def _claim(claim_id, text, fact, refs, classification="factual"):
    return {
        "claim_id": claim_id,
        "text": text,
        "classification": classification,
        "fact": None if fact is None else fact.to_dict(),
        "evidence_refs": list(refs),
    }


def _claims(claims):
    return json.dumps({"claims": claims})


@pytest.mark.unit
def test_a10_real_graph_four_turns_and_manager_prompt(tmp_path, monkeypatch, offline):
    fact_close = _fact("close", 100.5)
    fact_volume = _fact("volume", 1_000_000.0)
    units = [_unit("ev-close", fact_close), _unit("ev-volume", fact_volume)]
    registry = _registry("run-a10", units)
    evidence_context = _context(registry)
    replies = [
        _claims([_claim("bull-1", "bull close text", fact_close, ["ev-close"])]),
        _claims([_claim("bear-1", "bear volume text", fact_volume, ["ev-volume"])]),
        _claims([_claim("bull-2", "bull close again", fact_close, ["ev-close"])]),
        _claims([_claim("bear-2", "bear volume again", fact_volume, ["ev-volume"])]),
    ]
    model = EvidenceScriptedModel(replies=list(replies))
    graph = _graph(tmp_path, monkeypatch, model)

    state, rating = graph.propagate_with_evidence(
        "NVDA", TRADE_DATE, evidence_context=evidence_context
    )

    assert rating == "Overweight"
    audit = state["evidence_verdicts"]
    assert len(audit) == 4
    assert [item["speaker"] for item in audit] == ["bull", "bear", "bull", "bear"]
    assert [item["round"] for item in audit] == [1, 1, 2, 2]
    for record in audit:
        assert set(record) == {
            "speaker",
            "round",
            "verdicts",
            "rejected_refs",
            "as_of",
            "run_id",
        }
        assert record["as_of"] == TRADE_DATE
        assert record["run_id"] == "run-a10"
        assert_strict_json(record)
        json.dumps(record, allow_nan=False)
        for verdict in record["verdicts"]:
            assert verdict["verdict"] == "accept_factual"
            assert verdict["evidence_refs"]
            assert verdict["projection"]
            assert verdict["claim_id"].startswith(("bull-", "bear-"))

    debate = state["investment_debate_state"]
    history = debate["history"]
    assert history.count("Bull Analyst:") == 2
    assert history.count("Bear Analyst:") == 2
    assert "ev-close" in history and "ev-volume" in history
    assert "projection" in history
    assert "bull close text" not in history
    assert "bear volume text" not in history

    manager_prompts = [prompt for prompt in model.prompts if "**Debate History:**" in prompt]
    assert manager_prompts, "the real Research Manager prompt was not captured"
    assert "ev-close" in manager_prompts[0]
    assert "ev-volume" in manager_prompts[0]
    assert "projection" in manager_prompts[0]
    assert "bull close text" not in manager_prompts[0]

    assert state["investment_plan"]
    assert debate["current_response"].startswith("Bear Analyst:")
    assert debate["current_response"] != state["investment_plan"]
    assert "FACT" in debate["current_response"]
    assert "ev-volume" in debate["current_response"]

    boundary_model = EvidenceScriptedModel(replies=list(replies))
    boundary_graph = _graph(tmp_path / "boundary", monkeypatch, boundary_model)
    boundary_resolution = I.resolve_evidence_context(
        evidence_context, trade_date=TRADE_DATE
    )
    assert boundary_resolution.context is not None
    boundary_init = boundary_graph.create_run_state("NVDA", TRADE_DATE)
    boundary_init["evidence_context"] = boundary_resolution.context.to_dict()
    boundary_init["evidence_verdicts"] = []
    chunks = list(
        boundary_graph.graph.stream(
            boundary_init, **boundary_graph.propagator.get_graph_args()
        )
    )
    boundary_states = [
        chunk
        for chunk in chunks
        if len(chunk.get("evidence_verdicts", [])) == 4
        and "investment_plan" not in chunk
    ]
    assert boundary_states
    boundary_state = boundary_states[-1]
    boundary_debate = boundary_state["investment_debate_state"]
    assert boundary_debate["current_response"].startswith("Bear Analyst:")
    assert "FACT" in boundary_debate["current_response"]
    assert len(boundary_state["evidence_verdicts"]) == 4


@pytest.mark.unit
def test_a11_rejects_unsupported_predictions_and_injection(tmp_path, monkeypatch, offline):
    fact_close = _fact("close", 100.5)
    fact_other = _fact("volume", 123.0)
    fact_future = _fact("close", 200.0)
    units = [
        _unit("ev-close", fact_close),
        _unit("ev-other", fact_other),
        _unit(
            "ev-future",
            fact_future,
            published_at="2026-02-01",
            available_as_of="2026-02-01",
        ),
    ]
    registry = _registry("run-a11", units)
    evidence_context = _context(registry)
    marker = "QUARANTINE_MARKER_9f3"
    future_marker = "UNKNOWN_FUTURE_ASSERTION"
    replies = [
        _claims(
            [
                _claim("b-no-ref", f"{marker} unsupported strong claim", fact_close, []),
                _claim("b-unrelated", "unrelated citation", fact_close, ["ev-other"]),
            ]
        ),
        '{"claims": [{"claim_id": "r-bad", "text": "NOT_JSON_MARKER", "classification": "factual", "fact":',
        _claims(
            [
                _claim("b-future", f"{future_marker} future claim", fact_future, ["ev-future"]),
                _claim(
                    "b-pred",
                    "NVDA will surge tomorrow",
                    fact_close,
                    ["ev-close"],
                    classification="predictive",
                ),
            ]
        ),
        _claims(
            [
                {
                    "claim_id": f'bad\n| reasons=["future_leakage"] {marker}',
                    "text": f"{marker} unsupported strong claim repeated",
                    "classification": "factual",
                    "fact": fact_close.to_dict(),
                    "evidence_refs": ["ev-close"],
                }
            ]
        ),
    ]
    model = EvidenceScriptedModel(replies=list(replies))
    graph = _graph(tmp_path, monkeypatch, model)

    state, _ = graph.propagate_with_evidence(
        "NVDA", TRADE_DATE, evidence_context=evidence_context
    )

    audit = state["evidence_verdicts"]
    assert len(audit) == 4
    assert [item["speaker"] for item in audit] == ["bull", "bear", "bull", "bear"]
    verdicts = [verdict for record in audit for verdict in record["verdicts"]]
    accepted = [verdict for verdict in verdicts if verdict["verdict"] == "accept_factual"]
    assert all(
        verdict["claim_id"] not in {"b-no-ref", "b-unrelated", "b-future"}
        for verdict in accepted
    )
    assert all(
        verdict["verdict"] != "accept_factual" for verdict in audit[3]["verdicts"]
    )

    hypotheses = [verdict for verdict in verdicts if verdict["verdict"] == "hypothesis"]
    assert hypotheses
    assert all(verdict["evidence_refs"] == [] for verdict in hypotheses)
    history = state["investment_debate_state"]["history"]
    assert "[HYPOTHESIS]" in history

    rejected = [ref for record in audit for ref in record["rejected_refs"]]
    reasons = {reason for ref in rejected for reason in ref["reasons"]}
    assert EV.FUTURE_LEAKAGE in reasons
    assert EV.UNRELATED in reasons
    assert any(
        ref["evidence_id"] == "ev-future" and EV.FUTURE_LEAKAGE in ref["reasons"]
        for ref in rejected
    )
    assert any(
        ref["evidence_id"] == "ev-other" and EV.UNRELATED in ref["reasons"]
        for ref in rejected
    )

    debate = state["investment_debate_state"]
    for text in (
        debate["history"],
        debate["bull_history"],
        debate["bear_history"],
        debate["current_response"],
    ):
        assert marker not in text
        assert future_marker not in text
        assert "will surge tomorrow" not in text
    for prompt in model.prompts:
        assert marker not in prompt
        assert future_marker not in prompt
        assert "will surge tomorrow" not in prompt
    assert marker not in json.dumps(audit)
    assert future_marker not in json.dumps(audit)
    assert "will surge tomorrow" not in json.dumps(audit)


@pytest.mark.unit
def test_a11_limits_plain_json_and_untrusted_payloads(offline):
    fact = _fact("close", 100.5)
    registry = _registry("run-limits", [_unit("ev-close", fact)])
    policy = EV.FreshnessPolicy(name="test", max_age_days=10)
    good = _context(registry, policy=policy)

    assert not I.resolve_evidence_context(
        {**good, "as_of": "2026-01-08"}, trade_date=TRADE_DATE
    ).allowed
    assert not I.resolve_evidence_context(
        {**good, "registry": {**registry.to_dict(), "units": "not-a-list"}},
        trade_date=TRADE_DATE,
    ).allowed
    assert not I.resolve_evidence_context(
        {**good, "policy": {**policy.to_dict(), "extra": 1}},
        trade_date=TRADE_DATE,
    ).allowed

    tuple_quarantine = registry.to_dict()
    tuple_quarantine["quarantine"] = {
        "conflicted": ("ev-close",),
        "foreign": [],
        "malformed": [],
    }
    assert not I.resolve_evidence_context(
        {**good, "registry": tuple_quarantine}, trade_date=TRADE_DATE
    ).allowed

    bad_key_quarantine = registry.to_dict()
    bad_key_quarantine["quarantine"] = {1: []}
    assert not I.resolve_evidence_context(
        {**good, "registry": bad_key_quarantine}, trade_date=TRADE_DATE
    ).allowed

    resolution = I.resolve_evidence_context(good, trade_date=TRADE_DATE)
    assert resolution.allowed and resolution.context is not None
    context_value = resolution.context
    responses = [
        '{"claims":[],"claims":[]}',
        (
            '{"claims":[{"claim_id":"n","text":"x","classification":"factual",'
            '"fact":{"subject":"NVDA","metric":"close","value":{"kind":"float",'
            '"value":NaN},"relation":null,"unit":"usd","period":"'
            + TRADE_DATE
            + '"},"evidence_refs":["ev-close"]}]}'
        ),
        _claims(
            [
                {
                    "claim_id": "u",
                    "text": "x",
                    "classification": "factual",
                    "fact": fact.to_dict(),
                    "evidence_refs": ["ev-close"],
                    "evidence": {"fake": True},
                }
            ]
        ),
        _claims(
            [
                _claim(
                    "narr",
                    "NVDA is great",
                    None,
                    ["ev-close"],
                )
            ]
        ),
        _claims(
            [
                {
                    "claim_id": "missing-class",
                    "text": "x",
                    "fact": fact.to_dict(),
                    "evidence_refs": ["ev-close"],
                }
            ]
        ),
        _claims(
            [
                {
                    "claim_id": "missing-refs",
                    "text": "x",
                    "classification": "factual",
                    "fact": fact.to_dict(),
                }
            ]
        ),
    ]
    for response in responses:
        turn = I.evaluate_researcher_turn(
            context_value, speaker="bull", round_index=1, response=response
        )
        assert all(verdict.verdict != "accept_factual" for verdict in turn.verdicts)
        assert "NVDA is great" not in turn.history

    surrogate_response = json.dumps(
        {
            "claims": [
                {
                    "claim_id": "surrogate",
                    "text": "x",
                    "classification": "factual",
                    "fact": fact.to_dict(),
                    "evidence_refs": ["ev-\ud800"],
                }
            ]
        },
        ensure_ascii=True,
    )
    surrogate_turn = I.evaluate_researcher_turn(
        context_value, speaker="bull", round_index=1, response=surrogate_response
    )
    audit_record = surrogate_turn.audit_record()
    json.dumps(audit_record, allow_nan=False, ensure_ascii=False).encode("utf-8")
    assert "\ud800" not in json.dumps(audit_record, ensure_ascii=False)


@pytest.mark.unit
def test_a12_missing_unavailable_unknown_and_non_proceed_gates(
    tmp_path, monkeypatch, offline
):
    fact = _fact("close", 100.5)
    units = [
        _unit("ev-valid", fact),
        _unit("ev-missing", fact, published_at=None, available_as_of=None),
        _unit("ev-unavail", fact, status="unavailable"),
        _unit("ev-unknown", fact, status="unknown"),
    ]
    registry = _registry("run-a12", units)
    resolution = I.resolve_evidence_context(_context(registry), trade_date=TRADE_DATE)
    assert resolution.allowed and resolution.context is not None
    context_value = resolution.context

    prompt = I.prepare_prompt_section(context_value)
    assert "ev-valid" in prompt
    for inadmissible in ("ev-missing", "ev-unavail", "ev-unknown"):
        assert inadmissible not in prompt

    response = _claims(
        [
            _claim("c-missing", "m", fact, ["ev-missing"]),
            _claim("c-unavail", "u", fact, ["ev-unavail"]),
            _claim("c-unknown", "k", fact, ["ev-unknown"]),
        ]
    )
    turn = I.evaluate_researcher_turn(
        context_value, speaker="bull", round_index=1, response=response
    )
    rejected_reasons = {reason for ref in turn.rejected_refs for reason in ref.reasons}
    assert {
        EV.MISSING_DATE,
        EV.UNAVAILABLE_STATUS,
        EV.UNKNOWN_STATUS,
    } <= rejected_reasons
    assert all(verdict.verdict != "accept_factual" for verdict in turn.verdicts)

    for index, decision in enumerate(("review", "abstain", 3, {"x": 1})):
        model = EvidenceScriptedModel(replies=[])
        graph = _graph(tmp_path / f"non-proceed-{index}", monkeypatch, model)
        state, rating = graph.propagate_with_evidence(
            "NVDA",
            TRADE_DATE,
            evidence_context=_context(registry, decision=decision),
        )
        assert rating == EV.REVIEW
        assert state["final_rating"] == EV.REVIEW
        assert model.prompts == []
        assert state["evidence_verdicts"]
        assert state["evidence_verdicts"][0]["speaker"] == "bull"
        assert any(
            EV.NON_PROCEED in verdict["reasons"]
            for verdict in state["evidence_verdicts"][0]["verdicts"]
        )

    fallback_contexts = [
        _context(registry, decision=decision)
        for decision in ("review", "abstain", 3, {"x": 1})
    ]
    fallback_contexts.append(_context(registry, as_of="2026-01-08"))
    for factory, speaker in (
        (create_bull_researcher, "bull"),
        (create_bear_researcher, "bear"),
    ):
        for bad_context in fallback_contexts:
            model = EvidenceScriptedModel(replies=[])
            node = factory(model)
            raw_history = "RAW_HISTORY_PROBE"
            raw_bull = "RAW_BULL_PROBE"
            raw_bear = "RAW_BEAR_PROBE"
            raw_current = "RAW_CURRENT_PROBE"
            node_state = {
                "evidence_context": bad_context,
                "trade_date": TRADE_DATE,
                "investment_debate_state": {
                    "history": raw_history,
                    "bull_history": raw_bull,
                    "bear_history": raw_bear,
                    "current_response": raw_current,
                    "count": 1,
                },
                "evidence_verdicts": [
                    {"speaker": "bull", "round": 1, "unserializable": {1, 2}}
                ],
            }
            output = node(node_state)
            assert model.prompts == []
            debate = output["investment_debate_state"]
            assert "[ABSTAIN" in debate["history"]
            assert output["evidence_verdicts"][0]["speaker"] == speaker
            for seed in (raw_history, raw_bull, raw_bear, raw_current):
                assert seed not in debate["history"]
                assert seed not in debate["bull_history"]
                assert seed not in debate["bear_history"]
                assert seed not in debate["current_response"]
            assert debate["count"] == 2
            assert_strict_json(output["evidence_verdicts"])
            json.dumps(
                output["evidence_verdicts"], allow_nan=False, ensure_ascii=False
            ).encode("utf-8")
            assert all(
                verdict["verdict"] != "accept_factual"
                for record in output["evidence_verdicts"]
                for verdict in record["verdicts"]
            )

    invalid_contexts = [
        _context(registry, as_of="2026-01-08"),
        {**_context(registry), "registry": {**registry.to_dict(), "units": "bad"}},
        {**_context(registry), "policy": {"name": "test", "max_age_days": -1}},
    ]
    for index, bad in enumerate(invalid_contexts):
        model = EvidenceScriptedModel(replies=[])
        graph = _graph(tmp_path / f"invalid-{index}", monkeypatch, model)
        with pytest.raises(ValueError):
            graph.propagate_with_evidence("NVDA", TRADE_DATE, evidence_context=bad)
        assert model.prompts == []


@pytest.mark.unit
def test_a13_default_propagate_unchanged_and_checkpoint_rejected(
    tmp_path, monkeypatch, offline
):
    model = EvidenceScriptedModel(replies=[])
    graph = _graph(tmp_path, monkeypatch, model)
    state, rating = graph.propagate("NVDA", TRADE_DATE)

    assert rating == "Overweight"
    assert state.get("evidence_context") is None
    assert state.get("evidence_verdicts") is None
    history = state["investment_debate_state"]["history"]
    assert "Bull Analyst:" in history
    assert "Bear Analyst:" in history
    assert "Report." in history
    assert "EVIDENCE_CONTEXT_JSON" not in history

    manager_prompts = [prompt for prompt in model.prompts if "**Debate History:**" in prompt]
    assert manager_prompts
    assert "EVIDENCE_CONTEXT_JSON" not in manager_prompts[0]

    fact = _fact("close", 100.5)
    registry = _registry("run-a13", [_unit("ev-close", fact)])
    checkpoint_model = EvidenceScriptedModel(replies=[])
    checkpoint_graph = _graph(
        tmp_path / "checkpoint", monkeypatch, checkpoint_model, checkpoint_enabled=True
    )
    monkeypatch.setattr(
        checkpoint_graph,
        "create_run_state",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("state created")),
    )
    with pytest.raises(ValueError, match="checkpoint"):
        checkpoint_graph.propagate_with_evidence(
            "NVDA", TRADE_DATE, evidence_context=_context(registry)
        )
    assert checkpoint_model.prompts == []

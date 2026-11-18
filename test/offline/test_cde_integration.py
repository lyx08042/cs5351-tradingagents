"""Offline integration tests for the CDE pipeline (D -> AI -> C -> E).

Anchors: FR-003, FR-004, FR-005, INV-003, INV-004, INV-005, NFR-003, NFR-004,
NFR-005 and ADR-004. The real D/C/E leaf implementations and a real SQLite audit
store run here; only the model and external inputs are fixed. No network, no
credentials, no live LLM call.
"""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError
from typer.testing import CliRunner

from cli.main import app
from tradingagents.agents.managers import portfolio_manager as pm_module
from tradingagents.agents.schemas import PortfolioDecision, PortfolioRating, SimulationCandidate
from tradingagents.course.audit import AuditError, AuditStore, replay_run
from tradingagents.course.pipeline import (
    GATE_ID,
    RULE_CATALOG,
    V1_RULE_VERSION,
    CourseAuditError,
    CourseCheckpointUnsupported,
    CourseConflictError,
    CourseRequest,
    CourseRequestError,
    gate_registry,
    run_course,
)
from tradingagents.graph.trading_graph import TradingAgentsGraph

DOMAINS = ("news", "social", "macro", "price", "fundamentals")


def _observations(domains=DOMAINS):
    return [
        {
            "domain": domain,
            "kind": "value",
            "source": "fixture",
            "observed_as_of": "2026-11-17",
            "value": 1,
            "value_present": True,
        }
        for domain in domains
    ]


def _request_data(tmp_path, **overrides):
    data = {
        "run_id": "run-1",
        "timestamp": "2026-11-17T15:00:00+08:00",
        "analysis_cutoff": "2026-11-17",
        "observations": _observations(),
        "holdings_snapshot": {
            "snapshot_id": "acct-1-20261117",
            "as_of": "2026-11-17",
            "currency": "USD",
            "cash": "10000.00",
            "positions": {"NVDA": "10"},
            "flat_declared": False,
        },
        "instrument": "NVDA",
        "instrument_currency": "USD",
        "rule_version": V1_RULE_VERSION,
        "audit_path": str(tmp_path / "audit.sqlite"),
    }
    data.update(overrides)
    return data


def _candidate(**overrides):
    candidate = {"action": "buy", "units": "5", "price": "100", "currency": "USD"}
    candidate.update(overrides)
    return candidate


def _ai(candidate, calls):
    def invoke(course_context):
        calls.append(course_context)
        return {
            "final_trade_decision": "**Rating**: Buy\n\nignored prose",
            "final_rating": "Buy",
            "simulation_proposal": candidate,
        }

    return invoke


def _ai_without_candidate(calls):
    def invoke(course_context):
        calls.append(course_context)
        return {"final_trade_decision": "**Rating**: Buy", "final_rating": "Buy"}

    return invoke


def _open_store(data):
    return AuditStore.open(data["audit_path"])


def test_d_blocked_before_model_and_audited(tmp_path):
    data = _request_data(tmp_path, observations=_observations(("news", "social", "macro", "price")))
    calls = []

    result = run_course(CourseRequest.from_mapping(data), _ai(_candidate(), calls))

    assert calls == []
    assert result.outcome == "review"
    assert result.signal == "REVIEW"
    assert result.published is False
    with _open_store(data) as store:
        record = store.get("cde:run-1")
        assert record is not None
        assert record.entry_type == "rejection"
        assert record.payload["observed"]["data_quality"]["decision"] == "review"
        assert record.payload["observed"]["safety"] is None
        replay = replay_run(store, "run-1", gate_registry())
        assert replay.status == "pass"


def test_accepted_buy_publishes_and_replays(tmp_path):
    data = _request_data(tmp_path)
    calls = []

    result = run_course(CourseRequest.from_mapping(data), _ai(_candidate(), calls))

    assert len(calls) == 1
    assert result.outcome == "accepted"
    assert result.published is True
    assert result.signal == "Buy"
    assert result.proposal == {
        "action": "buy",
        "units": "5",
        "price": "100",
        "currency": "USD",
        "holdings_snapshot": "acct-1-20261117",
        "rule_version": V1_RULE_VERSION,
    }
    with _open_store(data) as store:
        record = store.get("cde:run-1")
        assert record.entry_type == "decision"
        assert record.rules_version == V1_RULE_VERSION
        assert record.payload["gate_id"] == GATE_ID
        assert record.payload["observed"]["published"] is True
        # Stored payload is canonical-JSON safe (no Decimal/tuple).
        json.dumps(record.payload)
        replay = replay_run(store, "run-1", gate_registry())
        assert replay.status == "pass"
        assert replay.gate_total == 1


def test_insufficient_cash_rejects_and_signal_is_review(tmp_path):
    data = _request_data(tmp_path)
    calls = []

    result = run_course(
        CourseRequest.from_mapping(data),
        _ai(_candidate(units="200", price="100"), calls),
    )

    assert result.outcome == "rejected"
    assert result.published is False
    assert result.signal == "REVIEW"
    assert result.safety["reason_code"] == "insufficient_cash"
    with _open_store(data) as store:
        record = store.get("cde:run-1")
        assert record.entry_type == "rejection"
        with pytest.raises(AuditError) as raised:
            store.final_decision("run-1")
        assert raised.value.code == "invariant_violation"


def test_hold_is_legal_noop(tmp_path):
    data = _request_data(tmp_path)
    calls = []

    result = run_course(
        CourseRequest.from_mapping(data),
        _ai(_candidate(action="hold", units="0", price="100"), calls),
    )

    assert result.outcome == "hold"
    assert result.published is False
    assert result.proposal is None
    assert result.signal == "Hold"
    assert result.safety["accepted"] is True
    assert result.safety["is_noop"] is True
    with _open_store(data) as store:
        assert store.get("cde:run-1").entry_type == "decision"


def test_missing_candidate_is_rejected_without_guessing_units(tmp_path):
    data = _request_data(tmp_path)
    calls = []

    result = run_course(CourseRequest.from_mapping(data), _ai_without_candidate(calls))

    assert len(calls) == 1
    assert result.outcome == "rejected"
    assert result.published is False
    assert result.signal == "REVIEW"
    assert result.safety["reason_code"] == "missing_action"
    with _open_store(data) as store:
        record = store.get("cde:run-1")
        assert record.payload["inputs"]["candidate"] is None


def test_request_without_snapshot_is_refused_before_model(tmp_path):
    data = _request_data(tmp_path)
    data.pop("holdings_snapshot")
    calls = []

    with pytest.raises(CourseRequestError):
        run_course(CourseRequest.from_mapping(data), _ai(_candidate(), calls))
    assert calls == []


def test_in_memory_audit_is_refused_before_model(tmp_path):
    data = _request_data(tmp_path, audit_path=":memory:")
    calls = []

    with pytest.raises(CourseRequestError):
        run_course(CourseRequest.from_mapping(data), _ai(_candidate(), calls))
    assert calls == []


def test_bad_snapshot_is_not_treated_as_flat(tmp_path):
    data = _request_data(tmp_path)
    data["holdings_snapshot"] = {
        "snapshot_id": "acct-empty",
        "as_of": "2026-11-17",
        "currency": "USD",
        "cash": "10000.00",
        "positions": {},
    }
    calls = []

    result = run_course(CourseRequest.from_mapping(data), _ai(_candidate(), calls))

    assert result.outcome == "rejected"
    assert result.published is False
    assert result.safety["reason_code"] == "undeclared_flat"


def test_missing_positions_is_rejected_even_when_flat_declared(tmp_path):
    data = _request_data(tmp_path)
    data["holdings_snapshot"] = {
        "snapshot_id": "acct-missing-positions",
        "as_of": "2026-11-17",
        "currency": "USD",
        "cash": "10000.00",
        "flat_declared": True,
    }

    result = run_course(CourseRequest.from_mapping(data), _ai(_candidate(), []))

    assert result.outcome == "rejected"
    assert result.published is False
    assert result.safety["reason_code"] == "unresolved_holdings_snapshot"


def test_explicit_empty_positions_with_flat_declared_is_accepted(tmp_path):
    data = _request_data(tmp_path)
    data["holdings_snapshot"] = {
        "snapshot_id": "acct-empty-declared",
        "as_of": "2026-11-17",
        "currency": "USD",
        "cash": "10000.00",
        "positions": {},
        "flat_declared": True,
    }

    result = run_course(CourseRequest.from_mapping(data), _ai(_candidate(), []))

    assert result.outcome == "accepted"
    assert result.published is True


@pytest.mark.parametrize("extra", [{"execution_mode": "live"}, {"real_execution": True}])
def test_candidate_real_execution_intent_is_not_dropped(tmp_path, extra):
    data = _request_data(tmp_path)

    result = run_course(
        CourseRequest.from_mapping(data), _ai(_candidate(**extra), [])
    )

    assert result.outcome == "rejected"
    assert result.published is False
    assert result.signal == "REVIEW"
    assert result.safety["reason_code"] == "real_execution_requested"
    key, value = next(iter(extra.items()))
    with _open_store(data) as store:
        record = store.get("cde:run-1")
        assert record.payload["inputs"]["candidate"][key] == value


def test_invalid_timestamp_is_rejected_before_model(tmp_path):
    data = _request_data(tmp_path, timestamp="not-a-timestamp")
    calls = []

    with pytest.raises(CourseRequestError):
        run_course(CourseRequest.from_mapping(data), _ai(_candidate(), calls))
    assert calls == []


def test_rule_catalog_is_immutable():
    with pytest.raises(TypeError):
        RULE_CATALOG[V1_RULE_VERSION] = object()


def test_callback_mutation_does_not_change_the_frozen_snapshot(tmp_path):
    data = _request_data(tmp_path)
    data["holdings_snapshot"]["cash"] = "1000"
    request = CourseRequest.from_mapping(data)
    calls = []

    def invoke(course_context):
        calls.append(course_context)
        request.holdings_snapshot["cash"] = "999999"
        return {
            "final_trade_decision": "**Rating**: Buy",
            "final_rating": "Buy",
            "simulation_proposal": _candidate(units="200", price="10"),
        }

    result = run_course(request, invoke)

    assert len(calls) == 1
    assert result.outcome == "rejected"
    assert result.published is False
    assert result.safety["reason_code"] == "insufficient_cash"
    with _open_store(data) as store:
        replay = replay_run(store, "run-1", gate_registry())
        assert replay.status == "pass"


def test_unknown_rule_version_rejected_and_replay_reviews(tmp_path):
    data = _request_data(tmp_path, rule_version="cde-long-only-v2")
    calls = []

    result = run_course(CourseRequest.from_mapping(data), _ai(_candidate(), calls))

    assert result.outcome == "rejected"
    assert result.published is False
    assert result.safety["reason_code"] == "unknown_rule_version"
    with _open_store(data) as store:
        replay = replay_run(store, "run-1", gate_registry())
        assert replay.status == "review"
        assert replay.results[0].reason == "version_unknown"


def test_audit_write_failure_does_not_publish(tmp_path):
    data = _request_data(tmp_path, audit_path=str(tmp_path))
    calls = []

    with pytest.raises(CourseAuditError):
        run_course(CourseRequest.from_mapping(data), _ai(_candidate(), calls))
    assert len(calls) == 1


def test_duplicate_run_is_idempotent_then_conflicts(tmp_path):
    data = _request_data(tmp_path)
    request = CourseRequest.from_mapping(data)
    calls = []

    first = run_course(request, _ai(_candidate(), calls))
    second = run_course(request, _ai(_candidate(), calls))
    assert first.to_dict() == second.to_dict()
    with _open_store(data) as store:
        assert len(store.iter_run("run-1")) == 1

    with pytest.raises(CourseConflictError):
        run_course(request, _ai(_candidate(units="6"), calls))
    with _open_store(data) as store:
        assert len(store.iter_run("run-1")) == 1


def test_replay_rejects_tampered_observed(tmp_path):
    data = _request_data(tmp_path)
    run_course(CourseRequest.from_mapping(data), _ai(_candidate(), []))

    with _open_store(data) as store:
        payload = store.get("cde:run-1").payload
    payload["observed"]["outcome"] = "rejected"
    payload["observed"]["safety"]["accepted"] = False
    payload["observed"]["published"] = False

    tampered_path = tmp_path / "tampered.sqlite"
    with AuditStore.open(str(tampered_path)) as store:
        store.append(
            record_id="cde:run-1",
            run_id="run-1",
            timestamp=data["timestamp"],
            entry_type="decision",
            payload=payload,
            rules_version=V1_RULE_VERSION,
        )
        replay = replay_run(store, "run-1", gate_registry())
        assert replay.status == "review"
        assert replay.results[0].reason == "observed_mismatch"


def test_replay_rejects_wrong_rules_version(tmp_path):
    data = _request_data(tmp_path)
    run_course(CourseRequest.from_mapping(data), _ai(_candidate(), []))

    with _open_store(data) as store:
        payload = store.get("cde:run-1").payload
    payload["rules_version"] = "cde-long-only-v9"

    wrong_path = tmp_path / "wrong-version.sqlite"
    with AuditStore.open(str(wrong_path)) as store:
        store.append(
            record_id="cde:run-1",
            run_id="run-1",
            timestamp=data["timestamp"],
            entry_type="decision",
            payload=payload,
            rules_version="cde-long-only-v9",
        )
        replay = replay_run(store, "run-1", gate_registry())
        assert replay.status == "review"
        assert replay.results[0].reason == "version_unknown"


def _graph_stub(candidate, calls, *, checkpoint_enabled=False, record_flags=None):
    graph = TradingAgentsGraph.__new__(TradingAgentsGraph)
    graph.config = {"checkpoint_enabled": checkpoint_enabled}

    def fake_run(company_name, trade_date, asset_type="stock", portfolio=None,
                 course_context=None, record=True):
        calls.append(course_context)
        if record_flags is not None:
            record_flags.append(record)
        return (
            {
                "company_of_interest": company_name,
                "trade_date": trade_date,
                "final_trade_decision": "**Rating**: Buy\n\nignored prose",
                "final_rating": "Buy",
                "simulation_proposal": candidate,
            },
            "Buy",
        )

    graph._run_graph = fake_run
    return graph


def test_propagate_course_request_entrypoint(tmp_path):
    data = _request_data(tmp_path)
    calls = []
    record_flags = []
    graph = _graph_stub(_candidate(), calls, record_flags=record_flags)

    final_state, signal = graph.propagate(
        "NVDA", "2026-11-17", course_request=CourseRequest.from_mapping(data)
    )

    assert len(calls) == 1
    assert "NVDA" in calls[0]
    assert record_flags == [False]
    assert signal == "Buy"
    assert final_state["simulation_proposal"]["action"] == "buy"
    assert final_state["course_result"]["published"] is True
    with _open_store(data) as store:
        assert store.get("cde:run-1").entry_type == "decision"


def test_propagate_course_rejects_checkpoint(tmp_path):
    data = _request_data(tmp_path)
    calls = []
    graph = _graph_stub(_candidate(), calls, checkpoint_enabled=True)

    with pytest.raises(CourseCheckpointUnsupported):
        graph.propagate("NVDA", "2026-11-17", course_request=CourseRequest.from_mapping(data))
    assert calls == []


def test_propagate_rejects_mismatched_instrument_before_model(tmp_path):
    data = _request_data(tmp_path, instrument="AAPL")
    calls = []
    graph = _graph_stub(_candidate(), calls)

    with pytest.raises(CourseRequestError):
        graph.propagate("NVDA", "2026-11-17", course_request=CourseRequest.from_mapping(data))
    assert calls == []


def test_propagate_rejects_mismatched_cutoff_before_model(tmp_path):
    data = _request_data(tmp_path, analysis_cutoff="2026-11-16")
    calls = []
    graph = _graph_stub(_candidate(), calls)

    with pytest.raises(CourseRequestError):
        graph.propagate("NVDA", "2026-11-17", course_request=CourseRequest.from_mapping(data))
    assert calls == []


def _pm_state(course_context=None):
    state = {
        "company_of_interest": "NVDA",
        "asset_type": "stock",
        "instrument_context": "The instrument to analyze is `NVDA`.",
        "portfolio_context": "Portfolio context: not provided.",
        "investment_plan": "plan",
        "trader_investment_plan": "trader plan",
        "risk_debate_state": {
            "history": "debate",
            "aggressive_history": "a",
            "conservative_history": "c",
            "neutral_history": "n",
            "latest_speaker": "",
            "current_aggressive_response": "",
            "current_conservative_response": "",
            "current_neutral_response": "",
            "count": 1,
        },
    }
    if course_context is not None:
        state["course_context"] = course_context
    return state


class _FakeStructured:
    def __init__(self, course_mode):
        self.course_mode = course_mode
        self.prompts = []

    def invoke(self, prompt):
        self.prompts.append(prompt)
        if self.course_mode:
            return PortfolioDecision(
                rating=PortfolioRating.BUY,
                executive_summary="summary",
                investment_thesis="thesis",
                simulation_proposal=SimulationCandidate(
                    action="buy", units="5", price="100", currency="USD"
                ),
            )
        return PortfolioDecision(
            rating=PortfolioRating.BUY,
            executive_summary="summary",
            investment_thesis="thesis",
        )


class _FakeLLM:
    def __init__(self, course_mode):
        self.structured = _FakeStructured(course_mode)

    def with_structured_output(self, schema):
        return self.structured

    def invoke(self, prompt):
        class _Message:
            content = "**Rating**: Buy"

        return _Message()


def test_pm_only_returns_simulation_proposal_in_course_mode():
    normal_llm = _FakeLLM(course_mode=False)
    normal = pm_module.create_portfolio_manager(normal_llm)
    normal_result = normal(_pm_state())
    assert "simulation_proposal" not in normal_result
    assert "Course simulation mode" not in normal_llm.structured.prompts[0]

    course_llm = _FakeLLM(course_mode=True)
    course = pm_module.create_portfolio_manager(course_llm)
    course_result = course(_pm_state(course_context="Course simulation mode"))
    assert course_result["simulation_proposal"] == {
        "action": "buy",
        "units": "5",
        "price": "100",
        "currency": "USD",
    }
    assert "Course simulation mode" in course_llm.structured.prompts[0]


def test_pm_candidate_schema_rejects_real_execution_extras():
    with pytest.raises(ValidationError):
        SimulationCandidate(
            action="buy", units="5", price="100", currency="USD", execution_mode="live"
        )



def test_cli_course_route_uses_propagate(tmp_path, monkeypatch):
    data = _request_data(tmp_path)
    input_path = tmp_path / "course-input.json"
    input_path.write_text(json.dumps(data), encoding="utf-8")
    captured = {}

    class FakeGraph:
        def __init__(self, selected_analysts=(), debug=False, config=None, callbacks=None):
            captured["selected_analysts"] = selected_analysts
            captured["config"] = config

        def propagate(self, company_name, trade_date, asset_type="stock", portfolio=None,
                      course_request=None):
            captured["company"] = company_name
            captured["date"] = trade_date
            captured["asset_type"] = asset_type
            captured["course_request"] = course_request
            return (
                {"final_rating": "Buy", "final_trade_decision": "**Rating**: Buy"},
                "Buy",
            )

    monkeypatch.setattr("cli.main.TradingAgentsGraph", FakeGraph)
    monkeypatch.setattr("cli.main.run_analysis", lambda **kwargs: pytest.fail("course path must not call run_analysis"))

    result = CliRunner().invoke(
        app,
        [
            "--ticker", "NVDA",
            "--date", "2026-11-17",
            "--course-inputs", str(input_path),
            "--no-save",
            "--no-show",
        ],
    )

    assert result.exit_code == 0, result.output
    assert captured["company"] == "NVDA"
    assert captured["date"] == "2026-11-17"
    assert captured["asset_type"] == "stock"
    assert isinstance(captured["course_request"], CourseRequest)
    assert captured["course_request"].run_id == "run-1"


def test_cli_rejects_mismatched_ticker(tmp_path, monkeypatch):
    data = _request_data(tmp_path)
    input_path = tmp_path / "course-input.json"
    input_path.write_text(json.dumps(data), encoding="utf-8")
    called = []
    monkeypatch.setattr("cli.main.TradingAgentsGraph", lambda *a, **k: called.append(1))

    result = CliRunner().invoke(
        app,
        ["--ticker", "AAPL", "--date", "2026-11-17", "--course-inputs", str(input_path)],
    )

    assert result.exit_code == 1
    assert called == []


def test_cli_rejects_mismatched_date(tmp_path, monkeypatch):
    data = _request_data(tmp_path)
    input_path = tmp_path / "course-input.json"
    input_path.write_text(json.dumps(data), encoding="utf-8")
    called = []
    monkeypatch.setattr("cli.main.TradingAgentsGraph", lambda *a, **k: called.append(1))

    result = CliRunner().invoke(
        app,
        ["--ticker", "NVDA", "--date", "2026-11-16", "--course-inputs", str(input_path)],
    )

    assert result.exit_code == 1
    assert called == []


def test_cli_normal_path_does_not_pass_course_kwarg(monkeypatch):
    captured = {}

    def fake_run_analysis(checkpoint=None, portfolio=None, flags=None):
        captured.update({"checkpoint": checkpoint, "portfolio": portfolio, "flags": flags})

    monkeypatch.setattr("cli.main.run_analysis", fake_run_analysis)
    result = CliRunner().invoke(
        app,
        ["--ticker", "NVDA", "--date", "2026-11-17", "--no-save", "--no-show"],
    )

    assert result.exit_code == 0, result.output
    assert captured["flags"]["ticker"] == "NVDA"
    assert "course_request" not in captured

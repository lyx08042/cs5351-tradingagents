"""Offline, deterministic tests for the role A evidence leaf (FR-001 / INV-001 / ADR-005).

No network, no real LLM, no live services. Covers the fixed EVAL-006/008/009
cases, plan cases A01–A09, the Codex-review regressions (missing/padded dates,
future-leakage precedence, quarantine replay), strict JSON typing, and static AST
checks over the production source read from disk.
"""
from __future__ import annotations

import ast
import importlib
import json
import math
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

EV = importlib.import_module("tradingagents.course.evidence")

EVIDENCE_DIR = REPO_ROOT / "tradingagents" / "course" / "evidence"
COURSE_MARKER = REPO_ROOT / "tradingagents" / "course" / "__init__.py"
LEAF_NAMES = {"budget", "safety", "data_quality", "audit"}
FORBIDDEN_IMPORTS = {"time", "random", "secrets", "uuid"}
FORBIDDEN_CALLS = {
    "now",
    "utcnow",
    "today",
    "time",
    "monotonic",
    "perf_counter",
    "urandom",
    "uuid4",
    "randint",
    "randrange",
    "getrandbits",
    "choice",
    "shuffle",
}
STDLIB = set(sys.stdlib_module_names)
AS_OF = "2026-09-01"
POLICY = EV.FreshnessPolicy(name="default", max_age_days=2)

pytestmark = pytest.mark.unit


def macd_fact(**overrides):
    record = {
        "subject": "NVDA",
        "metric": "macd_cross",
        "value": None,
        "relation": "golden_cross",
        "unit": None,
        "period": "2026-08-30",
    }
    record.update(overrides)
    return EV.Fact.from_record(record)


def close_fact(value):
    return EV.Fact.from_record(
        {
            "subject": "NVDA",
            "metric": "close",
            "value": value,
            "relation": None,
            "unit": "usd",
            "period": "2026-08-30",
        }
    )


def unit(
    evidence_id="ev-1",
    *,
    run_id="run-a",
    status="available",
    published_at="2026-08-30",
    available_as_of="2026-08-30",
    fact=None,
    freshness_policy="default",
    source="tool",
    content_ref=None,
):
    return {
        "evidence_id": evidence_id,
        "run_id": run_id,
        "source": source,
        "content_ref": content_ref or f"snapshot:NVDA:{evidence_id}",
        "status": status,
        "published_at": published_at,
        "available_as_of": available_as_of,
        "fact": (macd_fact() if fact is None else fact).to_dict(),
        "freshness_policy": freshness_policy,
    }


def registry(units, *, run_id="run-a", as_of=AS_OF):
    return EV.EvidenceRegistry.build(run_id=run_id, as_of=as_of, candidates=units)


def claim(refs, *, fact=None, text="", classification="factual", claim_id="c1"):
    record = {
        "claim_id": claim_id,
        "text": text,
        "classification": classification,
        "evidence_refs": list(refs),
    }
    if fact is not None:
        record["fact"] = fact.to_dict()
    return EV.Claim.from_record(record)


def json_roundtrip(value):
    return json.loads(json.dumps(value, allow_nan=False))


def assert_strict_json(value):
    kind = type(value)
    if value is None or kind is bool or kind is str or kind is int:
        return
    if kind is float:
        assert math.isfinite(value)
        return
    if kind is list:
        for item in value:
            assert_strict_json(item)
        return
    if kind is dict:
        for key, item in value.items():
            assert type(key) is str
            assert_strict_json(item)
        return
    raise AssertionError(f"non-plain JSON type: {kind!r}")


def production_files():
    return sorted(EVIDENCE_DIR.rglob("*.py"))


def parse_production(path):
    source = path.read_text(encoding="utf-8")
    return source, ast.parse(source, filename=str(path), feature_version=(3, 11))


def iter_imports(tree):
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name, 0, ()
        elif isinstance(node, ast.ImportFrom):
            yield node.module or "", node.level, tuple(alias.name for alias in node.names)


def test_a01_eval008_accepts_historical_fact_and_resolves_reference():
    reg = registry([unit()])
    verdict = EV.verify_claim(
        claim(["ev-1"], fact=macd_fact(), text="MACD golden cross"),
        registry=reg,
        policy=POLICY,
    )
    assert verdict.verdict == "accept_factual"
    assert verdict.reasons == (EV.EVIDENCE_SUPPORTS_FACTUAL_CLAIM,)
    assert verdict.evidence_refs == ("ev-1",)
    assert verdict.projection == (macd_fact(),)
    admitted = reg.admissibility("ev-1", POLICY)
    assert admitted.status == EV.ACCEPT
    assert admitted.unit is not None
    assert admitted.unit.content_ref == "snapshot:NVDA:ev-1"


def test_projection_emits_fresh_json_and_cannot_be_mutated():
    reg = registry([unit("ev-close", fact=close_fact(150.0))])
    verdict = EV.verify_claim(
        claim(["ev-close"], fact=close_fact(150.0)), registry=reg, policy=POLICY
    )
    assert verdict.verdict == "accept_factual"
    assert all(isinstance(item, EV.Fact) for item in verdict.projection)
    expected = close_fact(150.0).to_dict()
    first = verdict.to_dict()
    assert first["projection"] == [expected]
    first["projection"][0]["metric"] = "tampered"
    first["projection"][0]["value"]["value"] = 999
    first["projection"][0]["value"]["kind"] = "int"
    second = verdict.to_dict()
    assert second["projection"] == [expected]
    assert second["projection"] is not first["projection"]
    assert second["projection"][0] is not first["projection"][0]
    assert second["projection"][0]["value"] is not first["projection"][0]["value"]
    assert_strict_json(second)


def test_a03_eval006_predictions_are_hypotheses_with_and_without_reference():
    reg = registry([unit()])
    bare = EV.verify_claim(
        claim([], text="MACD 金叉，股价必涨", classification=None, claim_id="e6-bare"),
        registry=reg,
        policy=POLICY,
    )
    assert bare.verdict == "hypothesis"
    assert bare.reasons == (EV.FORECAST_REQUIRES_HYPOTHESIS_LABEL,)
    assert bare.evidence_refs == ()
    supported = EV.verify_claim(
        claim(["ev-1"], fact=macd_fact(), text="MACD 金叉，股价必涨", claim_id="e6-supported"),
        registry=reg,
        policy=POLICY,
    )
    assert supported.verdict == "hypothesis"
    assert supported.reasons == (EV.FORECAST_REQUIRES_HYPOTHESIS_LABEL,)
    assert supported.evidence_refs == ()


def test_a05_eval009_future_available_without_published_still_leaks():
    reg = registry([unit("ev-future", published_at=None, available_as_of="2026-09-05")])
    admitted = reg.admissibility("ev-future", POLICY)
    assert admitted.status == EV.REJECT
    assert admitted.reasons == (EV.FUTURE_LEAKAGE,)
    verdict = EV.verify_claim(claim(["ev-future"], fact=macd_fact()), registry=reg, policy=POLICY)
    assert verdict.verdict == "abstain"
    assert EV.FUTURE_LEAKAGE in verdict.reasons


def test_a02_age_boundary_and_same_day_are_inclusive():
    reg = registry(
        [
            unit("ev-same", published_at=AS_OF, available_as_of=AS_OF),
            unit("ev-edge", published_at="2026-08-30", available_as_of="2026-08-30"),
        ]
    )
    two_day = EV.FreshnessPolicy("default", 2)
    one_day = EV.FreshnessPolicy("default", 1)
    assert reg.admissibility("ev-same", two_day).status == EV.ACCEPT
    assert reg.admissibility("ev-same", one_day).status == EV.ACCEPT
    assert reg.admissibility("ev-edge", two_day).status == EV.ACCEPT
    stale = reg.admissibility("ev-edge", one_day)
    assert stale.status == EV.REJECT
    assert stale.reasons == (EV.STALE,)


def test_a05_future_on_either_date_is_future_leakage():
    reg = registry(
        [
            unit("ev-pub", published_at="2026-09-05", available_as_of="2026-08-30"),
            unit("ev-av", published_at="2026-08-30", available_as_of="2026-09-05"),
        ]
    )
    assert reg.admissibility("ev-pub", POLICY).reasons == (EV.FUTURE_LEAKAGE,)
    assert reg.admissibility("ev-av", POLICY).reasons == (EV.FUTURE_LEAKAGE,)
    for evidence_id in ("ev-pub", "ev-av"):
        verdict = EV.verify_claim(claim([evidence_id], fact=macd_fact()), registry=reg, policy=POLICY)
        assert verdict.verdict == "abstain"
        assert EV.FUTURE_LEAKAGE in verdict.reasons


def test_a06_absent_dates_reject_per_axis_even_when_other_date_is_legal():
    cases = {
        "ev-mp": unit("ev-mp", published_at=None, available_as_of="2026-08-30"),
        "ev-ma": unit("ev-ma", published_at="2026-08-30", available_as_of=None),
        "ev-both": unit("ev-both", published_at=None, available_as_of=None),
    }
    reg = registry(list(cases.values()))
    for evidence_id in cases:
        assert reg.admissibility(evidence_id, POLICY).reasons == (EV.MISSING_DATE,)


def test_a06_padded_dates_and_cutoff_reject():
    reg = registry([unit("ev-pad", published_at=" 2026-08-30", available_as_of="2026-08-30")])
    assert reg.admissibility("ev-pad", POLICY).reasons == (EV.INVALID_DATE,)
    with pytest.raises(ValueError) as info:
        EV.EvidenceRegistry.build(run_id="run-a", as_of=" 2026-09-01", candidates=[unit()])
    assert str(info.value) == EV.INVALID_AS_OF


def test_a06_status_and_policy_fail_closed():
    reg = registry(
        [
            unit("ev-un", status="unavailable"),
            unit("ev-uk", status="unknown"),
            unit("ev-policy", freshness_policy="other"),
        ]
    )
    assert reg.admissibility("ev-un", POLICY).reasons == (EV.UNAVAILABLE_STATUS,)
    assert reg.admissibility("ev-uk", POLICY).reasons == (EV.UNKNOWN_STATUS,)
    assert reg.admissibility("ev-policy", POLICY).reasons == (EV.POLICY_MISMATCH,)
    assert registry([unit("ev-neutral", status="neutral")]).admissibility(
        "ev-neutral", POLICY
    ).reasons == (EV.NEUTRAL_STATUS,)
    assert registry([unit("ev-bad", status="neutral-ish")]).admissibility(
        "ev-bad", POLICY
    ).reasons == (EV.INVALID_STATUS,)
    assert registry([unit("ev-bad-date", published_at="2026-13-40")]).admissibility(
        "ev-bad-date", POLICY
    ).reasons == (EV.INVALID_DATE,)
    assert registry([unit("ev-old", published_at="2026-07-01", available_as_of="2026-07-01")]).admissibility(
        "ev-old", POLICY
    ).reasons == (EV.STALE,)
    assert registry([unit()]).admissibility(
        "ev-1", EV.FreshnessPolicy("default", -1)
    ).reasons == (EV.INVALID_POLICY,)
    assert registry([unit()]).admissibility(
        "ev-1", EV.FreshnessPolicy(42, 2)
    ).reasons == (EV.INVALID_POLICY,)


def test_a07_mismatch_across_every_fact_dimension_is_unrelated():
    reg = registry([unit("ev-1", fact=macd_fact())])
    mismatches = {
        "subject": macd_fact(subject="MSFT"),
        "metric": macd_fact(metric="macd"),
        "relation": macd_fact(relation="death_cross"),
        "unit": macd_fact(unit="usd"),
        "period": macd_fact(period="2026-08-29"),
    }
    for label, fact in mismatches.items():
        verdict = EV.verify_claim(claim(["ev-1"], fact=fact, claim_id=label), registry=reg, policy=POLICY)
        assert verdict.verdict == "abstain", label
        assert EV.UNRELATED in verdict.reasons, label
    value_reg = registry([unit("ev-close", fact=close_fact(150.0))])
    assert EV.verify_claim(
        claim(["ev-close"], fact=close_fact(151.0)), registry=value_reg, policy=POLICY
    ).verdict == "abstain"
    relation_claim = EV.Fact.from_record(
        {"subject": "NVDA", "metric": "close", "value": None, "relation": "up", "unit": "usd", "period": "2026-08-30"}
    )
    assert EV.verify_claim(
        claim(["ev-close"], fact=relation_claim), registry=value_reg, policy=POLICY
    ).verdict == "abstain"


def test_a04_absent_foreign_and_fake_references_never_accept():
    reg = registry([unit()])
    empty = EV.verify_claim(claim([], fact=macd_fact()), registry=reg, policy=POLICY)
    assert empty.verdict == "abstain" and EV.NO_REFERENCE in empty.reasons
    blank = EV.verify_claim(claim([""], fact=macd_fact()), registry=reg, policy=POLICY)
    assert blank.verdict == "abstain" and EV.UNTRUSTED in blank.reasons
    missing = EV.verify_claim(claim(["ev-missing"], fact=macd_fact()), registry=reg, policy=POLICY)
    assert missing.verdict == "abstain" and EV.UNKNOWN_REFERENCE in missing.reasons
    foreign_reg = registry([unit(), unit("ev-foreign", run_id="run-b")])
    foreign = EV.verify_claim(
        claim(["ev-foreign"], fact=macd_fact()), registry=foreign_reg, policy=POLICY
    )
    assert foreign.verdict == "abstain" and EV.FOREIGN_REFERENCE in foreign.reasons
    fake_index = {
        "claim_id": "fake",
        "text": "MACD golden cross",
        "classification": "factual",
        "fact": macd_fact().to_dict(),
        "evidence_refs": ["ev-1"],
        "evidence": {"evidence_id": "ev-1", "status": "available"},
    }
    inline = EV.verify_claim(fake_index, registry=reg, policy=POLICY)
    assert inline.verdict == "abstain"
    fake_registry = EV.verify_claim(
        claim(["ev-1"], fact=macd_fact()), registry={"ev-1": {}}, policy=POLICY
    )
    assert fake_registry.verdict == "abstain" and EV.MALFORMED in fake_registry.reasons
    for verdict in (empty, blank, missing, foreign, inline, fake_registry):
        assert verdict.evidence_refs == ()


def test_a03_mixed_and_free_text_never_accept():
    reg = registry([unit()])
    mixed = EV.verify_claim(
        claim(["ev-1"], fact=macd_fact(), text="MACD 金叉，股价必涨", claim_id="mixed"),
        registry=reg,
        policy=POLICY,
    )
    assert mixed.verdict == "hypothesis"
    free = EV.verify_claim(
        claim(["ev-1"], fact=None, text="The RSI is overbought", classification=None, claim_id="free"),
        registry=reg,
        policy=POLICY,
    )
    assert free.verdict == "abstain"
    assert free.reasons == (EV.UNCLASSIFIED,)
    undeclared = EV.verify_claim(
        claim(["ev-1"], fact=None, text="MACD golden cross", classification=None, claim_id="prose"),
        registry=reg,
        policy=POLICY,
    )
    assert undeclared.verdict == "abstain"
    declared = EV.verify_claim(
        claim(["ev-1"], fact=None, text="MACD golden cross", classification="factual", claim_id="declared"),
        registry=reg,
        policy=POLICY,
    )
    assert declared.verdict == "abstain"


def test_forecast_language_in_english_and_chinese_overrides_facts():
    reg = registry([unit()])
    for text in (
        "The price will rise",
        "价格将上涨",
        "股价必涨",
        "It is likely to surge",
        "The stock rises tomorrow",
        "股价明天涨",
        "股价将涨",
    ):
        assert EV.verify_claim(
            claim(["ev-1"], fact=macd_fact(), text=text, claim_id="f"),
            registry=reg,
            policy=POLICY,
        ).verdict == "hypothesis", text
    for text in ("MACD golden cross", "MACD 金叉"):
        assert EV.verify_claim(
            claim(["ev-1"], fact=macd_fact(), text=text, classification=None, claim_id="f2"),
            registry=reg,
            policy=POLICY,
        ).verdict == "accept_factual", text


def test_historical_directional_verbs_are_not_forecasts():
    reg = registry([unit("ev-close", fact=close_fact(150.0))])
    for text in (
        "NVDA surged to 150 USD on 2026-08-30",
        "On May 30, NVDA surged to 150 USD",
        "NVDA plunged yesterday",
        "NVDA rallied on 2026-08-30",
        "NVDA tumbled last week",
        "NVDA rebounded on 2026-08-30",
    ):
        verdict = EV.verify_claim(
            claim(["ev-close"], fact=close_fact(150.0), text=text, claim_id="hist"),
            registry=reg,
            policy=POLICY,
        )
        assert verdict.verdict == "accept_factual", text


def test_modal_and_phrasal_forecasts_are_hypotheses():
    reg = registry([unit("ev-close", fact=close_fact(150.0))])
    for text in (
        "The price will surge",
        "The stock may surge",
        "It might tumble",
        "Shares could rebound",
        "The stock is going to rally",
        "The stock is likely to surge",
        "The stock is expected to rally",
        "Prices are set to plunge",
        "The stock will rise",
        "The stock may fall",
        "The stock could climb",
        "The stock might drop",
        "NVDA is going to exceed 150 USD",
    ):
        verdict = EV.verify_claim(
            claim(["ev-close"], fact=close_fact(150.0), text=text, claim_id="forecast"),
            registry=reg,
            policy=POLICY,
        )
        assert verdict.verdict == "hypothesis", text


def test_mandarin_forecast_markers_are_hypotheses():
    reg = registry([unit("ev-close", fact=close_fact(150.0))])
    for text in ("目标价200美元", "即将上涨", "大概率上涨", "可能上涨", "可能下跌", "涨停", "跌停"):
        verdict = EV.verify_claim(
            claim(["ev-close"], fact=close_fact(150.0), text=text, claim_id="zh-forecast"),
            registry=reg,
            policy=POLICY,
        )
        assert verdict.verdict == "hypothesis", text


def test_factual_declaration_without_fact_distinguishes_outcomes():
    reg = registry([unit()])
    declared = EV.verify_claim(
        claim(["ev-1"], fact=None, text="MACD golden cross", classification="factual", claim_id="declared"),
        registry=reg,
        policy=POLICY,
    )
    assert declared.verdict == "abstain"
    assert declared.reasons == (EV.NO_STRUCTURED_FACT,)
    assert declared.rejected_refs == ()
    undeclared = EV.verify_claim(
        claim(["ev-1"], fact=None, text="MACD golden cross", classification=None, claim_id="undeclared"),
        registry=reg,
        policy=POLICY,
    )
    assert undeclared.verdict == "abstain"
    assert undeclared.reasons == (EV.UNCLASSIFIED,)
    unknown = EV.verify_claim(
        claim(["ev-1"], fact=None, text="MACD golden cross", classification="unknown", claim_id="explicit-unknown"),
        registry=reg,
        policy=POLICY,
    )
    assert unknown.verdict == "abstain"
    assert unknown.reasons == (EV.UNCLASSIFIED,)
    forecast = EV.verify_claim(
        claim(["ev-1"], fact=None, text="股价必涨", classification="factual", claim_id="forecast"),
        registry=reg,
        policy=POLICY,
    )
    assert forecast.verdict == "hypothesis"
    assert forecast.reasons == (EV.FORECAST_REQUIRES_HYPOTHESIS_LABEL,)


def test_rejected_refs_audit_mixed_and_all_rejected():
    mixed_reg = registry([unit("ev-good"), unit("ev-future", available_as_of="2026-09-05")])
    mixed = EV.verify_claim(
        claim(["ev-future", "ev-good"], fact=macd_fact(), claim_id="mixed-audit"),
        registry=mixed_reg,
        policy=POLICY,
    )
    assert mixed.verdict == "accept_factual"
    assert mixed.reasons == (EV.EVIDENCE_SUPPORTS_FACTUAL_CLAIM,)
    assert mixed.evidence_refs == ("ev-good",)
    assert mixed.projection == (macd_fact(),)
    assert all(isinstance(item.reasons, tuple) for item in mixed.rejected_refs)
    assert [(item.evidence_id, item.reasons) for item in mixed.rejected_refs] == [
        ("ev-future", (EV.FUTURE_LEAKAGE,))
    ]
    first = mixed.to_dict()
    second = mixed.to_dict()
    assert first == second
    assert first["rejected_refs"] == [{"evidence_id": "ev-future", "reasons": ["future_leakage"]}]
    assert first["rejected_refs"] is not second["rejected_refs"]
    assert first["rejected_refs"][0] is not second["rejected_refs"][0]
    assert first["rejected_refs"][0]["reasons"] is not second["rejected_refs"][0]["reasons"]
    first["rejected_refs"][0]["reasons"].append("tampered")
    assert second["rejected_refs"][0]["reasons"] == ["future_leakage"]
    assert_strict_json(second)
    assert json_roundtrip(second) == second

    all_reg = registry(
        [
            unit("ev-good"),
            unit("ev-conflict", fact=macd_fact()),
            unit("ev-conflict", fact=macd_fact(relation="death_cross")),
            unit("ev-other", fact=close_fact(150.0)),
        ]
    )
    all_rejected = EV.verify_claim(
        claim(["ev-conflict", "ev-other", "ev-missing"], fact=macd_fact(), claim_id="all-rejected"),
        registry=all_reg,
        policy=POLICY,
    )
    assert all_rejected.verdict == "abstain"
    assert all_rejected.evidence_refs == ()
    assert all_rejected.projection == ()
    assert [(item.evidence_id, item.reasons) for item in all_rejected.rejected_refs] == [
        ("ev-conflict", (EV.CONFLICTING_ID,)),
        ("ev-other", (EV.UNRELATED,)),
        ("ev-missing", (EV.UNKNOWN_REFERENCE,)),
    ]
    assert set(all_rejected.reasons) == {EV.CONFLICTING_ID, EV.UNRELATED, EV.UNKNOWN_REFERENCE}
    payload = all_rejected.to_dict()
    assert payload["rejected_refs"] == [
        {"evidence_id": "ev-conflict", "reasons": ["conflicting_id"]},
        {"evidence_id": "ev-other", "reasons": ["unrelated"]},
        {"evidence_id": "ev-missing", "reasons": ["unknown_reference"]},
    ]
    assert_strict_json(payload)
    assert json_roundtrip(payload) == payload


def test_rejected_refs_keep_blank_and_invalid_entries():
    reg = registry([unit()])
    verdict = EV.verify_claim(
        claim(["", "n/a", "ev-missing"], fact=macd_fact(), claim_id="blank-audit"),
        registry=reg,
        policy=POLICY,
    )
    assert verdict.verdict == "abstain"
    assert [(item.evidence_id, item.reasons) for item in verdict.rejected_refs] == [
        ("", (EV.UNTRUSTED,)),
        ("n/a", (EV.UNTRUSTED,)),
        ("ev-missing", (EV.UNKNOWN_REFERENCE,)),
    ]
    payload = verdict.to_dict()
    assert payload["rejected_refs"][0] == {"evidence_id": "", "reasons": ["untrusted"]}
    assert_strict_json(payload)
    assert json_roundtrip(payload) == payload


def test_claim_verdict_validates_rejected_refs_container():
    with pytest.raises(ValueError):
        EV.ClaimVerdict("c", "abstain", ("x",), (), (), ({"evidence_id": "ev-1"},))


def test_a08_conflicting_ids_and_illegal_structure():
    conflicting = registry(
        [unit("ev-dup", fact=macd_fact()), unit("ev-dup", fact=macd_fact(relation="death_cross"))]
    )
    assert conflicting.admissibility("ev-dup", POLICY).reasons == (EV.CONFLICTING_ID,)
    verdict = EV.verify_claim(claim(["ev-dup"], fact=macd_fact()), registry=conflicting, policy=POLICY)
    assert verdict.verdict == "abstain" and EV.CONFLICTING_ID in verdict.reasons
    illegal = {
        "claim_id": "illegal",
        "text": "MACD golden cross",
        "classification": "factual",
        "fact": macd_fact().to_dict(),
        "evidence_refs": "ev-1",
    }
    assert EV.verify_claim(illegal, registry=registry([unit()]), policy=POLICY).verdict == "abstain"


def test_registry_constructor_cannot_bypass_quarantine():
    with pytest.raises(TypeError):
        EV.EvidenceRegistry()
    with pytest.raises(TypeError):
        EV.EvidenceRegistry(run_id="run-a", as_of=AS_OF, units=())
    conflicting = registry(
        [unit("ev-dup", fact=macd_fact()), unit("ev-dup", fact=macd_fact(relation="death_cross"))]
    )
    assert conflicting.admissibility("ev-dup", POLICY).reasons == (EV.CONFLICTING_ID,)
    replayed = EV.EvidenceRegistry.from_dict(json_roundtrip(conflicting.to_dict()))
    assert replayed.admissibility("ev-dup", POLICY).reasons == (EV.CONFLICTING_ID,)


def test_result_constructors_reject_malformed_fields():
    with pytest.raises(ValueError):
        EV.ClaimVerdict(set(), "abstain", ("x",), (), ())
    with pytest.raises(ValueError):
        EV.ClaimVerdict("", "abstain", ("x",), (), ())
    with pytest.raises(ValueError):
        EV.ClaimVerdict("c", "not-a-verdict", ("x",), (), ())
    with pytest.raises(ValueError):
        EV.ClaimVerdict("c", "abstain", {"x"}, (), ())
    with pytest.raises(ValueError):
        EV.ClaimVerdict("c", "abstain", ("x",), (set(),), ())
    with pytest.raises(ValueError):
        EV.Admissibility(set(), ("x",), None)
    with pytest.raises(ValueError):
        EV.Admissibility(EV.REJECT, {"x"}, None)
    with pytest.raises(ValueError):
        EV.Admissibility(EV.REJECT, ("x",), "")
    with pytest.raises(ValueError):
        EV.Admissibility(EV.REJECT, ("x",), 5)
    assert EV.ClaimVerdict("c", "abstain", ("x",), (), ()).to_dict()["claim_id"] == "c"
    assert EV.Admissibility(EV.REJECT, ("x",), None).to_dict()["evidence_id"] is None
    assert EV.Admissibility(EV.REJECT, ("x",), "ev-1").to_dict()["evidence_id"] == "ev-1"


def test_a08_quarantine_survives_registry_json_replay():
    original = registry([unit("ev-1", fact=macd_fact()), unit("ev-1", status="neutral")])
    assert original.admissibility("ev-1", POLICY).reasons == (EV.CONFLICTING_ID,)
    replayed = EV.EvidenceRegistry.from_dict(json_roundtrip(original.to_dict()))
    assert replayed.admissibility("ev-1", POLICY).reasons == (EV.CONFLICTING_ID,)
    malformed = registry([unit("ev-neutral", status="neutral")])
    assert malformed.admissibility("ev-neutral", POLICY).reasons == (EV.NEUTRAL_STATUS,)
    replayed_malformed = EV.EvidenceRegistry.from_dict(json_roundtrip(malformed.to_dict()))
    assert replayed_malformed.admissibility("ev-neutral", POLICY).reasons == (EV.NEUTRAL_STATUS,)
    verdict = EV.verify_claim(
        claim(["ev-neutral"], fact=macd_fact()), registry=replayed_malformed, policy=POLICY
    )
    assert verdict.verdict == "abstain" and EV.NEUTRAL_STATUS in verdict.reasons


def test_a08_malformed_evidence_metadata_is_quarantined():
    broken = unit("ev-broken")
    del broken["content_ref"]
    assert registry([broken]).admissibility("ev-broken", POLICY).reasons == (EV.MALFORMED,)
    assert registry([unit("ev-src", source="blog")]).admissibility(
        "ev-src", POLICY
    ).reasons == (EV.MALFORMED,)


def test_future_fact_period_and_provenance_inversion_fail_closed():
    future_period = registry([unit("ev-period", fact=macd_fact(period="2026-09-05"))])
    assert future_period.admissibility("ev-period", POLICY).reasons == (EV.FUTURE_LEAKAGE,)
    inverted = registry([unit("ev-inv", published_at="2026-08-31", available_as_of="2026-08-30")])
    assert inverted.admissibility("ev-inv", POLICY).reasons == (EV.INVALID_DATE,)
    no_limit = EV.FreshnessPolicy("default", None)
    assert inverted.admissibility("ev-inv", no_limit).reasons == (EV.INVALID_DATE,)


def test_fresh_recapture_does_not_reset_freshness():
    reg = registry([unit("ev-recapture", published_at="2026-07-01", available_as_of="2026-09-01")])
    assert reg.admissibility("ev-recapture", POLICY).reasons == (EV.STALE,)


def test_registry_ingests_evidenceunit_objects_like_mappings():
    reg = registry([EV.EvidenceUnit.from_record(unit("ev-object")), unit("ev-map")])
    assert reg.admissibility("ev-object", POLICY).status == EV.ACCEPT
    assert reg.admissibility("ev-map", POLICY).status == EV.ACCEPT
    conflict = registry(
        [
            EV.EvidenceUnit.from_record(unit("ev-dup", fact=macd_fact())),
            EV.EvidenceUnit.from_record(unit("ev-dup", fact=macd_fact(relation="death_cross"))),
        ]
    )
    assert conflict.admissibility("ev-dup", POLICY).reasons == (EV.CONFLICTING_ID,)


@pytest.mark.parametrize("bad_item", [None, 123, "ev-1"])
def test_registry_rejects_non_mapping_batch_items(bad_item):
    with pytest.raises(ValueError) as info:
        registry([unit("ev-1"), bad_item])
    assert str(info.value) == EV.MALFORMED


def test_whitespace_only_mapping_id_is_skipped_but_replay_rejects():
    legacy = registry([unit("   "), unit()])
    assert legacy.admissibility("ev-1", POLICY).status == EV.ACCEPT
    assert legacy.admissibility("   ", POLICY).reasons == (EV.UNTRUSTED,)
    payload = json_roundtrip(legacy.to_dict())
    payload["quarantine"]["conflicted"] = ["   "]
    with pytest.raises(ValueError) as info:
        EV.EvidenceRegistry.from_dict(payload)
    assert str(info.value) == EV.MALFORMED


@pytest.mark.parametrize(
    ("category", "expected_reason"),
    [
        ("conflicted", EV.CONFLICTING_ID),
        ("foreign", EV.FOREIGN_REFERENCE),
        ("malformed", EV.MALFORMED),
    ],
)
def test_padded_replay_quarantine_ids_still_quarantine(category, expected_reason):
    original = registry([unit("ev-1")])
    assert original.admissibility("ev-1", POLICY).status == EV.ACCEPT
    payload = json_roundtrip(original.to_dict())
    if category == "malformed":
        payload["quarantine"]["malformed"] = [["  ev-1  ", EV.MALFORMED]]
    else:
        payload["quarantine"][category] = ["  ev-1  "]
    replayed = EV.EvidenceRegistry.from_dict(payload)
    admitted = replayed.admissibility("ev-1", POLICY)
    assert admitted.status == EV.REJECT
    assert admitted.reasons == (expected_reason,)


def test_typed_values_keep_bool_int_float_str_distinct():
    assert EV.CanonicalValue.from_value(True).to_dict() == {"kind": EV.VALUE_KIND_BOOL, "value": True}
    assert EV.CanonicalValue.from_value(1).to_dict() == {"kind": EV.VALUE_KIND_INT, "value": 1}
    assert EV.CanonicalValue.from_value(1.0).to_dict() == {"kind": EV.VALUE_KIND_FLOAT, "value": 1.0}
    assert EV.CanonicalValue.from_value("1").to_dict() == {"kind": EV.VALUE_KIND_STR, "value": "1"}
    assert not EV.values_equal(EV.CanonicalValue.from_value(True), EV.CanonicalValue.from_value(1))
    assert not EV.values_equal(EV.CanonicalValue.from_value(1), EV.CanonicalValue.from_value(1.0))
    assert not EV.values_equal(EV.CanonicalValue.from_value("1"), EV.CanonicalValue.from_value(1))
    bool_fact = EV.Fact.from_record(
        {"subject": "NVDA", "metric": "flag", "value": True, "relation": None, "unit": None, "period": None}
    )
    int_fact = EV.Fact.from_record(
        {"subject": "NVDA", "metric": "flag", "value": 1, "relation": None, "unit": None, "period": None}
    )
    assert not EV.fact_matches(bool_fact, int_fact)
    big = 2**63 + 1
    encoded = EV.CanonicalValue.from_value(big).to_dict()
    assert encoded["value"] == big
    assert type(encoded["value"]) is int
    assert json_roundtrip(encoded)["value"] == big


def test_non_finite_float_values_reject():
    for bad in (float("nan"), float("inf"), float("-inf")):
        with pytest.raises(ValueError) as info:
            EV.CanonicalValue.from_value(bad)
        assert str(info.value) == EV.NON_FINITE_VALUE
    raw = unit("ev-nan")
    raw["fact"] = {
        "subject": "NVDA",
        "metric": "close",
        "value": float("nan"),
        "relation": None,
        "unit": "usd",
        "period": "2026-08-30",
    }
    assert registry([raw]).admissibility("ev-nan", POLICY).reasons == (EV.NON_FINITE_VALUE,)


def test_a09_repeat_runs_and_json_roundtrip_are_deterministic():
    candidates = [unit(), unit("ev-future", available_as_of="2026-09-05")]
    first = registry(candidates)
    second = registry(candidates)
    assert first.to_dict() == second.to_dict()
    a = EV.verify_claim(claim(["ev-1", "ev-future"], fact=macd_fact()), registry=first, policy=POLICY)
    b = EV.verify_claim(claim(["ev-1", "ev-future"], fact=macd_fact()), registry=second, policy=POLICY)
    assert a == b
    for payload in (a.to_dict(), first.to_dict(), EV.ClaimVerdict("x", "hypothesis", ("r",), (), ()).to_dict()):
        assert_strict_json(payload)
        assert json_roundtrip(payload) == payload
        assert json.dumps(payload, allow_nan=False)


def test_production_imports_are_stdlib_or_same_leaf_only():
    for path in production_files():
        source, tree = parse_production(path)
        assert not source.startswith("\ufeff"), path
        for module, level, names in iter_imports(tree):
            if level:
                assert level == 1, (path, module, level)
                if module:
                    assert module not in LEAF_NAMES, (path, module)
                for name in names:
                    assert name not in LEAF_NAMES, (path, name)
                continue
            top = module.split(".")[0]
            assert top not in FORBIDDEN_IMPORTS, (path, module)
            if top == "tradingagents":
                parts = module.split(".")
                assert parts[:3] == ["tradingagents", "course", "evidence"], (path, module)
                if len(parts) > 3:
                    assert parts[3] not in LEAF_NAMES, (path, module)
                continue
            if top == "__future__":
                continue
            assert top in STDLIB, (path, module)


def test_production_has_no_clock_or_rng_calls():
    for path in production_files():
        _, tree = parse_production(path)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Attribute):
                    assert func.attr not in FORBIDDEN_CALLS, (path, func.attr)
                elif isinstance(func, ast.Name):
                    assert func.id not in FORBIDDEN_CALLS, (path, func.id)


def test_course_marker_has_no_imports_and_no_bom():
    source = COURSE_MARKER.read_text(encoding="utf-8")
    assert not source.startswith("\ufeff")
    tree = ast.parse(source, filename=str(COURSE_MARKER), feature_version=(3, 11))
    assert not any(isinstance(node, (ast.Import, ast.ImportFrom)) for node in ast.walk(tree))


def test_public_docstrings_cite_requirement_invariant_and_adr():
    for path in production_files():
        _, tree = parse_production(path)
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue
            if node.name.startswith("_"):
                continue
            doc = ast.get_docstring(node) or ""
            assert "FR-001" in doc, (path, node.name)
            assert "INV-001" in doc, (path, node.name)
            assert "ADR-005" in doc, (path, node.name)


def test_demo_cli_subprocess_is_deterministic_and_covers_fixed_cases():
    command = [sys.executable, "-m", "tradingagents.course.evidence", "--demo"]
    first = subprocess.run(command, cwd=REPO_ROOT, capture_output=True, text=True, timeout=120, check=False)
    second = subprocess.run(command, cwd=REPO_ROOT, capture_output=True, text=True, timeout=120, check=False)
    assert first.returncode == 0, first.stderr
    assert first.stdout == second.stdout
    assert "EVAL-008" in first.stdout and "accept_factual" in first.stdout
    assert "EVAL-009" in first.stdout and "future_leakage" in first.stdout
    assert "EVAL-006" in first.stdout and "hypothesis" in first.stdout
    lines = first.stdout.strip().splitlines()
    assert len(lines) == 3
    for line in lines:
        label, _, payload = line.partition(" ")
        assert label.startswith("EVAL-")
        assert_strict_json(json.loads(payload))

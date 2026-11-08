"""Offline tests for F4 global data sufficiency (FR-004 / INV-004).

Deterministic, fixed-date fixtures; no network, no LLM/API, no system clock.
"""

from __future__ import annotations

import json

import pytest

from tradingagents.course.data_quality.admission import admit
from tradingagents.course.data_quality.classifier import classify
from tradingagents.course.data_quality.contracts import (
    REQUIRED_DOMAINS,
    AdmissionDecision,
    DomainLabel,
    RawObservation,
    validate_label,
)

CUTOFF = "2026-11-05"
EARLY = "2026-10-06"


def _value(domain: str, value=1.0, as_of: str = CUTOFF, sentiment=None) -> RawObservation:
    """A valid value observation (explicit zero allowed via value=0)."""
    return RawObservation(
        domain=domain,
        kind="value",
        source=f"{domain}-src",
        observed_as_of=as_of,
        value=value,
        value_present=True,
        sentiment=sentiment,
    )


def _unavailable(domain: str, as_of: str = CUTOFF) -> RawObservation:
    return RawObservation(
        domain=domain, kind="no_data", source=f"{domain}-src", observed_as_of=as_of
    )


def _unknown(domain: str, as_of: str = CUTOFF) -> RawObservation:
    return RawObservation(
        domain=domain,
        kind="missing",
        source=f"{domain}-src",
        observed_as_of=as_of,
        value_present=False,
    )


def _all_available() -> list[RawObservation]:
    return [_value(domain) for domain in REQUIRED_DOMAINS]


def _exception_placeholders() -> list[str]:
    return list(REQUIRED_DOMAINS)


# ---------------------------------------------------------------- positive


@pytest.mark.unit
def test_pt1_all_available_proceeds():
    decision = admit(_all_available(), CUTOFF)
    assert decision.decision == "proceed"
    assert decision.insufficient_domains == []
    assert {label.domain for label in decision.labels} == set(REQUIRED_DOMAINS)


@pytest.mark.unit
def test_pt2_explicit_zero_neutral_is_available():
    obs = [
        _value("news"),
        _value("social", value=0, sentiment=0),
        _value("macro"),
        _value("price"),
        _value("fundamentals"),
    ]
    decision = admit(obs, CUTOFF)
    assert decision.decision == "proceed"
    social = [label for label in decision.labels if label.domain == "social"][0]
    assert social.status == "available"
    assert social.sentiment == 0
    assert social.source == "social-src"
    assert "neutral" in social.reason


@pytest.mark.unit
def test_pt3_one_unavailable_abstains():
    obs = [_unavailable("news")] + [
        _value(domain) for domain in REQUIRED_DOMAINS if domain != "news"
    ]
    decision = admit(obs, CUTOFF)
    assert decision.decision == "abstain"
    assert decision.insufficient_domains == ["news"]
    assert decision.reason


@pytest.mark.unit
def test_pt_early_evidence_is_accepted():
    obs = [_value(domain, as_of=EARLY) for domain in REQUIRED_DOMAINS]
    decision = admit(obs, CUTOFF)
    assert decision.decision == "proceed"


# ---------------------------------------------------------------- negative


@pytest.mark.unit
def test_nt1_unknown_domain_reviews_not_abstains():
    obs = [_unknown("macro")] + [
        _value(domain) for domain in REQUIRED_DOMAINS if domain != "macro"
    ]
    decision = admit(obs, CUTOFF)
    assert decision.decision == "review"
    assert "macro" in decision.insufficient_domains
    assert decision.decision not in ("proceed", "abstain")


@pytest.mark.unit
def test_nt2_unavailable_relabeled_neutral_rejected():
    label = DomainLabel(domain="news", status="neutral", as_of=CUTOFF, reason="labelled neutral")
    violations = validate_label(label)
    assert any(v.code == "neutral_status_forbidden" for v in violations)

    decision = admit([label] + [
        _value(domain) for domain in REQUIRED_DOMAINS if domain != "news"
    ], CUTOFF)
    assert decision.decision == "review"
    assert any(v.code == "neutral_status_forbidden" for v in decision.violations)


@pytest.mark.unit
def test_nt3_missing_field_defaulted_to_zero_intercepted():
    # Missing field but value=0 supplied as a placeholder -> must not be trusted.
    placeholder = RawObservation(
        domain="news",
        kind="missing",
        source="news-src",
        observed_as_of=CUTOFF,
        value=0,
        value_present=False,
        sentiment=0,
    )
    decision = admit([placeholder] + [
        _value(domain) for domain in REQUIRED_DOMAINS if domain != "news"
    ], CUTOFF)
    assert decision.decision == "review"
    assert "news" in decision.insufficient_domains
    assert decision.decision != "proceed"


@pytest.mark.unit
def test_nt4_unknown_relabeled_neutral_rejected():
    label = DomainLabel(domain="macro", status="neutral", as_of=CUTOFF, reason="labelled neutral")
    violations = validate_label(label)
    assert violations
    assert all(v.code != "ok" for v in violations)

    decision = admit([label] + [
        _value(domain) for domain in REQUIRED_DOMAINS if domain != "macro"
    ], CUTOFF)
    assert decision.decision == "review"
    assert "macro" in decision.insufficient_domains


@pytest.mark.unit
def test_nt5_empty_input_reviews_all_domains():
    decision = admit([], CUTOFF)
    assert decision.decision == "review"
    assert set(decision.insufficient_domains) == set(REQUIRED_DOMAINS)


@pytest.mark.unit
def test_nt6_missing_required_domain_reviews():
    obs = [_value(domain) for domain in REQUIRED_DOMAINS if domain != "fundamentals"]
    decision = admit(obs, CUTOFF)
    assert decision.decision == "review"
    assert "fundamentals" in decision.insufficient_domains


@pytest.mark.unit
def test_nt7_duplicate_conflicting_domain_reviews():
    obs = _all_available()
    obs.append(_unavailable("price"))
    decision = admit(obs, CUTOFF)
    assert decision.decision == "review"
    assert any(v.code == "duplicate_conflict" for v in decision.violations)


@pytest.mark.unit
def test_nt8_invalid_domain_reviews():
    obs = _all_available() + [_value("weather")]
    decision = admit(obs, CUTOFF)
    assert decision.decision == "review"
    assert any(v.code == "invalid_domain" for v in decision.violations)


@pytest.mark.unit
def test_nt9_invalid_status_reviews():
    label = DomainLabel(domain="news", status="partial", as_of=CUTOFF, reason="partial data")
    decision = admit([label] + [
        _value(domain) for domain in REQUIRED_DOMAINS if domain != "news"
    ], CUTOFF)
    assert decision.decision == "review"
    assert any(v.code == "invalid_status" for v in decision.violations)


@pytest.mark.unit
def test_nt10_invalid_date_reviews():
    label = DomainLabel(domain="news", status="available", as_of="2026-13-40", reason="bad date")
    decision = admit([label] + [
        _value(domain) for domain in REQUIRED_DOMAINS if domain != "news"
    ], CUTOFF)
    assert decision.decision == "review"
    assert any(v.code == "invalid_date" for v in decision.violations)


@pytest.mark.unit
def test_nt11_future_date_reviews():
    obs = [_value("news", as_of="2026-11-06")] + [
        _value(domain) for domain in REQUIRED_DOMAINS if domain != "news"
    ]
    decision = admit(obs, CUTOFF)
    assert decision.decision == "review"
    assert any(v.code == "future_date" for v in decision.violations)


@pytest.mark.unit
def test_nt12_invalid_cutoff_reviews():
    decision = admit(_all_available(), "not-a-date")
    assert decision.decision == "review"
    assert any(v.code == "invalid_cutoff" for v in decision.violations)


# ---------------------------------------------------------------- extended


@pytest.mark.unit
def test_explicit_zero_vs_missing_distinction():
    zero_label = classify(_value("price", value=0))
    missing_label = classify(
        RawObservation(domain="price", kind="missing", source="price-src",
                       observed_as_of=CUTOFF, value=None, value_present=False)
    )
    assert zero_label.status == "available"
    assert missing_label.status == "unknown"


@pytest.mark.unit
def test_deterministic_decisions():
    first = admit(_all_available(), CUTOFF).to_dict()
    second = admit(_all_available(), CUTOFF).to_dict()
    assert first == second

    unavailable_first = admit(
        [_unavailable("social")] + [
            _value(domain) for domain in REQUIRED_DOMAINS if domain != "social"
        ],
        CUTOFF,
    ).to_dict()
    unavailable_second = admit(
        [_value(domain) for domain in REQUIRED_DOMAINS if domain != "social"]
        + [_unavailable("social")],
        CUTOFF,
    ).to_dict()
    assert unavailable_first == unavailable_second


@pytest.mark.unit
def test_refusal_event_fields_complete_and_serializable():
    cases = [
        admit(_all_available(), CUTOFF),
        admit([_unavailable("news")] + [
            _value(domain) for domain in REQUIRED_DOMAINS if domain != "news"
        ], CUTOFF),
        admit([_unknown("macro")] + [
            _value(domain) for domain in REQUIRED_DOMAINS if domain != "macro"
        ], CUTOFF),
    ]
    for decision in cases:
        payload = decision.to_dict()
        assert payload["decision"] in ("proceed", "abstain", "review")
        assert isinstance(payload["insufficient_domains"], list)
        assert isinstance(payload["reason"], str) and payload["reason"]
        assert payload["analysis_cutoff"] == CUTOFF
        for label in payload["labels"]:
            assert set(label) >= {"domain", "status", "as_of", "reason"}
        # Must be JSON-serializable.
        json.dumps(payload)


@pytest.mark.unit
def test_admission_decision_requires_no_extra_dependency():
    # Sanity: the module is importable without heavy runtime deps and has no
    # side effects at import time.
    assert AdmissionDecision(decision="review").decision == "review"
    assert _exception_placeholders() == list(REQUIRED_DOMAINS)

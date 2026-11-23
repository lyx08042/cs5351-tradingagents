"""Scenario combiner for the demo page.

The page lets the reader choose one option per module and shows what the system
does with that combination. Every branch below calls the module's own function;
nothing is simulated.

Kept in its own module so `collect.py` stays readable and so the escaping of a
large embedded string cannot corrupt it.
"""

from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

TRADE_DATE = "2026-09-01"
DOMAINS = ("news", "social", "macro", "price", "fundamentals")

SCENARIO_OPTIONS: dict[str, list] = {
    "D": ["all available", "one domain missing", "all unavailable"],
    "A": ["valid evidence", "future evidence", "no evidence"],
    "B": ["no cap", 220_000, 180_000, 120_000],
    "C": ["small buy", "buy beyond cash"],
    "E": ["normal write", "overwrite a decision"],
}


def _observations(mode: str) -> list[dict]:
    if mode == "all unavailable":
        chosen, kind, value = DOMAINS, "no_data", None
    elif mode == "one domain missing":
        chosen, kind, value = DOMAINS[:4], "value", 1
    else:
        chosen, kind, value = DOMAINS, "value", 1
    return [
        {
            "domain": domain,
            "kind": kind,
            "value": value,
            "value_present": value is not None,
            "source": "demo-scenario",
            "observed_as_of": "2026-08-30",
        }
        for domain in chosen
    ]


def _evidence(mode: str) -> dict:
    """Build an evidence context the way the module's own tests do."""
    from tradingagents.course.evidence import EvidenceRegistry, Fact, FreshnessPolicy

    if mode == "no evidence":
        return {}

    published = TRADE_DATE if mode == "valid evidence" else "2026-09-05"
    fact = Fact.from_record(
        {
            "subject": "NVDA",
            "metric": "close",
            "value": {"kind": "float", "value": 100.5},
            "relation": None,
            "unit": "USD",
            "period": published,
        }
    )
    registry = EvidenceRegistry.build(
        run_id="demo-scenario",
        as_of=published,
        candidates=[
            {
                "evidence_id": "ev-1",
                "run_id": "demo-scenario",
                "source": "tool",
                "status": "available",
                "published_at": published,
                "available_as_of": published,
                "policy": "demo",
                "fact": fact,
            }
        ],
    )
    policy = FreshnessPolicy(name="demo", max_age_days=10)
    return {
        "as_of": published,
        "registry": registry.to_dict(),
        "policy": policy.to_dict(),
    }


def _d(mode: str) -> dict:
    from tradingagents.course.data_quality.admission import admit

    decision = admit(_observations(mode), TRADE_DATE)
    return {
        "module": "D",
        "input": mode,
        "verdict": decision.decision,
        "blocks": decision.decision != "proceed",
        "detail": ", ".join(decision.insufficient_domains) or "all five domains available",
    }


def _a(mode: str) -> dict:
    from tradingagents.course.evidence.integration import resolve_evidence_context

    try:
        resolution = resolve_evidence_context(_evidence(mode), trade_date=TRADE_DATE)
        allowed = resolution.allowed
        detail = resolution.reason or "accepted"
    except Exception as exc:  # noqa: BLE001 - report, never crash the page
        allowed = False
        detail = type(exc).__name__
    return {
        "module": "A",
        "input": mode,
        "verdict": "accepted" if allowed else "rejected",
        "blocks": not allowed,
        "detail": detail,
    }


def _b(cap) -> dict:
    from tradingagents.course.budget.replay import baseline_trace, replay

    trace = baseline_trace()
    if cap in (None, "no cap"):
        result = replay(trace, limit_tokens=None)
        return {
            "module": "B",
            "input": "no cap",
            "verdict": f"{result.total_tokens:,} tokens / L0",
            "blocks": False,
            "detail": f"{result.calls_executed} calls, {result.completed if hasattr(result, 'completed') else result.ended}",
        }
    result = replay(trace, limit_tokens=int(cap))
    return {
        "module": "B",
        "input": f"cap {int(cap):,}",
        "verdict": f"{result.total_tokens:,} tokens / L{result.level}",
        "blocks": False,
        "detail": f"{result.calls_executed} calls, {result.skipped} skipped",
    }


def _c(mode: str) -> dict:
    from tradingagents.course.safety import (
        HoldingsSnapshot,
        RuleSet,
        SafetyContext,
        validate_proposal,
    )

    rule_version = "cde-long-only-v1"
    units = 1 if mode == "small buy" else 100_000
    snapshot = HoldingsSnapshot(
        snapshot_id="s1",
        as_of=TRADE_DATE,
        currency="USD",
        cash=Decimal("1000.00"),
        positions={},
        flat_declared=True,
    )
    context = SafetyContext(
        instrument="NVDA",
        instrument_currency="USD",
        holdings_snapshot=snapshot,
        rule_set=RuleSet(version=rule_version),
        available_rule_versions=frozenset({rule_version}),
    )
    verdict = validate_proposal(
        {
            "action": "buy",
            "units": units,
            "price": "100.00",
            "currency": "USD",
            "holdings_snapshot": {
                "snapshot_id": "s1",
                "as_of": TRADE_DATE,
                "currency": "USD",
                "cash": "1000.00",
                "positions": {},
                "flat_declared": True,
            },
            "rule_version": rule_version,
            "status": "proposed",
        },
        context=context,
    )
    return {
        "module": "C",
        "input": mode,
        "verdict": verdict.status.value,
        "blocks": verdict.status.value != "accepted",
        "detail": verdict.reason_code.value,
    }


def _e(mode: str) -> dict:
    from tradingagents.course.audit import AuditError, AuditStore

    audit_dir = ROOT / ".demo_audit"
    audit_dir.mkdir(exist_ok=True)
    db = audit_dir / "scenario.db"
    db.unlink(missing_ok=True)
    store = AuditStore.open(str(db))
    store.append(
        record_id="r1",
        run_id="demo-scenario",
        timestamp="2026-09-01T12:00:00Z",
        entry_type="decision",
        payload={"final_rating": "Buy"},
        rules_version="cde-long-only-v1",
    )
    if mode == "overwrite a decision":
        try:
            store.append(
                record_id="r1",
                run_id="demo-scenario",
                timestamp="2026-09-01T12:05:00Z",
                entry_type="decision",
                payload={"final_rating": "Sell"},
                rules_version="cde-long-only-v1",
            )
            verdict, detail = "accepted", "overwrite allowed"
        except AuditError as exc:
            verdict, detail = "rejected", str(exc).split(":")[0]
    else:
        verdict, detail = "recorded", "first write accepted"
    store.close()
    db.unlink(missing_ok=True)
    audit_dir.rmdir()
    return {
        "module": "E",
        "input": mode,
        "verdict": verdict,
        "blocks": verdict == "rejected",
        "detail": detail,
    }


def run_scenario(choices: dict | None = None) -> dict:
    """Run D, A, B, C and E against one combination and collect their verdicts."""
    choices = choices or {}
    rows = [
        _d(choices.get("D", SCENARIO_OPTIONS["D"][0])),
        _a(choices.get("A", SCENARIO_OPTIONS["A"][0])),
        _b(choices.get("B", SCENARIO_OPTIONS["B"][0])),
        _c(choices.get("C", SCENARIO_OPTIONS["C"][0])),
        _e(choices.get("E", SCENARIO_OPTIONS["E"][0])),
    ]
    blockers = [row["module"] for row in rows if row["blocks"]]
    final = f"blocked by {', '.join(blockers)}" if blockers else "every module allows the run"
    return {"choices": choices, "modules": rows, "final": final}


def sample_scenarios() -> list[dict]:
    """A few combinations the page ships with, each executed at collect time."""
    return [
        run_scenario({}),
        run_scenario({"D": "one domain missing"}),
        run_scenario({"A": "future evidence"}),
        run_scenario({"B": 120_000, "C": "buy beyond cash"}),
        run_scenario({"E": "overwrite a decision"}),
    ]

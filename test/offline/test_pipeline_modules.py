"""Offline tests for the pipeline integration of roles A and B.

The pipeline gained two optional keyword arguments. These tests pin the
contract: without them nothing changes, with them they reach ``invoke_ai``,
and an ``invoke_ai`` that cannot accept them fails loudly instead of silently
ignoring them.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from tradingagents.course.pipeline import CourseExecutionError, run_course


def _request(audit_path: Path) -> dict[str, Any]:
    """A minimal course request that passes D so the model path is reached."""
    return {
        "run_id": "test-run",
        "timestamp": "2026-11-23T00:00:00Z",
        "analysis_cutoff": "2026-09-01",
        "instrument": "NVDA",
        "instrument_currency": "USD",
        "rule_version": "cde-long-only-v1",
        "holdings_snapshot": {
            "cash": "1000.00",
            "positions": [{"ticker": "NVDA", "quantity": 1}],
        },
        "observations": [
            {"domain": d, "kind": "value", "value": 1, "value_present": True,
             "source": "fixture", "observed_as_of": "2026-08-30"}
            for d in ("news", "social", "macro", "price", "fundamentals")
        ],
        "audit_path": str(audit_path),
    }


@pytest.fixture
def audit_dir(tmp_path_factory):
    """A writable directory for the audit file, removed after the test.

    `tmp_path` is blocked by the sandbox on the authoring machine, so this
    fixture falls back to a directory beside the test file.
    """
    import shutil
    try:
        yield tmp_path_factory.mktemp("audit")
        return
    except Exception:
        pass
    base = Path(__file__).resolve().parent / "_tmp_audit"
    if base.exists():
        shutil.rmtree(base, ignore_errors=True)
    base.mkdir(exist_ok=True)
    yield base
    shutil.rmtree(base, ignore_errors=True)


@pytest.fixture
def captured():
    seen: dict[str, Any] = {}

    def invoke(context: str, **kwargs: Any):
        seen["context"] = context
        seen["kwargs"] = kwargs
        return {"simulation_proposal": None}

    return seen, invoke


def test_without_extras_the_callback_receives_only_the_context(audit_dir, captured) -> None:
    """FR-002 / FR-001: the default call signature is unchanged."""
    seen, invoke = captured

    run_course(_request(audit_dir / "audit.db"), invoke)

    assert "context" in seen
    assert seen["kwargs"] == {}


def test_budget_is_forwarded(audit_dir, captured) -> None:
    """FR-002: a ledger supplied to the pipeline reaches the graph callback."""
    seen, invoke = captured
    ledger = object()

    run_course(_request(audit_dir / "audit.db"), invoke, budget=ledger)

    assert seen["kwargs"]["budget"] is ledger


def test_evidence_context_is_forwarded(audit_dir, captured) -> None:
    """FR-001: an evidence context supplied to the pipeline reaches the callback."""
    seen, invoke = captured
    evidence = {"as_of": "2026-09-01"}

    run_course(_request(audit_dir / "audit.db"), invoke, evidence_context=evidence)

    assert seen["kwargs"]["evidence_context"] is evidence


def test_both_extras_are_forwarded_together(audit_dir, captured) -> None:
    """FR-002 + FR-001: both modules can be enabled in one run."""
    seen, invoke = captured
    ledger, evidence = object(), {"as_of": "2026-09-01"}

    run_course(_request(audit_dir / "audit.db"), invoke,
               budget=ledger, evidence_context=evidence)

    assert seen["kwargs"] == {"budget": ledger, "evidence_context": evidence}


def test_callback_without_kwargs_support_fails_loudly(audit_dir) -> None:
    """A callback that cannot accept the modules must not silently ignore them."""
    def narrow(context: str):
        return {"simulation_proposal": None}

    with pytest.raises(CourseExecutionError):
        run_course(_request(audit_dir / "audit.db"), narrow, budget=object())


def test_none_values_are_not_forwarded(audit_dir, captured) -> None:
    """Explicit None means "not enabled", not "pass None through"."""
    seen, invoke = captured

    run_course(_request(audit_dir / "audit.db"), invoke,
               budget=None, evidence_context=None)

    assert seen["kwargs"] == {}

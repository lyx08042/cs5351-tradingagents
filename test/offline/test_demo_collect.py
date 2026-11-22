"""Tests for the demo page's data collector.

The page renders whatever `demo.collect` writes, so a wrong collector means a
wrong demo. These tests pin the shape and the provenance of each figure.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from demo import collect

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def payload(tmp_path_factory):
    """Run the collector once and hand back what it produced."""
    collect.main()
    data_path = Path(collect.__file__).parent / "data.json"
    return json.loads(data_path.read_text(encoding="utf-8"))


def test_baseline_figures_match_the_recorded_run(payload) -> None:
    """The baseline block is read from docs/baseline.md, not invented."""
    baseline = payload["baseline"]
    assert baseline["calls"] == 19
    assert baseline["tokens"] == 228_275
    assert baseline["seconds"] == pytest.approx(150.61, abs=0.01)


def test_replay_matches_the_budget_module(payload) -> None:
    """The replay rows come from the same function the module's own tests use.

    Recomputing here means a change in `replay.py` cannot silently leave the
    page showing stale numbers.
    """
    from tradingagents.course.budget.replay import compare

    expected = compare([240_000, 200_000, 180_000, 150_000, 120_000])
    rows = payload["replay"]

    assert len(rows) == len(expected)
    for row, result in zip(rows, expected, strict=True):
        assert row["limit"] == result.limit_tokens
        assert row["calls"] == result.calls_executed
        assert row["tokens"] == result.total_tokens
        assert row["level"] == result.level


def test_a_cap_above_the_baseline_does_not_degrade(payload) -> None:
    """BUG-004 regression, visible on the page: 240k must stay at L0."""
    row = next(r for r in payload["replay"] if r["limit"] == 240_000)

    assert row["level"] == 0
    assert row["skipped"] == 0
    assert row["delta"] == 0.0


def test_replay_is_sorted_by_descending_budget(payload) -> None:
    """The table reads top-down from the loosest cap to the tightest."""
    limits = [r["limit"] for r in payload["replay"]]

    assert limits[0] is None
    assert limits[1:] == sorted(limits[1:], reverse=True)


def test_every_module_has_requirements_and_tests(payload) -> None:
    """Each role maps to at least one requirement and one test file."""
    for role in ("A", "B", "C", "D", "E"):
        assert payload["modules"][role]["reqs"], role
        assert payload["tests"][role], f"{role} has no test file"


def test_trace_covers_the_budget_requirements(payload) -> None:
    """FR-006 and INV-006 came from this work and must appear in the trace."""
    ids = {row["id"] for row in payload["trace"]}

    assert {"FR-002", "FR-006", "INV-002", "INV-006"} <= ids


def test_process_evidence_is_present(payload) -> None:
    """The demo shows review rounds and defects, so both must be non-empty."""
    assert payload["reviews"], "no review entries collected"
    assert any(b["id"] == "BUG-004" for b in payload["defects"])


def test_collected_json_is_valid_and_serialisable(payload) -> None:
    """The page parses this file, so it must round-trip through JSON."""
    text = json.dumps(payload, ensure_ascii=False)
    assert json.loads(text) == payload

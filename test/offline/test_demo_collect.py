"""Tests for the demo page's data collector.

The page renders whatever `demo.collect` writes, so a wrong collector means a
wrong demo. These tests pin the shape and the provenance of each figure.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from demo import collect

ROOT = Path(__file__).resolve().parents[2]


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

def test_sweep_covers_the_slider_range(payload) -> None:
    """The slider needs a row per step, from 100k to 300k."""
    sweep = payload["sweep"]

    assert len(sweep) == 21
    assert sweep[0]["limit"] == 100_000
    assert sweep[-1]["limit"] == 300_000


def test_sweep_never_spends_more_as_the_cap_shrinks(payload) -> None:
    """Monotonic in the cap: a tighter budget cannot cost more tokens."""
    tokens = [row["tokens"] for row in payload["sweep"]]

    assert tokens == sorted(tokens)


def test_the_widest_cap_matches_the_baseline(payload) -> None:
    """300k is above the recorded run, so nothing changes."""
    row = payload["sweep"][-1]

    assert row["delta"] == 0.0
    assert row["level"] == 0
    assert row["calls"] == payload["baseline"]["calls"]


def test_rejection_cases_were_actually_executed(payload) -> None:
    """Each card carries the outcome the code returned, not a label typed in."""
    by_key = {c["key"]: c["outcome"] for c in payload["rejections"]}

    assert by_key["proceed"] == "proceed"
    assert by_key["unavailable"] == "abstain"
    assert by_key["unknown"] == "review"
    assert by_key["budget"] == "call_limit"


def test_unavailable_and_unknown_stay_distinct(payload) -> None:
    """FR-004 / INV-004: the two failures must not collapse into one answer."""
    by_key = {c["key"]: c["outcome"] for c in payload["rejections"]}

    assert by_key["unavailable"] != by_key["unknown"]

def test_timeline_records_the_design_change(payload) -> None:
    """The page tells the BUG-004 story, so the steps must be present in order."""
    steps = [node["step"] for node in payload["timeline"]]

    assert steps == ["v1", "found", "v2", "guard"]


def test_timeline_ends_with_the_current_behaviour(payload) -> None:
    """The v2 line quotes the replay, not a hand-written claim."""
    row = next(r for r in payload["replay"] if r["limit"] == 240_000)
    v2 = next(node for node in payload["timeline"] if node["step"] == "v2")

    assert f"L{row['level']}" in v2["result"]
    assert f"{row['calls']} calls" in v2["result"]
    assert f"{row['tokens']:,} tokens" in v2["result"]

def test_governance_records_both_episodes(payload) -> None:
    """The process section must show the review catch and the CI catch."""
    text = " ".join(node["detail"] + node["title"] for node in payload["governance"])

    assert "AI-USE-0002" in text
    assert "BOM" in text


def test_ci_checks_are_read_from_the_workflows(payload) -> None:
    """A check appears only if the workflow file really wires it in."""
    names = {c["name"] for c in payload["ci"]["checks"]}

    assert "course scaffold" in names
    assert "course offline suite" in names


def test_the_course_suite_is_reported_as_wired(payload) -> None:
    """The delivery branch runs the full course suite; if that regresses the page must say so."""
    suite = next(c for c in payload["ci"]["checks"] if c["name"] == "course offline suite")

    assert suite["state"] == "on", "course-bootstrap no longer runs the full offline suite"

def test_every_module_has_a_story(payload) -> None:
    """Each role gets a section in the switcher, so all five appear in the demo."""
    stories = payload["stories"]

    assert set(stories) == {"A", "B", "C", "D", "E"}
    for role, story in stories.items():
        assert story["question"], role
        assert story["answer"], role
        assert story["refuse"], role
        assert story["files"], f"{role} lists no code files"


def test_story_adr_references_existing_files(payload) -> None:
    """A story names an ADR only when that ADR exists on disk."""
    adr_dir = ROOT / "docs" / "architecture" / "adr"

    for role, story in payload["stories"].items():
        if story["adr"]:
            assert (adr_dir / story["adr"]).exists(), f"{role} names a missing ADR"

"""Offline tests for the deterministic replay of the baseline trace.

The replay is a what-if analysis, not a live measurement: these tests pin the
aggregates to `docs/baseline.md` and assert that the ledger, the policy and the
skip rules behave monotonically as the budget shrinks.
"""

from __future__ import annotations

from tradingagents.course.budget.replay import (
    BASELINE_CALLS,
    BASELINE_TOTAL_TOKENS,
    baseline_trace,
    compare,
    replay,
)


def test_trace_matches_the_recorded_baseline_totals() -> None:
    """The synthetic trace reproduces the 19 calls and 228,275 tokens of the run."""
    trace = baseline_trace()

    assert len(trace) == BASELINE_CALLS
    assert sum(call.input_tokens + call.output_tokens for call in trace) == BASELINE_TOTAL_TOKENS


def test_unbudgeted_replay_is_the_baseline() -> None:
    """Without a ledger the replay reproduces the trace unchanged."""
    result = replay(baseline_trace(), limit_tokens=None)

    assert result.calls_executed == BASELINE_CALLS
    assert result.total_tokens == BASELINE_TOTAL_TOKENS
    assert result.level == 0
    assert result.ended == "completed"


def test_a_generous_budget_changes_nothing() -> None:
    """A budget above the baseline must not degrade a healthy run."""
    result = replay(baseline_trace(), limit_tokens=BASELINE_TOTAL_TOKENS + 20_000)

    assert result.level == 0
    assert result.degradations == 0
    assert result.total_tokens == BASELINE_TOTAL_TOKENS
    assert result.calls_executed == BASELINE_CALLS


def test_a_tight_budget_compresses_and_saves_tokens() -> None:
    """A budget below the baseline triggers L1 and cuts token use."""
    result = replay(baseline_trace(), limit_tokens=200_000)

    assert result.level >= 1
    assert result.degradations >= 1
    assert result.total_tokens < BASELINE_TOTAL_TOKENS
    assert result.ended == "completed"


def test_smaller_budgets_never_spend_more() -> None:
    """The ladder is monotonic: a smaller budget cannot cost more tokens."""
    results = compare([240_000, 200_000, 180_000, 120_000])
    tokens = [result.total_tokens for result in results]

    assert tokens == sorted(tokens, reverse=True)


def test_replay_is_deterministic() -> None:
    """The same trace and budget produce the same record twice."""
    first = replay(baseline_trace(), limit_tokens=180_000)
    second = replay(baseline_trace(), limit_tokens=180_000)

    assert first.to_dict() == second.to_dict()


def test_replay_reports_the_highest_level_reached() -> None:
    """A very tight budget escalates beyond compression."""
    result = replay(baseline_trace(), limit_tokens=120_000)

    assert result.level >= 3
    assert result.skipped >= 1
    assert result.calls_executed < BASELINE_CALLS

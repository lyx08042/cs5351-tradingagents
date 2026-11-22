"""Deterministic replay of the recorded baseline trace under the budget (FR-002).

This is a what-if analysis, not a live model measurement. The aggregate
numbers come from `docs/baseline.md` (one real run: 19 calls, 228,275 tokens,
150.61 s); the per-call split is a synthetic distribution calibrated to those
aggregates, because the original run did not record per-call usage.

What the replay does prove: given a token trace, the ledger, the degradation
policy and the skip rules produce a deterministic outcome, so the behaviour is
reproducible and testable without spending money.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from .contracts import STAGES, BudgetDenied, LedgerConfig
from .ledger import BudgetLedger
from .policy import L2_FEWER_ROUNDS, L4_SKIP_OPTIONAL_AGENT, L5_DEGRADED_VERDICT, DegradationPolicy

BASELINE_INPUT_TOKENS = 196_870
BASELINE_OUTPUT_TOKENS = 31_405
BASELINE_TOTAL_TOKENS = BASELINE_INPUT_TOKENS + BASELINE_OUTPUT_TOKENS
BASELINE_CALLS = 19

# (agent, stage, model tier, number of calls) 鈥?9 + 4 + 1 + 1 + 3 + 1 = 19
CALL_PLAN: tuple[tuple[str, str, str, int], ...] = (
    ("market_analyst", "analyst", "quick", 3),
    ("social_analyst", "analyst", "quick", 2),
    ("news_analyst", "analyst", "quick", 2),
    ("fundamentals_analyst", "analyst", "quick", 2),
    ("bull_researcher", "debate", "quick", 2),
    ("bear_researcher", "debate", "quick", 2),
    ("research_manager", "research_manager", "deep", 1),
    ("trader", "trader", "deep", 1),
    ("aggressive_analyst", "risk_debate", "quick", 1),
    ("neutral_analyst", "risk_debate", "quick", 1),
    ("conservative_analyst", "risk_debate", "quick", 1),
    ("portfolio_manager", "portfolio_manager", "deep", 1),
)

# Share of the run's tokens per stage; matches the quota split in the scope doc.
STAGE_SHARE: dict[str, float] = {
    "analyst": 0.40,
    "debate": 0.25,
    "research_manager": 0.08,
    "trader": 0.07,
    "risk_debate": 0.15,
    "portfolio_manager": 0.05,
}

OPTIONAL_AGENTS: tuple[str, ...] = ("social_analyst", "news_analyst")

L1_INPUT_SCALE = 0.60


@dataclass(frozen=True)
class TraceCall:
    index: int
    agent: str
    stage: str
    model_tier: str
    input_tokens: int
    output_tokens: int


@dataclass(frozen=True)
class ReplayResult:
    limit_tokens: int | None
    calls_executed: int
    input_tokens: int
    output_tokens: int
    tokens_spent: int
    level: int
    degradations: int
    skipped: int
    ended: str

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    def to_dict(self) -> dict[str, object]:
        return {
            "limit_tokens": self.limit_tokens,
            "calls_executed": self.calls_executed,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "tokens_spent": self.tokens_spent,
            "level": self.level,
            "degradations": self.degradations,
            "skipped": self.skipped,
            "ended": self.ended,
        }


def _split(total: int, parts: int, index: int) -> int:
    """Deterministic split of ``total`` into ``parts`` values; last one takes the rest."""
    base = total // parts
    if index == parts - 1:
        return total - base * (parts - 1)
    return base


def baseline_trace(
    input_tokens: int = BASELINE_INPUT_TOKENS,
    output_tokens: int = BASELINE_OUTPUT_TOKENS,
) -> tuple[TraceCall, ...]:
    """Build the synthetic per-call trace that matches the recorded totals."""
    calls: list[TraceCall] = []
    index = 0
    for stage in STAGES:
        entries = [entry for entry in CALL_PLAN if entry[1] == stage]
        count = sum(entry[3] for entry in entries)
        if not count:
            continue
        stage_input = int(input_tokens * STAGE_SHARE[stage])
        stage_output = int(output_tokens * STAGE_SHARE[stage])
        offset = 0
        for agent, _stage, tier, repeats in entries:
            for _ in range(repeats):
                calls.append(
                    TraceCall(
                        index=index,
                        agent=agent,
                        stage=stage,
                        model_tier=tier,
                        input_tokens=_split(stage_input, count, offset),
                        output_tokens=_split(stage_output, count, offset),
                    )
                )
                index += 1
                offset += 1

    # Push any rounding remainder onto the last call so totals stay exact.
    drift_input = input_tokens - sum(call.input_tokens for call in calls)
    drift_output = output_tokens - sum(call.output_tokens for call in calls)
    if drift_input or drift_output:
        last = calls[-1]
        calls[-1] = TraceCall(
            index=last.index,
            agent=last.agent,
            stage=last.stage,
            model_tier=last.model_tier,
            input_tokens=last.input_tokens + drift_input,
            output_tokens=last.output_tokens + drift_output,
        )
    return tuple(calls)


def _stage_estimates(trace: Sequence[TraceCall]) -> dict[tuple[str | None, str], int]:
    totals: dict[str, int] = {}
    counts: dict[str, int] = {}
    for call in trace:
        totals[call.stage] = totals.get(call.stage, 0) + call.input_tokens + call.output_tokens
        counts[call.stage] = counts.get(call.stage, 0) + 1
    return {(None, stage): max(1, totals[stage] // counts[stage]) for stage in totals}


def replay(
    trace: Sequence[TraceCall],
    *,
    limit_tokens: int | None = None,
) -> ReplayResult:
    """Replay a trace with (or without) a budget; deterministic by construction."""
    if limit_tokens is None:
        return ReplayResult(
            limit_tokens=None,
            calls_executed=len(trace),
            input_tokens=sum(call.input_tokens for call in trace),
            output_tokens=sum(call.output_tokens for call in trace),
            tokens_spent=0,
            level=0,
            degradations=0,
            skipped=0,
            ended="completed",
        )

    config = LedgerConfig(
        limit_tokens=limit_tokens,
        limit_calls=len(trace) + 10,
        estimate_margin=1.0,
    )
    ledger = BudgetLedger(config, stage_estimates=_stage_estimates(trace))
    policy = DegradationPolicy(config)

    executed_input = 0
    executed_output = 0
    calls_executed = 0
    skipped = 0
    debate_calls = 0
    ended = "completed"

    ahead: dict[str, int] = {}
    for call in trace:
        ahead[call.stage] = ahead.get(call.stage, 0) + 1

    for call in trace:
        ahead[call.stage] -= 1

        projected = sum(count * ledger.estimate("", name) for name, count in ahead.items())
        level = policy.evaluate(
            ledger,
            call.stage,
            remaining_calls=ahead[call.stage],
            projected_remaining_tokens=projected,
        )
        if level is not None:
            ledger.apply_level(level)
        current = ledger.level

        if current >= L5_DEGRADED_VERDICT:
            ended = "degraded_verdict"
            break

        if current >= L4_SKIP_OPTIONAL_AGENT and call.agent in OPTIONAL_AGENTS:
            skipped += 1
            continue

        if current >= L2_FEWER_ROUNDS and call.stage == "debate":
            if debate_calls >= 2:
                skipped += 1
                continue
            debate_calls += 1

        input_tokens = call.input_tokens
        if current >= 1:
            input_tokens = max(1, int(input_tokens * L1_INPUT_SCALE))

        try:
            reservation = ledger.reserve(call.agent, call.stage, call.model_tier)
        except BudgetDenied:
            skipped += 1
            if ledger.state == "exhausted":
                ended = "exhausted"
                break
            continue

        ledger.settle(reservation.call_id, input_tokens, call.output_tokens)
        executed_input += input_tokens
        executed_output += call.output_tokens
        calls_executed += 1

    return ReplayResult(
        limit_tokens=limit_tokens,
        calls_executed=calls_executed,
        input_tokens=executed_input,
        output_tokens=executed_output,
        tokens_spent=ledger.snapshot()["spent"],
        level=ledger.level,
        degradations=sum(1 for event in ledger.events() if event.type == "degraded"),
        skipped=skipped,
        ended=ended,
    )


def compare(limits: Sequence[int]) -> list[ReplayResult]:
    """Baseline plus one replay per budget, for the evaluation table."""
    trace = baseline_trace()
    results = [replay(trace, limit_tokens=None)]
    results.extend(replay(trace, limit_tokens=limit) for limit in limits)
    return results


__all__ = [
    "BASELINE_CALLS",
    "BASELINE_INPUT_TOKENS",
    "BASELINE_OUTPUT_TOKENS",
    "BASELINE_TOTAL_TOKENS",
    "CALL_PLAN",
    "OPTIONAL_AGENTS",
    "STAGE_SHARE",
    "ReplayResult",
    "TraceCall",
    "baseline_trace",
    "compare",
    "replay",
]

"""Degradation policy for the run budget (FR-006 / INV-006).

The policy is pure: it reads the ledger through public accessors and returns
the level that should apply. The caller applies it through
``BudgetLedger.apply_level``, which is the only mutator of the level and
therefore the place where monotonicity and mandatory event emission are
enforced.

Effects are exposed as small helpers so the graph nodes can ask "how many
debate rounds may I still run?" without embedding thresholds themselves.
"""

from __future__ import annotations

from .contracts import LedgerConfig
from .ledger import BudgetLedger

L0_NORMAL = 0
L1_COMPRESS_INJECTION = 1
L2_FEWER_ROUNDS = 2
L3_DOWNGRADE_MODEL = 3
L4_SKIP_OPTIONAL_AGENT = 4
L5_DEGRADED_VERDICT = 5

OPTIONAL_AGENTS: tuple[str, ...] = ("sentiment", "news")


class DegradationPolicy:
    """Maps ledger headroom onto a degradation level."""

    def __init__(self, config: LedgerConfig) -> None:
        self.config = config

    def evaluate(
        self,
        ledger: BudgetLedger,
        stage: str,
        *,
        remaining_calls: int | None = None,
        projected_remaining_tokens: int | None = None,
    ) -> int | None:
        """Return the level to apply now, or None when the current level stands.

        Two signals are supported:

        * ``projected_remaining_tokens`` — the run's remaining spend estimate. When
          supplied, the global level compares the remaining budget against that
          projection, so a run that will comfortably fit never degrades just
          because it is near the end.
        * ``remaining_calls`` — the calls this stage still has ahead. When
          supplied, the stage level is forward-looking too.

        Without either signal the policy falls back to fixed headroom fractions,
        which is all a caller can do when it cannot see the remaining plan.
        """
        total = self.config.limit_tokens
        remaining_global = ledger.remaining("global")
        remaining_stage = ledger.remaining(stage)
        next_estimate = ledger.estimate("", stage)

        level = L0_NORMAL

        if projected_remaining_tokens is not None:
            projected = max(1, projected_remaining_tokens)
            if remaining_global < projected:
                level = max(level, L1_COMPRESS_INJECTION)
            if remaining_global < 0.85 * projected:
                level = max(level, L2_FEWER_ROUNDS)
            if remaining_global < 0.70 * projected:
                level = max(level, L3_DOWNGRADE_MODEL)
            if remaining_global < 0.55 * projected:
                level = max(level, L4_SKIP_OPTIONAL_AGENT)
        else:
            if remaining_global < self.config.l4_threshold * total:
                level = max(level, L4_SKIP_OPTIONAL_AGENT)
            if remaining_global < self.config.l3_threshold * total:
                level = max(level, L3_DOWNGRADE_MODEL)

        if remaining_calls is None:
            if remaining_stage < next_estimate:
                level = max(level, L2_FEWER_ROUNDS)
            elif remaining_stage < 1.5 * next_estimate:
                level = max(level, L1_COMPRESS_INJECTION)
        else:
            projected_stage = max(1, remaining_calls) * next_estimate
            if remaining_stage < 0.6 * projected_stage:
                level = max(level, L2_FEWER_ROUNDS)
            elif remaining_stage < projected_stage:
                level = max(level, L1_COMPRESS_INJECTION)

        if remaining_global < next_estimate:
            level = max(level, L5_DEGRADED_VERDICT)

        return level if level > ledger.level else None

    # ------------------------------------------------------------- effects

    def debate_rounds(self, level: int, configured: int) -> int:
        """Debate rounds still allowed at this level (never below one)."""
        if level >= L2_FEWER_ROUNDS:
            return max(1, configured - 1)
        return configured

    def forced_tier(self, level: int, requested: str) -> str:
        """Model tier to use; a degraded run may only use the cheap tier."""
        if level >= L3_DOWNGRADE_MODEL:
            return "quick"
        return requested

    def skipped_agents(self, level: int) -> tuple[str, ...]:
        """Optional agents dropped at this level, in fixed order."""
        if level >= L4_SKIP_OPTIONAL_AGENT:
            return OPTIONAL_AGENTS
        return ()

    def pm_verdict(self, level: int) -> str:
        """Portfolio-manager latitude: ``any`` or ``hold_only``."""
        return "hold_only" if level >= L5_DEGRADED_VERDICT else "any"


__all__ = [
    "L0_NORMAL",
    "L1_COMPRESS_INJECTION",
    "L2_FEWER_ROUNDS",
    "L3_DOWNGRADE_MODEL",
    "L4_SKIP_OPTIONAL_AGENT",
    "L5_DEGRADED_VERDICT",
    "OPTIONAL_AGENTS",
    "DegradationPolicy",
]

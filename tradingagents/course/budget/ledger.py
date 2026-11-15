"""Metered budget ledger for one analysis run (FR-002 / FR-006).

Every mutation happens under a single lock, so "check the balance" and "charge
the reservation" are one atomic step; that is what prevents oversell when the
four analysts call the pool in parallel.

The clock and the id factory are injected, and estimates come from a table
supplied by the caller, so a fixed script always produces the same event
sequence (AC-7). No I/O and no model call happens inside the lock.
"""

from __future__ import annotations

import threading
import uuid
from collections.abc import Callable, Mapping
from datetime import UTC, datetime

from .contracts import (
    LEVELS,
    MODEL_TIERS,
    STAGES,
    BudgetDenied,
    BudgetEvent,
    ContractError,
    LedgerConfig,
    LevelRegression,
    Reservation,
    Settlement,
)


def _utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _allocate(config: LedgerConfig) -> dict[str, int]:
    """Split the token budget into per-stage integer shares.

    Rounding leftovers go to the protected stage so the shares always add up to
    exactly ``limit_tokens``.
    """
    budgets = {
        stage: int(config.limit_tokens * config.stage_quota.get(stage, 0.0))
        for stage in STAGES
    }
    remainder = config.limit_tokens - sum(budgets.values())
    if remainder:
        budgets[config.protected_stage] += remainder
    return budgets


class BudgetLedger:
    """Reserve-then-settle accounting for one run."""

    def __init__(
        self,
        config: LedgerConfig,
        *,
        clock: Callable[[], str] | None = None,
        id_factory: Callable[[], str] | None = None,
        stage_estimates: Mapping[tuple[str | None, str], int] | None = None,
    ) -> None:
        self.config = config
        self._clock = clock or _utc_now
        self._new_call_id = id_factory or (lambda: uuid.uuid4().hex)
        self._lock = threading.Lock()
        self._stage_budget = _allocate(config)
        self._estimates = dict(stage_estimates or {})
        self._reserved: dict[str, Reservation] = {}
        self._settled: dict[str, Settlement] = {}
        self._events: list[BudgetEvent] = []
        self._spent = 0
        self._outstanding = 0
        self._reservations = 0
        self._event_seq = 0
        self._level = 0
        self._state = "open"

    # ------------------------------------------------------------------ reads

    @property
    def level(self) -> int:
        return self._level

    @property
    def state(self) -> str:
        return self._state

    def remaining(self, scope: str = "global") -> int:
        with self._lock:
            if scope == "global":
                return self._remaining_global()
            if scope not in STAGES:
                raise ContractError(f"unknown scope: {scope!r}")
            return self._stage_budget[scope]

    def events(self) -> tuple[BudgetEvent, ...]:
        with self._lock:
            return tuple(self._events)

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            return {
                "limit_tokens": self.config.limit_tokens,
                "limit_calls": self.config.limit_calls,
                "spent": self._spent,
                "outstanding": self._outstanding,
                "remaining_global": self._remaining_global(),
                "reservations": self._reservations,
                "level": self._level,
                "state": self._state,
                "stage_budget": dict(self._stage_budget),
                "events": len(self._events),
            }

    def estimate(self, agent: str, stage: str) -> int:
        """Estimated token cost of the next call, from the fixed table."""
        base = self._estimates.get((agent, stage))
        if base is None:
            base = self._stage_estimate(stage)
        return max(self.config.estimate_floor, int(base * self.config.estimate_margin))

    # --------------------------------------------------------------- mutation

    def reserve(
        self,
        agent: str,
        stage: str,
        model_tier: str,
        call_id: str | None = None,
    ) -> Reservation:
        """Reserve budget for one call; raise BudgetDenied when it cannot be funded."""
        if stage not in STAGES:
            raise ContractError(f"unknown stage: {stage!r}")
        if model_tier not in MODEL_TIERS:
            raise ContractError(f"unknown model tier: {model_tier!r}")

        with self._lock:
            if self._state != "open":
                raise BudgetDenied("ledger_closed", self._remaining_global())
            if self._reservations >= self.config.limit_calls:
                raise BudgetDenied("call_limit", self._remaining_global())

            estimate = self.estimate(agent, stage)
            remaining = self._remaining_global()

            if remaining < estimate:
                self._emit(
                    "exhausted",
                    agent=agent,
                    stage=stage,
                    model_tier=model_tier,
                    estimate=estimate,
                    reason="global_exhausted",
                )
                self._state = "exhausted"
                raise BudgetDenied("global_exhausted", remaining)

            shortfall = estimate - self._stage_budget[stage]
            if shortfall > 0 and not self._borrow(stage, shortfall, agent, model_tier):
                self._emit(
                    "exhausted",
                    agent=agent,
                    stage=stage,
                    model_tier=model_tier,
                    estimate=estimate,
                    reason="stage_exhausted",
                )
                raise BudgetDenied("stage_exhausted", remaining)

            new_id = call_id or self._new_call_id()
            if new_id in self._reserved:
                raise ContractError(f"duplicate call_id: {new_id!r}")

            self._stage_budget[stage] -= estimate
            self._outstanding += estimate
            self._reservations += 1
            reservation = Reservation(
                call_id=new_id,
                agent=agent,
                stage=stage,
                model_tier=model_tier,
                estimated=estimate,
                remaining_global_after=self._remaining_global(),
                remaining_stage_after=self._stage_budget[stage],
            )
            self._reserved[new_id] = reservation
            self._emit(
                "reserve",
                agent=agent,
                stage=stage,
                model_tier=model_tier,
                estimate=estimate,
                reason="",
            )
            return reservation

    def settle(self, call_id: str, input_tokens: int, output_tokens: int) -> Settlement:
        """Settle a reservation with the actual usage; idempotent per call_id."""
        if input_tokens < 0 or output_tokens < 0:
            raise ContractError("token counts must be non-negative")

        with self._lock:
            settled = self._settled.get(call_id)
            if settled is not None:
                return settled

            reservation = self._reserved.pop(call_id, None)
            if reservation is None:
                raise ContractError(f"unknown call_id: {call_id!r}")

            actual = input_tokens + output_tokens
            refunded = max(0, reservation.estimated - actual)
            overrun = max(0, actual - reservation.estimated)

            self._outstanding -= reservation.estimated
            self._stage_budget[reservation.stage] += refunded
            self._spent += actual
            remaining = self._remaining_global()

            if remaining < 0:
                self._emit(
                    "over_budget",
                    agent=reservation.agent,
                    stage=reservation.stage,
                    model_tier=reservation.model_tier,
                    estimate=reservation.estimated,
                    actual=actual,
                    reason="settled_above_reservation",
                )
                self._state = "exhausted"

            settlement = Settlement(
                call_id=call_id,
                reserved=reservation.estimated,
                actual=actual,
                refunded=refunded,
                overrun=overrun,
                remaining_global=remaining,
                state=self._state,
            )
            self._settled[call_id] = settlement
            self._emit(
                "settle",
                agent=reservation.agent,
                stage=reservation.stage,
                model_tier=reservation.model_tier,
                estimate=reservation.estimated,
                actual=actual,
                reason="",
            )
            return settlement

    def release(self, call_id: str, reason: str = "released") -> None:
        """Return an unused reservation; releasing a settled call is a no-op."""
        with self._lock:
            if call_id in self._settled:
                return
            reservation = self._reserved.pop(call_id, None)
            if reservation is None:
                raise ContractError(f"unknown call_id: {call_id!r}")

            self._outstanding -= reservation.estimated
            self._stage_budget[reservation.stage] += reservation.estimated
            self._emit(
                "release",
                agent=reservation.agent,
                stage=reservation.stage,
                model_tier=reservation.model_tier,
                estimate=reservation.estimated,
                reason=reason,
            )

    def apply_level(self, level: int) -> None:
        """Raise the degradation level; lowering it is a violation (INV-006)."""
        if level not in LEVELS:
            raise ContractError(f"unknown level: {level!r}")

        with self._lock:
            if level < self._level:
                raise LevelRegression(f"level {level} < current {self._level}")
            if level > self._level:
                self._level = level
                self._emit("degraded", reason=f"level:{level}")

    # ---------------------------------------------------------------- helpers

    def _remaining_global(self) -> int:
        return self.config.limit_tokens - self._spent - self._outstanding

    def _stage_estimate(self, stage: str) -> int:
        for key in ((None, stage), ("", stage)):
            value = self._estimates.get(key)
            if value is not None:
                return int(value)
        return self.config.estimate_floor

    def _borrow(self, stage: str, need: int, agent: str, model_tier: str) -> bool:
        """Move quota from unspent stages; never touches the protected stage."""
        lenders = sorted(
            (
                other
                for other in STAGES
                if other != stage
                and other != self.config.protected_stage
                and self._stage_budget[other] > 0
            ),
            key=lambda other: (-self._stage_budget[other], other),
        )
        available = sum(self._stage_budget[other] for other in lenders)
        ceiling = int(self._remaining_global() * self.config.borrow_max_fraction)
        if need > min(available, ceiling):
            return False

        gathered = 0
        for lender in lenders:
            if gathered >= need:
                break
            take = min(self._stage_budget[lender], need - gathered)
            self._stage_budget[lender] -= take
            self._stage_budget[stage] += take
            gathered += take
            self._emit(
                "borrow",
                agent=agent,
                stage=stage,
                model_tier=model_tier,
                estimate=take,
                reason=f"borrow:{lender}->{stage}",
            )
        return gathered >= need

    def _emit(
        self,
        event_type: str,
        *,
        agent: str | None = None,
        stage: str | None = None,
        model_tier: str | None = None,
        estimate: int | None = None,
        actual: int | None = None,
        reason: str = "",
    ) -> None:
        self._event_seq += 1
        self._events.append(
            BudgetEvent(
                event_id=f"evt-{self._event_seq}",
                ts=self._clock(),
                type=event_type,
                agent=agent,
                stage=stage,
                model_tier=model_tier,
                estimate=estimate,
                actual=actual,
                remaining_global=self._remaining_global(),
                remaining_stage=self._stage_budget.get(stage) if stage else None,
                level=self._level,
                reason=reason,
            )
        )


__all__ = ["BudgetLedger"]

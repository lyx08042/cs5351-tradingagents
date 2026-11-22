"""Contracts for the FR-002 run-budget ledger.

Anchors: FR-002, FR-006, INV-002, INV-006. Every structure here is
JSON-serialisable and carries no behaviour beyond validation, so the ledger
logic stays testable without I/O, network access or a language model.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

STAGES: tuple[str, ...] = (
    "analyst",
    "debate",
    "research_manager",
    "trader",
    "risk_debate",
    "portfolio_manager",
)

MODEL_TIERS: tuple[str, ...] = ("quick", "deep")

RESERVE_STATES: tuple[str, ...] = ("reserved", "settled", "released")

LEDGER_STATES: tuple[str, ...] = ("open", "exhausted", "closed")

EVENT_TYPES: tuple[str, ...] = (
    "reserve",
    "settle",
    "release",
    "borrow",
    "degraded",
    "compacted",
    "over_budget",
    "exhausted",
)

LEVELS: tuple[int, ...] = (0, 1, 2, 3, 4, 5)

DEFAULT_STAGE_QUOTA: Mapping[str, float] = {
    "analyst": 0.40,
    "debate": 0.25,
    "research_manager": 0.08,
    "trader": 0.07,
    "risk_debate": 0.15,
    "portfolio_manager": 0.05,
}


class ContractError(ValueError):
    """Raised when a contract value is structurally invalid (fail-closed)."""


class BudgetDenied(Exception):
    """Raised when a reservation cannot be funded (fail-closed)."""

    def __init__(self, reason: str, remaining_global: int = 0) -> None:
        super().__init__(reason)
        self.reason = reason
        self.remaining_global = remaining_global


class LevelRegression(Exception):
    """Raised when a caller tries to lower the degradation level (INV-006)."""


@dataclass(frozen=True)
class LedgerConfig:
    """Static configuration of one run's budget.

    The defaults mirror `tasks/plans/B/FR-002-scope.md`; the thresholds are
    provisional and are calibrated later against the evaluation set.
    """

    limit_tokens: int = 240_000
    limit_calls: int = 60
    stage_quota: Mapping[str, float] = field(
        default_factory=lambda: dict(DEFAULT_STAGE_QUOTA)
    )
    protected_stage: str = "portfolio_manager"
    borrow_max_fraction: float = 0.30
    estimate_margin: float = 1.30
    estimate_floor: int = 800
    l3_threshold: float = 0.15
    l4_threshold: float = 0.10
    context_cap: int = 16_000
    compact_threshold: int = 12_000
    compact_target: int = 8_000

    def __post_init__(self) -> None:
        validate_config(self)


def validate_config(config: LedgerConfig) -> None:
    """Validate a configuration; raise ContractError on the first violation."""
    if config.limit_tokens <= 0:
        raise ContractError("limit_tokens must be positive")
    if config.limit_calls <= 0:
        raise ContractError("limit_calls must be positive")
    if config.protected_stage not in STAGES:
        raise ContractError(f"unknown protected stage: {config.protected_stage!r}")

    unknown = sorted(set(config.stage_quota) - set(STAGES))
    if unknown:
        raise ContractError(f"stage_quota has unknown stages: {unknown}")
    negative = sorted(stage for stage, share in config.stage_quota.items() if share < 0)
    if negative:
        raise ContractError(f"stage_quota has negative shares: {negative}")
    total = sum(config.stage_quota.values())
    if abs(total - 1.0) > 1e-9:
        raise ContractError(f"stage_quota must sum to 1.0, got {total!r}")

    if not 0.0 < config.borrow_max_fraction < 1.0:
        raise ContractError("borrow_max_fraction must be within (0, 1)")
    if config.estimate_margin < 1.0:
        raise ContractError("estimate_margin must be at least 1.0")
    if config.estimate_floor <= 0:
        raise ContractError("estimate_floor must be positive")
    if not 0.0 < config.l4_threshold < config.l3_threshold < 1.0:
        raise ContractError("thresholds must satisfy 0 < l4_threshold < l3_threshold < 1")
    if not 0 < config.compact_target < config.compact_threshold <= config.context_cap:
        raise ContractError(
            "context limits must satisfy compact_target < compact_threshold <= context_cap"
        )


@dataclass(frozen=True)
class Reservation:
    """A successful budget reservation for one prospective model call."""

    call_id: str
    agent: str
    stage: str
    model_tier: str
    estimated: int
    remaining_global_after: int
    remaining_stage_after: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "call_id": self.call_id,
            "agent": self.agent,
            "stage": self.stage,
            "model_tier": self.model_tier,
            "estimated": self.estimated,
            "remaining_global_after": self.remaining_global_after,
            "remaining_stage_after": self.remaining_stage_after,
        }


@dataclass(frozen=True)
class Settlement:
    """The result of settling one reservation against actual token usage."""

    call_id: str
    reserved: int
    actual: int
    refunded: int
    overrun: int
    remaining_global: int
    state: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "call_id": self.call_id,
            "reserved": self.reserved,
            "actual": self.actual,
            "refunded": self.refunded,
            "overrun": self.overrun,
            "remaining_global": self.remaining_global,
            "state": self.state,
        }


@dataclass(frozen=True)
class BudgetEvent:
    """One auditable ledger event; E persists these, B only emits them."""

    event_id: str
    ts: str
    type: str
    agent: str | None = None
    stage: str | None = None
    model_tier: str | None = None
    estimate: int | None = None
    actual: int | None = None
    remaining_global: int = 0
    remaining_stage: int | None = None
    level: int = 0
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "ts": self.ts,
            "type": self.type,
            "agent": self.agent,
            "stage": self.stage,
            "model_tier": self.model_tier,
            "estimate": self.estimate,
            "actual": self.actual,
            "remaining_global": self.remaining_global,
            "remaining_stage": self.remaining_stage,
            "level": self.level,
            "reason": self.reason,
        }


__all__ = [
    "DEFAULT_STAGE_QUOTA",
    "EVENT_TYPES",
    "LEDGER_STATES",
    "LEVELS",
    "MODEL_TIERS",
    "RESERVE_STATES",
    "STAGES",
    "BudgetDenied",
    "BudgetEvent",
    "ContractError",
    "LedgerConfig",
    "LevelRegression",
    "Reservation",
    "Settlement",
    "validate_config",
]

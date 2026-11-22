"""Run-budget ledger for role B (FR-002 / FR-006).

Public surface: the ledger, its configuration, the records it returns and the
exceptions it raises. Nothing here performs I/O or calls a model.
"""

from .context import (
    assemble_context,
    assert_manifest,
    budget_for_section,
    compact,
    reinject,
    should_compact,
)
from .contracts import (
    DEFAULT_STAGE_QUOTA,
    EVENT_TYPES,
    LEDGER_STATES,
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
    validate_config,
)
from .ledger import BudgetLedger
from .policy import DegradationPolicy

__all__ = [
    "DEFAULT_STAGE_QUOTA",
    "EVENT_TYPES",
    "LEDGER_STATES",
    "LEVELS",
    "MODEL_TIERS",
    "STAGES",
    "BudgetDenied",
    "BudgetEvent",
    "BudgetLedger",
    "ContractError",
    "DegradationPolicy",
    "LedgerConfig",
    "LevelRegression",
    "Reservation",
    "Settlement",
    "assemble_context",
    "assert_manifest",
    "budget_for_section",
    "compact",
    "reinject",
    "should_compact",
    "validate_config",
]

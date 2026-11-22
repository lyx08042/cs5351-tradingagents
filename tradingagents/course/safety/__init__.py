"""Deterministic simulation safety (FR-003, INV-003, SEC-001, NFR-003).

Public surface:

- ``SimulationProposal``: fixed candidate contract fields.
- ``HoldingsSnapshot`` / ``RuleSet`` / ``SafetyContext``: independent trusted
  inputs supplied by the caller, never by the candidate.
- ``validate_proposal``: pure, deterministic accept/reject gate.
- ``ReasonCode`` / ``SafetyVerdict``: stable machine-readable outcomes.
"""
from .models import (
    Action,
    HoldingsSnapshot,
    ProposalStatus,
    ReasonCode,
    RuleSet,
    SafetyContext,
    SafetyVerdict,
    SimulationProposal,
)
from .validator import validate_proposal

__all__ = [
    "Action",
    "HoldingsSnapshot",
    "ProposalStatus",
    "ReasonCode",
    "RuleSet",
    "SafetyContext",
    "SafetyVerdict",
    "SimulationProposal",
    "validate_proposal",
]

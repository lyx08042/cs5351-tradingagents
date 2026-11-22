"""Context budget, compaction and constraint re-injection (FR-002, course D2.2).

Course requirement D2.2 asks for a token-budget cap, a compaction threshold
and a policy for re-injecting critical constraints after compaction. This
module implements the assembly pipeline: ``budget -> compact -> reinject``.

The four re-injected blocks carry fixed sentinel prefixes, so the check is a
substring test rather than a model judgement (AC-5).
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence

from .contracts import ContractError

SECTIONS: tuple[str, ...] = (
    "identity",
    "constraints",
    "evidence",
    "conversation",
    "state",
    "task",
)

SECTION_WEIGHTS: dict[str, float] = {
    "identity": 0.03,
    "constraints": 0.07,
    "evidence": 0.25,
    "conversation": 0.40,
    "state": 0.10,
    "task": 0.15,
}

SAFETY_MARKER = "[SAFETY]"
IDENTITY_MARKER = "[IDENTITY]"
LEVEL_MARKER = "[LEVEL]"
BUDGET_MARKER = "[BUDGET]"

REQUIRED_MARKERS: tuple[str, ...] = (
    SAFETY_MARKER,
    IDENTITY_MARKER,
    LEVEL_MARKER,
    BUDGET_MARKER,
)

SAFETY_BLOCK = (
    "[SAFETY] long-only; no real broker; never exceed available cash or holdings"
)


def count_tokens(text: str) -> int:
    """Deterministic token proxy used for budgeting (whitespace tokens)."""
    return len(text.split())


def budget_for_section(section: str, available: int) -> int:
    """Token allowance for one context section out of ``available``."""
    if section not in SECTION_WEIGHTS:
        raise ContractError(f"unknown context section: {section!r}")
    if available < 0:
        raise ContractError("available tokens must be non-negative")
    return int(available * SECTION_WEIGHTS[section])


def should_compact(assembled_tokens: int, compact_threshold: int) -> bool:
    """True when the assembled context must be compacted before the call."""
    return assembled_tokens > compact_threshold


def compact(
    messages: Sequence[str],
    target_tokens: int,
    *,
    counter: Callable[[str], int] = count_tokens,
) -> list[str]:
    """Drop the oldest messages until the context fits ``target_tokens``.

    The newest messages are kept because they carry the current turn; the
    number of dropped messages is recorded in a single deterministic marker.
    """
    if target_tokens <= 0:
        raise ContractError("target_tokens must be positive")

    kept: list[str] = []
    total = 0
    for message in reversed(messages):
        size = counter(message)
        if kept and total + size > target_tokens:
            break
        kept.append(message)
        total += size

    kept.reverse()
    omitted = len(messages) - len(kept)
    if omitted:
        kept.insert(0, f"[COMPACTED] {omitted} earlier messages omitted")
    return kept


def reinject(
    messages: Sequence[str],
    *,
    identity: str,
    level: int,
    remaining_fraction: float,
) -> list[str]:
    """Prepend the four constraint blocks that must survive compaction."""
    if not 0.0 <= remaining_fraction <= 1.0:
        raise ContractError("remaining_fraction must be within [0, 1]")

    blocks = [
        SAFETY_BLOCK,
        f"{IDENTITY_MARKER} {identity}",
        f"{LEVEL_MARKER} degradation level L{level}",
        f"{BUDGET_MARKER} remaining budget below {remaining_fraction:.0%}",
    ]
    return blocks + list(messages)


def assert_manifest(messages: Iterable[str]) -> None:
    """Fail closed when a mandatory constraint block is missing (AC-5)."""
    joined = "\n".join(messages)
    missing = [marker for marker in REQUIRED_MARKERS if marker not in joined]
    if missing:
        raise ContractError(f"assembled context is missing: {', '.join(missing)}")


def assemble_context(
    messages: Sequence[str],
    *,
    identity: str,
    level: int,
    remaining_fraction: float,
    compact_threshold: int,
    compact_target: int,
    counter: Callable[[str], int] = count_tokens,
) -> list[str]:
    """Run the full pipeline: budget -> compact -> reinject -> verify."""
    if compact_target >= compact_threshold:
        raise ContractError("compact_target must be smaller than compact_threshold")

    assembled = list(messages)
    total = sum(counter(message) for message in assembled)
    if should_compact(total, compact_threshold):
        assembled = compact(assembled, compact_target, counter=counter)

    assembled = reinject(
        assembled,
        identity=identity,
        level=level,
        remaining_fraction=remaining_fraction,
    )
    assert_manifest(assembled)
    return assembled


__all__ = [
    "BUDGET_MARKER",
    "IDENTITY_MARKER",
    "LEVEL_MARKER",
    "REQUIRED_MARKERS",
    "SAFETY_BLOCK",
    "SAFETY_MARKER",
    "SECTIONS",
    "SECTION_WEIGHTS",
    "assemble_context",
    "assert_manifest",
    "budget_for_section",
    "compact",
    "count_tokens",
    "reinject",
    "should_compact",
]

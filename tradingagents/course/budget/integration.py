"""Budget enforcement at the model-client boundary (FR-002 / FR-006, M4).

The graph builds exactly two chat models and every agent composes
``(prompt | llm).invoke(...)``, so wrapping those two objects is the narrowest
place that covers the whole run without editing ten agent modules.

The proxy is transparent: it forwards ``invoke``, ``bind_tools`` and
``with_structured_output`` so LangChain composition keeps working, and it only
adds accounting. When the ledger refuses a call the proxy raises
``BudgetExhausted`` instead of returning an empty answer, so a degraded run can
never be mistaken for a normal one.
"""

from __future__ import annotations

from typing import Any

from .contracts import BudgetDenied
from .ledger import BudgetLedger

# Ordered: the first matching fragment wins, so "portfolio" is checked before
# "risk" and "research manager" before "researcher".
NODE_STAGE_RULES: tuple[tuple[str, str], ...] = (
    ("portfolio", "portfolio_manager"),
    ("risk", "risk_debate"),
    ("trader", "trader"),
    ("research manager", "research_manager"),
    ("researcher", "debate"),
    ("analyst", "analyst"),
)

DEFAULT_STAGE = "analyst"


class BudgetExhausted(RuntimeError):
    """Raised when a call cannot be funded; the caller maps it to L5."""

    def __init__(self, reason: str, remaining_global: int) -> None:
        super().__init__(f"budget denied: {reason}")
        self.reason = reason
        self.remaining_global = remaining_global


def stage_for_node(node: str | None) -> str:
    """Map a LangGraph node name onto a ledger stage (best effort)."""
    if not node:
        return DEFAULT_STAGE
    lowered = node.lower()
    for needle, stage in NODE_STAGE_RULES:
        if needle in lowered:
            return stage
    return DEFAULT_STAGE


def _extract_usage(response: Any) -> tuple[int, int] | None:
    """Read token usage from a response; None when the provider reports none."""
    usage = getattr(response, "usage_metadata", None)
    if isinstance(usage, dict):
        prompt = usage.get("input_tokens")
        completion = usage.get("output_tokens")
        if isinstance(prompt, int) and isinstance(completion, int):
            return prompt, completion

    metadata = getattr(response, "response_metadata", None)
    if isinstance(metadata, dict):
        token_usage = metadata.get("token_usage") or metadata.get("usage")
        if isinstance(token_usage, dict):
            prompt = token_usage.get("prompt_tokens")
            completion = token_usage.get("completion_tokens")
            if isinstance(prompt, int) and isinstance(completion, int):
                return prompt, completion
    return None


class BudgetedChatModel:
    """Transparent proxy that reserves before a call and settles afterwards."""

    def __init__(
        self,
        inner: Any,
        ledger: BudgetLedger,
        *,
        model_tier: str,
        agent: str = "graph",
        stage: str | None = None,
    ) -> None:
        self._inner = inner
        self._ledger = ledger
        self._model_tier = model_tier
        self._agent = agent
        self._stage = stage

    # ------------------------------------------------------------ internals

    def _resolve_stage(self, config: Any) -> str:
        if self._stage:
            return self._stage
        metadata = (config or {}).get("metadata") or {}
        return stage_for_node(metadata.get("langgraph_node"))

    # ----------------------------------------------------------- public API

    def invoke(self, input: Any, config: Any = None, **kwargs: Any) -> Any:
        stage = self._resolve_stage(config)
        try:
            reservation = self._ledger.reserve(self._agent, stage, self._model_tier)
        except BudgetDenied as exc:
            raise BudgetExhausted(exc.reason, exc.remaining_global) from exc

        try:
            response = self._inner.invoke(input, config=config, **kwargs)
        except Exception:
            self._ledger.release(reservation.call_id, reason="call_failed")
            raise

        usage = _extract_usage(response)
        if usage is None:
            # Conservative: an unreported usage consumes the whole reservation,
            # so a provider that hides its counters cannot defeat the budget.
            self._ledger.settle(reservation.call_id, reservation.estimated, 0)
        else:
            self._ledger.settle(reservation.call_id, usage[0], usage[1])
        return response

    def __call__(self, input: Any, config: Any = None, **kwargs: Any) -> Any:
        return self.invoke(input, config=config, **kwargs)

    def bind_tools(self, tools: Any, **kwargs: Any) -> BudgetedChatModel:
        return self._rewrap(self._inner.bind_tools(tools, **kwargs))

    def with_structured_output(self, schema: Any, **kwargs: Any) -> BudgetedChatModel:
        return self._rewrap(self._inner.with_structured_output(schema, **kwargs))

    def _rewrap(self, inner: Any) -> BudgetedChatModel:
        return BudgetedChatModel(
            inner,
            self._ledger,
            model_tier=self._model_tier,
            agent=self._agent,
            stage=self._stage,
        )

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)


def wrap_models(
    quick: Any,
    deep: Any,
    ledger: BudgetLedger,
    *,
    agent: str = "graph",
) -> tuple[BudgetedChatModel, BudgetedChatModel]:
    """Wrap the quick and deep tier models used by the graph."""
    return (
        BudgetedChatModel(quick, ledger, model_tier="quick", agent=agent),
        BudgetedChatModel(deep, ledger, model_tier="deep", agent=agent),
    )


__all__ = [
    "DEFAULT_STAGE",
    "NODE_STAGE_RULES",
    "BudgetExhausted",
    "BudgetedChatModel",
    "stage_for_node",
    "wrap_models",
]

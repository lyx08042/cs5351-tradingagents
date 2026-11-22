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

import contextvars
from collections.abc import Callable
from contextlib import contextmanager, suppress
from typing import Any

from .contracts import STAGES, BudgetDenied, ContractError
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


class BudgetOverrun(RuntimeError):
    """Raised when one call alone exhausts the pool.

    The response is attached rather than discarded: the caller decides whether to
    surface a degraded verdict, but it cannot do that by accident, because the
    overrun never returns silently as if the call had been paid for.
    """

    def __init__(self, settlement: Any, response: Any) -> None:
        super().__init__(
            f"single call overran the budget by {settlement.overrun} tokens"
        )
        self.settlement = settlement
        self.response = response


_CURRENT_STAGE: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "budget_current_stage", default=None
)


@contextmanager
def budget_stage(stage: str):
    """Attribute calls made inside the block to ``stage``.

    The agents call ``llm.invoke(prompt)`` without a config, so the node name is
    not always available. A caller that knows which stage it is running (an
    orchestrator, a node wrapper, a test) sets it here instead of relying on
    config metadata.
    """
    token = _CURRENT_STAGE.set(stage)
    try:
        yield stage
    finally:
        _CURRENT_STAGE.reset(token)


def stage_for_node(node: str | None) -> str:
    """Map a LangGraph node name onto a ledger stage (best effort)."""
    if not node:
        return DEFAULT_STAGE
    lowered = node.lower()
    # A caller may pass a canonical stage name (budget_stage("debate")) or a
    # LangGraph node name ("Bull Researcher"); accept both.
    if lowered in STAGES:
        return lowered
    for needle, stage in NODE_STAGE_RULES:
        if needle in lowered:
            return stage
    return DEFAULT_STAGE


def _extract_usage(response: Any) -> tuple[int, int] | None:
    """Read token usage from a response; None when the provider reports none."""
    # with_structured_output(..., include_raw=True) returns {"parsed": ..., "raw": ...}
    if isinstance(response, dict) and "raw" in response:
        return _extract_usage(response["raw"])

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
        stage_resolver: Callable[[], str | None] | None = None,
    ) -> None:
        self._inner = inner
        self._ledger = ledger
        self._model_tier = model_tier
        self._agent = agent
        self._stage = stage
        self._stage_resolver = stage_resolver

    # ------------------------------------------------------------ internals

    def _resolve_stage(self, config: Any) -> str:
        """Explicit stage wins, then a resolver, then the context, then the node name."""
        if self._stage:
            return self._stage
        if self._stage_resolver is not None:
            resolved = self._stage_resolver()
            if resolved:
                return stage_for_node(resolved)
        contextual = _CURRENT_STAGE.get()
        if contextual:
            return stage_for_node(contextual)
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
        tokens_in, tokens_out = (
            (reservation.estimated, 0) if usage is None else usage
        )
        try:
            settlement = self._ledger.settle(reservation.call_id, tokens_in, tokens_out)
        except ContractError:
            # A provider reporting nonsense usage must not leak the reservation.
            with suppress(ContractError):
                self._ledger.release(reservation.call_id, reason="invalid_usage")
            raise

        if settlement.overrun > 0 and settlement.state == "exhausted":
            raise BudgetOverrun(settlement, response)
        return response

    def __call__(self, input: Any, config: Any = None, **kwargs: Any) -> Any:
        return self.invoke(input, config=config, **kwargs)

    def bind_tools(self, tools: Any, **kwargs: Any) -> BudgetedChatModel:
        return self._rewrap(self._inner.bind_tools(tools, **kwargs))

    def with_structured_output(self, schema: Any, **kwargs: Any) -> BudgetedChatModel:
        return self._rewrap(self._inner.with_structured_output(schema, **kwargs))

    def with_stage(self, stage: str) -> BudgetedChatModel:
        """Return a proxy that always charges to ``stage``."""
        return self._rewrap(self._inner, stage=stage)

    def _rewrap(self, inner: Any, *, stage: str | None = None) -> BudgetedChatModel:
        return BudgetedChatModel(
            inner,
            self._ledger,
            model_tier=self._model_tier,
            agent=self._agent,
            stage=stage if stage is not None else self._stage,
            stage_resolver=self._stage_resolver,
        )

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)


def wrap_models(
    quick: Any,
    deep: Any,
    ledger: BudgetLedger,
    *,
    agent: str = "graph",
    stage_resolver: Callable[[], str | None] | None = None,
) -> tuple[BudgetedChatModel, BudgetedChatModel]:
    """Wrap the quick and deep tier models used by the graph."""
    return (
        BudgetedChatModel(
            quick, ledger, model_tier="quick", agent=agent, stage_resolver=stage_resolver
        ),
        BudgetedChatModel(
            deep, ledger, model_tier="deep", agent=agent, stage_resolver=stage_resolver
        ),
    )


__all__ = [
    "DEFAULT_STAGE",
    "NODE_STAGE_RULES",
    "BudgetExhausted",
    "BudgetOverrun",
    "BudgetedChatModel",
    "budget_stage",
    "stage_for_node",
    "wrap_models",
]

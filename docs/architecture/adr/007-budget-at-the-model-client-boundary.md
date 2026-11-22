# ADR-007 — Enforce the run budget at the model-client boundary

- Status: Accepted (role B), pending non-author review
- Date: 2026-11-19
- Requirements: FR-002, FR-006, INV-002, INV-006
- Supersedes: none
- Numbering: 007 (was 002, then 005; renumbered again so A's ADR-005 stays unique)
- Related: ADR-001 (course extension), `tasks/plans/B/FR-002-scope.md`

## Context

A run of the trading graph makes 19 model calls and consumes roughly 228,275 tokens
(`docs/baseline.md`). The upstream framework has no notion of a budget: each agent calls the model as often
as its own logic decides, debate rounds are fixed by configuration, and the four analysts run in parallel
against the same unreserved resource.

FR-002 requires a metered ledger (reserve before a call, settle after it, refuse past the cap). FR-006
requires a degradation ladder instead of an abort. Course requirement D2.2 additionally asks for a token
budget cap, a compaction threshold and a policy for re-injecting critical constraints after compaction.

The architectural question is therefore not *what* to enforce but *where* to intercept. Three properties
constrain the answer:

1. Coverage must be complete, including agents that use structured output.
2. The interception point must be narrow, because the agent modules are shared code and the repository
   treats them as a frozen baseline.
3. The mechanism must be testable without a provider.

## Decision

Enforce the budget at the **model-client boundary**: wrap the two chat models the graph constructs and let
every call pass through a proxy that reserves, delegates, and settles.

The graph builds exactly two models:

```python
self.deep_thinking_llm = create_tier_client(self.config, "deep").get_llm()
self.quick_thinking_llm = create_tier_client(self.config, "quick").get_llm()
```

and every node composes `(prompt | llm).invoke(...)`. Wrapping those two objects therefore covers the whole
pipeline with a fourteen-line, opt-in change in `tradingagents/graph/trading_graph.py`; when no ledger is
supplied the behaviour is byte-for-byte the baseline.

The proxy forwards `bind_tools` and `with_structured_output`. The second one matters: the research manager,
the trader and the portfolio manager produce structured output, and a proxy that only forwarded `invoke`
would leave the three most expensive agents entirely unmetered.

The stage a call belongs to is derived from the LangGraph node name carried in
`config["metadata"]["langgraph_node"]`, with an ordered mapping (`portfolio` before `risk`, `research
manager` before `researcher`). A caller that supplies no metadata is charged to a default stage rather than
being exempted.

## Alternatives considered

**A. Accounting inside each agent.** Each of the ten agent modules calls `reserve`/`settle` around its own
model call. Rejected: it needs ten edits to frozen code, it is easy to miss a new agent, and every
structured-output path needs its own hand-written accounting. Coverage would be a property of discipline
rather than of structure.

**B. Accounting in the thin orchestrator.** The orchestrator sees whole stages, not individual calls, so it
can bound a stage but cannot reserve per call without cooperation from the agents. It also cannot see calls
made inside tool loops, which is where a large share of the tokens goes. Rejected as the *enforcement*
point; it remains the right place to decide *which* stage runs next, which is why degradation below is
expressed as stage-level levels.

**C. Provider-side quotas.** Delegating the cap to the model provider. Rejected: it is not enforceable in
this environment, it cannot express the six-stage allocation, and a provider cap fails the whole run rather
than degrading it.

**D. Wrapping at the graph node level (LangGraph middleware).** Rejected for the same coverage reason as A:
a node may make several calls, and the reserve/settle bracket would then cover a group of calls rather than
one.

## Consequences

Positive:

- One construction site covers every agent, including tool-bound and structured-output calls.
- The mechanism is testable offline: the tests drive a fake model and assert the ledger, not a provider.
- The baseline is untouched when no ledger is passed, so the upstream regression suite keeps its meaning.

Negative and accepted:

- The proxy is transparent by delegation (`__getattr__`), so an attribute it does not override returns the
  inner model and would escape accounting. This is a known, documented hole rather than a silent one.
- A refusal currently surfaces as `BudgetExhausted`. Turning that into an L5 "degraded verdict" written by
  the portfolio manager requires the shared orchestrator and is a separate coordination change.
- The mechanism meters the calls that are made; it cannot stop an agent from *wanting* to make more calls.
  Bounding that is the job of the stage quotas and the ladder, not of the proxy.

## When to reopen

- The graph stops constructing models in one place, or a second construction path appears.
- A component calls a model through an interface the proxy does not override (for example a provider SDK
  used directly).
- The orchestrator gains per-call visibility, which would make alternative B viable and cheaper to reason
  about.
- A per-call budget below the stage granularity becomes a requirement.

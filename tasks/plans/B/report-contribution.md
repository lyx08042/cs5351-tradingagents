# Report Contribution — Role B (FR-002 / FR-006)

> Draft for the team report. The leader merges the relevant parts into `Report.md`.
> Language: English (course language). Member name, student id and the personal reflection are
> placeholders the member must fill in; nothing here invents an identity or a result.

## 1. Problem

The baseline run analyses one ticker in 19 model calls, consuming 228,275 tokens in 150.61 s
(`docs/baseline.md`). The framework has no notion of a budget: every agent calls the model as often as
its own logic decides, debate rounds are fixed by configuration, and the four analysts run in parallel
against the same unreserved resource. There is therefore no way to bound the cost of a run, no record of
where the tokens went, and no defined behaviour when a cap is reached — the run either finishes or fails.

## 2. Design

The budget is enforced at the model-client boundary rather than inside each agent, because the graph
constructs exactly two chat models and every node composes `(prompt | llm).invoke(...)`. Wrapping those
two objects covers the whole pipeline with a five-line, opt-in change and leaves the upstream behaviour
untouched when no ledger is supplied.

Four components:

- **Ledger** — reserve before the call, settle after it, idempotent per `call_id`, one lock so the check
  and the charge are a single atomic step.
- **Allocation** — six stage quotas over a global pool; quotas are soft and borrowable, except the
  portfolio manager's share, which is reserved for the final decision.
- **Degradation policy** — L0–L5, monotonic, evaluated against the *projected remaining spend* so that a
  run which fits never degrades merely because it is near its end.
- **Context assembly** — section budget, compaction above a threshold, and mandatory re-injection of the
  four critical constraint blocks after compaction, verified by a substring check rather than a model.

## 3. Implementation

`tradingagents/course/budget/` (contracts, ledger, policy, context, integration, replay) with 48 offline
tests. The proxy forwards `bind_tools` and `with_structured_output`, because the research manager, the
trader and the portfolio manager use structured output and would otherwise escape accounting. A provider
that reports no usage consumes its whole reservation, so a hidden counter cannot defeat the cap.

## 4. Evaluation (deterministic replay — not a live measurement)

Method: replay the recorded baseline trace under five caps. The aggregates are real; the per-call split is
synthetic because the original run did not record per-call usage. No model is called, no key is used.

| Cap (tokens) | Calls | Tokens | Δ | Level | Skipped |
|---|---|---|---|---|---|
| baseline | 19 | 228,275 | — | L0 | 0 |
| 240,000 | 19 | 228,275 | 0.0% | L0 | 0 |
| 200,000 | 19 | 149,519 | −34.5% | L1 | 0 |
| 180,000 | 17 | 130,827 | −42.7% | L2 | 2 |
| 150,000 | 17 | 130,827 | −42.7% | L3 | 2 |
| 120,000 | 13 | 104,251 | −54.3% | L4 | 6 |

Findings: (i) a cap at or above the baseline leaves the run untouched, so the controller does not degrade
healthy runs; (ii) compression alone buys 34.5% with every call still executed, which makes it the cheapest
lever; (iii) L3 downgrades the model tier and therefore changes price per token, not token volume — the
150,000 row matches the 180,000 row, and the report must not claim a token saving from L3.

Limits: decision quality was not measured, so `NFR-002` remains inconclusive; wall-clock time is not
modelled; the per-call split is synthetic. A live comparison is scripted in `test/live/eval_budget.py` and
can be run by any member with a provider key.

## 5. What human oversight caught

The first policy version compared the remaining budget against fixed fractions of the total. The replay
showed a 240,000-token cap (above the 228,275 baseline) degrading the run to L1 — obviously wrong, and
invisible in unit tests that only exercised one stage. The fix compares the remaining budget against the
projected remaining spend, and the regression is now pinned by `test_a_generous_budget_changes_nothing`.

## 6. Personal reflection (300–500 words) — TO BE WRITTEN BY THE MEMBER

> Placeholder. Replace with your own words; do not submit this text unchanged.
> Prompts to answer: what you expected the budget work to be, what surprised you, where you had to
> stop the agent, what you would do differently, and what you now understand about cost as an
> architectural constraint rather than a number.

## 7. Demo material

- Screen 1: the replay table above (baseline vs four caps).
- Screen 2: `pytest test/offline/test_budget*.py -q` → 48 passed.
- Screen 3: the ledger event log for one tight cap, showing the level transitions with reasons.

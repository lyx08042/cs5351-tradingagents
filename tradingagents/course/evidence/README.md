# Evidence leaf (FR-001 / INV-001 / ADR-005)

Models claims and evidence-id references; the trusted evidence index is built only
from collector-supplied data for one explicit run. The M2 leaf is standalone; M3
adds an opt-in adapter (`integration.py` plus
`TradingAgentsGraph.propagate_with_evidence`) while the default `propagate` path and
its outputs stay unchanged.

## Contracts

- `Fact(subject, metric, value | relation, unit, period)` — one canonical fact.
  `value` is a typed scalar (`CanonicalValue`) and compares exactly by type, so
  `True` never matches `1` and `1` never matches `1.0`.
- `EvidenceUnit` — trusted evidence: id, run id, `source` (`tool`/`report`),
  `content_ref`, `status` (`available`/`unavailable`/`unknown`), `published_at`,
  `available_as_of`, `fact`, `freshness_policy`. Both provenance dates are
  mandatory and must be strict `YYYY-MM-DD`; `fact.period` is optional but, when
  present, is checked against the `as_of` cutoff.
- `EvidenceRegistry` — immutable, run-scoped index built from collector records,
  created only via `EvidenceRegistry.build(...)` or `from_dict(...)`. The collector
  may pass `EvidenceUnit` objects or plain mappings; any other batch item fails closed
  with `malformed`, and `from_dict` trims replay quarantine IDs. It rejects malformed,
  foreign, conflicting and non-admissible references.
- `Claim` — model-supplied text, optional structured fact, evidence-id refs only.
- `ClaimVerdict` — `accept_factual` / `hypothesis` / `abstain` with stable top-level
  reasons and a `rejected_refs` audit.

## Dates and freshness

- `as_of`, `published_at`, and `available_as_of` must be canonical `YYYY-MM-DD`;
  padded strings are rejected. Both provenance dates are mandatory and are never
  filled from the cutoff.
- `published_at <= available_as_of <= as_of`. A present future date (including a
  future `fact.period`) is `future_leakage`; `available_as_of < published_at` is
  `invalid_date` even with no age limit; a missing date is `missing_date`; a
  non-canonical date is `invalid_date`.
- Freshness uses `published_at` and is inclusive: `(as_of - published_at).days <=
  max_age_days`, so `0` accepts same-day evidence and a fresh recapture cannot reset
  age. `None` means no age bound beyond the cutoff checks.

## Claims

- English directional verbs stay historical by default; they are predictions only in
  modal/future contexts (e.g., "will surge", "may surge", "is going to exceed",
  "is likely to surge", "to plunge"), plus temporal markers such as "tomorrow".
  Chinese target/forecast markers (e.g., 目标价, 即将, 大概率, 可能上涨, 涨停) are
  hypotheses even with a valid structured fact and reference.
- A factual claim needs a structured fact that matches an admitted evidence unit
  on subject, metric, value-or-relation, unit and period. An evidence id alone, or
  free/mixed prose, can never yield `accept_factual`. An explicitly declared factual
  claim with no structured fact abstains with `no_structured_fact`; no declaration or
  an explicit `unknown` without a fact is `unclassified`.
- Acceptance emits only the trusted, normalized evidence fact as `projection`.
  `rejected_refs` records every evaluated reference that failed admission or exact
  support, in input order, as `[{"evidence_id": ..., "reasons": [...]}]`; one valid
  matching reference still yields `accept_factual`.

## Offline demo

```bash
python -m tradingagents.course.evidence --demo
```

Prints deterministic JSON for EVAL-008 (accepted historical fact), EVAL-009
(future evidence rejected) and EVAL-006 (prediction hypothesis).

## M3 debate integration (opt-in)

- **Accepted envelope.** `evidence_context` is a JSON snapshot with `as_of`, a
  serialized `EvidenceRegistry` (`registry`), a serialized `FreshnessPolicy`
  (`policy`), and an optional `data_admission_decision`. `as_of`, `registry.as_of`
  and the graph `trade_date` must be the same canonical `YYYY-MM-DD`. Unknown
  fields, malformed dates, an invalid registry or policy, or a malformed decision
  fail closed before any run state or provider call.
- **D statuses and non-proceed gate.** Evidence units keep the D statuses
  `available` / `unavailable` / `unknown`; only `available` units that the registry
  admits enter the prompt catalog. Future, stale, unavailable, unknown and
  missing-date units stay in the registry for audit but are omitted from the prompt.
  When `data_admission_decision` is present, only the exact string `"proceed"` allows
  the run; any other present value is a non-proceed gate.
- **State.** `AgentState` gains only the optional `evidence_context` and
  `evidence_verdicts`; `InvestDebateState` and existing fields are unchanged. The
  model returns only `{"claims": [...]}`. Researchers insert only trusted
  `projection` / `evidence_refs`, an explicit `[HYPOTHESIS]` marker, or a controlled
  `[ABSTAIN]` marker into the debate state; raw `response.content` is never inserted.
  `current_response` keeps the `Bull Analyst:` / `Bear Analyst:` prefix that
  `ConditionalLogic` reads.
- **E audit.** Each researcher turn appends one strict plain-JSON record with
  `speaker`, `round`, `verdicts`, `rejected_refs`, `as_of` and `run_id` to
  `evidence_verdicts`. The record is preserved in the returned state; this module
  does not claim audit persistence.
- **Return and exception behavior.** `propagate_with_evidence` raises `ValueError`
  for `checkpoint_enabled=True`, an invalid `trade_date`, an invalid evidence
  context, or a date mismatch, before `run_config` or state creation. An explicit
  non-proceed returns `(abstain_state, "REVIEW")` with zero graph or LLM calls. A
  valid snapshot returns `(final_state, run_rating(final_state))`. Default
  `propagate` behavior is unchanged.
- **Coverage.** A10–A13 are covered offline with the real compiled graph and scripted
  models. A14 full B/C/D/E interoperability is **PENDING** until PRs #3/#4/#5/M3 share
  one baseline. No online semantic verification is claimed.

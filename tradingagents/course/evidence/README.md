# Evidence leaf (FR-001 / INV-001 / ADR-005)

Models claims and evidence-id references; the trusted evidence index is built only
from collector-supplied data for one explicit run. This is a standalone M2 module:
**it is not wired into the LangGraph or the CLI in M1/M2** (main-graph integration
is deferred to M3).

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

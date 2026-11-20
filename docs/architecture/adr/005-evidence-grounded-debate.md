# ADR-005: Evidence-grounded debate (FR-001 / INV-001)

- Status: PROPOSED (design record). Not approved; no approver is named.
- Date: 2026-11-20. Scope: role A, milestones M1/M2 only (standalone module).
- Related: ADR-001 (leaf-module architecture), FR-001, INV-001, NFR-002, NFR-005, FR-004.

## Context

FR-001/INV-001 require strong factual claims in the bull/bear debate to bind at least
one retrieved, usable evidence unit, while forecasts stay hypotheses and unsupported
or unclassifiable text fails closed.

## Provenance findings (upstream, read-only)

- `tradingagents/dataflows/vendors/yahoo/snapshot.py` renders a deterministic Markdown
  snapshot. It prints the requested analysis cutoff and the "latest trading row used"
  as two distinct dates; the OHLCV/indicator rows are *observation* dates, not the
  original publication or availability timestamps of the vendor data.
- `tradingagents/dataflows/vendors/yahoo/market.py` renders indicator series as
  vendor-specific `"date: value"` text; a dated observation alone does not prove when
  the datum was published or became available.
- `tradingagents/agents/tools.py` exposes `get_stock_data`, `get_indicators`, and
  `get_verified_market_snapshot`; it clamps requests to the run cutoff (`as_of` /
  `as_of_window`) and returns "unavailable"/error text as results, not provenance
  metadata.
- `tradingagents/agents/analysts/turn.py`, `.../state.py`, and both
  `.../researchers/bull_researcher.py` / `bear_researcher.py` keep analyst reports and
  debate history as plain strings. No structured provenance survives into state.
- Therefore: the cutoff and the latest observation date must never stand in for
  publication/availability metadata. Missing dates on LLM reports are `unknown`, never
  filled from the cutoff.

No graph or upstream code changes are made in M1/M2; main-graph enforcement is deferred
to M3, where structured numeric snapshot provenance is the preferred boundary.

## Decision (M2 contracts)

- A deterministic, immutable, run-scoped `EvidenceRegistry` is built only from trusted
  collector-supplied evidence units (id, run id, source, `content_ref`, status
  `available|unavailable|unknown`, `published_at`, `available_as_of`, canonical fact,
  freshness policy). `neutral` is rejected.
- The model may supply `Claim` text and evidence *references only*; it cannot inject
  evidence records or free text into the trusted path.
- Two verdict layers: (1) admissibility `accept|reject` with stable reason codes and
  EVAL-009 `future_leakage`; (2) claim `accept_factual|hypothesis|abstain` with fixed
  EVAL-006 `forecast_requires_hypothesis_label` and EVAL-008
  `evidence_supports_factual_claim`.
- Matching is exact over ticker, metric, value-or-relation, unit, and period/date. An ID
  match alone can never establish a claim. Value typing keeps `bool`, `int`, `float`,
  `str` distinct (no `True == 1`).
- The collector may supply `EvidenceUnit` objects or plain mappings; any other batch
  item fails closed with `malformed`, and `from_dict` trims replay quarantine IDs
  before applying them.
- Dates are mandatory and canonical: `published_at <= available_as_of <= as_of`, and
  an optional `fact.period` is cutoff-checked. A present future date (including a
  future `fact.period`) is `future_leakage`; `available_as_of < published_at` is
  `invalid_date` even with no age limit; missing dates are `missing_date` with no
  cutoff fallback.
- Freshness is measured from `published_at` and is inclusive: `(as_of -
  published_at).days <= max_age_days`, so same-day and boundary-age evidence pass and
  a fresh recapture cannot reset age; invalid policy or dates fail closed.
- Missing/unknown/unavailable/malformed/foreign/conflicting/unrelated inputs cannot
  produce `accept_factual`.
- Classification: English directional verbs stay historical unless in a modal/future
  context (e.g., "will surge", "may surge", "is going to exceed", "is likely to
  surge", "to plunge"); Chinese target/forecast markers (e.g., 目标价, 即将, 大概率,
  可能上涨, 涨停) are hypotheses. An explicitly declared factual claim with no
  structured fact abstains with `no_structured_fact`, while no declaration or an
  explicit `unknown` without a fact is `unclassified`.
- Audit: accepted matching references remain only in `evidence_refs` and
  `projection`. `rejected_refs` records every evaluated reference that failed
  admission or exact support in input order, as plain JSON
  `[{"evidence_id": ..., "reasons": [...]}]` with stable per-reference reasons
  (including `future_leakage` and `conflicting_id`). One valid matching reference
  preserves factual acceptance. Early verdicts (hypothesis, unclassified,
  no_structured_fact, no_reference) do not evaluate reference support, so their
  `rejected_refs` is empty.

## Consequences

- Contract objects serialize to plain JSON (`to_dict`), so tests and M3 audit replay can
  round-trip them.
- The module is Python 3.11 standard library only, uses no clock/RNG, and imports no
  other leaf module (`budget`, `safety`, `data_quality`, `audit`) or the shared
  `pipeline` orchestrator, preserving NFR-005 and ADR-001 leaf boundaries.
- Reopen if the teacher requires a different layout, if BASE-001/002 would be affected,
  or when M3 integrates the debate nodes.

# Report Contribution — Role B (FR-002 / FR-006)

> Consolidated material for `Report.md`. English (course language).
> Every claim points at a commit, a file, or a CI result. Anything not done is listed in §6.
> Member name, student id and the personal reflection are the member's to supply.

## 1. Contribution record

| Item | Value |
|---|---|
| Pull request | [#4](https://github.com/lyx08042/cs5351-tradingagents/pull/4) |
| Branch | `feat/B-budget` |
| Commits | 19 |
| Files | 36 (+9,204 / −7; 32 files at the first review) |
| Requirements | FR-002, FR-006, INV-002, INV-006 (touches NFR-001, NFR-002) |
| CI | 8/8 checks green on `4b994e9` (tests on py3.11–3.14, clean-install, ruff, scaffold) |

Code: `tradingagents/course/budget/{contracts,ledger,policy,context,integration,replay}.py`, plus a
fourteen-line opt-in change in `tradingagents/graph/trading_graph.py`.
Tests: `test/offline/test_budget.py`, `test_budget_integration.py`, `test_budget_replay.py`
(58 tests), and `test/live/eval_budget.py` (offline-safe driver, never executed).
Plans and evidence: `tasks/plans/B/` including `evidence/`.
Session record: `transcripts/60399223-YixinSONG/{raw.md,annotations.md}`.
Governance: `docs/ai-use-log.yaml` (AI-USE-B-0001), `docs/bug-diary.md` (BUG-004),
`docs/architecture/evaluation-logbook.md`, `docs/architecture/adr/005-*.md`,
`docs/architecture/runtime-policy-catalog.md` §5, `docs/review-memo.md`.

## 2. Implementation

**Ledger.** Reserve before a call, settle after it, keyed by call id, so a repeated settlement cannot charge
twice. Every mutation happens under one lock, which makes the balance check and the charge a single atomic
step; this is what prevents the four parallel analysts from overselling the same pool. An identity is
validated *before* any quota is borrowed, so a duplicate id cannot leave a partial charge behind.

**Allocation.** Six stage quotas over one global pool. Quotas are soft and borrowable, except the portfolio
manager's share, which is reserved for the final decision: a run that spends everything before the last node
produces no decision at all.

**Degradation.** L0–L5: compress injected content, reduce debate rounds, downgrade the model tier, skip
optional agents, then emit an explicitly degraded verdict. The level is monotonic within a run and every
change emits an event with a reason. The trigger compares the remaining budget against the *projected*
remaining spend rather than a fixed fraction — the difference between degrading a run that is merely ending
and one that will actually overspend.

**Context assembly.** Section budget, compaction above 12,000 tokens to 8,000, then re-injection of four
critical blocks (safety constraints, instrument identity, degradation level, remaining budget). The check is a
substring assertion, so a missing block fails closed rather than relying on the model to notice.

**Enforcement point.** The graph constructs exactly two chat models and every node composes
`(prompt | llm)`; wrapping those two covers the whole pipeline. The proxy forwards `bind_tools` and
`with_structured_output`, because the research manager, trader and portfolio manager produce structured
output and would otherwise escape accounting. ADR-007 records this decision against three alternatives
(per-agent accounting, orchestrator accounting, provider quotas).

## 3. Verification

Three tiers. **Structural:** a source scan asserts the budget package imports none of the sibling leaves.
**Behavioural:** 58 offline tests; the negative cases are the substance — a call beyond the cap is refused,
16 threads against a 10-call budget admit exactly 10, a repeated settlement charges once, a duplicate id
leaves the quota untouched, a provider failure or a nonsense usage releases its reservation, a lower
degradation level raises, and a single call that exhausts the pool raises instead of returning. **Regression:**
the upstream suite runs in CI on four Python versions and is green.

Cost behaviour was measured by replaying the recorded baseline (19 calls, 228,275 tokens, from
`docs/baseline.md`) under five caps. This is a deterministic what-if analysis, not a live model run: the
aggregates are real, the per-call split is synthetic because the original run did not record it.

| Cap (tokens) | Calls | Tokens | Δ | Level | Skipped |
|---|---|---|---|---|---|
| baseline | 19 | 228,275 | — | L0 | 0 |
| 240,000 | 19 | 228,275 | 0.0% | L0 | 0 |
| 200,000 | 19 | 149,519 | −34.5% | L1 | 0 |
| 180,000 | 17 | 130,827 | −42.7% | L2 | 2 |
| 150,000 | 17 | 130,827 | −42.7% | L3 | 2 |
| 120,000 | 13 | 104,251 | −54.3% | L4 | 6 |

Three findings:

1. A cap at or above the baseline leaves the run untouched, so the controller does not degrade runs that
   already fit.
2. Compression alone buys 34.5% with every call still executed, which makes it the cheapest lever.
3. L3 downgrades the model tier and therefore changes price per token, not token volume — the 150,000 row
   matches the 180,000 row. The report must not claim a token saving from L3.

## 4. Process evidence (what review and CI actually caught)

**Review round 1** (`cba1277`, reviewer A, four findings, all accepted and fixed in `b23f541`):

| Finding | What it was | Fix |
|---|---|---|
| 1 | `AI-USE-0002`, the owner's historical G-1/D9 record, had been overwritten by the agent | Restored verbatim from `origin/main`; `git diff origin/main -- docs/ai-use-log.yaml` now shows an addition only |
| 2 | `reserve()` borrowed quota before validating the call id, and never checked settled ids | Identity validated first; settled ids rejected; two regression tests |
| 3 | Stage attribution fell back to `analyst` when no config is passed; `include_raw` usage ignored; negative usage leaked the reservation; a single-call overrun was returned downstream | `budget_stage()` / `with_stage()` / `stage_resolver`; usage read from `raw`; failed settlement releases; `BudgetOverrun` raised with the response attached |
| 4 | Stale counts and statuses in the B documents; `INV-006` missing from the invariant register | Counts aligned to 58 tests; ADR-005 and the catalogue recorded; `INV-006` added |

The first finding is the one worth reporting: an agent rewriting a historical governance entry is exactly the
class of damage that a non-author review exists to catch, and it would have silently replaced the owner's
policy record at merge time.

**CI round 1** caught a defect that no local run could: two source files carried a UTF-8 BOM, which broke
`ast.parse` in `tests/test_layering.py` on all four Python versions. The cause was an editing tool that adds a
BOM on Windows; the local suite could not run at all (missing runtime dependencies), so CI was the only place
it could surface. Fixed in `a4dff87`.

**BUG-004** was found by replaying the baseline rather than by a unit test: a cap above the baseline degraded
the run, because the policy compared the remaining budget to fixed fractions and every healthy run dips below
those fractions near its end. Fixed by making the rule projection-aware; pinned by a regression test.

## 5. Design trade-offs worth stating

- **Soft quotas, frozen final share.** Hard partitions waste money when analysts are cheap and debates are
  expensive; pure soft allocation lets the expensive stage eat the decision budget.
- **Proxy transparency versus coverage.** The proxy delegates unknown attributes to the inner model, so an
  un-overridden attribute would escape accounting. This is documented rather than hidden.
- **Token metering versus cost.** L3 changes price, not volume; the module says so instead of implying a
  saving it does not deliver.

## 6. Limits and deferred work

- `NFR-001` and `NFR-002` remain **inconclusive**: no live comparison was run, because the authoring machine
  has neither a provider key nor the runtime dependencies. `test/live/eval_budget.py` is ready for whoever
  runs it.
- The per-call token split in `replay.py` is synthetic, calibrated to the recorded totals.
- L5 currently propagates as `BudgetExhausted`; turning it into a portfolio-manager verdict needs the shared
  orchestrator.
- Stage attribution has a hook but is not yet wired into the researcher agents (shared modules, coordination
  PR); until then their calls fall to the default stage.
- Compaction does not yet protect A's `as_of` / `evidence_ref` blocks; deferred to the integration PR.

## 7. Personal reflection (300–500 words)

The course template requires the reflection to be self-written. The member writes this section; it is not
generated here.

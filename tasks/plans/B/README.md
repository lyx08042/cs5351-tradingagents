# Role B — Run Budget (FR-002): Planning Workspace

> Status: **DRAFT / working notes**. This file records the scope and file locations for role B. It claims no
> approval and no completed review.
> This directory (`tasks/plans/B/`) holds B's plans and evidence. Under `DEVELOPMENT-POLICY.md` §3 these are
> working documents, not approval gates. Do not add new plans to `docs/approvals/`.

## 1. Scope

| Item | Content |
|---|---|
| Primary requirement | `FR-002` run budget: allocation, reserve before a call, settle after it, fail closed past the cap |
| Degradation | `FR-006` ladder L0–L5, monotonic, every change emits an event |
| Invariants | `INV-002` (reserve-then-settle), `INV-006` (monotonic level, no silent degradation) |
| Non-functional | `NFR-001` cost (provisional), `NFR-002` quality (provisional) |
| Code path | `tradingagents/course/budget/` |
| Offline tests | `test/offline/test_budget*.py` (58 tests) |
| Review chain | A reviews B; B reviews C; handoff direction B → A |

## 2. Files in this directory

- `FR-002-scope.md` — scope, budget model, ladder, acceptance criteria
- `FR-002-implementation-plan.md` — contracts, state machine, integration point
- `FR-002-test-plan.md` — positive and negative cases, verification commands
- `handoff.md` — seven-category handoff to the reviewer
- `validation.md` — what was verified, and what was not
- `report-contribution.md` — consolidated material for `Report.md`
- `evidence/` — archived test, lint and replay output, plus the BUG-004 note

## 3. Decisions taken (formerly open questions)

1. **Boundary of FR-002** — allocation across stages plus graceful degradation, not a bare global cap. FR-002
   was rewritten and FR-006/INV-006 added; the ledger therefore carries `agent` and `stage`.
2. **Budget unit** — tokens are the primary measure; call count is a secondary hard cap; cost is derived and
   used for reporting only.
3. **Concurrency** — one lock per ledger, and the balance check plus the charge are a single atomic step.
   Pinned by a 16-thread test that admits exactly ten calls.
4. **Semantics at exhaustion** — degrade along the ladder; the final level emits an explicitly degraded
   verdict. A single call that alone exhausts the pool raises `BudgetOverrun` instead of returning silently.

## 4. Out of bounds

- Do not modify the upstream baseline: `tradingagents/` (except the new `course/`), `cli/`, `tests/`, `pyproject.toml`.
- Do not write plans into `docs/approvals/` (human-only).
- Do not claim approved, implemented or evaluated status that is not true.
- No circular imports between leaf modules; the thin orchestrator changes only via a coordination PR.

## 5. References

- `tasks/B-budget.md` — task book
- `docs/req/requirements.yaml` — FR-002 / FR-006 / INV-002 / INV-006
- `docs/architecture/adr/007-budget-at-the-model-client-boundary.md`
- `docs/architecture/invariants.md`, `docs/architecture/trace-matrix.md`
- `DEVELOPMENT-POLICY.md` — the active workflow

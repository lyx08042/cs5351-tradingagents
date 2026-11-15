# Role B — Run Budget (FR-002): Planning Workspace

> Status: **DRAFT / placeholder**. This file states the scope and file locations for role B only. It claims no completed implementation, test result, or approval.
> This directory (`tasks/plans/B/`) is where B's implementation plan and test design live. Under `DEVELOPMENT-POLICY.md` §3 these are working documents, not approval gates. Do not add new plans to `docs/approvals/`.

## 1. Scope

| Item | Content |
|---|---|
| Primary requirement | `FR-002` run budget: reserve before a call, settle after it, fail closed when the budget is exceeded |
| Invariant | `INV-002` reserve-then-settle ordering; deny calls beyond the budget |
| Non-functional | `NFR-001` cost down 20% (provisional target), `NFR-002` quality regression at most 3pp (provisional target) |
| Proposed code path | `tradingagents/course/budget/` |
| Offline tests | `test/offline/` |
| Review chain | A reviews B; B reviews C; handoff direction B → A |

## 2. Files this directory will hold

- `FR-002-scope.md` — scope definition: budget model, degradation ladder, acceptance criteria (present)
- `FR-002-implementation-plan.md` — contracts, state machine, integration points, milestones
- `FR-002-test-plan.md` — positive and negative cases, invariant coverage, verification commands

## 3. Open questions to settle before planning

1. **Boundary of FR-002**: a global pool with a hard rejection (current wording), or allocation across agents plus graceful degradation (the three capabilities listed for role B in the team plan)? This decides whether the ledger contract carries `agent` / `stage` fields.
2. **Budget unit**: tokens, call counts, or derived cost — which are the primary measures?
3. **Concurrency semantics**: with four analysts calling in parallel, how does the shared pool avoid overselling (lock, compare-and-set, reserve-then-refund)?
4. **Runtime semantics at exhaustion**: abort the run, emit a partial result, or continue with a `degraded` flag?

## 4. Out of bounds

- Do not modify the upstream baseline: `tradingagents/` (except the new `course/`), `cli/`, `tests/`, `pyproject.toml`.
- Do not write plans into `docs/approvals/` (human-only directory; agents must not edit it).
- Do not claim approved, implemented, or evaluated status; `PROPOSED` never becomes `APPROVED` through a documentation edit alone.
- No circular imports between leaf modules; the shared thin orchestrator changes only through a coordination PR.
- Never read or commit API keys; offline by default, and live evaluation requires explicit human authorisation of provider, model, and cost cap.

## 5. References

- `tasks/B-budget.md` — task book (deliverables, contract, acceptance table)
- `docs/req/requirements.yaml` — FR-002 / INV-002 / NFR-001 / NFR-002
- `docs/architecture/invariants.md`, `docs/architecture/trace-matrix.md`
- `DEVELOPMENT-POLICY.md` — the active workflow
- `tasks/plans/D/` — D's implementation and test plans, a useful format reference

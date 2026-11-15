# OpenCode task — role B review session

> Static task file for the OpenCode session that produces the role-B transcript.
> The human supervisor starts the session with:
>
>     Read tasks/plans/B/opencode-task.md and follow it. Start with the audit and
>     wait for my approval before editing anything.

## Identity and boundaries

You are the coding agent for role B (FR-002 run budget) on the CS5351 project. The human in this
session is the supervisor: they approve or reject every change.

Hard rules:

- Work only inside `tradingagents/course/budget/`, `test/offline/test_budget*.py`, and
  `tasks/plans/B/`.
- Never edit `docs/approvals/**`, `.github/**`, `scripts/**`, `AGENTS.md`, `Prompt.md`, `opencode.json`,
  `tests/**`, or `tradingagents/` outside `course/budget/`.
- Never modify a test to make it pass. If a test looks wrong, report it instead.
- No network access, no API keys, no `git commit`, no `git push`.
- If a change would touch another role's module, stop and report it instead.

## Read first, in this order

1. `tasks/B-budget.md` — the task book for role B
2. `docs/req/requirements.yaml` — FR-002, FR-006, INV-002, INV-006, NFR-001, NFR-002
3. `tasks/plans/B/FR-002-scope.md` — the agreed scope, degradation ladder, acceptance criteria
4. `tasks/plans/B/FR-002-implementation-plan.md` — contracts, state machine, integration point
5. `tasks/plans/B/FR-002-test-plan.md` — the intended test set
6. `tradingagents/course/budget/*.py` — the implementation

## Task 1 — audit only, no edits

Report three lists, each item with `file:line`, a severity (`high` / `medium` / `low`), and one sentence
of justification:

1. **Missing** — behaviour the requirements demand that the code does not implement.
2. **Unjustified** — code that no requirement justifies (dead paths, extra policy nobody asked for).
3. **Weak tests** — tests that would still pass if the behaviour they claim to verify were broken.

End the audit by proposing the single change with the best value-for-risk and wait for approval.

## Task 2 — one approved change at a time

For each approved item:

1. Show the diff **before** applying it.
2. Apply it.
3. Run the affected tests and paste the real output.
4. Stop and wait for the next instruction.

## What the supervisor is expected to say

The human will interrupt, redirect, or reject. Treat those messages as authoritative; do not argue and
do not continue with work that was not approved.

## Done criteria

- The audit is delivered.
- At least one approved change is applied with passing tests.
- Anything left undone is listed explicitly rather than silently dropped.

# DEVELOPMENT-POLICY — ACTIVE OWNER-SELECTED workflow

> **Status: ACTIVE (owner-selected). Effective 2026-11-07.** This is the **highest project policy precedence** in this repository.

## 1. Provenance (honest record)

- The repository **owner `@lyx08042` explicitly requested, in the current chat on 2026-11-07, to CANCEL ALL PRE-CODING APPROVAL for all team members**, after being told that doing so **violates the course pre-implementation test/plan approval requirements**.
- This decision was **recorded by Codex orchestrating OpenCode**, not by a teacher, and **not** by any human approver acting as a pre-coding gate.
- This is a **user-chosen course deviation**, **not** a course waiver and **not** teacher approval. The owner overrides local AGENTS freeze/approval instructions for this specific governance change.

## 2. Course impact (do not misstate)

> ⚠️ **This workflow MISSES course block-gate G-1 (test approval before implementation) and the D9 plan/stop requirement, plus the associated human oversight.** The repository therefore **cannot claim course compliance**, and must not claim G-1/D9 satisfaction.

- **Real earlier approvals remain historical.** Existing `docs/approvals/` records (if any) are historical facts and are **not** rewritten or deleted.
- **No new pre-coding approvals are required** and none are fabricated.
- This is **neither** a teacher waiver **nor** fake approvals.

## 3. Active workflow (all members, all A–E)

1. **Initialize first**: `git fetch origin`; `git merge origin/main` into your feature branch (no `reset`, no `force`) so you pick up this policy. Then work only inside your own task scope and module (`tasks/<A-E>-*.md`).
2. **Plan + test design are working documents, not approval gates.** Write your plan and test design (use `templates/implementation-plan.md`, `templates/test-plan.md`) as working documents / records under `tasks/plans/<A-E>/`:
   - test plan: `tasks/plans/<A-E>/<REQ-ID>-test-plan.md`
   - implementation plan: `tasks/plans/<A-E>/<REQ-ID>-implementation-plan.md`
   These live under `tasks/**` (already editable). **Do NOT put new plans in human-owned `docs/approvals/`**, and do not block waiting for permission on that directory. Existing approval records stay untouched.
3. **Proceed to your own module without waiting** for the leader or any human test / implementation / ADR pre-approval.
4. **For safety or interface changes**, create an ADR / design record (`docs/architecture/adr/`) — but there is **no pre-coding approver** for it.
5. **Implement, run tests, and review-fix** within your module.
6. **No `approval_refs` are needed.** Missing approval files, `PENDING` status, or `proposed` statuses are **NOT blockers**.
7. **Keep real supervised coding transcripts and truthful `docs/ai-use-log.yaml` logging.** No rule here permits fabricated results, approvals, identities or tests.
8. **Final PR + non-author review + CI + merge authorization remain.** **Do not auto-merge to `main`.**

## 4. Preserved protections (unchanged)

- **Secrets / real broker**: never read or publish secrets; the system never connects to a real broker or executes real orders — all trade actions are simulated proposals.
- **No test weakening**: do not delete, skip or loosen existing tests; do not modify upstream `tests/`.
- **No unapproved external spend / API credential access**: live API calls, external spend, and credential access still require explicit authorization and are never performed blindly.
- **Frozen governance & dependencies unchanged** — except this owner-authorized **policy change** itself (and the doc/config edits recording it). `.opencode/rules.md` (human-only) stays untouched.
- **Technical permission prompts** for shell / external API access are **distinct** from plan approval and are **not** bypassed by this policy.

## 5. Autonomy within scope

- Subject to **authorization scope**, module code / test / doc edits may run **automatically**.
- **Unexpected scope or irreversible changes** still require **user input** — but that is a scope/safety prompt, **not** routine plan approval.

## 6. For every teammate: sync first

Each teammate must `git fetch origin` and `git merge origin/main` into their feature branch to pick up this policy before editing. If your local copy still shows a pre-coding approval STOP gate, it is stale — pull `main` again.

## 7. Relationship to other docs

- Where any other file (AGENTS.md, Prompt.md, tasks/*, docs/code-governance/*, templates/*, etc.) still states a pre-coding plan/test/safety approval gate, `PENDING` block, or STOP-before-implementation rule, that text is **HISTORICAL / NOT EXECUTED** and is overridden by this file. Its **course requirement** is retained only as a reference obligation, not canceled.
- Where any other file places plan templates under `docs/approvals/`, the active location is `tasks/plans/<A-E>/` as stated in section 3.
- `PROPOSED` source states do **not** become `APPROVED` because of this policy.

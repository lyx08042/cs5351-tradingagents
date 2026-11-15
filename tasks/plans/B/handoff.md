# Handoff: B → A

> Seven-category handoff per `tasks/README.md` §4 and `templates/handoff.md`.
> Status: DRAFT — member name and student id are intentionally left blank; the member fills them.
> Nothing here claims approval, course compliance, or a completed review.

## 1) Requirements + fits

- IDs: `FR-002` (metered budget ledger), `FR-006` (degradation ladder), `INV-002`, `INV-006`;
  non-functional anchors `NFR-001`, `NFR-002`.
- Statements and fit criteria live in `docs/req/requirements.yaml` (edited in `a7c7f17`).
- Fits:
  - FR-002: metric = LLM calls still executed after the budget is exhausted; threshold = 0.
  - FR-006: metric = degradations without a recorded reason; threshold = 0.
  - INV-002 / INV-006: zero-tolerance, each backed by a test that fails when violated.

## 2) Design / interfaces / ADR / invariants

- Contracts: `tradingagents/course/budget/contracts.py` (`LedgerConfig`, `Reservation`, `Settlement`,
  `BudgetEvent`, `BudgetDenied`, `LevelRegression`, `ContractError`).
- Ledger: `ledger.py` — `reserve` / `settle` / `release` / `remaining` / `snapshot`; one lock per ledger.
- Policy: `policy.py` — L0–L5, projection-aware; `apply_level` is the only mutator and always emits.
- Context: `context.py` — section budget, compaction, four mandatory re-injected blocks, `assert_manifest`.
- Integration: `integration.py` — `BudgetedChatModel` proxy (`invoke`, `bind_tools`,
  `with_structured_output`, `__call__`), plus a five-line opt-in change in `graph/trading_graph.py`.
- ADR: still to be written (`docs/architecture/adr/00x-...`); the decision is "enforce at the model-client
  boundary", with alternatives recorded in `tasks/plans/B/FR-002-implementation-plan.md` §12.
- Invariants: fail-closed throughout — invalid config raises at construction, denied calls never reach the
  provider, and an overrun stops the run instead of being absorbed silently.

## 3) Code + tests + PR

- Files: `tradingagents/course/budget/{__init__,contracts,ledger,policy,context,integration,replay}.py`;
  `test/offline/test_budget.py`, `test_budget_integration.py`, `test_budget_replay.py`;
  `test/live/eval_budget.py` (optional live driver).
- Tests: 48 offline tests, including negative cases for over-budget denial, oversell under 16 threads,
  double settlement, level regression, missing re-injection, and provider failure.
- PR: not opened yet (planned after the transcript lands).
- Plans: `tasks/plans/B/FR-002-scope.md`, `FR-002-implementation-plan.md`, `FR-002-test-plan.md`.
- Approval refs: none required under `DEVELOPMENT-POLICY.md`; none claimed.

## 4) Evaluation / configuration / results

- Case set: `docs/evaluation/cases.yaml` (EVAL-004 covers the over-budget rejection).
- Method: deterministic replay of the recorded baseline trace (`replay.py`), not a live model run.
- Result: `docs/architecture/evaluation-logbook.md` record `FR-002-replay-2026-11-15`
  (pass for deterministic behaviour, inconclusive for decision quality).
- Live comparison: not run — no provider key and no runtime dependencies on the authoring machine;
  `test/live/eval_budget.py` is ready for whoever runs it.

## 5) Raw session + annotations

- raw: `transcripts/<studentid-name>/raw.md` (to be added by the member; complete and unedited)
- annotations: `transcripts/<studentid-name>/annotations.md`
- Status: pending — the member must supply the identifier and the real session export.

## 6) AI use / review / bugs / debt

- AI use: `docs/ai-use-log.yaml` (entries for this work appended).
- Review: `docs/review-memo.md` — awaiting A's review of this handoff.
- Bug: `docs/bug-diary.md` BUG-004 (false degradation, fixed in `aade521`).
- Debt: `docs/debt-register.md` — two items worth recording: the L5 verdict path still needs the shared
  orchestrator, and `BudgetedChatModel` delegates unknown attributes to the inner model (so an unbudgeted
  path could exist if a future caller uses one of those attributes directly).

## 7) Report contribution + reflection + evidence + demo material

- Report section: `tasks/plans/B/report-contribution.md` (draft; the leader merges it into `Report.md`).
- Reflection: 300–500 words, to be written by the member in their own voice.
- Evidence: commits `d90893b`, `a7c7f17`, `8245b6f`, `784ecbd`, `a50de4a`, `e086478`, `aade521`, `cf960f6`;
  test output (48 passed); evaluation logbook record.
- Demo: the replay table in the logbook is the cheapest demo — it shows baseline vs four caps in one screen.

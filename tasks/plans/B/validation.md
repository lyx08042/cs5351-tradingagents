# Validation report 鈥?role B (FR-002 / FR-006 / INV-002 / INV-006)

> Every claim points at a file in `tasks/plans/B/evidence/` or at a repository path.
> Language: English (course language).
> Scope: what was actually executed. Anything not executed is listed in section 5 as unverified 鈥?> it is not implied to have passed.

## 1. Environment and method

- Python 3.12.14, pytest 9.2.0, ruff 0.17.5.
- Offline only: no network call, no model call, no API key read.
- Deterministic: the ledger takes an injected clock and id factory; the replay takes a fixed trace.
- The upstream `tests/` suite was **not** run on the authoring machine (runtime dependencies absent);
  it is expected to run in CI when the pull request opens 鈥?see section 5.

## 2. Three-tier verification

| Tier | What was checked | Result | Evidence |
|---|---|---|---|
| Structural | `budget/` imports nothing from `evidence/`, `safety/`, `data_quality/`, `audit/` | pass | `test_budget_module_does_not_import_sibling_leaf_modules` (source scan) |
| Regression | course scaffold schema/trace coverage | pass | `python scripts/check_course.py --root .` 鈫?`course scaffold check: OK` |
| Behavioral | 56 offline tests across ledger, policy, context, integration and replay | pass | `offline-final.txt` (56 passed) |

## 3. Key numbers and where they come from

| Item | Value | Source |
|---|---|---|
| Budget suite | 56 passed in 0.14 s | `offline-final.txt` |
| Lint | All checks passed | `ruff-final.txt` |
| Baseline trace | 19 calls, 228,275 tokens (196,870 in + 31,405 out) | `docs/baseline.md` |
| Replay at 240,000 | 228,275 tokens, L0, 0 degradations | `replay-table.json` |
| Replay at 200,000 | 149,519 tokens (鈭?4.5%), L1 | `replay-table.json` |
| Replay at 120,000 | 104,251 tokens (鈭?4.3%), L4, 6 calls skipped | `replay-table.json` |
| BUG-004 regression | cap 240,000 鈫?no degradation after the fix | `bug-004-after-fix.txt`, `bug-004.md` |

## 4. Requirement coverage

| Requirement | Fit criterion | Tests |
|---|---|---|
| FR-002 | calls executed after exhaustion = 0 | `nt1`, `nt4`, `nt15` |
| FR-002 | concurrent oversell = 0 | `nt5` (16 threads, 10 admitted) |
| FR-002 | reservation released when the provider fails | `nt14` |
| FR-006 | degradations without a recorded reason = 0 | `nt6`, `nt7`, `pt14` |
| INV-002 | reserve-before-settle, no double charge | `pt2`, `pt3`, `nt3`, `nt9` |
| INV-006 | level never regresses | `nt6` |
| D2.2 | compaction keeps the four constraint blocks | `pt15`鈥揱pt19`, `nt8`, `nt12`, `nt13` |

## 5. Not verified (stated, not hidden)

1. **Live model comparison** 鈥?no provider key was available; `test/live/eval_budget.py` is written and
   syntax-checked but never executed. `NFR-001` and `NFR-002` therefore remain `inconclusive`.
2. **Upstream regression suite (1412 tests)** 鈥?not runnable on the authoring machine; deferred to CI.
3. **Independent review** 鈥?A has not reviewed this work yet; `tasks/plans/B/handoff.md` is the request.
4. **Per-call token split** 鈥?synthetic inside `replay.py`, calibrated to the recorded totals; the original
   run did not record per-call usage.
5. **L5 degraded verdict** 鈥?the proxy raises `BudgetExhausted`; mapping it to a portfolio-manager verdict
   needs the shared orchestrator and is not implemented.

## 6. How to reproduce

```bash
python scripts/check_course.py --root .
python -m pytest test/offline/test_budget.py test/offline/test_budget_integration.py \
    test/offline/test_budget_replay.py -q
ruff check tradingagents/course test/offline/test_budget*.py
python -c "from tradingagents.course.budget.replay import compare; \
print([r.to_dict() for r in compare([240000,200000,180000,150000,120000])])"
```

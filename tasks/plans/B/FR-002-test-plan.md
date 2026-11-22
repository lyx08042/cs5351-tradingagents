# Test Plan — FR-002 / FR-006 / INV-002 / INV-006

- Author: coding agent (role B) — member identity not assumed
- Reviewer (non-author): A (planned, not yet reviewed)
- Related implementation plan: `tasks/plans/B/FR-002-implementation-plan.md`
- Status: DRAFT (working document, not an approval gate)
- Location: `test/offline/test_budget.py` (deterministic; no network, no LLM, no API key)

## 1. Strategy

- **Offline and deterministic.** The ledger takes an injected clock and id factory; estimates come from a fixed
  table. The same input must produce the same event sequence (AC-7).
- **Negative first.** Every invariant gets at least one test that *fails when the invariant is violated*
  (course D4). Positive tests prove the happy path but do not substitute for them.
- **No mocking of the module under test.** Tests drive the real classes; only the clock, the id factory and the
  estimate table are injected.
- **Three tiers** (course D4): structural (module imports, no circular dependency), behavioural (this file),
  regression (the existing `tests/` suite is untouched and must keep passing).

## 2. Fixtures

```python
@pytest.fixture
def clock():
    """Monotonic fake clock: 2026-11-15T00:00:00Z + n seconds."""
    t = {"n": 0}
    def now():
        t["n"] += 1
        return f"2026-11-15T00:00:{t['n']:02d}Z"
    return now

@pytest.fixture
def ledger():
    cfg = LedgerConfig(limit_tokens=10_000, limit_calls=10)
    # fixed estimates: every (agent, stage) costs exactly 1_000
    est = {(None, s): 1_000 for s in STAGES} | {("market_analyst", "analyst"): 1_000}
    return BudgetLedger(cfg, clock=clock(), id_factory=SeqIds(), stage_estimates=est)
```

`SeqIds` returns `call-1`, `call-2`, … so assertions can reference exact ids.

## 3. Positive tests

| ID | Behaviour under test | Assertion |
|---|---|---|
| PT-1 | Reserve inside budget | `Reservation` returned; `remaining_global` drops by the estimate; one `reserve` event |
| PT-2 | Settle exactly at the estimate | `refunded == 0`, `overrun == 0`, remaining unchanged after settle |
| PT-3 | Settle below the estimate | `refunded == estimate - actual`; the stage and global pools are restored |
| PT-4 | Stage quota is honoured | Spending on `analyst` does not reduce `portfolio_manager`'s quota below its protected share |
| PT-5 | Borrowing succeeds | A stage short of budget borrows from an unspent stage; a `borrow` event carries `reason` |
| PT-6 | Determinism | Two ledgers fed the identical call script produce identical `snapshot()` and event sequences |
| PT-7 | Release before execution | Reservation returned in full; one `release` event; no `settle` event |

## 4. Negative tests

| ID | Violation being forced | Expected fail-closed behaviour |
|---|---|---|
| NT-1 | Reserve beyond `limit_tokens` | `BudgetDenied("global_exhausted")`; ledger state `exhausted`; `exhausted` event emitted |
| NT-2 | Reserve beyond `limit_calls` | `BudgetDenied("call_limit")`; no charge applied |
| NT-3 | Settle a call twice | Second call returns the stored `Settlement`; total spend unchanged (INV-002 idempotency) |
| NT-4 | Settle above the reservation, beyond the pool | `over_budget` event; state `exhausted`; every later `reserve` denied |
| NT-5 | 8 threads × 1 call against `limit_calls=10` | Exactly 10 succeed, 8 denied at most; total spend never exceeds the limit (AC-2) |
| NT-6 | Lower the degradation level | `LevelRegression` raised; `level` unchanged (INV-006) |
| NT-7 | Advance two levels at once | Allowed (monotonic increase), but exactly one `degraded` event per change with the new level |
| NT-8 | Compact without re-injection | `assert_manifest` raises `ContractError`; assembly is rejected (AC-5) |
| NT-9 | Unknown stage or negative config | `ContractError` at construction/validation time (fail-closed) |
| NT-10 | Release a settled call | No-op, no event, no double refund |

## 5. Requirement → test mapping

| Requirement / invariant | Fit criterion | Tests |
|---|---|---|
| FR-002 | Calls executed after exhaustion = 0 | NT-1, NT-4 |
| FR-002 | Concurrent oversell = 0 | NT-5 |
| FR-006 | Degradations without a recorded reason = 0 | NT-6, NT-7 |
| INV-002 | Reserve-before-settle ordering; no double charge | PT-2, PT-3, NT-3, NT-10 |
| INV-006 | Level reversals + silent degradations = 0 | NT-6, NT-7 |
| AC-5 | Compaction keeps the four constraint blocks | NT-8, plus a positive assembly test |
| AC-7 | Same input → same event sequence | PT-6 |
| NFR-001 / NFR-002 | Cost −20%, quality −3pp | **Out of scope here** — needs the live/replay evaluation harness (section 7) |

## 6. Coverage rules (course D4)

1. Every fit criterion above has at least one test.
2. Every invariant has at least one test that **fails when the invariant is violated** (NT-3, NT-6, NT-7).
3. Every test docstring names the requirement ID it verifies, e.g. `"""FR-002: reserve beyond the pool is denied."""`
4. No test is skipped or marked xfail to make the suite pass.
5. The existing `tests/` suite is untouched; `pytest` must show zero regressions.

## 7. Out of scope (deferred to the evaluation step)

- AC-8 (token use −20%) and AC-9 (quality −3pp) require real runs against a fixed case set
  (`docs/evaluation/cases.yaml`) with a model; they belong to the evaluation milestone, not the offline suite.
- Recording those results into `docs/architecture/evaluation-logbook.md` is an evaluation task, not a unit test.

## 8. Commands

```bash
python scripts/check_course.py --root .
pytest -o testpaths=test/offline test/offline/test_budget.py -q
pytest -o testpaths=test/offline test/offline -q
ruff check tradingagents/course/budget test/offline/test_budget.py
```

Expected: all green, no network access, no API key required.

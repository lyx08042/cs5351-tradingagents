# Implementation Plan — FR-002 / FR-006 / INV-002 / INV-006

- Author: coding agent (role B) — member identity not assumed
- Reviewer (non-author): A (planned, not yet reviewed)
- Related test plan: `tasks/plans/B/FR-002-test-plan.md`
- Related scope: `tasks/plans/B/FR-002-scope.md`
- Status: DRAFT (working document, not an approval gate)
- Approval refs: none (per `DEVELOPMENT-POLICY.md`; no pre-coding approval is required or claimed)

## 0. Requirement and scope

- Requirements: `FR-002` (metered budget ledger), `FR-006` (degradation ladder), `INV-002` (reserve before call, fail closed), `INV-006` (monotonic level, no silent degradation).
- Non-functional anchors: `NFR-001` (cost down 20%, provisional), `NFR-002` (quality regression ≤ 3pp, provisional).
- Change scope — new files only:
  - `tradingagents/course/__init__.py` (package docstring only, no logic)
  - `tradingagents/course/budget/__init__.py`
  - `tradingagents/course/budget/contracts.py`
  - `tradingagents/course/budget/ledger.py`
  - `tradingagents/course/budget/policy.py`
  - `tradingagents/course/budget/context.py` (compaction budget + re-injection manifest)
  - `test/offline/test_budget.py`
  - `tasks/plans/B/FR-002-{implementation,test}-plan.md`
- Frozen (not modified): existing `tradingagents/**` (except the new `course/`), `cli/`, `tests/`, `pyproject.toml`,
  `.github/**`, `scripts/**`, `AGENTS.md`, `Prompt.md`, `opencode.json`, `docs/approvals/**`, and the other leaf
  modules (`evidence/`, `safety/`, `data_quality/`, `audit/`).
- Integration into `tradingagents/graph/**` is **M4** and lands through a coordination PR, not this one.

## 1. Contracts (`contracts.py`)

No behaviour beyond validation and normalisation; every structure is JSON-serialisable.

### 1.1 Enums (as `str` Literal + tuple constants)

```
Stage         = "analyst" | "debate" | "research_manager" | "trader" | "risk_debate" | "portfolio_manager"
ModelTier     = "quick" | "deep"
Level         = 0..5            # degradation level, L0 = normal
ReserveState  = "reserved" | "settled" | "released"
LedgerState   = "open" | "exhausted" | "closed"
EventType     = "reserve" | "settle" | "release" | "borrow" | "degraded" | "compacted" | "over_budget" | "exhausted"
```

### 1.2 Configuration

```python
@dataclass(frozen=True)
class LedgerConfig:
    limit_tokens: int = 240_000
    limit_calls: int = 60
    stage_quota: Mapping[Stage, float] = {...}   # fractions summing to 1.0
    protected_stage: Stage = "portfolio_manager"  # never borrowable
    borrow_max_fraction: float = 0.30             # max share of global remainder per borrow
    estimate_margin: float = 1.30
    estimate_floor: int = 800
    l3_threshold: float = 0.15                    # global remainder fraction
    l4_threshold: float = 0.10
    context_cap: int = 16_000
    compact_threshold: int = 12_000
    compact_target: int = 8_000
```

Validation (fail-closed): `limit_tokens > 0`, `limit_calls > 0`, `estimate_margin >= 1.0`,
`0 < l4_threshold < l3_threshold < 1`, `compact_target < compact_threshold <= context_cap`,
quota fractions non-negative and summing to 1.0 ± 1e-9. Any violation raises `ContractError`.

### 1.3 Records

```python
@dataclass(frozen=True)
class Reservation:
    call_id: str
    agent: str
    stage: Stage
    model_tier: ModelTier
    estimated: int
    remaining_global_after: int
    remaining_stage_after: int

@dataclass(frozen=True)
class Settlement:
    call_id: str
    reserved: int
    actual: int
    refunded: int          # reserved - actual, >= 0
    overrun: int           # actual - reserved, >= 0
    remaining_global: int
    state: ReserveState

@dataclass(frozen=True)
class BudgetEvent:
    event_id: str
    ts: str                # ISO-8601, injected clock
    type: EventType
    agent: str | None
    stage: Stage | None
    model_tier: ModelTier | None
    estimate: int | None
    actual: int | None
    remaining_global: int
    remaining_stage: int | None
    level: Level
    reason: str
```

`BudgetEvent.to_dict()` returns only str/int/None (JSON-serialisable, asserted in tests).

### 1.4 Errors

- `BudgetDenied(reason, remaining_global)` — raised by `reserve` when the request cannot be met.
- `ContractError` — malformed config or records.
- `LevelRegression` — raised when a caller tries to lower the degradation level (INV-006).

## 2. Ledger (`ledger.py`)

### 2.1 State

```python
class BudgetLedger:
    def __init__(self, config: LedgerConfig, *, clock=..., id_factory=...,
                 stage_estimates: Mapping[tuple[str, Stage], int] | None = None): ...
    _lock: threading.Lock
    _state: LedgerState
    _reserved: dict[str, Reservation]      # call_id -> reservation
    _settled: dict[str, Settlement]        # call_id -> settlement (idempotency)
    _stage_spent: dict[Stage, int]
    _stage_budget: dict[Stage, int]        # quota + borrowed - lent
    _level: Level
    _events: list[BudgetEvent]
```

`clock` and `id_factory` are injected so tests are deterministic (AC-7).

### 2.2 `reserve(agent, stage, model_tier, call_id=None) -> Reservation`

All of the following happen inside `with self._lock:` — the check and the charge are one atomic step:

1. If `self._state != "open"` → `BudgetDenied("ledger_closed")`.
2. `estimate = self._estimate(agent, stage)` (§3).
3. If `remaining_global < estimate` → no reallocation can help (borrowing moves stage quotas, it does not grow
   the global pool): apply the policy to L5, emit `exhausted`, set state `exhausted`, raise
   `BudgetDenied("global_exhausted")`.
4. If `remaining_stage(stage) < estimate` → try to borrow from unspent, non-protected stages (§4); if borrowing
   fails → apply the degradation policy (§5) and re-check **once**; if still short →
   `BudgetDenied("stage_exhausted")`.
5. Charge: `_reserved[call_id] = Reservation(...)`, decrement `_stage_budget[stage]` and the global pool.
6. Emit `reserve` event; return the `Reservation`.

`call_id` defaults to `uuid4().hex`; callers may supply one for replay tests.

### 2.3 `settle(call_id, input_tokens, output_tokens) -> Settlement`

1. Inside the lock: if `call_id in _settled` → return the stored `Settlement` (idempotent, AC-4).
2. `actual = input_tokens + output_tokens`; `refund = max(0, reserved - actual)`; `overrun = max(0, actual - reserved)`.
3. Refund the difference to the stage and the global pool.
4. If `overrun > 0`:
   - if the refundable pool covers it → charge the overrun, emit `settle` with the overrun recorded;
   - else → emit `over_budget`, set state `exhausted`, charge what is available, and mark the settlement
     `overrun` (subsequent `reserve` calls are denied by rule 1). Never silently continue (INV-002).
5. Emit `settle`; return the `Settlement`.

### 2.4 `release(call_id, reason)`

Returns the full reservation to the pool when a call is abandoned before execution; emits `release`.
Releasing an already-settled call is a no-op that emits nothing (idempotent).

### 2.5 Read-only accessors

`remaining(scope)`, `level`, `events()` (tuple copy), `snapshot()` (dict with totals, per-stage spend,
current level, event count). `snapshot()` is the payload E consumes.

## 3. Estimation

```python
def _estimate(self, agent, stage) -> int:
    base = self._stage_estimates.get((agent, stage))
    if base is None:
        base = self._stage_estimates.get((None, stage), self.config.estimate_floor)
    return max(self.config.estimate_floor,
               int(base * self.config.estimate_margin))
```

`stage_estimates` is a table derived from the baseline run and is a constructor argument — never measured from a
live call. Determinism therefore holds without any network access.

## 4. Allocation and borrowing

- `_stage_budget` is initialised from `stage_quota × limit_tokens`.
- `remaining_global = limit_tokens - spent - reserved_outstanding`.
- `_borrow(target_stage, need)` may take from any stage with `remaining > 0`, **except** `protected_stage`.
- A single borrow may not exceed `borrow_max_fraction × remaining_global`; a borrow that would exceed it is
  denied rather than scaled (predictable failure beats silent partial borrowing).
- Every successful borrow emits `borrow` with `reason=f"borrow:{lender}->{target_stage}"`.

## 5. Degradation policy (`policy.py`)

```python
class DegradationPolicy:
    def evaluate(self, ledger, stage) -> Level | None:
        """Return the level that should be applied now, or None to keep the current level."""
```

Rules (evaluated in this order; the ledger applies the result through `apply_level`):

| Level | Condition | Effect applied by the caller |
|---|---|---|
| L1 | `remaining_stage < 1.5 × next_estimate` | injector trims news/evidence to `l1_inject_limit` |
| L2 | `remaining_stage < 1.0 × next_estimate` | debate runner decrements `max_debate_rounds` (min 1) |
| L3 | `remaining_global < l3_threshold × limit_tokens` | tier forced to `quick` |
| L4 | `remaining_global < l4_threshold × limit_tokens` | optional agents skipped |
| L5 | `remaining_global < 1 × next_estimate` | PM restricted to `hold` + `degraded=True` |

Monotonicity (INV-006):

```python
def apply_level(self, level: Level) -> None:
    with self._lock:
        if level < self._level:
            raise LevelRegression(f"{level} < {self._level}")
        if level > self._level:
            self._level = level
            self._emit("degraded", level=level, reason=...)
```

A caller cannot lower the level; a degradation without an emitted event is impossible because `apply_level` is
the only mutator and it always emits.

## 6. Context compaction and re-injection (`context.py`)

- `budget_for_section(section, total_available) -> int` distributes the available context budget across
  `identity / constraints / evidence / conversation / state / task` using fixed weights.
- `should_compact(assembled_tokens) -> bool` — true when `assembled_tokens > compact_threshold`.
- `compact(messages, target) -> messages` — deterministic truncation of the conversation section only.
- `reinject(messages, level, remaining_fraction) -> messages` — prepends the four mandatory blocks
  (safety constraints, identity, level, remaining budget) and is **always** called after `compact`.
- `assert_manifest(messages) -> None` — raises `ContractError` if any of the four blocks is missing (AC-5).

The four blocks are plain text with stable sentinel prefixes (`[SAFETY]`, `[IDENTITY]`, `[LEVEL]`,
`[BUDGET]`) so the assertion is a substring check, not an LLM judgement.

## 7. Integration point (M4, coordination PR — described here, not implemented now)

`tradingagents/graph/trading_graph.py` builds exactly two chat models:

```python
self.deep_thinking_llm = create_tier_client(self.config, "deep").get_llm()
self.quick_thinking_llm = create_tier_client(self.config, "quick").get_llm()
```

and agents ultimately call `(prompt | llm).invoke(...)` (`tradingagents/agents/analysts/turn.py`).

Plan: a `BudgetedChatModel` proxy that wraps a model and:

- implements `invoke(input, config=None)` → `reserve` → delegating call → `settle` using
  `response.usage_metadata` (fallback `response_metadata["token_usage"]`);
- implements `bind_tools(tools)` → returns a new proxy around `model.bind_tools(tools)` with the same ledger;
- delegates everything else through `__getattr__` so LCEL composition keeps working;
- on `BudgetDenied` raises `BudgetExhausted` which the graph maps to L5 (degraded verdict), never to a silent
  empty answer.

This keeps the change to **one construction site** instead of editing every agent.

## 8. Files and sizes (estimate)

| File | ~lines | Content |
|---|---|---|
| `contracts.py` | 220 | config, records, events, errors, validation |
| `ledger.py` | 260 | reserve/settle/release, borrowing, atomicity |
| `policy.py` | 120 | level evaluation, monotonic enforcement |
| `context.py` | 140 | section budget, compaction, re-injection manifest |
| `test/offline/test_budget.py` | 320 | cases PT-1..PT-6, NT-1..NT-9 |

## 9. Steps

1. `contracts.py` + validation tests (no behaviour yet).
2. `ledger.py` — reserve/settle/release, single-threaded first, then the lock and the concurrency test.
3. `policy.py` — levels, triggers, monotonicity.
4. `context.py` — compaction and re-injection with the manifest check.
5. `test/offline/test_budget.py` — full case set from the test plan.
6. Verification: `check_course.py`, targeted pytest, ruff.
7. M4 (separate PR): wire `BudgetedChatModel` into `trading_graph.py`.

## 10. Verification commands

```bash
python scripts/check_course.py --root .
pytest -o testpaths=test/offline test/offline/test_budget.py -q
pytest -o testpaths=test/offline test/offline -q
ruff check tradingagents/course/budget test/offline/test_budget.py
```

## 11. Risks and rollback

| Risk | Mitigation |
|---|---|
| Lock contention with four parallel analysts | The critical section is arithmetic only; no I/O inside the lock |
| Estimate drift makes L1 fire constantly | Estimates are a table, not a measurement; tune the table from the baseline run |
| Event schema drifts from E's needs | Fields frozen in §1.3; E consumes read-only |
| Integration changes behaviour of existing agents | M4 is a separate PR with the proxy delegating by default; ledger disabled by config means no-op |

Rollback: the module is additive and unused until M4; deleting the new directory and the test file restores the
baseline exactly.

## 12. ADR

- Needs an ADR (D2.2): "budget enforcement at the model-client boundary rather than inside each agent" with the
  alternatives considered (per-agent accounting, orchestrator-level accounting, provider-side quotas).
- The ADR also records the provisional thresholds and the calibration plan, satisfying the "policy for
  re-injecting critical constraints after compaction" clause.

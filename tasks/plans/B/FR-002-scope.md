# FR-002 Scope Definition — Role B: Run Budget

> Status: **DRAFT (working document)**. This is a scope decision record, not an approval gate, and it claims no completed implementation.
> Basis: `tasks/B-budget.md`, `docs/req/requirements.yaml` (FR-002 / INV-002 / NFR-001 / NFR-002), `architecture-blueprint.md` §6, course Project Requirement Sheet D2.2 / D2.7, `docs/baseline.md`.
> Location: `tasks/plans/B/` (per `DEVELOPMENT-POLICY.md` §3, plans live here and are not written into `docs/approvals/`).

---

## 0. Goal in one sentence

Give one stock-analysis run a "finance department": **allocate a budget up front, check the balance before each call, degrade according to a predefined ladder when money runs short, and record every transaction** — so the system still produces a decision under a cost cap instead of dying mid-run.

## 1. Non-goals (explicitly out of scope)

| Not doing | Reason / owner |
|---|---|
| Deciding whether a trade proposal is legal (holdings, cash, long-only) | C (FR-003 / INV-003) |
| Binding debate claims to evidence | A (FR-001 / INV-001) |
| Separating `unavailable` from `unknown` data | D (FR-004 / INV-004) |
| Persisting and replaying audit records | E (FR-005 / INV-005) |
| Real billing (USD reconciliation) | No payment system in the course; cost is **derived** from tokens × unit price |
| Distributed / cross-process budget pool | A run is a single LangGraph process; no cross-process locking in M2 |
| Model routing optimisation (auto-pick cheapest model) | This module only makes the budget-triggered downgrade choice |
| Changing upstream config semantics (`max_tokens`, `llm_max_retries`, `max_debate_rounds`) | Existing upstream capability, not this feature; rewriting them would be answering a different question |

## 2. Budget model

### 2.1 Unit of measurement

| Unit | Role | Rationale |
|---|---|---|
| **tokens** | **Primary (hard constraint)** | The only quantity that can be estimated before a call and is independent of vendor pricing |
| call count | Secondary hard cap | Prevents "many small calls" from bypassing token estimates |
| cost (derived) | Reporting only | `tokens × unit price`; never used for enforcement |

### 2.2 Total and allocation

- **Total budget**: default `240,000 tokens` (baseline single run is 228,275, leaving ~5% headroom); configurable.
- **Allocation**: per-stage quotas (soft) plus a global pool (hard).

| Stage | Default quota | Note |
|---|---|---|
| Analysts (4, parallel) | 40% | Each analyst gets its own sub-quota |
| Bull/bear debate | 25% | Spread across rounds |
| Research manager | 8% | Single call |
| Trader | 7% | Single call |
| Risk debate | 15% | Spread across rounds |
| Portfolio manager | 5% | Final decision, **protected last** |

- **Soft quotas are borrowable**: a stage that finishes early can lend its remainder to later stages.
- **Three hard rules for borrowing**:
  1. No stage may consume the "final-decision reserve" (100% of the portfolio-manager quota is frozen).
  2. A single borrow may not exceed 30% of the global remainder.
  3. Every borrow emits a `budget_borrowed` event (auditable).

> Why not pure hard partitioning: fixed slices waste money when analysts are cheap and debates are expensive; pure soft allocation lets the most expensive stage eat the money reserved for the final decision.

### 2.3 Pre-call estimate (basis for `reserve`)

```
estimate = clamp( 1.3 × rolling mean of (agent, stage) historical usage,
                  floor 800 tokens,
                  ceiling remaining quota of the stage )
```

- Round up and keep a 30% margin (model output length is not controllable).
- Estimation error is corrected at settlement (§3.3).

## 3. Lifecycle

### 3.1 State machine

```
        reserve()                 settle()
  --------------> RESERVED --------------> SETTLED
        |                |
        | release()      | settle(actual > reserved)
        v                v
     RELEASED         OVER_BUDGET (recorded + fail-closed)
```

Per-reservation state: `reserved | settled | released`.
Ledger state: `open | exhausted | closed`.

### 3.2 Interface (aligned with `tasks/B-budget.md` §4)

```text
reserve(agent, stage, model_tier, estimate_tokens) -> Reservation | Denied
settle(call_id, actual_input_tokens, actual_output_tokens) -> Settlement
release(call_id, reason) -> None
remaining(scope="global" | stage_name) -> int
snapshot() -> dict            # consumed by E (audit) and by the report
```

### 3.3 Three hard constraints

1. **Reserve before call**: no `Reservation`, no LLM call (INV-002).
2. **Idempotent settlement**: repeated `settle` for the same `call_id` does not double-charge and returns the first result.
3. **Fail-closed on overrun**: if `actual > reserved` and the global remainder is exceeded, emit `over_budget` and stop further calls; never continue silently.

## 4. Degradation ladder (the core)

When budget is short the run must **not** be aborted; it degrades in the following order, and the level **never rises again** within a run (monotonic).

| Level | Action | Trigger | Quality cost | Reversible |
|---|---|---|---|---|
| **L0** | Normal | Budget sufficient | none | — |
| **L1** | Compress injected content (news 20 → 8 items, evidence summarised) | Stage remainder < 1.5 × next estimate | low | no |
| **L2** | Reduce debate rounds by one (minimum 1) | Stage remainder < 1 × next estimate | medium | no |
| **L3** | Downgrade model deep → quick | Global remainder < 15% | medium-high | no |
| **L4** | Skip optional agents (sentiment, then news, in that order) | Global remainder < 10% | high | no |
| **L5** | Emit a degraded verdict: PM may only output `hold` plus a `degraded` flag | Global remainder < 1 × next estimate | very high, but a decision exists | no |

Rules:

- Every degradation emits `budget_degraded{level, reason, remaining}`.
- Degradation must never be silent: the final report carries the highest level reached.
- **L5 is not a failure**: it is an explicitly declared degraded verdict, fundamentally different from a crash with no output.

## 5. Context compaction and constraint re-injection

Course D2.2 requires a token-budget cap, a compaction threshold, and a policy for re-injecting critical constraints after compaction.

| Parameter | Value | Note |
|---|---|---|
| `context_cap` | 16,000 tokens | Hard ceiling per call |
| `compact_threshold` | 12,000 tokens | Compaction starts above this |
| `compact_target` | 8,000 tokens | Target length after compaction |

Items that must be **re-injected on every assembly**, unaffected by compaction:

1. Safety constraints: `long-only`, no spending beyond cash/holdings, no real broker
2. Instrument and date (identity)
3. Current degradation level
4. Remaining budget (coarse, e.g. "below 20%")

> Verification: the assembled prompt must contain markers for all four classes; a missing class is an assembly failure (fail-closed).

## 6. Concurrency and atomicity

- The four analysts call the same budget pool **in parallel**.
- Implementation: a single-process `threading.Lock` guards ledger mutations; `reserve` is an atomic "check and charge".
- A two-step "read then charge" is forbidden (oversell race).
- Idempotency key: `call_id` (uuid4, generated by the caller).

## 7. Events and module contracts

### 7.1 Event shape (consumed by E; this module does not persist)

```json
{
  "event_id": "uuid",
  "ts": "ISO-8601",
  "type": "reserve|settle|release|borrow|degraded|compacted|over_budget|exhausted",
  "agent": "market_analyst",
  "stage": "analyst",
  "model_tier": "quick|deep",
  "estimate": 1200,
  "actual": 1180,
  "remaining_global": 98500,
  "remaining_stage": 12000,
  "level": 0,
  "reason": "stage_below_threshold"
}
```

### 7.2 Cross-module contracts

| Counterpart | Contract |
|---|---|
| A (evidence) | At L1 the evidence injector decides which items to drop; B only supplies the token allowance |
| C (safety) | The L5 `degraded` flag must reach C and must not be accepted as a normal proposal |
| D (data quality) | Low budget is **not** insufficient data; the two must never substitute for each other |
| E (audit) | B emits events only; persistence and replay belong to E |

## 8. Acceptance criteria (ready for `requirements.yaml`)

| ID | Criterion | How judged |
|---|---|---|
| AC-1 | With `limit_calls=10`, the 11th call is denied and zero LLM calls follow the denial | negative test |
| AC-2 | 8 threads reserving one call each against a 10-call limit → exactly 10 succeed | concurrency test |
| AC-3 | `settle` over the reservation and over the global remainder → `over_budget` recorded and the run stops | negative test |
| AC-4 | Repeated `settle` on one `call_id` charges once | idempotency test |
| AC-5 | Context above 12,000 → compaction triggers and all four constraint classes remain in the assembly | structural test |
| AC-6 | Degradation level never decreases within a run | invariant test |
| AC-7 | Same input → same event sequence (fixed estimate table) | determinism test |
| AC-8 | Token use at least 20% below baseline | evaluation (live or historical replay) |
| AC-9 | Decision quality regression at most 3 percentage points | evaluation (fixed case set) |

## 9. Proposed requirement changes (to be written into `docs/req/requirements.yaml`)

### 9.1 Rewrite FR-002

```yaml
  - id: FR-002
    type: functional
    statement: "A run must use a metered budget ledger: quotas are allocated per stage and role, every LLM call reserves before execution and settles afterwards, and exceeding the global budget fails closed on further calls while degrading along a predefined ladder instead of aborting the run."
    priority: must
    tradeoff: "Budget pressure may reduce analysis depth, in exchange for bounded cost and a usable decision."
    owner: B
    status: proposed
    invariants: [INV-002, INV-006]
    fit:
      metric: "LLM calls still executed after the budget is exceeded"
      threshold: 0
      verification: "Negative test + concurrency test (planned)"
    code_paths: ["tradingagents/course/budget/"]
```

### 9.2 New FR-006 (degradation policy)

```yaml
  - id: FR-006
    type: functional
    statement: "When budget is insufficient the run must degrade along the fixed ladder L1-L5 (compress injection, reduce debate rounds, downgrade model, skip optional agents, emit a degraded verdict); the level is monotonic within a run and every degradation produces a retrievable event with a reason."
    priority: must
    tradeoff: "Keeps a decision available at the cost of reduced depth in extreme cases."
    owner: B
    status: proposed
    invariants: [INV-006]
    fit:
      metric: "Degradations without a recorded reason"
      threshold: 0
      verification: "Negative test: force L1-L5 by lowering the budget (planned)"
    code_paths: ["tradingagents/course/budget/"]
```

### 9.3 New INV-006

```yaml
  - id: INV-006
    type: invariant
    statement: "The budget trajectory is monotonic: the degradation level never rises again within a run, and no degradation or overrun may occur without an event."
    priority: must
    tradeoff: "Removes the option to recover quota mid-run, in exchange for predictability and auditability."
    owner: B
    status: proposed
    fit:
      metric: "Level reversals plus undetected degradations"
      threshold: 0
      verification: "Invariant test (planned)"
```

> Adding IDs requires a matching update to `docs/architecture/trace-matrix.md`; otherwise `scripts/check_course.py` fails on incomplete trace coverage.

## 10. Risks and open questions

| # | Risk | Mitigation |
|---|---|---|
| R1 | Estimation bias causes frequent L1 | Historical mean plus 30% margin; log estimation error for later tuning |
| R2 | Degradation triggers too early and costs more quality than it saves | Configurable thresholds; calibrate on the fixed evaluation set |
| R3 | Event schema drifts from E's expectations | Freeze event fields first; E consumes read-only |
| R4 | Sub-quotas are hard to split across parallel analysts | Start with an even split, later weight by historical usage |
| R5 | Cost cannot be measured for real (no payment) | Estimate as tokens × published unit price; label it as an estimate in the report |

**Needs teammate confirmation**: whether the L3/L4 thresholds (15% / 10%) conflict with C's verdict ordering (does degradation happen before or after the safety verdict?).

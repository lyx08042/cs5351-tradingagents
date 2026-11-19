# 运行时策略目录（PROPOSED）

> 状态：**PROPOSED**。策略均为计划，**未实现**、**未激活**。
> 本文件集中描述 F1–F5 的运行时策略及其 fail-closed/abstain/review 行为。

## 1. 策略清单

| 策略 ID | 所属功能 | 触发条件 | 默认动作 | 需求锚点 |
|---|---|---|---|---|
| POL-EVD-01 | F1 证据 | 强断言无 evidence_ref | 标注/降级为假设 | FR-001, INV-001 |
| POL-EVD-02 | F1 证据 | 证据可用日期晚于分析日期（未来泄漏） | 排除 | FR-001, INV-001 |
| POL-EVD-03 | F1 证据 | 证据日期早于分析日期但超出新鲜度策略 | 标为 stale（可配置） | FR-001, INV-001 |
| POL-EVD-04 | F1 证据 | 预测性断言（未来价格等） | 始终标为 hypothesis | FR-001, INV-001 |
| POL-BUD-01 | F2 预算 | 预留后余额不足 | 拒绝调用（fail-closed） | FR-002, INV-002 |
| POL-BUD-02 | F2 预算 | 结算超预留 | 记录并终止后续 | FR-002, INV-002 |
| POL-SAF-01 | F3 安全 | 缺 holdings_snapshot | 拒绝提案 | FR-003, INV-003 |
| POL-SAF-02 | F3 安全 | Buy/Sell 时 units ≤ 0，或 price ≤ 0 | 拒绝提案（Hold 的 units=0 合法） | FR-003, INV-003 |
| POL-SAF-03 | F3 安全 | holdings 为空但未声明 flat | 拒绝 | FR-003, INV-003 |
| POL-SAF-04 | F3 安全 | Buy 超出 cash / Sell 超出持仓 | 拒绝 | FR-003, INV-003 |
| POL-SAF-05 | F3 安全 | LLM 文本自称安全但代码判据不满足 | 以代码 verdict 为准，拒绝 | FR-003, INV-003 |
| POL-DQ-01 | F4 数据 | 必需数据域 unavailable 或 unknown | abstain / review（default-deny） | FR-004, INV-004 |
| POL-DQ-02 | F4 数据 | 缺失被标 neutral | 拒绝该标签 | FR-004, INV-004 |
| POL-AUD-01 | F5 审计 | 覆盖终局决策 | 拒绝，要求 supersede | FR-005, INV-005 |
| POL-AUD-02 | F5 审计 | 回放不一致 | 标记 review | FR-005, INV-005 |
| POL-SEC-01 | 全局 | 真实券商执行请求 | 永久拒绝 | SEC-001, INV-003 |

## 2. 动作语义

- **fail-closed**：默认拒绝，不静默降级。
- **abstain**：明确输出“无法得出确定性结论”。
- **review**：升级人工复核，不自动通过。
- **记录**：所有拒绝/abstain/review 进入审计（INV-005）。

## 3. 配置化（PROPOSED）

- 阈值与策略为**可配置**参数，不作为性能结论。
- 配置变更需 ADR + 人工批准。

## 4. 当前状态

- 无任何策略代码；全部为设计。
  （例外：F2 预算的 POL-BUD 策略已实现并有测试，见第 5 节。）

## 5. F2 budget runtime policies (role B, implemented)

Status: **implemented** in `tradingagents/course/budget/policy.py` and covered by
`test/offline/test_budget*.py`. This section supersedes the "not implemented" status for F2 only; the other
modules remain design.

| Policy ID | Trigger | Action | Requirement |
|---|---|---|---|
| POL-BUD-01 | a reservation does not fit the stage quota after borrowing | refuse the call (`BudgetDenied`) | FR-002, INV-002 |
| POL-BUD-02 | settlement exceeds the reservation and the pool | emit `over_budget`, close the ledger, refuse further calls | FR-002, INV-002 |
| POL-BUD-03 | L1: remaining global budget below the projected remaining spend | compress injected content (news 20 → 8 items, evidence summarised) | FR-006 |
| POL-BUD-04 | L2: projection shortfall deeper than 0.85 | reduce debate rounds by one, minimum one | FR-006 |
| POL-BUD-05 | L3: projection shortfall deeper than 0.70 | force the cheap model tier (`deep` → `quick`) | FR-006 |
| POL-BUD-06 | L4: projection shortfall deeper than 0.55 | skip optional agents (sentiment, then news) | FR-006 |
| POL-BUD-07 | L5: remaining budget below one call estimate | emit an explicitly degraded verdict instead of aborting | FR-006, INV-006 |
| POL-BUD-08 | assembled context above 12,000 tokens | compact to 8,000 and re-inject the four constraint blocks | FR-002, D2.2 |
| POL-BUD-09 | a constraint block is missing after assembly | reject the assembly (fail-closed) | FR-002, D2.2 |

Semantics specific to F2:

- **Monotonic.** The level only rises within a run. `apply_level` is the single mutator and it always emits a
  `degraded` event; a caller that tries to lower the level raises `LevelRegression` (INV-006).
- **Projection, not fraction.** The trigger compares the remaining budget with the *projected* remaining
  spend when a forecast is available. Fixed fractions remain only as the fallback for callers without one;
  the fixed-fraction form degraded a run whose cap was above the baseline (BUG-004).
- **L3 changes price, not volume.** Downgrading the model tier does not reduce token count, so the catalogue
  does not claim a token saving from L3.
- **L5 is a verdict, not a failure.** The current implementation raises `BudgetExhausted`; mapping it to a
  portfolio-manager verdict needs the shared orchestrator.

Thresholds are configuration (`LedgerConfig`), not constants, and are marked provisional pending the
evaluation in `docs/architecture/evaluation-logbook.md`.

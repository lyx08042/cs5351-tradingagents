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

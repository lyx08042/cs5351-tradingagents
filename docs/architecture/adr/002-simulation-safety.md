# ADR-002：确定性模拟安全门（成员 C / F3）

- **状态：PROPOSED（待人工批准）**
- **日期：** 2026-11-11
- **决策者：** 成员 C（草稿作者）；非作者评审（M4）待办；不得虚构批准人
- **关联需求：** `FR-003`、`INV-003`、`SEC-001`、`NFR-003`
- **关联文档：** `architecture-blueprint.md`、`docs/architecture/invariants.md`、`docs/architecture/adr/001-course-extension.md`、`tasks/plans/C/FR-003-handoff.md`
- **课程差异：** 按 `DEVELOPMENT-POLICY.md`（ACTIVE, owner-selected, 2026-11-07）推进；课程 **G-1/D9 未满足**；**非教师 waiver、非伪造批准**。

> 本 ADR **未被批准**。它记录提案与待确认点；不代表 M3 已集成，也不代表 M4 已评审。

## 1. 背景

运行时 AI（TradingAgents 多智能体系统）会产生交易分析供评测，但课程设计**不连接真实券商**。LLM 输出可能是文本评级、理由和不完全结构化的建议；若直接把文本当作可执行交易，既不可复现，也无法保证资金/持仓约束。

F3 需要在候选与任何模拟执行之间加入一个**确定性、可离线回放**的安全门。候选及其自报的余额、持仓、规则版本、`safe`/`approved` 声明均不可信；判定必须只使用独立可信输入。

## 2. 决策

在 `tradingagents/course/safety/` 提供纯函数校验器：

```python
validate_proposal(proposal, *, context: SafetyContext) -> SafetyVerdict
```

- 候选只产生结构化 `SimulationProposal`：`action`、`units`、`price`、`currency`、`holdings_snapshot`、`rule_version`、`status`。
- 判定由确定性代码给出；候选文本、`status` 或自报安全声明不能覆盖代码 verdict。
- `SafetyVerdict` 含稳定 `reason_code`、`status`、可信 `snapshot_id`/`rule_version`、`is_noop`、`ignored_claims`，并提供 `to_dict()` 供离线回放。
- 不连接真实券商，不访问网络/凭证；真实执行请求永久拒绝。
- 未接入正常入口前，C 只提供可离线调用的独立模块（M2）；不发布“已验证模拟提案”。

## 3. 可信输入与防伪造

`SafetyContext` 必须由调用方从**独立可信来源**构造，而不是从候选复制：

| 字段 | 可信来源要求 |
|---|---|
| `instrument` / `instrument_currency` | 运行标的与其报价币种，由编排器绑定 |
| `holdings_snapshot` | 来自 `PortfolioContext` 或团队指定账户源；必须保留“有持仓 / 显式空仓 / 无上下文”三态 |
| `rule_set` | 团队规则目录中的固定条目；当前只实现显式 long-only |
| `available_rule_versions` | 可信规则目录允许的版本集合 |

防伪造规则：

1. 候选的 `holdings_snapshot` 只能是可信 `snapshot_id` 引用，或与可信快照**内容完全一致**的对象；校验只使用可信快照计算。
2. 候选自带的余额、持仓、`rule_version`、`status`、`safe`/`approved` 等均视为**未信任声明**；不一致即拒绝，被忽略的声明记录在 `ignored_claims`。
3. 缺失快照**不得**默认 flat；空持仓必须 `flat_declared=true`，否则 `undeclared_flat`。
4. 规则版本缺失、未知或与可信固定版本不一致时拒绝。
5. 候选快照中的额外字段不参与可信比较；但若核心字段与可信快照不一致，拒绝。

## 4. 当前实现规则范围

- `buy` / `sell`：`units > 0`；`hold`：`units == 0` 且标记 `is_noop=True`。
- `units < 0`：拒绝（当前显式 long-only scope，不是通用“禁止负值”）。
- `price`：必须有限且 `> 0`。
- `currency`：必须匹配标的报价币种；可信快照币种也必须匹配。
- `buy`：`units * price <= trusted.cash`，否则 `insufficient_cash`。
- `sell`：`units <= trusted position`，否则 `insufficient_holdings`。
- 可信快照现金 `< 0` 拒绝；持仓 `< 0` 拒绝。
- 金额与数量使用 `Decimal`；float 经 `Decimal(str(value))` 转换，避免二进制浮点边界误差。
- 买成本使用显式 `decimal.Context`（固定 precision/范围/舍入/clamp/traps，不继承调用者状态）；超界或不精确返回 `amount_precision_unsupported`。
- 非法 `SafetyContext.rule_set` 类型返回 `invalid_rule_set`；拒绝路径不二次抛异常。
- 真实执行意图（`execute`/`place_order`/`live`/`broker` 等）在其它字段校验前拒绝。

## 5. 明确不在本轮实现（不虚构策略）

- 参考价偏离阈值 / 滑点上限。
- 手续费、税费、舍入公式。
- 额外仓位上限、集中度限制。
- 做空、保证金、杠杆。
- 任何真实券商适配器或订单写入。

上述均为**待确认输入**，不得以默认值冒充策略。

## 6. M3 集成边界与待确认输入

已核对当前真实入口：

- `TradingAgentsGraph.record_decision()`：`tradingagents/graph/trading_graph.py:359`，`propagate()` 与 CLI 的共同收尾点。
- CLI 收尾：`cli/run.py:353` 调用 `graph.record_decision(...)`。
- Portfolio Manager 当前只产出 `final_trade_decision` 文本与 `final_rating`：`tradingagents/agents/managers/portfolio_manager.py:78-86`；**没有**结构化 `action/units/price`。
- 账户上下文：`tradingagents/portfolio.py:33-38`（`PortfolioContext`），文件头明确区分“有持仓 / 空仓 / 无上下文”。

最小后续改动（协调 PR，M3 待办）：

1. 由协调 PR 在 `record_decision()` 汇合点之前，取得一个**结构化候选**（来源与 owner 待确认）。
2. 从可信账户源与规则目录构造 `SafetyContext`；无上下文时不得构造为 flat。
3. 调用 `validate_proposal`，仅当 `accepted` 时发布“已验证模拟提案”；拒绝时保留原因码供 E 审计，原始文本仍作为分析证据。
4. 不改变既有 `final_rating`/报告/返回语义；不新增真实执行路径。

待确认输入：

- 结构化候选的字段来源与 owner（Trader/PM 新增结构化输出，还是单独候选生产者）。
- 报价/执行参考价来源与币种口径（用于现金校验）。
- `PortfolioContext` → `HoldingsSnapshot` 的映射：`cash`/`currency`/`positions`、`as_of`、`flat_declared`。
- 规则目录与版本固定方式（谁维护 `RuleSet`、如何 pin）。
- `Hold` 是否必须携带价格字段（当前契约固定字段含 `price`，测试沿用任务书示例要求有限正值）。
- 与 D 的数据状态、与 E 的审计/回放字段（决定、原因码、提案关联 ID、快照引用、规则版本）。

## 7. 验证结果（2026-11-11，Codex 独立运行）

OpenCode 本会话未运行 shell；以下由 Codex 独立执行：

- 课程离线测试：`python -m pytest -q -o testpaths=test/offline test/offline` -> **76 passed**（原有脚手架 20，C 新增 56）。
- 脚手架校验：`python scripts/check_course.py --root .` -> **OK**。
- 全仓库 `ruff check .` -> **通过**（三处 UP037 已由本 OpenCode 会话修复：仅移除 `from __future__ import annotations` 下多余的注解引号，行为不变）。
- 上游完整回归（允许本机回环连接并使用工作区临时目录）-> **1407 passed, 6 skipped, 1 deselected, 24 warnings, 100 subtests passed in 41.30s**。
- 第一次受限环境出现临时目录权限与回环连接失败；修正运行环境后通过。

## 8. 后果与里程碑

- M2：C 独立模块与离线测试已完成，准备上传到 `feat/C-safety`；实际上传状态以 GitHub 分支为准。
- M3：正常入口集成待协调 PR；当前未改共享 CLI/图节点/CI，也未发布已验证提案。
- M4：非作者（B）评审待办；本 ADR 保持 **PROPOSED**，不得声称已批准。
- 课程 G-1/D9 未满足；这是 owner 选择的流程差异，不是教师 waiver，也不是伪造批准。
- 不连接真实券商；拒绝路径不写订单/现金/持仓。

## 9. 重开条件

出现以下任一情形必须重开本 ADR：

1. 安全规则范围变更（新增滑点、费用、仓位上限等）。
2. 可信输入来源或 `PortfolioContext` 三态语义变更。
3. 需要真实券商执行（**当前明确排除**）。
4. 正常入口集成需要改变既有报告/评级/返回语义。
5. 非作者评审或 CI 发现本 ADR 的契约不成立。

## 10. 批准记录

- 批准人：**待人工填写（不得虚构）**
- 批准日期：**待填**
- 关联 commit：**待填**

> 在本节被真实人工填写之前，本 ADR 保持 **PROPOSED**。

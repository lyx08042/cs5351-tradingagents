# Trace 矩阵（PROPOSED）

> 状态：**PROPOSED**。覆盖关系是**计划**，不代表已实现。
> 每行对应 `docs/req/requirements.yaml` 中**一个真实需求 ID**。列含义：强制组件 → 提议代码路径 → 计划测试/证据 → 运行时监控。
> 代码路径 `tradingagents/course/**` **当前不存在**；所有测试/监控均为 **planned**。
> `scripts/check_course.py` 要求本文件出现**每一个** registry 需求 ID；缺失即校验失败（不得弱化检查）。

## 1. 基线需求（BASE）

| 需求 | 强制组件 | 提议代码路径 | 测试/证据（planned） | 运行时监控 |
|---|---|---|---|---|
| BASE-001 | 上游 `TradingAgentsGraph` 公共导入与主流程 | `tradingagents/graph/trading_graph.py`、`cli/main.py`（只读，不改） | 冒烟导入 + 主流程 smoke（planned） | 导入失败即 CI 失败 |
| BASE-002 | 上游测试套件 | `tests/`（冻结） | `pytest` 全量回归（既有基线，见 `docs/baseline.md`） | CI 测试通过率 |

## 2. 功能需求（FR）

| 需求 | 强制组件 | 提议代码路径 | 测试/证据（planned） | 运行时监控 |
|---|---|---|---|---|
| FR-001 | 证据绑定校验器（A） | `tradingagents/course/evidence/` | 有证据通过 + 无证据降级负向测试 | 无证据断言比例 |
| FR-002 | 预算账本 reserve/settle（B） | `tradingagents/course/budget/` | 超预算拒绝负向测试 | 预算耗尽事件 |
| FR-003 | 确定性提案校验器（C） | `tradingagents/course/safety/` | 缺快照/非法 units/未声明 flat 负向测试 | 拒绝事件与原因 |
| FR-004 | 数据状态标签 + default-deny unknown（D） | `tradingagents/course/data_quality/` | unavailable 被标 neutral 负向测试；unknown/缺失默认拒绝 | unavailable / unknown 比例 |
| FR-005 | 追加式审计 + supersede 链 + 回放（E） | `tradingagents/course/audit/` | 覆盖终局决策被拒 + 回放一致性 | 修订次数、回放差异 |

## 3. 非功能需求（NFR）

| 需求 | 强制组件 | 提议代码路径 | 测试/证据（planned） | 运行时监控 |
|---|---|---|---|---|
| NFR-001 | 预算账本（B）成本统计 | `tradingagents/course/budget/` | 重复评估对照（临时 20% 目标） | 令牌/成本统计 |
| NFR-002 | 预算 + 证据（B/A）质量对照 | `tradingagents/course/budget/`、`tradingagents/course/evidence/` | 固定评估集对照（≤3pp 临时目标） | 评估分数 |
| NFR-003 | 安全 + 审计（C/E）确定性回放 | `tradingagents/course/safety/`、`tradingagents/course/audit/` | 重复回放一致率测试 | 回放差异计数 |
| NFR-004 | 审计（E）留痕 | `tradingagents/course/audit/` | 拒绝/abstain 事件留痕覆盖测试 | 留痕覆盖率 |
| NFR-005 | 结构与契约（共同） | `docs/code-governance/structural-constraints.md` + 各 `tradingagents/course/*/` | 导入方向结构性检查 + 契约变更 ADR 审阅 | 循环导入检查（planned） |

## 4. 不变量（INV）

| 需求 | 强制组件 | 提议代码路径 | 测试/证据（planned） | 运行时监控 |
|---|---|---|---|---|
| INV-001 | 证据绑定校验（A） | `tradingagents/course/evidence/` | 无证据强断言被拒/降级 | 无证据断言比例 |
| INV-002 | 账本预留/结算原子性（B） | `tradingagents/course/budget/` | 超预算调用被拒；重复结算幂等 | 预算耗尽事件 |
| INV-003 | 提案确定性校验（C） | `tradingagents/course/safety/` | 缺快照/非法 units/未声明 flat 被拒 | 拒绝事件 |
| INV-004 | 状态标签校验（D） | `tradingagents/course/data_quality/` | unknown/缺失不当中性被拒 | unavailable / unknown 比例 |
| INV-005 | 追加式存储 + 修订链（E） | `tradingagents/course/audit/` | 覆盖终局决策被拒；回放一致性 | 修订次数、回放差异 |

## 5. 治理需求（GOV）

| 需求 | 强制组件 | 提议代码路径 | 测试/证据（planned） | 运行时监控 |
|---|---|---|---|---|
| GOV-001 | 人工批准门 + PR 模板 | `docs/approvals/README.md`、`templates/*.md`、`.github/PULL_REQUEST_TEMPLATE.md` | 人工流程审阅（无自动强制，automation pending） | N/A（流程控制，非运行时监控） |
| GOV-002 | 诚实记录与禁止伪造 | `docs/ai-use-log.yaml`、`docs/review-memo.md`、`docs/bug-diary.md`、`docs/debt-register.md` | 人工审阅 | N/A（流程控制，非运行时监控） |

## 6. 安全需求（SEC）

| 需求 | 强制组件 | 提议代码路径 | 测试/证据（planned） | 运行时监控 |
|---|---|---|---|---|
| SEC-001 | 提案校验器 + 无真实执行路径（C） | `tradingagents/course/safety/` | 安全负向测试 + 代码审阅 | 拒绝事件（真实执行请求） |

## 7. 覆盖规则

- 每个功能需求（FR）至少映射一个不变量与一个负向测试（planned）。
- 每个不变量（INV）作为独立行列出，不得只靠 FR 行间接出现。
- `scripts/check_course.py` 校验 registry 中**每个**需求 ID 在本文件出现；缺失即非零退出。
- 治理需求（GOV）的监控列可标注 N/A，但必须给出**理由**（流程控制，非运行时监控）。

## 8. 当前状态

- 所有“测试/证据”“运行时监控”列均为 **planned**；当前没有实现。
- 上游 `tests/` 是既有回归基线，不属于本矩阵的 F1–F5 覆盖。

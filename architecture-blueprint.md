# 架构蓝图（PROPOSED）— CS5351 TradingAgents 课程扩展

> ## ⚠️ CURRENT OVERRIDE：`DEVELOPMENT-POLICY.md`（ACTIVE, owner-selected, 2026-11-07）
> 下方所有旧的实现前计划/测试/安全批准、`PENDING`、STOP 要求均为 **HISTORICAL / NOT EXECUTED**，不再阻断你自己任务的实现。写计划+测试设计（工作文档）后**继续实现**，无需 `approval_refs`。**最终 PR + 非作者评审 + CI + 合并授权保留**。课程 **G-1/D9 未满足**；**非教师 waiver、非伪造批准**。本文件的 `PROPOSED` 状态**不**因本政策变为 `APPROVED`。开始前对 feature 分支 `git fetch origin` + `git merge origin/main`（不 reset、不 force）。

> **状态：PROPOSED（待学生批准）**。本文件是**提案基线**，不是已达成的实现，也不构成课程合规声明。
> **规范源**：本文件是权威副本；`docs/architecture/architecture-blueprint.md` 只是指针。
> **基线**：上游 TauricResearch/TradingAgents v0.7.1，commit `9fa1196fffbcfd9de5146d2dd2869df84ab99838`。
> **目录提示**：本文件当前位于仓库根。若教师确认要求 `docs/architecture/` 布局，需人工迁移；本仓库**不声称**根布局已被接受。

---

## 1. 背景与范围

### 1.1 现有系统（上游 v0.7.1，**不是**新功能）

上游已实现并保留以下能力；任何课程报告或演示都**不得**把它们算作本团队的新增功能：

- 并行分析师（fundamentals / sentiment / news / market）
- 每次调用的 token 配置（`max_tokens`、各 tier 配置）
- 辩论轮次与工具轮次上限（`max_debate_rounds`、`max_risk_discuss_rounds`、`max_tool_rounds`）
- LLM 重试预算（`llm_max_retries`）
- 结构化输出 schema（research manager / trader / portfolio manager）
- LangGraph checkpoint 与 resume
- Memory log（决策记忆 + 反思结算）
- 报告（HTML / Markdown）与完整测试套件
- 多 provider、多市场、point-in-time 数据约束

模块映射见 `src/README.md` 与 `test/README.md`。

### 1.2 课程扩展范围（F1–F5，**未实现**）

| 功能 | 命题 | 提议归属 | 提议代码位置（当前不存在） |
|---|---|---|---|
| **F1** 证据约束辩论 | 辩论中的断言须绑定到已检索证据（evidence-grounded） | A | `tradingagents/course/evidence/` |
| **F2** 运行预算 | 为一次分析运行设置可计量、可拒绝的预算（调用/令牌/成本） | B | `tradingagents/course/budget/` |
| **F3** 确定性模拟安全 | 将交易提议约束为确定性、可复现的模拟提案（无真实执行） | C | `tradingagents/course/safety/` |
| **F4** 全局数据充分性 | 明确区分 *不可用（unavailable）* 与 *中性（neutral）*，并据此 gate | D | `tradingagents/course/data_quality/` |
| **F5** 可验证审计 | 不可变审计、最终决策权威、决策修订与离线 gate 回放 | E | `tradingagents/course/audit/` |

> **重要**：`tradingagents/course/**` 目录当前**不存在**，也没有任何文件。它们只是本提案中的**计划路径**，不是已完成代码。

---

## 2. 架构驱动因素与设计目标

| 驱动 | 说明 | 相关需求 |
|---|---|---|
| 可验证性 | 任何断言、预算、安全、数据、审计结论都可被结构化检查与回放 | FR-001, FR-002, FR-005 |
| 缺失语义清晰 | “拿不到数据”与“数据表示中性”严格区分 | FR-004 |
| 默认拒绝 | 任何不确定/超限/缺失都必须 fail-closed 或 abstain | INV-001..005 |
| 可审计但不伪造 | 审计记录不可篡改，决策可修订且保留历史 | FR-005 |
| 无真实执行 | 只有模拟提案，永不触达真实券商 | FR-003, SEC-001 |
| 成本可控 | 20% 成本下降目标（临时），质量不劣化 ≤3 个百分点 | NFR 组 |

## 3. 权威性与咨询性（Advisory vs Authoritative）

| 组件 | 权威性 | 说明 |
|---|---|---|
| 运行时 AI 智能体（分析师/研究员/交易员/风控/PM） | **咨询性（advisory）** | 其输出是建议；不得直接产生可执行后果 |
| 安全模块（F3，C 负责） | **权威性** | 对模拟提案做确定性合法性判定；违规即拒绝 |
| 预算模块（F2，B 负责） | **权威性** | 超预算即拒绝后续调用 |
| 数据充分性（F4，D 负责） | **权威性** | 数据不足即 abstain 或降级为 review |
| 审计模块（F5，E 负责） | **权威性（终局）** | 最终决策与修订历史以审计记录为准 |
| 证据模块（F1，A 负责） | 咨询性 + 约束 | 约束辩论引用，但不直接决定交易 |

权威性意味着：**当模块判定拒绝，运行必须服从，不得被 LLM 文本覆盖**。

## 4. 组件与边界

### 4.1 提议模块布局

```
tradingagents/
  course/                 # PROPOSED，当前不存在
    evidence/             # A：证据检索、断言绑定、引用校验
    budget/               # B：预算账本、预留、结算、拒绝
    safety/               # C：模拟提案 schema、确定性规则、失效关闭
    data_quality/         # D：数据充分性、unavailable vs neutral
    audit/                # E：审计记录、决策修订、离线回放
```

### 4.2 模块职责与不变量锚点

- **evidence（A）**：从已获取的工具输出/报告中提取证据单元，给断言分配 evidence_ref；无证据的强断言必须标注或降级。锚点：`INV-001`。
- **budget（B）**：在调用前**预留（reserve）**、调用后**结算（settle）**；超额 fail-closed。锚点：`INV-002`。
- **safety（C）**：LLM 只产生结构化候选；由**确定性代码**给出 accept/reject verdict。缺失 holdings 快照不默认 flat；缺失快照或规则版本则拒绝；Hold 为 `units=0` 合法。锚点：`INV-003`。
- **data_quality（D）**：把每个数据域标为 `available | unavailable | unknown`，`neutral` 只能是显式的数据语义，不得用默认值冒充；unknown 默认拒绝。锚点：`INV-004`。
- **audit（E）**：追加式不可变记录；终局决策唯一；修订以 supersede 链保存；支持离线 gate 回放。锚点：`INV-005`。

### 4.3 叶子模块与薄编排器

- 五个叶子模块**不得相互循环导入**；依赖方向为单向或经共享契约。
- **薄编排器（thin orchestrator）**由**共同**所有，只能在协调 PR 中编辑。编排器只做顺序编排与契约转换，不承载业务规则。

## 5. 集成契约（PROPOSED）

### 5.1 关键 schema 契约

- **不可用 vs 中性**：
  - `DataStatus = "available" | "unavailable" | "unknown"`
  - 当 `unavailable` 或 `unknown` 时，任何下游**不得**把缺失值当作 `neutral`（default-deny unknown）。
- **预算账本**：`BudgetLedger` 含 `reserve()`、`settle()`、`remaining()`；状态 `reserved | settled | released`。
- **模拟提案（SimulationProposal）**：`action`、`units`、`price`、`currency`、`holdings_snapshot`、`rule_version`、`status`；Hold 用 `units=0`，Buy/Sell 需 `units>0`。
- **证据**：`published_at`/`available_as_of` 必须 `<=` 分析日期，可按可配置新鲜度策略判定，证据日期可早于分析日；预测性断言恒为 hypothesis。
- **审计**：`AuditRecord` 不可变；`final_decision` 唯一权威；`superseded_by` 形成修订链。

### 5.2 契约约束

- 所有契约必须可 JSON 序列化，便于离线回放与测试。
- 契约变更需 ADR + 人工批准（见第 9 节）。

## 6. 智能体工作流（PROPOSED 分层运行时上下文）

提议的运行时上下文分层（**计划中的设计，不是已达成事实**）：

```
identity → constraints → retrieved evidence → conversation → state → task
```

- `identity`：ticker、asset_type、日期（确定性来源）。
- `constraints`：预算、安全规则版本、权限。
- `retrieved evidence`：已绑定证据。
- `conversation`：辩论历史。
- `state`：LangGraph 状态快照。
- `task`：当前子任务。

建议的上下文流水线（PROPOSED）：`dedup → prioritize → budget → compact → assemble`。

> **注意**：cap **16000 tokens** 与 compaction 阈值 **12000 tokens** 是**计划中的可配置设计阈值**，**不是**已达成事实，也**不是**性能结论。

## 7. 权限模型（默认拒绝）

- 默认 **no read / no write**。
- 实际生效的是 `opencode.json`（全局并集白名单）；按角色（A–E）的路径白名单定义在 `.opencode/permissions.jsonc`。
- 秘密/元数据冻结（任何角色不得读写）：`.env*`、auth、`.git/**`。
- 既有源码/测试/构建默认受保护、不整树替换；窄范围集成编辑需显式 scope + 契约 + 人工批准（见 `docs/architecture/permission-model.md`）。
- **声明**：`.opencode/permissions.jsonc` 是**课程制品**，OpenCode **不会自动加载**；`opencode.json` 白名单是**全局并集**，因此**不提供**可执行的按角色隔离。更强的 per-role profiles **待实现**，当前依赖人工流程与评审。

## 8. 验证与监控（PROPOSED，planned）

- **结构层**：schema/契约/导入方向检查（planned）。
- **回归层**：上游测试 `tests/` 必须保持通过（BASE-002）。
- **行为层**：F1–F5 各自的正向 + 负向测试（planned）。
- **监控**：预算耗尽事件、fail-closed 事件、unavailable 比例、审计修订次数、回放一致性（planned，目前无运行监控）。
- 课程脚手架当前仅做 schema/trace 引导检查，**不是**六道 gate 的完整实现。

## 9. 变更政策

- 架构契约、安全规则、预算策略、审计权威性：**必须有 ADR + 人工批准**。
- 提示词/模型：先固定评估集并先评测。
- 目录迁移（如根 `architecture-blueprint.md` → `docs/architecture/`）：需教师确认后由人工执行。
- 变更需更新 trace 矩阵与验证约束。

## 10. 明确不做的事

- 不连接真实券商，不下真实订单，不做资金转移。
- 不伪造运行时结果、评估分数或批准。
- 不把上游既有能力重新包装为新功能。
- 不声称本蓝图已批准或已合规。

## 11. 相关文档

- `docs/architecture/invariants.md`
- `docs/architecture/trace-matrix.md`
- `docs/architecture/memory-design.md`
- `docs/architecture/permission-model.md`
- `docs/architecture/runtime-policy-catalog.md`
- `docs/architecture/adr/001-course-extension.md`
- `docs/req/requirements.yaml`
- `docs/code-governance/structural-constraints.md`

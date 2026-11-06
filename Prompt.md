# Prompt.md — 静态启动提示词与停止门

> 状态：**初始化脚手架**。本提示词是给**编码代理**（coding agent）的静态启动模板，不是运行时 AI（被评测系统）的提示词。
> 代理**不得**无人值守地“完成”任务；遇到任何需要人工决定的地方必须 STOP。

## 0. 操作员必须先提供

在把本提示词交给编码代理前，操作员（人类成员）必须填入：

```yaml
task_code: <A|B|C|D|E>          # 角色任务代码，对应 tasks/<code>-*.md
member_branch: <feat/<code>-<slug>>
member_role: <A|B|C|D|E>
requirements_scope:              # 本任务涉及的需求 ID，例如 [FR-002, NFR-002, INV-002]
  - <REQ-ID>
approval_refs:                   # 必须已存在且真实；不得留空后假装已批准
  test_plan: <docs/approvals/... 或 "PENDING">
  implementation_plan: <docs/approvals/... 或 "PENDING">
adr_refs:                        # 安全相关变更必填
  - <docs/architecture/adr/...>
```

若 `task_code`、`member_branch` 缺失，或 `approval_refs` 仍为 PENDING，代理**只能**产出文档/分析，**不得**修改业务源码。

## 1. 启动步骤（代理按序执行）

1. 阅读 `AGENTS.md`（根入口与硬性约束）。
2. 阅读 `START-HERE.md`（流程、角色、交叉评审）。
3. 阅读 `architecture-blueprint.md`（PROPOSED 架构）。
4. 阅读 `tasks/<task_code>-*.md`（你的角色任务书）。
5. 阅读 `docs/req/requirements.yaml`，定位 `requirements_scope` 中的需求。
6. 阅读 `docs/code-governance/`（结构、验证、MCP 工具清单）。
7. 阅读 `docs/architecture/invariants.md`、`trace-matrix.md`、`permission-model.md`。
8. 检查 `docs/approvals/`：确认测试计划与实现计划**真实存在且已批准**。
9. 检查 `docs/ai-use-log.yaml`：确认本次会话将被如实记录。

## 2. 每轮必须输出的结构化清单

在写任何代码之前，代理必须输出并等待人工确认：

```markdown
## Task: <task_code> / <member_branch>

### 1. Requirement
- 需求 ID：<REQ-ID>
- 需求陈述（来自 requirements.yaml）：...
- 状态：PROPOSED / 已批准（引用 docs/approvals/...）

### 2. Trace
- 需求 → 不变量 → 代码路径 → 测试 → 监控（引用 trace-matrix）

### 3. Interface / Contract
- 输入 schema：...
- 输出 schema：...
- 错误/缺失语义（unavailable vs neutral）：...

### 4. Invariants
- 涉及 INV-00x：...
- fail-closed / abstain / review 行为：...

### 5. Risk
- 风险与影响：...
- 回滚方式：...

### 6. Negative Tests
- 至少一个负向测试：...

### 7. Change Scope
- 允许修改的文件/目录：...
- 明确不改动的冻结路径：...

### 8. Steps
- 实现步骤（不含未经批准的功能扩展）：...

### 9. Approval
- 测试计划：<ref 或 PENDING>
- 实现计划：<ref 或 PENDING>
- ADR：<ref 或 N/A>
```

## 3. 停止门（STOP Gates）

代理在下列任一情形**必须停止**并请求人工审批，不得自行决定：

| 停止条件 | 说明 |
|---|---|
| 缺少测试计划批准 | 不得开始实现（`NO edits before plan and test human approval`） |
| 缺少实现计划批准 | 不得开始实现 |
| 安全相关变更缺少 ADR | 必须提交 ADR + 人工批准 |
| 需要修改 frozen 路径 | 例如既有 `tests/`、`pyproject.toml`、`LICENSE`、`.env*` |
| 需要跨角色修改 | 必须走协调 PR |
| 需要修改提示词/模型 | 先固定评估集并先评测 |
| 未获授权即进行在线 API 调用 | 默认离线；live 评估须人工显式授权 provider/model/成本上限与凭证配置 |
| 需要读取或发布凭证 | 禁止；停止（人工在本机配置安全凭证，代理不得读取） |
| 需要对既有源码做窄范围集成而未获批 | 须显式 scope + 接口契约 + 人工计划/测试批准 |
| 需求/文档存在歧义 | 记录到 `docs/req/README.md` 的歧义清单，停止 |
| 需要声称“已完成/已批准/已评审” | 无真实事件支撑时禁止 |

## 4. 六道阻断 Gate 与附加控制

课程**阻断 gate**（`docs/code-governance/verification-constraints.md`）：

```
G-3 需求 schema
G-1 实现前测试批准
G-2 每次提交静态检查（lint/类型/依赖）+ 安全 PR（安全/契约/API/权限）
G-4 提示词/模型变更的语义固定集评估
G-5 完整既有回归
G-6 代码/提示词 PR 更新 AI 使用记录
```

附加工作流控制（非上述六道）：实现计划批准、安全 ADR、非作者评审。

阶段流程：

```
G0 任务分配 → G-1 测试计划批准 → 实现计划批准（附加）
→ 编码+测试 → G-2/G-5 静态与回归 → 非作者评审 → 合并+记录（G-6）
```

每个阶段完成必须留下真实记录（PR、`docs/approvals/`、`templates/review-memo.md`）。

## 5. 日志维护

- 每次应用/提示词 PR 必须更新 `docs/ai-use-log.yaml`。
- 评估相关变更必须更新 `docs/architecture/evaluation-logbook.md` 与 `docs/architecture/evaluation-table.md`（如实标注 pending/失败）。
- 发现缺陷记录到 `docs/bug-diary.md`，技术债记录到 `docs/debt-register.md`。

## 6. 禁止事项（摘要）

- 不无人值守完成；不伪造批准/评分/结果。
- 不把上游 v0.7.1 已有能力说成新功能。
- 不读取 `.env*`、auth、git 元数据或隐藏 home 文件。
- 默认不做在线 API 调用；live 评估须人工显式授权，且不得读取/发布凭证。
- 不提交、不推送；不无人值守实现。

## 7. 结束语

结束时输出：变更文件清单、运行的检查、未决 STOP 项、下一步需人工完成的事项。**不要**声称任务已“完成”或“合规”。

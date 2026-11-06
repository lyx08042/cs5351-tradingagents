# AGENTS.md — 编码代理根入口

> 适用于所有在本仓库工作的编码代理（包括 OpenCode）。本文件是根入口；先读它，再读下列文件。
> 本文档为**初始化脚手架**。路由到业务源码的改动**尚未**被任何人工批准；F1–F5 也**未被批准实施**。

## 0. 术语：运行时 AI ≠ 编码代理

- **运行时 AI（runtime AI）**：被评测的 TradingAgents 多智能体系统（分析师、研究员、交易员、风控、组合经理）。它产生交易分析，本课程设计上**不连接真实券商**。
- **编码代理（coding agent）**：修改本仓库代码/文档的 AI 工具（例如 OpenCode）。它受本文件与 `Prompt.md` 约束。
- 两者互不替代。禁止把编码代理的行为或能力说成运行时 AI 的能力，反之亦然。

## 1. 必读文件（按顺序）

1. `START-HERE.md` — 五人流程与角色
2. `Prompt.md` — 静态启动提示词与**停止门**
3. `architecture-blueprint.md` — PROPOSED 架构基线（规范源）
4. 你的任务书：`tasks/<A|B|C|D|E>-*.md`
5. `docs/req/requirements.yaml` — 需求注册表
6. `docs/code-governance/structural-constraints.md`、`verification-constraints.md`、`mcp-tool-manifest.md`
7. `docs/architecture/invariants.md`、`trace-matrix.md`、`permission-model.md`

## 2. 业务编码只由 OpenCode 完成

- 业务源码（`tradingagents/**`、`cli/**` 及未来 `tradingagents/course/**`）的编码**只能通过**受本文件约束的编码代理完成。
- **禁止**绕过代理直接手工修补业务代码（“no direct manual code repair”）。人工可做的是：审阅、批准、写需求/测试计划、评审、提交记录。
- 既有源码/测试/构建默认受保护、不整树替换基线；集成所需的**窄范围编辑**同样由 OpenCode 在获批后完成（见第 5 节）。
- 文档与模板可人工撰写，但同样应如实记录 AI 使用（`docs/ai-use-log.yaml`）。

## 3. 先确认角色与任务范围

- 每次开始前，检查你被分配的**角色/任务范围**（`tasks/`）。只在你负责的模块内修改。
- 跨角色修改（例如 C 修改 B 的预算账本）必须走协调 PR，并在 PR 模板中说明。
- 提议的模块归属：证据 A、预算 B、安全 C、数据质量 D、审计 E。叶子模块**不得**相互循环导入；薄编排器由**共同**所有，只能在协调 PR 中编辑。

## 4. 批准门（硬性）

以下必须在**编码之前**完成，且只能由**人类成员**产生：

1. **功能/实现计划批准**：`templates/implementation-plan.md` → `docs/approvals/`
2. **测试计划批准**：`templates/test-plan.md` → `docs/approvals/`
3. **安全相关变更**：ADR（`docs/architecture/adr/`）+ 人工批准

- 没有上述批准，**不得**开始实现。
- **NO edits before plan and test human approval.**
- **NO invented approvals.** 不得在 `docs/approvals/` 中写入任何未真实发生的批准记录；不得编造评审人、时间戳或 commit。
- 提示词/模型变更：必须先固定评估集（`docs/evaluation/cases.yaml`）并先做评估。

## 5. Human-only 路径与受保护路径（代理不得编辑）

**真正只允许人类撰写/批准的路径：**
- `.opencode/rules.md` — 未获批的人工占位文件（见第 6 节）
- `docs/approvals/**` — 人工批准记录

**默认受保护（deny 编辑）的治理基础设施：**
- `.github/**`（工作流、PR 模板等）、`scripts/**`、`AGENTS.md`、`Prompt.md`、`opencode.json`

> 若确需变更治理基础设施，由**人类成员显式授权**一次**窄范围**配置/会话（写明 scope），随后由 **OpenCode 生成代码**，经非作者评审后**恢复保护**。课程采用 agentic development，**不要求**所有 CI 代码由人类手工编写。

**既有业务源码/测试/构建**（`tradingagents/**`、`cli/**`、`tests/**`、`pyproject.toml`）默认受保护，**不得整树替换基线**。窄范围集成编辑仅在同时满足以下条件时允许：显式书面 scope + 接口契约 + 人工实现/测试计划批准（安全相关再加 ADR）。

## 6. `.opencode/rules.md` 的特殊地位

- `.opencode/rules.md` 当前是**AI 生成的脚手架占位文件**，**不是**人工撰写或批准的政策。
- 真正草案在 `docs/code-governance/human-rules-draft.md`，须由团队人类成员审阅后**人工转移并批准**。
- 引导完成后，**代理不得再编辑** `.opencode/rules.md`。
- `.opencode/permissions.jsonc` 是**课程制品**，OpenCode **不会**自动加载；它**不构成**可执行的运行时角色隔离。
- `opencode.json` 的 permission 白名单是**全局并集**：五类角色的允许路径都在其中，因此**不能**仅凭配置断言“角色已隔离”。角色纪律目前依赖**人工流程**，更强的按角色生成配置（per-role profiles）**尚待实现**。

## 7. 测试不得被静默削弱

- 不得删除、跳过、放宽断言，或以 mock 替换真实行为来“让测试通过”。
- 不得修改既有 `tests/` 来迁就新代码；上游测试是 BASE-002 的约束。
- 每个功能至少一个**负向测试**；测试必须由批准的计划约束，且由**非作者**评审。
- 结构性、回归性、行为性三层验证见 `docs/code-governance/verification-constraints.md`。

## 8. 安全变更

- 任何失败/失效（fail / 失效）必须 **fail-closed**（默认拒绝），不得静默降级。
- 涉及交易安全、预算、审计权威性的变更：必须提交 ADR（`docs/architecture/adr/001-course-extension.md` 为样例）+ 人工批准。
- 本系统**没有真实券商执行**；任何“下单”仅为模拟提案。

## 9. 上下文新鲜度

- 你的理解必须基于**当前**仓库与该 sprint 的文档；不要依赖过期的对话记忆。
- 变更前重读相关 `docs/` 与 `tasks/`；记录发现的不一致到 `docs/debt-register.md` 或 `docs/bug-diary.md`。

## 10. 显式命令（安全、只读优先）

以下命令供本地人工执行；代理在 shell 被禁用/需批准时不得自行运行可能泄露秘密的命令。

```bash
# 仅课程脚手架校验（schema + 唯一 id + trace 覆盖 + 必需文件）
python scripts/check_course.py --root .

# 课程脚手架负向/正向测试
pytest -o testpaths=test/offline test/offline/test_course_scaffold.py

# 上游完整测试（历史基线，见 docs/baseline.md）
pytest

# 代码风格（不自动修复业务逻辑）
ruff check .
```

## 11. 引导现状

- 本次初始化的**业务源码与既有测试未被修改**；`pyproject.toml`、依赖、`LICENSE` 未改。
- 新增文件均为文档、治理与引导 CI。见仓库根 `docs/baseline.md` 与 `docs/course-requirements-checklist.md` 的真实状态表。

## 12. 参考链接（仓库内）

- 流程：`START-HERE.md`
- 提示词：`Prompt.md`
- 架构：`architecture-blueprint.md`，`docs/architecture/architecture-blueprint.md`（指针）
- 需求：`docs/req/requirements.yaml`，`docs/req/README.md`，`docs/req/req-schema.json`
- 治理：`docs/code-governance/*.md`
- 不变量：`docs/architecture/invariants.md`
- 批准：`docs/approvals/README.md`
- 角色任务：`tasks/README.md` 与 `tasks/A-*.md` … `tasks/E-*.md`
- 提交与 GitHub：`docs/github-setup.md`，`docs/submission-checklist.md`
- 课程对照：`docs/course-requirements-checklist.md`
- AI 使用记录：`docs/ai-use-log.yaml`

## 13. 底线

不伪造；不越权；不先写代码后补批准；不把模板当完成；不声称课程合规。遇到不确定，**停止并请求人工审批**（见 `Prompt.md` 的 STOP 语义）。

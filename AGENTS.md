# AGENTS.md — 编码代理根入口

> 适用于所有在本仓库工作的编码代理（包括 OpenCode）。
> **最高项目政策优先级：`DEVELOPMENT-POLICY.md`（ACTIVE, owner-selected, 2026-11-07）。** 与本文冲突时以它为准。
> 本文其余关于“实现前必须人工批准 / PENDING / STOP”的表述，除下文明确保留者外，均为 **HISTORICAL（不执行）**。课程要求仍作为**参考义务**保留，未被取消；本仓库**不声称**课程合规。

## 0. 术语：运行时 AI ≠ 编码代理

- **运行时 AI（runtime AI）**：被评测的 TradingAgents 多智能体系统。产生交易分析，课程设计上**不连接真实券商**。
- **编码代理（coding agent）**：修改本仓库代码/文档的 AI 工具（例如 OpenCode）。
- 两者互不替代；禁止把编码代理的行为说成运行时 AI 的能力，反之亦然。

## 1. 必读文件（按顺序）

1. `DEVELOPMENT-POLICY.md` — **ACTIVE 工作流（最高优先级）**
2. `START-HERE.md` — 五人流程与角色
3. `Prompt.md` — 静态启动提示词
4. `architecture-blueprint.md` — PROPOSED 架构基线（规范源）
5. 你的任务书：`tasks/<A|B|C|D|E>-*.md`
6. `docs/req/requirements.yaml` — 需求注册表
7. `docs/code-governance/*.md`、`docs/architecture/invariants.md`、`trace-matrix.md`、`permission-model.md`

## 2. 活跃工作流（见 `DEVELOPMENT-POLICY.md` 全文）

- 先 `git fetch origin` + `git merge origin/main` 到自己的 feature 分支，再在本任务范围内改本模块。
- **写实现计划与测试设计（工作文档，非批准门）后即可继续实现**，不必等待 leader 或任何人工的测试/实现/ADR 预批准。
- **绝不**仅因 `PENDING`、缺失的计划批准文件、或 `proposed` 需求而等待。
- 安全/接口变更：创建 ADR/设计记录（`docs/architecture/adr/`），但**无实现前批准人**。
- 在已分配的**模拟**范围内，**无需**逐个功能的实现前人工安全批准。
- `approval_refs` 不需要。缺失批准文件/`PENDING`/`proposed` 状态**不是阻断项**。
- 真实受监督编码 transcript 与诚实的 `docs/ai-use-log.yaml` 记录照旧；不得伪造任何结果/批准/身份/测试。
- **最终 PR + 非作者评审 + CI + 合并授权仍保留；不自动合并到 `main`。**

## 3. 角色与任务范围（保留）

- 只在你负责的模块内修改（提议归属：证据 A、预算 B、安全 C、数据质量 D、审计 E）。
- 跨角色修改（例如 C 修改 B 的预算账本）必须走协调 PR。
- 叶子模块**不得**相互循环导入；薄编排器由**共同**所有，只能在协调 PR 中编辑。

## 4. 业务编码只由 OpenCode 完成（保留）

- 业务源码（`tradingagents/**`、`cli/**`、及未来 `tradingagents/course/**`）只能通过受本文约束的编码代理完成；禁止绕过代理手工修补业务代码。
- 既有源码/测试/构建默认受保护、不整树替换基线；集成所需的窄范围编辑由 OpenCode 在获批 scope 内完成（见第 6 节）。

## 5. 不伪造（保留）

- **NO invented approvals.** 不得在 `docs/approvals/` 写入未真实发生的批准；不得编造评审人、时间戳或 commit。真实历史批准保持原样。
- 不得把 PROPOSED 说成 APPROVED；不得声称教师合规或 waiver。

## 6. Human-only / 受保护路径（保留）

**人类专属（代理不得编辑）：** `.opencode/rules.md`（人类专属历史占位，**不编辑**，不是本政策可改的对象）、`docs/approvals/**`。

**默认受保护（deny 编辑）的治理基础设施：** `.github/**`、`scripts/**`、`AGENTS.md`、`Prompt.md`、`opencode.json`。确需变更时由人类显式授权一次窄范围会话，OpenCode 生成、经非作者评审后恢复保护（本次 owner 授权的政策变更即属例外）。

**既有业务源码/测试/构建**（`tradingagents/**`、`cli/**`、`tests/**`、`pyproject.toml`）默认受保护，不得整树替换基线。窄范围集成编辑需：明确 scope + 接口契约（实现前人工批准不再是硬门，改由 owner 选择的活跃工作流）。

## 7. `.opencode/rules.md` 与 `.opencode/permissions.jsonc`（保留）

- `.opencode/rules.md` 是 **AI 生成的、人类专属的未批准占位历史文件**；代理**不得编辑**。真正草案在 `docs/code-governance/human-rules-draft.md`。
- `.opencode/permissions.jsonc` 是**课程制品**，OpenCode **不自动加载**，**不构成**可执行的运行时角色隔离。
- `opencode.json` 的 permission 白名单是**全局并集**，不能仅凭配置断言“角色已隔离”。

## 8. 测试不得被静默削弱（保留）

- 不得删除、跳过、放宽断言，或以 mock 替换真实行为。
- 不得修改既有 `tests/` 来迁就新代码；上游测试是 BASE-002 的约束。
- 每个功能至少一个**负向测试**；测试由**非作者**评审。
- 三层验证见 `docs/code-governance/verification-constraints.md`。

## 9. 安全（保留）

- 任何失败/失效必须 **fail-closed**，不得静默降级。
- 安全/接口变更：创建 ADR/设计记录（无实现前批准人，见 `DEVELOPMENT-POLICY.md`）。
- 本系统**没有真实券商执行**；任何“下单”仅为模拟提案。
- 技术性 permission 提示（shell/外部 API）与计划批准**不同**，**不**被本政策绕过。

## 10. 上下文新鲜度（保留）

- 基于**当前**仓库与本 sprint 文档；不要依赖过期对话记忆。
- 变更前重读 `DEVELOPMENT-POLICY.md`、`docs/`、`tasks/`；发现不一致记录到 `docs/debt-register.md` 或 `docs/bug-diary.md`。

## 11. 显式命令（安全、只读优先）

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

## 12. 参考链接（仓库内）

- **政策：`DEVELOPMENT-POLICY.md`**
- 流程：`START-HERE.md`；提示词：`Prompt.md`；架构：`architecture-blueprint.md`
- 需求：`docs/req/requirements.yaml`；治理：`docs/code-governance/*.md`
- 不变量：`docs/architecture/invariants.md`；角色任务：`tasks/README.md`、`tasks/A-*.md`…`E-*.md`
- 提交/GitHub：`docs/github-setup.md`、`docs/submission-checklist.md`；课程对照：`docs/course-requirements-checklist.md`
- AI 使用记录：`docs/ai-use-log.yaml`

## 13. 底线

不伪造；不越权；不把模板当完成；不声称课程合规。遇到真实的**范围外 / 不可逆 / 凭证**问题，才请求用户输入（不是例行计划批准）。

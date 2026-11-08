# TradingAgents — CS5351 课程团队仓库

> ## ⚠️ 当前生效政策（CURRENT OVERRIDE）：`DEVELOPMENT-POLICY.md`（ACTIVE, owner-selected, 2026-11-07）
>
> - Owner `@lyx08042` 于 2026-11-07 当前对话中**显式决定取消所有成员的实现前批准**（在被告知这违反课程实现前测试/计划批准要求之后）。由 **Codex 编排 OpenCode** 记录，**非教师批准**。
> - 这是**用户选择的课程偏离**，**不是 waiver、不是伪造批准**。缺失课程 **G-1** 与 **D9** 计划/停止要求；本仓库**不声称课程合规**。
> - **工作流不再等待**：写计划+测试设计（工作文档）→ 在自己模块实现/测试/评审修复 → 最终 PR + 非作者评审 + CI + 合并授权。无需 `approval_refs`。
> - 开始前对自己的 feature 分支执行 `git fetch origin` 与 `git merge origin/main`（不 reset、不 force）。下方旧表述为 **HISTORICAL（不执行）**。

本仓库是基于上游 [TauricResearch/TradingAgents](https://github.com/TauricResearch/TradingAgents) 的 **Team fork**，用于 CityU **CS5351** 五人课程小组的协作、治理与扩展。上游原文保留在 [`README.upstream.md`](README.upstream.md)。

- 团队仓库：<https://github.com/lyx08042/cs5351-tradingagents>（public）
- 上游基线：v0.7.1，commit `9fa1196fffbcfd9de5146d2dd2869df84ab99838`
- 本仓库当前状态：**初始化脚手架**。现有业务源码（`tradingagents/`、`cli/`、`tests/`）与 `pyproject.toml` **未被修改**；新增内容为文档、治理与 CI 引导文件。

> 本文档只是起点。所有架构与需求文档当前状态为 **PROPOSED（待学生批准）**。本仓库**不声称**已完全满足课程要求；课程 D1-D9 与六道 gate 的真实状态见 `docs/course-requirements-checklist.md`。

## 五步快速开始（详见 [`START-HERE.md`](START-HERE.md)）

1. **克隆团队仓库**（不是上游 fork 的个人仓库）：
   ```bash
   git clone https://github.com/lyx08042/cs5351-tradingagents.git
   cd cs5351-tradingagents
   ```
2. **准备 Python ≥ 3.11 环境**：
   ```bash
   python -m venv .venv
   source .venv/bin/activate          # Windows: .venv\Scripts\activate
   pip install -e '.[dev]'
   pip install -r requirements-course.txt
   ```
3. **按顺序阅读**：`START-HERE.md` → `AGENTS.md` → `Prompt.md` → `architecture-blueprint.md` → 你被分配的 `tasks/<code>-*.md` → `docs/req/requirements.yaml` → `docs/code-governance/`。
4. **在个人分支开发，向团队仓库提 PR**（不向上游提 PR）。先 `git fetch origin` + `git merge origin/main` 取得当前政策；按 `DEVELOPMENT-POLICY.md` 先写计划+测试设计（工作文档）然后继续实现，无需 `approval_refs`。
5. **API 凭证仅保存在本机**，绝不入库、不写进 transcript。离线测试与在线测试分开（见 `test/README.md`）。

## 关键事实（避免误解）

- 上游 v0.7.1 **已经具备**：并行分析师、每次调用 token 配置、辩论/工具轮次上限、重试、结构化 schema、checkpoint、memory、报告与测试。**这些不是**本团队的新功能，不得在报告或视频中宣称为新实现。
- 本团队计划的功能（F1–F5）**尚未实现**，当前目录 `tradingagents/course/` **不存在**（蓝图中的 PROPOSED 路径）。
- 运行时 AI（被评测的交易分析系统）与本仓库的编码代理（OpenCode）是**两个不同主体**，见 `AGENTS.md`。
- 模板不承诺完成度；任何“已完成/已批准/已评审”的标记只能由真实事件与真实签名产生。

## 文档地图

| 文件 | 作用 | 状态 |
|---|---|---|
| `START-HERE.md` | 五人上手流程与分工 | 脚手架 |
| `DEVELOPMENT-POLICY.md` | **ACTIVE owner-selected 工作流（最高优先级）** | 政策 |
| `AGENTS.md` | 编码代理入口与硬性约束 | 脚手架 |
| `Prompt.md` | 静态启动提示词与停止门 | 脚手架 |
| `architecture-blueprint.md` | PROPOSED 架构基线 | 提案 |
| `docs/req/requirements.yaml` | 需求注册表（含 BASE/FR/NFR/INV/GOV/SEC） | 提案 |
| `docs/code-governance/` | 结构与验证约束、MCP 工具清单 | 提案 |
| `tasks/` | A–E 五个角色任务书（自包含提示词） | 脚手架 |
| `templates/` | 交接、测试计划、实现计划、评审等模板 | 模板 |
| `Report.md` | 课程报告提纲（非最终报告） | 提纲 |
| `docs/course-requirements-checklist.md` | D1-D9 与六道 gate 的真实状态 | 事实台账 |
| `docs/baseline.md` | 上游基线与一次运行的实际证据（脱敏） | 事实台账 |
| `docs/ai-use-log.yaml` | 真实 AI 使用记录 | 事实台账 |
| `docs/approvals/README.md` | 人工批准格式（当前无批准记录；实现前批准已由 owner 取消——见 `DEVELOPMENT-POLICY.md`） | 人类专属 |
| `docs/evaluation/` | 固定评估集（人工设计）与评估说明 | planned |
| `.agent/rules.md` | 编码代理脚手架契约（AI 生成） | 脚手架 |
| `.opencode/rules.md` | **未获人工批准的占位**（人类专属） | 占位 |
| `docs/architecture/` | 不变量、trace 矩阵、ADR、权限、评估与风险台账 | 提案 |
| `test/` | 离线/在线测试说明与课程脚手架的负向测试 | 脚手架 |
| `.github/workflows/course-bootstrap.yml` | 仅校验课程脚手架 schema/trace | 引导 CI |

## 课程与合规提示

- 本仓库**未**声称满足课程全部要求，也**未**获得教师对目录布局迁移的确认；布局是否接受以教师答复为准。
- `.opencode/permissions.jsonc` 是**课程制品**，不会被 OpenCode 自动加载，**不提供**真实的运行时角色隔离。
- `.opencode/rules.md` 是**未获人工批准的占位文件**；真正的规则草案在 `docs/code-governance/human-rules-draft.md`，需由团队成员人工审阅后转移并批准。
- 本仓库为研究用途，不构成任何投资建议；**没有真实券商下单**，交易决策仅为模拟提案。

上游完整说明（安装、CLI、记忆日志、回测、复现性等）请阅读 [`README.upstream.md`](README.upstream.md) 与 [`src/README.md`](src/README.md)。

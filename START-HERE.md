# START-HERE — CS5351 五人小组启动流程

> 状态：**初始化脚手架（initial scaffolding）**。本文件由编码代理起草，真实批准与实施需由五名成员人工完成。
> 本文件不承诺任何交付完成度；模板与门禁不会替人产生“已完成”。

## 1. 仓库与访问

团队仓库（public）：<https://github.com/lyx08042/cs5351-tradingagents>

```bash
git clone https://github.com/lyx08042/cs5351-tradingagents.git
cd cs5351-tradingagents
```

- 个人开发一律使用**个人分支 + 向本团队仓库提 PR**；**不要**向官方上游 `TauricResearch/TradingAgents` 提 PR。
- **重要限制**：若你只在 AI 工具的对话框里提供这个 URL，而该运行环境没有文件系统与仓库写权限，AI **无法**编辑或推送文件。你需要在本地 git 环境中操作，或使用具备明确仓库写权限并由你授权的工具。
- 所有 GitHub 设置（Actions、分支保护、CODEOWNERS）由**仓库 owner** 在网页端人工完成，见 `docs/github-setup.md`。本地文件不会自动修改远端设置。

## 2. 环境准备（Python ≥ 3.11）

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e '.[dev]'
pip install -r requirements-course.txt
```

- `pip install -e '.[dev]'`：安装上游包及开发依赖（pytest、ruff 等），来源 `pyproject.toml`。
- `pip install -r requirements-course.txt`：课程脚手架额外依赖（`jsonschema`、`PyYAML`），仅用于校验课程文档，不改变业务依赖。

**API 凭证仅在本地环境变量或本地 `.env` 中配置**，绝不提交、绝不写入 transcript 或报告。仓库中 `.env*`、auth、`.git/` 路径禁止被代理读取或编辑（见 `opencode.json`）。

### OpenCode 配置（真实生效的部分）

- 实际生效的是根目录 `opencode.json`（`$schema: https://opencode.ai/config.json`），它加载 `.agent/rules.md` 与 `.opencode/rules.md` 作为 `instructions`。
- 权限语法与语义参考官方文档：<https://opencode.ai/docs/permissions/>（路径白名单、`ask`/`allow`/`deny`、`external_directory`、`webfetch`）。
- rules 加载机制参考：<https://opencode.ai/docs/rules/>。
- 默认拒绝：读/写默认 deny，只对本仓库文档、测试、源码与治理文件按路径放行；`.env*`、auth、`.git/**` 一律 deny。
- 源码集成的编辑为 **ASK**（需人工确认），受保护治理路径与人类专属路径为 **DENY**。
- `.opencode/permissions.jsonc` 是**课程制品**，OpenCode **不会**自动加载，**不提供**角色隔离。`opencode.json` 的路径白名单是**全局并集**，角色隔离目前依赖人工流程。
- 不要把任何密钥写进配置；本仓库配置不包含 model/provider 或 secret。

## 3. 阅读顺序（按此顺序）

1. `START-HERE.md`（本文件）
2. `AGENTS.md` — 编码代理入口与硬性约束
3. `Prompt.md` — 静态启动提示词与停止门
4. `architecture-blueprint.md` — PROPOSED 架构基线（是否迁到 `docs/architecture/` 待教师确认）
5. 你被分配的角色任务书：`tasks/A-evidence.md` / `B-budget.md` / `C-safety.md` / `D-data-quality.md` / `E-audit.md`
6. `docs/req/requirements.yaml` 与 `docs/req/README.md` — 需求注册表与工作流
7. `docs/code-governance/` — 结构性约束、验证约束、MCP 工具清单
8. `docs/architecture/` — 不变量、trace 矩阵、权限模型、评估、风险与选项台账
9. `Report.md`、`templates/`、`transcripts/README.md` — 交付物与记录规范

## 4. 五个角色（F1–F5 与 A–E）

| 角色代码 | 负责功能 | 任务书 | 提议的源码路径（PROPOSED） |
|---|---|---|---|
| A | F1 证据约束辩论（evidence-grounded debate） | `tasks/A-evidence.md` | `tradingagents/course/evidence/` |
| B | F2 运行预算（run budget） | `tasks/B-budget.md` | `tradingagents/course/budget/` |
| C | F3 确定性模拟安全（deterministic simulation safety） | `tasks/C-safety.md` | `tradingagents/course/safety/` |
| D | F4 全局数据充分性（unavailable vs neutral） | `tasks/D-data-quality.md` | `tradingagents/course/data_quality/` |
| E | F5 可验证审计 + 决策修订 + 离线 gate 回放 | `tasks/E-audit.md` | `tradingagents/course/audit/` |

> 上述 `tradingagents/course/**` 目录**当前不存在**；它们是 PROPOSED 设计。是否采用该布局以及是否必须迁移到课程要求目录，**以教师答复为准**。成员身份与姓名**未知/待填**，不得虚构。

**交叉评审环**：A 评审 B，B 评审 C，C 评审 D，D 评审 E，E 评审 A。评审人不得是作者本人。交接方向与之对应：A→E、B→A、C→B、D→C、E→D。

**五角色轮换（仅流程角色，功能责任不变）**：A–E 模块负责人固定；每个 sprint 在 coordinator / architect / OpenCode build operator / verifier / reviewer-release 之间轮换。见 `tasks/README.md`。

## 5. 工作流（每个变更都必须遵守）

1. **先看角色与任务范围**：确认你改动的模块属于你的角色职责；跨角色修改需协调 PR。
2. **先写测试计划，并取得人工批准**：使用 `templates/test-plan.md`，记录到 `docs/approvals/`，在**实现之前**获得批准。
3. **获得功能计划批准**：使用 `templates/implementation-plan.md`，同样走人工批准。
4. **实现**：通过 OpenCode/编码代理完成业务编码（见 `AGENTS.md` 的硬性约束）。
5. **提交 PR**：使用 `.github/PULL_REQUEST_TEMPLATE.md`，如实填写 gate 状态。
6. **人工评审**：评审人非作者；记录到 `templates/review-memo.md`。
7. **合并后更新**：`docs/ai-use-log.yaml`、`docs/architecture/evaluation-logbook.md`、按需更新交接与债务台账。

### 测试与计划批准（硬性顺序）

```
先测试计划批准 → 再实现计划批准 → 然后编码 → 再评审 → 再合并
```

没有批准不得开始实现。**提示词/模型变更**必须先固定评估集（`docs/evaluation/cases.yaml`），先评测再改。

## 6. 离线测试 vs 在线测试

- **离线测试**：不访问网络、不调用真实 LLM/API，可在 CI 中稳定运行。见 `test/offline/README.md`。
- **在线测试**：需要真实 API key 与外部行情/LLM 服务。默认不进行；人工可**显式授权** provider/model/成本上限与安全凭证配置后，在本地运行。**不得**进入公共 CI、不得读取或发布凭证、不得写入公开 transcript。见 `test/live/README.md`。
- 上游测试套件位于 `tests/`（历史基线），课程脚手架测试位于 `test/offline/`。两者互不覆盖。

## 7. 记录与提交

- **transcript**：每人提交一份**完整、带注释的原始会话记录**，命名为 `studentid-name`，放在 `transcripts/`。**不要**提交空的或伪造的记录；不要包含 API key、个人信息或未公开数据。规范见 `transcripts/README.md`。
- **视频**：**10 分钟**视频作为**独立交付物**提交，**不放入**代码提交 ZIP；无需为视频单独创建 ZIP。
- **提交 ZIP**：排除 `.git/`、`.venv/`、密钥文件、大体积原始数据；**10 分钟视频作为独立交付物提交，不放入项目 ZIP**（不要求为视频单独创建 ZIP）。见 `docs/submission-checklist.md`。

## 8. 你绝不能做的事

- 不伪造人工批准、学生身份、运行结果、功能完成、评审记录、bug 或 transcript。
- 不声称任何 PROPOSED 文档已被教师批准或课程合规。
- 不把上游 v0.7.1 已有的能力（并行分析师、token 配置、重试、checkpoint、memory、报告、测试等）说成新功能。
- 不承诺“按模板提交即完成”；模板只提供结构，真实完成度取决于实际实现、测试与人工评审。
- 不读取环境/认证文件、环境变量秘密、外部目录或隐藏 home 文件；默认不做在线 API 调用（live 评估须人工显式授权，且不得读取/发布凭证）。

## 9. 当前状态一览

| 项目 | 状态 |
|---|---|
| 上游业务源码与测试 | 未修改，见 `docs/baseline.md` |
| 课程架构/需求 | **PROPOSED**，待学生批准 |
| 课程脚手架 CI | 仅 schema/trace 引导检查，**不是**全部六道 gate |
| 测试/计划批准自动化 | **PENDING**，目前人工流程 |
| F1–F5 实现 | **未实现** |

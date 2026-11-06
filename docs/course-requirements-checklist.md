# 课程要求对照表（D1–D9 与六道 gate）

> 状态：**事实台账**。本表如实标注**已存在 / 部分 / 未完成 / PENDING**。**不**声称课程合规。
> 校验机制见 `scripts/check_course.py`（仅 schema/trace）与 `docs/code-governance/verification-constraints.md`。

## 1. D1–D9 映射

| 编号 | 要求（概括） | 对应文件/机制 | 真实状态 |
|---|---|---|---|
| D1 | 项目/仓库与基线 | `README.md`、`README.upstream.md`、`docs/baseline.md` | 已存在（基线记录） |
| D2 | 需求工程（可度量） | `docs/req/requirements.yaml`、`req-schema.json`、`docs/req/README.md` | PROPOSED（未批准） |
| D3 | 架构设计（模块边界/权威性） | `architecture-blueprint.md`、`docs/architecture/adr/001-course-extension.md` | PROPOSED |
| D4 | 治理（审批、评审、AI 记录） | `AGENTS.md`、`Prompt.md`、`docs/approvals/`、`docs/ai-use-log.yaml`、`templates/` | 机制存在；批准记录为空 |
| D5 | 测试（三层 + 负向） | `tests/`（基线）、`test/`（脚手架）、`docs/code-governance/verification-constraints.md` | 仅脚手架 + 基线；行为层未实现 |
| D6 | 代码实现 F1–F5 | `tradingagents/course/**` | **未实现（目录不存在）** |
| D7 | 评估 | `docs/evaluation/`、`docs/architecture/evaluation-table.md` | planned，无结果 |
| D8 | 文档/报告/视频 | `Report.md`、`transcripts/`、`docs/submission-checklist.md` | 提纲/模板，未完成 |
| D9 | 提交与诚信 | `docs/submission-checklist.md`、`docs/github-setup.md` | 待人工执行 |

## 2. 六道阻断 Gate 真相表（精确）

| Gate | 描述 | 实现状态 | 说明 |
|---|---|---|---|
| G-1 实现前测试批准 | 人工 | **PENDING** | 无自动化；无批准记录 |
| G-2 每次提交静态检查（lint/类型/依赖）+ 安全 PR（安全/契约/API/权限） | 继承 CI + 扩展 | lint 继承上游 `ci.yml`（存在）；类型/依赖与安全 PR 审查 **PENDING**；fork Actions owner 启用 **PENDING** |
| G-3 需求 schema | `scripts/check_course.py` | **已实现**（本地校验通过后）；CI 需 owner 启用 |
| G-4 提示词/模型变更语义固定集评估 | 固定集 + rubric | **PENDING**（无运行器） |
| G-5 完整既有回归 | 上游 `pytest`（BASE-002） | 继承 `ci.yml`（存在）；fork Actions/分支保护 owner 启用 **PENDING** |
| G-6 代码/提示词 PR 更新 AI 使用记录 | `docs/ai-use-log.yaml` | **PENDING**（人工流程） |

> 本表的 gate 定义与 `docs/code-governance/verification-constraints.md` 一致。实现计划批准、安全 ADR、非作者评审是**附加工作流控制**，不属于这六道阻断 gate。
> 引导 CI（`.github/workflows/course-bootstrap.yml`）**只**覆盖 G-3 的 schema/trace 部分；不得被表述为“六道 gate 已通过”。

## 3. Owner 需人工完成的事项

- 在 fork/团队仓库启用 GitHub Actions（见 `docs/github-setup.md`）。
- 保护 `main`：要求 PR + 至少 1 名审批 + 状态检查；不得绕过。
- 填写真实 GitHub 身份；`CODEOWNERS` 可选（待定，不得用无效占位）。
- `.github/**` 变更需人工评审；这是治理基础设施，需人工授权窄范围变更。

## 4. 诚实声明

- 本仓库**未**达到课程全部要求；本表不是合规证明，且**不**自动强制任何 gate。
- G-1/G-2 扩展/G-4/G-6 的自动化为 PENDING；目前依赖人工流程。

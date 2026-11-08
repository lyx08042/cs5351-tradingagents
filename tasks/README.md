# 任务书总览（A–E）

> ## ⚠️ CURRENT OVERRIDE：`DEVELOPMENT-POLICY.md`（ACTIVE, owner-selected, 2026-11-07）
> 下方**所有**旧的实现前计划/测试/安全批准、`PENDING`、STOP 要求均为 **HISTORICAL / NOT EXECUTED**，不再阻断你自己任务的实现。写计划+测试设计（工作文档）后**继续实现**，无需 `approval_refs`。**最终 PR + 非作者评审 + CI + 合并授权保留**。课程 **G-1/D9 未被满足**；**非教师 waiver、非伪造批准**。`PROPOSED` 不因本政策变为 `APPROVED`。开始前对自己的 feature 分支 `git fetch origin` + `git merge origin/main`（不 reset、不 force）。

> 状态：**初始化脚手架**。每个任务书是**自包含、可复制**的编码代理提示词，受 `DEVELOPMENT-POLICY.md`（最高优先级）与 `AGENTS.md` 约束。
> 成员姓名/学号**未知**；不得虚构。

## 1. 功能责任（**稳定，不轮换**）

A–E 是**模块/功能所有者**，整个课程中**固定不变**。每位成员始终负责自己的模块与自己的 transcript。

| 角色 | 功能 | 任务书 | 需求 | 不变量 | 提议源码路径（PROPOSED） |
|---|---|---|---|---|---|
| A | F1 证据约束辩论 | `tasks/A-evidence.md` | FR-001（关联 NFR-002, NFR-005） | INV-001 | `tradingagents/course/evidence/` |
| B | F2 运行预算 | `tasks/B-budget.md` | FR-002（关联 NFR-001, NFR-002） | INV-002 | `tradingagents/course/budget/` |
| C | F3 确定性模拟安全 | `tasks/C-safety.md` | FR-003, SEC-001（关联 NFR-003） | INV-003 | `tradingagents/course/safety/` |
| D | F4 数据充分性 | `tasks/D-data-quality.md` | FR-004（关联 NFR-004） | INV-004 | `tradingagents/course/data_quality/` |
| E | F5 可验证审计 | `tasks/E-audit.md` | FR-005（关联 NFR-004, NFR-005） | INV-005 | `tradingagents/course/audit/` |

## 2. 交叉评审环（无歧义）

| 作者 | 产出交给（Handoff） | 由谁评审 |
|---|---|---|
| A | **E** | A 评审 **B** |
| B | **A** | B 评审 **C** |
| C | **B** | C 评审 **D** |
| D | **C** | D 评审 **E** |
| E | **D** | E 评审 **A** |

即：A 评审 B；B 评审 C；C 评审 D；D 评审 E；E 评审 A。
随之 A→E、B→A、C→B、D→C、E→D 的**交接方向**。评审人**不得**是作者本人。评审记录使用 `templates/review-memo.md`。

## 3. 工作流角色轮换（**只轮换流程角色**）

功能责任不变；以下**流程角色**每 sprint 轮换。成员编号 M1–M5 为占位（真实身份待填）。

五个工作流角色：
- **coordinator**（协调、排期、gate 追踪）
- **architect**（契约/ADR/INV 一致性）
- **OpenCode build operator**（驱动编码代理、控制 scope）
- **verifier**（测试/证据/回放核查）
- **reviewer/release**（非作者评审汇总、提交打包）

| Sprint | M1 | M2 | M3 | M4 | M5 |
|---|---|---|---|---|---|
| S1 | coordinator | architect | build operator | verifier | reviewer/release |
| S2 | reviewer/release | coordinator | architect | build operator | verifier |
| S3 | verifier | reviewer/release | coordinator | architect | build operator |
| S4 | build operator | verifier | reviewer/release | coordinator | architect |
| S5 | architect | build operator | verifier | reviewer/release | coordinator |

> 无论流程角色如何轮换，每人**始终**负责自己的 A–E 模块与自己的 transcript。

## 4. 七类交接信息（每个任务书/交接都含）

1. **需求 + fits**：需求 ID、statement、`fit.metric/threshold/verification`。
2. **设计/接口/ADR/INV**：契约、接口、ADR 引用、不变量与 fail-closed 行为。
3. **代码 + 测试 + PR + 计划记录（可选历史批准引用）**：变更文件、测试、PR、以及计划/测试设计工作文档；`docs/approvals/` 的历史批准引用为**可选**（不再必需）。
4. **实际评估/配置/结果**：固定评估集、模型/配置、实际结果（如实，含失败）。
5. **完整原始会话 + 独立干预注释**：`transcripts/<studentid-name>/raw.md`（只读）+ `annotations.md`（单独）。
6. **AI 使用/评审/bug/债务/变更记录**：`docs/ai-use-log.yaml`、`docs/review-memo.md`、`docs/bug-diary.md`、`docs/debt-register.md`。
7. **报告贡献 + 300–500 词个人反思 + 姓名/学号贡献证据 + 演示材料**：`Report.md` 对应章节、`templates/member-reflection.md`、演示脚本/截图。

> 模块路径、需求、约束**不是**“七类交付物”；它们是上述条目中的**内容**。

## 5. 通用工作约束（所有任务，见 `DEVELOPMENT-POLICY.md`）

- 写计划 + 测试设计（工作文档，非批准门）后直接实现；`approval_refs` 不需要，`PENDING`/缺失批准/`proposed` 状态**不是阻断项**。
- 既有 `TradingAgents` 源码/测试/构建默认受保护，**不得整树替换基线**；窄范围集成编辑需明确 scope + 接口契约。
- 安全/接口变更创建 ADR/设计记录，但**无实现前批准人**。
- 治理基础设施（`.github/`、`scripts/`、`AGENTS.md`、`Prompt.md`、`opencode.json`）默认 deny 编辑；`.opencode/rules.md` 人类专属、不编辑。
- **离线优先**：默认不进行在线 API 调用；live 评估需人工显式授权 provider/model/成本上限与凭证配置（凭证只在本机，不得读取或发布）。
- 真实 transcript 与诚实 AI 记录照旧；最终 PR + 非作者评审 + CI + 合并授权保留，**不自动合并到 `main`**。

## 6. 当前状态

- 五份任务书均为**计划**；`tradingagents/course/**` 不存在。

# 任务书总览（A–E）

> 状态：**初始化脚手架**。每个任务书是**自包含、可复制**的编码代理提示词，但**都**受 `AGENTS.md` 与 `Prompt.md` 的停止门约束。
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
3. **代码 + 测试 + PR + 实现前批准链接**：变更文件、测试、PR、`docs/approvals/` 的测试/实现批准引用。
4. **实际评估/配置/结果**：固定评估集、模型/配置、实际结果（如实，含失败）。
5. **完整原始会话 + 独立干预注释**：`transcripts/<studentid-name>/raw.md`（只读）+ `annotations.md`（单独）。
6. **AI 使用/评审/bug/债务/变更记录**：`docs/ai-use-log.yaml`、`docs/review-memo.md`、`docs/bug-diary.md`、`docs/debt-register.md`。
7. **报告贡献 + 300–500 词个人反思 + 姓名/学号贡献证据 + 演示材料**：`Report.md` 对应章节、`templates/member-reflection.md`、演示脚本/截图。

> 模块路径、需求、约束**不是**“七类交付物”；它们是上述条目中的**内容**。

## 5. 通用工作约束（所有任务）

- 实现前必须有人工**测试计划批准**（G-1）；实现计划与安全 ADR 是**附加**控制。
- 既有 `TradingAgents` 源码/测试/构建默认受保护，**不得整树替换基线**；窄范围集成编辑需显式书面 scope + 接口契约 + 人工批准（安全再加 ADR）。
- 治理基础设施（`.github/`、`scripts/`、`AGENTS.md`、`Prompt.md`、`opencode.json`）默认 deny 编辑；若确需变更，由人工授权一次**窄范围配置/会话**，OpenCode 生成代码、评审后再恢复保护。
- **离线优先**：默认不进行在线 API 调用。人工可**显式授权** live 评估的 provider/model/成本上限与安全凭证配置（凭证只在本机，不得读取或发布）。
- 不得无人值守实现，不得自动推送。

## 6. 当前状态

- 五份任务书均为**计划**；`tradingagents/course/**` 不存在。

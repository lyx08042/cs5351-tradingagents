# 权限模型（PROPOSED）

> ## ⚠️ CURRENT OVERRIDE：`DEVELOPMENT-POLICY.md`（ACTIVE, owner-selected, 2026-11-07）
> 下方所有旧的实现前计划/测试/安全批准、`PENDING`、STOP 要求均为 **HISTORICAL / NOT EXECUTED**，不再阻断你自己任务的实现。**最终 PR + 非作者评审 + CI + 合并授权保留**。课程 **G-1/D9 未满足**；**非教师 waiver、非伪造批准**。安全/凭证约束不变。

> 状态：**PROPOSED**。本文件描述**设计意图**；`.opencode/permissions.jsonc` 是课程制品，**不被 OpenCode 自动加载**，**不提供**可执行的运行时角色隔离。

## 1. 原则

- **默认拒绝（default deny）**：默认无读、无写。
- **按角色白名单**：只有任务范围内的路径可读/可写（ASK）。
- **冻结路径（frozen）**：任何角色不得写。
- **人类专属路径（human-only）**：代理一律 DENY。
- **不声明虚假隔离**：目录级白名单只是**协作约束**，不是操作系统级或进程级隔离。

## 2. 角色与路径（设计意图）

| 角色 | 可写（ASK） | 只读 | 冻结/人类专属 |
|---|---|---|---|
| A 证据 | `tradingagents/course/evidence/**`、其测试、其任务文档 | 全部治理文档 | 见第 3 节 |
| B 预算 | `tradingagents/course/budget/**`、其测试、其任务文档 | 全部治理文档 | 同上 |
| C 安全 | `tradingagents/course/safety/**`、其测试、其任务文档 | 全部治理文档 | 同上 |
| D 数据质量 | `tradingagents/course/data_quality/**`、其测试、其任务文档 | 全部治理文档 | 同上 |
| E 审计 | `tradingagents/course/audit/**`、其测试、其任务文档 | 全部治理文档 | 同上 |
| 共同 | 薄编排器（仅协调 PR） | 全部 | 同上 |

> 交叉评审环：A 评审 B，B 评审 C，C 评审 D，D 评审 E，E 评审 A（交接方向 A→E、B→A、C→B、D→C、E→D）；评审人不得是作者。

## 3. 受保护区与集成编辑

**默认受保护（不得整树替换基线）**：既有 `tradingagents/**`、`cli/**`、`tests/**`、`pyproject.toml`、`LICENSE`。

**窄范围集成编辑**（例如在辩论节点接入证据校验）需：明确书面 scope + 接口契约；安全/接口变更创建 ADR/设计记录（**无实现前批准人**）。这属于正常 agentic 集成，不要求人工手写。

**人类专属路径**：`.opencode/rules.md`、`docs/approvals/**`。

**治理基础设施**：`.github/**`、`scripts/**`、`AGENTS.md`、`Prompt.md`、`opencode.json` 默认 deny 编辑；确需变更时人工授权窄范围会话，OpenCode 生成代码、评审后恢复保护。

## 4. 强制执行的真实状态

| 层次 | 是否可执行 | 说明 |
|---|---|---|
| `opencode.json` 的 `permission` | **部分可执行** | 实际 OpenCode 配置；路径白名单是**全局并集**，不区分角色 |
| `.opencode/permissions.jsonc` | **不可执行** | 课程制品，不被自动加载 |
| 按角色隔离（per-role profiles） | **未实现** | 角色纪律依赖人工流程 |
| 人工评审 | 可执行（流程） | 依赖人类纪律 |
| 操作系统级隔离 | **无** | 未实现 |

## 5. 违规处理（计划）

- 尝试写冻结路径：拒绝并记录到 `docs/bug-diary.md` 或流程记录。
- 跨角色修改：必须走协调 PR，在 PR 模板中说明。
- 读取秘密/外部目录：禁止；如发生应视为安全事故并人工复核。

> 注意：owner 于 2026-11-07 取消实现前批准（见 `DEVELOPMENT-POLICY.md`），这是**课内计划审批**的取消，**不**改变上述安全/凭证约束，也**不**提供任何运行时隔离。

## 6. 当前状态

- 只有 `opencode.json` 与人工流程部分生效；其余为设计。
- 不声称任何自动化角色隔离已上线。

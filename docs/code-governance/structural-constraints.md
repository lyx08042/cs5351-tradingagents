# 结构性约束（PROPOSED，权威）

> ## ⚠️ CURRENT OVERRIDE：`DEVELOPMENT-POLICY.md`（ACTIVE, owner-selected, 2026-11-07）
> 下方所有旧的实现前计划/测试/安全批准、`PENDING`、STOP 要求均为 **HISTORICAL / NOT EXECUTED**，不再阻断你自己任务的实现。写计划+测试设计（工作文档）后**继续实现**，无需 `approval_refs`。**最终 PR + 非作者评审 + CI + 合并授权保留**。课程 **G-1/D9 未满足**；**非教师 waiver、非伪造批准**。`PROPOSED` 不因本政策变为 `APPROVED`。

> 状态：**PROPOSED**。本文件是课程扩展的**权威集成约束**；契约变更创建记录后即可推进。
> 关联：`architecture-blueprint.md`、`docs/architecture/adr/001-course-extension.md`、`docs/architecture/invariants.md`。

## 1. 文件清单（每个模块/函数需引用 ADR/INV）

| 模块（PROPOSED） | 责任角色 | 必须声明的 ADR/INV | 允许导入 | 禁止导入 |
|---|---|---|---|---|
| `tradingagents/course/evidence/` | A | ADR-001, INV-001 | 上游只读模块、共享契约 | `budget`, `safety`, `data_quality`, `audit`（直接） |
| `tradingagents/course/budget/` | B | ADR-001, INV-002 | 共享契约 | 其他叶子模块（直接） |
| `tradingagents/course/safety/` | C | ADR-001, INV-003, SEC-001 | 共享契约 | 其他叶子模块（直接） |
| `tradingagents/course/data_quality/` | D | ADR-001, INV-004 | 共享契约 | 其他叶子模块（直接） |
| `tradingagents/course/audit/` | E | ADR-001, INV-005 | 共享契约 | 其他叶子模块（直接） |
| 薄编排器（共同） | 共同 | ADR-001 | 所有叶子模块 | — |

> **规则**：叶子模块之间**不得循环导入**；需要协作时通过共享契约（数据类型/schema）或编排器完成。编排器由共同所有，只能在协调 PR 中编辑。

## 2. 代码注释要求（planned）

- 每个公开函数/类必须在其 docstring 或注释中引用一个 ADR 或 INV ID（例如 `# INV-002`）。
- 未引用任何 ADR/INV 的公开函数在结构性检查中应被标记（planned，当前无自动检查）。

## 3. 契约约束

- 所有跨模块数据必须 JSON 可序列化，并有 schema。
- 不使用可变全局状态跨模块共享预算/审计。
- 缺失语义：`available | unavailable | unknown`，禁止隐式 `neutral`；unknown 默认拒绝（INV-004）。
- 模拟提案字段固定：`action`, `units`, `price`, `currency`, `holdings_snapshot`, `rule_version`, `status`（INV-003）；Hold 用 `units=0`。

## 4. 受保护与集成编辑

既有 `tradingagents/**`、`cli/**`、`tests/**`、`pyproject.toml`、`LICENSE` **默认受保护，不得整树替换基线**。新功能代码只进入 `tradingagents/course/**`（PROPOSED）。

**窄范围集成编辑**（在既有模块中接入新契约）需：

1. 明确书面 scope（哪些文件、哪些函数）；
2. 明确的接口契约；
3. 安全/接口变更创建 ADR/设计记录（**无实现前批准人**）。

这属于课程 agentic development 的正常集成方式，**不要求**人类手工重写既有代码。

**治理基础设施**（`.github/**`、`scripts/**`、`AGENTS.md`、`Prompt.md`、`opencode.json`）默认 deny 编辑；确需变更时由人工授权一次**窄范围配置/会话**，由 OpenCode 生成代码、经非作者评审后**恢复保护**。

## 5. 依赖方向（planned）

```
orchestrator → {evidence, budget, safety, data_quality, audit} → shared contracts
```

- 不允许叶子模块导入 orchestrator。
- 不允许反向依赖（叶子 → 叶子）。

## 6. 现状

- 无 `tradingagents/course/**` 代码；上述仅为约束设计。
- 结构性自动检查为 **planned**，尚未实现。

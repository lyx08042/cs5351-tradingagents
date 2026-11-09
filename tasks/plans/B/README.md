# 角色 B：运行预算（FR-002）— 计划工作区

> 状态：**DRAFT / 占位**。本文件只声明 B 的负责范围与文件落位，**不含**任何已完成的实现、测试结果或批准。
> 本目录（`tasks/plans/B/`）是 B 的实现计划与测试设计的位置。按 `DEVELOPMENT-POLICY.md` 第 3 节，计划与测试设计是**工作文档**，不是批准门；不要往 `docs/approvals/` 写新计划。

## 1. 负责范围

| 项 | 内容 |
|---|---|
| 主需求 | `FR-002` 运行预算：调用前预留、调用后结算、超预算 fail-closed |
| 不变量 | `INV-002` 先预留后结算，超预算拒绝 |
| 非功能 | `NFR-001` 成本下降 20%（临时目标）、`NFR-002` 质量不劣化 ≤3pp（临时目标） |
| 代码路径（PROPOSED） | `tradingagents/course/budget/` |
| 离线测试 | `test/offline/` |
| 评审关系 | A 评审 B；B 评审 C；交接方向 B → A |

## 2. 本目录后续会包含

- `FR-002-implementation-plan.md` —— 契约、状态机、集成点、里程碑
- `FR-002-test-plan.md` —— 正向/负向用例、不变量覆盖、验证命令

在写这两份文件之前，先确认第 3 节的开放问题。

## 3. 待确认的开放问题

1. **FR-002 的语义边界**：只做“全局池 + 超限拒绝”（现行 `requirements.yaml` 的写法），还是扩展到“跨 Agent 分配 + 不足时降级”（分工图里 B 的三个能力）？这决定账本契约是否要带 `agent` / `stage` 字段。
2. **预算单位**：token、调用次数、成本，三者取哪些作为主计量？
3. **并发语义**：四个分析师并行调用时，同一预算池如何保证不超卖（锁 / CAS / 预扣+回补）？
4. **耗尽后的运行时语义**：中止整次运行、输出部分结论，还是标记 `degraded` 继续？

## 4. 边界（明确不做）

- 不改上游基线：`tradingagents/`（除新增 `course/`）、`cli/`、`tests/`、`pyproject.toml`。
- 不把计划写进 `docs/approvals/`（该目录人类专属，代理不得编辑）。
- 不声称已批准、已实现、已评估；`PROPOSED` 不因任何文档改动变成 `APPROVED`。
- 不与其他叶子模块循环导入；共享编排器只能走协调 PR。
- 不读取或提交任何 API key；默认离线，live 评估需人工显式授权 provider / model / 成本上限。

## 5. 参考

- `tasks/B-budget.md` —— 任务书（交付物、契约、验收表）
- `docs/req/requirements.yaml` —— FR-002 / INV-002 / NFR-001 / NFR-002
- `docs/architecture/invariants.md`、`docs/architecture/trace-matrix.md`
- `DEVELOPMENT-POLICY.md` —— 当前生效的工作流
- `tasks/plans/D/` —— D 的实现计划与测试计划，可作格式参考

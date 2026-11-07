# 批准记录（Human-owned）

> ## ⚠️ CURRENT OVERRIDE：`DEVELOPMENT-POLICY.md`（ACTIVE, owner-selected, 2026-11-07）
> 下方所有旧的实现前计划/测试/安全批准、`PENDING`、STOP 要求均为 **HISTORICAL / NOT EXECUTED**，不再阻断你自己任务的实现。写计划+测试设计（工作文档）后**继续实现**，无需 `approval_refs`。**最终 PR + 非作者评审 + CI + 合并授权保留**。课程 **G-1/D9 未满足**；**非教师 waiver、非伪造批准**。真实历史批准保持原样；本政策**不**新增任何批准。

> **本目录由人类成员维护。编码代理一律不得写入。**

## 1. 批准格式（必须真实）

每个批准必须是一个独立文件，命名建议 `YYYY-MM-DD-<type>-<req-id>.md`，包含：

```yaml
type: <test-plan | implementation-plan | safety-adr>
requirement: <REQ-ID>
test_plan_ref: <commit 或文件路径>
implementation_starting_commit: <sha>
reviewer: <真实评审人姓名/ID>
approver: <真实批准人>
timestamp: <ISO-8601>
summary: <批准范围摘要>
```

## 2. 规则

- 批准必须在**实现之前**产生。
- 不得写入未真实发生的批准；不得编造评审人、时间戳或 commit。
- 安全相关变更额外需要 ADR（`docs/architecture/adr/`）与人工批准。
- 提示词/模型变更：先固定评估集（`docs/evaluation/cases.yaml`）并先评测，再批准。

## 3. 当前已批准记录

**无。** 本仓库引导阶段没有任何已批准的测试计划、实现计划或安全 ADR。

> 空列表是诚实状态；不代表已完成或已通过。实现前批准已由 owner 于 2026-11-07 取消（`DEVELOPMENT-POLICY.md`）；本政策**不**创建任何批准，也**不**把任何 `PROPOSED` 变为 `APPROVED`。

# 批准记录（Human-owned）

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

> 空列表是诚实状态；不代表已完成或已通过。

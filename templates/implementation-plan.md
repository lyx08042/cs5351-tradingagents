# 实现计划模板（Implementation Plan）

> ## ⚠️ CURRENT OVERRIDE：`DEVELOPMENT-POLICY.md`（ACTIVE, owner-selected, 2026-11-07）
> 实现计划现在是**工作文档**，**不是批准门**。下方旧的“编码之前必须人工批准/PENDING”表述均为 **HISTORICAL / NOT EXECUTED**。写完后继续实现，无需 `approval_refs`。课程 **G-1/D9 未满足**；**非教师 waiver、非伪造批准**。
>
> **保存位置**：`tasks/plans/<A-E>/<REQ-ID>-implementation-plan.md`（已在 `tasks/**` 编辑白名单内）。**不得**放进人类专属 `docs/approvals/`，也不要为等待该目录权限而阻塞；既有批准记录保持不动。

> 模板。实现计划作为**工作文档**编写；写完即继续实现。

```markdown
## Implementation Plan: <REQ-ID>

- 作者：<待填>
- 评审人（非作者）：<待填>
- 关联测试计划：<ref>
- 状态：DRAFT（工作文档，非批准门）
- 批准引用（可选，历史）：<docs/approvals/... 或 N/A>

### 1. 变更范围
- 新增/修改文件：<path>
- 明确不改：<frozen paths>

### 2. 契约
- 输入/输出 schema：<...>
- 缺失语义：available/unavailable

### 3. 不变量与失效行为
- INV：<...>
- fail-closed / abstain / review：<...>

### 4. 步骤
1. ...
2. ...

### 5. 风险与回滚
- <...>

### 6. ADR（安全/接口变更填写）
- <docs/architecture/adr/...>
```

> 计划是工作文档，不是批准门；不得把 `DRAFT` 写成人工 `APPROVED`。

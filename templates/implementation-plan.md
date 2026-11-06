# 实现计划模板（Implementation Plan，批准前）

> 模板。实现计划必须在**编码之前**经**人工批准**。

```markdown
## Implementation Plan: <REQ-ID>

- 作者：<待填>
- 评审人（非作者）：<待填>
- 关联测试计划：<ref>
- 批准状态：PENDING

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

### 6. ADR（安全变更必填）
- <docs/architecture/adr/...>
```

> 不得在批准前开始编码；不得先写代码后补计划。

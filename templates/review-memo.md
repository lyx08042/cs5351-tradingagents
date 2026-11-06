# 评审备忘模板（Review Memo）

> 模板。评审人**不得**是作者本人。

```markdown
## Review: <PR/commit>

- 作者：<待填>
- 评审人（非作者）：<待填>
- 日期：<待填>
- 需求：<REQ-ID>

### 检查
| 项 | 结果 | 备注 |
|---|---|---|
| 测试计划已批准 | pass/fail/n/a | |
| 实现计划已批准 | pass/fail/n/a | |
| ADR（安全变更） | pass/fail/n/a | |
| 负向测试存在 | pass/fail | |
| 未削弱既有测试 | pass/fail | |
| 无循环导入 | pass/fail | |
| unavailable≠neutral | pass/fail | |
| fail-closed 验证 | pass/fail | |

### 发现与结论
- <...>
- 结论：approve / request changes / reject
```

> 只可基于真实检查填写；模板不产生结论。

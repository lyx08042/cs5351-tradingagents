# 测试计划模板（Test Plan，批准前）

> 模板。测试计划必须在**实现之前**提交并经**人工批准**（`docs/approvals/`）。

```markdown
## Test Plan: <REQ-ID>

- 作者：<待填>
- 评审人（非作者）：<待填>
- 批准状态：PENDING（不得预填 PASS）

### 范围
- 功能：<FR-00x>
- 不变量：<INV-00x>
- 路径：<tradingagents/course/...>

### 正向测试
| 用例 | 输入 | 预期 |
|---|---|---|
| | | |

### 负向测试（必须至少一个/功能）
| 用例 | 输入 | 预期（fail-closed/abstain/review） |
|---|---|---|
| | | |

### 回归
- [ ] 上游 `pytest` 通过（BASE-002）
- [ ] 不修改 `tests/`

### 判定标准
- <可度量阈值，来自 requirements.yaml 的 fit>
```

> 批准由人类在 `docs/approvals/` 中记录；本模板不产生批准。

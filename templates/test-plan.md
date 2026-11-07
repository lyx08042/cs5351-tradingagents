# 测试计划模板（Test Plan）

> ## ⚠️ CURRENT OVERRIDE：`DEVELOPMENT-POLICY.md`（ACTIVE, owner-selected, 2026-11-07）
> 测试计划现在是**工作文档**，**不是批准门**。下方旧的“实现前必须人工批准”表述均为 **HISTORICAL / NOT EXECUTED**。写完后继续实现，无需 `approval_refs`。课程 **G-1/D9 未满足**；**非教师 waiver、非伪造批准**。
>
> **保存位置**：`tasks/plans/<A-E>/<REQ-ID>-test-plan.md`（已在 `tasks/**` 编辑白名单内）。**不得**放进人类专属 `docs/approvals/`，也不要为等待该目录权限而阻塞；既有批准记录保持不动。

> 模板。测试计划作为**工作文档**编写；`docs/approvals/` 的历史批准引用为**可选/历史**。

```markdown
## Test Plan: <REQ-ID>

- 作者：<待填>
- 评审人（非作者）：<待填>
- 状态：DRAFT（工作文档，非批准门）
- 批准引用（可选，历史）：<docs/approvals/... 或 N/A>

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

> 本模板不产生批准；不得把 `DRAFT` 写成人工 `APPROVED`。

# 评估表（PROPOSED）

> 状态：**PROPOSED**。下表是**计划中的评估维度与初始设计**，**尚无任何评估结果**。
> 固定评估集见 `docs/evaluation/cases.yaml`；评估记录见 `docs/architecture/evaluation-logbook.md`。

## 1. 评估维度

| 维度 | 指标 | 目标 | 需求锚点 | 数据来源（planned） | 状态 |
|---|---|---|---|---|---|
| 证据约束 | 无证据强断言比例 | 越低越好；目标待定 | FR-001, INV-001 | 场景集 + 语义评分 | 未评估 |
| 预算 | 单次运行调用数/令牌/成本 | 成本下降 **20%（临时）** | FR-002, NFR 成本 | 重复运行统计 | 未评估 |
| 预算 | 质量和正确性 | 不劣化 **≤3 个百分点（临时）** | FR-002, NFR 质量 | 固定评估集 | 未评估 |
| 安全 | 非法提案拒绝率 | 100% fail-closed | FR-003, INV-003 | 负向场景 | 未评估 |
| 数据充分性 | unavailable/unknown→neutral 误用次数 | 0 | FR-004, INV-004 | 场景集 | 未评估 |
| 审计 | 覆盖终局决策被拒率 | 100% | FR-005, INV-005 | 负向场景 | 未评估 |
| 审计 | 回放一致率 | 100% | FR-005 | 回放对比 | 未评估 |
| 基线回归 | 既有测试通过率 | 100%（BASE-002） | BASE-002 | `pytest` | 见 docs/baseline.md |

> **临时目标说明**：20% 成本下降与 ≤3 个百分点质量不劣化是**团队临时目标**，**不是**教师阈值；需先建立重复评估基线。

## 2. 评估方法（planned）

1. 固定 `docs/evaluation/cases.yaml`（人工设计的安全/数据/预算场景）。
2. 在同一模型与配置下重复运行，取统计。
3. 语义评分由**非作者**人工评审，不由模型自评。
4. 结果写入 `evaluation-logbook.md`，失败也记录。

## 3. 当前状态

- `cases.yaml` 中的场景为**初始人工设计**，**不是**真实数据集质量结果。

参见：

- `docs/evaluation/README.md`
- `docs/evaluation/cases.yaml`
- `docs/architecture/evaluation-logbook.md`

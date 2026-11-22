# 评估表

> 状态：**部分已评估**。各模块的离线测试结果已记录；端到端的实时模型评估**尚未进行**。
> 固定评估集见 `docs/evaluation/cases.yaml`；评估记录见 `docs/architecture/evaluation-logbook.md`。

## 1. 评估维度

| 维度 | 指标 | 目标 | 需求锚点 | 数据来源 | 状态 |
|---|---|---|---|---|---|
| 证据约束 | 无证据强断言比例 | 0 | FR-001, INV-001 | `test/offline/test_evidence.py` | **离线测试通过**（43 项）；语义评分未做 |
| 预算 | 单次运行调用数/令牌/成本 | 成本下降 **20%（临时）** | FR-002, NFR-001 | 确定性回放 + `test_budget_replay.py` | **回放已测**（200k 档 −34.5%）；实时未测 |
| 预算 | 质量和正确性 | 不劣化 **≤3 个百分点（临时）** | FR-002, NFR-002 | 固定评估集 | **未评估**（需实时模型） |
| 安全 | 非法提案拒绝率 | 100% fail-closed | FR-003, INV-003 | `test/offline/test_safety_simulation.py` | **离线测试通过** |
| 数据充分性 | unavailable/unknown→neutral 误用次数 | 0 | FR-004, INV-004 | `test/offline/test_data_quality.py` | **离线测试通过** |
| 审计 | 覆盖终局决策被拒率 | 100% | FR-005, INV-005 | `test/offline/test_audit.py` | **离线测试通过** |
| 审计 | 回放一致率 | 100% | FR-005 | `test_audit.py` 回放用例 | **离线测试通过** |
| 集成 | 五个模块同时参与的运行 | 可运行 | FR-001 / FR-002 | `test/offline/test_pipeline_modules.py` | **离线测试通过**（6 项） |
| 基线回归 | 既有测试通过率 | 100%（BASE-002） | BASE-002 | CI（四个 Python 版本） | **CI 通过**（PR #8、#9 8/8 绿） |

> **临时目标说明**：20% 成本下降与 ≤3 个百分点质量不劣化是**团队临时目标**，**不是**教师阈值。

## 2. 已执行的离线验证

| 模块 | 测试文件 | 结果 |
|---|---|---|
| A 证据 | `test_evidence.py` | 43 passed |
| B 预算 | `test_budget.py`、`test_budget_integration.py`、`test_budget_replay.py` | 58 passed |
| C 安全 | `test_safety_simulation.py` | 随 C/D/E 共 78 passed |
| D 数据 | `test_data_quality.py` | 同上 |
| E 审计 | `test_audit.py` | 同上 |
| 集成 | `test_pipeline_modules.py` | 6 passed |

> 运行环境说明：在缺少运行依赖的机器上，`test_cde_graph_flow.py` 与 `test_cde_integration.py`
> 无法收集（需要 `langchain_core`、`pydantic`）；`test_audit.py` 中依赖 `tmp_path` 的用例在本机受限。
> 这些用例在 CI（`ubuntu-latest`）中运行。

## 3. 尚未进行的评估

- **实时模型评估**：`NFR-001`（成本）与 `NFR-002`（质量）需要真实模型对照，目前没有结果。
- **语义评分**：需要非作者人工评审，尚未安排。

## 4. 评估方法

1. 固定 `docs/evaluation/cases.yaml`（人工设计的安全/数据/预算场景）。
2. 在同一模型与配置下重复运行，取统计。
3. 语义评分由**非作者**人工评审，不由模型自评。
4. 结果写入 `evaluation-logbook.md`，失败也记录。

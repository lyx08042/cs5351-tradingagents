# 评估（Evaluation）

> 状态：**PROPOSED / planned**。当前**没有**任何评估结果；`cases.yaml` 为**人工设计的初始场景**，**不是**真实数据集质量结果。
> 本仓库当前**不能**运行任何真实功能来评估（F1–F5 未实现）。

## 1. 目标

- 为 F1–F5 建立可复现、可比较的评估。
- 固定评估集，避免提示词/模型变更导致不可比。
- 结果如实记录（含失败）。

## 2. 文件

| 文件 | 说明 |
|---|---|
| `docs/evaluation/README.md` | 本文件 |
| `docs/evaluation/cases.yaml` | 固定初始场景集（人工设计） |
| `docs/architecture/evaluation-table.md` | 评估维度与（临时）目标 |
| `docs/architecture/evaluation-logbook.md` | 记录册（当前为空） |

## 3. 方法

- 场景覆盖：安全、数据缺失、预算、审计、证据。
- 每场景有**期望的确定性状态**与**语义评分 rubric**。
- 语义评分由**非作者**人工评审。
- 重复运行取统计；记录模型、配置、commit、日期。

## 4. 诚实边界

- 场景是**初始设计**，尚未用真实 LLM 运行。
- 不得把 fixture 通过等同于真实评估通过。
- 20% 成本与 ≤3pp 质量为**临时目标**，非教师阈值。

## 5. 命令（planned）

- 当前**没有**评估运行器；F1–F5 未实现，无法运行真实评估。
- 目前只能做脚手架格式校验（`python scripts/check_course.py --root .`）。

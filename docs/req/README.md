# 需求注册表工作流（PROPOSED）

> ## ⚠️ CURRENT OVERRIDE：`DEVELOPMENT-POLICY.md`（ACTIVE, owner-selected, 2026-11-07）
> 下方所有旧的实现前计划/测试/安全批准、`PENDING`、STOP 要求均为 **HISTORICAL / NOT EXECUTED**，不再阻断你自己任务的实现。**最终 PR + 非作者评审 + CI + 合并授权保留**。课程 **G-1/D9 未满足**；**非教师 waiver、非伪造批准**。GOV-001 保持原始课程表述并标注为 `not_satisfied`；`PROPOSED` 不因本政策变为 `APPROVED`。

> 状态：**PROPOSED**。`requirements.yaml` 中的所有需求均为 `status: proposed`，**未经人工批准**。

## 1. 文件

| 文件 | 作用 |
|---|---|
| `docs/req/requirements.yaml` | 需求注册表（唯一事实源） |
| `docs/req/req-schema.json` | JSON Schema draft 2020-12，定义字段/类型/必填 |
| `docs/req/README.md` | 本文件：工作流与歧义清单 |

## 2. ID 规则

| 前缀 | 类型 | 当前范围 |
|---|---|---|
| `BASE-` | 上游基线约束 | BASE-001..002 |
| `FR-` | 功能需求 | FR-001..005 |
| `NFR-` | 非功能需求 | NFR-001..005 |
| `INV-` | 不变量 | INV-001..005 |
| `GOV-` | 治理需求 | GOV-001..002 |
| `SEC-` | 安全需求 | SEC-001 |

- ID 全局唯一，格式 `^[A-Z]+-[0-9]{3}$`。
- 新增需求只能追加新号，不复用已废弃号。

## 3. 必填字段

每个需求必须包含：`id`、`type`、`statement`、`priority`（MoSCoW：`must|should|could|wont`）、`tradeoff`、`source`、`owner`（`A|B|C|D|E|shared`）、`status`、`fit`。

`fit` 必须含：
- `metric`：可度量的指标名；
- `threshold`：JSON 兼容的数值/字符串阈值（结构化，不是模糊描述）；
- `verification`：如何验证（明确标注 planned 与否）。

## 4. 工作流

1. **提出**：在 PR 中新增/修改需求，`status: proposed`。
2. **评审**：由非作者评审，检查可度量性与 trace 覆盖。
3. **实现**：通过 OpenCode 实现；`status` 可改为 `implemented`（需测试支撑）。**计划/测试设计为工作文档，非批准门**（见 `DEVELOPMENT-POLICY.md`）。
4. **合规偏离**：GOV-001 保留原始课程表述，但以 `course_deviation: true` / `implementation_policy: pre_coding_approval_disabled_by_owner` / `fulfillment_status: not_satisfied` 如实标注；**不得**把教师要求改写为已满足。
5. **校验**：
   ```bash
   python scripts/check_course.py --root .
   pytest -o testpaths=test/offline test/offline/test_course_scaffold.py
   ```

## 5. 校验内容（脚手架脚本）

`scripts/check_course.py` 执行：
- schema 校验（`jsonschema`，draft 2020-12）；`fit.threshold` 接受数值（含整数/浮点）或字符串；
- 需求 ID 唯一；
- 每个需求 ID 在 `docs/architecture/trace-matrix.md` 中至少出现一次；
- 引导必需文件存在；
- 非法结构（如某条目不是映射）给出清晰错误而非 traceback；
- 占位符（TODO/TBD/`{{...}}`）仅允许出现在 `proposed` 状态；`approved`/`implemented`/`superseded` 禁止占位符。

它**不**验证：
- 不变量是否真正被代码强制；
- 评估分数是否达标；
- 六道课程阻断 gate 是否通过（它只覆盖 G-3 的 schema/trace 部分）。

## 6. 歧义清单（待人工澄清）

| ID | 歧义 | 涉及 | 建议 |
|---|---|---|---|
| AMB-01 | 课程是否要求把根 `architecture-blueprint.md` 迁入 `docs/architecture/` | 目录布局 | 询问教师后人工迁移 |
| AMB-02 | 20% 成本下降与 ≤3 个百分点质量不劣化是否为教师阈值 | NFR-001/002 | 视为团队临时目标，待 baseline 评估 |
| AMB-03 | 是否允许修改上游 `tests/` | BASE-002 | 当前冻结，不改 |
| AMB-04 | `tradingagents/course/**` 布局是否被接受 | 架构 | 教师确认前为 PROPOSED |
| AMB-05 | 成员姓名/学号/权重数据 | Report/transcripts | 人工填写，代理不得虚构 |

## 7. 来源

- `SRC-PROJECT-SHEET`：课程 project sheet 第 3-10 页（PDF 未随仓库分发）。
- `SRC-INTRO`：课程 intro 第 20-25 页（PDF 未随仓库分发）。
- `SRC-UPSTREAM`：上游源码/README（commit `9fa1196fffbcfd9de5146d2dd2869df84ab99838`）。
- `SRC-BASELINE-RUN`：本仓库一次基线运行（脱敏，见 `docs/baseline.md`）。

> 引用仅为页码与仓库内文件，不包含需要外部检索的网页断言。

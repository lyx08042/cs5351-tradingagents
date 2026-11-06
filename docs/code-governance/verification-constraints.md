# 验证约束（PROPOSED，权威）

> 状态：**PROPOSED**。除已实现部分外，多数自动化为 **pending**。本文件**不**被任何 checklist 强制执行；它是治理约定。

## 1. 六道课程阻断 Gate（精确）

以下**六道**是课程**阻断性** gate。请勿与其他工作流控制（见第 3 节）混淆。

| # | Gate | 触发时机 | 机制 | 当前真实状态 |
|---|---|---|---|---|
| **G-1** | **实现前的测试批准**（test approval before implementation） | 任何实现开始前 | `templates/test-plan.md` → `docs/approvals/` 人工批准 | **PENDING**：人工流程；无自动强制；无批准记录 |
| **G-2** | **每次提交的静态检查**：lint / 类型 / 依赖；**安全 PR 额外**：安全 / 契约 / API / 权限 | 每次 commit / PR | ruff + 类型/依赖检查；安全 PR 增加安全/契约/API/权限审查 | lint 继承上游 `ci.yml`（存在）；类型/依赖检查与安全 PR 审查 **PENDING**；fork Actions 需 owner 启用 |
| **G-3** | **需求 schema** | 每次使用 registry 时 | `scripts/check_course.py`（`docs/req/req-schema.json`） | **已实现**（本地校验通过后在 `docs/course-requirements-checklist.md` 标注）；CI 需 owner 启用 |
| **G-4** | **提示词/模型变更的语义固定集评估** | 提示词或模型变更时 | `docs/evaluation/cases.yaml` 固定集 + 语义 rubric | **PENDING**：无运行器；F1–F5 未实现 |
| **G-5** | **完整既有回归** | 每次提交/合并 | 上游 `pytest`（BASE-002） | 继承上游 `ci.yml`（存在）；fork Actions/分支保护需 owner 启用，**PENDING** |
| **G-6** | **代码/提示词 PR 更新 AI 使用记录** | 每次代码或提示词 PR | `docs/ai-use-log.yaml` 追加条目 | **PENDING**：人工流程；无自动强制 |

> 引导 CI（`.github/workflows/course-bootstrap.yml`）**仅**覆盖 G-3 的 schema/trace 部分；**不**代表 G-1/G-2/G-4/G-5/G-6 通过。

## 2. G-3 需求 schema 与 trace 覆盖

- 校验：JSON Schema draft 2020-12、需求 ID 唯一、trace 覆盖每个 ID、必需文件存在、占位符策略。
- 阈值类型：`number` 或 `string`（整数与浮点均满足 `number`）。
- 占位符（TODO/TBD/`{{...}}`）：仅允许处于 `proposed` 状态；`approved`/`implemented`/`superseded` 禁止。
- 该脚本**不**验证不变量是否被代码强制，也**不**验证评估分数。

## 3. 附加工作流控制（非六道阻断 gate）

| 控制 | 说明 | 状态 |
|---|---|---|
| 实现计划批准 | `templates/implementation-plan.md` → `docs/approvals/` | PENDING（人工） |
| 安全 ADR | 安全相关变更需 ADR + 人工批准 | PENDING（ADR-001 为 PROPOSED） |
| 非作者评审 | A 评审 B，B 评审 C，C 评审 D，D 评审 E，E 评审 A（交接 A→E、B→A、C→B、D→C、E→D） | PENDING（人工） |
| 负向测试 | 每个功能至少一个 | PENDING（行为层未实现） |

## 4. 三层验证

| 层级 | 内容 | 当前状态 |
|---|---|---|
| 结构层 | schema、ID 唯一、trace 覆盖、导入方向、必需文件 | 部分（`scripts/check_course.py`） |
| 回归层 | 上游 `tests/`（BASE-002） | 已有基线；fork CI 待启用 |
| 行为层 | F1–F5 正向/负向/回放测试 | planned，未实现 |

## 5. 每个功能至少一个负向测试（planned）

| 功能 | 负向测试 |
|---|---|
| FR-001 | 无证据强断言被降级/拒绝 |
| FR-002 | 超预算调用被拒绝 |
| FR-003 | 缺 holdings_snapshot 被拒绝；Buy/Sell units ≤ 0 被拒绝；未声明 flat 被拒绝 |
| FR-004 | `unavailable` 或 `unknown` 被标 `neutral` 被拒绝 |
| FR-005 | 覆盖终局决策被拒绝；回放不一致被标记 |

## 6. 命令

```bash
# G-3 课程脚手架（离线、无网络）
python scripts/check_course.py --root .

# G-3 负向/正向测试
pytest -o testpaths=test/offline test/offline/test_course_scaffold.py

# G-5 上游回归（历史基线）
pytest

# G-2 风格（不自动修复）
ruff check .
```

## 7. 诚实声明

- 本仓库**不声称**六道 gate 已全部自动化或已通过。
- 清单/文档**不**自动强制任何 gate。
- 评估中的模拟 fixture **不等于**真实 LLM 评估。

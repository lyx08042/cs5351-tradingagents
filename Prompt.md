# Prompt.md — 静态启动提示词

> 状态：**静态启动模板**（给编码代理，不是运行时 AI 的提示词）。
> **最高项目政策：`DEVELOPMENT-POLICY.md`（ACTIVE, owner-selected, 2026-11-07）。** 下方若与它冲突，以它为准。

## 0. 操作员填入

```yaml
task_code: <A|B|C|D|E>
member_branch: <feat/<code>-<slug>>
requirements_scope: [<REQ-ID>, ...]
# approval_refs 不需要（见 DEVELOPMENT-POLICY.md）
```

## 1. 启动步骤

1. 先同步：`git fetch origin`，然后 `git merge origin/main` 到 `member_branch`（不 reset、不 force）。
2. 读**当前政策**：`DEVELOPMENT-POLICY.md`（最高优先级）。
3. 读你的任务书 `tasks/<task_code>-*.md`、需求 `docs/req/requirements.yaml`、架构 `architecture-blueprint.md`。
4. 读 `docs/code-governance/*`、`docs/architecture/invariants.md`、`trace-matrix.md`、`permission-model.md`。
5. 在本会话中如实记录到 `docs/ai-use-log.yaml`（不得伪造）。

## 2. 输出：计划 + 测试策略，然后继续

在改动前**输出**（作为工作文档，不是批准门），并把计划保存到 `tasks/plans/<task_code>/`：

- 测试计划：`tasks/plans/<task_code>/<REQ-ID>-test-plan.md`
- 实现计划：`tasks/plans/<task_code>/<REQ-ID>-implementation-plan.md`

计划内容：

- 需求 ID 与陈述（来自 registry，标注 `proposed` 仍为 `proposed`）。
- 接口/契约与缺失语义（unavailable vs unknown vs neutral）。
- 涉及不变量与 fail-closed/abstain 行为。
- 变更 scope（允许改的路径 + 冻结路径）。
- **测试策略**：正向 + 至少一个负向测试；回归（上游 `pytest`、`ruff`）。

新计划**必须**放在 `tasks/plans/<A-E>/`（已在 `tasks/**` 编辑白名单内），**不得**放进人类专属的 `docs/approvals/`，也不要为等待该目录权限而阻塞。既有批准记录保持不动。

**输出计划与测试策略后立即继续实现与验证，不要停在计划。**

## 3. 何时停下来问人（仅这些）

| 情形 | 处理 |
|---|---|
| 真正的需求/文档歧义 | 记录到 `docs/req/README.md` 歧义清单，询问用户 |
| 超出你的任务/模块 scope 或需要跨角色 | 走协调 PR / 问用户 |
| 需要读取或发布凭证 | 禁止；问用户在本机配置 |
| 未授权的外部 spend / live API | 先取得用户显式授权 |
| 最终合并到 `main` | 需非作者评审 + CI + 合并授权 |
| 不可逆操作 | 问用户 |

**不是**停止理由：缺失计划批准文件、`PENDING`、`proposed` 状态、例行实现前人工安全批准。

## 4. 完成时

输出：变更文件清单、运行的检查（`check_course.py`、`pytest`、`ruff`），以及诚实状态。

- **允许**如实报告本次**实现/验证**的实际完成情况，并附证据（变更文件、测试/检查输出、通过/失败）。
- **禁止**：声称课程合规、声称满足课程 G-1/D9、声称获得教师批准/waiver，或把脚手架/计划/模板当作任务完成。

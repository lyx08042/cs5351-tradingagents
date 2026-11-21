# 任务 E：可验证审计与决策修订（F5, verifiable audit）

> ## ⚠️ CURRENT OVERRIDE：`DEVELOPMENT-POLICY.md`（ACTIVE, owner-selected, 2026-11-07）
> 下方所有旧的实现前计划/测试/安全批准、`PENDING`、STOP 要求均为 **HISTORICAL / NOT EXECUTED**，不再阻断本任务实现。写计划+测试设计（工作文档）后**继续实现**，无需 `approval_refs`。**最终 PR + 非作者评审 + CI + 合并授权保留**。课程 **G-1/D9 未满足**；**非教师 waiver、非伪造批准**。`PROPOSED` 不因本政策变为 `APPROVED`。开始前对 feature 分支 `git fetch origin` + `git merge origin/main`（不 reset、不 force）。

> 状态：**PROPOSED 计划**。未实现。成员身份未知，不得虚构。
> 规划顺序：先写计划+测试设计（工作文档），然后继续实现。审计权威性变更**创建 ADR/设计记录**，但无实现前批准人。

## 1. 交付物（Deliverables）

- 不可变审计记录（追加式）。
- 唯一终局决策权威（`final_decision`）。
- 决策修订链（`superseded_by`）。
- 离线 gate 回放（reward/evaluation replay）与一致性检查。
- 正/负向测试与审计文档。

## 2. 需求 ID

- 主：`FR-005`
- 关联：`INV-005`、`NFR-003`（确定性回放）、`NFR-004`（留痕）、`NFR-005`

## 3. 拥有/提议源码路径（PROPOSED，当前不存在）

- `tradingagents/course/audit/`（新增）
- 测试：`test/offline/`（新增）

## 4. 依赖与契约

- `AuditRecord`（不可变，JSON）：
  ```json
  {
    "record_id": "...",
    "run_id": "...",
    "timestamp": "ISO-8601",
    "entry_type": "decision|rejection|abstain|revision",
    "payload_ref": "...",
    "rules_version": "...",
    "previous_record_id": null
  }
  ```
- 最终决策：`final_decision` 唯一；修订以 `superseded_by` 链保存，旧版可回放。
- 消费 B/C/D 的事件（通过共享契约或编排器，不直接循环导入）。

## 5. 冻结范围

- 既有 memory/checkpoint 公共行为、`tests/`、`pyproject.toml` 受保护；不整树替换基线。
- 窄范围集成编辑需：明确 scope + 接口契约（实现前人工批准不再是硬门）。
- 不删除或覆盖历史审计记录。

## 6. 验收与负向测试

| 项 | 预期 |
|---|---|
| 正常追加记录 | 成功且顺序可验证 |
| **覆盖终局决策**（负向） | 拒绝，要求 supersede |
| **删除历史记录**（负向） | 拒绝 |
| 回放与记录不一致（负向） | 标记 review，不得静默通过 |

## 7. 里程碑

- M1：记录契约 + 修订链 + 回放设计（文档）。
- M2：实现 + 负向/回放测试。
- M3：集成（协调 PR）。
- M4：非作者评审 + 评估记录。

## 8. 具体示例

> 已有终局决策 `d-001`。新决策 `d-002` 必须写成 `revision`，并设 `superseded_by: d-002`；直接覆盖 `d-001` 必须被拒绝。

## 9. 自包含可复制提示词

```text
[CURRENT OVERRIDE — 最高项目政策：DEVELOPMENT-POLICY.md（ACTIVE, owner-selected, 2026-11-07）]
旧的实现前计划/测试/安全批准、PENDING、STOP 要求均为 HISTORICAL / NOT EXECUTED，不阻断本任务实现；
写计划+测试设计（工作文档）后继续实现，无需 approval_refs。课程 G-1/D9 未满足；非教师 waiver、非伪造批准。
最终 PR + 非作者评审 + CI + 合并授权保留；不自动合并 main。开始前 git fetch origin + git merge origin/main（不 reset/force）。

你是 CS5351 team 的编码代理，负责角色 E（F5 可验证审计+修订+离线回放）。
必读：DEVELOPMENT-POLICY.md、AGENTS.md、Prompt.md、START-HERE.md、architecture-blueprint.md、
tasks/E-audit.md、docs/req/requirements.yaml、docs/code-governance/*、
docs/architecture/invariants.md、evaluation-table.md 与 trace-matrix.md。

任务范围：仅 FR-005/INV-005，路径限于 tradingagents/course/audit/ 与 test/offline/。
改动前输出计划与测试策略，然后继续实现与验证；不要停在计划。审计权威性变更创建 ADR/设计记录（无实现前批准人）。
仅当真实的范围外/不可逆/凭证问题才请求用户；不因 PENDING、缺失计划批准或 proposed 状态停下。
不得覆盖终局决策；不得伪造回放结果；不得读取秘密；默认离线；不自动合并 main。
```

## 10. 交接（Handoff）

使用模板 `templates/handoff.md`（七类信息），交给评审人 **D**（E 的产出由 D 评审）。

## 11. 2026-11-14 状态

- E 独立模块（FR-005 / INV-005 / NFR-003/004/005）已在 `tradingagents/course/audit/` 实现；本地受测源码提交 `fe5805ffc4c16bd8e69379a70a8b93ca94746ec4`（未 push），GitHub 同内容代码快照 `94ba2e51d3117aad3b24027c378b74faa28c5815`（tree API 核验 12 份文件 blob SHA 与本地相同）。
- 实现前批准：受审 commit `bebfe912185bb1c5f735d6dae7acc79acaff4fb9`，记录 commit `85d4fc7`，见 `tasks/plans/E/FR-005-pre-code-approval.md`（本聊天用户真实决定，非教师批准）。
- 实际验证：离线 80 passed（E 60 + 脚手架 20）、上游 1412 passed/1 skipped/1 deselected/100 subtests、ruff passed、独立 demo exit 0；证据在 `tasks/plans/E/evidence/`。
- 文档链接：交接 `tasks/plans/E/FR-005-handoff.md`、验证 `tasks/plans/E/FR-005-validation.md`、报告素材 `FR-005-report-notes.md`、评审须知 `FR-005-review-notes.md`、ADR `docs/architecture/adr/003-append-only-audit.md`。
- 未完成：M3 主流程真实接入（协调 PR）、M4 D 非作者评审（待 D）。PR 尚未创建，最终以 GitHub 为准。
- 本节仅追加状态，不改变上方原任务要求与历史政策。

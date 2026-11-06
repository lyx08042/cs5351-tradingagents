# 任务 E：可验证审计与决策修订（F5, verifiable audit）

> 状态：**PROPOSED 计划**。未实现。成员身份未知，不得虚构。
> 先读 `AGENTS.md` 与 `Prompt.md`；严格遵守停止门。审计权威性变更需 **ADR + 人工批准**。

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
- 窄范围集成编辑需：显式 scope + 接口契约 + 人工计划/测试批准。
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
- M2：实现 + 负向/回放测试（批准后）。
- M3：集成（协调 PR）。
- M4：非作者评审 + 评估记录。

## 8. 具体示例

> 已有终局决策 `d-001`。新决策 `d-002` 必须写成 `revision`，并设 `superseded_by: d-002`；直接覆盖 `d-001` 必须被拒绝。

## 9. 自包含可复制提示词

```text
你是 CS5351 team 的编码代理，负责角色 E（F5 可验证审计+修订+离线回放）。
必读：AGENTS.md、Prompt.md、START-HERE.md、architecture-blueprint.md、
tasks/E-audit.md、docs/req/requirements.yaml、docs/code-governance/*、
docs/architecture/invariants.md、evaluation-table.md 与 trace-matrix.md。

任务范围：仅 FR-005/INV-005，路径限于 tradingagents/course/audit/ 与 test/offline/。
写代码前输出结构化清单；审计权威性变更需 ADR + 人工批准，否则 STOP。
不得覆盖终局决策；不得伪造回放结果；不得读取秘密；默认离线；不得无人值守推送。
```

## 10. 交接（Handoff）

使用模板 `templates/handoff.md`（七类信息），交给评审人 **D**（E 的产出由 D 评审）。

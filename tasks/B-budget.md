# 任务 B：运行预算（F2, run budget）

> 状态：**PROPOSED 计划**。未实现。成员身份未知，不得虚构。
> 先读 `AGENTS.md` 与 `Prompt.md`；严格遵守停止门。

## 1. 交付物（Deliverables）

- 预算账本 `BudgetLedger`：`reserve()` / `settle()` / `release()` / `remaining()`。
- 调用前预留、调用后结算；超额 fail-closed。
- 预算事件记录（供 E 的审计消费）。
- 正/负向测试与评估准备（配合 `docs/evaluation/`）。

## 2. 需求 ID

- 主：`FR-002`
- 关联：`INV-002`、`NFR-001`（成本 -20% 临时目标）、`NFR-002`（质量不劣化 ≤3pp 临时目标）

## 3. 拥有/提议源码路径（PROPOSED，当前不存在）

- `tradingagents/course/budget/`（新增）
- 测试：`test/offline/`（新增）

## 4. 依赖与契约

- 账本状态：`reserved | settled | released`。
- 账本字段（JSON）：
  ```json
  {
    "ledger_id": "...",
    "limit_tokens": 0,
    "limit_calls": 0,
    "reserved": {"tokens": 0, "calls": 0},
    "settled": {"tokens": 0, "calls": 0},
    "events": []
  }
  ```
- 被编排器调用；**不得**直接导入其它叶子模块。

## 5. 冻结范围

- 不改上游 `max_tokens`/`llm_max_retries` 等既有配置语义（这些是**既有能力**，不是本功能）。
- 既有 `tradingagents/**`、`tests/**`、`pyproject.toml` 受保护；不整树替换基线。
- 窄范围集成编辑需：显式 scope + 接口契约 + 人工计划/测试批准；否则 STOP。

## 6. 验收与负向测试

| 项 | 预期 |
|---|---|
| 预留后余额充足 | 允许调用并结算 |
| **超预算调用**（负向） | 被拒绝，fail-closed |
| 结算超过预留（负向） | 记录并终止后续调用 |
| 并发/重复结算 | 幂等或拒绝，不得重复扣减 |

## 7. 里程碑

- M1：账本契约与状态机（文档）。
- M2：实现 + 单元/负向测试（批准后）。
- M3：与编排器集成（协调 PR）。
- M4：建立评估基线（配合 E），评估 20%/≤3pp 目标（如实记录；live 评估需人工明确授权）。

## 8. 具体示例

> 预算 `limit_calls=10`。第 11 次调用必须被拒绝并记录 `budget_exceeded`；不得继续。

## 9. 自包含可复制提示词

```text
你是 CS5351 team 的编码代理，负责角色 B（F2 运行预算）。
必读：AGENTS.md、Prompt.md、START-HERE.md、architecture-blueprint.md、
tasks/B-budget.md、docs/req/requirements.yaml、docs/code-governance/*、
docs/architecture/invariants.md 与 trace-matrix.md。

任务范围：仅 FR-002 / INV-002，路径限于 tradingagents/course/budget/ 与 test/offline/。
写代码前输出结构化清单；无真实的测试/实现计划批准或需窄范围集成/跨角色时 STOP。
默认离线；live 评估需人工显式授权 provider/model/成本上限与安全凭证配置。
不得把上游已有的 token 配置/重试说成新功能；不得伪造评估结果；不得读取/发布凭证；
不得无人值守推送。
```

## 10. 交接（Handoff）

使用模板 `templates/handoff.md`（七类信息），交给评审人 **A**（B 的产出由 A 评审）。

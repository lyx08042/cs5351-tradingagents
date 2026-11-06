# 任务 C：确定性模拟安全（F3, deterministic simulation safety）

> 状态：**PROPOSED 计划**。未实现。成员身份未知，不得虚构。
> 先读 `AGENTS.md` 与 `Prompt.md`；严格遵守停止门。安全相关变更需 **ADR + 人工批准**。

## 1. 交付物（Deliverables）

- `SimulationProposal` schema（含 Hold/no-op 的合法形态）。
- **确定性代码校验器**：判定由确定性代码给出，而非由 LLM 输出“决定”是否安全。
- 提议的 **long-only** 模拟策略（仅是显式选择的当前 scope；可配置策略变更需批准）。
- fail-closed 规则与拒绝原因；正/负向测试与安全文档。

## 2. 需求 ID

- 主：`FR-003`、`SEC-001`
- 关联：`INV-003`、`NFR-003`（确定性）

## 3. 拥有/提议源码路径（PROPOSED，当前不存在）

- `tradingagents/course/safety/`（新增）
- 测试：`test/offline/`（新增）
- ADR（策略/规则变更）：`docs/architecture/adr/`（需人工批准）

## 4. 依赖与契约

- 提议字段（固定）：`action`、`units`、`price`、`currency`、`holdings_snapshot`、`rule_version`、`status`。
- **权威性分工**：LLM 只生成**结构化候选**；**确定性代码**给出 verdict（accept/reject）。不得把“确定的安全结论”归功于“确定性的 LLM 输出”。
- **动作语义（PROPOSED）**：
  - `Hold` / no-op：`units = 0`，合法；仍需 `holdings_snapshot` 与 `rule_version`。
  - `Buy` / `Sell`：`units > 0`，且需满足资金/持仓约束（Buy 需足够 cash；Sell 需足够持仓）。
  - **long-only 策略（仅当前显式 scope）**：拒绝负持仓/负 units；这是**所选策略**，不是“通用禁止负值”。
- **不得默认 flat**：缺失 `holdings_snapshot` 不得假定为空仓；必须拒绝或显式声明。

## 5. 冻结范围

- 既有 trader/PM 公共行为、`tests/`、`pyproject.toml` 受保护；不整树替换基线。
- 窄范围集成编辑需：显式 scope + 接口契约 + 人工计划/测试批准 + 安全 ADR。
- 不连接真实券商（永久排除）。

## 6. 验收与负向测试

| 项 | 预期 |
|---|---|
| 合法 Buy（cash 充足、快照齐全） | accept |
| 合法 Hold（`units=0`，快照齐全） | accept |
| **缺 holdings_snapshot**（负向） | reject |
| **未声明 flat 但持仓为空**（负向） | reject（不得默认 flat） |
| **Buy/Sell units <= 0**（负向） | reject |
| **Buy 超出现金 / Sell 超出持仓**（负向） | reject |
| **units < 0（long-only 下）**（负向） | reject 并记录 |
| **price <= 0**（负向） | reject |
| **LLM 文本声称“安全”但代码判据不满足**（负向） | 以代码 verdict 为准，reject |
| 真实券商执行请求（负向） | 永久 reject |

## 7. 里程碑

- M1：schema（含 Hold）、策略文档 + ADR 草案。
- M2：确定性校验器 + 负向测试（需批准）。
- M3：集成（协调 PR + 窄范围批准）。
- M4：非作者（B）评审。

## 8. 具体示例

> - `{action:"hold", units:0, price:150.0, currency:"USD", holdings_snapshot:{...}, rule_version:"v1"}` → **accept**。
> - `{action:"buy", units:10, price:150.0, currency:"USD", rule_version:"v1"}`（缺快照）→ **reject**，`missing_holdings_snapshot`。
> - `{action:"buy", units:-5, ...}` → **reject**（long-only 策略）。

## 9. 自包含可复制提示词

```text
你是 CS5351 team 的编码代理，负责角色 C（F3 确定性模拟安全）。
必读：AGENTS.md、Prompt.md、START-HERE.md、architecture-blueprint.md、
tasks/C-safety.md、docs/req/requirements.yaml、docs/code-governance/*、
docs/architecture/invariants.md、permission-model.md 与 trace-matrix.md。

任务范围：仅 FR-003/SEC-001/INV-003，路径限于 tradingagents/course/safety/ 与 test/offline/。
写代码前输出结构化清单；安全变更需 ADR + 人工批准，否则 STOP。
不得实现真实下单；不得把 long-only 说成通用禁止负值；不得让 LLM 文本覆盖代码 verdict；
不得伪造测试结果；默认离线；不得无人值守推送。
```

## 10. 交接（Handoff）

使用模板 `templates/handoff.md`（七类信息），交给评审人 **B**（C 的产出由 B 评审）。

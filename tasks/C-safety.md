# 任务 C：确定性模拟安全（F3, deterministic simulation safety）

> ## ⚠️ CURRENT OVERRIDE：`DEVELOPMENT-POLICY.md`（ACTIVE, owner-selected, 2026-11-07）
> 下方所有旧的实现前计划/测试/安全批准、`PENDING`、STOP 要求均为 **HISTORICAL / NOT EXECUTED**，不再阻断本任务实现。写计划+测试设计（工作文档）后**继续实现**，无需 `approval_refs`。**最终 PR + 非作者评审 + CI + 合并授权保留**。课程 **G-1/D9 未满足**；**非教师 waiver、非伪造批准**。`PROPOSED` 不因本政策变为 `APPROVED`。开始前对 feature 分支 `git fetch origin` + `git merge origin/main`（不 reset、不 force）。

> 状态：**PROPOSED 计划**。未实现。成员身份未知，不得虚构。
> 规划顺序：先写计划+测试设计（工作文档），然后继续实现。安全相关变更**创建 ADR/设计记录**，但无实现前批准人。

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
- ADR（策略/规则变更）：`docs/architecture/adr/`（创建记录，无实现前批准人）

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
- 窄范围集成编辑需：明确 scope + 接口契约 + 安全 ADR/设计记录（无实现前批准人）。
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
- M2：确定性校验器 + 负向测试。
- M3：集成（协调 PR + 窄范围 scope）。
- M4：非作者（B）评审。

## 8. 具体示例

> - `{action:"hold", units:0, price:150.0, currency:"USD", holdings_snapshot:{...}, rule_version:"v1"}` → **accept**。
> - `{action:"buy", units:10, price:150.0, currency:"USD", rule_version:"v1"}`（缺快照）→ **reject**，`missing_holdings_snapshot`。
> - `{action:"buy", units:-5, ...}` → **reject**（long-only 策略）。

## 9. 自包含可复制提示词

```text
[CURRENT OVERRIDE — 最高项目政策：DEVELOPMENT-POLICY.md（ACTIVE, owner-selected, 2026-11-07）]
旧的实现前计划/测试/安全批准、PENDING、STOP 要求均为 HISTORICAL / NOT EXECUTED，不阻断本任务实现；
写计划+测试设计（工作文档）后继续实现，无需 approval_refs。课程 G-1/D9 未满足；非教师 waiver、非伪造批准。
最终 PR + 非作者评审 + CI + 合并授权保留；不自动合并 main。开始前 git fetch origin + git merge origin/main（不 reset/force）。

你是 CS5351 team 的编码代理，负责角色 C（F3 确定性模拟安全）。
必读：DEVELOPMENT-POLICY.md、AGENTS.md、Prompt.md、START-HERE.md、architecture-blueprint.md、
tasks/C-safety.md、docs/req/requirements.yaml、docs/code-governance/*、
docs/architecture/invariants.md、permission-model.md 与 trace-matrix.md。

任务范围：仅 FR-003/SEC-001/INV-003，路径限于 tradingagents/course/safety/ 与 test/offline/。
改动前输出计划与测试策略，然后继续实现与验证；不要停在计划。安全变更创建 ADR/设计记录（无实现前批准人）。
仅当真实的范围外/不可逆/凭证问题才请求用户；不因 PENDING、缺失计划批准或 proposed 状态停下。
不得实现真实下单；不得把 long-only 说成通用禁止负值；不得让 LLM 文本覆盖代码 verdict；
不得伪造测试结果；默认离线；不自动合并 main。
```

## 10. 交接（Handoff）

使用模板 `templates/handoff.md`（七类信息），交给评审人 **B**（C 的产出由 B 评审）。

## 11. 实现记录（2026-11-07 起，2026-11-11 更新，如实记录）

- **M2 状态：** 独立模块已完成，准备上传到 `feat/C-safety`；实际上传状态以 GitHub 分支为准，本节不声称已推送。
- **已写入：**
  - `tradingagents/course/safety/models.py`：`SimulationProposal`、`HoldingsSnapshot`、`RuleSet`、`SafetyContext`、`SafetyVerdict`、`ReasonCode`。
  - `tradingagents/course/safety/validator.py`：纯函数 `validate_proposal`。
  - `tradingagents/course/safety/__init__.py`、`tradingagents/course/__init__.py`。
  - `test/offline/test_safety_simulation.py`：固定账户/行情/规则版本的离线正负向测试与确定性回放测试。
  - `docs/architecture/adr/002-simulation-safety.md`：正式安全 ADR（**PROPOSED**，非人工批准）。
  - `tasks/plans/C/FR-003-safety-adr-draft.md`：指向正式 ADR 的草稿入口。
  - `tasks/plans/C/FR-003-handoff.md`：交接、实际验证结果、M3/M4 待办与非作者评审清单。
- **验证口径：** OpenCode 本会话未运行 shell；Codex 调度并独立运行验证。
- **实际结果（2026-11-11，Codex 独立验证）：**
  - 课程离线：`python -m pytest -q -o testpaths=test/offline test/offline` -> **76 passed**（原有脚手架 20，C 新增 56）。
  - 脚手架校验：`python scripts/check_course.py --root .` -> **OK**。
  - 全仓库 `ruff check .` -> **通过**（三处 UP037 已由本 OpenCode 会话修复：仅移除 future-annotations 下多余的注解引号，行为不变）。
  - 上游完整回归（允许本机回环连接并使用工作区临时目录）-> **1407 passed, 6 skipped, 1 deselected, 24 warnings, 100 subtests passed in 41.30s**；第一次受限环境因临时目录权限与回环连接失败，修正环境后通过。
- **历史修复：** `_exact_product` 改为从显式 `Context` 构建（固定 precision/范围/舍入/clamp/traps，不继承调用者状态）；非法 `SafetyContext.rule_set` 返回 `invalid_rule_set`，拒绝路径不二次抛异常。
- **M3 待办：** 共享 CLI、图节点、CI、成员 A/B/D/E 代码、`tests/`、`pyproject.toml` 均未改动；未接入 `record_decision()`，未发布“已验证模拟提案”；集成需协调 PR。
- **M4 待办：** 非作者（B）评审尚未发生；不得声称已评审。
- **课程差异：** 按 `DEVELOPMENT-POLICY.md` 推进，G-1/D9 未满足；非教师 waiver、非伪造批准。
- **待确认：** 结构化候选来源、可信报价/币种口径、`PortfolioContext` → `HoldingsSnapshot` 映射、规则目录 owner、Hold 的价格语义、与 D/E 的交接字段。详见正式 ADR 第 6 节。

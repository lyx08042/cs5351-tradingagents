# 任务 A：证据约束辩论（F1, evidence-grounded debate）

> ## ⚠️ CURRENT OVERRIDE：`DEVELOPMENT-POLICY.md`（ACTIVE, owner-selected, 2026-11-07）
> 下方所有旧的实现前计划/测试/安全批准、`PENDING`、STOP 要求均为 **HISTORICAL / NOT EXECUTED**，不再阻断本任务实现。写计划+测试设计（工作文档）后**继续实现**，无需 `approval_refs`。**最终 PR + 非作者评审 + CI + 合并授权保留**。课程 **G-1/D9 未满足**；**非教师 waiver、非伪造批准**。`PROPOSED` 不因本政策变为 `APPROVED`。开始前对 feature 分支 `git fetch origin` + `git merge origin/main`（不 reset、不 force）。

> 状态：**PROPOSED 计划**。未实现。成员身份未知，不得虚构。
> 规划顺序：先写计划+测试设计（工作文档），然后继续实现。

## 1. 交付物（Deliverables）

- 证据单元（`EvidenceUnit`）与断言绑定（`Claim→evidence_ref`）的契约。
- 证据新鲜度/可用性校验（**可与分析日期不同**，见第 4 节）。
- 断言分类器：区分**事实性断言**（须有证据）与**预测性断言**（必须标为假设）。
- 正/负向测试与文档更新。

## 2. 需求 ID

- 主：`FR-001`
- 关联：`INV-001`、`NFR-002`、`NFR-005`、`FR-004`（证据可用性对齐）

## 3. 拥有/提议源码路径（PROPOSED，当前不存在）

- `tradingagents/course/evidence/`（新增）
- 测试：`test/offline/`（新增）
- 文档：`docs/architecture/` 中与本角色相关条目

## 4. 依赖与契约

- 消费上游工具输出与报告（**只读**，不改其公共行为，BASE-001）。
- 契约（JSON 可序列化）：
  ```json
  {
    "evidence_id": "ev-...",
    "source": "tool|report",
    "published_at": "YYYY-MM-DD",
    "available_as_of": "YYYY-MM-DD",
    "status": "available|unavailable|unknown",
    "freshness_policy": "configurable",
    "content_ref": "..."
  }
  ```
- **日期语义**：证据的 `published_at` / `available_as_of` 必须 **<=** 分析日期（`as_of` cutoff），防止未来信息泄漏（look-ahead）。**证据日期可以早于分析日期**，不要求相等；是否算“新鲜”由**可配置新鲜度策略**决定，而非一律拒绝。
- 与 D（`data_quality`）对齐状态语义；**不得**直接导入其它叶子模块。

## 5. 冻结范围

- 既有 `tradingagents/**`、`cli/**`、`tests/**`、`pyproject.toml`、`LICENSE` 受保护；**不得整树替换基线**。
- 如需在既有模块内做**窄范围集成编辑**（例如把证据校验接入辩论节点），需明确书面 scope + 接口契约（实现前人工批准不再是硬门；安全/接口变更创建 ADR/设计记录，无实现前批准人）。
- 不改预算/安全/审计模块。

## 6. 验收与负向测试

| 项 | 预期 |
|---|---|
| 事实性断言 + 日期合法的证据 | 通过并保留 evidence_ref |
| **无证据的事实性断言**（负向） | 标注为假设或 abstain，不得作为确定性结论 |
| **证据日期晚于分析日期**（负向，未来泄漏） | 拒绝该证据 |
| 证据日期早于分析日期但在可配置新鲜度窗口内 | 允许（不是缺陷） |
| **预测性断言**（如“股价将上涨”） | 始终标为假设，不得因匹配了证据 ID 而当作已验证事实 |

## 7. 里程碑

- M1：契约、日期语义与新鲜度策略文档（无代码）。
- M2：校验器 + 单元/负向测试。
- M3：集成到辩论（协调 PR + 窄范围集成批准）+ 负向测试。
- M4：非作者（E）评审 + 记录。

## 8. 具体示例

> 断言：“MACD 已金叉。”
> - 若存在 market 工具证据（`ev-macd-...`，日期 <= 分析日期且新鲜度合格）→ **作为事实性指标支持**，绑定 evidence_ref。
>
> 断言：“股价将上涨。”
> - 这是**预测**；即使有 MACD 证据，也只能标为 **假设（hypothesis）**，不得视为已证实。匹配证据 ID **不**等于验证了未来预测。

## 9. 自包含可复制提示词

```text
[CURRENT OVERRIDE — 最高项目政策：DEVELOPMENT-POLICY.md（ACTIVE, owner-selected, 2026-11-07）]
旧的实现前计划/测试/安全批准、PENDING、STOP 要求均为 HISTORICAL / NOT EXECUTED，不阻断本任务实现；
写计划+测试设计（工作文档）后继续实现，无需 approval_refs。课程 G-1/D9 未满足；非教师 waiver、非伪造批准。
最终 PR + 非作者评审 + CI + 合并授权保留；不自动合并 main。开始前 git fetch origin + git merge origin/main（不 reset/force）。

你是 CS5351 team 的编码代理，负责角色 A（F1 证据约束辩论）。
必读：DEVELOPMENT-POLICY.md、AGENTS.md、Prompt.md、START-HERE.md、architecture-blueprint.md、
tasks/A-evidence.md、docs/req/requirements.yaml、docs/code-governance/*、
docs/architecture/invariants.md 与 trace-matrix.md。

任务范围：仅 FR-001 / INV-001，路径限于 tradingagents/course/evidence/ 与 test/offline/。
改动前输出计划与测试策略（requirement/trace/interface/invariants/risk/negative tests/
change scope/steps），然后继续实现与验证；不要停在计划。
仅当真实的范围外/不可逆/凭证问题才请求用户；不因 PENDING、缺失计划批准或 proposed 状态停下。
不得伪造证据/结果/批准；不得读取秘密；默认离线；不自动合并 main。
```

## 10. 交接（Handoff）

使用模板 `templates/handoff.md`（七类信息），按评审环交给 **E**（A 的产出由 E 评审；A 也评审 B 的产出）。

# FR-003 交接｜C 确定性模拟安全（F3）

> 状态：**M2 独立模块已完成，准备上传到 `feat/C-safety`**。实际上传状态以 GitHub 分支为准；本文**不声称已推送**。
> **M3 正常入口集成**与 **M4 非作者评审**仍待办。本文是交接记录，**不是**人工批准，也不改变 ADR-002 的 `PROPOSED` 状态。
> 证据口径：OpenCode 本会话未运行 shell；Codex 调度并独立运行验证（2026-11-11）。

## 0. 里程碑状态

| 里程碑 | 状态 |
|---|---|
| M2 独立模块（C 自有路径 + 离线测试） | **完成，准备上传**；业务代码与测试保持当前版本 |
| M3 正常入口集成（CLI/图节点协调 PR） | **待办** |
| M4 非作者评审（B） | **待办** |
| 上传/PR/合并 | 以 GitHub `feat/C-safety` 分支为准；本文不声称已推送或已合并 |

## 1. 对应需求

| 需求 | 覆盖方式 |
|---|---|
| FR-003 | 结构化 `SimulationProposal` + 确定性 `validate_proposal` |
| INV-003 | 缺快照不默认 flat；Hold=0；Buy/Sell units>0；资金/持仓校验；long-only 显式 |
| SEC-001 | 真实执行请求永久拒绝；无券商/网络/凭证访问 |
| NFR-003 | 纯函数、稳定原因码、重复回放一致；Decimal 使用显式 Context，不继承调用者状态 |

## 2. 已实现（C 自有路径）

- `tradingagents/course/safety/models.py`
  - `SimulationProposal`（固定字段 `action/units/price/currency/holdings_snapshot/rule_version/status`）
  - `HoldingsSnapshot`、`RuleSet`、`SafetyContext`、`SafetyVerdict`、`ReasonCode`
- `tradingagents/course/safety/validator.py`
  - `validate_proposal(proposal, *, context) -> SafetyVerdict`
  - 候选快照/规则/状态均不可信；只使用 `SafetyContext` 中的可信快照与规则
  - 精确成本计算：显式 `Context(prec=64, Emin=MIN_EMIN, Emax=MAX_EMAX, ROUND_HALF_EVEN, clamp=0, traps=[])`；输入超界或结果不精确 -> `amount_precision_unsupported`
  - 非法 `rule_set` 类型 -> `invalid_rule_set`，拒绝路径不二次抛异常
- `tradingagents/course/safety/__init__.py`、`tradingagents/course/__init__.py`（包标记）
- `test/offline/test_safety_simulation.py`：C 的 56 个离线测试（固定账户/行情/规则版本）
- `docs/architecture/adr/002-simulation-safety.md`：正式安全 ADR（**PROPOSED**，非人工批准）
- `tasks/plans/C/FR-003-safety-adr-draft.md`：指向正式 ADR 的草稿入口
- `tasks/plans/C/FR-003-handoff.md`：本文件

## 3. 未接入边界（M3 待办）

- M2 只覆盖 C 自有路径；共享 CLI、图节点、CI、成员 A/B/D/E 代码、`tests/`、`pyproject.toml` 未改。
- 未在 `TradingAgentsGraph.record_decision()` 或 CLI 收尾处调用校验器。
- 未发布“已验证模拟提案”；当前 C 只提供可离线调用的纯校验器。
- 没有结构化候选来源：PM 当前只输出 `final_trade_decision` 文本与 `final_rating`（`tradingagents/agents/managers/portfolio_manager.py:78-86`），没有 `units/price`。

## 4. 实际验证结果（2026-11-11，Codex 独立运行）

OpenCode 本会话未运行 shell；以下由 Codex 独立执行：

```bash
python -m pytest -q -o testpaths=test/offline test/offline
# 76 passed（原有脚手架 20，C 新增 56）

python scripts/check_course.py --root .
# OK

ruff check .
# passed
```

上游完整回归（允许本机回环连接并使用工作区临时目录）：

```text
1407 passed, 6 skipped, 1 deselected, 24 warnings, 100 subtests passed in 41.30s
```

说明：第一次受限环境出现临时目录权限与回环连接失败；修正运行环境后上述上游回归通过。`ruff check .` 的三处 UP037 已由本 OpenCode 会话修复（仅移除 `from __future__ import annotations` 下多余的注解引号，行为不变）。

## 5. M3 正常入口集成：协调 PR 摘要（待办）

最小接入点：

- `TradingAgentsGraph.record_decision()`：`tradingagents/graph/trading_graph.py:359`
- CLI 收尾：`cli/run.py:353`
- 账户上下文：`tradingagents/portfolio.py:33-38`

建议改动（协调 PR）：

1. 由调用方取得结构化候选（action/units/price/currency），不从评级文本猜数量。
2. 从可信账户源与规则目录构造 `SafetyContext`；`PortfolioContext` 三态（有持仓/显式空仓/无上下文）必须保留，无上下文不得当作 flat。
3. 在共同收尾点调用 `validate_proposal`；仅 `accepted` 时发布“已验证模拟提案”。
4. 拒绝时保留稳定 `reason_code`、可信 `snapshot_id`/`rule_version` 供 E 审计；原始报告文本仍作为分析证据。
5. 不改变既有 `final_rating`/报告/返回语义；不新增真实执行路径。

## 6. 证据与会话

- 工具：OpenCode 1.19.5
- 模型：`opencode/deepseek-v4.1-flash-free`
- Session：`ses_e49959e9effeVEnDsA1Cja2ZYI`
- 编排：Codex 调度 OpenCode；Codex 独立运行上述验证（离线测试、checker、ruff、上游回归）。
- 未进行交易应用实时 API 调用；未连接真实券商；未读凭证。
- **无人工批准或人工评审记录**；不得声称已批准或已评审。
- 课程差异：按 `DEVELOPMENT-POLICY.md` 推进，**G-1/D9 未满足**；非教师 waiver、非伪造批准。

## 7. M4 非作者评审清单（C 的产出由 B 评审；当前待办）

- [ ] FR-003/INV-003/SEC-001/NFR-003 覆盖与任务书一致
- [ ] 快照/规则/结果来源独立，候选伪造被拒
- [ ] 缺失快照不默认 flat；显式空仓需 `flat_declared`
- [ ] Buy/Sell/Hold 语义与 long-only 负值拒绝正确
- [ ] 非正/非有限价格、币种不一致、未知/缺失规则版本被拒
- [ ] 真实执行请求永久拒绝
- [ ] LLM 自报安全不能覆盖代码 verdict
- [ ] Decimal 显式 Context 不继承调用方 precision/trap/clamp；超界/不精确拒绝
- [ ] 非法 `SafetyContext.rule_set` 返回稳定原因且不二次抛异常
- [ ] 正负向测试覆盖，命令可复现
- [ ] 未改共享代码、依赖、既有测试
- [ ] 非作者（B）真实评审记录；**M4 待办，当前尚无**

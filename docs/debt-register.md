# 技术债登记簿

> 状态：**模板 + 基线初始条目**。不含虚构历史条目。
> 类别：prompt rot / hallucinated deps / untouchable code / hidden deps / bloat / evaluation / guardrail / human cognitive。

## 条目格式

```yaml
- id: DEBT-000x
  category: <prompt-rot|hallucinated-deps|untouchable-code|hidden-deps|bloat|evaluation|guardrail|human-cognitive>
  title: <简短标题>
  description: <事实描述>
  impact: <影响>
  related: [<需求/文件>]
  status: <open|accepted|mitigated|wontfix>
  discovered_at: <YYYY-MM-DD>
```

## 初始条目（引导阶段真实记录）

```yaml
- id: DEBT-001
  category: evaluation
  title: 20% 成本与 ≤3pp 质量目标尚无基线
  description: 目标是团队临时目标，尚未进行重复评估。
  impact: 无法验证 NFR-001/NFR-002。
  related: [NFR-001, NFR-002]
  status: open
  discovered_at: "2026-11-06"

- id: DEBT-002
  category: guardrail
  title: 测试/计划批准与安全 ADR 的 gate 尚未自动化
  description: 当前依赖人工流程；没有强制检查。
  impact: 依赖人类纪律，存在绕过风险。
  related: [GOV-001]
  status: open
  discovered_at: "2026-11-06"

- id: DEBT-003
  category: human-cognitive
  title: 目录布局是否迁移待教师确认
  description: 根 architecture-blueprint.md 与 docs/architecture/ 的路径差异未决。
  impact: 可能出现双份文档漂移。
  related: [AMB-01]
  status: open
  discovered_at: "2026-11-06"

- id: DEBT-004
  category: untouchable-code
  title: 上游 tests/ 与 pyproject.toml 冻结
  description: BASE-001/002 要求保持既有测试与依赖不变，限制了重构空间。
  impact: 扩展只能新增模块。
  related: [BASE-001, BASE-002]
  status: accepted
  discovered_at: "2026-11-06"

- id: DEBT-005
  category: guardrail
  title: Owner 取消实现前批准导致课程 G-1/D9 未满足（课程偏离）
  description: >
    Owner @lyx08042 于 2026-11-07 在当前对话中显式决定取消所有成员的实现前批准，
    在被告知这违反课程实现前测试/计划批准要求后仍选择为之。由 Codex 编排 OpenCode
    记录，非教师批准。见 DEVELOPMENT-POLICY.md。GOV-001 保持原始课程表述并标注为 not_satisfied。
  impact: >
    缺失课程阻断 gate G-1 与 D9 计划/停止要求及相关人工监督；本仓库不得声称课程合规。
    非 waiver、非伪造批准；真实历史批准保持原样。
  related: [GOV-001, G-1, D9]
  status: accepted
  discovered_at: "2026-11-07"
```

## 说明

- 新条目只能如实记录已观察到的债务；不得预填虚假条目。

## A 模块剩余项（2026-11-21，FR-001 / INV-001）

```yaml
- id: DEBT-A-001
  category: evaluation
  title: A14 全员共享基线联调（A+B+C+D+E）与在线语义对比评估尚未执行
  description: >
    当前 PR #5（M1–M2）与 PR #6（M3）基于 feat/A-evidence 独立验证，已通过脚本化离线端到端
    测试（A01–A13），但 PR #3（CDE）、PR #4（B）、PR #5/#6（A）尚未合入同一主线基线，
    因此全员联合回归（A14）与基于真实 LLM 的在线语义评估（NFR-002 / G-4）均未执行。
  impact: 无法在单分支内证明跨模块联调通过或报告真实模型下的质量差值（pp）。
  related: [FR-001, INV-001, NFR-002, docs/architecture/adr/006-evidence-debate-integration.md]
  status: open
  owner: A
  discovered_at: "2026-11-21"

- id: DEBT-A-002
  category: guardrail
  title: 预算上下文压缩下保护 A 的 as_of、evidence_ref 与证据约束待共享编排层统一接线
  description: >
    交叉评审 B（PR #4）确认 tradingagents/course/budget/context.py 超过 12,000 tokens 压缩时
    仅重注入四个通用块，可能裁掉 A 的分析日期、证据引用与证据约束提示；双方已约定在后续全组
    协调集成 PR 的共享编排器中将 A 的必保证据锚点纳入不可裁剪与重注入校验清单。
  impact: 若直接串联 B 压缩与 A 证据辩论而未加保护，压缩后可能导致证据引用丢失并触发大面积 abstain。
  related: [FR-001, INV-001, FR-002, INV-002, docs/review-memo.md]
  status: open
  owner: A
  discovered_at: "2026-11-21"

- id: DEBT-A-003
  category: hidden-deps
  title: Fact.period 仅支持严格 YYYY-MM-DD 单日，且提示目录未对同 ID 幂等重复记录去重
  description: >
    M2/M3 面向市场指标单日事实，Fact.period 强制校验 YYYY-MM-DD（暂不支持如 2026-Q2 / FY2025
    等财务报告周期）；另在 M3 对抗检查中观察到当采集侧向 EvidenceRegistry.build 传入两条完全一致
    的同 ID 证据时，build_evidence_catalog 会在提示目录中列出两份同 ID 项（不破坏确定性或不变量）。
  impact: 扩展至基本面季度财报事实前需经 ADR 扩充周期类型；幂等重复输入会轻微增加提示词 token。
  related: [FR-001, tradingagents/course/evidence/contracts.py, tradingagents/course/evidence/integration.py]
  status: accepted
  owner: A
  discovered_at: "2026-11-21"
```

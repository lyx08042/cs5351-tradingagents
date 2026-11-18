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

## E 模块剩余项（2026-11-14，FR-005）

```yaml
- id: DEBT-E-001
  category: evaluation
  title: 全链验证每次 O(n)，连续追加总成本 O(n^2)
  description: verify_chain 每次全量扫描；适合小规模审计，未做增量/缓存优化。
  impact: 大规模或高频写入场景性能受限。
  related: [FR-005, tradingagents/course/audit/store.py]
  status: accepted
  owner: E
  discovered_at: "2026-11-14"

- id: DEBT-E-002
  category: guardrail
  title: 定位为小规模审计使用
  description: 当前实现面向课程规模审计，不是高吞吐生产审计服务。
  impact: 超出规模需另行设计。
  related: [FR-005]
  status: accepted
  owner: E
  discovered_at: "2026-11-14"

- id: DEBT-E-003
  category: guardrail
  title: 可信头必须外存；实现非签名、非 WORM
  description: 内部链无法察觉整段尾截断或整体重算哈希，需可信方在库外保存 trusted_head；记录不是密码学签名。
  impact: 无外部 checkpoint 时无法证明未被尾部截断。
  related: [INV-005, docs/architecture/adr/003-append-only-audit.md]
  status: accepted
  owner: E
  discovered_at: "2026-11-14"

- id: DEBT-E-004
  category: hidden-deps
  title: 生产主流程真实入口尚未接入（M3）
  description: E 已作为独立叶子模块完成，回放核心已实现；与主流程的真实接入属协调 PR。
  impact: E 能力尚未在主运行路径生效。
  related: [FR-005]
  status: open
  owner: E (coordination PR)
  discovered_at: "2026-11-14"

- id: DEBT-E-005
  category: human-cognitive
  title: 真实 D 非作者评审待做（M4）
  description: 作者侧已列评审清单，独立评审人/日期/结论待 D 真实填写。
  impact: 尚无独立人评审结论。
  related: [FR-005, tasks/plans/E/FR-005-review-notes.md]
  status: open
  owner: D
  discovered_at: "2026-11-14"

- id: DEBT-E-006
  category: guardrail
  title: 课程共享 CI 尚未自动运行 E 测试
  description: 本轮由 Codex 本地实际运行 E 测试与 ruff；共享 CI 是否纳入 E 测试属全组治理，不是 E 功能未实现。
  impact: 合并前依赖人工/本地执行。
  related: [FR-005, .github/]
  status: open
  owner: shared (course CI)
  discovered_at: "2026-11-14"
```


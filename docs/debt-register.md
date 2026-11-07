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

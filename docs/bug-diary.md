# Bug 日记

> 状态：**模板**。不含虚构历史条目。仅记录**真实观察到**的缺陷或可疑行为。
> 未经证实的差异必须标注“未证明为 bug”。

## 条目格式

```yaml
- id: BUG-000x
  title: <简短标题>
  observed_at: <YYYY-MM-DD>
  environment: <commit / 模型 / 配置>
  steps: <复现步骤>
  expected: <预期>
  actual: <实际>
  evidence: <日志/文件引用，脱敏>
  status: <open|confirmed|fixed|wontfix|needs-review>
  owner: <角色代码>
```

## 初始观察（引导阶段，来自真实基线运行）

```yaml
- id: BUG-001
  title: 未提供持仓时仍出现条件性仓位表述
  observed_at: "2026-11-06"
  environment: "上游 v0.7.1 @ 9fa1196；NVDA 2026-09-01；见 docs/baseline.md"
  steps: "运行一次分析且不传 portfolio"
  expected: "无持仓信息时，建议应面向读者自己的仓位，而非假设具体仓位"
  actual: "最终决策出现条件性 sizing 表述"
  evidence: "docs/baseline.md（脱敏数字）"
  status: needs-review
  owner: C
  note: "未证明为 bug；需人工判断是否为设计行为。"

- id: BUG-002
  title: 历史新闻/社交数据不可用 + FRED 无 key，导致缺失 feed 被计为 neutral（5 处）
  observed_at: "2026-11-06"
  environment: "上游 v0.7.1 @ 9fa1196；见 docs/baseline.md"
  steps: "无 FRED_API_KEY；运行日期早于当前"
  expected: "缺失应标 unavailable，而非 neutral"
  actual: "缺失 feed 被计为 neutral 5 处"
  evidence: "docs/baseline.md"
  status: needs-review
  owner: D
  note: "正是 FR-004/INV-004 要解决的问题；尚未实现。"

- id: BUG-003
  title: 成交量条件 150M vs 298.9M 差异
  observed_at: "2026-11-06"
  environment: "上游 v0.7.1 @ 9fa1196"
  steps: "观察决策中的成交量条件"
  expected: "待人工判断"
  actual: "使用 150M 条件而非 298.9M"
  evidence: "docs/baseline.md"
  status: needs-review
  owner: A
  note: "可能是有意决策，未证明为 bug；不得在报告中断言为缺陷。"
```

## 说明

- 不得虚构复现步骤或日志。
- `evidence` 只引用脱敏后的仓库内文件。

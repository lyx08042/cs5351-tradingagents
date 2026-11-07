# Test Plan: FR-004

- 作者：Chaoqun ZHENG ID: 60569580
- 评审人（非作者）：Jingbin ZHANG
- 批准状态：PENDING

## 范围

- 功能：FR-004 全局数据充分性（available / unavailable / unknown 区分，default-deny unknown）
- 不变量：INV-004（unavailable 与 unknown 不得被当作 neutral；下游必须显式处理，默认拒绝）
- 关联非功能：NFR-004（abstain/review 事件需可留痕；实际持久化由 E 模块负责，本模块只产出事件记录）
- 路径：`tradingagents/course/data_quality/`（新增）；离线测试：`test/offline/`（新增）

## 数据域与状态约定

- 数据域（domain）：`news`、`social`、`macro`、`price`、`fundamentals`
- 状态（status）：
  - `available`：数据存在、非空、对分析日期有效；
  - `unavailable`：数据源明确返回无该日期数据（如无 FRED key、当日新闻不可用）；
  - `unknown`：没有探测结果或探测结论不明确，按 default-deny 视为不足。
- `neutral` 只能是显式数据语义（例如情绪评分恰好为 0），不能作为缺失/不可用/未知的默认值。

## 状态标签契约（输入/输出 JSON）

    {
      "domain": "news|social|macro|price|fundamentals",
      "status": "available|unavailable|unknown",
      "as_of": "YYYY-MM-DD",
      "reason": "..."
    }

## 正向测试

| 用例 | 输入 | 预期 |
| --- | --- | --- |
| PT-1 全部关键域 available | 五个域均为 `available`，日期一致 | 准入决策 `proceed`，不产生 abstain/review |
| PT-2 显式 neutral 被接受 | 某域情绪评分为显式 0（`neutral` 语义），其余域 `available` | 允许进入下游；`neutral` 标签被保留并标注来源 |
| PT-3 某域 unavailable 时降级 | 一个域为 `unavailable`，其余 `available` | 决策 `abstain` 或 `review`，列出不足域与原因，不进入后续决策 |

## 负向测试（每个功能至少一个）

| 用例 | 输入 | 预期（fail-closed / abstain / review） |
| --- | --- | --- |
| NT-1 unknown 被当作充分（负向） | 某域状态为 `unknown` | 视为不足，决策 `abstain`/`review`；不得判为 `available` 或 `proceed` |
| NT-2 unavailable 被误标 neutral（负向） | 把 `unavailable` 的域改标为 `neutral` | 标签校验拒绝该标签，记录违规，不得放行 |
| NT-3 缺失域被默认填 0/中性（负向） | 缺失字段被默认填充 0 或 `neutral` 占位 | 拦截该默认填充并记录，按不足处理 |
| NT-4 unknown 被误标 neutral（负向） | 把 `unknown` 的域改标为 `neutral` | 标签校验拒绝，按不足处理 |

## 回归

- [ ] 上游 `pytest` 通过（BASE-002）
- [ ] 不修改 `tests/`
- [ ] 不修改既有 `tradingagents/**`、`cli/**`、`pyproject.toml`
- [ ] 新离线测试可在无网络、无 LLM/API key 环境下运行

## 判定标准

- 来自 `requirements.yaml` 的 fit：`unavailable/unknown 被误标为 neutral 的次数 = 0`。
- 度量方式：上述负向用例全部拦截；误标计数为 0。
- 所有决策事件（proceed/abstain/review）带域、状态、日期、原因，可供后续审计留痕。

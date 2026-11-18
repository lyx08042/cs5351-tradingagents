# Test Plan: FR-004

- 作者：编码代理（role D）— 成员姓名未知，不虚构
- 评审人（非作者）：C（计划，未评审）
- 状态：DRAFT（工作文档，非批准门）
- 批准引用（可选，历史）：`docs/approvals/test-plan-FR-004.md`（PENDING，仅作设计输入）

## 范围

- 功能：FR-004（available / unavailable / unknown 区分，default-deny unknown）
- 不变量：INV-004（unavailable、unknown 不得当作 neutral）
- 关联 NFR：NFR-004（拒绝/abstain/review 事件含可检索字段；持久化归 E）
- 路径：`tradingagents/course/data_quality/`（新增）；测试 `test/offline/test_data_quality.py`（新增）
- 全离线：无网络、无 LLM/API；固定日期 fixture（`CUTOFF = "2026-11-05"`），不读系统时间。

## 固定 fixture 约定

- 基准日 `CUTOFF = "2026-11-05"`；早于/等于为合法，晚于为未来（future）。
- 五域：`news, social, macro, price, fundamentals`。
- 「显式 0」：`kind="value", value_present=True, value=0`；「缺失」：`kind="missing", value=None, value_present=False`。

## 判定优先级（与 approval record clarification 4 一致）

1. 非法输入 / 缺必需域 / 重复冲突域 / 标签违规 / 非法或未来日期 / 任一 `unknown` -> `review`
2. 否则任一 `unavailable` -> `abstain`
3. 仅当五域全部有效且 `available` -> `proceed`

> `unknown` 一律 `review`（不映射为 abstain），并记入 `insufficient_domains`；
> `unavailable` 一律 `abstain`。

## 正向测试

| 用例 | 输入 | 预期 |
|---|---|---|
| PT-1 全可用 | 五域 `available`，`as_of` 均 `<= CUTOFF` | `decision=proceed`；`insufficient_domains=[]` |
| PT-2 显式 0/neutral | social 显式 `sentiment=0`（`value=0, value_present=True`），其余 available | `proceed`；social 标签 `status=available`、`sentiment=0`、含 `source` |
| PT-3 一域 unavailable | news=unavailable，其余 available | `abstain`（或 review），`insufficient_domains=["news"]`，含 reason |
| PT-early 早于截止的合法证据 | 某域 `as_of=CUTOFF-30d` | 与 PT-1 同样 `proceed`（证据日可早于分析日） |

## 负向测试

| 用例 | 输入 | 预期（fail-closed） |
|---|---|---|
| NT-1 域 unknown | macro=unknown，其余 available | `review`；`insufficient_domains` 含 macro；不得 `available`/`proceed` |
| NT-2 unavailable 改标 neutral | 把 news unavailable 的标签 `status="neutral"` | 标签校验拒绝（`violations` 记录）；`decision=review`；不 release |
| NT-3 缺失默认填 0/neutral | news `kind="missing"` 但 `value=0`（或 placeholder neutral） | 拦截并记 `violations`；视为不足 -> `abstain`/`review`；不 `proceed` |
| NT-4 unknown 改标 neutral | 把 macro unknown 的标签 `status="neutral"` | 拒绝标签；`review`；按不足处理 |
| NT-5 空输入 | `[]` | `review`，列出全部五域为不足 |
| NT-6 缺必需域 | 只给 4 域 | `review`，缺域记入 `insufficient_domains` |
| NT-7 重复冲突域 | news 出现两次且状态冲突 | `review`，记录冲突 |
| NT-8 非法 domain | `domain="weather"` | `review`（未知域 fail-closed） |
| NT-9 非法 status | `status="partial"` | `review` |
| NT-10 非法日期 | `as_of="2026-13-40"` | `review`（invalid_date） |
| NT-11 未来日期 | `as_of > CUTOFF` | `review`（future_date） |
| NT-12 非法 cutoff | `analysis_cutoff="not-a-date"` | `review`（invalid_cutoff） |

## 扩展/一致性

- 显式 0 与缺失的区分：同一域 `value=0,value_present=True` -> available；`value=None,value_present=False` -> 不足。
- 确定性：同一输入连续两次 `admit()`，`to_dict()` 相等。
- 留痕完整性：任何 `abstain`/`review` 的 `labels` 均含 domain/status/as_of/reason，
  `decision`、`insufficient_domains`、`reason` 均存在且 JSON 可序列化。

## 回归

- [ ] `python scripts/check_course.py --root .`
- [ ] 定向 `pytest -o testpaths=test/offline test/offline/test_data_quality.py`
- [ ] 上游 `pytest`（BASE-002）
- [ ] `ruff check .`
- [ ] 不修改 `tests/`、`tradingagents/**`（除新增 course/）、`pyproject.toml`

## 判定标准

- 来自 requirements.yaml fit：`unavailable/unknown 被误标为 neutral 的次数 = 0` -> 上述负向用例全部拦截。
- 每个 `abstain`/`review`/`proceed` 事件均带域、状态、日期、原因、不足域清单（NFR-004 可检索字段）。

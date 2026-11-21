# 评审备忘（模板）

> 状态：**模板**。不含历史评审记录。
> 评审人**不得**是作者本人。评审须基于真实提交与真实测试。

## 基本信息

- PR / commit：<待填>
- 作者：<待填>
- 评审人（非作者）：<待填>
- 评审日期：<待填>
- 关联需求 ID：<FR-00x / INV-00x / NFR-00x>

## 检查清单

| 项 | 状态（pass / fail / n/a） | 说明 |
|---|---|---|
| 测试计划已批准（`docs/approvals/`） | | |
| 实现计划已批准 | | |
| 安全变更 ADR（如适用） | | |
| 至少一个负向测试 | | |
| 未削弱既有测试 | | |
| 未修改 `tests/` | | |
| 叶子模块无循环导入 | | |
| 缺失语义 = unavailable/neutral 区分 | | |
| fail-closed 行为验证 | | |
| ai-use-log 已更新 | | |
| 文档状态标注真实 | | |

## 发现

- 优点：<待填>
- 问题：<待填>
- 建议：<待填>

## 结论

<approve / request changes / reject>（只可基于真实检查填写）

> 本模板不会自动产生通过结论。

## 记录

### PR #4 — feat(B): FR-002 run budget with a degradation ladder

- PR / commit: #4 — round 1 reviewed at `cba1277`, fixes in `b23f541`
- 作者: 60399223 SONG Yixin (role B)
- 评审人（非作者）: A
- 评审日期: 2026-11-21
- 关联需求 ID: FR-002, FR-006, INV-002, INV-006

#### Round 1 — verdict: CHANGES REQUIRED

Four items were raised against `cba1277`; all four were accepted and fixed in `b23f541`:

| # | Finding | Resolution |
|---|---|---|
| 1 | `AI-USE-0002`, the owner's historical G-1/D9 entry, had been rewritten | Restored verbatim from `origin/main`; only the new AI-USE-0003 entry is added (`git diff origin/main -- docs/ai-use-log.yaml` now shows an addition only) |
| 2 | `reserve()` borrowed quota before validating the call id, and never checked settled ids | Identity is validated before any borrow or charge; settled ids are rejected; two regression tests added |
| 3 | Stage attribution fell back to `analyst` when a caller passes no config (the researchers call `llm.invoke(prompt)`); `include_raw` usage was ignored; a provider returning negative usage leaked the reservation; a single-call overrun was returned downstream | Added `budget_stage()` / `with_stage()` / `stage_resolver`; usage is read from the `raw` member; a failed settlement releases the reservation; an overrun that exhausts the pool raises `BudgetOverrun` carrying the response |
| 4 | Stale counts and statuses in the B documents; `INV-006` missing from the invariant register | Counts aligned to 56 tests, integration described as fourteen lines, ADR-002 and the catalogue recorded as written, `INV-006` added |

Deferred by agreement with the reviewer:

- Protecting A's `as_of` / `evidence_ref` blocks during compaction, and wiring `DegradationPolicy` into the
  runtime — both belong to the shared orchestrator and will be handled in the group integration PR.
- `ADR-002` collides with C's ADR numbering and `tradingagents/course/__init__.py` conflicts with the
  A/CDE branches; both are to be resolved at integration.

#### Checklist (round 2, at `b23f541`)

| Item | Status | Note |
|---|---|---|
| Test plan approved (`docs/approvals/`) | n/a | pre-coding approval disabled by `DEVELOPMENT-POLICY.md`; recorded as a course deviation |
| Implementation plan approved | n/a | same policy; plans are working documents under `tasks/plans/B/` |
| Safety-change ADR | n/a | the module changes no safety boundary; ADR-002 covers the integration point |
| At least one negative test | pass | 56 offline tests; new ones cover duplicate ids, settled-id reuse, negative usage, single-call overrun |
| Existing tests not weakened | pass | `tests/` untouched |
| `tests/` not modified | pass | `git diff origin/main -- tests/` is empty |
| Leaf modules free of cycles | pass | `test_budget_module_does_not_import_sibling_leaf_modules` |
| Missing-data semantics (unavailable vs neutral) | n/a | owned by module D |
| fail-closed behaviour verified | pass | invalid config raises; a denied call never reaches the provider; an overrun raises |
| ai-use-log updated | pass | AI-USE-0003 (history restored) |
| Documentation status truthful | pass | `tasks/plans/B/validation.md` §5 lists what was not verified |

#### Verdict

Round 1: **CHANGES REQUIRED**. Round 2: awaiting the reviewer's re-check; **no approval is claimed here**.
When the reviewer approves on GitHub, record their handle and the date in this table.

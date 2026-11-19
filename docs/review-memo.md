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

- PR / commit: #4 / `a4dff87` (14 commits, 32 files, +8,769 −11)
- 作者: 60399223 SONG Yixin (role B)
- 评审人（非作者）: A — **verbal review on 2026-11-19**
- 评审日期: 2026-11-19
- 关联需求 ID: FR-002, FR-006, INV-002, INV-006

Checklist:

| Item | Status | Note |
|---|---|---|
| Test plan approved (`docs/approvals/`) | n/a | pre-coding approval disabled by `DEVELOPMENT-POLICY.md`; recorded as a course deviation |
| Implementation plan approved | n/a | same policy; plans are working documents under `tasks/plans/B/` |
| Safety-change ADR | n/a | module changes no safety boundary; ADR-002 covers the integration point |
| At least one negative test | pass | over-budget denial, 16-thread oversell, double settlement, level regression |
| Existing tests not weakened | pass | `tests/` untouched (`git diff main -- tests/` is empty) |
| `tests/` not modified | pass | same |
| Leaf modules free of cycles | pass | `test_budget_module_does_not_import_sibling_leaf_modules` |
| Missing-data semantics (unavailable vs neutral) | n/a | owned by module D |
| fail-closed behaviour verified | pass | invalid config raises; a denied call never reaches the provider |
| ai-use-log updated | pass | AI-USE-0003 |
| Documentation status truthful | pass | `tasks/plans/B/validation.md` §5 lists what was not verified |

Findings:

- Strengths: the negative cases target invariants rather than the happy path; the evidence directory makes
  every claim reproducible; the known limits are stated rather than implied.
- Issues: CI initially failed on all four Python versions because two source files carried a UTF-8 BOM,
  which broke `ast.parse` in `tests/test_layering.py`. Fixed in `a4dff87`; CI then passed 8/8.
- Suggestions: write ADR-002 and the runtime policy catalogue (done in this PR), and run the live
  comparison before claiming `NFR-001` / `NFR-002`.

Verdict: **APPROVE (verbal)** — the reviewer examined the branch and reported it acceptable on 2026-11-19.

> Not recorded on GitHub: at the time of writing there was no formal Approve event on the pull request.
> If one is added later, record the reviewer's GitHub handle here and remove this note. This memo does not
> claim a GitHub review that did not happen.

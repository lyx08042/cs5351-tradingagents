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
| 1 | `AI-USE-0002`, the owner's historical G-1/D9 entry, had been rewritten | Restored verbatim from `origin/main`; only the new AI-USE-B-0001 entry is added (`git diff origin/main -- docs/ai-use-log.yaml` now shows an addition only) |
| 2 | `reserve()` borrowed quota before validating the call id, and never checked settled ids | Identity is validated before any borrow or charge; settled ids are rejected; two regression tests added |
| 3 | Stage attribution fell back to `analyst` when a caller passes no config (the researchers call `llm.invoke(prompt)`); `include_raw` usage was ignored; a provider returning negative usage leaked the reservation; a single-call overrun was returned downstream | Added `budget_stage()` / `with_stage()` / `stage_resolver`; usage is read from the `raw` member; a failed settlement releases the reservation; an overrun that exhausts the pool raises `BudgetOverrun` carrying the response |
| 4 | Stale counts and statuses in the B documents; `INV-006` missing from the invariant register | Counts aligned to 58 tests, integration described as fourteen lines, ADR-002 and the catalogue recorded as written, `INV-006` added |

Deferred by agreement with the reviewer:

- Protecting A's `as_of` / `evidence_ref` blocks during compaction, and wiring `DegradationPolicy` into the
  runtime — both belong to the shared orchestrator and will be handled in the group integration PR.
- ADR numbering was resolved on this branch: the B ADR became `007`, so C's `002` stays unique.
  `tradingagents/course/__init__.py` still conflicts with the A/CDE branches and is left to integration.

#### Checklist (round 2, at `b23f541`)

| Item | Status | Note |
|---|---|---|
| Test plan approved (`docs/approvals/`) | n/a | pre-coding approval disabled by `DEVELOPMENT-POLICY.md`; recorded as a course deviation |
| Implementation plan approved | n/a | same policy; plans are working documents under `tasks/plans/B/` |
| Safety-change ADR | n/a | the module changes no safety boundary; ADR-007 covers the integration point |
| At least one negative test | pass | 58 offline tests; new ones cover duplicate ids, settled-id reuse, negative usage, single-call overrun |
| Existing tests not weakened | pass | `tests/` untouched |
| `tests/` not modified | pass | `git diff origin/main -- tests/` is empty |
| Leaf modules free of cycles | pass | `test_budget_module_does_not_import_sibling_leaf_modules` |
| Missing-data semantics (unavailable vs neutral) | n/a | owned by module D |
| fail-closed behaviour verified | pass | invalid config raises; a denied call never reaches the provider; an overrun raises |
| ai-use-log updated | pass | AI-USE-B-0001 (history restored) |
| Documentation status truthful | pass | `tasks/plans/B/validation.md` §5 lists what was not verified |

#### Verdict

Round 1: **CHANGES REQUIRED**. Round 2: awaiting the reviewer's re-check; **no approval is claimed here**.
When the reviewer approves on GitHub, record their handle and the date in this table.

### PR #3 — feat/CDE-integration (reviewed by role B)

- PR / commit: #3 / `afe1215` (48 commits, 72 files, +71,429 / −14)
- 作者: role C (C + D + E integration)
- 评审人（非作者）: 60399223 SONG Yixin (role B)
- 评审日期: 2026-11-21
- 关联需求 ID: FR-003, FR-004, FR-005, INV-003/004/005

Method: static review of the diff and of repository metadata. Nothing was executed locally (no runtime
dependencies, no provider key), so behavioural claims are read, not measured.

| # | Finding | Blocking |
|---|---|---|
| F1 | Three D plans added under `docs/approvals/**`, a human-only path; they belong under `tasks/plans/D/` | yes |
| F2 | C's `adr/002-simulation-safety.md` collided with the B branch's ADR-002 | yes — **resolved**: B renumbered its ADR to `005` |
| F3 | `AI-USE-0003` is duplicated across the B and D branches; this PR already carries D's entry | yes — **resolved**: B renamed its entry to `AI-USE-B-0001` |
| F4 | The five new `test/offline/*.py` files are not collected by any workflow (`testpaths=["tests"]`); CI green does not cover them | no, needs a caveat |
| F5 | `cli/main.py` is a protected baseline file; the scope must be recorded | no, needs a record |

Verdict: **CHANGES REQUIRED** for F1–F3; F4 and F5 need a sentence rather than a code change. Full record:
`tasks/plans/B/review-of-PR3.md`. No approval is claimed.

#### Author response (2026-11-21)

F2 and F3 are resolved on the B side (ADR renumbered to `005`, AI-use entry renamed to `AI-USE-B-0001`).
F4 and F5 were accepted by the author, who will state the offline-test caveat and the CLI scope in the PR
description. F1 remains open: the three plan documents arrived with D's branch and are textually identical to
D's copies, so the decision whether they belong in `docs/approvals/` sits with D and the leader. Re-review is
pending that decision; no approval is claimed.

#### F1 mitigation (2026-11-21)

The leader accepted the reviewer's proposal: the three plan documents carried in from the D branch stay in
`docs/approvals/` **only with a status line** at the top of each file:

> Historical record (D branch). Carried into `main` with the D branch merge. It records a stage approval for
> D's independent module only. It supersedes nothing and is not an approval for the CDE integration. See
> `DEVELOPMENT-POLICY.md`.

Author D agreed to the change. The files sit on a human-only path, so the reviewer did **not** edit them; the
change is made by a member through the GitHub web editor and proposed as a small PR against
`feat/CDE-integration`. This memo records the decision and the owner of the fix, not the fix itself.

Reviewer's approval of PR #3 is conditional on that line landing before `main` first contains those files.
If it does not land, this note is the record that the condition was known and accepted.
## 角色 A 非作者评审记录（A → B，PR #4）

### 基本信息

- PR / commits：PR #4（`feat/B-budget`，https://github.com/lyx08042/cs5351-tradingagents/pull/4）— Round 1 核查 `cba1277`，Round 2 复核 `fa648ce` → 最终 `8a194b2`
- 作者：角色 B（60399223 SONG Yixin，GitHub `@404notfound-s`）
- 评审人（非作者）：角色 A（60825646 Ye Wenhao，GitHub `@MANHO219`）
- 评审日期：2026-11-21（完成 Round 1 提出修改、Round 2 复测与 GitHub Approve）
- 关联需求 ID：`FR-002`、`INV-002`、`FR-006`、`INV-006`（交叉核查 `FR-001`、`INV-001`、`NFR-005`）

### 检查清单（最终基线 `8a194b2`）

| 项 | 状态（pass / fail / n/a） | 说明 |
|---|---|---|
| 测试计划已批准（`docs/approvals/`） | n/a | 按团队现行 `DEVELOPMENT-POLICY.md` 取消实现前批准，保留测试工作计划；课程 G-1/D9 未满足且如实披露 |
| 实现计划已批准 | n/a | 同上，实现计划作为工作文档保存在 `tasks/plans/B/` |
| 安全变更 ADR（如适用） | n/a | 未改变模拟安全裁决规则；`docs/architecture/adr/002-budget-at-the-model-client-boundary.md` 记录模型客户端边界（与 C 的 ADR-002 编号冲突约定在集成 PR 统一重编号） |
| 至少一个负向测试 | pass | 独立离线快照复跑 B 专项 58 passed（覆盖 16 线程并发防超卖、超预算拒绝、重复/已结算 `call_id`、负用量释放、单次打穿 `BudgetOverrun`、降级单调性） |
| 未削弱既有测试 | pass | `git diff origin/main...origin/feat/B-budget -- tests/` 为空，`tests/test_layering.py` 1 passed |
| 未修改 `tests/` | pass | 同上；受保护路径（`.github/`、`scripts/`、`AGENTS.md`、`Prompt.md`、`opencode.json`、`.opencode/`、`docs/approvals/`、`cli/`、`pyproject.toml`、`LICENSE`）diff 均为空 |
| 叶子模块无循环导入 | pass | 仅导入标准库与同叶模块；`tradingagents/course/__init__.py` 无导入、无 UTF-8 BOM |
| 缺失语义 = unavailable/neutral 区分 | n/a | 由角色 D 负责；A/B 压缩时保留 `as_of` 与 `evidence_ref` 约定在全组协调集成 PR 中共同实现 |
| fail-closed 行为验证 | pass | 预留失败零模型调用；非法负用量释放 `outstanding`；单次打穿池上限抛 `BudgetOverrun` 不静默返回 |
| ai-use-log 已更新 | pass | Round 1 发现的历史条目 `AI-USE-0002` 被改写已在 `b23f541` 按 `origin/main` 逐字节恢复，仅追加 `AI-USE-0003` |
| 文档状态标注真实 | pass | `docs/review-memo.md`、`docs/architecture/invariants.md`（补 `INV-006`）、`docs/debt-register.md`（`DEBT-006`）与 58 项测试计数已对齐；保留 `NFR-001`/`NFR-002` 未做在线实测的限定 |

### 发现与修复闭环

- **优点**：账本原子锁、并发与幂等结算设计扎实，单次测试覆盖负向不变量，文档对估算回放与在线评估边界交代诚实。
- **Round 1（`cba1277` → `CHANGES REQUIRED`）提出 4 项均获接受并在 `b23f541`/`4b994e9`/`fa648ce` 修复**：
  1. `docs/ai-use-log.yaml` 历史条目 `AI-USE-0002` 被覆盖改写 → 已从 `origin/main` 原文恢复；
  2. `ledger.py` 先 `_borrow` 再查重且未校验已结算 `_settled` → 已将重复/已结算 ID 校验提前至借调前并补回归测试；
  3. `integration.py` 阶段归属在无 `config` 调用（如 `bull_researcher` / `bear_researcher`）时回落 `analyst`、`include_raw` 字典忽略 `raw` 用量、负用量异常泄漏 `outstanding`、单次打穿静默返回 → 已新增 `budget_stage()` / `with_stage()` / `stage_resolver`、读取 `raw` 用量、异常时 `release`、超额抛 `BudgetOverrun`；
  4. 同步旧文档计数并补齐 `INV-006`，清理旧口头通过记录。
- **Round 2 复测（`fa648ce` → `e95fb5a` / `8a194b2`）**：
  - 独立探针发现 `with budget_stage("debate"):` 与 `"research_manager"` 因 `stage_for_node` 仅匹配节点子串仍回落 `"analyst"` → B 在 `e95fb5a` 中改为先匹配全部 6 个标准 `STAGES` 并补 2 条回归测试（56 → 58），在 `8a194b2` 追加 `DEBT-006`；
  - 最终只读快照复跑：`test_budget*.py` **58 passed**、`test/offline` **78 passed**、`tests/test_layering.py` **1 passed**、`ruff check` 与 `scripts/check_course.py` 均退出 0，全部 6 组独立探针通过。
- **约定留待全组协调集成 PR 的非阻断项**：
  - 上下文超过 12,000 tokens 压缩时保护角色 A 的 `as_of`、`evidence_ref`、事实投影与证据约束，以及在共享编排层接入运行时 `DegradationPolicy`；
  - 合并时统一处理 `ADR-002`（与 C 撞号）、`tradingagents/course/__init__.py` 与 `docs/ai-use-log.yaml` 冲突。

### 结论

- Round 1（`cba1277`）：`CHANGES REQUIRED`
- Round 2（`8a194b2`）：**`APPROVE`**（已由 `60825646 Ye Wenhao` / `@MANHO219` 于 2026-11-21 在 GitHub PR #4 正式提交 Approve）

> 注：角色 A 自己的 PR #5（`faf4065`）与 PR #6（`d59e62f`）须由非作者角色 E（`@lyx08042`）完成正式评审与 Approve，本文件不包含角色 A 对自身 PR 的自我批准。

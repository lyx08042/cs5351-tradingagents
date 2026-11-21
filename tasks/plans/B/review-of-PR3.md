# Review record — PR #3 (CDE integration), reviewer B

- Reviewer: 60399223 SONG Yixin (role B), non-author
- Reviewee: role C's integration branch `feat/CDE-integration`
- PR: #3 — 48 commits, 72 files, +71,429 / −14
- Commit reviewed: `afe1215`
- Date: 2026-11-21
- Method: static review of the diff plus repository checks. **No local execution**: the authoring
  machine has neither the runtime dependencies nor a provider key, so every statement below is either
  read from the diff or read from CI metadata, and is labelled as such.

## 1. What was checked

1. Scope against the declared purpose: D before the model, C validates the proposal, E records the gate.
2. Protected paths (`tests/`, `cli/`, `pyproject.toml`, `LICENSE`, governance files).
3. Whether the new tests can actually run in CI.
4. Shared-document integrity: `docs/ai-use-log.yaml`, `docs/approvals/**`, ADR numbering.
5. Cross-branch integration risk with `feat/B-budget` and `feat/D-data-quality`.

## 2. Findings

### F1 — Plans were added under `docs/approvals/**` (should be fixed before merge)

Three files appear as **added** in this PR:

```
docs/approvals/2026-11-07-D-FR-004-M2-approved.md
docs/approvals/implementation-plan-FR-004.md
docs/approvals/test-plan-FR-004.md
```

`AGENTS.md` §6 marks `docs/approvals/**` as human-only: agents must not edit it, and `DEVELOPMENT-POLICY.md`
moved working plans to `tasks/plans/<role>/`. These three are D's plan documents, so they belong under
`tasks/plans/D/`. Leaving them in `docs/approvals/` presents agent-written plans as approval records, which
is exactly what the repository's own rules forbid.

Recommendation: move them to `tasks/plans/D/` in this PR, or drop them from the diff.

### F2 — ADR number collision with the B branch (should be fixed before merge)

This PR adds `docs/architecture/adr/002-simulation-safety.md`. At the time of review the B branch also
added an ADR numbered 002, so two ADRs with the same number would have coexisted after both merged.
Different filenames, so git would not conflict, which made it easy to miss.

Resolution: the B branch renumbered its own ADR to `005-budget-at-the-model-client-boundary.md`, so the
collision is gone without touching this PR. C's `002` stays as written.

### F3 — `AI-USE-0003` is duplicated across branches (should be fixed before merge)

`docs/ai-use-log.yaml` on this branch contains:

```
AI-USE-0001, AI-USE-0002, AI-USE-0003, AI-USE-C-0001, AI-USE-C-0002,
AI-USE-E-20261114, AI-USE-CDE-20261118
```

The `AI-USE-0003` in this list is D's entry. At the time of review the B branch also added an entry with
that number, so after both merged two entries would have shared one id, and a reader could not tell which
run produced which record. The renaming this PR already did for C (`AI-USE-C-0001`, with a note explaining that no
historical entry was modified) is the right pattern.

Resolution: the B branch renamed its entry to `AI-USE-B-0001`. This PR does not need to change; D's
`AI-USE-0003` stays as it is.

### F4 — The new offline tests are not executed by any workflow (non-blocking, but the claim needs a caveat)

Five test files are added under `test/offline/`:

```
test/offline/test_audit.py
test/offline/test_cde_graph_flow.py
test/offline/test_cde_integration.py
test/offline/test_data_quality.py
test/offline/test_safety_simulation.py
```

`pyproject.toml` sets `testpaths = ["tests"]`, so `ci.yml` (`pytest -q`) never collects them.
`course-bootstrap.yml` runs exactly one file, `test/offline/test_course_scaffold.py`. Therefore the green
checks on this PR do **not** cover these five files, and the "1596 passed / 33 integration tests" figures in
the description are local claims, not CI evidence.

Recommendation: either add a workflow step (`pytest -o testpaths=test/offline test/offline`) or state in the
PR description that the offline suite is verified locally only. The second option costs nothing and keeps the
claim honest.

### F5 — `cli/main.py` is a protected baseline file (non-blocking, scope must be recorded)

The diff shows `cli/main.py` modified (+96 / −1) to add the `--course-inputs` entry point. `AGENTS.md` §6
treats `cli/**` as protected, with narrow integration edits allowed when the scope and the interface
contract are explicit. The PR description does declare the CLI entry, so this is acceptable if the review
memo records the exact scope. Flagging it so it is a recorded decision rather than an unnoticed edit.

## 3. What looks right

- `tests/` is untouched, `pyproject.toml` and `LICENSE` are untouched.
- The `trading_graph.py` change is additive: `propagate` gains an optional `course_request`, and the
  description states that `None` keeps the original behaviour. That is the right shape for an opt-in path.
- The historical `ai-use-log` entries are preserved: the new entries append after `AI-USE-0002`, and the
  C entry carries a note explaining its renumbering.
- Each of C, D and E ships tests with negative cases, not only happy paths.

## 4. Cross-module note (not a defect in this PR)

The pipeline takes `invoke_ai: Callable[[str], Mapping[str, Any]]` and never constructs a budget ledger, so
the B module is inactive in the course path. That is consistent with B's scope (the ledger is injected at the
model-client boundary), but integration should pass one ledger through the pipeline so a course run is
metered as a whole. Recorded as a follow-up, not a blocker.

## 5. Verdict

**CHANGES REQUIRED** for F1 only. F2 and F3 are resolved on the B side (ADR renumbered to 005, AI-use entry
renamed to AI-USE-B-0001). F4 and F5 need a sentence in the description or the memo, not code changes.

Once F1–F3 are addressed, the scope, the tests and the protected paths are acceptable to this reviewer.

## 6. Limits of this review

- Nothing was executed locally. All behavioural claims come from the diff and from CI metadata.
- The 71k added lines are mostly transcripts (`role-E`, `role-CDE`, `role-C`, D's session), which were
  sampled but not read line by line.
- Semantic quality of the safety rules was not assessed; that is C's own verification concern.

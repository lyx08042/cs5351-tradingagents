# FR-003 安全 ADR 草稿｜确定性模拟提案门（C）

> **状态：DRAFT / POINTER。** 正式 ADR 已移至 `docs/architecture/adr/002-simulation-safety.md`（**PROPOSED**）。
> 本文仅保留为 C 计划目录的入口，**不再重复**正式 ADR 内容；**不是**人工批准，也不改变 ADR-002 的 `PROPOSED` 状态。
> **草稿日期：** 2026-11-07；**正式 ADR 日期：** 2026-11-11。
> **关联：** `FR-003`、`INV-003`、`SEC-001`、`NFR-003`；`architecture-blueprint.md`；`docs/architecture/adr/001-course-extension.md`、`002-simulation-safety.md`。
> **课程差异：** 按 `DEVELOPMENT-POLICY.md`（ACTIVE, owner-selected, 2026-11-07）推进；课程 **G-1/D9 未满足**；**非教师 waiver、非伪造批准**。

## 1. 正式路径

- 正式 ADR：`docs/architecture/adr/002-simulation-safety.md`。
- 本文件：C 计划目录的索引/草稿入口；保留历史日期与关联信息，避免重复维护。
- 可信输入、防伪造规则、当前规则范围、集成待确认点、验证结果与批准记录均在正式 ADR 中。
- **M2：** 独立模块已完成并准备上传；**M3** 正常入口集成与 **M4** 非作者评审待办；实际上传状态以 GitHub `feat/C-safety` 分支为准，本文不声称已推送。
- **验证（2026-11-11，Codex 独立运行）：** 76 个课程离线用例通过（C 56 + 脚手架 20），`check_course` OK，`ruff check .` 通过；上游回归 1407 passed, 6 skipped, 1 deselected, 24 warnings, 100 subtests passed in 41.30s。
- 状态不变：**PROPOSED**；非作者评审（M4）尚未发生，不得声称已批准。

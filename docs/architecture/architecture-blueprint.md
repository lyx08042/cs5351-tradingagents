# 架构蓝图（指针）

> **状态：PROPOSED，指针文件**。

**规范源（canonical）**：仓库根 `architecture-blueprint.md`。

本文件**不是**第二份架构说明；它只指向根文件，以避免两份内容漂移。若根文件内容发生变化，本指针无需同步。

## 课程路径差异说明

- 当前规范源位于仓库根：`/architecture-blueprint.md`。
- 若课程要求架构文档位于 `docs/architecture/architecture-blueprint.md`，需要由**人类成员**在确认教师要求后执行迁移，并将根文件替换为指针（这与本文件当前方向相反）。
- 本仓库**不声称**根布局已被教师接受；迁移与否以教师答复为准。
- 在迁移完成前，`docs/architecture/` 下只存放不变量、trace 矩阵、ADR、权限模型等**附属**架构文档，不复制蓝图正文。

相关文件：

- 根蓝图：`architecture-blueprint.md`
- 不变量：`docs/architecture/invariants.md`
- trace 矩阵：`docs/architecture/trace-matrix.md`
- ADR：`docs/architecture/adr/001-course-extension.md`

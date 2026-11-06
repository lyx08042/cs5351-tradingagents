# HUMAN-ONLY PLACEHOLDER — 未获人工批准的占位文件

> **⚠️ 重要声明（请务必先读）**
>
> 1. 本文件由**编码代理（AI）生成**，属于**初始化脚手架占位**（bootstrap placeholder）。
> 2. 本文件**不是**人工撰写、**不是**人工批准的政策，**不具有**任何政策效力。
> 3. 引导完成后，**任何编码代理都不得再编辑本文件**。
> 4. 真正的规则草案位于 [`docs/code-governance/human-rules-draft.md`](../docs/code-governance/human-rules-draft.md)，供团队成员人工审阅。

---

## 给团队人类成员（Team Human）的指示

本文件（`.opencode/rules.md`）是 OpenCode 通过 `opencode.json` 的 `instructions` 加载的规则入口。**它的内容必须由人类成员撰写并批准**，而不是由代理自动填写。

请人类成员完成以下步骤：

1. **审阅草案**：阅读 `docs/code-governance/human-rules-draft.md`。
2. **修改与定稿**：根据课程要求与团队共识修改。
3. **人工转移**：由一名人类成员将定稿内容复制到本文件（替换本占位内容）。
4. **记录批准**：在 PR 中记录作者、批准人、日期、commit（不得虚构）。
5. **冻结**：批准后，代理不得再修改本文件（见 `opencode.json` 中 `.opencode/rules.md` 的 DENY 规则）。

## 为什么需要区分

| 项 | 性质 |
|---|---|
| 本文件当前内容 | AI 生成的**未批准占位** |
| `docs/code-governance/human-rules-draft.md` | 供人工审阅的**草案** |
| 获批后的 `.opencode/rules.md` | 人工撰写并批准的**正式政策** |

- `.opencode/permissions.jsonc` 是**课程制品**，OpenCode **不会**自动加载；它不提供可执行的运行时角色隔离。
- 本文件与 `.agent/rules.md` 一同作为 `instructions` 被加载，但 `.agent/rules.md` 同样是 AI 生成的脚手架契约，需人类审阅确认。

## 代理须知

- 读到本文件时，应理解：**当前没有人工批准的政策**；你只能遵循 `AGENTS.md`、`Prompt.md` 与 `docs/code-governance/*` 的显式约束。
- 你**不得**把本文件当作已批准政策，也**不得**声称它已被批准。
- 你**不得**编辑本文件。

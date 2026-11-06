# 交接模板（Handoff）

> 模板，不含历史记录。每次交接覆盖**七类信息**（与 `tasks/README.md` 第 4 节一致）。
> 实际文件去向写在每类末尾的“→ 存放位置”。

```markdown
## Handoff: <作者角色> → <评审角色>

### 1) 需求 + fits
- 需求 ID：<FR-00x / INV-00x / NFR-00x>
- statement：<来自 docs/req/requirements.yaml>
- fit：metric=<...>, threshold=<number|string>, verification=<...>
  → 存放位置：docs/req/requirements.yaml（由该需求 owner 维护）

### 2) 设计 / 接口 / ADR / INV
- 接口与契约：<schema / 函数签名>
- ADR：<docs/architecture/adr/... 或 N/A>
- 不变量与失效行为：<INV-00x，fail-closed/abstain/review>
  → 存放位置：docs/architecture/（ADR、invariants、trace-matrix）

### 3) 代码 + 测试 + PR + 实现前批准链接
- 变更文件：<tradingagents/course/... / test/offline/...>
- 正向/负向测试：<...>
- PR：#<n>
- 实现前批准：测试计划 <docs/approvals/...>、实现计划 <docs/approvals/...>
  → 存放位置：代码 PR；批准记录在 docs/approvals/（人工写入）

### 4) 实际评估 / 配置 / 结果
- 固定评估集：docs/evaluation/cases.yaml@<commit>
- 模型/配置：<model / config>
- 结果：<pass|fail|inconclusive|pending，如实>
  → 存放位置：docs/architecture/evaluation-logbook.md、docs/architecture/evaluation-table.md

### 5) 完整原始会话 + 独立干预注释
- raw：transcripts/<studentid-name>/raw.md（完整、不可变、只读）
- annotations：transcripts/<studentid-name>/annotations.md（单独文件，追加）
  → 存放位置：transcripts/（不得包含凭证/个人信息）

### 6) AI 使用 / 评审 / bug / 债务 / 变更记录
- AI use：docs/ai-use-log.yaml（追加）
- review：docs/review-memo.md
- bug：docs/bug-diary.md（仅记录真实观察）
- debt：docs/debt-register.md
  → 存放位置：docs/

### 7) 报告贡献 + 个人反思 + 可验证贡献证据 + 演示材料
- 报告章节：Report.md <节>
- 个人反思：300–500 WORDS（英文词数，见 Report.md；中文计数需教师澄清）
- 姓名/学号与贡献证据：<PR/commit/评审/测试>
- 演示材料：<demo 脚本/截图/视频时间戳>
  → 存放位置：Report.md、templates/member-reflection.md、transcripts/、演示附件
```

> 不得把 `pending` 写成 `done`；不得编造测试输出、批准或身份。

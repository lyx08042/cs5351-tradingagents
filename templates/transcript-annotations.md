# Transcript 注释模板

> 模板。原始 transcript 必须**完整、不可变、追加式**保存；注释**单独**记录，不修改原始文件。

## 1. 文件约定

- 原始记录：`transcripts/<studentid-name>/raw.md`（或导出文件），**只读**。
- 注释：`transcripts/<studentid-name>/annotations.md`，**单独**文件。

## 2. 注释格式（追加）

```markdown
## Annotation <n>

- 时间：<raw 中的时间戳>
- 位置：<raw 文件行号/消息序号>
- 类型：<prompt|decision|review|test|correction|stop>
- 内容：<当时为什么这样做>
- 关联：<REQ-ID / PR / commit>
```

## 3. 规则

- 不得编辑 raw 原文；不得删减。
- 不得包含 API key、秘密、个人信息。
- 不得伪造记录或时间。

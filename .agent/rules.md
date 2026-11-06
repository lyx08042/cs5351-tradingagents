# 代理规则（AI 生成的脚手架契约）

> 状态：**AI 生成的脚手架提示（2026-11-06）**。本文件是 `.agent/rules.md`，作为 `opencode.json` 的 `instructions` 之一被加载。
> 本文件不是人工批准的政策；正式政策需由团队人类成员撰写并批准，见 `docs/code-governance/human-rules-draft.md` 与 `.opencode/rules.md`。

## 1. 契约

- 只做被明确请求的工作；不擅自扩展范围。
- 不伪造任何事实、批准、结果、身份或记录。
- 不确定时停止并请求人工确认。

## 2. 依赖

- 不新增运行时依赖，除非人工批准并记录 ADR。
- 课程脚手架依赖固定为 `requirements-course.txt`（`jsonschema>=4.23,<5`、`PyYAML>=6,<7`）。
- 不修改 `pyproject.toml` 的依赖与构建配置。

## 3. 测试

- 不删除、跳过、放宽既有测试；不修改 `tests/`。
- 每个新功能必须有至少一个负向测试。
- 测试必须由非作者评审。

## 4. 抽象

- 叶子模块不得循环导入；跨模块协作通过共享契约或薄编排器。
- 契约变更需 ADR + 人工批准。

## 5. 批准

- 实现前必须有测试计划批准与实现计划批准（`docs/approvals/`）。
- 安全相关变更需 ADR + 人工批准。
- 提示词/模型变更先固定评估集并先评测。

## 6. 上下文新鲜度

- 依据**一个 sprint 内**的当前仓库文档作答；不依赖过期对话记忆。
- 变更前重读相关 `docs/`、`tasks/` 与 `architecture-blueprint.md`。
- 发现文档不一致时记录到 `docs/debt-register.md` 或 `docs/bug-diary.md` 并停止。

## 7. 禁止

- 读取 `.env*`、auth、git 元数据、隐藏 home 文件、外部目录。
- 在线 API 调用、提交、推送。
- 把上游 v0.7.1 既有能力说成新功能。

# 代理规则（AI 生成的脚手架契约）

> 状态：**AI 生成的脚手架提示**。本文件作为 `opencode.json` 的 `instructions` 之一被加载。
> **活跃工作流以 `DEVELOPMENT-POLICY.md`（ACTIVE, 2026-11-07）为准**；本文与其冲突时以它为准。本文件不是人工批准的政策；真正草案见 `docs/code-governance/human-rules-draft.md` 与 `.opencode/rules.md`（人类专属，不编辑）。

## 1. 契约

- 只做被明确请求的工作；不擅自扩展范围。
- 不伪造任何事实、批准、结果、身份或记录。
- 只对**真实的**范围外 / 不可逆 / 凭证问题请求用户输入；不因 `PENDING`、缺失计划批准或 `proposed` 状态停下。

## 2. 依赖与冻结

- 不新增运行时依赖，除非有记录（ADR/设计记录）。
- 课程脚手架依赖固定为 `requirements-course.txt`（`jsonschema>=4.23,<5`、`PyYAML>=6,<7`）。
- 不修改 `pyproject.toml` 的依赖与构建配置。

## 3. 测试

- 不删除、跳过、放宽既有测试；不修改 `tests/`。
- 每个新功能必须有至少一个负向测试。
- 测试必须由非作者评审。

## 4. 抽象

- 叶子模块不得循环导入；跨模块协作通过共享契约或薄编排器。
- 契约/安全/接口变更：创建 ADR/设计记录，**无实现前批准人**。

## 5. 工作流（见 `DEVELOPMENT-POLICY.md`）

- 先 `git fetch origin` + `git merge origin/main` 到 feature 分支。
- 写计划 + 测试设计（工作文档，非批准门）后**继续实现**，不等待人工测试/实现/ADR 预批准；`approval_refs` 不需要。
- 最终 PR + 非作者评审 + CI + 合并授权保留；**不自动合并到 `main`**。

## 6. 版本控制

- **允许**在 feature 分支上的本地 commit/push，前提是用户任务与授权允许。
- **绝不**自动合并到 `main`。
- 不提交明文凭证或密钥。

## 7. 上下文新鲜度

- 依据**当前**仓库文档作答；不依赖过期对话记忆。
- 变更前重读 `DEVELOPMENT-POLICY.md`、`docs/`、`tasks/`。
- 发现文档不一致时记录到 `docs/debt-register.md` 或 `docs/bug-diary.md`。

## 8. 禁止

- 读取 `.env*`、auth、git 元数据、隐藏 home 文件、外部目录。
- 未授权的外部 spend、在线 API 调用或凭证访问。
- 把上游 v0.7.1 既有能力说成新功能。

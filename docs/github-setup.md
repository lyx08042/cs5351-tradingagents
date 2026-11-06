# GitHub 设置指南（Owner 人工操作）

> 状态：**说明**。本地文件**不会**修改 GitHub 设置；以下需仓库 owner 在网页端人工完成。
> 团队仓库：<https://github.com/lyx08042/cs5351-tradingagents>（public）

## 1. 启用 Actions

1. 进入仓库 **Settings → Actions → General**。
2. 选择 “Allow all actions and reusable workflows”（或最小必要）。
3. 确认 `course-bootstrap.yml` 与既有 `ci.yml` 可运行。

> 注意：本仓库源自上游，可能继承了 `release-assets.yml` 等发布工作流。**不要**在课程中自动启用发布/部署；如需禁用，由 owner 人工处理。

## 2. 保护 main

1. **Settings → Branches → Add branch protection rule**，匹配 `main`。
2. 勾选：
   - Require a pull request before merging
   - Require approvals：**至少 1**
   - Require status checks to pass（选择 CI 与 course-bootstrap 的相关 check）
   - Do not allow bypassing the above settings
3. 保存。

## 3. 身份与 CODEOWNERS

- 由 owner 填写真实 GitHub 用户名（**不得**使用无效占位）。
- `CODEOWNERS` 为**可选**；若添加，需真实有效账号，否则会被 GitHub 忽略/报错。

## 4. PR 模板

- `.github/PULL_REQUEST_TEMPLATE.md` 已包含 gate 状态字段。
- 该路径属于 `.github/**`，变更需**人工评审**。

## 5. 工作流边界

| 工作流 | 作用 | 是否课程 gate |
|---|---|---|
| `ci.yml` | 上游测试/风格/冒烟（既有） | 否（基线回归） |
| `release-assets.yml` | 上游发布（继承） | 否；**不要自动启用发布** |
| `course-bootstrap.yml` | 课程脚手架 schema/trace | **仅 G-3（schema/trace）**，非全部六道阻断 gate |

## 6. 不得声称

- 不得声称“已自动完成课程 gate”。
- 不得声称“测试批准/安全 ADR 已自动化”（PENDING）。

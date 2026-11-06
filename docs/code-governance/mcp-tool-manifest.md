# MCP 工具清单（PROPOSED）

> 状态：**PROPOSED**。默认**无 MCP 服务器**；本文件说明本地工具 vs 应用运行时工具的区别。

## 1. 术语

- **本地工具（local tooling）**：开发者/CI 用于校验仓库的工具（pytest、ruff、`scripts/check_course.py`、git）。
- **应用运行时工具（app runtime tools）**：TradingAgents 运行时智能体可调用的工具（数据 vendor、指标、检索等）。
- **MCP（Model Context Protocol）服务器**：可被编码代理接入的外部工具服务。

## 2. 默认配置

| 项 | 值 | 说明 |
|---|---|---|
| MCP 服务器数量 | **0** | 无默认 MCP；不得在未批准情况下引入 |
| 网络访问（编码代理） | 默认拒绝 | 见 `opencode.json` |
| 秘密访问 | 禁止 | `.env*`/auth 禁止读取 |

## 3. 引入 MCP 的流程（planned）

1. 提交 ADR，说明用途、权限、数据边界、失败模式。
2. 人工批准。
3. 在 `opencode.json` 中显式配置，最小权限（deny 默认）。
4. 记录到本清单。

## 4. 运行时工具边界

- 运行时智能体的数据工具由上游拥有，课程扩展**不得**改变其公共行为（BASE-001）。
- 工具失败必须 fail-closed/unavailable，不得伪造数据（与 INV-004 一致）。

## 5. 现状

- 无 MCP、无外部工具接入。
- 本清单为设计基线；实际引入需人工批准。

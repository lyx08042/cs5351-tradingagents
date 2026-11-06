# Pull Request

> 如实填写。**不得**勾选未真实发生的项；不得伪造批准、评审或测试结果。

## 关联需求

- Req IDs：<FR-00x / INV-00x / NFR-00x>
- 类型：<feature | test | docs | governance | safety>

## 批准（实现前必须具备）

- 测试计划：<路径/commit/日期，或 PENDING>
- 实现计划：<路径/commit/日期，或 PENDING>
- ADR（安全变更）：<路径，或 N/A>
- 批准记录位置：`docs/approvals/`

## 变更范围

- 修改文件/目录：<...>
- 明确未改动：`tests/`、`pyproject.toml`、`LICENSE`、既有 `tradingagents/**`、`cli/**`

## 证据

- 测试命令与结果：<...>
- 负向测试：<...>
- 评估（如适用）：<...>

## AI 使用

- `docs/ai-use-log.yaml` 已更新：<yes/no>

## 评审

- 评审人（非作者）：<...>
- 评审备忘：<...>

## Gate 状态（如实，六道阻断 gate 见 verification-constraints.md）

| Gate | 状态 |
|---|---|
| G-1 实现前测试批准 | |
| G-2 每次提交静态检查 + 安全 PR 审查 | |
| G-3 需求 schema | |
| G-4 提示词/模型固定集评估 | |
| G-5 完整既有回归 | |
| G-6 AI 使用记录更新 | |

附加控制（非上述六道）：实现计划批准 / 安全 ADR / 非作者评审 → <如实填写>

## 声明

- [ ] 未伪造批准/结果/评审
- [ ] 未削弱既有测试
- [ ] 未包含秘密
- [ ] 状态如实标注（PROPOSED/未实现/PENDING）

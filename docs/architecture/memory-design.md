# 记忆与上下文设计（PROPOSED）

> 状态：**PROPOSED**。以下均为计划设计，**未实现**、**未验证**。
> 上游 v0.7.1 的 memory log 与 checkpoint 是**既有能力**（见 README.upstream.md），本文件讨论课程扩展如何在**不破坏**它们的前提下增加分层上下文。

## 1. 分层运行时上下文（PROPOSED）

```
identity → constraints → retrieved evidence → conversation → state → task
```

| 层 | 内容 | 来源 | 责任 |
|---|---|---|---|
| identity | ticker、asset_type、trade_date | 确定性解析（上游已有身份解析） | A（消费） |
| constraints | 预算、安全规则版本、权限 | F2/F3 | B、C |
| retrieved evidence | 已绑定证据单元 | F1 | A |
| conversation | 辩论历史 | 上游 LangGraph state | A（约束） |
| state | checkpoint 状态 | 上游 checkpoint | E（留痕） |
| task | 当前子任务 | 编排器 | 共同 |

## 2. 上下文流水线（PROPOSED）

```
dedup → prioritize → budget → compact → assemble
```

- **dedup**：去除重复证据/重复工具输出。
- **prioritize**：按相关性与新近度排序。
- **budget**：在 token 预算内裁剪（与 F2 联动）。
- **compact**：超过阈值时压缩，保留关键证据。
- **assemble**：重新注入（reinjection）关键证据后组装为最终 prompt。

## 3. 计划中的可配置阈值（**非已达成事实**）

| 参数 | 提议值 | 性质 |
|---|---|---|
| `context_token_cap` | **16000 tokens** | 计划中的设计上限 |
| `compaction_threshold` | **12000 tokens** | 计划中的压缩触发阈值 |
| `reinjection` | 压缩后重新注入关键证据 | 计划机制 |

> 这些数值是**设计阈值**，不是测量结果，也不是质量结论。

## 4. 与上游 memory/checkpoint 的关系

- 上游 memory log（`~/.tradingagents/memory/trading_memory.md`）与 checkpoint 继续使用，**不改**其公共行为。
- 本设计的“记忆”指**上下文层**的近程证据/对话管理，不是替代上游的跨运行决策记忆。
- 任何对上游 memory/checkpoint 的修改都需 ADR + 人工批准（涉及 BASE-001/002）。

## 5. 失效与安全

- 证据缺失时不得伪造记忆；标为 `unavailable`（与 F4 一致）。
- 压缩不得删除安全约束或规则版本信息。
- 上下文组装必须可回放（与 F5 联动）。

## 6. 当前状态

- 无代码、无测试、无监控。
- 上述阈值与流水线均待实现与评估。

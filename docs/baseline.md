# 基线（Baseline）

> 状态：**事实台账**。记录上游基线与**一次**实际运行的脱敏证据。
> **单次运行不代表总体质量**；价格未独立审计；只使用脱敏后的数字，不复制大体积生成报告或个人信息。

## 1. 上游基线

| 项 | 值 |
|---|---|
| 上游仓库 | TauricResearch/TradingAgents |
| 版本 | v0.7.1 |
| commit | `9fa1196fffbcfd9de5146d2dd2869df84ab99838` |
| 团队仓库 | <https://github.com/lyx08042/cs5351-tradingagents>（public） |

## 2. 已有模块映射（保留，未修改）

| 路径 | 内容 |
|---|---|
| `tradingagents/` | 包：agents、dataflows、graph、memory、llm_clients、portfolio、backtest、reporting |
| `cli/` | 命令行入口与显示 |
| `tests/` | 上游测试套件（91 个测试文件等） |
| `pyproject.toml` | 构建/依赖/工具配置 |

详见 `src/README.md`。

## 3. 一次运行证据（脱敏）

| 指标 | 值 |
|---|---|
| ticker / 日期 | NVDA / 2026-09-01 |
| 耗时 | 150.61 s |
| LLM 调用次数 | 19 |
| 输入 tokens | 196870 |
| 输出 tokens | 31405 |
| 总 tokens | 228275 |
| cache tokens | 46464 |
| 最大输入 tokens | 26085 |
| 最终信号 | Hold |

### 观察（事实）

- 历史新闻/社交数据**不可用**；FRED **无 key**。
- 虽未提供持仓，最终决策仍出现**条件性 sizing** 表述（见 `docs/bug-diary.md` BUG-001，`needs-review`）。
- 缺失 feed 被计为 **neutral 5 处**（正是 FR-004/INV-004 要解决的问题；见 BUG-002）。
- 成交量条件 **150M vs 298.9M** 的差异**可能**是有意决策，**未证明**为 bug（BUG-003）。

> 未对价格做独立审计；以上为运行记录中的数字。

## 4. 测试基线

| 项 | 值 |
|---|---|
| 离线测试 | **1412 passed, 1 skipped, 1 deselected, 100 subtests** |
| 端到端 | **15 passed**（e2e） |

> 这些是**历史基线**数字，用于 BASE-002 的约束参考；不保证未来运行完全一致。

## 5. 说明

- 单次运行不能说明系统总体质量。
- 不复制大体积生成财务报告或个人信息到公共仓库。

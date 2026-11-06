# 源码布局说明（src/)

> 本文件说明**上游既有模块映射**，帮助课程成员理解现有能力。
> **本目录不是源代码树**；不要在此添加重复源码。真实代码在 `tradingagents/` 与 `cli/`。

## 1. 模块映射

| 模块 | 作用 | 关键文件 |
|---|---|---|
| `tradingagents/agents/` | 分析师、研究员、交易员、风控、经理、状态与 schema | `state.py`、`schemas.py`、`structured.py`、`analysts/`、`researchers/`、`risk_mgmt/`、`managers/`、`trader/` |
| `tradingagents/dataflows/` | 数据 vendor、路由、日期窗口、符号、错误 | `router.py`、`config.py`、`date_window.py`、`vendors/` |
| `tradingagents/graph/` | LangGraph 装配、传播、条件逻辑、checkpoint | `trading_graph.py`、`setup.py`、`propagation.py`、`checkpointer.py` |
| `tradingagents/memory/` | 决策记忆与反思结算 | `log.py`、`reflection.py`、`settlement.py` |
| `tradingagents/llm_clients/` | 多 provider 客户端、能力、模型目录 | `factory.py`、`openai_client.py`、`anthropic_client.py`、`google_client.py`、`capabilities.py` |
| `tradingagents/portfolio.py` | 持仓上下文 | `portfolio.py` |
| `tradingagents/backtest.py` | 网格回测与评分 | `backtest.py` |
| `tradingagents/reporting.py` / `report_html.py` | 报告生成 | — |
| `cli/` | 交互/非交互命令行 | `main.py`、`run.py`、`display.py` |

## 2. 模块映射（`tradingagents` 包根）

- `__init__.py`：版本与公共导入。
- `default_config.py`：`DEFAULT_CONFIG`、`TRADINGAGENTS_*` 环境覆盖。

## 3. 课程扩展（PROPOSED，**当前不存在**）

```
tradingagents/course/{evidence,budget,safety,data_quality,audit}/
```

- 这些目录**尚未创建**；属于蓝图中的计划路径。
- 是否采用该布局**取决于教师答复**；本文件**不声称**布局已被接受。

## 4. 测试映射

见 `test/README.md`。上游测试在 `tests/`，课程脚手架测试在 `test/offline/`。

## 5. 重要声明

- 现有能力（并行分析师、token 配置、辩论/工具上限、重试、schema、checkpoint、memory、报告、测试）均为**上游既有**，**不是**本团队新功能。
- 本目录不复制源码，不引入重复源树。

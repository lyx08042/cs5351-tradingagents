# CDE 输入样例与运行说明

- 状态：WORKING（工作记录；不是人工批准，也不是课程合规声明）
- 关联：`docs/architecture/adr/004-cde-integration.md`、
  `tasks/plans/integration/CDE-integration-plan.md`
- 输入样例：`tasks/plans/integration/evidence/cde-input-sample.json`

## 1. 这个样例是什么

`cde-input-sample.json` 是**调用方提供**的课程模式输入，不是模型生成物，也不是真实行情或券商数据。
其中：

- `observations`：交给 D 的数据充分性观察（五个必需域各一条）；
- `holdings_snapshot`：调用方信任的模拟账户快照；`positions` 必须显式提供（空仓需 `{}` 且
  `flat_declared: true`），缺失 `positions` 不会被补成空仓；
- `instrument` / `analysis_cutoff`：必须与 `propagate(...)` 的标的名和交易日期一致；
- `rule_version`：当前唯一固定版本 `cde-long-only-v1`；
- `audit_path`：E 的 SQLite 审计文件位置（由调用方指定，目录需可写）。样例使用当前目录的
  `cde-course.sqlite`；`:memory:` 等内存数据库会被接入层在模型调用前拒绝，因为关闭连接后
  记录无法作为可验证证据保留。

本样例**不包含**余额授权、真实下单或任何执行意图。真实执行请求（例如
`execution_mode: "live"`）会被 C 拒绝，且不会被编排器静默丢弃。

## 2. 如何进入课程模式

只有显式提供 `--course-inputs`（CLI）或 `course_request=`（程序入口）才进入 CDE 路径；否则
原 CLI / 原图行为不变。

```bash
tradingagents \
  --ticker NVDA \
  --date 2026-11-17 \
  --course-inputs tasks/plans/integration/evidence/cde-input-sample.json \
  --no-save \
  --no-show
```

课程路径使用普通配置中的**实际模型**完成分析；上面的命令不是离线测试，会按当前 provider/model
配置发起真实模型请求。本仓库未做 live API 评估，也不连接真实券商；测试使用脚本模型替身，不代表示例
命令可在无网络/无凭证环境中运行。D 先于模型；模型只返回可选的 `simulation_proposal` 候选；
快照 id 和规则版本由编排器绑定；C 决定是否接受；E 先写入审计再允许发布。

程序入口：

```python
from tradingagents.course.pipeline import CourseRequest
from tradingagents.graph.trading_graph import TradingAgentsGraph

request = CourseRequest.from_mapping(payload)
graph = TradingAgentsGraph(selected_analysts, config=config)
final_state, signal = graph.propagate(
    request.instrument,
    request.analysis_cutoff,
    course_request=request,
)
```

`final_state["course_result"]` 是 D/C/E 结果的 JSON 形态，`signal` 由 C 的结果导出：
accepted buy → `Buy`，accepted sell → `Sell`，合法 Hold → `Hold`，其余 → `REVIEW`。

## 3. 明确限制

- 课程模式**不支持** checkpoint 恢复：`checkpoint_enabled` 与 `course_request` 同时存在会
  fail-closed 报错，避免旧状态缺少课程上下文。
- `audit_path` 必须是持久文件；`:memory:` / SQLite memory URI 在模型前被拒绝。
- 没有真实 API 评估、没有真实券商执行；所有交易动作都是模拟提案。
- 审计失败或重复 run 冲突时不发布成功结果。
- 本文件与样例不声称任何测试通过、人工批准或课程合规。

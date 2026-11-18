# CDE 接入 Handoff（离线验证完成，待评审）

- 状态：**接入代码和离线验证完成，待非作者评审及 CI/合并授权**
- 日期：2026-11-18
- 冻结：业务代码与测试自 2026-11-18 最终验证后冻结，不再改动
- 范围：D（数据充分性）→ 原 AI 图 → C（确定性安全）→ E（可验证审计）的共享接入
- 关联：`docs/architecture/adr/004-cde-integration.md`、
  `tasks/plans/integration/CDE-integration-plan.md`、`docs/ai-use-log.yaml`
- 证据：`tasks/plans/integration/evidence/final-validation-2026-11-18.txt`
- 说明：本文件不是人工批准、不是课程合规声明，也不虚构任何未实际发生的测试或评审。

## 1. 真实已知结果

| 项目 | 已知结果 |
| --- | --- |
| 组合回归（`tests` + `test/offline`） | **1596 passed, 6 skipped, 1 deselected, 24 warnings, 100 subtests passed in 44.19s**；`suite_exit=0` |
| 上游回归 | **1407 passed**（组合回归中的上游部分） |
| 课程离线 | **189 passed** = 原 CDE 156 + 新增 33；33 中含 3 个真实图端到端和最后的内存审计回归 |
| 真实图端到端 | 3 passed：合法发布、超现金 `REVIEW`、CLI `--course-inputs` 真实入口 |
| 静态/课程检查 | `ruff check .` 通过（`ruff_exit=0`）；`check_course` OK（`schema_exit=0`） |
| 运行时真实 API | 未评估；测试使用脚本模型与离线 vendor 替身 |

历史故障记录：首次新增集为 17/18；随后实际复现并修复了三类接入绕过（ticker/日期不一致、
缺失 `positions` 被补空仓、模型回调篡改快照），并修复金额字符串与真实执行标志问题。
最后修复的 `:memory:` 审计路径缺口已加入回归并包含在最终 189 中；全部结果见上述证据文件。

## 2. 当前入口与样例

CLI：

```bash
tradingagents \
  --ticker NVDA \
  --date 2026-11-17 \
  --course-inputs tasks/plans/integration/evidence/cde-input-sample.json \
  --no-save \
  --no-show
```

- 只有显式 `--course-inputs` 才进入课程路径。
- CLI 使用当前配置的实际模型；该命令不是离线测试，可能发起真实模型请求。测试中的脚本模型
  不代表样例命令无需网络/凭证。
- `--ticker`/`--date` 若提供，必须与输入文件一致。

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

- 返回的 `signal` 由 C 的结果导出：accepted buy → `Buy`，accepted sell → `Sell`，
  合法 Hold → `Hold`，其余 → `REVIEW`。
- `final_state["course_result"]` 是 D/C/E 的 JSON 形态。

样例：`tasks/plans/integration/evidence/cde-input-sample.json`
（`audit_path` 为当前目录的 `cde-course.sqlite`）。

## 3. 失败语义与固定版本

- 固定规则版本：`cde-long-only-v1`；其他版本由 C 拒绝，回放置 `version_unknown`/review。
- 固定 gate：`cde.pipeline.final`；每 run 一条确定性记录 `cde:<run_id>`。
- D 在模型前执行：`review` → `rejection`，`abstain` → `abstain`，模型 0 调用。
- C 是唯一发布门：只有 `accepted and not is_noop` 才发布模拟提案；Hold 为合法无操作。
- 缺 `positions` 不补空仓；必须显式 `positions={}` 且 `flat_declared=true` 才能表示空仓。
- 模型候选金额为十进制字符串；`execution_mode=live`/`real_execution=true` 等真实执行意图
  不会被静默丢弃，由 C 拒绝。
- `timestamp` 在模型前用 E 的 `validate_append_inputs` 预检。
- `audit_path` 必须是持久文件；`:memory:`/SQLite memory URI 在模型前抛
  `CourseRequestError`。
- 审计先写后发布；写失败抛错且不发布；重复 run 结果相同则幂等，不同则冲突。
- 课程模式明确不支持 checkpoint 恢复，直接 fail-closed。

## 4. 待办

1. 非作者评审：CDE 接入代码、测试与文档均待组员评审。
2. CI 结果收集与合并授权；不得自动合并到 `main`。
3. `transcripts/role-CDE/raw.json` 尚未在本分支出现；随后由 Codex 原样导出，不代填身份。
4. 真实学生身份、投入小时/story points 待本人补充；原始 transcript 待本人确认。
5. 课程 G-1/D9 仍未满足；本仓库不声称课程合规。

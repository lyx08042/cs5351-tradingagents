# Role-CDE 会话注释（真实记录）

- 日期：2026-11-18
- 工具：OpenCode 1.19.5
- 模型：`opencode/deepseek-v4.1-flash-free`
- Session：`ses_e1306faacffebtHTt3iEtHc5kh`
- 调度：Codex 编排 OpenCode；测试命令由 Codex 实际执行
- 状态：接入代码和离线验证完成，待非作者评审及 CI/合并授权；业务代码与测试已冻结
- 身份：待本人填写；本文件不代填姓名、学号或人工评审

## 1. 范围

本会话负责已合并 C（FR-003 确定性模拟安全）、D（数据充分性）与 E（可验证审计）叶子模块的
**共享接入**：`tradingagents/course/pipeline.py`、`TradingAgentsGraph.propagate` 可选
`course_request`、PM 可选 `SimulationCandidate`、CLI `--course-inputs`、离线测试与接入文档。
叶子模块本身仍归各自作者；本会话不把 D/E 原代码算作 C 的成果。

## 2. 真实过程

1. 解决 C/D 与 C/D/E 合并冲突：`docs/ai-use-log.yaml`、`tradingagents/course/__init__.py`。
   历史 entries 各保留一次，未改写历史批准或身份。
2. 先写接入测试，再实现 pipeline/graph/CLI。首次新增集成测试结果为 **17/18 passed**。
3. 实际复现并修复三类接入绕过：
   - `propagate` 未核对 `course_request.instrument`/`analysis_cutoff`，AI 仍分析另一标的；
   - 缺失 `holdings_snapshot.positions` 被补成空仓，`flat_declared=true` 时可发布；
   - 模型回调可修改调用方 `CourseRequest.holdings_snapshot`，影响快照判定。
4. 同轮修复金额契约与执行意图：`SimulationCandidate.units/price` 改为十进制字符串；
   `execution_mode=live`/`real_execution=true` 不再被候选规范化吞掉，由 C 拒绝；新增候选
   schema 的 `extra="forbid"`。
5. 模型前校验审计 timestamp；固定规则目录为只读映射与 `cde-long-only-v1`。
6. 新增 3 个真实 LangGraph 端到端测试由 Codex 实际运行通过（合法发布、超现金 `REVIEW`、
   CLI `--course-inputs` 真实入口）。
7. 最终复现并修复 `audit_path=":memory:"`：原实现可发布，但 `close()` 后记录消失。现已加入
   模型前拒绝回归，接入层拒绝内存 SQLite 路径，未修改 E 叶子。
8. 最终验证（Codex 实际执行，证据
   `tasks/plans/integration/evidence/final-validation-2026-11-18.txt`）：
   组合回归 **1596 passed, 6 skipped, 1 deselected, 24 warnings, 100 subtests passed
   in 44.19s**；其中上游 **1407**、课程离线 **189**（原 CDE 156 + 新增 33，33 含 3 个真实图
   测试和内存审计回归）；`suite_exit=0`、`ruff_exit=0`、`schema_exit=0`。

## 3. 证据与限制

- 最终证据：`tasks/plans/integration/evidence/final-validation-2026-11-18.txt`。
- 上游回归已知结果：1407 passed；课程离线 189 passed；ruff 与课程 schema/check_course 通过。
- 没有运行时真实 API 评估；测试使用脚本模型与离线 vendor 替身，并显式禁止网络。
- `transcripts/role-CDE/raw.json` 当前尚未出现在本分支；随后由 Codex 原样导出，不代填身份。
- 非作者评审、CI 与合并批准待完成；本文件不声称这些已发生。
- 课程 G-1/D9 仍未满足；不得据此声称课程合规。

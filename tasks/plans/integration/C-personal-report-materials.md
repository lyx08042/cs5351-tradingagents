# C 个人报告材料（供组长汇总）

- 状态：离线验证完成，待非作者评审及 CI/合并授权
- 姓名、学号、投入量、个人经历：待本人核对后填写；本文件不代填
- 角色：C（F3 确定性模拟安全）
- 说明：代码与测试由 Codex 调度的 OpenCode 完成，Codex 独立运行验证命令；不虚构本人
  亲自发现、批准或评审。

## 1. 个人贡献记录

| 成员 | 学号 | 角色 | 负责需求 | 投入量（待本人确认） | 可验证证据 |
| --- | --- | --- | --- | --- | --- |
| C（姓名待本人填写） | 待本人填写 | C / F3 确定性模拟安全 | FR-003 / INV-003 / SEC-001 / NFR-003 | 待本人填写（小时或 story points） | C `a78d88c`；CDE 分支 https://github.com/lyx08042/cs5351-tradingagents/tree/feat/CDE-integration（正在准备上传/待评审） |

### 可验证证据清单

- C 叶子模块提交：`a78d88c`
- CDE 协调接入分支：https://github.com/lyx08042/cs5351-tradingagents/tree/feat/CDE-integration
  （正在准备上传/待评审）
- 源码：
  - `tradingagents/course/safety/`（C 叶子）
  - `tradingagents/course/pipeline.py`（共享接入）
  - `tradingagents/graph/trading_graph.py`（课程入口）
  - `cli/main.py`（`--course-inputs`）
- 测试：
  - `test/offline/test_safety_simulation.py`（C 独立 56 用例）
  - `test/offline/test_cde_integration.py`（CDE 接入回归）
  - `test/offline/test_cde_graph_flow.py`（真实图端到端）
- ADR：
  - `docs/architecture/adr/002-simulation-safety.md`
  - `docs/architecture/adr/004-cde-integration.md`
  - `tasks/plans/C/FR-003-safety-adr-draft.md`
- 计划：
  - `tasks/plans/C/FR-003-implementation-plan.md`
  - `tasks/plans/C/FR-003-test-plan.md`
  - `tasks/plans/integration/CDE-integration-plan.md`
- 原始会话/验证证据：
  - `transcripts/role-C/raw.json`
  - `transcripts/role-CDE/annotations.md`
  - `transcripts/role-CDE/raw.json`（尚未出现，随后由 Codex 原样导出）
  - `tasks/plans/integration/evidence/final-validation-2026-11-18.txt`

## 2. Report 实现与验证

### 2.1 C 独立实现

C 叶子模块已在 `tradingagents/course/safety/` 独立完成：`SimulationProposal`、
`HoldingsSnapshot`、`RuleSet`、`SafetyContext`、`SafetyVerdict`、`ReasonCode` 与
`validate_proposal`。独立测试为 **56 个离线用例**，覆盖正例、负例、确定性重放、规则版本、
持仓缺失、标的绑定、金额精度与真实执行意图拒绝。

### 2.2 共享 CDE 接入

当前共享接入已完成并接入 `--course-inputs`（CLI）或 `course_request`（`propagate`），
调用方需显式提供 D 的观察与可信账户快照；模型只返回可选的 `simulation_proposal`，C 决定是否
发布，E 先写审计再允许发布。接入新增 **33 个用例**，其中含 3 个真实 LangGraph 端到端测试
（合法发布、超现金 `REVIEW`、CLI 入口）和最后的内存审计拒绝回归。

最终完整验证为 **1596 passed**：上游 **1407** + 课程离线 **189**（原 CDE 156 + 新增 33）；
同次 `ruff` 与 `check_course` 通过。原 D 的 20 个、E 的 60 个、scaffold 的 20 个用例是
D/E/脚手架作者的成果，**不计入 C 个人贡献**；C 的 56 个独立用例与共享 CDE 的 33 个用例分开
统计。证据：`tasks/plans/integration/evidence/final-validation-2026-11-18.txt`。

### 2.3 实际复现并修复的缺陷

- **Decimal 精度**：买入成本使用显式 `decimal.Context`，不接受调用方上下文污染。
- **非法 `rule_set`**：返回稳定的 `INVALID_RULE_SET` 拒绝原因，而不是异常逃逸。
- **标的绑定**：模型前核对 `instrument` / `analysis_cutoff`，不一致 fail-closed。
- **缺失持仓**：不把缺失 `positions` 补成空仓；空仓需显式 `positions={}` 且
  `flat_declared=true`。
- **快照固定**：模型前深拷贝并重新校验请求，回调不能篡改调用方快照。
- **金额与执行意图**：金额为十进制字符串；真实执行额外字段保留并由 C 拒绝。
- **审计持久性**：`:memory:` 审计路径在模型前拒绝，避免发布后记录消失。

这些缺陷由 Codex/OpenCode 的复现与测试记录支持，不写成 C 成员个人独立发现。

### 2.4 限制与待办

- 课程模式不支持 checkpoint 恢复，检测到即 fail-closed。
- 调用方必须提供 D 观察与可信账户快照；不提供则无法通过 D。
- 未进行 live 模型或券商评估；测试使用脚本模型与离线替身。
- 非作者评审、CI 收集与合并授权待完成；不得自动合并到 `main`。
- 课程 G-1/D9 仍未满足；不得声称课程合规。

## 3. English personal reflection draft (330–420 words)

姓名/学号/个人经历待本人核对后使用；以下只基于真实材料。

My assigned work was the C role: the deterministic simulation-safety gate for the course
extension. The C leaf checks a proposed simulated trade against a trusted account snapshot
and a fixed rule set, returns stable rejection reasons, and produces the same verdict on
replay. The shared integration also fell within my assigned scope. It connects the
data-sufficiency check, the original multi-agent graph, the safety gate, and the audit
record, while leaving the D and E modules with their own authors.

The implementation and verification were performed in OpenCode sessions orchestrated by
Codex, and Codex ran the combined validation independently; the counts below come from that
record. The C module has 56 independent offline cases. The shared CDE work added 33 cases, including three real-graph end-to-end
tests and a regression for the in-memory audit gap. The final combined run reported 1596
passing tests: 1407 upstream and 189 course offline. The course count is the original CDE
156 plus the 33 new cases; the D, E, and scaffold tests are not my personal contribution.

What I learned is that a correct leaf is not enough. Integration is where a safe function
can be bypassed: the caller can pass a different ticker, omit positions so an empty account
is assumed, mutate the request while the model runs, or point the audit at a database that
disappears when the connection closes. The fixes were concrete: validate the instrument and
cutoff before the model, treat missing positions as unresolved rather than flat, freeze the
request snapshot, keep decimal amounts as strings, preserve explicit real-execution flags
for rejection, and refuse an in-memory audit path. These are boundary lessons more than
algorithm lessons.

The current entry is `--course-inputs` on the CLI or `course_request` on `propagate`. The
caller must provide the D observations and a trusted account snapshot. Checkpoint recovery
is explicitly unsupported in this mode, and no live model or broker evaluation was performed.
The remaining limitations are real: non-author review, CI collection, and merge authorization
are still pending, and the course G-1/D9 gates remain unsatisfied. The useful result is that
the integration now has a durable audit and fail-closed behavior at the seams, with the known
validation record frozen rather than an unverified claim.

# CDE 接入实现计划（worktree `feat/CDE-integration`）

- 状态：实现与离线验证完成；待非作者评审及 CI/合并授权（工作文档，不是人工批准门）
- 日期：2026-11-18
- 作者：OpenCode（经 Codex 调度；未填学生身份）
- 基线：C/D 合并已提交 `70eb44f`；本次在合并 E `8c8112c` 的冲突解决后保存基线
- 关联：`docs/architecture/adr/004-cde-integration.md`、`architecture-blueprint.md`、
  `docs/architecture/invariants.md`、`tasks/C-safety.md`、`tasks/D-data-quality.md`、
  `tasks/E-audit.md`
- 范围声明：本计划记录接入契约、实现与测试设计；实现只改本轮授权的共享接入/新增测试路径，
  不改 C/D/E 叶子、不改 `tests/`。测试由 Codex 运行，本文件不记录未实际发生的通过结果。

## 1. 目标

把三个已合并的叶子模块接入现有运行路径，且不破坏原模式：

1. **D（数据充分性）先于模型调用**：不足时直接结束并留审计，模型 0 调用。
2. **原 AI 图产出候选**：Portfolio Manager 在同一结构化响应里可选地返回模拟候选。
3. **C（确定性安全）在发布前校验**：只有 `accepted` 且不是 `Hold` 才发布“已验证模拟提案”。
4. **E（审计）记录每个 run 的一条聚合 gate 记录**，并支持离线纯规则回放。
5. 原 `TradingAgentsGraph.propagate`、原 CLI 流式路径、原评级与报告输出保持兼容。

非目标：真实券商/下单、真实 API、修改 C/D/E 叶子模块、破坏性重构上游流程、课程合规声明。

## 2. 事实基线（读过的真实文件）

| 模块 | 路径 | 现有关键接口 |
| --- | --- | --- |
| D | `tradingagents/course/data_quality/admission.py` | `admit(observations, analysis_cutoff) -> AdmissionDecision`；`decision ∈ {proceed, abstain, review}` |
| D | `tradingagents/course/data_quality/contracts.py` | `RawObservation`、`DomainLabel`、`AdmissionDecision.to_dict()`；`REQUIRED_DOMAINS = news/social/macro/price/fundamentals` |
| C | `tradingagents/course/safety/validator.py` | `validate_proposal(proposal, *, context: SafetyContext) -> SafetyVerdict` |
| C | `tradingagents/course/safety/models.py` | `SimulationProposal.from_mapping`、`HoldingsSnapshot`、`RuleSet`、`SafetyContext`、`SafetyVerdict.to_dict()` |
| E | `tradingagents/course/audit/store.py` | `AuditStore.open/append/get/iter_run/verified_records/project/final_decision/head/verify_chain`；`entry_type ∈ {decision, rejection, abstain, revision}`；每 run 至多一条 initial decision |
| E | `tradingagents/course/audit/replay.py` | `replay_run(store, run_id, registry, trusted_head=None)`；registry `{gate_id: {rules_version: callable(inputs)->observed}}` |
| 图 | `tradingagents/graph/trading_graph.py` | `propagate(company_name, trade_date, asset_type="stock", portfolio=None)`；`create_run_state`、`_run_graph`、checkpoint 作用域 |
| PM | `tradingagents/agents/managers/portfolio_manager.py` | `PortfolioDecision` 结构化调用 + 自由文本回退；返回 `final_trade_decision`/`final_rating` |
| Schema | `tradingagents/agents/schemas.py` | `PortfolioDecision`、`render_pm_decision`（`**Rating**` 等标题被下游解析） |
| 状态 | `tradingagents/agents/state.py` | `AgentState`（含 `portfolio_context`、`final_rating` 等） |
| CLI | `cli/main.py`、`cli/run.py` | `analyze` 选项、`run_analysis(...)`；CLI 现走 `stream_run`，非 `propagate` |

已确认原始记录存在：`transcripts/role-C/raw.json`、`transcripts/role-E/raw.json`、
`transcripts/60569580-ChaoqunZHENG/`（role-D）。

## 3. 分层与依赖方向

- `tradingagents/course/pipeline.py` 是**共享薄编排器**，可导入 D/C/E 叶子与共享契约。
- 叶子之间**不得互相导入**：D 不导入 C/E，C 不导入 D/E，E 不导入 C/D。
- `tradingagents/course/__init__.py` 保持无副作用包标记，不导入任何叶子或 pipeline。
- `tradingagents/graph/trading_graph.py` 只依赖 `pipeline` 的公开函数与 `CourseRequest`，
  不直接导入叶子模块；pipeline 通过调用方注入的回调触发原 AI 图。
- 回调方向：`graph -> pipeline -> (D, C, E)`，pipeline 以 `invoke_ai` 回调反向调用图，
  避免图与叶子耦合，也避免叶子循环导入。

## 4. 设计

### 4.1 `CourseRequest`（显式、可 JSON 化、无 LLM 权威值）

必填字段（缺一即 fail-closed，不调模型）：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `run_id` | str | E 的 run 标识，非空 |
| `timestamp` | str | 带时区 ISO-8601；E 不读时钟 |
| `analysis_cutoff` | str | `YYYY-MM-DD`，交给 D |
| `observations` | list[dict] | D 的原始观察（RawObservation 兼容） |
| `holdings_snapshot` | dict | 可信账户快照（snapshot_id/as_of/currency/cash/positions/flat_declared） |
| `instrument` | str | 标的 |
| `instrument_currency` | str | 计价币种 |
| `rule_version` | str | 规则目录中的固定版本 |
| `audit_path` | str | SQLite 审计路径 |

`timestamp` 是上述 E 契约所必需，故显式加入；`record_id` 由编排器确定性生成
（`cde:<run_id>`），不接受外部覆盖。

金额/数量在 request 中允许数字或字符串，进入 C 前统一规范为**字符串**；`ignored_claims` 用
`list`；全部 payload 必须 `canonical_json` 可序列化。

### 4.2 流程（`run_course(request, invoke_ai)`）

1. 解析并校验 request；非法 → `CourseRequestError`，不调模型、不发布。`course_request`
   还必须与 `propagate` 的 `company_name`/`trade_date` 一致（ticker 或日期不符都在 AI 前拒绝）。
2. 在调用模型前**重新校验并深拷贝**请求（`CourseRequest.frozen_copy()`），固定本次独立快照；
   同时用 E 的 `validate_append_inputs` 预检 `timestamp` 等审计字段，非法即
   `CourseRequestError`，不调模型。
3. `admission = admit(request.observations, request.analysis_cutoff)`。
4. **模型前判定**：`admission.decision != "proceed"` 时：
   - `review` → 聚合记录 `entry_type="rejection"`，`payload.outcome="review"`；
   - `abstain` → `entry_type="abstain"`；
   - 追加 E 后直接返回，`invoke_ai` 不调用。
5. `proceed` → 调 `invoke_ai(course_context)`，返回 PM 的结构化候选或 `None`。
6. 编排器绑定可信引用：`holdings_snapshot = snapshot_id`、`rule_version = request.rule_version`；
   候选取 `action/units/price/currency`，并保留其他未知字段（如 `execution_mode`/`real_execution`）
   交给 C 识别；绝不静默抹除真实执行意图。
7. `SafetyContext(instrument, instrument_currency, 调用方 snapshot, RuleSet(version), available_rule_versions)`；
   快照原样交给 C 解析，不构造默认 `positions={}`。缺 `positions` 即拒绝；显式
   `positions={}` + `flat_declared=true` 才可视为空仓。`verdict = validate_proposal(...)`。
8. 规范化为可 JSON 的 observed；`entry_type = "decision" if verdict.accepted else "rejection"`。
9. 追加聚合 gate 记录；**追加失败即抛出，不发布**。
10. 返回 outcome；仅当 `verdict.accepted and not verdict.is_noop` 时带“已验证模拟提案”。

`Hold`（`accepted` 且 `units == 0`）是合法无操作：记录 decision，`published=False`，不带提案。

### 4.3 PM 结构化候选（同一响应内可选）

- `tradingagents/agents/schemas.py`：
  - 新增 `SimulationCandidate(BaseModel)`：`action: str | None`、`units: str | None`、
    `price: str | None`、`currency: str | None`，全部默认 `None`（缺失交给 C 拒绝）；
    金额是**十进制字符串**，避免先转 float 损失精度。
  - `SimulationCandidate` 设置 `extra="forbid"`：模型响应若携带 `execution_mode`/
    `real_execution` 等执行意图，结构化校验失败，而不是被截断成可发布候选。
  - `PortfolioDecision` 增加 `simulation_proposal: SimulationCandidate | None = None`。
  - `render_pm_decision` **不渲染**候选，保持原有 markdown 标题与末尾结构，报告兼容。
- `portfolio_manager.py`：仅当 state 有课程上下文时，在 prompt 末追加“填写 simulation_proposal”
  的说明；structured 路径把 `decision.simulation_proposal` 写入 state 的
  `simulation_proposal`；自由文本回退时该值为 `None`。
- 不接受“从评级文本/散文猜 units/price”：唯一来源是结构化字段。
- 模型看到任何余额文本都只作上下文；权威值只来自 request 的 trusted snapshot。
- `snapshot_id` 与 `rule_version` 由编排器绑定，模型候选里即使出现同类字段也被覆盖。

### 4.4 图入口与状态

- `propagate(..., course_request: CourseRequest | None = None)`；`None` 时走现有代码路径，
  行为与返回 `(final_state, signal)` 不变。
- 非 `None` 时：
  - 先核对 `course_request.instrument`/`analysis_cutoff` 与 `company_name`/`trade_date`；
    不一致在 AI 前抛 `CourseRequestError`；
  - 若 `config["checkpoint_enabled"]` → 明确拒绝（见 4.7），不读旧 checkpoint、不调模型；
  - 校验 request 后调用 `run_course`，`invoke_ai` 内部复用现有 `_run_graph` 流程，
    通过 `create_run_state` 注入 `course_context`；
  - PM 节点把 `simulation_proposal` 写回 state；图结束后 pipeline 完成 C/E 与发布决策；
  - `final_state` 仍含原有字段，另加 `course_result`（JSON 可序列化）；`final_rating`
    原样保留；返回 signal 由 C 结果导出（accepted buy→Buy、sell→Sell、hold→Hold、其余 REVIEW）。
- `AgentState` 增加 `course_context: str`、`simulation_proposal: dict | None`、
  `course_result: dict | None`（普通模式不写）。
- `record_decision`/报告/内存日志继续按原逻辑执行，但课程模式的“发布”以 C/E 结果为准。

### 4.5 CLI（同一程序入口）

- `cli/main.py` 的 `analyze` 增加 `--course-inputs PATH`（JSON 文件）。
- 读取并用 `CourseRequest` 解析；若同时提供 `--ticker`/`--date`，必须与 request 的
  `instrument`/`analysis_cutoff` 一致，否则在构建图/调用模型前报错退出。随后调用
  `TradingAgentsGraph.propagate(..., course_request=req)`，**与程序化入口是同一函数**；
  普通模式下 CLI 仍走现有流式展示路径，不改变行为。
- 课程模式输出只展示原报告 + 课程结果摘要；审计/拒绝原因以文本打印，非零退出码仅在
  请求错误/审计失败/冲突等 fail-closed 情况下使用。
- `--course-inputs` 与 checkpoint 同时出现 → 直接报错退出（范围决定见 4.7）。

### 4.6 E 事件与离线回放

- 每 run 只追加**一条最终聚合 gate 记录**：
  - `record_id = "cde:<run_id>"`（确定性，防双写）；
  - `entry_type`：`decision`（C accepted，含 Hold）或 `rejection` / `abstain`（D 阻断、C 拒绝）；
  - `rules_version = verdict.rule_version`（C 实际使用并由 orchestrator 固定的 trusted 版本）；
    D 在 C 之前阻断时，使用 request 中同一 trusted `rule_version`；
  - `payload = {gate_id, rules_version, inputs, observed}`，并带面向人的 `outcome` 字段。
- `inputs`（回放所需，纯规则）：`analysis_cutoff`、`observations`、`holdings_snapshot`、
  `instrument`、`instrument_currency`、`rule_version`、`candidate`（缺失为 `null`）。
- `observed`：`outcome`、`data_quality`（D 的 `to_dict`）、`safety`（C 的 `to_dict` 或 `null`）、
  `published`（bool）、`proposal`（`null` 或规范化的 action/units/price/currency + 绑定引用）。
- 程序固定注册 registry：`GATE_ID` → `{rule_version: replay_callback}`；回调只重跑 D 与 C
  纯规则（不调模型、不读 store、不访问网络）。未知版本由 E 的 `version_unknown` 置 review。
- D 的 `proceed` 只表示**数据充分性**，不是投资授权；run 的终局含义由 C 的 verdict 决定。
- 由于每 run 单条确定性记录，正常重试只会命中重复，不会产生同 run 第二条 decision。
- 被 D 阻断的 run 只有 `abstain`/`rejection` 事件、无 terminal decision；调用
  `final_decision(run_id)` 预期抛错，这本身就是“无决策”的诚实表达。

### 4.7 失败、幂等、并发与 checkpoint 范围决定

- **审计失败不发布**：先成功 `append`，再返回/保存结果；`append` 抛错则整个课程 run 失败，
  不返回已验证提案。
- **重复 run**：
  - 先 `store.get("cde:<run_id>")`/捕获 `duplicate_record_id`；
  - 记录与本次规范化 payload 一致 → 幂等返回已有结果，不重复写；
  - 不一致 → `CourseConflictError`，不写第二终局（也不自动 revision）。
- **并发/重试双写**：依赖 E 的 `BEGIN IMMEDIATE`、唯一 `record_id`、唯一 initial decision；
  第二个写入者捕获 `duplicate_record_id`/`duplicate_decision` 后走上面的比较逻辑。
- **输入冻结**：`CourseRequest` 在 D/模型前深拷贝并重新校验；模型回调修改调用方对象不能影响
  本次判定或回放证据。`RULE_CATALOG` 只含固定版本 `cde-long-only-v1`，并用只读映射暴露，
  调用方不能改全局规则目录。
- **checkpoint**：课程模式不兼容旧 checkpoint（旧状态缺 course 上下文）。本轮明确：
  `course_request != None` 且 checkpoint 启用 → 拒绝开启，报错退出；普通模式 checkpoint 原样保留。
  该限制记录为范围决定，不做静默降级。

### 4.8 JSON 规范

- 所有跨模块数据可 `json.loads(json.dumps(...))`；Decimal → 字符串；`ignored_claims` → list；
  tuple/set → list；禁止 NaN/inf；键必须为 str。
- E 的 `canonical_json` 是最终规范；pipeline 在写入前做一次规范化，避免 replay 形状漂移。

## 5. 预计变更文件（实现阶段）

| 文件 | 变更 |
| --- | --- |
| `tradingagents/course/pipeline.py` | 新增：CourseRequest/Outcome、run_course、gate registry、规范化 |
| `tradingagents/agents/schemas.py` | 新增可选仿真候选模型与字段；render 不变 |
| `tradingagents/agents/managers/portfolio_manager.py` | 课程提示 + 返回候选；普通模式不变 |
| `tradingagents/agents/state.py` | 新增三个可选状态键 |
| `tradingagents/graph/trading_graph.py` | `propagate` 增加可选参数、checkpoint 拒绝、pipeline 接入 |
| `cli/main.py` | `--course-inputs` 选项，走 `propagate` |
| `test/offline/test_cde_integration.py` | 新增离线测试 |
| `test/offline/test_cde_graph_flow.py` | 新增真实 LangGraph 端到端测试 |

不改 `tradingagents/course/{safety,data_quality,audit}` 叶子实现、不改 `tests/`、不改依赖。

## 6. 测试设计（真实 C/D/E，只固定模型与外部数据）

先写负例，再写正例；`tests/` 冻结，新增在 `test/offline/test_cde_integration.py` 与
`test/offline/test_cde_graph_flow.py`。

| # | 用例 | 断言 |
| --- | --- | --- |
| N1 | D 阻断（review/abstain） | 模型调用计数 = 0；有 E 记录；无发布 |
| N2 | 现金不足（buy units×price > cash） | C=`insufficient_cash`；E=rejection；无发布 |
| N3 | Hold（units=0） | C accepted；`is_noop`；E=decision；发布为 None |
| N4 | 缺候选 / 文本回退 | C=`missing_action`；无发布；不解析评级文本 |
| N5 | 缺可信快照 / 请求非法 | 0 模型调用；明确错误；无发布 |
| N5b | 缺 `positions` 但 `flat_declared=true` | C 拒绝，不补默认空仓；显式 `positions={}` + flat 才放行 |
| N5c | `execution_mode=live`/`real_execution=true` | C=`real_execution_requested`；额外字段不被编排器抹除 |
| N5d | 非法 `timestamp` | 模型 0 调用；`CourseRequestError` |
| N5e | ticker 或日期与 request 不一致 | AI 前 `CourseRequestError` |
| N5f | 模型回调篡改调用方快照/规则目录 | 判定使用冻结副本；全局目录不可写 |
| N6 | 未知 rule_version | C=`unknown_rule_version`；replay 为 `version_unknown`/review |
| N7 | 审计失败（不可写/链损坏） | 抛错；无发布；不声称成功 |
| N8 | 重复 run（相同/不同结果） | 相同→幂等且仅一条记录；不同→冲突且无第二终局 |
| N9 | 叶子导入约束 | D/C/E 互不导入；仅 pipeline 导入三者 |
| P1 | 合法 buy（现金足够） | accepted；发布含 trusted snapshot_id/rule_version；E=decision |
| P2 | 真实回放 | `replay_run` 对正常记录 pass；篡改副本后 review |
| P3 | 两种入口一致 | `propagate(course_request)` 与 CLI `--course-inputs` 结果/审计 payload 一致 |
| P4 | 普通模式回归 | `course_request=None` 的 `propagate` 返回与既有测试一致 |

测试注入：使用现有 client 缝（如 `create_tier_client`）注入确定性 stub LLM；外部数据用静态
fixture；不 mock D/C/E，不联网，不读凭证。

## 7. 最终离线验证（2026-11-18，已执行）

证据：`tasks/plans/integration/evidence/final-validation-2026-11-18.txt`

```text
python -m pytest -q -p no:cacheprovider --disable-warnings --tb=short \
  --basetemp <fresh temp> tests test/offline
1596 passed, 6 skipped, 1 deselected, 24 warnings, 100 subtests passed in 44.19s
suite_exit=0
ruff check .
All checks passed!
ruff_exit=0
python scripts/check_course.py --root .
course scaffold check: OK
schema_exit=0
```

其中上游 1407，课程离线 189（原 CDE 156 + 新增 33）。新增 33 含 3 个真实图端到端测试和
最后的内存审计拒绝回归。业务代码与测试自此冻结；非作者评审、CI 与合并授权仍待完成。

## 8. 风险与未决

- E 的 registry 由程序固定登记；若未来规则版本增加，必须同时登记回调，否则回放置 review（设计如此）。
- 课程模式只支持单一计价币种、long-only；费率/参考价偏离仍未实现（沿用 C 的范围）。
- 审计的 `trusted_head` 仍需库外保存；本轮不新增外部存储。
- 课程模式与 checkpoint 互斥是明确的减范围决定。
- 本仓库仍不声称课程 G-1/D9 合规；本计划也未被人工批准。

# ADR-004：CDE 叶子模块接入契约（D → 原 AI 图 → C → E）

- 状态：**接入代码和离线验证完成，待非作者评审及 CI/合并授权**（设计记录；未获人工批准）
- 日期：2026-11-18（Asia/Hong_Kong）
- 作者：OpenCode（经 Codex 调度编写；学生身份未提供，未填姓名/学号）
- 关联需求：FR-003、FR-004、FR-005、INV-003、INV-004、INV-005、NFR-003、NFR-004、NFR-005
- 关联文档：`architecture-blueprint.md`、`docs/architecture/invariants.md`、
  `docs/architecture/adr/001-course-extension.md`、`docs/architecture/adr/002-simulation-safety.md`、
  `docs/architecture/adr/003-append-only-audit.md`
- 关联计划：`tasks/plans/integration/CDE-integration-plan.md`
- 基线：C/D 合并 `70eb44f`；E 合并源 `8c8112c`

本 ADR 只记录接入决策与契约。它不修改任何叶子模块，不构成课程合规声明，也不满足或声称满足
课程 G-1/D9；工作流仍按 `DEVELOPMENT-POLICY.md` 的 owner-selected 偏差进行。

## 1. 背景与约束

C（确定性模拟安全）、D（数据充分性）、E（可验证审计）已各自合并，且被设计为**互不导入**的
叶子模块。现在需要一个共享编排器把它们接到现有运行路径，同时：

- 不改变原 `TradingAgentsGraph.propagate` 的默认行为、原评级解析和报告格式；
- 不让模型成为余额、快照或规则版本的权威来源；
- 不让“评级文本”反推数量；
- 审计失败时不发布结果；
- 跨模块数据可 JSON 序列化，并支持 E 的离线纯规则回放。

## 2. 决策

### 2.1 共享编排器：`tradingagents/course/pipeline.py`

新增一个薄编排器，位于 `tradingagents/course/` 顶层（不是叶子），导入 D/C/E 与共享契约，
按 `D -> invoke_ai -> C -> E` 执行。叶子之间仍互不导入；`course/__init__.py` 保持无副作用包
标记，不导入叶子或编排器。图与 CLI 只依赖 pipeline 的公开类型/函数，不直接导入叶子。

依赖方向：

```text
cli/main.py ─┐
             ├─> graph/trading_graph.py ─> course/pipeline.py ─> data_quality (D)
             │                                             ├─> safety (C)
             │                                             └─> audit (E)
             └─(普通模式，保持现有流式路径)
graph ──invoke_ai 回调──> pipeline（反向，仅调用注入的图回调，不形成导入环）
```

### 2.2 `CourseRequest` 契约

课程模式**只**由调用方显式提供下列输入；任何一项缺失即 fail-closed：

```json
{
  "run_id": "run-20261118-001",
  "timestamp": "2026-11-18T10:00:00+08:00",
  "analysis_cutoff": "2026-11-17",
  "observations": [
    {"domain": "news", "kind": "value", "source": "fixture", "observed_as_of": "2026-11-17", "value": 1, "value_present": true}
  ],
  "holdings_snapshot": {
    "snapshot_id": "acct-1-20261117",
    "as_of": "2026-11-17",
    "currency": "USD",
    "cash": "10000.00",
    "positions": {"NVDA": "10"},
    "flat_declared": false
  },
  "instrument": "NVDA",
  "instrument_currency": "USD",
  "rule_version": "cde-long-only-v1",
  "audit_path": "cde-course.sqlite"
}
```

- `timestamp` 为 E 的显式时间（E 不读时钟）；`record_id` 由编排器确定性生成，不接受外部覆盖。
- `observations` 直接交给 D 的 `admit`；金额/数量规范为字符串。
- 权威余额/持仓只来自 `holdings_snapshot`；**不读 LLM 文本**。
- 有意不提供“数量/动作”字段：候选只能来自 PM 的结构化响应。

### 2.3 程序入口：`TradingAgentsGraph.propagate(..., course_request=None)`

- `course_request is None`：完全走现有路径，返回值仍为 `(final_state, signal)`。
- `course_request` 存在：先核对 request 的 `instrument`/`analysis_cutoff` 与 `propagate` 的
  `company_name`/`trade_date`；任一不一致即抛 `CourseRequestError`，不调模型。随后调用
  `pipeline.run_course(request, invoke_ai)`；`invoke_ai` 复用现有 `create_run_state`/`_run_graph`，
  把课程上下文写入 state，并取回 PM 的 `simulation_proposal`。
- 原 `final_rating`、`final_trade_decision`、报告、内存日志保持原有形状；新增的
  `course_result` 为附加 JSON 字段，原消费者可忽略。返回 signal 由 C 结果导出：
  accepted buy→`Buy`、accepted sell→`Sell`、合法 hold→`Hold`、其余→`REVIEW`。
- **checkpoint 范围决定**：课程模式复用旧 checkpoint 会缺少课程上下文，因此当
  `checkpoint_enabled` 与 `course_request` 同时存在时明确拒绝启动（不静默降级）；普通模式
  checkpoint 支持不变。

### 2.4 PM 结构化候选（同一响应内可选）

`PortfolioDecision` 增加可选 `simulation_proposal`：

```text
SimulationCandidate (extra="forbid"):
  action: "buy" | "sell" | "hold" | null
  units: decimal string | null
  price: decimal string | null
  currency: string | null
```

- 仅在课程模式 prompt 中要求填写；普通模式默认 `None`。
- 金额使用**十进制字符串**，避免在交给 C 前先经 float 损失精度。
- `extra="forbid"`：模型响应若带 `execution_mode`/`real_execution` 等执行意图，结构化校验
  失败，而不会被静默截断为可发布候选。编排器的候选规范化也保留这些未知字段，交给 C 的
  `real_execution_requested` 拒绝。
- 缺失字段或自由文本回退 → 候选视为缺字段，交给 C 拒绝（`missing_action` 等）。
- **不从评级文本或散文猜数量/价格**；唯一来源是结构化字段。
- `snapshot_id` 与 `rule_version` **由编排器绑定**，模型即使输出同名字段也被忽略/覆盖。
- `render_pm_decision` 不渲染候选，保持 `**Rating**`/`**Executive Summary**`/`**Investment Thesis**`
  等标题与现有报告兼容。

### 2.5 顺序：D 先于模型

`admit(observations, analysis_cutoff)` 在模型调用前执行：

- `decision == "review"` → 聚合记录 `rejection`（`payload.outcome="review"`），不调模型；
- `decision == "abstain"` → 聚合记录 `abstain`，不调模型；
- `decision == "proceed"` → 调模型并进入 C。

D 的 `proceed` 只表示**数据充分性**，不是投资授权；是否有投资动作由 C 的 verdict 决定。

### 2.6 C 校验与“发布”定义

- 候选规范为 `{action, units, price, currency, holdings_snapshot: snapshot_id, rule_version}`，
  配 `SafetyContext(instrument, instrument_currency, 调用方 snapshot, RuleSet, available_rule_versions)`。
- 调用方快照**原样交给 C 解析**；编排器不构造默认 `positions={}`。缺 `positions` 即拒绝，
  显式 `positions={}` 且 `flat_declared=true` 才视为空仓。
- `verdict = validate_proposal(...)`；C 的 `rule_version`/`snapshot_id` 取自 trusted context。
- **只有 `verdict.accepted and not verdict.is_noop` 才发布已验证模拟提案**。
- `Hold` 是合法无操作：C accepted、`is_noop=True`，记录 decision，`published=False` 且无提案。
- 现金不足、币种不符、快照不符、未知版本等一律拒绝，不发布。

### 2.7 E：每 run 一条聚合 gate 记录

E 只有 `decision` / `rejection` / `abstain` / `revision` 四类事件。本接入约定：

- 每个 run 追加**恰好一条**最终聚合 gate 记录；`record_id = "cde:<run_id>"`（确定性）。
- `entry_type`：C accepted → `decision`（含 Hold）；C 拒绝或 D review → `rejection`；
  D abstain → `abstain`。
- `rules_version`：取 C 实际固定使用的 `verdict.rule_version`；D 在 C 前阻断时取 request 的同一
  trusted `rule_version`。
- `payload`：

```json
{
  "gate_id": "cde.pipeline.final",
  "rules_version": "cde-long-only-v1",
  "inputs": {
    "analysis_cutoff": "2026-11-17",
    "observations": ["..."],
    "holdings_snapshot": {"snapshot_id": "...", "cash": "10000.00", "positions": {"NVDA": "10"}, "...": "..."},
    "instrument": "NVDA",
    "instrument_currency": "USD",
    "rule_version": "cde-long-only-v1",
    "candidate": {"action": "buy", "units": "5", "price": "100", "currency": "USD"}
  },
  "observed": {
    "outcome": "accepted",
    "data_quality": {"decision": "proceed", "...": "..."},
    "safety": {"accepted": true, "reason_code": "accepted", "ignored_claims": [], "...": "..."},
    "published": true,
    "proposal": {"action": "buy", "units": "5", "price": "100", "currency": "USD",
                 "holdings_snapshot": "acct-1-20261117", "rule_version": "cde-long-only-v1"}
  }
}
```

- 回放 registry 由程序固定登记：`GATE_ID -> {rule_version: callback}`；callback 只重跑 D 与 C
  的纯规则并返回同形状 `observed`，**不调模型、不读 store、不联网**。
- 未知版本、缺键、回调异常、结果不一致由 E 现有逻辑置 `review`；失配不会静默通过。
- `observed` 的 `ignored_claims` 为 list，金额为字符串，整体可 JSON 序列化。
- 同一 run 的重复执行命中确定性 `record_id` / 唯一 decision 约束；绝不产生第二条终局。
- 被 D 阻断的 run 没有 terminal decision，`final_decision(run_id)` 预期抛错，这表示“本 run 无决策”。

### 2.8 失败、幂等与并发

- **输入冻结**：`run_course` 在 D/模型前深拷贝并重新校验 `CourseRequest`；模型回调修改调用方
  对象不得影响本次判定或回放证据。固定规则目录 `cde-long-only-v1` 用只读映射暴露，调用方不能
  修改全局 catalog。
- **审计元数据预检**：模型调用前复用 E 的 `validate_append_inputs` 校验 `timestamp` 等字段；
  非法请求直接 `CourseRequestError`，避免先调模型再报审计错误。
- **审计持久性**：`audit_path` 为 `:memory:` 或 SQLite memory URI 时，在模型前抛
  `CourseRequestError`；内存记录关闭后消失，不能作为可验证证据。
- **先审计后发布**：E `append` 成功后才返回已验证提案；追加失败 → 课程 run 失败、不发布。
- **幂等**：重复执行先读 `cde:<run_id>`；规范化 payload 相同则返回既有结果，不重复写。
- **冲突**：同一 run 得到不同结果 → `CourseConflictError`，不写第二终局；`revision` 仅保留给
  显式修订流程，不自动使用。
- **并发/重试**：复用 E 的 `BEGIN IMMEDIATE`、`duplicate_record_id`、`duplicate_decision`
  作为串行化信号；捕获后重新读取并比较，不覆盖。
- **JSON 规范**：Decimal→str、tuple/set→list、键必须 str、拒绝 NaN/inf；以 E 的
  `canonical_json` 为准。

### 2.9 CLI

- `cli/main.py` 新增 `--course-inputs PATH`；读取 JSON → `CourseRequest` →
  `TradingAgentsGraph.propagate(..., course_request=...)`，与程序化调用**同一入口**。
- 若同时给出 `--ticker`/`--date`，必须与 request 的 `instrument`/`analysis_cutoff` 一致，
  否则在构建图或调用模型前报错退出。
- 普通模式 CLI 仍走现有 `stream_run` 展示路径，行为不变。
- 课程模式与 checkpoint 同时请求 → 报错退出（2.3 的范围决定）。

## 3. 备选方案与取舍

- **新增独立 CLI 子命令/脚本**：会造成第二套入口、易与 `propagate` 行为漂移 → 拒绝。
- **图直接导入叶子模块**：违反叶子边界与测试约束 → 拒绝。
- **由 PM 文本解析数量**：不可靠且违反“不得从评级文本猜数量” → 拒绝。
- **每 run 写多条 D/C/E 事件**：与“避免同 run 重复 decision”冲突，回放分母也易漂移 →
  采用一条聚合 gate 记录。
- **课程模式复用 checkpoint**：旧状态缺少 course 上下文，会静默产生错误终局 → 明确拒绝。
- **把 D 的 proceed 当作投资授权**：语义错误 → 终局只由 C verdict 决定。

## 4. 后果

优点：叶子保持独立；入口单一；C 是发布的唯一硬门；E 可离线真实回放；普通模式零行为变化。

代价/限制：

- 课程模式暂不支持 checkpoint 恢复；
- 只支持 long-only、单一计价币种；费率/参考价偏离仍不在 C 范围；
- 每 run 只有一条聚合事件，细粒度诊断靠 payload 内的 D/C 结构；
- `trusted_head` 仍需库外保存（沿用 ADR-003）；
- PM 结构化输出依赖 provider 支持；不支持时课程候选为空，C 会拒绝（fail-closed）。

## 5. 验证结果（2026-11-18）

最终离线验证已执行，证据见
`tasks/plans/integration/evidence/final-validation-2026-11-18.txt`：

- 组合回归 `tests` + `test/offline`：**1596 passed, 6 skipped, 1 deselected,
  24 warnings, 100 subtests passed in 44.19s**；`suite_exit=0`。
- 其中上游 **1407 passed**，课程离线 **189 passed**（原 CDE 156 + 新增 33）。
- 新增 33 含 3 个真实 LangGraph 端到端测试（合法发布、超现金 `REVIEW`、CLI
  `--course-inputs`）和最后的内存审计拒绝回归。
- `ruff check .` 通过（`ruff_exit=0`）；`check_course` OK（`schema_exit=0`）。
- 未进行运行时 live 模型或券商评估；测试使用脚本模型与离线替身。

负例覆盖 D 阻断 0 模型调用、现金不足、缺候选、缺快照、未知版本、审计失败/篡改、重复冲突、
ticker/日期不一致、缺失持仓、回调篡改、内存审计路径；正例覆盖合法 buy 发布、Hold 无操作、
真实离线回放、两种入口一致与普通模式回归。业务代码与测试自最终验证后冻结。

## 6. 未决与边界

- gate registry 的版本扩展需与 C 的规则目录同步登记；否则回放置 `review`（设计如此）。
- 审计记录中的 `timestamp` 是调用方输入，不是可信时间源。
- 本 ADR 未被人工批准，也未满足课程 G-1/D9；不得据此声称课程合规。

# FR-003 实现计划｜C 确定性模拟安全

**版本 v0.2，供团队评审。** 已按团队 `main` 的固定快照更新。本文是计划，功能和测试尚未实现或运行。配套文件为 [FR-003 测试计划](FR-003-test-plan.md)。

## 1. 基线与现有入口

- 团队仓库当前默认分支为 `main`，本次核对提交 `7dc46516935755d5a09ba3507ccd55dbadda066b`。团队登记的上游基线为 v0.7.1、`9fa1196fffbcfd9de5146d2dd2869df84ab99838`。查阅的分支列表有 `main` 和 `feat/D-data-quality`，未见 C 分支。固定快照的文件树未见 `tradingagents/course/safety/` 或 C 离线测试。 [团队快照](https://github.com/lyx08042/cs5351-tradingagents/tree/7dc46516935755d5a09ba3507ccd55dbadda066b) · [基线台账](https://github.com/lyx08042/cs5351-tradingagents/blob/7dc46516935755d5a09ba3507ccd55dbadda066b/docs/baseline.md)
- `GraphSetup.setup_graph()` 把 Trader 的结果送进风险讨论，再交给 Portfolio Manager。后者可以取得结构化 `PortfolioDecision`，但对外状态目前暴露的是 `final_trade_decision` 报告文本和 `final_rating` 等字段。模型不支持结构化输出时还会回退到文本。C 应使用独立的结构化候选契约，避免从文本评级猜测下单数量或把评级直接当作交易授权。 [图装配](https://github.com/lyx08042/cs5351-tradingagents/blob/7dc46516935755d5a09ba3507ccd55dbadda066b/tradingagents/graph/setup.py) · [Portfolio Manager](https://github.com/lyx08042/cs5351-tradingagents/blob/7dc46516935755d5a09ba3507ccd55dbadda066b/tradingagents/agents/managers/portfolio_manager.py#L80-L106)
- 程序入口 `TradingAgentsGraph.propagate()` 和 CLI 的 `run_analysis()` 采用不同的图运行方式，最终都调用 `record_decision()`。该函数写的是运行状态与决策记忆。CLI 的 `--portfolio` 可从文件加载账户上下文，图会将其渲染给代理。沿已检查的入口未找到模拟订单、现金或持仓的交易写入点，因此本轮以**是否发布了可供后续系统消费的已验证模拟提案**为集成验收点。 [程序入口与决策记录](https://github.com/lyx08042/cs5351-tradingagents/blob/7dc46516935755d5a09ba3507ccd55dbadda066b/tradingagents/graph/trading_graph.py#L359-L405) · [CLI 收尾](https://github.com/lyx08042/cs5351-tradingagents/blob/7dc46516935755d5a09ba3507ccd55dbadda066b/cli/run.py#L345-L385) · [账户上下文](https://github.com/lyx08042/cs5351-tradingagents/blob/7dc46516935755d5a09ba3507ccd55dbadda066b/tradingagents/portfolio.py)

## 2. 需求与验收

沿用团队 registry，四条均为 `must`、当前为 `proposed`。此前初稿的临时需求 ID 由下表替代。需要更新验证描述时，使用 Schema 要求的 `fit.metric`、`fit.threshold`、`fit.verification`，沿用已有条目。 [需求注册表](https://github.com/lyx08042/cs5351-tradingagents/blob/7dc46516935755d5a09ba3507ccd55dbadda066b/docs/req/requirements.yaml) · [JSON Schema](https://github.com/lyx08042/cs5351-tradingagents/blob/7dc46516935755d5a09ba3507ccd55dbadda066b/docs/req/req-schema.json)

| 需求 | 已登记阈值 | 本计划的验证方式 |
| --- | --- | --- |
| `FR-003` | 非法提案拒绝率 1.0 | 测试合法 Buy、Sell、Hold，以及缺字段、现金不足、卖出超量和非法价格等负例 |
| `INV-003` | 非法提案通过数 0 | 模型自报安全也要执行代码校验。正常入口对被拒提案发布的已验证交易提案数为 0 |
| `SEC-001` | 真实执行路径数 0 | 真实券商或下单请求的负例，加上对生产依赖和可达调用路径的代码审阅 |
| `NFR-003` | 重复回放一致率 1.0 | 固定候选、可信快照和规则版本，两次离线结果的决定与原因码一致。与 E 验证审计回放契约 |

规则以任务书为准。当前 long-only 策略要求 Buy/Sell 的数量大于零，买入所需资金可覆盖，卖出数量不超过可信持仓，价格大于零且为有限数，Hold 的数量为零且仍需快照及规则版本。空仓要有显式证据。任务书给出的现金和持仓约束优先；价格相对行情的偏离阈值、额外仓位上限、费用及舍入公式属于待确认的策略细节。 [C 任务书](https://github.com/lyx08042/cs5351-tradingagents/blob/7dc46516935755d5a09ba3507ccd55dbadda066b/tasks/C-safety.md)

## 3. ADR 草案｜确定性规则与共享发布边界

| 候选 | 收益 | 代价 |
| --- | --- | --- |
| A．最终提案之后，在 CLI 和程序入口共用的收尾流程中调用同一个安全校验器，再发布已验证模拟提案 | 两条入口共享判断，便于阻断违规发布，便于离线固定输入 | 需要协调调用路径及数据传递。`record_decision()` 是现有汇合点线索，其参数、调用方和日志兼容性需核对 |
| B．Portfolio Manager 后接新的图节点，再输出已验证模拟提案 | 图中能看到单独的安全阶段 | 需要在图状态中传入可信账户及规则，核对 checkpoint 恢复、旧图状态及两种运行方式 |

**拟选 A。** 在 `tradingagents/course/safety/` 放置纯校验器，由受控的收尾路径调用。先在 C 模块内完成规则与测试，再通过协调 PR 确认共享接入。ADR 和接口记录确认后，以最小改动保留既有评级、报告及程序返回语义。收尾时把原始建议和 C 的已验证结果分开存放，只有通过 C 校验的 Buy/Sell 可以进入已验证模拟提案字段。Hold 保留为合法的无操作。若未来确有模拟器，在写入前也必须验证对应提案和有效快照。

| 边界 | 拟定契约 |
| --- | --- |
| 提案输入 | 使用团队定义的 `action`、`units`、`price`、`currency`、`holdings_snapshot`、`rule_version`、`status`。由调用方绑定实际运行标的。模型可以提出动作、数量和价格，状态与授权由确定性代码赋予 |
| 可信快照及规则 | 账户快照从明确传入的结构化 `PortfolioContext` 或团队指定账户源组装，保留显式空仓语义。模型自报余额、持仓、规则版本和状态不能作为权威。对价格做有限性、正值及币种一致性校验。若团队指定可信执行价或参考价，现金校验应按已定义的计价口径执行 |
| 失败路径 | 缺少可验证候选、账户快照或有效规则时阻断。格式错误、业务违规或校验异常时也不发布已验证交易提案。原因码稳定，原始文本可继续作为分析证据 |
| D 与 E | D 可提供数据准入状态，C 仍检查自己使用的账户及价格字段。C 向 E 交付决定、原因码、提案关联 ID、快照引用及规则版本；E 负责审计与重放。两方须确认快照引用能解析出回放使用的固定数据 |

默认改动限于 C 安全模块、`test/offline/` 内的 C 测试和 C 的任务文档。共享 CLI、图或经理模块改动通过协调 PR 处理，并记录安全 ADR。上游 `tests/` 和依赖配置属于受保护路径。 [权限模型](https://github.com/lyx08042/cs5351-tradingagents/blob/7dc46516935755d5a09ba3507ccd55dbadda066b/docs/architecture/permission-model.md)

## 4. 实施、交接与评审

1. 在自己的 C 分支同步团队 `main`，将两份工作文档保存为 `tasks/plans/C/FR-003-implementation-plan.md` 和 `tasks/plans/C/FR-003-test-plan.md`。本次只读核对未创建分支。
2. 记录 ADR，先写离线规则测试，再实现 C 模块。在接入共享路径前，与上游确认结构化候选来源、与 D/E 确认交接字段，并确定 Hold 的价格字段语义、快照格式和规则版本。确定接口后加入正常入口的防绕过测试。
3. 执行配套测试计划。保留固定输入、命令、两侧提交、退出状态和实际输出。更新 C 的追踪证据、真实 AI-use log 和会话干预记录。
4. 提交 C 的 PR 时附 ADR、运行证据与可复现命令，完成非作者评审、CI 和最终合并授权。任务书当前指定 B 评审 C。按本次对话中你描述的分工，由你安排人选及流程；如另定人选，应与团队确认后如实记录。 [C 任务书](https://github.com/lyx08042/cs5351-tradingagents/blob/7dc46516935755d5a09ba3507ccd55dbadda066b/tasks/C-safety.md) · [团队流程](https://github.com/lyx08042/cs5351-tradingagents/blob/7dc46516935755d5a09ba3507ccd55dbadda066b/DEVELOPMENT-POLICY.md)

**评审口径。** 当前仓库政策把实现计划和测试设计作为工作文档，允许完成后继续实现。课程项目说明第 7、10 页另要求 D9 的计划批准停点和 G-1 的实现前测试批准。仓库政策明确记录了这一差异。若 C 实际保留这两个课程停点，分别保存真实批准；若走仓库现行流程，提交时如实写明偏离及实际发生的评审。

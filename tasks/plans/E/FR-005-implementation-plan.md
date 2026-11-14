## Implementation Plan: FR-005（E 模块 · 可验证审计 + 决策修订 + 离线 gate 回放）

- 作者：OpenCode（经 Codex 编排编写；学生身份未提供，未填姓名/学号）
- 评审人（非作者，计划阶段）：待 owner 批准本文件时指派（预期 D，见 §11）
- 关联测试计划：`tasks/plans/E/FR-005-test-plan.md`
- 关联 ADR：`docs/architecture/adr/003-append-only-audit.md`（PROPOSED）
- 基线 commit：`7dc46516935755d5a09ba3507ccd55dbadda066b`
- 日期：2026-11-14（Asia/Hong_Kong）
- 状态：`awaiting owner approval`（M1 只产出计划 + ADR；本文件描述批准后要做什么，未实现）
- 批准引用：无（尚未发生人工批准）

E 本次自愿采用实现前批准停点：owner 批准本计划与 ADR 后才进入 M2。这不改变全组政策，也不构成批准记录。

### 1. 目标与需求锚点

- 主需求：FR-005 — 最终决策可验证审计：记录不可变、终局决策唯一且具权威性、修订以 supersede 链保存、支持离线 gate 回放。
- 不变量：INV-005 — 审计不可变；终局决策唯一；修订以 supersede 链保存，旧版本可回放。
- 非功能：NFR-003（确定性回放）、NFR-004（拒绝/abstain/review 留痕）、NFR-005（叶子模块无循环导入）。
- 需求在 registry 中仍为 `proposed`，实现后也不自动变成 `approved`。

### 2. 变更范围（M2 要动的文件）

新增，仅限 E 归属路径：

- `tradingagents/course/__init__.py`（让 `tradingagents.course.audit` 可导入的最小包文件）。
- `tradingagents/course/audit/__init__.py`（导出公共 API）。
- `tradingagents/course/audit/records.py`（规范 JSON、哈希、`AuditRecord`、错误码）。
- `tradingagents/course/audit/store.py`（SQLite 追加式存储、全局链、schema、触发器、唯一约束）。
- `tradingagents/course/audit/replay.py`（gate registry 回放、`trusted_head` 校验）。
- `tradingagents/course/audit/__main__.py`（独立演示入口，见 §9）。
- `tradingagents/course/audit/README.md`（模块说明与独立演示用法）。
- `test/offline/test_audit.py`（离线正/负向测试，见测试计划）。

不修改：`tests/**`、既有上游 `tradingagents/**`（分析师/研究员/交易员/记忆/图等）、`cli/**`、`pyproject.toml`、`.github/**`、`scripts/**`、`docs/approvals/**`、`AGENTS.md`、`Prompt.md`、`opencode.json`、`.opencode/rules.md`。

`docs/ai-use-log.yaml` 在本次计划阶段不修改。真实编码完成后由 OpenCode 按实际会话追加 AI 使用记录，并补 raw session、annotations、交接与报告素材；记录内容须与真实发生一致。个人反思与非作者评审不由代理代写。

不引入新依赖；实现只用标准库（`sqlite3`、`hashlib`、`json`、`datetime`、`ast` 仅测试侧用）。

独立运行边界（重要）：上游 `tradingagents/__init__.py` 会 import python-dotenv 并可能自动 `load_dotenv()` 读取 `.env`。因此不承诺“从仓库根 `python -m tradingagents.course.audit` 只依赖标准库、不读环境文件”。独立验收采用在 `tradingagents/course` 目录下 `python -S -m audit --demo`：以 `audit` 为顶层包加载 `audit/__main__.py`，包内全部用相对导入（`from .records import ...`），从而不加载顶层 `tradingagents`、不加载 dotenv、不读 `.env`、不访问凭证，`-S` 也不加载 site-packages 的第三方包。正常已安装环境仍可 `python -m tradingagents.course.audit`，但它继承上游的 python-dotenv 依赖与环境加载行为，不作为独立证明依据。不改上游 `tradingagents/__init__.py` 及任何既有源码。

### 3. 设计概述

#### 3.1 存储：SQLite 单文件，单行同存 payload

- 每条记录一行；`payload` 以规范 JSON 序列化后与元数据同行存储；另存 `payload_ref = "sha256:" + sha256(canonical(payload))`。
- 追加在 `BEGIN IMMEDIATE` 事务内完成“读取当前头 → 计算 record_hash → 校验规则 → INSERT”，先拿写锁，避免多实例同时抢先建决策或按同一头做 revision。
- `PRAGMA journal_mode=WAL`，建表/索引/触发器用 `IF NOT EXISTS`，可幂等重开。

理由：审计低频、强一致；SQLite 事务 + WAL 足够，单文件便于离线演示与测试，无外部服务。

这是应用层不可变 + 可检测篡改，不是 WORM、不是签名，也不假设拥有文件的管理员无法修改。

#### 3.2 不可变：触发器 + 只追加 API

- `BEFORE UPDATE` / `BEFORE DELETE` 触发器 `RAISE(ABORT)`。
- 公共 API 只有 append 与读取，无 update/delete 方法。

触发器防的是通过本库 SQL 连接的改/删；用其他工具关掉触发器或换文件仍能改，因此还需链哈希与 trusted_head。

#### 3.3 全局链：单条链，按 sequence 排序

整个数据库只有一条链，不按 run 分链。表内有 SQLite 自增 `sequence`，链顺序即 `sequence` 顺序。

- 每条记录存 `previous_record_id` 与 `previous_hash`；root 记录 `previous_record_id` 与 `previous_hash` 均为 null。
- `record_hash = sha256(canonical(record_id, run_id, timestamp, entry_type, payload, rules_version, supersedes, previous_record_id, previous_hash))`。
- `run_id` 只用于筛选（`iter_run` / `project` / `final_decision`），不改变链结构。
- `verify_chain` 遍历**全部**记录（按 sequence），检查：从 root 起前驱连续（第 k 条的 `previous_record_id` 等于第 k-1 条的 `record_id`、`previous_hash` 等于第 k-1 条的 `record_hash`）、每行 `record_hash` 重算一致、`payload_ref` 与 payload 一致、决策/修订语义合法（每 run 至多一个首建 decision、revision 指向当时叶子终局）。这能发现孤儿行、缺中间行、重排、字段改、payload 换；不只是回溯当前头。
- append 在写前先 `verify_chain`，已损坏则拒写。
- `final_decision` / `project` 在返回权威结果前先 `verify_chain`，损坏则拒绝，不返回看似有效的终局。

内部链无法察觉整段尾部截断或从某点整体重算哈希；这靠外部 trusted_head（§3.4）。

#### 3.4 外部 trusted_head

- `head()` 返回当前 `(record_id, record_hash, count)`，调用方把它存到库外（发布记录、CI 产物、日志等）。
- `verify_against_trusted_head` 检查“当前头与已封存 head 是否完全相等”。
- 判定语义要准确：不相等不等于被篡改。后续合法追加也会使当前头不等于旧 head。因此不相等输出 `head_mismatch` 并置 review，交人工确认，不自动判为篡改。
- 合法追加后，可信方需另存新 checkpoint；库当前值不能自动被当作可信值。

#### 3.5 时间与 id 由调用方传入

- `timestamp` 为调用方传入的带时区 ISO-8601 字符串，解析时须能识别 offset。库不读系统时钟。
- `record_id` 由调用方显式传入，库不生成随机 id。
- 违反（无时区、坏格式、空 id、重复 id）抛错，不静默修正。

理由：NFR-003 要求同输入同记录同哈希；读时钟/随机 id 会破坏确定性。

#### 3.6 payload 的 JSON 约束

- 只接受 JSON 原生类型：`dict`（键必须是 `str`）/ `list` / `str` / `bool` / `int` / `float`（有限）/ `None`。
- 拒绝非字符串 key、`NaN` / `Infinity` / `-Infinity`（`json.dumps(..., allow_nan=False)`）。
- 不静默转换输入，遇到即抛错。
- 规范：`sort_keys=True`、`separators=(",", ":")`、`ensure_ascii=False`，utf-8 编码后 sha256。

### 4. 数据契约

#### 4.1 读取/返回的 `AuditRecord`（不可变）

| 字段 | 类型 | 说明 |
|---|---|---|
| `record_id` | str | 调用方显式传入，全局唯一 |
| `run_id` | str | 所属运行 |
| `timestamp` | str | 带时区 ISO-8601 |
| `entry_type` | str | 见 4.2 |
| `payload_ref` | str | `sha256:<hex>`，由 store 生成 |
| `rules_version` | str | 该记录适用规则版本 |
| `previous_record_id` | str \| null | 全局链前驱；root 为 null |
| `payload` | JSON | 事件内容，规范 JSON 存内 |
| `previous_hash` | str \| null | 前驱 record_hash；root 为 null |
| `record_hash` | str | 本条哈希，store 生成 |
| `supersedes` | str \| null | 仅 revision 使用：被取代的当前终局 record_id |

`AuditRecord` 作为读取/返回的不可变数据。构造时内部已持有规范 JSON 文本；`to_dict()` 返回**深拷贝**，调用方修改返回值不影响记录内部状态（不能只是 frozen 外壳、内部嵌套 payload 仍可变）。

#### 4.2 entry_type 与 review

- `entry_type ∈ {decision, rejection, abstain, revision}`。
- review 不单列第五类，作为 `rejection` 的 `payload.outcome = "review"` 表达（升级人工复核，不自动通过）。

#### 4.3 superseded_by 与 final_decision

- 不把 `superseded_by` 写回旧行。读取投影时从“后继 revision 的 `supersedes`”导出：若 revision R 的 `supersedes == old_id`，投影中 `old_id.superseded_by = R.record_id`。
- `final_decision(run_id)`：在该 run 内沿 supersede 链到唯一叶子；多条叶子或该 run 无 decision → 不变量破坏，报错，不随便挑一条。返回前先 `verify_chain`。

### 5. 决策与修订规则（INV-005）

1. 每 run 只能首建一次 decision：某 `run_id` 已有首条 `decision` 后再 append `entry_type=decision` 被拒（改用 revision）。`(run_id, entry_type)` 部分唯一索引 + 事务内检查双重保障。
2. revision 的 `supersedes` 必须存在且是该 `run_id` 当前叶子终局。拒绝：跨 run、指向已被取代的旧头、指向 rejection/abstain 事件、指向不存在 id、null。
3. 旧行不改；revision 只加新行，`superseded_by` 靠投影导出。
4. rejection/abstain 不是 decision，不参与终局判定，也不能作为 revision 的 supersedes 目标。
5. 并发：`BEGIN IMMEDIATE` + 唯一索引保证首次决策竞争只一个赢；revision 竞争按当前头校验，另一连接已推进链则本次因 `supersedes` 不再是叶子被拒。

### 6. 公共 API 契约（草案，待批准）

错误设计从简：一个 `AuditError`，带稳定的字符串 `code`，用 `code` 区分原因，不铺开大量无必要子类。错误码示例：`invalid_json`、`non_string_key`、`non_finite_number`、`invalid_timestamp`、`empty_id`、`duplicate_record_id`、`duplicate_decision`、`invalid_supersede`、`chain_broken`、`invariant_violation`。

`records.py`

- `canonical_json(obj) -> bytes`：按 §3.6 序列化；非法抛 `AuditError(code=...)`。
- `payload_ref(payload) -> str`：`"sha256:" + hex`。
- `AuditRecord`：读取/返回类型，字段见 §4.1；`to_dict()` 深拷贝。由 store 构造，不接受调用方伪造 `payload_ref`/`previous_record_id`/`previous_hash`/`record_hash`。

`store.py`

- `AuditStore.open(path) -> AuditStore`：建表、索引、触发器，WAL，幂等重开。
- `AuditStore.append(*, record_id, run_id, timestamp, entry_type, payload, rules_version, supersedes=None) -> AuditRecord`：调用方**不传** `payload_ref`/`previous_record_id`/`previous_hash`/`record_hash`，这些由 store 在事务内基于已有链生成，防止伪造前驱。流程：先 `verify_chain`（已损坏则拒写）→ 生成 `payload_ref` → 计算链前驱 → 校验 §5 规则 → INSERT。返回构造好的 `AuditRecord`；失败整事务回滚，不留半条记录。
- `AuditStore.get(record_id) -> AuditRecord | None`。
- `AuditStore.iter_run(run_id) -> list[AuditRecord]`：按 sequence 顺序。
- `AuditStore.project(run_id) -> dict`：返回前先 `verify_chain`；含各记录 `superseded_by`。
- `AuditStore.final_decision(run_id) -> AuditRecord`：返回前先 `verify_chain`，返回唯一叶子。
- `AuditStore.head() -> tuple[record_id, record_hash, count]`。
- `AuditStore.verify_chain() -> VerificationResult`：按 §3.3 遍历全部记录，返回 ok 或破损位置与原因；库损坏到无法读时抛 `AuditError`。

`replay.py`

- 不导入 C/D/B 叶子模块。回放用调用方提供的版本化 gate registry：`{gate_id: {rules_version: callable(inputs) -> observed}}`。
- `replay_record(record, registry) -> ReplayResult`：只验证**本条**记录的哈希与回放一致性，不声称检测全链损坏。从 payload 取 `gate_id`、`rules_version`、`inputs`、`observed`；查 registry → 回调（传深拷贝 inputs）→ 用规范 JSON 比较回调返回值与记录的 `observed`。
- `replay_run(store, run_id, registry, trusted_head=None) -> list[ReplayResult]`：先 `verify_chain`，若给 trusted_head 再做 head 校验，均通过后逐一实际回放该 run 的 gate 记录。链或 head 不过则整体 review，不进入回放。
- 回放统一 payload 键为 `observed`；不使用 `recorded_observed`。
- 任一条下情形置 review：未知 gate 或 `rules_version`、缺 `gate_id`/`inputs`/`observed`、`payload.rules_version` 与记录 `rules_version` 不一致、回调返回值不可 JSON、回调异常、回调篡改输入（以传入深拷贝并核对输入的规范 JSON 是否被改）、规范 JSON 不一致。
- 非 gate 的叙述记录（无 `gate_id`）明示不纳入 gate 一致率分母。0 条 gate 回放不报成 100% 通过，而是分母为 0、状态如实标注。

`__init__.py` 导出：`AuditRecord`、`AuditStore`、`canonical_json`、`payload_ref`、`replay_record`、`replay_run`、`verify_against_trusted_head`、`AuditError`、结果类型。

### 7. 回放输入映射（边界契约）

C/D 已有独立实现分支（尚未合并 main）：C `a78d88cc3fd7ca4e877a677a95e9ada0caddaed5`、D `bd3a853ee332b72c46d86a62a39c457782e6ddcb`；B 仅有准备文档。E 不依赖它们安装，M2 不直接导入也不合并其代码，只做 JSON 形状兼容：

- C `to_dict` 形状：`accepted: bool`、`reason_code`、`status`、`action`、`rule_version`、`snapshot_id`、`instrument`、`is_noop`、`ignored_claims`。
- D `to_dict` 形状：`decision: "proceed"|"abstain"|"review"`、`insufficient_domains`、`labels`、`reason`、`violations`、`analysis_cutoff`。

E 只消费规范 JSON 形状，不 `import tradingagents.course.safety` / `data_quality` / `budget`。

M2 覆盖 E 全部功能，包括回放核心，用固定同形 fixture（手工构造符合上述形状的输入与期望 observed，registry 用本地确定性小函数）。这只证明形状兼容，不等同真实 C/D 跨模块运行。真实系统接入属 M3（协调 PR）。

### 8. 失败行为

| 场景 | 行为 |
|---|---|
| 覆盖终局（再次 append decision） | `AuditError(code=duplicate_decision)`，事务回滚 |
| SQL UPDATE/DELETE 历史行 | 触发器 `RAISE(ABORT)` |
| revision 引用非当前终局 / 跨 run / 事件 / 不存在 / null | `AuditError(code=invalid_supersede)` |
| 重复 record_id | `AuditError(code=duplicate_record_id)` |
| append 前链已损坏 | `AuditError(code=chain_broken)`，拒写 |
| 非法 JSON / 非 str key / NaN / inf | 写前 `AuditError(code=invalid_json/non_string_key/non_finite_number)`，不写库 |
| 非法 timestamp / 空 id | `AuditError(code=invalid_timestamp/empty_id)` |
| final_decision / project 时链损坏 | 拒绝返回，`AuditError(code=chain_broken)` |
| 回放未知版本 / 缺键 / rules_version 不一致 / 回调异常 / 结果不可 JSON / 篡改输入 / 不一致 | `ReplayResult.status=review`，不通过 |
| 外部 trusted_head 不相等 | `head_mismatch`，review 待人工确认（不自动判篡改） |
| final_decision 多叶子 | `AuditError(code=invariant_violation)` |

失败不静默降级，不自动修正输入。

### 9. 独立验收（保证各模块独立完成性）

独立证明的正式命令是在 `tradingagents/course` 目录下运行 `python -S -m audit --demo`：

- `-S` 不加载 site-packages，因此不依赖第三方包，也排除 pytest 等。
- 以 `audit` 为顶层包，`audit/__main__.py` 及其内部全部使用相对导入（`from .records import ...`、`from .store import ...`），不 import 顶层 `tradingagents` 包，因此不触发上游 `__init__.py` 的 python-dotenv/`load_dotenv`，不读 `.env`、不访问凭证。
- 不 import C/D/B 叶子模块与网络。

`__main__.py` 解析 `--demo` 后在临时数据库上依次演示：

1. 追加首条 decision。
2. 追加一条 rejection(outcome=review) 留痕。
3. 两次 revision，旧行保留。
4. 读取唯一终局。
5. 回放成功一次。
6. 回放不一致得到 review 一次。
7. 外部 head 核验（含合法追加后 head_mismatch 的情形）。

演示不写仓库内固定文件，用临时目录；退出码非 0 表示某步未达预期。

正常已安装环境下 `python -m tradingagents.course.audit --demo` 等同功能，但它会先加载顶层 `tradingagents`，继承 python-dotenv 依赖与 `.env` 加载行为，不作为独立证明。

`README.md` 记录模块用途、API 概要、两种运行方式（独立证明与已安装运行）的差异，以及上述步骤预期输出。

### 10. 实施步骤（M2，获批准后）

1. 建 `tradingagents/course/__init__.py` 与 `audit/__init__.py`。
2. `records.py`：`canonical_json`、`payload_ref`、`AuditRecord`、`AuditError` 及 code。
3. `store.py`：schema（表 + sequence + 索引 + UPDATE/DELETE 触发器）、`open` / `append` / `get` / `iter_run` / `project` / `final_decision` / `head` / `verify_chain`。
4. `replay.py`：`replay_record`、`replay_run`、`verify_against_trusted_head`。
5. `__main__.py` + `README.md`：独立演示；包内全部相对导入，`--demo` 支持 `python -S -m audit --demo`（cwd 在 `tradingagents/course`）。
6. `test/offline/test_audit.py`：按测试计划全部用例。
7. 运行并如实报告实际结果（本次不运行、不预设通过数）。

### 11. 风险与回滚

- 触发器可被外部工具绕过：§3.2/§3.4 已限定为应用层不可变 + 可检测篡改，并加 trusted_head。
- 尾截断内部链察觉不到：靠 trusted_head；前提是调用方真把 head 存库外。
- head_mismatch 不等于篡改：合法追加也会不相等，只置 review 交由人工确认。
- 并发在极端网络文件系统下行为可能不同：M2 用多连接测试覆盖首建决策与 revision 竞争；环境不支持则如实记录到 `docs/debt-register.md`，不放宽测试。
- 回滚：新增目录 + 单测试文件，删除即回滚，不触碰上游与基线。

### 12. 后续评审清单（M4 交 D，非作者）

- [ ] 链为单条全局链、按 sequence 排序，`verify_chain` 遍历全部记录而非只回溯当前头；能发现孤儿行与中间缺失。
- [ ] append 写前校验链；final_decision/project 返回前校验链，损坏即拒。
- [ ] 触发器 / 唯一索引 / `BEGIN IMMEDIATE` 覆盖覆盖终局、跨实例竞争、revision 竞争。
- [ ] append 只接受调用方字段，`payload_ref`/前驱/哈希由 store 生成，无法伪造前驱。
- [ ] `AuditRecord.to_dict()` 深拷贝，嵌套 payload 改动不影响内部。
- [ ] `superseded_by` 只从后继 revision 导出；旧行从不被写。
- [ ] revision 严格指向当前叶子，跨 run / 旧头 / 事件 / 缺失均拒。
- [ ] `replay_record` 只验本条；`replay_run` 先 verify_chain 再回放；payload 键统一 `observed`；rules_version 一致；回调传深拷贝并能发现篡改输入；0 条回放不报 100%。
- [ ] trusted_head 语义为“同一已封存快照的头相等”，不相等只 head_mismatch/review。
- [ ] 未导入 C/D/B 叶子；JSON 形状兼容。
- [ ] 独立演示在 `tradingagents/course` 目录 `python -S -m audit --demo` 可跑（不加载顶层 tradingagents、dotenv、.env、site-packages）；已安装方式仅等价功能，不作独立证明。
- [ ] 非法 JSON 与 timestamp 拒而不静默转换；中途回滚用真实 SQL 失败验证。
- [ ] 每 fail-closed 行为有负向测试；PROPOSED 未被写成 APPROVED，无虚假批准。

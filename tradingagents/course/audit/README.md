# E 模块：可验证审计（tradingagents.course.audit）

FR-005 / INV-005 / NFR-003 / NFR-004 / NFR-005 的实现。设计见
`docs/architecture/adr/003-append-only-audit.md`，计划见
`tasks/plans/E/FR-005-{implementation,test}-plan.md`。

这是一个独立叶子模块：只用 Python 标准库；运行时不导入 C/D/B 或其他课程叶子模块，也不访问网络。

## 能做什么

- 追加式审计记录：SQLite 单文件、单条全局哈希链，按自增 `sequence` 排序。
- 不可变：`BEFORE UPDATE` / `BEFORE DELETE` 触发器拒绝改删；应用层只有 append。
- 决策与修订：每个 run 至多一条首建决策；修订以 `supersedes` 指向当前终局叶子，旧行保留、可查询。
- 权威读：`final_decision` / `project` / `replay_run` 读取前先 `verify_chain`，链损坏则拒绝。
- 离线 gate 回放：调用方提供版本化 registry，回放**实际执行回调**并与记录的 `observed` 比较。
- 外部可信头：`head()` + `verify_against_trusted_head`，与已封存头相等才通过；不相等报告 `head_mismatch`（review），因为合法追加也会改变头。

局限：这是应用层不可变 + 可检测篡改，不是 WORM、不是签名。整段尾部截断或从某点整体重算哈希，仅靠内部链无法察觉，必须依赖外部 trusted_head，且该 head 需由调用方存到库外。

## 最小可运行示例

```python
from tradingagents.course.audit import AuditStore, replay_run

with AuditStore.open("audit.sqlite") as store:
    store.append(
        record_id="dec-1", run_id="run-1",
        timestamp="2026-11-14T17:00:00+08:00",
        entry_type="decision", payload={"action": "hold", "units": 0},
        rules_version="v1",
    )
    store.append(
        record_id="rev-1", run_id="run-1",
        timestamp="2026-11-14T17:01:00+08:00",
        entry_type="revision", payload={"action": "buy", "units": 10},
        rules_version="v1", supersedes="dec-1",
    )
    assert store.final_decision("run-1").record_id == "rev-1"
    assert store.verify_chain().ok
```

## 完整 E API

`AuditStore`

- `AuditStore.open(path, *, timeout=30.0) -> AuditStore`：打开/创建；可幂等重开；支持 `with` 与 `close()`。
- `store.append(*, record_id, run_id, timestamp, entry_type, payload, rules_version, supersedes=None) -> AuditRecord`：单事务 `BEGIN IMMEDIATE`；先校验既有链；`payload_ref`、前驱、哈希由 store 生成（调用方不能传）。失败整事务回滚。
- `store.get(record_id) -> AuditRecord | None`
- `store.iter_run(run_id) -> list[AuditRecord]`：按全局 sequence 顺序。
- `store.verified_records(run_id=None) -> list[AuditRecord]`：先全链校验，返回同一次已验证快照中的记录（`project`/`final_decision`/`replay_run` 均基于它，避免校验与读取快照分裂）。
- `store.project(run_id) -> dict`：先校验链；含每条的 `superseded_by`（由后继 revision 导出）与 `final_decision_id`。
- `store.final_decision(run_id) -> AuditRecord`：先校验链；返回唯一叶子。
- `store.head() -> {"record_id", "record_hash", "count"}`
- `store.verify_chain() -> VerificationResult`

`AuditRecord`（返回的不可变记录）

- 固定字段：`record_id`、`run_id`、`timestamp`、`entry_type`、`payload_ref`、`rules_version`、`previous_record_id`；另含 `payload`、`previous_hash`、`record_hash`、`supersedes`、`sequence`。
- `record.payload` 返回深拷贝；`record.to_dict()` 返回深拷贝，改返回值不影响记录内部。

`replay`

- `replay_record(record, registry) -> ReplayResult`：验本条 `record_hash` 与 `payload_ref`，并比较回放一致；非 gate 记录返回 `inconclusive`、`count=0`（不计入一致率分母）。
  - gate 意图判定：payload 含 `gate_id`/`inputs`/`observed` 任一字段即视为 gate；缺 `gate_id` 或任一必需字段判 `review`，不会被当成叙述记录排除出分母。
  - 若 payload 三个回放字段全缺（例如只有 action/outcome/note 的纯叙述），无法自动推断为 gate，按 `inconclusive` 处理——这是有意的限制，gate 记录必须带这些字段。
- `replay_run(store, run_id, registry, trusted_head=None) -> ReplayRunResult`：先 `verify_chain`、可选 trusted_head，再逐条实际回放；0 条 gate 记 `inconclusive`，不报 100%。
- `verify_against_trusted_head(store, trusted_head) -> VerificationResult`
- registry 形状：`{gate_id: {rules_version: callable(inputs) -> observed}}`。回调收到 inputs 的深拷贝；篡改输入、异常、不可 JSON 结果、未知版本、缺键、`rules_version` 不一致、结果不一致都判 `review`。

`records`

- `canonical_json(obj) -> bytes`：键排序、紧凑、`ensure_ascii=False`、拒绝非 str key / NaN / inf / tuple / 循环，不静默转换。
- `payload_ref(payload) -> str`：`sha256:<hex>`。
- `AuditError`：单一异常类型，带稳定 `code`（如 `duplicate_decision`、`invalid_supersede`、`chain_broken`、`non_string_key`）。

## 独立演示（正式独立证明）

在 `tradingagents/course` 目录运行：

```bash
cd tradingagents/course
python -S -m audit --demo
```

- `-S` 不加载 site-packages，证明不依赖第三方包。
- 以 `audit` 为顶层包、包内全部相对导入，不加载顶层 `tradingagents`，因此不触发上游 `python-dotenv`/`load_dotenv`，不读 `.env`、不访问凭证。
- 使用临时数据库；输出可读 JSON；退出码 0 表示所有预期的成功/失败场景都表现正确。

已安装环境下等价命令是 `python -m tradingagents.course.audit --demo`，但它会先加载顶层 `tradingagents` 并继承其 python-dotenv 依赖与环境加载行为，不作为独立证明。

演示覆盖：追加首条决策、review/abstain 留痕、两次 revision（旧版仍可查）、读取唯一终局、实际回调回放 pass、回放不一致 review、trusted head 匹配通过、合法追加后 head_mismatch review、整链校验通过。

## 运行测试

```bash
pytest -o testpaths=test/offline test/offline/test_audit.py
```

测试只用标准库与 pytest，不访问网络、不调真实 LLM、不连真实交易。

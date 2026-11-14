# Bug 日记

> 状态：**模板**。不含虚构历史条目。仅记录**真实观察到**的缺陷或可疑行为。
> 未经证实的差异必须标注“未证明为 bug”。

## 条目格式

```yaml
- id: BUG-000x
  title: <简短标题>
  observed_at: <YYYY-MM-DD>
  environment: <commit / 模型 / 配置>
  steps: <复现步骤>
  expected: <预期>
  actual: <实际>
  evidence: <日志/文件引用，脱敏>
  status: <open|confirmed|fixed|wontfix|needs-review>
  owner: <角色代码>
```

## 初始观察（引导阶段，来自真实基线运行）

```yaml
- id: BUG-001
  title: 未提供持仓时仍出现条件性仓位表述
  observed_at: "2026-11-06"
  environment: "上游 v0.7.1 @ 9fa1196；NVDA 2026-09-01；见 docs/baseline.md"
  steps: "运行一次分析且不传 portfolio"
  expected: "无持仓信息时，建议应面向读者自己的仓位，而非假设具体仓位"
  actual: "最终决策出现条件性 sizing 表述"
  evidence: "docs/baseline.md（脱敏数字）"
  status: needs-review
  owner: C
  note: "未证明为 bug；需人工判断是否为设计行为。"

- id: BUG-002
  title: 历史新闻/社交数据不可用 + FRED 无 key，导致缺失 feed 被计为 neutral（5 处）
  observed_at: "2026-11-06"
  environment: "上游 v0.7.1 @ 9fa1196；见 docs/baseline.md"
  steps: "无 FRED_API_KEY；运行日期早于当前"
  expected: "缺失应标 unavailable，而非 neutral"
  actual: "缺失 feed 被计为 neutral 5 处"
  evidence: "docs/baseline.md"
  status: needs-review
  owner: D
  note: "正是 FR-004/INV-004 要解决的问题；尚未实现。"

- id: BUG-003
  title: 成交量条件 150M vs 298.9M 差异
  observed_at: "2026-11-06"
  environment: "上游 v0.7.1 @ 9fa1196"
  steps: "观察决策中的成交量条件"
  expected: "待人工判断"
  actual: "使用 150M 条件而非 298.9M"
  evidence: "docs/baseline.md"
  status: needs-review
  owner: A
  note: "可能是有意决策，未证明为 bug；不得在报告中断言为缺陷。"
```

## 说明

- 不得虚构复现步骤或日志。
- `evidence` 只引用脱敏后的仓库内文件。

## E 模块真实缺陷（2026-11-14，FR-005）

> 以下均为 Codex 独立实际验证中发现、已修复的真实缺陷；每条附症状、复现、根因、修复与对应测试。

```yaml
- id: BUG-E-001
  title: 返回的 AuditRecord 属性可被赋值修改（并非不可变）
  observed_at: "2026-11-14"
  environment: "fe5805f 前的 E 早期实现；Codex 实际验证"
  steps: "取出 append 返回的记录后执行 rec.record_id = 'changed'"
  expected: "不可变记录应拒绝属性赋值/删除"
  actual: "普通属性赋值成功，记录被改"
  evidence: "test/offline/test_audit.py::test_p04b_record_is_immutable"
  status: fixed
  owner: E
  root_cause: "记录类未冻结，属性可写"
  fix: "改为 frozen dataclass(slots=True)，payload 内部保留规范 JSON 文本并返回新结构"
  invariant: "INV-005"

- id: BUG-E-002
  title: 数据库行 payload 被改成非法 JSON 时回放抛 JSONDecodeError 而非 review
  observed_at: "2026-11-14"
  environment: "fe5805f 前；Codex 实际验证"
  steps: "drop update 触发器后将某行 payload 改为 'broken-json'，再 replay_run"
  expected: "损坏数据回放应为 review，不逃逸异常"
  actual: "抛出 JSONDecodeError"
  evidence: "test/offline/test_audit.py::test_n19c_replay_malformed_json_record_review、test_n21b_malformed_json_payload_no_escape"
  status: fixed
  owner: E
  root_cause: "回放/读取路径未统一捕获 JSON 解析错误"
  fix: "replay_record 捕获预期 JSON/编码异常返回 review；verify_chain 识别 malformed_payload"
  invariant: "INV-005, NFR-003"

- id: BUG-E-003
  title: 缺 gate_id 的畸形 gate 记录被当成叙述记录排除出一致率分母
  observed_at: "2026-11-14"
  environment: "fe5805f 前；Codex 实际验证"
  steps: "已有合法 gate 记录后再 append payload={inputs:{},observed:{}}（漏 gate_id），replay_run 竟然 pass 且 gate_total=1"
  expected: "含回放字段但缺 gate_id 的记录应 review，且进入分母"
  actual: "被排除，整体误判 pass"
  evidence: "test/offline/test_audit.py::test_n15c_mixed_valid_and_missing_gateid_run_reviews"
  status: fixed
  owner: E
  root_cause: "gate 意图仅看 gate_id，未识别 inputs/observed"
  fix: "含 gate_id/inputs/observed 任一即视为 gate；缺必需字段 review"
  invariant: "FR-005, NFR-003"

- id: BUG-E-004
  title: 读取行时重算 payload_ref 掩盖了被篡改的引用
  observed_at: "2026-11-14"
  environment: "fe5805f 前；Codex 实际验证"
  steps: "SQL 篡改 payload_ref 后 get() 再 replay_record，竟 pass"
  expected: "读取应保留数据库原始 payload_ref，回放应判 payload_ref_mismatch"
  actual: "物化记录时用 payload 重算 ref，掩盖篡改"
  evidence: "test/offline/test_audit.py::test_n15d_payload_ref_mismatch_review"
  status: fixed
  owner: E
  root_cause: "读取路径复用追加时的 make_record 重算字段"
  fix: "读取直接用 dataclass 一一赋值保留持久化字段；追加才由 make_record 生成"
  invariant: "INV-005"

- id: BUG-E-005
  title: 测试损坏 fixture 被唯一索引提前拦住（测试构造问题，非业务漏洞）
  observed_at: "2026-11-14"
  environment: "首轮离线测试"
  steps: "test_n32 直接插入与既有 supersedes 冲突的损坏行"
  expected: "构造出用于验证语义的损坏态"
  actual: "UNIQUE constraint failed: audit_records.supersedes"
  evidence: "tasks/plans/E/evidence/first-offline-failure.txt"
  status: fixed
  owner: E
  root_cause: "测试构造未先移除唯一索引，属测试问题，非正常约束缺陷"
  fix: "测试显式 drop 该唯一索引后注入自洽哈希行以验证语义；真实运行唯一索引不变"
  invariant: "INV-005"
```

## 说明（E）


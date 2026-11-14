# E 评审须知（供 D 使用，非作者评审）

> 作者侧列出检查点与实际证据；独立评审人、日期、结论由 D 真实填写。本文件不含 APPROVE 结论。
> 评审记录另填 `docs/review-memo.md`。本地受测源码提交 `fe5805ffc4c16bd8e69379a70a8b93ca94746ec4`；GitHub 同内容代码快照 `94ba2e51d3117aad3b24027c378b74faa28c5815`（tree API 核验 12 份文件 blob SHA 与本地相同）。

## 范围

- 源码：`tradingagents/course/__init__.py`、`tradingagents/course/audit/{__init__,records,store,replay,__main__}.py`、`README.md`。
- 测试：`test/offline/test_audit.py`（60 项）。
- 计划/ADR：`tasks/plans/E/FR-005-{implementation,test}-plan.md`、`docs/architecture/adr/003-append-only-audit.md`（获批快照，不改）。

## 一、规格（spec）

- [ ] FR-005 四个要素是否都实现：记录不可变、终局唯一、supersede 链、离线 gate 回放。
- [ ] INV-005 是否可被负向测试证明：`n01`（覆盖终局被拒）、`n02/n03`（触发器）、`p07`（旧行保留/导出的 superseded_by）、`n32`（语义违规）。
- [ ] NFR-003 确定性：`p08`（两次一致）、`n27`（不一致 review）；NFR-004 留痕：`p03/p10`；NFR-005：`n29/n30`。
- [ ] `review` 仅以 `rejection + payload.outcome="review"` 表达，未私设第五种 entry_type。

## 二、架构（architecture）

- [ ] ADR-003 与实现是否一致（全局单链、sequence 排序、payload 同行、触发器、唯一索引）。
- [ ] 手写边界注释/docstring 是否引用 ADR/INV/FR 锚点；公开函数语义是否与计划一致。
- [ ] `verify_chain` 是否遍历全部记录而非只看当前头；`project`/`final_decision`/`replay_run` 是否基于同一 `verified_records` 快照。
- [ ] 修订语义是否用 per-run `current_terminal` 推进，禁跨 run/旧头/事件/缺失/自指/未来。

## 三、代码 + 测试（code + tests）

- [ ] `AuditRecord` 是否真不可变（frozen+slots）：`p04b` 覆盖属性赋值/删除与嵌套 payload 改动。
- [ ] 读取物化是否保留数据库原始 `payload_ref`/`record_hash` 而非重算掩盖篡改：`n15d`（payload_ref 篡改 → `payload_ref_mismatch`）。
- [ ] 非法 JSON 回放是否 review 不逃逸：`n19c`、`n21b`；`canonical_json` 对 surrogate/超深是否统一 `invalid_json`：`n12c/n12d`。
- [ ] gate 意图判定：含 `gate_id`/`inputs`/`observed` 任一即 gate；缺 `gate_id` 判 review（`n15c` 混合 run `gate_total=2`）；纯叙述 inconclusive（`n15b`）。
- [ ] 回调输入深拷贝与篡改检测（`n18`）、回调异常/非法结果/版本不一致 review（`n16/n19/n14/n17`）。
- [ ] 并发：`n05/n06` 用 `ThreadPoolExecutor` + 每线程独立连接 + barrier，真并发；若无环境证据，请如实标注。
- [ ] 事务中途回滚用真实 SQL 失败（`n10` 用受控 `BEFORE INSERT` 触发器），非写前非法 payload 冒充。
- [ ] 威胁态 fixture（`n20..n23`、`n26`、`n32`）是否显式标注为测试构造、不改正常约束；`n32` 是否显式 drop 唯一索引后注入自洽哈希行以测语义。

## 四、运行（operational）

- [ ] 独立 demo 只标准库：`cd tradingagents/course && python -S -m audit --demo` exit 0，`all_expected=true`。
- [ ] 复现命令（通用）：`pytest -o testpaths=test/offline test/offline`、`pytest`、`ruff check .`。
- [ ] 证据与 `tasks/plans/E/evidence/validation-facts.json` 一致；无编造数字。

## 五、安全与效率（贯穿）

- [ ] fail-closed：链损坏时写入拒写、权威读拒绝、回放整体 review（`n24/n25/n28`）。
- [ ] 可信头语义只判相等/`head_mismatch`，不误判合法追加为篡改（`p11/n26c`）。
- [ ] 明确非签名、非 WORM，尾截断需外部 trusted_head（`README.md`、`FR-005-validation.md`）。
- [ ] 性能：全链 O(n) 扫描、连续追加 O(n²)，已如实记录为限制（`FR-005-validation.md`、`docs/debt-register.md`）。

## 作者侧已记录的实际证据（供核对，非评审结论）

- 离线 80 passed（`offline-final.txt`）；上游 1412 passed/1 skipped/1 deselected/100 subtests（`upstream-final.txt`）；ruff passed（`ruff-final.txt`）；C/D/E 临时组合 156 passed（只说明合到一起后各自测试仍通过，非真实接口联调，`cde-compatibility.txt`）；独立 demo exit 0（`standalone-demo.json`）。

---

- 独立评审人：**待 D 填写**
- 评审日期：**待 D 填写**
- 结论：**待 D 填写（本文件不作结论）**

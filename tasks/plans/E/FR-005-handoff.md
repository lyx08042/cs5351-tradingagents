# E → D 交接：F5 可验证审计（FR-005）

E 独立模块已完成；待 D 评审和主流程接入。

- 作者：OpenCode 1.18.29（模型 `cityu/CS5351/DeepSeek-V4-Flash`，会话 `ses_e26a98708ffehPgZu8n5f9GKTo`）生成代码/测试/文档。
- 执行者：Codex 编排，并独立实际运行离线测试、上游回归、ruff 与独立 demo。
- 评审人（非作者）：D（M4，当前未评审）。
- 本地受测源码提交：`fe5805ffc4c16bd8e69379a70a8b93ca94746ec4`（基线 `7dc46516935755d5a09ba3507ccd55dbadda066b`）。此提交未通过 `git push` 发布（当时无凭证，改用网页逐文件提交），因此不是一个可在 GitHub 上解析的 review commit。
- GitHub 同内容代码快照：`94ba2e51d3117aad3b24027c378b74faa28c5815`。Codex 用 GitHub tree API 逐一核验已发布的 12 份源码/测试/获批计划文件，blob SHA 与本地完全相同——remote tree/blob 逐一相同即为验证证据。
- 实现前批准：受审（本地）commit `bebfe912185bb1c5f735d6dae7acc79acaff4fb9`，批准记录（本地）commit `85d4fc7`，文件 `tasks/plans/E/FR-005-pre-code-approval.md`。这是本聊天用户的真实批准决定；不改动原批准记录中的真实本地 plan commit。
- 分支 `feat/E-audit` 已在远端创建；PR 尚未创建，最终以 GitHub 为准。

## 职责与局限

- OpenCode 生成计划、ADR、源码、测试、过程文档；本轮无 shell 权限，命令由 Codex 实际执行。
- 局限：应用层不可变 + 可检测篡改，非签名、非 WORM；尾截断需外部 trusted_head；`verify_chain` 每次全链 O(n)，连续追加总 O(n²)，面向小规模审计。
- M2 用固定同形 fixture 验证回放字段参照 C/D 输出结构，**未**用真实 C/D 回调做主流程联调；真实系统接入属 M3。

## 1) 需求 + fits

来源 `docs/req/requirements.yaml`（状态仍为 `proposed`，实现不自动转 `approved`）。

| ID | statement（摘要） | fit | 对应实际测试 |
|---|---|---|---|
| FR-005 | 最终决策可验证审计：记录不可变、终局唯一、修订以 supersede 链保存、支持离线 gate 回放 | 回放一致率 = 1.0；verification = 覆盖终局被拒 + 回放一致性 | `test_p01..p13`、`test_n01..n32`（见 §3 文件） |
| INV-005 | 审计不可变；终局决策唯一；修订以 supersede 链保存，旧版可回放 | 回放不一致数 = 0 | `test_n01`、`test_p07`、`test_n20..n28`、`test_n32` |
| NFR-003 | 确定性：相同输入与规则版本下回放可重现 | 重复回放一致率 = 1.0 | `test_p08`、`test_n27` |
| NFR-004 | 任何 rejection/abstain/review 事件留可检索记录 | 留痕比例 = 1.0 | `test_p03`、`test_p10` |
| NFR-005 | 叶子模块无循环导入，契约变更需 ADR | 循环导入数 = 0 | `test_n29`（AST）、`test_n30`（独立 demo） |

## 2) 设计 / 接口 / ADR / INV

- ADR：`docs/architecture/adr/003-append-only-audit.md`（PROPOSED，获批快照，未改）。
- 存储：SQLite 单文件、单条全局链（按自增 `sequence` 排序）、`BEGIN IMMEDIATE` 事务、`BEFORE UPDATE/DELETE` 触发器拒改删、单决策/单 supersedes 唯一索引。
- 记录：`AuditRecord` 为 `frozen dataclass(slots=True)`；`payload` 内部存规范 JSON 文本，`payload`/`to_dict()` 返回新结构；`payload_ref = sha256(canonical(payload))`；`record_hash = sha256(canonical(除 record_hash 外全部持久化字段))`，`sequence` 不入哈希、仅用于链序。
- 追加：`AuditStore.append(*, record_id, run_id, timestamp, entry_type, payload, rules_version, supersedes=None) -> AuditRecord`。调用方不传 `payload_ref`/前驱/哈希，全部由 store 在事务内生成；写前先校验既有链，损坏拒写；失败整事务回滚。
- 读：`get` / `iter_run` / `verified_records` / `project` / `final_decision` / `head` / `verify_chain`。`project`/`final_decision`/`replay_run` 均基于同一次 `verified_records` 快照，链损坏即失败。
- 回放：`replay_record(record, registry)` 验本条 `record_hash` 与 `payload_ref` 并比较回放；`replay_run(store, run_id, registry, trusted_head=None)` 先全链/可选 head 再逐条实际执行回调。registry 形状 `{gate_id: {rules_version: callable(inputs) -> observed}}`；回调收 inputs 深拷贝。
- 决策/修订：每 run 至多一条首建 decision；revision 的 `supersedes` 必须指向当前叶子终局，禁跨 run/旧头/事件/缺失/自指/未来；`superseded_by` 读取时由后继 revision 导出；`final_decision` 返唯一叶子。
- 失败语义：全部 fail-closed；`AuditError(code, message)` 单一异常类型；权威读在链损坏时统一 `chain_broken`（`invariant_violation` 保留自身 code，原因在 message/context）。
- INV 锚点：INV-005（不可变、终局唯一、supersede 链、可回放）；NFR-003/004/005 见上。

## 3) 代码 + 测试 + 计划记录

- 源码（新增）：`tradingagents/course/__init__.py`、`tradingagents/course/audit/{__init__,records,store,replay,__main__}.py`、`README.md`。
- 测试（新增）：`test/offline/test_audit.py`（60 项 E 测试）。
- 计划/测试设计：`tasks/plans/E/FR-005-implementation-plan.md`、`FR-005-test-plan.md`（获批快照，未改）。
- 批准记录：`tasks/plans/E/FR-005-pre-code-approval.md`。
- PR：尚未创建（不以本文件虚构编号）。

## 4) 实际评估 / 配置 / 结果

证据目录 `tasks/plans/E/evidence/`，来源 `validation-facts.json`。

| 项 | 结果 | 证据文件 |
|---|---|---|
| 离线全套 | 80 passed（E 60 + 脚手架 20），0.53s | `offline-final.txt` |
| 上游回归 | 1412 passed, 1 skipped, 1 deselected, 100 subtests passed, 24 warnings, 8.46s | `upstream-final.txt` |
| ruff 全仓 | All checks passed | `ruff-final.txt` |
| C/D/E 临时组合 | 156 passed，0.52s | `cde-compatibility.txt` |
| 独立 demo | `python -S -m audit --demo`（cwd `tradingagents/course`）exit 0，`all_expected=true` | `standalone-demo.json` |

- C/D/E 临时组合：把 C（`a78d88c…`）、D（`bd3a853…`）、E 的源码与离线测试临时合在一起跑，156 passed 只说明组合后各自测试仍通过。它**不**等于证明 JSON 形状兼容，更不是真实接口联调；E 的 M2 fixture 字段只是参照 C/D 输出结构，尚未用真实 C/D 回调做主流程联调。
- 环境：Python 3.12；命令用通用 `python`/`pytest`，不写依赖个人绝对路径的复制命令。
- 运行时应用未发起任何真实 LLM/交易调用（`runtime_api_calls=false`）；未修改其他模块（`other_modules_modified=false`）。
- 独立人评审：pending D。

## 5) 完整原始会话 + 独立干预注释

- 原始记录文件：`transcripts/role-E/raw.json`（交付时由 Codex 从 OpenCode 原样导出产生，当前尚未导出）。
- 注释：`transcripts/role-E/annotations.md`。
- 不得包含凭证/个人信息；身份待学生本人补入。

## 6) AI 使用 / 评审 / bug / 债务 / 变更记录

- AI 使用：`docs/ai-use-log.yaml` 追加 `AI-USE-E-20261114`。
- 评审：`docs/review-memo.md`（D 真实填写；当前未评审）。评审清单见 `tasks/plans/E/FR-005-review-notes.md`。
- bug：`docs/bug-diary.md` 追加 E 真实缺陷（a/b/c/d）。
- 债务：`docs/debt-register.md` 追加 E 剩余项。
- 验证报告：`tasks/plans/E/FR-005-validation.md`；报告素材：`FR-005-report-notes.md`。

## 7) 报告贡献 + 反思 + 贡献证据 + 演示材料

- 报告章节素材：`tasks/plans/E/FR-005-report-notes.md`（客观段落 + ~90 秒 demo 提纲；非最终 Report、非个人反思）。
- 个人反思：**未提供、未代写**（学生本人撰写）。
- 演示材料：`standalone-demo.json` 与 `FR-005-report-notes.md` 中的 demo 提纲；**视频未录制**，不声称已完成。
- 姓名/学号与贡献证据：身份未知，不编造；可验证证据为源码 commit、测试与证据文件。

## 里程碑状态

- M1 计划 + ADR：完成（获批）。
- M2 独立模块 + 离线测试 + 交接 + 真实记录：完成（本地受测源码提交 `fe5805f`；GitHub 同内容代码快照 `94ba2e5`）。
- M3 主流程接入（真实入口）：待协调 PR，本轮未做。
- M4 D 非作者评审 + 评估记录：待 D 完成。

## 复现命令（通用，不依赖个人路径）

```bash
# 独立 demo（仅标准库、不加载顶层 tradingagents/dotenv/site-packages）
cd tradingagents/course && python -S -m audit --demo && cd -

# E 离线测试
pytest -o testpaths=test/offline test/offline/test_audit.py

# 全离线（E + 脚手架）
pytest -o testpaths=test/offline test/offline

# 上游回归基线
pytest

# 全仓风格
ruff check .
```

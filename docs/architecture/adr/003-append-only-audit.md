# ADR-003：追加式审计存储、决策修订链与离线 gate 回放（E / F5）

- 状态：PROPOSED（待人工批准；尚未实现）
- 日期：2026-11-14（Asia/Hong_Kong）
- 作者：OpenCode（经 Codex 编排编写；学生身份未提供，未填姓名/学号）
- 关联需求：FR-005、INV-005、NFR-003、NFR-004、NFR-005
- 关联文档：`tasks/E-audit.md`、`architecture-blueprint.md`、`docs/architecture/adr/001-course-extension.md`、`docs/architecture/invariants.md`、`docs/code-governance/structural-constraints.md`
- 关联计划：`tasks/plans/E/FR-005-implementation-plan.md`、`tasks/plans/E/FR-005-test-plan.md`

本 ADR 记录设计决策与取舍，不代表已实施，也不被批准。E 本次自愿采用实现前批准停点：本 ADR 与两份计划需 owner 批准后才进入 M2。这不修改全组政策，也不构成批准记录。

## 1. 背景

F5 要求最终决策可验证审计：记录不可变、终局决策唯一且具权威性、修订以 supersede 链保存且旧版可回放，并支持离线 gate 回放。约束：只用标准库；叶子模块不导入 C/D/B；无网络；确定性回放（NFR-003）。

C/D 已有独立实现分支（未合并 main）：C `a78d88cc3fd7ca4e877a677a95e9ada0caddaed5`、D `bd3a853ee332b72c46d86a62a39c457782e6ddcb`；B 仅准备文档。E 不依赖它们安装，M2 不直接导入或合并其代码，仅做 JSON 形状兼容。

## 2. 决策

### 2.1 存储：SQLite 单文件，单行同存 payload，事务式追加

- 每记录一行；`payload` 规范 JSON 化后与元数据同行存储；另存 `payload_ref = sha256(canonical(payload))`。
- 追加在 `BEGIN IMMEDIATE` 内完成“读当前头 → 计算 record_hash → 校验 → INSERT”。
- `journal_mode=WAL`；建表/索引/触发器用 `IF NOT EXISTS`，可幂等重开。

### 2.2 不可变：触发器 + 只追加 API

- `BEFORE UPDATE` / `BEFORE DELETE` 触发器 `RAISE(ABORT)`；公共 API 无 update/delete。

### 2.3 全局链：单条链，按 sequence 排序

- 整个数据库一条链，表内自增 `sequence` 定链序；不按 run 分链。`run_id` 只用于筛选。
- root 的 `previous_record_id`、`previous_hash` 为 null。
- `record_hash = sha256(canonical(固定字段 + payload + supersedes + previous_record_id + previous_hash))`。
- `verify_chain` 遍历全部记录：从 root 起前驱连续、逐行 record_hash 重算、payload_ref 一致、决策/修订语义合法。能发现孤儿行、中间缺失、重排、字段改、payload 换。
- append 写前校验链，损坏拒写；final_decision/project 返回前校验链，损坏拒绝。
- 内部链无法察觉整段尾部截断或整体重算哈希，靠 trusted_head。

### 2.4 外部 trusted_head

- `head()` 给 `(record_id, record_hash, count)`，调用方存库外。
- `verify_against_trusted_head` 检查“当前头与已封存 head 完全相等”。不相等不等于篡改：合法追加也会不相等。因此只输出 `head_mismatch` 并置 review，交人工确认。
- 合法追加后需可信方另存新 checkpoint；库当前值不自动当可信值。

### 2.5 显式时间与 id

- `timestamp` 调用方传带时区 ISO-8601；`record_id` 调用方显式传入；库不读时钟、不生成随机 id。

### 2.6 AuditRecord 与 append 契约

- 读取/返回的 `AuditRecord` 不可变，7 个 task 字段 + `payload`/`previous_hash`/`record_hash`/`supersedes`；`to_dict()` 深拷贝，嵌套 payload 改动不影响内部。
- `entry_type ∈ {decision, rejection, abstain, revision}`；review 用 `rejection + payload.outcome="review"`，不单列第五类。
- `append(*, record_id, run_id, timestamp, entry_type, payload, rules_version, supersedes=None) -> AuditRecord`；调用方不传 `payload_ref`/`previous_record_id`/`previous_hash`/`record_hash`，由 store 在事务内生成，防止伪造前驱。
- 错误从简：一个 `AuditError` 带稳定 `code`（如 duplicate_decision、invalid_supersede、duplicate_record_id、chain_broken、invalid_json 等），不铺开大量子类。

### 2.7 决策与修订规则

- 每 run 只能首建一次 decision（部分唯一索引 + 事务内检查）。
- revision 的 `supersedes` 必须是当前叶子终局；禁止跨 run、旧头、事件、缺失、null。
- 旧行不改；`superseded_by` 读取时从后继 revision 导出；`final_decision` 返唯一叶子，多叶子 fail-closed。

### 2.8 回放

- 回放用调用方版本化 gate registry，不导入 C/D/B。
- `replay_record(record, registry)` 只验证本条哈希与回放一致性，不声称检测全链。
- `replay_run(store, run_id, registry, trusted_head=None)` 先 verify_chain、可选 head，再逐一实际执行回调回放。
- payload 统一键 `observed`；`payload.rules_version` 须与记录一致；未知版本/缺键/不可 JSON 结果/回调篡改输入/异常/不一致均 review；回调传深拷贝。
- 非 gate 叙述记录明示不纳入 gate 一致率分母；0 条回放不报 100%。

### 2.9 独立完成性

E 只用标准库；`__main__.py` 的 `--demo` 支持两种方式。独立证明用 `python -S -m audit --demo`，cwd 在 `tradingagents/course`：`audit` 作顶层包，包内全部相对导入，不 import 顶层 `tradingagents`，因此不加载上游 `__init__.py` 的 python-dotenv/`load_dotenv`，不读 `.env`、不访问凭证；`-S` 不加载 site-packages，排除第三方包。已安装环境用 `python -m tradingagents.course.audit --demo` 等同功能，但继承上游 dotenv 依赖与环境加载，不作独立证明。演示覆盖追加决策、review 留痕、两次修订、读取唯一终局、回放成功与不一致、外部 head 核验；不 import pytest/其他叶子/网络。M2 覆盖 E 全部功能（含回放核心）；真实系统接入属 M3。不改上游 `tradingagents/__init__.py`。

## 3. 备选方案

| 方案 | 优点 | 缺点 | 结论 |
|---|---|---|---|
| A. SQLite 追加 + 触发器 + 全局链哈希 + trusted_head（本 ADR） | 标准库、离线、可测、可检测改/删/重排/截断 | 非密码学防篡改；依赖调用方存 head | 采纳（PROPOSED） |
| B. 纯追加 JSONL + 链 | 简单 | 无事务并发控制，终局唯一难保证 | 拒绝 |
| C. 每记录非对称签名 | 强完整性 | 引入密钥与依赖，超课程需要且涉凭证 | 拒绝（可未来扩展） |
| D. 仅内存 | 最简单 | 不满足持久化不可变/可审计/可回放 | 拒绝 |

## 4. 理由

- 标准库 SQLite 事务足以保证首建决策唯一与 revision 竞争一致，无需外部服务。
- 触发器拒改删，链哈希检测被绕过后的篡改与重排，trusted_head 补内部链无法察觉的尾截断。
- 显式时间/id + 规范 JSON 保证确定性回放（NFR-003）。
- 回调式 registry 让 E 不依赖未合并的 C/D/B，满足 NFR-005。

## 5. 后果与限制

- 应用层不可变 + 可检测篡改，不是 WORM、不是签名，也不假设拥有文件的管理员无法修改。拥有文件权限者可关触发器改行；链哈希可检测许多篡改，但整段尾部截断或整体重算哈希仅靠内部链查不出，须依赖外部 trusted_head，且只在调用方真把 head 存库外并用于校验时有效。
- head_mismatch 可能来自合法追加，须人工确认。
- 每次追加与校验有序列化/哈希开销，审计低频可接受。
- 并发依赖 SQLite 文件锁与 WAL；极端网络文件系统行为可能不同，作为已知限制。
- 新增字段是对 task 7 字段的扩展，实现时须同步 trace/文档（本 ADR 不声称已完成）。

## 6. 重开条件

1. 需要密码学签名/WORM/外部不可变存储。
2. 改变 entry_type 语义或 review 表达。
3. 契约字段变更影响跨模块或 BASE-001/002。
4. 并发一致性在实际环境无法保证。
5. M3 真实集成暴露映射边界不足。

## 7. 批准记录

- 批准人：待人工填写（不得虚构）
- 批准日期：待填
- 关联 commit：待填

本节被真实人工填写前，本 ADR 保持 PROPOSED。

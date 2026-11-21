## Test Plan: FR-005（E 模块 · 离线审计 + 修订链 + gate 回放）

- 作者：OpenCode（经 Codex 编排编写；学生身份未提供，未填姓名/学号）
- 评审人（非作者）：待 owner 批准本文件时指派（预期 D，见实现计划 §12）
- 关联实现计划：`tasks/plans/E/FR-005-implementation-plan.md`
- 关联 ADR：`docs/architecture/adr/003-append-only-audit.md`（PROPOSED）
- 日期：2026-11-14（Asia/Hong_Kong）
- 状态：`awaiting owner approval`（M1 测试设计；不产生已实现/已通过结论）

### 范围

- 功能：FR-005（不可变审计、终局唯一、supersede 链、离线 gate 回放）。
- 不变量：INV-005。
- 非功能：NFR-003（确定性回放）、NFR-004（拒绝/abstain/review 留痕）、NFR-005（叶子无循环导入）。
- 测试文件：`test/offline/test_audit.py`（唯一新增测试文件）。
- 被测：`tradingagents/course/audit/`（含 `__main__.py`、`README.md`）及必要时 `tradingagents/course/__init__.py`。
- 全部测试独立、固定输入、不走网络、不调真实 LLM、不连真实交易；用 `tmp_path` 各自建库。

### 测试原则

- 每个测试自带 fixture，不依赖顺序，不共享可变全局状态。
- 固定 `record_id`、带时区 `timestamp`、固定 payload；哈希断言用相等/不等或 `sha256:` 前缀，不硬绑易漂移的完整值。
- 不预设通过数；实现后按实际 pytest 计数如实报告。
- 每个 fail-closed 行为至少一个负向测试。
- 多连接竞争若在环境不稳定，作为已知限制记录到 `docs/debt-register.md`，不删除、不放宽、不 mock 掉真实行为。

### 正向测试

| 用例ID | 用例 | 输入 | 预期 |
|---|---|---|---|
| P-01 | 追加首条 decision | `Append`(record_id="d-001", run_id="r-1", entry_type="decision", 带时区 ts, 合法 payload) | 返回 `AuditRecord`；store 生成 `payload_ref`/`previous_record_id=null`/`previous_hash=null`/`record_hash`；`get("d-001")` 一致 |
| P-02 | 关闭重开仍可读、触发器仍生效 | 先 append 若干条，close，再 `AuditStore.open` 同路径 | 计数与记录不变；`iter_run` 顺序一致；UPDATE/DELETE 仍被拒 |
| P-03 | 事件检索与 review 语义 | append decision + rejection(payload.outcome="review") + abstain | 各条可按 run_id 检索；review 以 rejection+outcome 保留 |
| P-04 | to_dict 深拷贝隔离 | 读取一次 `to_dict()` 后修改返回值的嵌套 payload | 记录内部与再次 `to_dict()` 不变 |
| P-05 | 字段与 entry_type 校验 | 合法追加一条 decision | 返回记录含 7 个 task 字段 + payload/previous_hash/record_hash/supersedes；entry_type 在四值内 |
| P-06 | 合法 revision | 已有终局 d-001，append revision d-002，supersedes="d-001" | 成功 |
| P-07 | 修订链保留旧行 | 承接 P-06 | d-001 仍在且不变；`project("r-1")` 中 d-001.superseded_by == "d-002"；`final_decision("r-1")` == d-002 |
| P-08 | 相同输入回放确定 | payload 存 gate g1@v1 固定 inputs 与 observed；registry 回调对相同 inputs 返回相同 observed | `replay_record` 两次都 pass，跨两次运行一致（NFR-003） |
| P-09 | trusted_head 匹配 | 保存 `head()` 后未改库，用相同 trusted_head 校验 | 通过 |
| P-10 | 首建决策后普通事件留痕 | decision 后 append rejection/abstain | 入库可检索（NFR-004），终局不变 |
| P-11 | 合法追加后 head_mismatch 非篡改 | 保存 head 后合法 append 一条，再用旧 trusted_head 校验 | 返回 head_mismatch → review，待人工确认；不标为链破损 |
| P-12 | 全局链跨 run 连续 | r-1 与 r-2 交错 append 多条 | `verify_chain` 通过；sequence 顺序的 `previous_record_id` 连续；iter_run 各 run 只筛自己的记录 |
| P-13 | 独立演示入口（正式独立证明） | 子进程运行 `python -S -m audit --demo`，cwd 固定 `tradingagents/course`，临时库 | 退出码 0；演示追加决策、review 留痕、两次修订、读取终局、回放成功与不一致 review、外部 head 核验均按预期；`-S` 下无 site-packages 也能跑 |

### 负向测试

| 用例ID | 用例 | 输入 | 预期 |
|---|---|---|---|
| N-01 | 覆盖终局决策 | 已有 decision d-001，再 append decision 同 run_id | `AuditError(code=duplicate_decision)`；仍只有一条 decision |
| N-02 | SQL DELETE 历史行 | 直接 DELETE | 触发器 ABORT；记录仍在 |
| N-03 | SQL UPDATE 历史行 | 直接 UPDATE | 触发器 ABORT；内容不变 |
| N-04 | 重复 record_id | 两次 append 相同 record_id | `AuditError(code=duplicate_record_id)`；第二条不入库 |
| N-05 | 首建决策竞争（多连接） | 两连接并发对空 run_id 首建 decision | 一个成功，另一个冲突错误；该 run 恰一条 decision |
| N-06 | revision 竞争（多连接） | 已有终局，两连接 append revision 指向同一 supersedes | 至多一个成功；另一个因 supersedes 不再是叶子被拒；无两条共存叶子 |
| N-07 | 跨 run 修订 | revision supersedes 指向另一 run 终局 | `AuditError(code=invalid_supersede)` |
| N-08 | 旧头修订 | revision supersedes 指向已被取代的旧头 | `invalid_supersede` |
| N-09 | 事件/缺失/null 修订 | supersedes 指向 rejection/abstain、不存在 id、或 null | 均 `invalid_supersede` |
| N-10 | 真正中途回滚 | 构造一条 append 使事务内 INSERT 被触发器拒绝（或等价真实 SQL 失败），使失败发生在事务内而非写前校验 | 整事务回滚；库计数不变、无部分行 |
| N-11 | 非法 JSON：非字符串 key | payload 含 int key | 写前 `AuditError(code=non_string_key)`；不写库；不静默转 str |
| N-12 | 非法 JSON：NaN / inf | payload 含 nan / inf | 写前 `AuditError(code=non_finite_number)`；不写库 |
| N-13 | 非法 timestamp / 空 id | 无时区、坏格式、空 record_id | `AuditError(code=invalid_timestamp/empty_id)` |
| N-14 | 未知版本回放 | gate g1@v9 不在 registry | `replay_record` → review |
| N-15 | 缺键回放 | payload 缺 inputs 或 observed 或 gate_id | review |
| N-16 | 回调异常回放 | 回调抛异常 | review，不冒泡成通过 |
| N-17 | rules_version 不一致 | payload.rules_version 与记录 rules_version 不同 | review |
| N-18 | 回调篡改输入 | 回调修改传入 inputs | 回放能发现输入被改 → review |
| N-19 | 回调结果不可 JSON | 回调返回不可 JSON 的对象 | review |
| N-20 | 篡改 payload | 绕过 API 直接改行内 payload 文本 | `verify_chain` 检出（payload_ref / record_hash 不符） |
| N-21 | 篡改链哈希 | 改某行 record_hash 或 previous_hash | `verify_chain` 报破损并指位置 |
| N-22 | 缺中间行 | 受控构造删掉一条中间记录（绕过触发器） | `verify_chain` 检出前驱不连续 |
| N-23 | 孤儿行 | 受控构造插入一条不接链的记录 | `verify_chain` 检出，不只回溯当前头而漏掉 |
| N-24 | 链损坏时拒写 | 先构造损坏态，再 append | append 返回 `AuditError(code=chain_broken)`，不写 |
| N-25 | 链损坏时 final_decision/project 拒绝 | 损坏态下调用 | 拒绝返回，`chain_broken`，不给看似有效终局 |
| N-26 | trusted_head 尾截断 | 保存 head 后构造删除尾部、内部自洽的库 | `verify_against_trusted_head` → head_mismatch / review |
| N-27 | 不一致回放 | registry 回调返回与记录 observed 不同 | review（重新执行比较，非拷贝自比） |
| N-28 | replay_run 链前置 | 损坏库上 `replay_run` | 整体 review，不进入逐条回放 |
| N-29 | 叶子无互相导入（AST） | 用 `ast` 扫描 `tradingagents/course/audit/` 全部 .py | 不 import evidence/budget/safety/data_quality；E 各文件依赖仅标准库与自身 |
| N-30 | 缺其他模块/无第三方也能跑 | 子进程 `python -S -m audit --demo`，cwd=`tradingagents/course` | 成功；`-S` 排除 site-packages、不加载顶层 tradingagents/dotenv、不读 .env，证明不依赖 C/D/B 安装与第三方包 |

> N-10 的要点：非法 payload 属 WRITE 前拒绝，不能用来证明事务中途回滚；必须让失败发生在事务内（INSERT 被触发器或约束拒绝）。N-22/N-23/N-26 用受控手段构造损坏态，测试内注明这是为验证检测逻辑而构造，不代表运行时允许。

### 需求→测试映射

| 需求 | 用例 |
|---|---|
| FR-005 | P-01..P-13, N-01..N-03, N-07..N-30 |
| INV-005 | N-01、P-07、N-20..N-25 |
| NFR-003 | P-08、N-27 |
| NFR-004 | P-03、P-10 |
| NFR-005 | N-29、N-30 |

### 回放 fixture 说明

C/D 已有独立实现分支（未合并 main）：C `a78d88cc3fd7ca4e877a677a95e9ada0caddaed5`、D `bd3a853ee332b72c46d86a62a39c457782e6ddcb`；B 仅准备文档。E 不依赖它们安装，M2 不直接导入或合并其代码。回放测试用固定同形 fixture（手工构造符合 C/D `to_dict` 形状的 inputs 与 observed，registry 用本地确定性小函数），只证明形状兼容，不是真实跨模块运行；真实系统接入属 M3。回放测试不导入 safety/data_quality/budget。

### 独立运行说明（与 P-13 / N-30 对应）

上游 `tradingagents/__init__.py` 会 import python-dotenv 并可能自动 load `.env`，所以不从仓库根 `python -m tradingagents.course.audit` 承诺“纯标准库/不读环境文件”。独立证明用子进程 `python -S -m audit --demo`，cwd 固定 `tradingagents/course`，`audit` 作顶层包、包内相对导入，不触发顶层 `tradingagents`；`-S` 不加载 site-packages。`python -m tradingagents.course.audit --demo` 仅作已安装环境的等价功能，继承上游 dotenv/环境加载，不作独立证明。不改上游 `__init__.py`。

### 回归

- [ ] 不修改 `tests/` 与既有 `test/offline/test_course_scaffold.py`。
- [ ] 新增测试不走网络、不调真实 LLM、不连真实交易。
- [ ] 后续真实运行命令：`pytest -o testpaths=test/offline test/offline/test_audit.py`；全 `test/offline`；上游 `pytest`；`ruff check .`（全仓）。本次不运行、不预设通过数，真实结果后填。

### 判定标准（requirements.yaml fit）

- FR-005：审计回放一致率 = 1.0（覆盖终局被拒 + 回放一致性）。
- INV-005：回放不一致数 = 0。
- NFR-003：重复回放一致率 = 1.0。
- NFR-004：拒绝/abstain 事件留痕比例 = 1.0。
- NFR-005：检测到的循环导入数 = 0。

阈值为 registry 的 `proposed` 目标；本文件只描述如何验证，不宣称达成。

### 给 D 的评审提示（M4）

- 看每个负向用例是否断言具体 code/review 状态，而非宽泛 Exception。
- 看多连接竞争是否真并发、是否可能 flaky；flaky 应如实记录不跳过。
- 看 verify_chain 是否遍历全部记录（含孤儿/缺失），final_decision/project 是否先校验。
- 看 trusted_head 是否只输出 head_mismatch/review，不误判合法追加为篡改。
- 看 M2 是否真用 fixture 且诚实标注非真实 C/D 集成。

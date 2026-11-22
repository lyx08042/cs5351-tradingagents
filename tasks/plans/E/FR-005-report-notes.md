# E 报告素材：F5 可验证审计（供整合进全组 Report）

> 这是客观素材，不是最终 Report，不是学生个人反思，不冒充学生第一人称，也不声称视频已录制。
> 数据来自 `tasks/plans/E/evidence/`（本地受测源码提交 `fe5805ffc4c16bd8e69379a70a8b93ca94746ec4`；GitHub 同内容代码快照 `94ba2e51d3117aad3b24027c378b74faa28c5815`）。

## 设计（客观）

E 模块在 `tradingagents/course/audit/` 提供一个只用标准库的追加式审计：
SQLite 单文件、单条全局哈希链（按自增 `sequence` 排序）。写入在 `BEGIN IMMEDIATE`
事务内完成“读当前头 → 生成链哈希 → 校验 → 插入”，`BEFORE UPDATE`/`BEFORE DELETE`
触发器拒绝改删，单决策与单 supersedes 唯一索引配合事务保证“终局唯一”。记录在内存中
是冻结值对象，`payload` 以规范 JSON 文本保存，读取返回新结构，外部改动不影响记录。
决策修订以 revision 指向当前叶子终局、旧行不改、`superseded_by` 由后继 revision 读取时
导出；`final_decision` 返回唯一叶子，出现多个叶子时 fail-closed。回放用调用方提供的
版本化 gate registry，重新执行回调并比较规范 JSON，失败一律 review，不以空分母冒充 100%。

## 实现要点

- `AuditStore.append(*, record_id, run_id, timestamp, entry_type, payload, rules_version, supersedes=None)`：
  调用方不传 `payload_ref`/前驱/哈希，全部由 store 在事务内生成，防止伪造前驱；写前先校验既有链。
- `verify_chain` 遍历全部记录（连续 sequence、逐行字段校验、payload 解析、`payload_ref`、`record_hash`、
  前驱连续、每 run 的 current_terminal 语义），能发现篡改、缺中间行、孤儿行。
- 读取 `project`/`final_decision` 与回放 `replay_run` 都基于同一次 `verified_records` 快照，链损坏即拒绝。
- `verify_against_trusted_head` 与已封存头比对，不相等只报 `head_mismatch` 交人工，不误判为篡改。

## 测试（客观数值）

- E 离线测试 60 项，脚手架 20 项，合计 80 passed（`offline-final.txt`）。
- 上游回归 1412 passed、1 skipped、1 deselected、100 subtests，未改上游测试（`upstream-final.txt`）。
- ruff 全仓 All checks passed（`ruff-final.txt`）。
- C/D/E 临时组合 156 passed，只说明三者源码+离线测试合到一起后各自测试仍通过，不是形状兼容证明、不是真实接口联调（`cde-compatibility.txt`）。
- 独立 demo `python -S -m audit --demo` exit 0，`all_expected=true`（`standalone-demo.json`）。
- 多轮修复中，两个阶段的失败输出保存在 `first-offline-failure.txt`、`second-offline-failure.txt`，其余过程见完整会话。

## 局限

- 应用层不可变 + 可检测篡改，不是签名、不是 WORM；整段尾截断或整体重算哈希需外部 trusted_head 才能察觉。
- 每次 `verify_chain` O(n) 全链扫描，连续追加总成本 O(n²)，面向小规模审计。
- 回放 fixture 为固定同形结构，不是真实交易/真实 LLM 评估；主流程真实接入（M3）与 D 非作者评审（M4）待办。

## ~90 秒 demo 讲解提纲

1.（10s）目的：F5 要“最终决策可验证、可修订、可回放”，且失败一律 review。
2.（20s）运行 `cd tradingagents/course && python -S -m audit --demo`，说明 `-S` 不加载 site-packages、不触发上游 dotenv。
3.（20s）看输出里追加决策、review 留痕、两次 revision 后旧版仍可查、唯一终局 rev-2。
4.（20s）看回放：`replay_record` 与实际回调一致判 pass，observed 被人为写错判 review；0 gate 报 inconclusive。
5.（15s）看可信头：头相等 pass；合法追加后旧头报 head_mismatch（review，非篡改判定）。
6.（5s）收尾：链校验通过，退出码 0；说明这是小规模、标准库、可独立运行的实现，接入主流程与 D 评审仍待办。

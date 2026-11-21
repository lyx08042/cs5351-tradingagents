# 评审备忘：D → E（PR #2）

## 基本信息

- PR / commit：PR #2 `feat(E): add append-only audit, decision revisions and offline replay`；head commit `8c8112cead569c3461703c993965544557673974`，基线 `main` `7dc46516935755d5a09ba3507ccd55dbadda066b`，被审分支 `feat/E-audit`
- 作者：`lyx08042`（Owner）
- 评审人（非作者）：Chaoqun ZHENG，学号 `60569580`，角色 D
- 评审日期：2026-11-21
- 关联需求 ID：`FR-005`、`INV-005`、`NFR-003`、`NFR-004`、`NFR-005`

评审依据：核对 PR 变更文件、源码、离线测试、计划/ADR、证据输出与仓库记录；在独立评审沙箱（Python 3.12.11，pytest 9.2.0，ruff 0.17.6）复跑 E 离线测试、脚手架测试、独立 demo 与 Ruff。上游回归与 C/D/E 临时组合结果引自 E 分支 evidence，本轮评审沙箱未独立复跑这两类套件（缺上游可选依赖）。Checks 8 项通过。

## 检查清单

| 项 | 状态（pass / fail / n/a） | 说明 |
|---|---|---|
| 测试计划已批准（`docs/approvals/`） | pass | `FR-005-pre-code-approval.md` 记录 owner 对实现计划、测试计划和 ADR 的批准答复；该记录不是教师批准，也不是独立代码评审。 |
| 实现计划已批准 | pass | 同上，批准范围为 E 独立模块、配套离线测试、独立演示及过程材料。 |
| 安全变更 ADR（如适用） | pass | `ADR-003` 记录追加式审计、全局哈希链、触发器、唯一索引和回放边界；ADR 状态仍为 `PROPOSED`，不等同教师批准。 |
| 至少一个负向测试 | pass | `test/offline/test_audit.py` 含 `n01` 至 `n32`，覆盖终局覆盖、改删拒绝、并发竞争、非法 JSON、篡改链、缺行、孤儿行、回放不一致等负向场景。 |
| 未削弱既有测试 | pass（证据引自 E） | 上游回归结果引自 E evidence `upstream-final.txt`：1412 passed，1 skipped，1 deselected，100 subtests passed；本轮评审沙箱因缺上游可选依赖未独立复跑 `tests/`。变更文件列表未显示修改上游 `tests/`。 |
| 未修改 `tests/` | pass | 新增测试为 `test/offline/test_audit.py`；上游测试和依赖未在 E 分支中改动。 |
| 叶子模块无循环导入 | pass | `test_n29` 用 AST 扫描确认 audit 不导入 evidence / budget / safety / data_quality；`test_n30` 以 `-S` 禁用 site-packages 方式启动独立 demo，返回码 0 且无 Traceback。 |
| 缺失语义 = unavailable/neutral 区分 | n/a | E 负责审计留痕与回放，不负责 D 的数据充分性判定；E 不把缺失或不可用消息改写成中性决策。 |
| fail-closed 行为验证 | pass | 链损坏时拒绝追加、权威读拒绝、回放整体 review；非法 JSON、回调异常、输入篡改、未知版本和结果不一致均进入 review。 |
| ai-use-log 已更新 | pass | `AI-USE-E-20261114` 记录会话标识、范围、测试结果、已知限制和未完成事项。 |
| 文档状态标注真实 | pass | 文档明确标注 M3 主流程接入、D 非作者评审、生产联调和真实评估尚未完成；未声称整组合规或已自动合并。 |

## 发现

- **优点**：
  1. 审计边界清楚：追加式存储、链哈希、触发器拒绝改删、权威读先验链，fail-closed 语义一致。
  2. 负向测试覆盖较完整，覆盖篡改、并发、非法 JSON、畸形 gate、坏链和 trusted head 不匹配。
  3. 证据和限制记录较完整：性能上限、非签名/非 WORM、尾截断依赖外部 trusted_head、M3 未接入等均已登记。
  4. 真实缺陷修复、技术债、工具使用日志和会话材料均有对应文件，便于追溯。
- **问题（非阻断）**：
  1. 主流程接入未完成：E 目前是独立叶子模块，尚未在真实运行路径中接收 B/C/D 的事件，属于 M3 协调 PR 范围。
  2. 性能规模有限：`verify_chain` 每次 O(n) 全链扫描，连续追加总成本 O(n²)，面向课程规模和小规模审计场景。
  3. 安全模型有限：当前是应用层不可变 + 可检测篡改，不是密码学签名，也不是数据库 WORM；整段尾截断或整体重算哈希需要库外保存 trusted_head。
  4. E 的回放 fixture 为参照 C/D 输出结构构造的固定 JSON，尚未接入真实 D 回调；D 侧字段如何进入 E 的 `payload` 待 M3 联调确认。已审阅代码中未发现 E 擅自修改 D 决策或绕过 D 准入结论的路径。
- **建议**：归档 transcript 时按 `transcripts/README.md` 约定的 `<studentid-name>/` 目录命名（当前为 `transcripts/role-E/`）；其余非阻断项随 M3 协调 PR 跟进。

## 结论

**APPROVE（限定 E 独立叶子模块与已声明范围）**

在已审阅的代码、测试、计划、ADR 和提交证据范围内，未发现需要阻断该范围通过的可复现代码缺陷：`FR-005` / `INV-005` / `NFR-003` / `NFR-004` / `NFR-005` 的核心能力有对应实现和正负向测试。本轮评审沙箱独立复跑 E 离线测试（60 passed）、脚手架测试（20 passed）、独立 demo（exit 0，`all_expected=true`）与 Ruff（All checks passed），结果均通过；上游回归与 C/D/E 临时组合结果引自 E 分支 evidence，本轮未独立复跑；失败路径保持 fail-closed。

本结论仅覆盖 E 独立叶子模块与已声明范围；PR 当前为 Draft、尚未合并；不代表主流程接入通过、真实接口兼容已证明、全项目验收完成或自动合并。

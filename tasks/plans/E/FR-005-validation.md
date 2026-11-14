# E 可追溯验证报告：FR-005 可验证审计（2026-11-14）

> 所有数字与结论均来自 `tasks/plans/E/evidence/` 与其中的 `validation-facts.json`。
> 执行者：Codex 独立实际运行命令；OpenCode（1.18.29，`cityu/CS5351/DeepSeek-V4-Flash`，
> 会话 `ses_e26a98708ffehPgZu8n5f9GKTo`）生成代码/测试/文档，在本会话无 shell 权限。
> 本地受测源码提交：`fe5805ffc4c16bd8e69379a70a8b93ca94746ec4`（未 `git push` 发布，非可在 GitHub 解析的 review commit）。
> GitHub 同内容代码快照：`94ba2e51d3117aad3b24027c378b74faa28c5815`；Codex 用 GitHub tree API 逐一核验已发布的 12 份源码/测试/获批计划文件，blob SHA 与本地完全相同，作为“发布内容一致”的验证证据。

## 1. 环境

- Python 3.12；通用 `python` / `pytest` 命令，不写依赖个人绝对路径的复制命令。
- 离线：不访问网络、不调用真实 LLM、不连接真实交易。
- 运行时应用真实调用：`runtime_api_calls=false`；其他模块修改：`other_modules_modified=false`。

## 2. 三层验证

| 层 | 内容 | 结果 | 证据 |
|---|---|---|---|
| 结构层 | AST 扫描 E 源码不跨叶子导入、不依赖第三方（`test_n29`）；独立 demo 无 site-packages 可跑（`test_n30`） | 通过 | `offline-final.txt` |
| 回归层 | 上游 `tests/` 基线 | 1412 passed, 1 skipped, 1 deselected, 100 subtests passed, 24 warnings, 8.46s | `upstream-final.txt` |
| 行为层 | E 正/负向 60 项 + 脚手架 20 项 | 80 passed, 0.53s | `offline-final.txt` |

## 3. 关键结果与来源

| 项 | 数值 | 来源 |
|---|---|---|
| 离线全套 | 80 passed（E 60、脚手架 20） | `offline-final.txt` |
| 上游回归 | 1412 passed / 1 skipped / 1 deselected / 100 subtests | `upstream-final.txt` |
| ruff 全仓 | All checks passed | `ruff-final.txt` |
| C/D/E 临时组合 | 156 passed（把三者源码与离线测试临时合在一起跑；只说明组合后各自测试仍通过） | `cde-compatibility.txt` |
| 独立 demo | `python -S -m audit --demo` exit 0，`all_expected=true` | `standalone-demo.json` |
| 真实失败记录 1 | `test_n32` 的损坏 fixture 被 `ux_audit_single_supersede` 唯一索引提前拦住 → IntegrityError | `first-offline-failure.txt` |
| 真实失败记录 2 | `test_n21b` 期望 `chain_broken` 得到 `malformed_payload`；`test_n22` 得到 `sequence_broken` | `second-offline-failure.txt` |

## 4. 需求逐项覆盖

- FR-005（审计不可变/终局唯一/supersede 链/离线回放）：`p01..p13`、`n01..n32`。
- INV-005：
  - 不可变：`p04`、`p04b`（属性赋值/删除与嵌套 payload）、`n02`、`n03`（触发器拒改删）。
  - 终局唯一：`n01`（覆盖被拒）、`p07`（链保留）、`n32`（语义违规）。
  - 链完整性：`n20`（payload 篡改）、`n21`（哈希篡改）、`n22`（缺中间行）、`n23`（孤儿行）、`n24`（损坏拒写）、`n25`（权威读拒绝）。
  - 可回放：`p08`、`n27`。
- NFR-003（确定性回放）：`p08`（两次回放一致）、`n27`（不一致 review）、`n19b/n19c`（非法结果/非法 JSON review）、`n31`（0 gate 不报 100%）。
- NFR-004（留痕）：`p03`（decision+rejection(review)+abstain 可检索）、`p10`（事件后留痕不改终局）。
- NFR-005（无循环导入 + 契约 ADR）：`n29`（AST 无跨叶子依赖）、`n30`（无第三方独立运行）。

## 5. 隔离与独立性证明

- 导入隔离：`test_n29` 用 `ast` 扫描 `tradingagents/course/audit/*.py`，确认不 `import` evidence/budget/safety/data_quality；`replay.py` 仅依赖标准库与 `records`/`store`。
- site-packages 隔离：`test_n30` 以子进程 `python -S -m audit --demo`（cwd `tradingagents/course`）运行成功，`-S` 不加载 site-packages，不加载顶层 `tradingagents`，因而不触发其 python-dotenv/`load_dotenv`，不读 `.env`、不访问凭证。
- 独立 demo 覆盖全部 E 功能：追加决策、review/abstain 留痕、两次 revision（旧版可查）、读取唯一终局、实际回调回放 pass、回放不一致 review、trusted head 匹配与合法追加后 head_mismatch，见 `standalone-demo.json` 的 11 个 check 全部 `ok:true`。
- C/D/E 组合只说明三者源码+离线测试合到一起后各自测试仍通过，**不**等于证明 JSON 形状兼容，更不是真实接口联调；E 的 M2 fixture 字段只是参照 C/D 输出结构，尚未用真实 C/D 回调做主流程联调。E 不依赖 A/B/C/D 安装。

## 6. 正负例与局限

- 正例：`p01`–`p13`。
- 负例：`n01`–`n32`（覆盖覆盖终局、并发竞争、非法 JSON/时间、回放各类失败、链篡改、可信头、导入隔离等）。
- 可信头局限：`verify_against_trusted_head` 只检查“当前头与已封存 head 完全相等”；不相等输出 `head_mismatch`（review），不代表被篡改（合法追加也会不相等）；需可信方在库外保存 checkpoint（`p09`、`p11`、`n26`、`n26c`）。
- 内部链局限：整段尾部截断或整体重算哈希仅靠内部链无法察觉，需外部 trusted_head（非签名、非 WORM）。
- 性能局限：`verify_chain` 每次 O(n) 全链扫描；连续追加总成本 O(n²)。适合小规模审计，不作为高频/大吞吐场景优化。
- fixture 说明：回放用固定同形 JSON 结构（手工构造符合 C/D `to_dict` 形状），不是运行真实交易或真实 LLM 评估。

## 7. 课程门禁状态（如实）

- 本轮 E 有真实实现前批准记录（`tasks/plans/E/FR-005-pre-code-approval.md`，受审 `bebfe91…`，记录 `85d4fc7`）。
- 但全项目六道 gate **并未**因本轮满足；D 非作者评审仍待办；不得声称课程合规或 G-1/D9 全项目达成。
- 共享 CI 尚未自动运行 E 测试（见 `docs/debt-register.md`）。

## 8. 复现命令（通用）

```bash
cd tradingagents/course && python -S -m audit --demo && cd -
pytest -o testpaths=test/offline test/offline/test_audit.py
pytest -o testpaths=test/offline test/offline
pytest
ruff check .
```

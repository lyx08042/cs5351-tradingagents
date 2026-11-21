# FR-001 离线验证证据

基线为 `7dc4651`，分支为 `feat/A-evidence`。Codex 用 Python 3.13.13 运行验证。OpenCode 编写 ADR、业务源码和测试。应用验证未调用真实模型或行情接口。

## M2 边界补修验收（run2）

沿用 OpenCode 会话 `ses_e07c64cd8ffejosyU60JfsMFsC` 修复时间和新鲜度、预测分类、无结构化事实的弃权原因、引用审计，以及注册与回放边界。OpenCode 完成写入后，Codex 重导出原会话，更新角色 A 的 AI 使用摘要，再顺序执行验收。原记录现在包含 86 条消息。[会话注释与 SHA-256](../../../../transcripts/role-A/annotations.md)

独立边界探针从[补修前 4/19 通过](m2-run2-00-before-fix.txt)提升至[补修后 19/19 通过](m2-run2-09-boundary-probe.txt)。[首次专项预检](m2-run2-00-claim-preflight.txt)的 1 项失败由保留断言 ID `unknown` 引起。OpenCode 更换了测试 ID，保留了分类和预期拒绝原因。

| 命令 | 退出码 | 原始结果 |
|---|---:|---|
| `.venv/bin/python -m pytest -o testpaths=test/offline test/offline/test_evidence.py -q` | 0 | [43 通过，0 跳过](m2-run2-01-feature.txt) |
| `.venv/bin/python -m pytest -o testpaths=test/offline test/offline -q` | 0 | [63 通过，0 跳过](m2-run2-02-offline.txt) |
| `.venv/bin/python -m pytest -q` | 0 | [1412 通过、1 跳过、1 未选中，100 个子测试通过](m2-run2-03-upstream.txt) |
| `.venv/bin/python -m ruff check .` | 0 | [通过](m2-run2-04-ruff.txt) |
| `.venv/bin/python scripts/check_course.py --root .` | 0 | [通过](m2-run2-05-course-checker.txt) |
| `git diff --check` | 0 | [无输出](m2-run2-06a-diff-check.txt) |
| `git status --short` | 0 | [工作区状态](m2-run2-06b-status.txt) |
| `.venv/bin/python -m tradingagents.course.evidence --demo` | 0 | [EVAL-006、008、009 原始输出](m2-run2-08-offline-demo.txt) |

验收在仅允许本机回环的沙箱中运行，禁用 dotenv 自动加载。上游跳过项仍为可选的 `langchain_aws`。保存了[命令顺序和退出码](m2-run2-results.json)，并核对了[当前文件 SHA-256 与变更范围](m2-final-scope.txt)。所有 `m2-run1-*` 文件均按原 SHA-256 核对为未变。

## 环境预检

| 输出 | 执行 | 退出码 | 结果 |
|---|---|---:|---|
| [默认沙箱](00-upstream-preflight-default-sandbox.txt) | `.venv/bin/python -m pytest -q` | 1 | 1405 通过、7 失败、1 跳过、1 未选中。7 个失败均发生在模拟登录测试绑定本机回环地址时，原始错误为 `PermissionError`。 |
| [仅允许回环](00-upstream-preflight-loopback.txt) | 同一命令，本机回环可用，外部网络仍被禁止 | 0 | 1412 通过、1 跳过、1 未选中，另有 100 个子测试通过。与上游历史基线一致。跳过项需要可选的 `langchain_aws`。 |

仅需默认沙箱无法绑定本机端口时，可在 macOS 使用下列约束执行回归。配置禁止外部网络，允许测试的本机 HTTP 回环。

```bash
/usr/bin/sandbox-exec -p '(version 1) (allow default) (deny network*) (allow network-bind (local ip "localhost:*")) (allow network-inbound (local ip "localhost:*")) (allow network-outbound (remote ip "localhost:*"))' .venv/bin/python -m pytest -q
```

## 复现顺序

从仓库根目录使用已有 `.venv`，按[测试计划](../FR-001-test-plan.md)顺序执行。记录每条命令、退出码和原始输出。离线演示运行 `.venv/bin/python -m tradingagents.course.evidence --demo`。

## 实现期间的检查

- [首轮定向测试](00-feature-preflight.txt)退出码 0，23 项通过。[Ruff 首轮](00-feature-ruff-preflight.txt)退出码 1，报告 `Fact` 的 `SIM102`。更早的[契约扫描](00-contracts-ruff-preflight.txt)及[模块扫描](00-module-ruff-preflight.txt)出现同一错误。
- [修复前离线演示](00-demo-preflight.txt)退出码 0，覆盖三个固定案例。
- 审查时发现序列化投影的嵌套可变值会被调用者改写，并确认两条带明确未来时间的预测会被误判。[首个探针](00-projection-and-forecast-review.txt)记录了可变值问题和探针本身的类型错误，[修正的探针](00-projection-and-forecast-repro.txt)复现了全部三项行为并退出 1。
- [构造器探针](00-constructor-bypass-repro.txt)退出 1，记录了直接构造可跳过冲突隔离，以及不合法的 verdict ID 可进入 JSON 投影。Codex 将发现交回同一 OpenCode 会话，最终结果以完整验收记录为准。

## M1–M2 首轮验收（run1 历史记录）

以下均在 OpenCode 最后一次源文件写入后由 Codex 顺序运行。执行环境只允许本机回环，显式禁用 dotenv 自动加载。逐条退出码记录在 [m2-run1-results.json](m2-run1-results.json)。

| 命令 | 退出码 | 结果 |
|---|---:|---|
| `.venv/bin/python -m pytest -o testpaths=test/offline test/offline/test_evidence.py -q` | 0 | [26 通过，0 跳过](m2-run1-01-feature.txt) |
| `.venv/bin/python -m pytest -o testpaths=test/offline test/offline -q` | 0 | [46 通过，0 跳过](m2-run1-02-offline.txt) |
| `.venv/bin/python -m pytest -q` | 0 | [1412 通过、1 跳过、1 未选中，100 个子测试通过](m2-run1-03-upstream.txt) |
| `.venv/bin/python -m ruff check .` | 0 | [All checks passed](m2-run1-04-ruff.txt) |
| `.venv/bin/python scripts/check_course.py --root .` | 0 | [课程脚手架检查通过](m2-run1-05-course-checker.txt) |
| `git diff --check` | 0 | [无输出](m2-run1-06a-diff-check.txt) |
| `git status --short` | 0 | [验收时的工作区状态](m2-run1-06b-status.txt) |
| `.venv/bin/python -m tradingagents.course.evidence --demo` | 0 | [固定场景原始输出](m2-run1-08-offline-demo.txt) |

EVAL-008 接纳可溯源的历史事实，EVAL-009 拒绝未来证据，EVAL-006 将预测标为假设。46 项离线测试含上述 26 项新测试和原有 20 项脚手架测试。结构测试检查依赖、系统时钟和随机数、Python 3.11 语法、包标记与公开 docstring。上游跳过项来自可选的 `langchain_aws`，与预检一致。

OpenCode 原始会话、SHA 和独立注释见[会话注释](../../../../transcripts/role-A/annotations.md)。最终工作区和保护路径检查见 [m2-final-scope.txt](m2-final-scope.txt)。本轮验收覆盖独立模块。主流程 M3、B 的评审、E 的非作者评审、在线语义评估和学生个人材料留在范围之外。

## M3 辩论集成验收

分支为 `feat/A-M3-debate-integration`，起点为 `faf4065`。OpenCode 在隔离副本中先写 ADR-006，再写适配器、图集成和测试。Codex 核查写入记录，将最终文件按原字节同步到分支。编码使用线上 `se-profile/deepseek-flash`。下列 TradingAgents 测试使用脚本化响应，在 macOS 仅允许本机回环的沙箱中运行，清空继承环境，禁用 dotenv 自动加载和 LangSmith tracing。环境为 Python 3.13.13。没有调用真实运行时模型或行情接口。[M3 会话与 SHA-256](../../../../transcripts/role-A/m3-annotations.md)

| 命令 | 退出码 | 原始结果 |
|---|---:|---|
| `.venv/bin/python -m pytest -o testpaths=test/offline test/offline/test_evidence_integration.py -q` | 0 | [5 通过](m3-run1-01-integration.txt) |
| `.venv/bin/python -m pytest -o testpaths=test/offline test/offline/test_evidence.py -q` | 0 | [43 通过](m3-run1-02-m2.txt) |
| `.venv/bin/python -m pytest -o testpaths=test/offline test/offline -q` | 0 | [68 通过](m3-run1-03-offline.txt) |
| `.venv/bin/python -m pytest -q` | 0 | [1412 通过、1 跳过、1 未选中，100 个子测试通过](m3-run1-04-upstream.txt) |
| `.venv/bin/python -m ruff check .` | 0 | [通过](m3-run1-05-ruff.txt) |
| `.venv/bin/python scripts/check_course.py --root .` | 0 | [通过](m3-run1-06-course-checker.txt) |
| `git diff --check` | 0 | [无输出](m3-run1-07a-diff-check.txt) |
| `git status --short` | 0 | [工作区状态](m3-run1-07b-status.txt) |
| `git status --short --untracked-files=all` | 0 | [完整文件清单](m3-run1-07c-status-all.txt) |

[命令顺序和退出码](m3-run1-results.json)记录在 OpenCode 最后一次写入后的正式验收。上游通过数、跳过数、未选中数及子测试通过数与 M2 run2 相同。A10–A13 涵盖两轮正反辩论、实际 Research Manager 提示词、拒绝原文隔离、D 准入拒绝及节点兜底、严格 JSON 记录和默认路径兼容。隔离副本的[首次专项预检](m3-preflight-integration1.txt)有 4 项失败，暴露了末轮响应、假设标签、严格 JSON 和证据夹具 run ID 问题。修正后另用[独立边界探针](m3-boundary.txt)验证无模型的拒绝路径。

[范围与哈希清单](m3-final-scope.txt)记录白名单核对，以及用本地 B/CDE 引用执行的只读三方预览。两次 `trading_graph.py` 预览均无文本冲突。CDE 与 M3 都在 `AgentState` 末尾追加字段，这一处预览报文本冲突，留待共用基线协调。本轮保留了 M1–M2 历史和原 A 分支。既有 B 评审草稿不计入 M3 变更。

**A14 PENDING**。本地结果覆盖与 D 准入、E JSON 的契约形状。待 #3/#4/#5 和 M3 落在同一基线后执行全员联调。E 非作者评审与在线语义评估仍待进行。

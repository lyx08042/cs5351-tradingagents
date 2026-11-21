# Pull Request

> 草稿，待成员核对。建议标题为 `feat(evidence): add standalone FR-001 evidence module`，建议分支为 `feat/A-evidence → main`，本地基线为 `7dc4651`。PR 编号、贡献提交与 CI 均为 **PENDING / 待成员发布后确认**。本草稿中的检查状态以实际证据为准。

## 关联需求

- Req IDs：`FR-001`、`INV-001`、`NFR-002`（关联质量目标，待评估）、`NFR-005`（结构约束与 ADR）。
- 类型：`feature`。

## 批准（实现前必须具备）

- 本节标题沿用模板。团队开发遵循现行 `DEVELOPMENT-POLICY.md`。测试和实现计划为工作记录，实现前审批流程按该政策停用。**课程 G-1/D9 未满足**，属于团队记录的课程偏离。没有教师 waiver，没有伪造批准，也不声称课程合规。
- 测试计划：`tasks/plans/A/FR-001-test-plan.md`，本地工作记录，无实现前批准。
- 实现计划：`tasks/plans/A/FR-001-implementation-plan.md`，本地工作记录，无实现前批准。
- ADR：`docs/architecture/adr/005-evidence-grounded-debate.md`，状态 **PROPOSED**，记录证据日期、断言分类、引用审计与回放契约。
- 批准记录位置：`docs/approvals/` 为历史批准记录位置。本 PR 无新增引用。最终非作者评审、分支 CI 与合并授权 **PENDING**。

## 变更范围

- 仅覆盖角色 A 的 M1–M2 独立模块。新增包标记 `tradingagents/course/__init__.py` 和 `tradingagents/course/evidence/`，提供可信证据索引、时间与新鲜度校验、事实绑定与预测分类、拒绝引用审计、JSON 回放和离线演示。
- 新增 `test/offline/test_evidence.py`，记录 ADR-005、实现/测试计划与验收证据。交付记录包括 `tasks/plans/A/`、`transcripts/role-A/` 与 `docs/ai-use-log.yaml` 的角色 A 条目。交接草稿为 `tasks/plans/A/FR-001-handoff.md`。
- 既有业务源码、`cli/**`、上游 `tests/**`、既有 `test/**` 脚手架、`pyproject.toml` 与 `LICENSE` 未改，A 的专项测试为新增文件。既有 `tradingagents/agents/**`、`tradingagents/graph/**`、其他课程叶子模块及共享课程编排器均未改。
- 受保护的 `.github/**`、`scripts/**`、`AGENTS.md`、`Prompt.md`、`opencode.json`、`.opencode/**` 与 `docs/approvals/**` 未改。未调整评估集、运行时模型或提示词。本地补修和验收制品不覆盖历史日志。
- **M3 主流程图接入 PENDING**，留待 M3 协调 PR。此变更没有把证据模块接入现有 LangGraph、研究员节点或 CLI。

## 证据

验证依据为 `tasks/plans/A/evidence/m2-run2-results.json`、同目录原始输出及 `m2-final-scope.txt`。在仓库根目录使用已有 `.venv`。run2 使用 Python 3.13.13，禁用 dotenv 自动加载，macOS 沙箱仅允许本机回环供模拟登录测试使用。以下是同序复现命令。

```bash
env -i PATH="$PATH" HOME="$HOME" TMPDIR="${TMPDIR:-/tmp}" LANG=en_US.UTF-8 TZ=Asia/Shanghai \
  PYTHON_DOTENV_DISABLED=1 LANGSMITH_TRACING=false \
  /usr/bin/sandbox-exec -p '(version 1) (allow default) (deny network*) (allow network-bind (local ip "localhost:*")) (allow network-inbound (local ip "localhost:*")) (allow network-outbound (remote ip "localhost:*"))' \
  /bin/sh -eu <<'SH'
.venv/bin/python -m pytest -o testpaths=test/offline test/offline/test_evidence.py -q
.venv/bin/python -m pytest -o testpaths=test/offline test/offline -q
.venv/bin/python -m pytest -q
.venv/bin/python -m ruff check .
.venv/bin/python scripts/check_course.py --root .
git diff --check
git status --short
git status --short --untracked-files=all
.venv/bin/python -m tradingagents.course.evidence --demo
SH
```

| run2 检查 | 退出码 | 实际结果 | 原始输出（相对 `tasks/plans/A/evidence/`） |
|---|---:|---|---|
| A 专项 | 0 | 43 通过，0 跳过 | `m2-run2-01-feature.txt` |
| 全部离线 | 0 | 63 通过，0 跳过 | `m2-run2-02-offline.txt` |
| 上游回归 | 0 | 1,412 通过、1 跳过、1 未选中，100 个子测试通过。跳过项为可选的 `langchain_aws`。 | `m2-run2-03-upstream.txt` |
| Ruff | 0 | All checks passed | `m2-run2-04-ruff.txt` |
| 课程脚手架、需求 schema/trace | 0 | 通过 | `m2-run2-05-course-checker.txt` |
| Git 差异与状态 | 0 | `git diff --check` 无诊断。状态列出预期的本地新文件和角色 A 日志变更。 | `m2-run2-06a-diff-check.txt`、`m2-run2-06b-status.txt`、`m2-run2-07-changed-paths.txt` |
| 离线演示 | 0 | EVAL-006 `hypothesis`、EVAL-008 `accept_factual`、EVAL-009 `reject`（`future_leakage`） | `m2-run2-08-offline-demo.txt` |

- 正向测试：可信 `EvidenceUnit`/映射均可注册。合格历史来源与匹配结构化事实可支持断言，英文过去式不会单因方向动词被判为预测。混合引用保留有效支持及无效引用审计。
- 负向测试：缺引用、无匹配证据和显式事实缺结构时弃权。未来发布日期、可用日期或事实周期拒绝，发布日期倒挂和陈旧重抓拒绝。带有效引用的中英文预测仍标为假设。非法批次、冲突/不匹配引用和带空白的回放隔离 ID 均有覆盖。序列化测试覆盖拒绝原因、顺序和纯 JSON。
- 评估：固定集为 `docs/evaluation/cases.yaml` @ `7dc4651`。以上三个案例为本地确定性检查。独立边界探针从 **4/19** 通过提升为 **19/19**，补修前、预检失败和补修后的输出均有保留。在线语义评估与 `NFR-002` 相对基线质量差值 **PENDING**。

## AI 使用

- `docs/ai-use-log.yaml` 已更新，条目为 `AI-USE-A-FR001-M1-M2`。OpenCode 编写业务源码、测试和 ADR，Codex 负责复现、离线验收和证据归档。当次没有运行时模型或行情请求。
- `transcripts/role-A/raw.json` 为会话 `ses_e07c64cd8ffejosyU60JfsMFsC` 原始导出，共 **86 条消息**。独立注释和 SHA-256 见 `transcripts/role-A/annotations.md`。学生姓名/学号 **PENDING / 待成员本人填写**。

## 评审

- 评审人（非作者）：**PENDING / 待角色 E 实际评审**。姓名、日期与结论待真实评审后填写。
- 评审备忘：**PENDING**。`tasks/plans/A/FR-001-handoff.md` 为 A→E 交接草稿与证据索引，评审完成后据实关联 `docs/review-memo.md`。补修所依据的审查反馈不计为 E 非作者评审。

## Gate 状态（如实，六道阻断 gate 见 verification-constraints.md）

| Gate | 状态 |
|---|---|
| G-1 实现前测试批准 | **未满足**。按 `DEVELOPMENT-POLICY.md` 留存测试工作计划，未执行实现前批准。课程 G-1/D9 偏离如实保留，无教师 waiver、无伪造批准。 |
| G-2 每次提交静态检查 + 安全 PR 审查 | **部分完成**。run2 本地 Ruff 和 A 的导入结构测试已通过。独立类型/依赖检查未运行，提交与 CI 检查、适用的安全/契约/API/权限复核 **PENDING**。 |
| G-3 需求 schema | **本地通过**。run2 的 `.venv/bin/python scripts/check_course.py --root .` 退出 0。PR CI **PENDING**。 |
| G-4 提示词/模型固定集评估 | **本 PR 未触发**运行时模型或提示词变更。A 固定案例已离线验证，在线语义评估及 `NFR-002` 对比 **PENDING**。 |
| G-5 完整既有回归 | **本地通过**。上游 run2 1,412 通过、1 跳过、1 未选中，100 个子测试通过。PR CI **PENDING**。 |
| G-6 AI 使用记录更新 | **本地已更新**。角色 A 条目、86 条消息的原始会话和独立注释已关联，旧条目保留。 |

附加控制（非上述六道）：实现计划作为工作记录，无实现前批准。ADR-005 为 **PROPOSED**。E 非作者评审、PR CI 和合并授权 **PENDING**。

## 声明

- [x] 未伪造批准/结果/评审
- [x] 未削弱既有测试
- [ ] 未包含秘密（run2 常见凭证模式扫描无命中，发布前待成员核对原始 transcript 与附件）
- [x] 状态如实标注（PROPOSED/未实现/PENDING）

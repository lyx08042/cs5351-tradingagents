## Handoff: A → E

交接草稿，待成员核对。分支为 `feat/A-evidence`，本地基线为 `7dc4651`。交付范围为 M1–M2 独立证据模块。E 为约定的非作者评审角色，实际人选和结果均待确认。

### 1) 需求 + fits

| ID | 需求陈述 | 验收标准与本次证据 |
|---|---|---|
| `FR-001` | 强断言须绑定至少一个已检索证据单元，证据可用日期不得晚于分析日期，按可配置策略判定新鲜度。无证据强断言和预测须标为假设或弃权。 | 指标为无证据强断言比例，阈值为 `0.0`，验证方式为固定场景证据绑定。run2 已验证所覆盖的独立模块场景。主流程比例实测 **PENDING**。 |
| `INV-001` | 强断言必须绑定至少一个证据。无证据不得作为确定性结论。 | 指标为无证据强断言数，阈值为 `0`，通过负向测试验证。run2 已覆盖缺引用、不匹配和不可用引用等弃权路径。 |
| `NFR-002` | 成本优化下决策质量不劣化超过 3 个百分点，属待建立基线的临时目标。 | 指标为相对基线的质量变化，阈值为 `-3` 个百分点。固定评估集对照和在线语义评估 **PENDING**，暂无可报告质量差值。需求归属为 B，本交接仅提供 A 的本地证据。 |
| `NFR-005` | 叶子模块无循环导入，契约变更须记录 ADR。 | 指标为检测到的循环导入数，阈值为 `0`，验证采用导入方向结构性检查。A 模块的 AST 约束测试通过，记录了 ADR-005。跨模块集成检查 **PENDING**。 |

→ 存放位置：[需求注册表](../../../docs/req/requirements.yaml) 仍标记为 `proposed`。[角色 A 任务说明](../../A-evidence.md)

### 2) 设计 / 接口 / ADR / INV

- 采集侧通过 `EvidenceRegistry.build(run_id=..., as_of=..., candidates=...)` 建立可信证据索引。输入为映射或 `EvidenceUnit`，非法批次元素拒绝。回放使用 `EvidenceRegistry.from_dict(...)`，隔离 ID 恢复前去除首尾空白。
- `registry.admissibility(evidence_id, policy)` 判定证据准入。时间约束为 `published_at <= available_as_of <= as_of`，同时检查可选事实周期。两个来源日期必填，新鲜度按原发布日期 `published_at` 计算。未来日期、倒挂和陈旧重抓分别记录对应原因。
- `verify_claim(claim, registry=..., policy=...)` 返回 `accept_factual`、`hypothesis` 或 `abstain`，结果可通过 `to_dict()` 转成纯 JSON。符合条件的引用和事实投影留在 `evidence_refs` 与 `projection`。已评估但被拒的引用按输入顺序留在 `rejected_refs`，含逐条原因。无结构化事实的显式事实断言返回 `no_structured_fact`。
- ADR-005 为 **PROPOSED**。M3 图集成 **PENDING**，待后续协调 PR 接入。交给 E 核对的重点是证据来源与截止日期、混合引用留痕，以及 JSON 回放与模块导入边界。

→ 存放位置：[ADR-005](../../../docs/architecture/adr/005-evidence-grounded-debate.md)、[不变量](../../../docs/architecture/invariants.md)、[追踪矩阵](../../../docs/architecture/trace-matrix.md)与[模块契约](../../../tradingagents/course/evidence/README.md)。

### 3) 代码 + 测试 + PR + 计划记录（可选历史批准引用）

- 本地交付包含新增包标记 [`tradingagents/course/__init__.py`](../../../tradingagents/course/__init__.py)、[独立证据模块](../../../tradingagents/course/evidence/)、[专项测试](../../../test/offline/test_evidence.py) 和 ADR-005。run2 专项 **43 通过**，全部离线 **63 通过**。
- 正向覆盖可信对象/映射输入、合格历史事实、英语过去式、同日和新鲜度边界，以及混合引用里合法证据仍可支持事实。负向覆盖缺失或不相关引用、未来日期、发布日期倒挂、陈旧重抓、明确事实缺结构、非法批次、隔离回放和预测降级。混合引用校验拒绝原因、确定性和纯 JSON。
- PR 编号及提交 SHA **PENDING / 待成员本人发布后填写**。建议目标为 `feat/A-evidence → main`。[PR 描述草稿](PR-M2-draft.md)
- 计划与测试设计已留档。[实现计划](FR-001-implementation-plan.md) · [测试计划](FR-001-test-plan.md)
- 历史批准引用为 N/A。本次按团队现行政策使用计划工作文档。课程 G-1/D9 **未满足**，属于团队记录的课程偏离，无教师 waiver，无伪造批准。[开发政策](../../../DEVELOPMENT-POLICY.md)

→ 存放位置：本地代码、测试、计划与[验收证据](evidence/)，待成员发布 PR 后填写 PR 引用。历史批准记录仅由成员在 `docs/approvals/` 如实维护。

### 4) 实际评估 / 配置 / 结果

- 固定评估集为 [`docs/evaluation/cases.yaml`](../../../docs/evaluation/cases.yaml) @ `7dc4651`。用本地确定性夹具执行 A 的 EVAL-006（预测标为假设）、EVAL-008（合法历史事实）和 EVAL-009（未来证据拒绝），结果均符合预期。
- 配置为 Python 3.13.13、仅允许本机回环的沙箱、禁用 dotenv 自动加载。测试与演示未调用运行时模型或行情 API。OpenCode 模型是编码工具。
- run2 的 9 条记录命令均退出 0。A 专项 **43 通过**、离线 **63 通过**、上游 **1,412 通过、1 跳过、1 未选中、100 个子测试通过**。跳过项为可选的 `langchain_aws`。独立边界探针从 4/19 提升至 **19/19**。
- 在线语义评估、成本优化下的质量差值和团队汇总 **PENDING**。

→ 存放位置：[证据索引](evidence/README.md) · [run2 命令与结果](evidence/m2-run2-results.json) · [演示输出](evidence/m2-run2-08-offline-demo.txt)。后续团队汇总位于[评估日志](../../../docs/architecture/evaluation-logbook.md)和[评估表](../../../docs/architecture/evaluation-table.md)。

### 5) 完整原始会话 + 独立干预注释

- 原始 OpenCode 导出保存于 [`transcripts/role-A/raw.json`](../../../transcripts/role-A/raw.json)。会话为 `ses_e07c64cd8ffejosyU60JfsMFsC`，共 **86 条消息**，原始文件须原样保留。
- 独立注释记录 OpenCode 写入、用户提供的审查反馈与 Codex 自动验收的分工。[注释与 SHA-256](../../../transcripts/role-A/annotations.md)
- 学生姓名/学号 **PENDING / 待成员本人填写**。目前以 `role-A` 为占位，由成员本人按提交模板替换交接身份及制品命名。保留原始导出内容，并在公开前核对会话及附件。

→ 存放位置：[`transcripts/role-A/`](../../../transcripts/role-A/)。

### 6) AI 使用 / 评审 / bug / 债务 / 变更记录

- AI 使用记录为 `AI-USE-A-FR001-M1-M2`。OpenCode 编写源码、测试和 ADR，Codex 负责复现、独立验收和归档。旧条目未改。[AI 使用日志](../../../docs/ai-use-log.yaml)
- E 非作者评审 **PENDING / 待 E 实际评审**。评审人姓名、日期、结论及备忘引用待实际评审后填写。CI 与合并授权同样 **PENDING**。
- 补修前探针、测试夹具使用保留 ID 的预检失败及复验结果均已保留。[补修前证据](evidence/m2-run2-00-before-fix.txt) · [专项预检](evidence/m2-run2-00-claim-preflight.txt) · [补修后探针](evidence/m2-run2-09-boundary-probe.txt)
- M3 图集成与在线语义评估 **PENDING**。这份交接引用真实观察，团队台账可在后续评审和集成时据实更新。

→ 存放位置：[`docs/ai-use-log.yaml`](../../../docs/ai-use-log.yaml)、[`docs/review-memo.md`](../../../docs/review-memo.md)、[`docs/bug-diary.md`](../../../docs/bug-diary.md)、[`docs/debt-register.md`](../../../docs/debt-register.md)及[本地变更和 SHA-256 记录](evidence/m2-final-scope.txt)。

### 7) 报告贡献 + 个人反思 + 可验证贡献证据 + 演示材料

- 报告贡献草稿可用于 [`Report.md`](../../../Report.md) 的架构设计、实现和验证章节。建议叙述独立证据准入、明确弃权和混合引用留痕，引用 EVAL-006/008/009 及 run2 结果，说明图接入与线上评估仍 **PENDING**。最终合稿 **PENDING / 待成员本人填写**。
- 个人反思（**300–500 英文词**）**PENDING / 待成员本人填写**。[个人反思模板](../../../templates/member-reflection.md)
- 学生姓名、学号和个人贡献声明 **PENDING / 待成员本人填写**。可验证证据为源码、ADR、通过的测试、原始 OpenCode 会话和 SHA-256。PR、贡献提交和 E 评审编号在实际产生后补齐。
- 离线演示命令为 `.venv/bin/python -m tradingagents.course.evidence --demo`，可展示预测、合格历史事实和未来拒绝三个固定场景。视频时间戳 **PENDING / 待成员本人填写**，以实际录制为准。[演示输出](evidence/m2-run2-08-offline-demo.txt)

→ 存放位置：[`Report.md`](../../../Report.md)、[`templates/member-reflection.md`](../../../templates/member-reflection.md)、[`transcripts/role-A/`](../../../transcripts/role-A/)以及成员录制后补充的演示附件。

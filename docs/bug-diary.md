# Bug 日记

> 状态：**模板**。不含虚构历史条目。仅记录**真实观察到**的缺陷或可疑行为。
> 未经证实的差异必须标注“未证明为 bug”。

## 条目格式

```yaml
- id: BUG-000x
  title: <简短标题>
  observed_at: <YYYY-MM-DD>
  environment: <commit / 模型 / 配置>
  steps: <复现步骤>
  expected: <预期>
  actual: <实际>
  evidence: <日志/文件引用，脱敏>
  status: <open|confirmed|fixed|wontfix|needs-review>
  owner: <角色代码>
```

## 初始观察（引导阶段，来自真实基线运行）

```yaml
- id: BUG-001
  title: 未提供持仓时仍出现条件性仓位表述
  observed_at: "2026-11-06"
  environment: "上游 v0.7.1 @ 9fa1196；NVDA 2026-09-01；见 docs/baseline.md"
  steps: "运行一次分析且不传 portfolio"
  expected: "无持仓信息时，建议应面向读者自己的仓位，而非假设具体仓位"
  actual: "最终决策出现条件性 sizing 表述"
  evidence: "docs/baseline.md（脱敏数字）"
  status: needs-review
  owner: C
  note: "未证明为 bug；需人工判断是否为设计行为。"

- id: BUG-002
  title: 历史新闻/社交数据不可用 + FRED 无 key，导致缺失 feed 被计为 neutral（5 处）
  observed_at: "2026-11-06"
  environment: "上游 v0.7.1 @ 9fa1196；见 docs/baseline.md"
  steps: "无 FRED_API_KEY；运行日期早于当前"
  expected: "缺失应标 unavailable，而非 neutral"
  actual: "缺失 feed 被计为 neutral 5 处"
  evidence: "docs/baseline.md"
  status: needs-review
  owner: D
  note: "正是 FR-004/INV-004 要解决的问题；尚未实现。"

- id: BUG-003
  title: 成交量条件 150M vs 298.9M 差异
  observed_at: "2026-11-06"
  environment: "上游 v0.7.1 @ 9fa1196"
  steps: "观察决策中的成交量条件"
  expected: "待人工判断"
  actual: "使用 150M 条件而非 298.9M"
  evidence: "docs/baseline.md"
  status: needs-review
  owner: A
  note: "可能是有意决策，未证明为 bug；不得在报告中断言为缺陷。"
```

## 说明

- 不得虚构复现步骤或日志。
- `evidence` 只引用脱敏后的仓库内文件。

## A 模块真实缺陷（2026-11-20，FR-001 / INV-001）

> 以下均为角色 A（60825646 Ye Wenhao，M1–M2 阶段 `faf4065` 前）在独立对抗审查与 Codex 离线复现中真实发现、并交回同一 OpenCode 会话（`ses_e07c64cd8ffejosyU60JfsMFsC`）修复的缺陷；每条均保留修复前探针证据与固化回归测试。

```yaml
- id: BUG-A-001
  title: 证据准入未拦截未来 fact.period、发布/可用日期倒挂及陈旧发布日期当日重抓
  observed_at: "2026-11-20"
  environment: "feat/A-evidence M2 run1（faf4065 之前）；Python 3.13.13 离线探针"
  classification: temporal-boundary / look-ahead-and-freshness
  steps: >
    构造三条证据（as_of=2026-09-01，max_age_days=2）：(1) published_at=available_as_of=2026-08-30
    但 fact.period=2026-09-05；(2) published_at=2026-08-31 但 available_as_of=2026-08-30；
    (3) published_at=2020-01-01 但 available_as_of=2026-09-01，调用 registry.admissibility()。
  expected: "分别拒绝并返回 future_leakage、invalid_date、stale。"
  actual: "三条记录在初版实现中均返回 accept (ok)。"
  root_cause: >
    _unit_reasons 未校验可选 fact.period <= as_of 与 published_at <= available_as_of，
    且新鲜度按 available_as_of 而非原发布日期 published_at 计龄，同时 FreshnessPolicy docstring 与代码语义不一致。
  fix: >
    强制校验 published_at <= available_as_of <= as_of 与 fact.period <= as_of，
    新鲜度统一按 (as_of - published_at).days 计算并同步 ADR-005、README 与 docstring。
  invariant: "INV-001, FR-001"
  evidence: >
    tasks/plans/A/evidence/m2-run2-00-before-fix.txt；
    tasks/plans/A/evidence/m2-run2-09-boundary-probe.txt；
    test/offline/test_evidence.py::test_future_fact_period_and_provenance_inversion_fail_closed；
    test/offline/test_evidence.py::test_fresh_recapture_does_not_reset_freshness
  status: fixed
  owner: A

- id: BUG-A-002
  title: 英文过去式方向动词误判为预测、中文“目标价”漏判及 NO_STRUCTURED_FACT 分支不可达
  observed_at: "2026-11-20"
  environment: "feat/A-evidence M2 run1（faf4065 之前）；Python 3.13.13 离线探针"
  classification: classification-precision / dead-code
  steps: >
    (1) 提交历史事实文本 "NVDA surged to 150 USD on 2026-08-30" 配匹配证据；
    (2) 提交中文预测文本 "目标价200美元" 配匹配证据；
    (3) 提交 classification="factual" 且 fact=None 的断言。
  expected: "(1) accept_factual；(2) hypothesis；(3) abstain (no_structured_fact)。"
  actual: "(1) 误判为 hypothesis；(2) 漏放为 accept_factual；(3) 返回 unclassified，NO_STRUCTURED_FACT 为死代码。"
  root_cause: >
    _EN_FORECAST_PREFIXES 无视时态匹配了 surged/rallied/rebounded 等历史动词；
    _ZH_FORECAST_MARKERS 缺失“目标价/即将/大概率/涨停/跌停”；classify_claim 在 fact is None 时直接返回 unknown 屏蔽了 NO_STRUCTURED_FACT。
  fix: >
    英文方向动词仅在情态/未来短语语境中判为预测，补齐中文预测标记，
    并区分显式 classification="factual" 缺结构化事实（no_structured_fact）与未声明分类（unclassified）。
  invariant: "INV-001, FR-001"
  evidence: >
    tasks/plans/A/evidence/m2-run2-00-before-fix.txt；
    test/offline/test_evidence.py::test_historical_directional_verbs_are_not_forecasts；
    test/offline/test_evidence.py::test_modal_and_phrasal_forecasts_are_hypotheses；
    test/offline/test_evidence.py::test_mandarin_forecast_markers_are_hypotheses；
    test/offline/test_evidence.py::test_factual_declaration_without_fact_distinguishes_outcomes
  status: fixed
  owner: A

- id: BUG-A-003
  title: 投影浅拷贝破坏不可变性、公开构造器可绕过隔离及混合引用静默吞掉被拒引用
  observed_at: "2026-11-20"
  environment: "feat/A-evidence M2 预检与 run1（faf4065 之前）；Python 3.13.13 离线探针"
  classification: immutability / audit-trail-gap
  steps: >
    (1) 修改 verdict.to_dict()["projection"][0]["value"]["value"] 后重新读取；
    (2) 直接调用 EvidenceRegistry(...) 绕过 build() 隔离计算；
    (3) 传入混合引用 ["ev-1", "ev-future"] 检查 future_leakage 是否留痕。
  expected: "(1) 内部状态不受影响；(2) 禁止直接构造；(3) 保留有效支持同时记录 ev-future 的 future_leakage 原因。"
  actual: "(1) 冻结对象内部嵌套值被篡改；(2) 直接构造成功绕过冲突隔离；(3) ev-future 的拒绝原因被静默丢弃。"
  root_cause: >
    ClaimVerdict.projection 原为 tuple[dict, ...] 且 to_dict 仅浅拷贝；EvidenceRegistry 未禁用默认 __init__；
    verify_claim 在 matched 非空时直接丢弃 reasons 列表。
  fix: >
    ClaimVerdict.projection 改为不可变 tuple[Fact, ...] 并在 to_dict 生成新 JSON；
    禁用 EvidenceRegistry 默认 __init__ 强制走 build()/from_dict()；新增严格纯 JSON 的 rejected_refs 字段记录所有被拒引用与原因。
  invariant: "INV-001, NFR-004"
  evidence: >
    tasks/plans/A/evidence/00-projection-and-forecast-repro.txt；
    tasks/plans/A/evidence/00-constructor-bypass-repro.txt；
    test/offline/test_evidence.py::test_projection_emits_fresh_json_and_cannot_be_mutated；
    test/offline/test_evidence.py::test_registry_constructor_cannot_bypass_quarantine；
    test/offline/test_evidence.py::test_rejected_refs_audit_mixed_and_all_rejected
  status: fixed
  owner: A

- id: BUG-A-004
  title: EvidenceRegistry.build 静默跳过 EvidenceUnit 与非法元素，且 from_dict 未规范化隔离 ID 空白
  observed_at: "2026-11-20"
  environment: "feat/A-evidence M2 run1（faf4065 之前）；Python 3.13.13 离线探针"
  classification: fail-closed-input / replay-integrity
  steps: >
    (1) 向 EvidenceRegistry.build 传入 [EvidenceUnit(...)] 或 [unit, None]；
    (2) 向 EvidenceRegistry.from_dict 传入带首尾空格的 quarantine.conflicted=["  ev-1  "]。
  expected: "(1) 接受 EvidenceUnit，非法非 Mapping 元素抛出 ValueError(malformed)；(2) 隔离 ID 规范化后仍拒绝 ev-1。"
  actual: "(1) 均被 if not isinstance(candidate, Mapping): continue 静默忽略；(2) 带空白 ID 未命中隔离检查。"
  root_cause: "build() 对非 Mapping 元素采用静默 continue，from_dict() 未对隔离集合中的 ID 执行 strip()。"
  fix: "支持 EvidenceUnit 与 Mapping 两种合法候选输入，其余元素直接抛 ValueError(malformed)；from_dict() 恢复隔离 ID 时统一规范化去空白。"
  invariant: "INV-001"
  evidence: >
    tasks/plans/A/evidence/m2-run2-00-before-fix.txt；
    test/offline/test_evidence.py::test_registry_ingests_evidenceunit_objects_like_mappings；
    test/offline/test_evidence.py::test_registry_rejects_non_mapping_batch_items；
    test/offline/test_evidence.py::test_padded_replay_quarantine_ids_still_quarantine
  status: fixed
  owner: A
```

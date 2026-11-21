# Implementation Plan: FR-004

- 作者：编码代理（role D）— 成员姓名未知，不虚构
- 评审人（非作者）：C（计划，未评审）
- 关联测试计划：`tasks/plans/D/FR-004-test-plan.md`
- 状态：DRAFT（工作文档，非批准门）
- 批准引用（可选，历史）：`docs/approvals/implementation-plan-FR-004.md`、`docs/approvals/test-plan-FR-004.md`（PENDING，仅作设计输入，不构成批准）

## 0. 需求与 scope

- 需求：FR-004（owner D，status: **proposed**）、INV-004、NFR-004（本文只产出可追溯事件，持久化归 E）。
- 变更 scope（仅新增，不修改既有文件）：
  - `tradingagents/course/__init__.py`（仅包 docstring，无共享逻辑；必要时）
  - `tradingagents/course/data_quality/__init__.py`
  - `tradingagents/course/data_quality/contracts.py`
  - `tradingagents/course/data_quality/classifier.py`
  - `tradingagents/course/data_quality/admission.py`
  - `test/offline/test_data_quality.py`
  - `tasks/plans/D/FR-004-{implementation,test}-plan.md`
- 冻结（不改）：既有 `tradingagents/**`（除新增 course/）、`cli/`、`tests/`、`pyproject.toml`、
  `requirements*.txt`、`Dockerfile`、`docker-compose.yml`、`LICENSE`、`.github/**`、`scripts/**`、
  `AGENTS.md`、`Prompt.md`、`opencode.json`、`.agent/**`、`.opencode/**`、`docs/approvals/**`、
  其它叶子模块 `evidence/`、`budget/`、`safety/`、`audit/`（不导入）。

## 1. 契约（contracts.py）

### 1.1 常量

- `DOMAINS = ("news", "social", "macro", "price", "fundamentals")`（五域均必需）
- `STATUSES = ("available", "unavailable", "unknown")`（`neutral` **不在** status 枚举中）
- `DECISIONS = ("proceed", "abstain", "review")`

### 1.2 原始观察（输入，供 classifier 判定）

每个域的原始探测结果，字段存在性与来源有效性显式建模：

```
RawObservation:
  domain: str
  source: str | None            # 数据来源标识；None/空 -> 来源无效
  observed_as_of: str | None     # 观测/发布日期 YYYY-MM-DD
  kind: "value" | "no_data" | "missing"
  value: Any                     # kind == "value" 时才有意义
  value_present: bool            # 字段是否真实存在（区分显式 0 与缺失）
  sentiment: float | int | None  # 情绪语义源值（仅 social 可能为 0 = 显式 neutral）
  probe_error: str | None
```

缺失语义：
- `kind == "missing"` 或 `value_present is False` 或 `value is None` **不是** 0/neutral。
- 显式 `0`（`value_present is True and value == 0`）是**合法数据**。
- `sentiment == 0` 且 `value_present` 为真 -> 语义 neutral，但 status 仍为 `available`。

### 1.3 域状态标签（输出）

```
{ "domain": <one of DOMAINS>, "status": <one of STATUSES>,
  "as_of": "YYYY-MM-DD", "reason": "<str>",
  "source": "<str|null>", "sentiment": <number|null> }   # source/sentiment 为附加留痕字段
```

约束（标签校验，`validate_label`）：
- `domain` 必须在 `DOMAINS`；`status` 必须在 `STATUSES`；`status == "neutral"` 恒非法。
- `as_of` 必须是合法 ISO 日期 `YYYY-MM-DD`。
- `reason` 必须是非空 str。

### 1.4 准入决策（输出）

```
{ "decision": "proceed|abstain|review",
  "insufficient_domains": ["<domain>"],
  "labels": ["<状态标签>"],
  "reason": "<str>",
  "violations": [ { "domain":..., "code":..., "reason":... } ],   # 违规留痕（NFR-004 可检索字段）
  "analysis_cutoff": "YYYY-MM-DD" }
```

全部 JSON 可序列化（`to_dict()` 只产出 dict/list/str/number/bool/None）。

## 2. 判定规则（admission.py，确定性）

输入：`(raw_observations: list[RawObservation], analysis_cutoff: str)`。
日期用固定 fixture，不读系统时间。

优先级（fail-closed，自上而下第一个命中决定结果）：

1. `analysis_cutoff` 非法或无法解析 -> `review`（reason: invalid_cutoff）。
2. 存在任一标签违规（未知域/未知状态/`neutral` 状态/非法日期/空 reason/
   来源或日期缺失导致无法确定）-> `review`，记录 `violations`。
   - 具体地：`unavailable`/`unknown`/缺失被标为 `status=neutral` 或显式语义另标 -> 拒绝标签。
3. 缺失必需域 / 空输入 / 重复冲突域（同域给出冲突状态或冲突 `as_of`）-> `review`。
4. 任一标签 `as_of > analysis_cutoff`（未来证据）-> `review`（future_date）。
5. 否则若任一必需域 `unknown` -> `review`，`insufficient_domains` 列出该 unknown 域（不映射为 abstain）。
6. 否则若任一必需域 `unavailable` -> `abstain`，`insufficient_domains` 列出 unavailable 域。
7. 五域全部 `available` 且日期合法且 `<= cutoff` -> `proceed`。

不变量：任何异常（校验/构造抛错）在 `admit()` 边界捕获 -> `review`（reason: exception:<type>），
不静默降级。`proceed` 只能由自然语言之外的显式状态集合得出。

## 3. 不变量与失效行为

- INV-004：`unavailable`/`unknown` 永不等同 `neutral`；unknown 决策为 `review`（不映射为 abstain），
  unavailable 决策为 `abstain`；neutral 仅由 `status=available` + 显式
  `sentiment==0` 表达；不把缺失/未知填为 0/neutral。
- NFR-004：`abstain`/`review`/`proceed` 事件均含 domain、status、as_of、reason、
  `insufficient_domains`；本模块不持久化（持久化由 E）。

## 4. 步骤

1. `contracts.py`：常量、`RawObservation`、`DomainLabel`、`AdmissionDecision`、`validate_label`。
2. `classifier.py`：`classify(observation, analysis_cutoff) -> DomainLabel`；显式 neutral 识别；拒绝缺失->0/neutral。
3. `admission.py`：`admit(observations, analysis_cutoff) -> AdmissionDecision`，实现第 2 节规则与异常兜底。
4. `test/offline/test_data_quality.py`：覆盖 PT-1..PT-3、NT-1..NT-4、扩展用例（见测试计划）。
5. 验证：`python scripts/check_course.py --root .`、定向 `pytest`、上游 `pytest`、`ruff check .`。

## 5. 风险与回滚

- 风险：日期语义需与 A（evidence）对齐；当前以 ISO 字符串 + `date` 解析比对，集成阶段核对。
- 风险：上游分析师数据结构未接入；先以固定 fixture 验证，接口以共享契约为准。
- 回滚：全部为新增独立目录/测试；失败即删除新增文件，不影响上游基线。

## 6. ADR

- 本范围为数据准入校验，不产生交易提案；契约为新模块内部 schema，不改既有接口。
- ADR：N/A（如后续集成触及编排器/交易安全路径，另行走协调 PR 并补 ADR）。

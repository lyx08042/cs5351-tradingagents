# Implementation Plan: FR-004

- 作者：Chaoqun ZHENG ID: 60569580
- 评审人（非作者）：Jingbin ZHANG
- 关联测试计划：`docs/approvals/test-plan-FR-004.md`
- 批准状态：PENDING

## 1. 变更范围

### 新增文件（批准后才创建）

- `tradingagents/course/data_quality/__init__.py`
- `tradingagents/course/data_quality/contracts.py`：状态枚举、标签与决策的数据结构（JSON 可序列化）
- `tradingagents/course/data_quality/classifier.py`：原始域数据 → `available|unavailable|unknown` 状态分类；显式 neutral 识别
- `tradingagents/course/data_quality/admission.py`：全局充分性判定（proceed / abstain / review）与 default-deny 拦截
- `test/offline/test_data_quality.py`：正向 + 负向离线测试（使用本地 fixture，不访问网络）

### 明确不改（冻结路径）

- 既有上游源码：`tradingagents/` 内除新增 `course/data_quality/` 外的所有文件、`cli/`、`tests/`
- 构建与配置：`pyproject.toml`、`requirements*.txt`、`Dockerfile`、`docker-compose.yml`
- 治理基础设施：`.github/**`、`scripts/**`、`AGENTS.md`、`Prompt.md`、`opencode.json`、`.agent/**`、`.opencode/**`
- 其他叶子模块：`evidence/`、`budget/`、`safety/`、`audit/` 不直接导入；跨模块只通过共享契约（数据 schema）对接

## 2. 契约

### 输入：各数据域原始观察（离线 fixture 或上游只读数据）

### 输出：域状态标签

    {
      "domain": "news|social|macro|price|fundamentals",
      "status": "available|unavailable|unknown",
      "as_of": "YYYY-MM-DD",
      "reason": "..."
    }

### 输出：准入决策

    {
      "decision": "proceed|abstain|review",
      "insufficient_domains": ["<domain>"],
      "labels": ["<状态标签>"],
      "reason": "..."
    }

### 缺失语义

- `available`：存在、非空、对 `as_of` 日期有效；
- `unavailable`：数据源明确无该日期数据；
- `unknown`：无探测结果或结论不明确，default-deny，按不足处理；
- `neutral`：仅允许显式数据语义（如情绪评分恰为 0）；缺失/不可用/未知一律不得默认填 neutral 或 0。

## 3. 不变量与失效行为

- 关联 INV-004：`unavailable`、`unknown` 不得当作 `neutral`；下游必须显式处理。
- fail-closed：任何状态无法确定、契约不合规、域缺失时，默认 `abstain`/`review`，不得静默放行。
- 决策规则：
  - 全部关键域 `available` → `proceed`；
  - 任一 `unavailable` → `abstain` 或 `review`；
  - 任一 `unknown` → 视为不足，`abstain`/`review`；
  - 标签违规（缺失/未知被标 neutral、默认填 0）→ 拦截并记录原因。
- 事件留痕：决策结果含域、状态、日期、原因；持久化到审计模块（E）的对接留到集成阶段，本模块只产出可追溯事件。

## 4. 步骤

1. 定义 `contracts.py`：状态枚举、标签与决策结构，字段与上面的 JSON 契约一致；docstring 标注 INV-004。
2. 实现 `classifier.py`：按原始观察判定状态；识别显式 neutral；拒绝把缺失/未知映射为 neutral。
3. 实现 `admission.py`：汇总各域标签，按规则给出决策与不足域清单；违规标签拦截。
4. 编写 `test/offline/test_data_quality.py`：覆盖测试计划 PT-1～PT-3、NT-1～NT-4。
5. 本地运行：离线测试、上游回归 `pytest`、`ruff check .`。
6. 集成（M3，协调 PR）：通过共享契约把准入决策接到编排器；该步骤涉及其他角色，另行走协调 PR 与批准。

## 5. 风险与回滚

- 风险：日期语义需与 A（证据模块）对齐；当前先按 `as_of` 字符串比对，集成阶段再核对。
- 风险：上游分析师数据结构尚未接入，模块先用固定 fixture 验证；接口以共享契约为准，不直接依赖其他叶子模块。
- 回滚：本模块为新增独立目录，未获批或测试不通过时，删除新增文件即可，不影响上游基线。

## 6. ADR（安全变更必填）

- 本范围为数据准入校验，不直接产生交易提案；ADR：N/A。
- 若后续集成触及交易安全/提案校验路径，再按治理要求补 ADR 并人工批准。

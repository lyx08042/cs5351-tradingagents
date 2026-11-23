# 评估记录册

> 状态：**部分记录**。已有一条确定性回放记录；**实时模型评估尚未进行**，原因见第 3 节。
> 每次评估（含失败）追加一条记录。记录必须可复现：模型、配置、日期、用例集版本、运行人（真实身份由人工填写）。

## 记录格式

```yaml
- run_id: <唯一字符串>
  date: <YYYY-MM-DD>
  operator: <真实成员，人工填写；不得虚构>
  model: <模型 ID>
  config_ref: <配置文件或 commit>
  cases_ref: docs/evaluation/cases.yaml@<commit>
  feature_under_test: <FR-00x>
  repetitions: <整数>
  metrics:
    cost_reduction_pct: <number|null>
    quality_delta_pp: <number|null>
  result: <pass|fail|inconclusive|pending>
  notes: <自由文本，如实描述>
```

## 记录

```yaml
- run_id: FR-002-replay-2026-11-15
  date: 2026-11-15
  operator: role B (member name and student id to be filled by the member; not fabricated here)
  model: none - deterministic replay, no model is called
  config_ref: tradingagents/course/budget/replay.py@e086478
  cases_ref: docs/baseline.md (NVDA 2026-09-01) + docs/evaluation/cases.yaml EVAL-004
  feature_under_test: FR-002 / FR-006
  repetitions: 2 (identical records)
  metrics:
    cost_reduction_pct: 0.0 / -34.5 / -42.7 / -42.7 / -54.3 depending on the cap (see table)
    quality_delta_pp: null - not measured, no model was run
  result: pass (deterministic behaviour) / inconclusive (decision quality)
  notes: >
    What-if replay of one recorded run under five budget caps. The aggregates
    (19 calls, 228,275 tokens, 150.61 s) are the real numbers from
    docs/baseline.md. The per-call split is synthetic because the original run
    did not record per-call usage, so this is NOT a live measurement and must
    not be reported as one. No provider, key or spend is involved.
```

### Detail

Baseline: NVDA / 2026-09-01, 19 calls, 196,870 input + 31,405 output = **228,275 tokens**, 150.61 s.
Replay caps and outcomes:

| Cap (tokens) | Calls executed | Tokens | Δ vs baseline | Level | Degradations | Calls skipped |
|---|---|---|---|---|---|---|
| none (baseline) | 19 | 228,275 | — | L0 | 0 | 0 |
| 240,000 | 19 | 228,275 | 0.0% | L0 | 0 | 0 |
| 200,000 | 19 | 149,519 | −34.5% | L1 | 1 | 0 |
| 180,000 | 17 | 130,827 | −42.7% | L2 | 1 | 2 |
| 150,000 | 17 | 130,827 | −42.7% | L3 | 1 | 2 |
| 120,000 | 13 | 104,251 | −54.3% | L4 | 2 | 6 |

Three findings worth reporting:

1. **No spurious degradation.** A cap at or above the baseline (240,000) leaves the run untouched, which verifies that the controller does not degrade a run that fits.
2. **Compression is the cheapest lever.** L1 alone buys a 34.5% reduction with all 19 calls still executed; dropping work only starts at L2.
3. **L3 changes cost, not tokens.** Downgrading `deep` to `quick` leaves the token count identical (150,000 row equals the 180,000 row), because the ledger meters tokens and a cheaper model changes the price per token, not the volume. The report must state this rather than claim a token saving from L3.

Honest boundaries:

- Decision quality was not measured; `NFR-002` stays `inconclusive` until a live comparison runs.
- Wall-clock time is not simulated; only token volume is.
- The per-call split is synthetic and calibrated to the recorded totals.

## 说明

- 空记录是**诚实状态**，不是“通过”。
- 任何使用实时 LLM 的评估必须在本地由人工运行，凭证不入库。
- 语义评分需非作者评审，并记录到评审备注。

## 3. 实时模型评估：为什么尚未进行，以及如何补

这一节记录**缺口本身**，不是评估结果。任何人读取本文件时应知道：
第 1 节的回放是模拟，第 2 节的结论只对 token 数量成立，**决策质量从未被测量**。

### 3.1 缺口清单

| 项目 | 需求锚点 | 现状 | 缺的是 |
|---|---|---|---|
| 原版与改进版在同条件下的重复运行 | NFR-001 | ❌ 无 | 两次真实运行 + 重复次数 |
| 真实 API 下的耗时对比 | NFR-001 | ❌ 无 | 墙钟时间实测 |
| 决策质量对比 | NFR-002 | ❌ 无 | 固定用例 + 非作者评分 |
| 实时调用的 token 实测 | NFR-001 | ❌ 无 | provider 返回的 usage |

### 3.2 为什么没有做（事实，非借口）

1. **实现机器缺少运行依赖。** 准备本仓库的机器上没有 `langchain_core`、`pydantic`、
   `yfinance`，`tradingagents` 包无法导入，因此任何真实运行都无法启动。
   课程离线套件在该机器上同样只能跑一部分（`test_cde_integration.py` 等导入失败）。
2. **凭证只在本机配置。** 课程提供的 API Key 由成员在本地环境变量或 `.env` 中配置，
   不入库、不写入 transcript、不在 CI 中使用。
3. **质量评分需要人工。** `NFR-002` 的定义是「劣化 ≤3 个百分点」，需要一个固定用例集
   与非作者评分；这一步无法由脚本代劳。

### 3.3 如何补（可执行步骤）

有能力访问课程 API 的成员，在**自己的机器**上按以下顺序执行：

```bash
# 0. 准备环境（一次性）
python -m venv .venv
.venv/Scripts/activate          # Windows
pip install -e .
pip install -r requirements-course.txt

# 1. 配置凭证（不要提交）
#    .env 中设置课程提供的 provider 与 key，参考 .env.example

# 2. 基线一次（不带预算）
python test/live/eval_budget.py --ticker NVDA --date 2026-09-01 --rounds 1 --skip-baseline

# 3. 带预算一次（完整对照）
python test/live/eval_budget.py --ticker NVDA --date 2026-09-01 --rounds 1

# 4. 把生成的 JSON 路径与结果追加到本文件第 4 节
```

`test/live/eval_budget.py` 已经写好并通过语法检查，但**从未被执行**。
它输出 token 数、墙钟时间与决策，不含 prompt 正文与任何凭证。

### 3.4 报告里应如何表述

建议在报告中写：

> NFR-001 与 NFR-002 为 `inconclusive`。成本证据来自确定性回放（20 万档 −34.5%，
> 19 次调用不变），已在评估表中标注为模拟；实时对照因实现环境缺少运行依赖而未进行。
> 质量对比尚未开始，需要固定用例集与非作者评分。

**不要**把回放数字写成「实测」，也**不要**声称达到了 20% 的教师阈值——
那是团队的临时目标，不是课程标准。

## 4. 实时评估记录

（尚无。完成 3.3 的步骤后在此追加，格式与第 2 节的记录一致。）

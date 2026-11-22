# 评估记录册（PROPOSED）

> 状态：**PROPOSED，空记录**。尚未进行任何评估；不包含虚构结果。
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

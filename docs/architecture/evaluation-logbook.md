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

（暂无。当前没有已完成的评估。）

## 说明

- 空记录是**诚实状态**，不是“通过”。
- 任何使用实时 LLM 的评估必须在本地由人工运行，凭证不入库。
- 语义评分需非作者评审，并记录到评审备注。

# 离线测试（Offline）

> 不访问网络、不调用真实 LLM/API；可在 CI 稳定运行。

## 1. 当前内容

- `test_course_scaffold.py`：课程脚手架校验测试。
  - 调用 `scripts/check_course.py`（通过 `--requirements` 指向临时 fixture）。
  - 覆盖：schema 通过、重复 ID 失败、缺 `fit` 失败、trace 覆盖失败、必需文件缺失、占位符规则。
  - 使用 `tmp_path` 生成**变异后的临时 registry**，不触碰真实文件。

## 2. 运行

```bash
pytest -o testpaths=test/offline test/offline/test_course_scaffold.py
```

## 3. 标记

- 测试标记 `unit`（与上游 `pyproject.toml` 的 marker 兼容）。

## 4. 未来

- F1–F5 的离线测试（正/负向）将放在本目录（已获批准后）。

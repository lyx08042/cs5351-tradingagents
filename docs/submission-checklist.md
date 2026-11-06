# 提交清单

> 状态：**清单**。仅列出要求与排除项；不表示已完成。

## 1. 提交 ZIP 内容

- 源码（不含 `.git/`、`.venv/`）。
- 文档与治理文件。
- 课程脚手架（`scripts/check_course.py`、`test/`）。
- 测试与评估记录（如实，含失败）。

## 2. 排除项

| 排除 | 原因 |
|---|---|
| `.git/` | 元数据/历史 |
| `.venv/` | 环境 |
| `.env*`、auth、密钥 | 秘密 |
| 大体积原始数据 | 体积 |
| 视频 | **不在项目 ZIP 内**（见第 3 节） |

## 3. 视频

- **10 分钟**视频作为**独立交付物**提交，**不放入项目 ZIP**。
- 教师要求**不**需要为视频单独创建 ZIP；按课程指定渠道单独提交。
- 视频中不得显示 API key 或秘密。

## 4. Transcript

- 每人一份完整带注释记录（`transcripts/README.md`）。
- **不得**包含 API key；**不得**伪造或空白。

## 5. 提交前检查

- [ ] 无秘密（`git grep` 人工自查）
- [ ] 真实状态如实标注（PROPOSED/未实现/PENDING）
- [ ] 未修改 `tests/`/`pyproject.toml`/`LICENSE`
- [ ] `python scripts/check_course.py --root .` 通过
- [ ] `pytest -o testpaths=test/offline test/offline/test_course_scaffold.py` 通过

> 不得声称已完成或已合规。

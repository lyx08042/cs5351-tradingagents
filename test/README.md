# 测试布局说明

> 本目录解释测试组织。**不**包含业务代码。

## 1. 目录

| 路径 | 内容 | 是否可改 |
|---|---|---|
| `tests/` | 上游测试套件（历史基线，BASE-002） | **冻结，不得改** |
| `test/offline/` | 课程离线测试（脚手架 + 未来 F1–F5 离线测试） | 可新增 |
| `test/live/` | 课程在线测试说明（需真实凭证，本地运行） | 说明 |
| `test/README.md` | 本文件 | — |
| `test/offline/README.md` | 离线测试说明 | — |
| `test/live/README.md` | 在线测试说明 | — |

## 2. 原则

- **离线优先**：CI 只跑离线、不访问网络。
- **在线本地**：需真实 API/LLM 的测试只在本地由人工运行。
- **不改既有**：不得修改 `tests/` 来迁就新代码。
- **负向测试**：每个功能至少一个。

## 3. 命令

```bash
# 课程脚手架（离线）
python scripts/check_course.py --root .
pytest -o testpaths=test/offline test/offline/test_course_scaffold.py

# 上游基线
pytest
```

## 4. 当前状态

- `test/offline/` 仅含课程脚手架测试。
- F1–F5 的真实测试**尚未实现**。

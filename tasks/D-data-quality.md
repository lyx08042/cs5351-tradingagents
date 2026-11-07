# 任务 D：全局数据充分性（F4, unavailable vs neutral）

> ## ⚠️ CURRENT OVERRIDE：`DEVELOPMENT-POLICY.md`（ACTIVE, owner-selected, 2026-11-07）
> 下方所有旧的实现前计划/测试/安全批准、`PENDING`、STOP 要求均为 **HISTORICAL / NOT EXECUTED**，不再阻断本任务实现。写计划+测试设计（工作文档）后**继续实现**，无需 `approval_refs`。**最终 PR + 非作者评审 + CI + 合并授权保留**。课程 **G-1/D9 未满足**；**非教师 waiver、非伪造批准**。`PROPOSED` 不因本政策变为 `APPROVED`。开始前对 feature 分支 `git fetch origin` + `git merge origin/main`（不 reset、不 force）。

> 状态：**PROPOSED 计划**。未实现。成员身份未知，不得虚构。
> 规划顺序：先写计划+测试设计（工作文档），然后继续实现。

## 1. 交付物（Deliverables）

- 数据域状态分类：`available | unavailable | unknown`。
- 全局充分性判定：关键数据域缺失/未知时 abstain 或降级为 review。
- 缺失→中性的拦截器（default-deny unknown）。
- 正/负向测试与数据文档。

## 2. 需求 ID

- 主：`FR-004`
- 关联：`INV-004`、`NFR-004`（可审计留痕）

## 3. 拥有/提议源码路径（PROPOSED，当前不存在）

- `tradingagents/course/data_quality/`（新增）
- 测试：`test/offline/`（新增）

## 4. 依赖与契约

- 状态标签（JSON）：
  ```json
  {
    "domain": "news|social|macro|price|fundamentals",
    "status": "available|unavailable|unknown",
    "as_of": "YYYY-MM-DD",
    "reason": "..."
  }
  ```
- `neutral` 只能是**显式的数据语义**（如情绪评分恰好为 0），不能是缺失的默认值。
- **default-deny unknown**：任何未明确判定为 `available` 的状态视为不足，不得假定中性。
- 与 A（evidence）对齐日期语义与状态；不直接导入其它叶子模块。

## 5. 冻结范围

- 既有 dataflows 公共 vendor 行为、`tests/` 受保护；不整树替换基线。
- 窄范围集成编辑需：明确 scope + 接口契约（实现前人工批准不再是硬门）。
- 不把 vendor 缺失静默转换为中性。

## 6. 验收与负向测试

| 项 | 预期 |
|---|---|
| 全部关键域 available | 继续 |
| 某关键域 unavailable | abstain 或 review |
| 某关键域 **unknown**（负向） | 视为不足，abstain/review，不得当 available |
| **unavailable 被标 neutral**（负向） | 拒绝该标签 |
| 缺失域被默认填充 0/中性（负向） | 拦截并记录 |

## 7. 里程碑

- M1：状态契约与判定规则（文档）。
- M2：实现 + 负向测试。
- M3：集成（协调 PR，涉及证据/审计契约）。
- M4：非作者（C）评审。

## 8. 具体示例

> 运行日期早于当前，新闻/社交数据不可用，FRED 无 key → `news=unavailable, social=unavailable, macro=unavailable`；不得把这些计为 `neutral`（与基线观察一致，见 `docs/baseline.md`）。
> 某域无探测结果 → `unknown` → 同样视为不足（default-deny）。

## 9. 自包含可复制提示词

```text
[CURRENT OVERRIDE — 最高项目政策：DEVELOPMENT-POLICY.md（ACTIVE, owner-selected, 2026-11-07）]
旧的实现前计划/测试/安全批准、PENDING、STOP 要求均为 HISTORICAL / NOT EXECUTED，不阻断本任务实现；
写计划+测试设计（工作文档）后继续实现，无需 approval_refs。课程 G-1/D9 未满足；非教师 waiver、非伪造批准。
最终 PR + 非作者评审 + CI + 合并授权保留；不自动合并 main。开始前 git fetch origin + git merge origin/main（不 reset/force）。

你是 CS5351 team 的编码代理，负责角色 D（F4 全局数据充分性）。
必读：DEVELOPMENT-POLICY.md、AGENTS.md、Prompt.md、START-HERE.md、architecture-blueprint.md、
tasks/D-data-quality.md、docs/req/requirements.yaml、docs/code-governance/*、
docs/architecture/invariants.md 与 trace-matrix.md、docs/baseline.md。

任务范围：仅 FR-004/INV-004，路径限于 tradingagents/course/data_quality/ 与 test/offline/。
改动前输出计划与测试策略，然后继续实现与验证；不要停在计划。
仅当真实的范围外/不可逆/凭证问题才请求用户；不因 PENDING、缺失计划批准或 proposed 状态停下。
不得把缺失或未知当中性；不得伪造数据；默认离线；不自动合并 main。
```

## 10. 交接（Handoff）

使用模板 `templates/handoff.md`（七类信息），交给评审人 **C**（D 的产出由 C 评审）。

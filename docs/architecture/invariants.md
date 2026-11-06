# 架构不变量（PROPOSED）

> 状态：**PROPOSED**。所有“强制/测试/监控”列仅表示**计划**；当前均**未实现**、**未验证**。
> 关联：`architecture-blueprint.md`、`docs/req/requirements.yaml`、`docs/architecture/trace-matrix.md`。

## 1. 不变量清单

| ID | 不变量陈述 | 需求锚点 | 责任角色 | 违规时动作 | 强制（planned） | 测试（planned） | 监控（planned） |
|---|---|---|---|---|---|---|---|
| **INV-001** | 辩论中的**强断言**必须绑定至少一个已检索证据单元（evidence_ref）；无证据不得作为确定性结论输出 | FR-001 | A | 降级为假设/标注 unclear；否则 abstain | 证据绑定校验 | 负向：无证据强断言被拒 | 无证据断言比例 |
| **INV-002** | 任何 LLM 调用必须在账本中**先预留**、后结算；超出预算即拒绝（fail-closed） | FR-002 | B | 拒绝后续调用；终止运行并记录 | 预留/结算原子性 | 负向：超预算调用被拒 | 预算耗尽事件 |
| **INV-003** | 确定性**代码**（非 LLM 输出）必须对结构化提案给出 verdict：字段齐全合法、缺失快照不默认 flat、Buy/Sell units>0 且资金/持仓充足；Hold 为 `units=0` 合法。采用**显式选择的 long-only 模拟策略**：拒绝负 units/负持仓；这是所选 scope，不是通用“禁止负值”，可配置策略需批准 | FR-003 | C | fail-closed，拒绝提案（以代码 verdict 为准） | 规则校验器 | 负向：缺快照/units≤0/未声明 flat 被拒 | 拒绝事件与原因 |
| **INV-004** | `unavailable` 与 `unknown`（数据缺失/未知）不得被当作 `neutral`；下游必须显式处理，默认拒绝（default-deny unknown） | FR-004 | D | abstain 或降级为 review，不得默认中性 | 状态标签校验 | 负向：缺失/未知被当中性被拒 | unavailable / unknown 比例 |
| **INV-005** | 审计记录不可变；终局决策唯一且具权威性；修订必须以 supersede 链保存，旧版本可回放 | FR-005 | E | 拒绝覆盖写；保留历史 | 追加式存储 + 修订链 | 负向：覆盖终局决策被拒 | 修订次数、回放一致性 |

## 2. 全局失效策略

- **fail-closed 优先**：任何不确定、缺失、超限、异常，默认拒绝或 abstain，不得静默降级。
- **abstain**：数据不足或证据不足时，输出“无法判断”，而非编造信号。
- **review**：边界情形升级为人工复核，不自动通过。
- **无真实执行**：任何提案仅为模拟，永不触达真实券商（SEC-001）。

## 3. 不变量之间的一致性

- INV-002/INV-003/INV-004/INV-005 的拒绝动作必须先在 INV-005 的审计记录中留痕。
- INV-001 的 evidence_ref 应可被 INV-005 回放引用。

## 4. 当前状态

- 上述所有不变量均处于**设计**阶段，无代码、无测试、无监控。
- 课程脚手架 `scripts/check_course.py` 仅检查 registry 的 id 唯一性与 trace 覆盖，**不验证**不变量本身。

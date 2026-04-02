> Historical document.
> Archived during the April 2026 documentation reorganization.
> Kept for context only. Do not treat this file as the current source of truth.
---
date: 2026-03-31
topic: v2-alignment
type: assessment
status: active
---

# Phase 4-5 v2 对齐评估 — 为正式规划提供输入

## 执行摘要

**核心结论：v2 的基础设施比计划预想的更成熟，但有两个关键产品能力完全缺失。**

当前 Phase 4-5 计划的 11 个工作项中，有 7 个是纯工程基建，不产生 v2 的产品能力边界扩张。
同时，代码库扫描发现 v2 的多案型基础（PROMPT_REGISTRY + 三案型 prompt 文件）在 Phase 1-3 中已大量铺垫，
但还没有人意识到这个进展。

真正缺失的不是 Unit 14/22 这样的重构项，而是两个 v2 Must Have 从未出现在任何计划里：
**文书辅助模块** 和 **结构化输出路径**。

---

## 一、v2 Must Have 完成度现状

### 1.1 统一对象模型（v2 Must Have #1）

**完成度：~85%**

`engines/shared/models.py` 已包含 v2 要求的全部核心对象：
`Party`、`Claim`、`Defense`、`Issue`、`Evidence`、`Burden`、`ProcedureState`。

`ChangeItemObjectType` 枚举（Scenario Engine 用）已显式列举 Party、Claim、Defense、Burden、ProcedureState，
证明这些对象已被系统视为独立可变实体，而非 civil_loan 的字段容器。

剩余工作：`models.py` 1747 行仍为单文件，拆分是 Unit 22 的工作。
但对象本身已足够中立，不因案型变化而重命名的验收标准在代码层面基本满足。

### 1.2 案型插件机制（v2 Must Have #2）

**完成度：~70%，但分布不均**

PROMPT_REGISTRY 模式已在 Phase 1-3 中广泛落地，实质上已是一个运行中的插件机制：

| 引擎层 | civil_loan | labor_dispute | real_estate |
|--------|-----------|--------------|-------------|
| evidence_indexer | ✅ | ✅ | ✅ |
| issue_extractor | ✅ | ✅ | ✅ |
| evidence_weight_scorer | ✅ | ✅ | ✅ |
| admissibility_evaluator | ✅ | ✅ | ✅ |
| adversarial | ✅ | ✅ | ✅ |
| pretrial_conference | ✅ | ✅ | ✅ |
| interactive_followup | ✅ | ✅ | ✅ |
| procedure_setup | ✅ | ✅ | ✅ |
| report_generation | ✅ | ✅ | ✅ |
| **action_recommender** | ✅ | ❌ | ❌ |
| **attack_chain_optimizer** | ✅ | ❌ | ❌ |
| **decision_path_tree** | ✅ | ❌ | ❌ |
| **defense_chain** | ✅ | ❌ | ❌ |
| **issue_category_classifier** | ✅ | ❌ | ❌ |
| **issue_impact_ranker** | ✅ | ❌ | ❌ |

**关键发现：** simulation_run 层 6 个分析模块只有 civil_loan prompt，
是当前多案型端到端跑通的主要阻塞项，且这 6 个模块在任何计划里都没有对应工作项。

### 1.3 输出升级（胜诉/败诉/调解/补证路径）（v2 Must Have #3）

**完成度：~35%，零散分布**

| 输出路径 | 现有支撑 | 缺口 |
|----------|---------|------|
| 调解路径 | `mediation_range.py`（Unit 11） | 无独立 OutputPath 对象 |
| 补证路径 | `EvidenceGapRoiRanker`（P1.7） | 无结构化路径格式 |
| 胜诉路径 | `DecisionPathTree`（有胜诉方判断） | 无"if-then"动作链 |
| 败诉路径 | 不存在 | 完全缺失 |

现有实现将 4 条路径散落在 4 个不同产物里，没有统一的 `OutputPath` 结构体将"条件、行动、证据链"串联为可读的路径对象。v2 验收标准"文书框架被律师人工修改量明显下降"无法通过当前散落输出达成。

### 1.4 文书辅助（起诉状/答辩状/质证意见框架）（v2 Must Have #4）

**完成度：0%**

代码库全局搜索"起诉状/答辩状/document_assist/pleading"：
- `procedure_setup` prompts 中有"原告起诉状已接收"字样（描述前提条件，非生成能力）
- `pretrial_conference/cross_examination_engine.py` 有质证意见生成（单证据级，非完整框架）

无任何文书辅助引擎或 schema 存在。这是 v2 Must Have 中唯一完全空白的能力域，
也是 Phase 4-5 所有 11 个工作项中没有一个覆盖的能力。

### 1.5 支持增删证据/切换场景/比较差异（v2 Must Have #5）

**完成度：100%（Unit 8 已完成）**

`ScenarioSimulator` + `scripts/run_scenario.py` 已完整实现：
- 增删证据通过 `ChangeItem(object_type=Evidence)` 处理
- 切换程序场景通过 `ProcedureState` change_set 处理
- 比较输出差异通过 `DiffEntry` / `ScenarioDiff` 对象处理

唯一缺口：Web API 没有对应端点（Unit A 在 Phase 4-5 评估中已识别）。

---

## 二、Phase 4-5 各 Unit 对 v2 的贡献评级

```
直接贡献 = 本 Unit 完成后直接解锁某条 v2 验收标准
间接贡献 = 降低风险或提升 v2 交付质量，但不新增产品能力
无贡献   = 与 v2 产品边界无关，属于工程卫生
```

| Unit | 名称 | v2 贡献 | 理由 |
|------|------|---------|------|
| Unit 13 | 配置外部化 XS | 无贡献 | 运营便利，不改变 v2 能力边界 |
| Unit 19a | CLI ProgressReporter S | 无贡献 | 开发体验改善，与产品能力无关 |
| Unit 12 | 案件输入简化 L | 间接贡献 | 降低多案型测试摩擦，但不解锁任何 v2 验收项 |
| Unit A | Scenario API 端点 S | 间接贡献 | Web API 端点，v2 本质是 CLI-first；端到端完整性 |
| Unit 15+17 | Web API 完善 L | 间接贡献 | 生产必要，但 v2 能力验证不依赖 API 层 |
| Unit 16+21 | CI 质量门禁 M | 间接贡献 | Unit 22 的安全网；v2 自身不依赖 CI |
| Unit 19b | API SSE 端点 S | 无贡献 | UX 优化 |
| Unit 20 | DOCX 增强 S | 无贡献 | 格式美化 |
| Unit B | API E2E 集成测试 S | 无贡献 | 质量保障，不改变功能 |
| **Unit 14** | **CaseTypePlugin L** | **直接贡献（低）** | 形式化已有 PROMPT_REGISTRY；v2 可在无 Unit 14 的情况下交付，Unit 14 改善扩展性 |
| **Unit 22** | **对象模型中立化 XXL** | **直接贡献（高）** | 对象模型拆分直接支撑"不因案型变化而重命名"；但当前对象已中立，拆分是形式整理 |

**小结：** Phase 4-5 的 11 个工作项中，**直接贡献 v2 验收标准的只有 Unit 22，且目前排在最末位（P3）**。
Unit 14 有贡献但比计划的重要性低（PROMPT_REGISTRY 已够用）。
其余 9 项是基建，且没有一项覆盖 v2 的两个完全空白域（文书辅助、结构化输出路径）。

---

## 三、v2 缺口分析 — 尚未存在的工作项

以下工作项在 Phase 1-3、Phase 4-5 的任何计划里均不存在，但对 v2 验收是必要的：

### v2-Gap-1：simulation_run 层案型补全（M）

**缺口：** 6 个 simulation_run 模块仅有 civil_loan prompt，labor_dispute 和 real_estate 跑不过完整 pipeline。

**工作量：** 每个模块新增 2 个 prompt 文件（labor_dispute.py + real_estate.py），
注册到 PROMPT_REGISTRY。6 个模块 × 2 案型 = 12 个 prompt 文件。

**v2 对应验收：** "5 个案型各自通过 10 个历史案件回放" — 这是前置依赖。

**建议优先级：P0（在 v2 规划中）**

---

### v2-Gap-2：文书辅助引擎（L）

**缺口：** 完全空白。起诉状/答辩状/质证意见框架是 v2 Must Have，无任何现有基础。

**工作内容：**
- 新引擎 `engines/document_assistance/`
- Schema: `PleadingDraft`（起诉状）、`DefenseStatement`（答辩状）、`CrossExaminationOpinion`（质证意见）
- 基于 IssueTree + EvidenceIndex + OptimalAttackChain 生成框架
- 输出到 report 层，可 DOCX 导出
- 3 案型各一套 prompt

**v2 对应验收：** "文书框架被律师人工修改量明显下降"。

**建议优先级：P1（v2 核心能力）**

---

### v2-Gap-3：结构化输出路径（M）

**缺口：** 胜诉/败诉/调解/补证路径散落在 4 个不同产物，无统一 OutputPath 对象。

**工作内容：**
- 新 schema: `OutcomePath`（含路径类型、触发条件、关键动作序列、所需证据、风险点）
- 4 条路径聚合为 `CaseOutcomePaths`（胜诉/败诉/调解/补证）
- 整合现有产物：DecisionPathTree → 胜/败路径条件，MediationRange → 调解路径，EvidenceGapRoiRanker → 补证路径
- 纳入报告主体

**v2 对应验收：** "可生成稳定的'争点-证据-抗辩'矩阵"（OutputPath 是矩阵的结论层）；
"Scenario 差异输出可解释"（差异需要对应到路径变化）。

**建议优先级：P1（v2 核心产出）**

---

### v2-Gap-4：多案型验收测试套件（M）

**缺口：** 当前只有 2 个 civil_loan case YAML，无 labor_dispute/real_estate 历史案件，
无批量回放测试框架。

**工作内容：**
- 补充 10 个 labor_dispute case YAML + 10 个 real_estate case YAML（最小 3+3 可迭代）
- 批量回放脚本：`scripts/run_acceptance.py`（批跑 + 汇总一致性指标）
- 验收指标：争点一致性 ≥75%、证据引用率 100%、路径可解释性人工评分

**v2 对应验收：** "5 个案型各自通过 10 个历史案件回放" — 这是最终验收门禁。

**建议优先级：P2（v2 验收基础设施）**

---

### v2-Gap-5：争点-证据-抗辩矩阵（S）

**缺口：** 矩阵形式的输出（Issue × Evidence × Defense 三维关联）在 Phase 1-3 的多个产物中有数据支撑，
但从未被汇聚为统一的矩阵输出格式。

**工作内容：**
- 新 schema: `IssueEvidenceDefenseMatrix`
- 聚合逻辑：从 IssueTree（Issue）、EvidenceIndex（Evidence 与 Issue 关联）、DefenseChain（Defense 与 Issue 关联）构建矩阵
- 报告中以表格形式输出
- 无 LLM 调用（纯数据聚合）

**v2 对应验收：** "可生成稳定的'争点-证据-抗辩'矩阵"。

**建议优先级：P1（直接对应验收标准，实现成本低）**

---

## 四、工程基建 Unit 中哪些是 v2 前置依赖

重新审视 Phase 4-5 各工程基建项对 v2 的前置关系：

| Unit | 是否 v2 前置依赖 | 判断理由 |
|------|----------------|---------|
| Unit 13（配置外部化） | 否 | v2 可以用当前配置方式跑通 |
| Unit 14（CaseTypePlugin） | **弱是** | PROMPT_REGISTRY 已够用；Unit 14 是形式化，不是 v2 的阻塞条件 |
| Unit 15+17（Web API） | 否 | v2 验收是 CLI 跑案件，不依赖 API 层 |
| Unit 16+21（CI 质量门禁） | **弱是** | Unit 22 的安全网；如果推进 Unit 22，CI 门禁应先到位 |
| Unit 22（对象模型中立化） | **是（但可后置）** | 当前 models.py 对象已中立，拆分是工程卫生；v2 验收"对象模型不因案型变化而重命名"可在不做 Unit 22 的前提下满足 |
| Unit 12（案件输入简化） | 弱前置 | 影响多案型测试摩擦，但 YAML 手写可绕过 |
| 其余 Unit | 否 | — |

**结论：** Phase 4-5 中没有任何一项是 v2 的硬性前置依赖。
v2 可以在当前基础设施上直接开始，先做 Gap 工作，Phase 4-5 基建项并行推进或选择性推迟。

---

## 五、v2 导向重新规划框架

### 原则

1. **v2 Must Have 驱动优先级**，不以"工程完整度"驱动。
2. **PROMPT_REGISTRY 已是插件机制**，Unit 14 的形式化不是 v2 的阻塞条件。
3. **两个完全空白的 v2 Must Have**（文书辅助、结构化输出路径）必须纳入规划。
4. **simulation_run 层的案型补全**（v2-Gap-1）是目前最快解锁多案型的路径，工作量确定，比 Unit 22 安全得多。

### 建议重构后的 Phase 划分

```
Phase v2-Alpha（解锁多案型管道）
├── v2-Gap-1: simulation_run 层案型补全  [M, ~1周]
├── v2-Gap-5: 争点-证据-抗辩矩阵        [S, ~2天]
├── Unit 13: 配置外部化（缩减版）         [XS, ~1天]  ← 低成本，顺手做
└── v2-Gap-3: 结构化输出路径             [M, ~1周]

Phase v2-Beta（文书辅助 + 验收）
├── v2-Gap-2: 文书辅助引擎               [L, ~2周]
├── v2-Gap-4: 多案型验收测试套件         [M, ~1周]
└── Unit 12: 案件输入简化                [L, ~1周]  ← 降低测试摩擦

Phase v2-Polish（API 完整性 + 质量门禁）
├── Unit 15+17: Web API 完善             [L, ~1周]
├── Unit A: Scenario API 端点            [S, ~2天]
└── Unit 16+21: CI 质量门禁              [M, ~1周]

Phase v2-Refactor（架构演进，v2 交付后）
├── Unit 14: CaseTypePlugin 形式化       [L]
├── Unit 22: 对象模型中立化              [XXL]  ← 需要 CI 门禁就位
└── Unit 19a/b: 进度输出                 [S+S]  ← 可随时穿插

可推迟至 v2 之后
├── Unit 20: DOCX 增强
└── Unit B: API E2E 集成测试
```

### 关键优先级重排

| 原优先级 | 工作项 | 建议新优先级 | 变化原因 |
|---------|--------|------------|---------|
| P3 | Unit 14（CaseTypePlugin） | P3（维持，但不是 v2 阻塞） | PROMPT_REGISTRY 已够用 |
| P3 | Unit 22（对象模型中立化） | P3（维持，但 v2 可先不做） | 当前对象已足够中立 |
| 不存在 | v2-Gap-1（simulation_run 案型补全） | **P0** | v2 多案型管道的硬性缺口 |
| 不存在 | v2-Gap-2（文书辅助） | **P1** | v2 Must Have，完全空白 |
| 不存在 | v2-Gap-3（结构化输出路径） | **P1** | v2 Must Have，当前散落 |
| 不存在 | v2-Gap-5（争点-证据-抗辩矩阵） | **P1** | 验收标准直接要求，成本低 |
| 不存在 | v2-Gap-4（多案型验收测试套件） | **P2** | v2 验收门禁，不能没有 |

---

## 六、依赖关系图

```
已完成基础
├── Unit 8 ✅ Scenario Engine
├── Unit 11 ✅ 报告增强（含调解区间）
├── Unit 5 ✅ Pretrial + evidence_state_machine
└── PROMPT_REGISTRY（evidence_indexer/issue_extractor/adversarial 等 9 个引擎）

v2-Alpha
├── v2-Gap-1（simulation_run 案型补全）
│   └── 解锁 → [labor_dispute, real_estate 全管道可跑通]
├── v2-Gap-5（争点-证据-抗辩矩阵）  ← 无依赖，可立即做
└── v2-Gap-3（结构化输出路径）
    └── 依赖 Unit 11 ✅, Unit 8 ✅, EvidenceGapRoiRanker ✅

v2-Beta
├── v2-Gap-2（文书辅助）
│   └── 依赖 v2-Gap-1（全管道跑通）
└── v2-Gap-4（验收测试套件）
    └── 依赖 v2-Gap-1, v2-Gap-3

v2-Refactor（v2 交付后）
├── Unit 16+21 → Unit 22
└── Unit 14（可随时）
```

---

## 七、风险重新评估

### 被高估的风险

- **Unit 22 的阻塞性**：models.py 中 Party/Claim/Defense 已相当中立；
  v2"对象模型不因案型变化而重命名"的验收标准可能在不做 Unit 22 的前提下就能通过。
  建议在 v2-Alpha 跑通后做一次快速验证再决定是否启动 Unit 22。

- **Unit 14 的必要性**：PROMPT_REGISTRY 模式已在 9 个引擎全面落地且稳定工作。
  Unit 14 提议的 Protocol 层是锦上添花，不是 v2 的基础设施。

### 被低估的风险

- **文书辅助的难度**：这是 v2 中唯一需要从零建立新引擎的工作。
  LLM 生成法律文书框架的质量不稳定，需要足够的 few-shot examples 和结构约束。
  建议最小化初版 scope（输出模板+填空，而非自由生成）。

- **simulation_run 层 prompt 质量**：补充 labor_dispute/real_estate prompt 文件成本低，
  但 prompt 质量需要案件样本验证。建议与 v2-Gap-4 联动——先跑通，再验收。

- **缺少 labor_dispute/real_estate 案件样本**：当前只有 2 个 civil_loan YAML。
  v2 验收"10 个历史案件回放"需要样本库，这是时间成本最不确定的部分，
  应在规划时标记为依赖项，尽早启动样本收集。

---

## 八、对 ce-plan 正式规划的输入建议

进入 ce-plan 时，建议以如下方式组织规划范围：

1. **明确 v2 的 Phase 边界**：Phase v2-Alpha 到 v2-Refactor 之间哪些是"v2 发布必须"，哪些是"v2 发布后"。建议"v2 发布必须"= Alpha + Beta，Refactor 属于后续技术债务。

2. **v2-Gap-1 作为第一个工作单元**：simulation_run 层案型补全是依赖最少、解锁价值最大的工作，应作为 v2 工作流的第一步，而非等待 Unit 14/22。

3. **文书辅助需要独立 ce-plan**：文书辅助（v2-Gap-2）工作量最大、不确定性最高，建议在 v2 主规划中作为独立子系统规划，不与其他工作项混排。

4. **样本库依赖要显式化**：v2-Gap-4 的 10 case × 5 type = 50 cases 的样本需求是当前最大的人力依赖，不是工程工作。应在规划启动时作为外部依赖显式跟踪。

5. **Unit 22 解耦**：Unit 22 不应出现在 v2 发布路径上。v2 发布后，视对象模型实际稳定程度再决定是否启动，避免 XXL 重构成为 v2 的压力。

---

## 附：Phase 4-5 工作项推荐处置

| Unit | 建议 | 时机 |
|------|------|------|
| Unit 13（配置外部化 XS） | 保留，顺手做 | v2-Alpha 期间并行 |
| Unit 19a（CLI Progress S） | 推迟 | v2-Refactor |
| Unit 12（案件输入简化 L） | 保留，提前 | v2-Beta（降低测试摩擦） |
| Unit A（Scenario API S） | 保留 | v2-Polish |
| Unit 15+17（Web API L） | 保留 | v2-Polish |
| Unit 16+21（CI 质量门禁 M） | 保留 | v2-Polish（为 Unit 22 铺路） |
| Unit 19b（API SSE S） | 可选，推迟 | v2-Refactor |
| Unit 20（DOCX 增强 S） | 低优先级 | v2 之后 |
| Unit B（E2E 集成测试 S） | 低优先级 | v2-Refactor |
| Unit 14（CaseTypePlugin L） | 保留，但去除阻塞性 | v2-Refactor |
| Unit 22（对象模型中立化 XXL） | 保留，彻底解耦 v2 路径 | v2 交付后 |


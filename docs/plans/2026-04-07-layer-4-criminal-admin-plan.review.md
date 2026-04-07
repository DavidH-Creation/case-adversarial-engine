Reading additional input from stdin...
OpenAI Codex v0.118.0 (research preview)
--------
workdir: C:/Users/david/dev/case-adversarial-engine
model: gpt-5.4
provider: openai
approval: never
sandbox: read-only
reasoning effort: xhigh
reasoning summaries: none
session id: 019d67af-2712-79f0-a792-0ee292403e93
--------
user
You are a skeptical senior engineer doing an ADVERSARIAL REVIEW of the Layer 4 (Criminal + Administrative) implementation plan attached in <stdin>. The project is a Chinese legal case adversarial engine currently supporting civil case types (civil_loan, labor_dispute, real_estate). This plan adds criminal and administrative case families.

Be harsh. Assume the author was optimistic. Your job is to find what will actually break.

Review the following 9 dimensions. For each, give concrete findings:

1. MVP SUBTYPE SELECTION: criminal trio (intentional injury / theft / fraud) + admin trio (administrative penalty / government info disclosure / work-injury determination). Is this reasonable? Any higher-frequency / more important subtypes missing? Does it really cover 60%+ of real practice?

2. ENGINE N0-N4 ADAPTATION GRADES: Are the grades accurate? Any engines under-estimated (marked N1 that should be N2, etc.)?

3. N4 HIGH-RISK ITEMS: amount_calculator hard-coupling + ProcedurePhase enum decoupling plans — do they hold up? Any deeper hidden couplings?

4. CaseTypePlugin PROTOCOL only adds case_family() — is that enough? Will criminal (罪名要素) / admin (行政行为合法性要件) expose needs for entirely new methods?

5. PROMPT TWO-LAYER INHERITANCE (base + override): beyond the three civil case types, does this actually save work? Will criminal/admin prompt structure diverge so much that base degenerates into an empty shell?

6. TEST ESTIMATE 100 + 6-12 golden: optimistic? Of the existing 2408 tests, how many case-type-agnostic ones will break when families are split?

7. BATCH SPLIT 6.0 → 6.1 → 6.2 → 7.0 → 7.1: reasonable? Is 6.0 preflight scope under-estimated? Should vocab research be its own batch?

8. 15 WEEKS REALISTIC: optimistic? Is the bottleneck identification (vocab review is not coding) accurate?

9. Any CRITICAL / IMPORTANT / MINOR / NIT defects: ignored engines, model field conflicts, fixture impact, CI / performance / backward-compat risks.

OUTPUT FORMAT: group findings under four headers — ## CRITICAL / ## IMPORTANT / ## MINOR / ## NIT. Each finding: (a) problem, (b) evidence from the plan, (c) suggested fix. Be specific. Cite line numbers or section headers from the plan when you can.

The plan document follows in <stdin>.

<stdin>
---
date: 2026-04-07
topic: layer-4-criminal-admin-expansion
type: plan
status: draft
author: Claude (plan-only, no code written)
---

# Layer 4 Plan：Criminal + Administrative 案种扩展

> **性质：plan-only 研究报告。** 本文档只回答问题、估算风险和工作量、推荐批次拆分；不写代码、不建 branch、不改源文件。
>
> **上游路线图：** `docs/01_product_roadmap.md §未来扩展` 列出了 Criminal Expansion 和 Administrative Expansion 两条未来线；`docs/archive/plans/2026-03-31-ce-brainstorm-phase4-5-assessment.md` 没有 Layer 4 章节（该文档只覆盖 Phase 4-5 的 Unit 12-22）。本计划是上述两条线的首次具体化设计。
>
> **样板参考：** `docs/archive/plans/2026-04-07-batch-5-unit-22-phase-c.md`（三 enum 中性化样板）、`engines/shared/models/civil_loan.py`（物理隔离样板）、`engines/simulation_run/issue_impact_ranker/prompts/*.py`（按案件类型一套 prompt 的样板）。

---

## 0. Layer 4 现状基线与架构发现

Batch 5 合并后（commit `50f28fe`），codebase 有三个关键结构性事实是 Layer 4 设计的前提：

1. **`CaseType` 枚举已经是三家族**：`engines/shared/models/core.py:20-25` 早已定义了
   ```python
   class CaseType(str, Enum):
       civil = "civil"
       criminal = "criminal"
       admin = "admin"
   ```
   但代码里**几乎没有任何地方**实际引用 `CaseType.criminal` / `CaseType.admin` 作值——它只是 schema 层占位。

2. **`PromptProfile` 与 `CaseType` 分离**：同一文件 `core.py:28-33`：
   ```python
   class PromptProfile(str, Enum):
       """提示模板 key（engine-level）。NOT a CaseType value."""
       civil_loan = "civil_loan"
       labor_dispute = "labor_dispute"
       real_estate = "real_estate"
   ```
   而且 `PromptProfile` 在整个 `engines/` 下只有 3 处引用（`core.py` 定义 + `__init__.py` 再导出 + `test_prompt_registry.py` 测试）。**真正跑在生产代码里的是裸字符串 `"civil_loan"` 等**，`PromptProfile` 并没有被作为类型约束使用。这是一把双刃剑：好处是加新值成本几乎为零；坏处是没有类型安全作为护栏，打字错误会在运行期才被发现。

3. **`Issue.impact_targets` 已经是 `list[str]`**（Batch 5 Phase C.3 的"不可逆点"）：模型层不再携带案件类型专属词汇，过滤发生在 `issue_impact_ranker` 层。这意味着 Layer 4 加新案种**不再需要改 `Issue` 模型本身** —— 只需要给每个新案种写一个 `ALLOWED_IMPACT_TARGETS` frozenset。

4. **`engines/shared/models/civil_loan.py` 是唯一的案种专属模块**：没有对应的 `labor_dispute.py` 或 `real_estate.py`，因为劳动争议和房屋买卖与民间借贷共用金额计算抽象（`AmountCalculationReport`、`ClaimCalculationEntry` 等）。这个样板可直接套用到 criminal/admin，但要警惕：**criminal 和 admin 的领域对象和"金额"概念差异极大**，照搬可能得不偿失。

5. **现有引擎清单**（来自 Explore agent 的 inventory）：
   - **17 个 engine 需要 Layer 4 prompt 扩展**（有 `prompts/` 子目录 + `PROMPT_REGISTRY`）
   - **8 个 engine 规则驱动，Layer 4 无需改**（`alternative_claim_generator`、`credibility_scorer`、`evidence_gap_roi_ranker`、`hearing_order`、`issue_dependency_graph`、`case_extraction`、`case_extractor`（使用 generic.py）、`similar_case_search`）
   - **1 个特殊引擎 `amount_calculator`**：硬编码 `if case_type == "civil_loan"` 专属逻辑（`calculator.py` 约第 140 行），对 criminal/admin 来说可能完全用不上金额复算，需要额外决策
   - **1 个特殊引擎 `document_assistance`**：`PROMPT_REGISTRY` 是 `(document_type, case_type)` 二元组键，加一个新案种意味着加 **3 × (文档类型数)** 个条目

---

## 问题 1：案种范围与 MVP 子类型

### 推荐的 MVP 子类型

**刑事（criminal）MVP：3 个子类型**

| 子类型 key | 中文 | 刑法条文 | 选它的理由 |
|---|---|---|---|
| `intentional_injury` | 故意伤害罪 | 《刑法》第 234 条 | 暴力犯罪原型；证据链靠伤情鉴定 + 现场证据，Evidence 模型很贴合；常见 Issue（正当防卫、因果关系、伤情等级） |
| `theft` | 盗窃罪 | 《刑法》第 264 条 + 法释〔2013〕8 号 | 财产犯罪原型；有清晰的"金额"概念（数额较大/巨大/特别巨大）—— 这是唯一一个现有 `AmountCalculationReport` 可以浅层复用的刑事子类型 |
| `fraud` | 诈骗罪 | 《刑法》第 266 条 + 法释〔2011〕7 号 | 欺诈原型；与民事合同纠纷有显著交叉（合同诈骗 vs 民事欺诈界限），对 hybrid 案件处理能力是加分项 |

**不选 MVP 的刑事子类型（及原因）**：
- 危险驾驶罪（§133-1）：案情单薄，90% 走速裁程序，分析价值低
- 交通肇事罪（§133）：核心是附带民事赔偿，已被 `civil_loan` / real_estate 部分覆盖
- 贪污受贿（§382/385）：领域知识门槛极高，公诉性质不适合对抗式模拟
- 毒品犯罪（§347）：证据结构特殊（控制下交付、线人），很难对标现有 Evidence 模型

**行政（administrative）MVP：3 个子类型**

| 子类型 key | 中文 | 法律依据 | 选它的理由 |
|---|---|---|---|
| `admin_penalty` | 行政处罚不服 | 《行政诉讼法》§12(1) + 《行政处罚法》 | 行政诉讼最大类（约 40%-50%），罚款/吊销/拘留/没收，"处罚明显不当可变更"（§77）有清晰的裁判方向 |
| `info_disclosure` | 政府信息公开 | 《政府信息公开条例》+ 法释〔2011〕17 号 | 法律框架最清晰的行政案由；请求-答复-诉讼链路规整；争点相对局限（是否属于政府信息、是否豁免、答复是否完整），对 Issue 模型友好 |
| `work_injury_recognition` | 工伤认定 | 《工伤保险条例》+ 法释〔2014〕9 号 | 跨"行政"与"社保"，既是工伤认定决定书的合法性审查，又带民事赔偿色彩；和现有 `labor_dispute` 能形成 natural companion，让用户能处理"工伤→认定→仲裁→赔偿"全链路 |

**不选 MVP 的行政子类型（及原因）**：
- 征地拆迁（《土地管理法》）：政治敏感且法条已经 2019 年改过一轮，案例分歧大
- 行政许可不服：许可门类太多（食品、药品、建设、环评…），每一种都是独立领域
- 行政不作为：争点结构单一（是否具有法定职责 + 是否履行），可能不需要独立 PromptProfile，留给 `admin_penalty` 的 variant 即可

### 推荐范围：刑事 3 + 行政 3 = 6 个新 `PromptProfile` 值

这个数量级保持和当前 civil kernel（3 个 civil 子类型）对称，也为"能不能按案种家族写一个 base prompt，子类型只 override 词汇"的架构选择留出空间。

---

## 问题 2：Engine 适配清单（26 个引擎 × Layer 4 工作量）

评级定义：
- **N0**：不需要改（规则驱动或案种无关）
- **N1**：只需加 prompt 模块 + 注册到 `PROMPT_REGISTRY`
- **N2**：N1 + 需要新的 `ALLOWED_IMPACT_TARGETS` 或 plugin 方法
- **N3**：N1/N2 + 需要新的领域字段或子模型
- **N4**：需要重构现有逻辑（硬编码 civil_loan 假设）

| # | Engine | 目录 | 评级 | 说明 |
|---|---|---|---|---|
| 1 | `action_recommender` | `simulation_run/` | **N1** | 现有 PROMPT_REGISTRY 模式，加 6 个 prompt 文件 |
| 2 | `alternative_claim_generator` | `simulation_run/` | **N0** | 规则驱动 |
| 3 | `attack_chain_optimizer` | `simulation_run/` | **N1** | PROMPT_REGISTRY 模式 |
| 4 | `credibility_scorer` | `simulation_run/` | **N0** | 规则驱动（职业放贷人检测是 civil_loan 专属但已经是可选分支） |
| 5 | `decision_path_tree` | `simulation_run/` | **N1** | PROMPT_REGISTRY 模式 |
| 6 | `defense_chain` | `simulation_run/` | **N1** | PROMPT_REGISTRY 模式 |
| 7 | `evidence_gap_roi_ranker` | `simulation_run/` | **N0** | 规则驱动 |
| 8 | `hearing_order` | `simulation_run/` | **N0** | 规则驱动 |
| 9 | `issue_category_classifier` | `simulation_run/` | **N1** | PROMPT_REGISTRY 模式 |
| 10 | `issue_dependency_graph` | `simulation_run/` | **N0** | 规则驱动 |
| 11 | `issue_impact_ranker` | `simulation_run/` | **N2** ⭐ | 需要 6 个 prompt 文件 + 6 个 ALLOWED_IMPACT_TARGETS + 6 个 few-shot JSON；这是 Layer 4 词汇研究的核心入口 |
| 12 | `case_extractor` | `case_structuring/` | **N0** | 已用 generic.py 一份 prompt 覆盖所有案种 |
| 13 | `admissibility_evaluator` | `case_structuring/` | **N1** | dict-based registry，加 6 个条目 |
| 14 | `amount_calculator` | `case_structuring/` | **N4** ⚠️ | 硬编码 civil_loan 逻辑；criminal/admin 绝大部分情况不需要金额复算；需要决策：(a) 扩展支持盗窃/诈骗的数额认定，(b) 支持行政处罚的罚款数额，或 (c) 在 runner 层直接 bypass |
| 15 | `evidence_indexer` | `case_structuring/` | **N1** | module-based |
| 16 | `evidence_weight_scorer` | `case_structuring/` | **N1** | dict-based |
| 17 | `issue_extractor` | `case_structuring/` | **N1** | module-based |
| 18 | `adversarial` | `engines/` | **N1** | PROMPT_REGISTRY；但刑事的"控辩"和"原被告"语义不同，需要在 prompt 层区分 |
| 19 | `case_extraction` | `engines/` | **N0** | 规则驱动 |
| 20 | `document_assistance` | `engines/` | **N1-N3** ⚠️ | `(doc_type, case_type)` 二元组键；新增 6 案种意味着 6 × (现有 doc_type 数 ≈ 3) = 18 个新条目；可能还要加刑事专属的 `doc_type`（起诉书/辩护词/上诉状）→ 升级到 N3 |
| 21 | `interactive_followup` | `engines/` | **N1** | PROMPT_REGISTRY 模式 |
| 22 | `pretrial_conference` | `engines/` | **N2** ⚠️ | 有 `judge.py` 独立模块；刑事庭前会议（刑诉法 §187）和民事庭前会议结构差异大，可能需要重写 judge.py 的 criminal 分支 |
| 23 | `procedure_setup` | `engines/` | **N2-N3** | 民事诉讼程序和刑事/行政程序不是同一个东西（刑事有侦查/起诉/审判三段式，行政有行政复议前置），procedure_setup 可能需要新增 stage 类型 |
| 24 | `report_generation` | `engines/` | **N1-N2** | PROMPT_REGISTRY；但刑事报告的"量刑建议"章节和民事"胜诉率评估"结构完全不同，v3 模板需要扩展 |
| 25 | `similar_case_search` | `engines/` | **N0** | 案种无关（关键词检索） |
| 26 | `report_generation/v3` | `engines/` (sub) | **N2** | 见 #24，v3 子目录需要对称扩展 |

### 汇总统计

- **N0 不改**：8 个引擎 → 工作量为 0（但可能需要 smoke test 验证新案种下行为一致）
- **N1 纯 prompt**：12 个引擎 → 单案种 1-2 天/engine
- **N2 prompt + plugin 方法**：3 个引擎（`issue_impact_ranker` / `pretrial_conference` / `report_generation`）→ 单案种 3-4 天/engine
- **N3 新领域字段**：1 个引擎（`document_assistance` 升级版）→ 单案种 4-5 天
- **N4 重构**：1 个引擎（`amount_calculator`）→ 一次性重构 5-7 天，独立于具体案种
- **N2/3 混合**：2 个引擎（`procedure_setup` / `report_generation` v3）→ 单案种 3-5 天

### 危险信号

- `amount_calculator` 的 civil_loan 硬耦合是 Layer 4 的**第一个绊脚石**，应当在开始任何案种扩展前作为"Batch 6.0"单独解耦
- `procedure_setup` 可能触发 `ProcedurePhase` 枚举（`core.py:118`）的扩展 —— 当前枚举是针对民事庭审流程设计的（`evidence_submission` / `evidence_challenge` / `judge_questions` / `rebuttal`），刑事的"法庭调查/法庭辩论/最后陈述"和行政的"陈述申辩/听证"可能需要新值

---

## 问题 3：Model 层需求

### 是否需要新的案种专属模块？

**推荐：是，但只创建必需的**。对 Batch 5 样板（`civil_loan.py` 承载了所有与放款/还款/金额复算相关的类型）的照搬没有意义，因为 criminal 和 admin 的领域对象完全不同。

#### `engines/shared/models/criminal.py`（推荐创建）

**承载**：
- `ChargeType`（罪名枚举，MVP 期只有 `intentional_injury` / `theft` / `fraud`；或者设计为 `tuple[str, str]` = (章节, 具体罪名)）
- `CriminalImpactTarget`（枚举或 frozenset，值：`conviction` / `charge_name` / `sentence_length` / `sentence_severity` / `incidental_civil_compensation` / `credibility`）
- `SentencingFactor`（量刑情节：法定/酌定 × 加重/减轻/从重/从轻）
- `ChargeElement`（犯罪构成要件：主体/客体/主观方面/客观方面）—— 可选，看 P0 是否真的需要结构化
- `EvidenceChainStatus`（证据链状态：`exclusive` 排他性认定 / `consistent` 相互印证 / `conflicting` 矛盾 / `insufficient` 不足）
- `IllegalEvidenceExclusionRecord`（非法证据排除记录）

**不承载**：刑事案件的"金额"概念（盗窃数额）应当作为 `Claim.amount` 或专门的 `CriminalAmount` 子类；不建议重用 `civil_loan.AmountCalculationReport`，因为盗窃数额不需要"本金/利息"拆分。

#### `engines/shared/models/administrative.py`（推荐创建）

**承载**：
- `AdminActionType`（被诉行政行为类型：`penalty` / `permit` / `coercion` / `inaction` / `info_disclosure_reply` / `compensation_decision`）
- `LegalBasisCheck`（合法性审查五要素：`authority` 职权 / `procedure` 程序 / `factual_basis` 事实 / `legal_basis` 法律依据 / `discretion` 裁量）
- `AdminReliefType`（判决类型：`revocation` / `declare_illegal` / `order_perform` / `alteration` / `compensation` / `dismiss`）
- `AdminImpactTarget`（枚举或 frozenset：`legality` 合法性 / `procedure_compliance` 程序合规 / `factual_accuracy` 事实认定 / `discretion_reasonableness` 裁量合理性 / `relief_type` 判决类型 / `credibility`）
- `ReconsiderationPrerequisite`（行政复议前置要求）

**不承载**：民事意义上的"赔偿金额"应当走 `state_compensation` 走一个独立的 `StateCompensationClaim`，不混入通用 `Claim`。

### CaseTypePlugin Protocol 需要扩展吗？

**当前 Protocol**（`case_type_plugin.py:42-89`）只有两个方法：
- `get_prompt(engine_name, case_type, context)`
- `allowed_impact_targets(case_type) -> frozenset[str]`

**推荐为 Layer 4 增加的方法**（按优先级排序）：

1. **`case_family(case_type) -> Literal["civil", "criminal", "admin"]`** 🔴 必须
   - 让引擎在不 hard-code 映射表的情况下把 `PromptProfile` 归一到 `CaseType.value`
   - 触发场景：报告生成要显示"本案属于刑事案件"；程序引擎要决定走民诉/刑诉/行诉流程

2. **`allowed_procedure_phases(case_type) -> tuple[ProcedurePhase, ...]`** 🟡 推荐
   - 因为 `ProcedurePhase` 是为民事庭审设计的，刑事/行政的阶段序列不同
   - 避免在每个引擎里重复写 `if case_family == "criminal": phases = [...]`

3. **`allowed_relief_types(case_type) -> frozenset[str]`** 🟢 可选
   - 民事是"判决支持/部分支持/驳回"，刑事是"有罪/无罪/发回"，行政是"撤销/确认违法/驳回"
   - 可以推迟到发现实际需要时再加

4. **`default_burden_allocation(case_type) -> dict[str, str]`** 🟢 可选
   - 刑事是"控方承担举证责任（无罪推定）"，行政是"被告承担主要举证责任"（《行政诉讼法》§34），民事是"谁主张谁举证"
   - 如果 `burden_allocator` 引擎能读到这个默认值，可以省掉每个案种一个 prompt

**推迟决策**：不推荐在 Layer 4 初期就扩展 Protocol，因为 Batch 5 刚刚才把 `allowed_impact_targets` 加进去。应当在 Batch 6.0（amount_calculator 解耦）之后、Batch 6.1（criminal 第一个子类型 PoC）之中再决定要不要加 `case_family()` 这样的方法。

---

## 问题 4：领域词汇研究清单

### 权威来源（要读的文件）

#### 刑事

1. **《中华人民共和国刑法》**（2020 修正版 = 刑法修正案十一）
   - 第二编 分则：§234（故意伤害）、§264（盗窃）、§266（诈骗）
   - 第一编 总则：§13-21（犯罪构成）、§22-26（故意过失）、§61-78（量刑）
2. **《中华人民共和国刑事诉讼法》**（2018 修正版）
   - §5（独立审判）、§12（无罪推定）、§50-56（证据）、§186-202（法庭审理）
3. **最高法 法释〔2021〕1 号**：最高人民法院关于适用《中华人民共和国刑事诉讼法》的解释
4. **各罪专属司法解释**：
   - 故意伤害：法释〔2013〕12 号、〔2015〕9 号（伤情鉴定标准）
   - 盗窃：法释〔2013〕8 号（数额认定）
   - 诈骗：法释〔2011〕7 号、〔2016〕25 号（电信网络诈骗）
5. **最高法指导性案例**（对照 CaseLaw Reasoner 能力）：第 3 号（潘玉梅诈骗）、第 13 号（王召成非法买卖爆炸物，定罪证据链样板）等

#### 行政

1. **《中华人民共和国行政诉讼法》**（2017 修正版）
   - §2-12（受案范围）、§25-27（当事人）、§34（被告举证责任）、§63-80（判决形式）
2. **最高法 法释〔2018〕1 号**：关于适用《中华人民共和国行政诉讼法》的解释
3. **《中华人民共和国行政处罚法》**（2021 修订）
   - §3-5（原则）、§8-15（处罚种类和设定）、§44-65（程序）
4. **《政府信息公开条例》**（2019 修订）+ 法释〔2011〕17 号
5. **《工伤保险条例》**（2010 修订）+ 法释〔2014〕9 号 + 人社部相关规范性文件
6. **《国家赔偿法》**（2012 修正版）— 涉及行政赔偿章节

### 需要研究的词汇维度（每个维度要填一个 frozenset）

| 维度 | civil 参考 | criminal 需查 | admin 需查 |
|---|---|---|---|
| `impact_targets` | principal/interest/penalty/attorney_fee/credibility | conviction / charge / sentence / incidental_civil / credibility | legality / procedure / factual / discretion / relief / credibility |
| `relief_types` | 支持/部分支持/驳回 | 有罪/无罪/发回/不起诉 | 撤销/确认违法/责令履行/变更/赔偿/驳回 |
| `evidence_categories` | 书证/物证/证人/视听/电子/鉴定/勘验 | + 被告人供述 + 被害人陈述 + 辨认笔录 + 侦查实验笔录 | + 行政卷宗 + 被诉行政行为底稿 + 听证记录 |
| `burden_keywords` | 谁主张谁举证 | 无罪推定 / 排除合理怀疑 | 被告举证行政行为合法 |
| `procedure_phases` | case_intake→opening→evidence→judge→rebuttal | 侦查→起诉→一审庭审（法庭调查→法庭辩论→最后陈述）→二审 | 复议前置→起诉→审理→判决 |

### 研究产出物（每个案种）

每个新案种应当产出**一份 vocab 研究笔记**（约 300-500 字），格式：
```
案种：故意伤害罪 (intentional_injury)
上级 CaseType：criminal
法律依据：《刑法》§234 / 法释〔2013〕12 号 / 人体损伤程度鉴定标准（2014）
核心争点类型：
  - 正当防卫与防卫过当的区分
  - 伤情等级认定（轻伤一级/二级、重伤一级/二级）
  - 因果关系（多因一果时的责任分配）
  - 故意 vs 过失（故意伤害 vs 过失致人重伤）
ALLOWED_IMPACT_TARGETS 候选：
  - conviction（定罪与否）
  - charge（罪名选择）
  - sentence_length（刑期长短）
  - sentence_severity（是否实刑/缓刑）
  - incidental_civil_compensation（附带民事赔偿金额）
  - credibility（可信度枢轴）
量刑情节（SentencingFactor）候选：
  法定：自首、立功、累犯、未成年人、限制责任能力…
  酌定：认罪认罚、退赃退赔、赔偿谅解、犯罪前科…
```

6 份这样的笔记（3 criminal + 3 admin）= Layer 4 的词汇研究交付物。

---

## 问题 5：Prompt 工程量估算

### 天真的全量估算（每个子类型一套 prompt）

- **17 个 N1+ 引擎 × 6 个新子类型 = 102 个新 prompt 模块**
- 每个模块平均 200 行 → **约 20,000 行新 prompt 代码**
- 加上 6 个 `issue_impact_ranker.{case_type}.json` few-shot 文件（约 50 行/文件）

这是**上限**。实际工程量可以显著压缩：

### 推荐：两层 prompt 继承策略

**层 1：案种家族 base prompt**
- 每个引擎每个家族一份：
  - `prompts/_criminal_base.py` — 刑事通用 system prompt + 通用 build_user_prompt
  - `prompts/_admin_base.py` — 行政通用 system prompt + 通用 build_user_prompt
- 覆盖 80% 通用结构（案件基本信息、证据清单、争点列表渲染）

**层 2：案种 override**
- 每个引擎每个子类型一份，但只定义变化部分：
  - `ALLOWED_IMPACT_TARGETS`（frozenset）
  - `DOMAIN_SPECIFIC_HINT`（案种专属 prompt 段落注入 base system prompt）
  - 可选的 `build_user_prompt` 覆盖（仅当需要专属 context 块）

**压缩后估算**：
- 17 个引擎 × 2 个 base（criminal base + admin base） = **34 个 base prompt 模块**
- 17 个引擎 × 6 个 subtype override = **102 个 override 文件，但平均只有 30-50 行**
- 总代码量 ≈ 34 × 200 + 102 × 40 = **约 10,880 行** （砍掉 ~45%）

### Few-shot 文件

- `issue_impact_ranker`：6 个新文件（critical，决定词汇过滤）
- `adversarial_plaintiff` / `adversarial_defendant`：**可能**需要按 criminal/admin 拆分，因为"控方/辩方"语义和"原告/被告"不一样；估 2 个新文件
- `defense_chain`：可能需要 criminal-specific（非法证据排除辩护 vs 民事合同无效辩护）；估 1 个新文件
- **合计 9 个新 few-shot JSON**（每个 50-100 行 = 450-900 行 JSON）

### Prompt 迭代成本

法律类 prompt 的**调优**通常比首写更费时间。根据 Batch 5 的经验（labor_dispute / real_estate 从对抗评审中暴露"例子和词汇不一致"的问题），每个新子类型的 prompt 在首次跑通后还需要 **2-3 轮 LLM-in-the-loop 调优**才能达到 civil_loan 的质量基线。这部分成本**不在代码行数里**，但是 Layer 4 最容易被低估的工作量。

---

## 问题 6：Test / Fixture / Golden 估算

### 现有测试状态（Batch 5 合并后）

- **2408 passed** on main
- **266 处**测试源文件中出现 `civil_loan` / `labor_dispute` / `real_estate` 字符串
- 约 **85 个测试文件**提到案件类型

### 新增测试估算

#### 单元测试（每个新子类型）

| 测试对象 | 每子类型新增数 | 6 个子类型合计 |
|---|---|---|
| 新 prompt 模块（build_user_prompt 结构） | ~3 | 18 |
| 新 ALLOWED_IMPACT_TARGETS（vocab lock-step） | ~2 | 12 |
| 新 few-shot JSON（example 与 vocab 一致） | ~2 | 12 |
| 新 model 类（criminal.py / administrative.py 的 pydantic 验证） | ~5-10（仅两个家族） | 10-20 |
| ranker `_resolve_impact_targets` 对新 vocab 过滤 | ~2 | 12 |
| CaseTypePlugin `allowed_impact_targets` 对新 case_type | ~1 | 6 |

**单元测试合计：约 70-80 个新测试**

#### 契约测试 / 参数化现有测试

- `test_prompt_registry.py` 需要扩展 `PromptProfile` 参数化 → +6 个 parametrize 展开
- `test_case_type_plugin.py` 需要为每个新案种跑一遍 UnsupportedCaseTypeError 反向测试 → +6 个
- 每个 N1+ 引擎的 `test_*.py`（如果当前是 hardcode `case_type="civil_loan"`）需要参数化 → **约 25-35 个测试文件需要重写**

#### E2E 测试（pipeline 穿透）

- 每个新子类型需要一条端到端 smoke test（输入 fixture → 跑完整 pipeline → 断言关键产物）
- 6 个新子类型 = **6 条新 E2E**
- 每条 E2E 需要一个 case fixture（模拟起诉书/判决书文本）+ golden output

#### Golden 文件

- `benchmarks/golden_outputs/` 当前有若干 civil 案例
- 每个新子类型需要 **1-2 个 golden case**（最小规模）
- 合计 **6-12 个新 golden case**

#### 受影响的现有测试

估计 **30-40 个现有测试文件需要更新**（主要是参数化、增加新 case_type 到 parametrize 列表、调整硬编码断言）。**不会破坏**的测试：所有使用 `LLM_MOCK=true` 的 unit test（约 2000+ 个），因为它们是 case_type-agnostic 的断言。

**总测试增量估算**：
- 新增：80 unit + 6 E2E + 12 golden ≈ **100 个新测试**
- 修改：30-40 个现有文件
- **预期最终测试数**：2408 → ~2500+

---

## 问题 7：风险 + 批次拆分

### 风险清单

#### 🔴 Critical

1. **`amount_calculator` 民事硬耦合** — 如果不先解耦，criminal/admin 引擎在 pipeline 层会被绊倒。**缓解**：Batch 6.0 专门解耦，在任何案种扩展前完成。

2. **`ProcedurePhase` 枚举不兼容** — 当前枚举只覆盖民事庭审阶段。刑事"法庭调查/法庭辩论/最后陈述"和行政"陈述申辩/听证"不在里面。如果 `procedure_setup` 或 `pretrial_conference` 访问了 phase 的具体值，扩展会引起回归。**缓解**：Batch 6.0 同时审查 `ProcedurePhase` 的所有使用点，决定是扩枚举还是让 `allowed_procedure_phases()` plugin 方法接管。

3. **Prompt 质量无法被单元测试保证** — LLM 输出在 `LLM_MOCK=true` 下是 mock 的，真实的 criminal/admin prompt 质量只能靠人工 review 和昂贵的 live LLM eval。如果没有 eval harness，每个子类型在生产环境都可能翻车。**缓解**：Batch 6.0 前置建立一个最小的 `benchmarks/layer4_eval/` 框架，至少每个新子类型有 3 个真实 LLM-driven 的 smoke test（打开 LLM live 标志运行）。

#### 🟡 Important

4. **`document_assistance` 的 (doc_type × case_type) 组合爆炸** — 刑事文书类型（起诉书/辩护词/上诉状/量刑建议书）和民事文书完全不同。如果每个组合都写独立 prompt，工程量会翻倍。**缓解**：Batch 6.0 前调研是否要从"组合键"切换到"工厂函数"模式。

5. **`adversarial` 引擎的"原被告"vs"控辩"语义错配** — `adversarial_plaintiff.json` / `adversarial_defendant.json` 的 few-shot 示例是民事语境。刑事的"控方/辩方"有完全不同的策略空间（控方不需要"诉请"，辩方有"罪轻辩护/无罪辩护"二选一）。**缓解**：criminal batch 需要一次性重写 adversarial 的 few-shot。

6. **`report_generation/v3` 模板分叉** — v3 模板是为民事对抗报告设计的（胜诉率评估、调解区间等已被删除）。刑事报告需要"量刑建议"章节，行政报告需要"合法性审查结论"章节。**缓解**：v3 需要三份并行的 section template，不能共用一份。

7. **研究深度不足导致设计返工** — 6 个新子类型的法律研究如果不到位，模型字段和 prompt 结构都会在编码过程中被推翻。**缓解**：Batch 6.0 前置一个纯研究 sprint（1-2 周），交付 6 份 vocab 研究笔记 + 模型字段草案，经过人类法律专家 review 后才开写代码。

#### 🟢 Minor

8. **Test 爆炸半径** — 现有 85 个提案件类型的测试文件，参数化成本不大但有 review 负担。
9. **CLI/API 层面的 case_type 参数暴露** — 需要更新 help text、API schema（OpenAPI）、CLI validation 列表。
10. **文档和 README 更新** — 低优先级但不可忽略。

### 批次拆分建议

**Criminal 和 administrative 应当完全分开，不能混合。** 理由：

- 两者领域模型差异巨大（criminal.py / admin.py 没有代码复用空间）
- 两者 vocab 研究不能互相参考（引用的法条完全不同）
- 两者的 prompt 调优回路独立，混在一个 batch 里会造成注意力分散和回归风险
- 批次越大，爆炸半径越大（Batch 5 的经验：一个 6 commit 的 batch 已经到了 adversarial review 能稳定审完的上限）

**建议的批次序列**：

#### Batch 6.0：Layer 4 Preflight（2 周）

**目标**：解耦和基础设施，不落地任何具体案种
- 6.0.1 解耦 `amount_calculator` 的 civil_loan 硬编码（让 pipeline 能跳过金额复算）
- 6.0.2 审查 `ProcedurePhase` 使用点，必要时扩展枚举或加 `allowed_procedure_phases()`
- 6.0.3 `CaseTypePlugin` Protocol 扩展：加 `case_family(case_type)` 方法
- 6.0.4 建立 `benchmarks/layer4_eval/` 最小 eval harness
- 6.0.5 完成 6 份 vocab 研究笔记（交付物 markdown，不碰代码）
- **Blast radius**：~10 文件，~30 测试
- **Gate**：人工 review vocab 笔记并签字

#### Batch 6.1：Criminal Foundation（2-3 周）

**目标**：criminal 第一个子类型跑通端到端
- 6.1.1 `engines/shared/models/criminal.py` 最小版（ChargeType、CriminalImpactTarget、SentencingFactor）
- 6.1.2 `intentional_injury` 的 `_criminal_base` + override prompt × 17 引擎
- 6.1.3 `issue_impact_ranker.intentional_injury.json` few-shot
- 6.1.4 端到端 smoke test + 1 个 golden case
- **Blast radius**：~30 文件，~40 新测试
- **Gate**：smoke test 在 LLM live 模式下通过

#### Batch 6.2：Criminal Expansion（2 周）

- 6.2.1 `theft` 子类型（包括对 amount_calculator 的可选扩展，支持盗窃数额认定）
- 6.2.2 `fraud` 子类型
- 6.2.3 adversarial few-shot 刑事化重写
- **Blast radius**：~40 文件

#### Batch 7.0：Administrative Foundation（2-3 周）

- 7.0.1 `engines/shared/models/administrative.py` 最小版
- 7.0.2 `admin_penalty` 第一个子类型端到端
- 7.0.3 report_generation v3 行政模板分叉
- **Blast radius**：~30 文件

#### Batch 7.1：Administrative Expansion（2 周）

- 7.1.1 `info_disclosure`
- 7.1.2 `work_injury_recognition`（与现有 labor_dispute 的协同集成）
- **Blast radius**：~30 文件

### 批次依赖图

```
6.0 Preflight ──┬──> 6.1 Criminal Foundation ──> 6.2 Criminal Expansion
                │
                └──> 7.0 Admin Foundation ──> 7.1 Admin Expansion
```

6.1 和 7.0 可以**并行**，但强烈**不建议** —— 因为人力上下文切换成本高于并行收益。串行执行更安全。

---

## 问题 8：时间估算

### 三档估算

| 批次 | Optimistic | Realistic | Pessimistic |
|---|---|---|---|
| 6.0 Preflight（含 vocab 研究） | 2 周（10 工作日） | 3 周（15 工作日） | 5 周（25 工作日） |
| 6.1 Criminal Foundation | 2 周 | 3 周 | 5 周 |
| 6.2 Criminal Expansion（2 子类型） | 2 周 | 3 周 | 4 周 |
| 7.0 Admin Foundation | 2 周 | 3 周 | 5 周 |
| 7.1 Admin Expansion（2 子类型） | 2 周 | 3 周 | 4 周 |
| **合计** | **10 周** | **15 周** | **23 周** |

换算成对话 turn（基于 Batch 5 的节奏：约 40-60 turn 完成一个类似 6.1 规模的 batch）：
- **Optimistic**：~200 turn
- **Realistic**：~300 turn
- **Pessimistic**：~450 turn

### 估算的假设和风险

**Optimistic 假设**：
- vocab 研究一次通过，不需要返工
- prompt 调优每个子类型不超过 2 轮
- `amount_calculator` 解耦能干净完成，无连锁回归
- 对抗评审每批只需要一轮

**Pessimistic 场景**：
- vocab 研究需要人工法律专家介入多轮（这是最可能发生的）
- `ProcedurePhase` 扩展触发 Batch 4 级别的全局回归
- `amount_calculator` 解耦涉及 civil pipeline 的意外依赖
- criminal 和 admin 报告模板需要重新设计（v4 模板）

**最可能的瓶颈**：**不是写代码，是法律研究的深度和人工 review 的响应速度**。Batch 5 的经验表明，AI 能一晚完成代码，但法律 vocab 的正确性需要人类签字。如果 review 循环是 2-3 天/轮，单个子类型的 wall-clock 时间会显著拉长。

---

## 总结

Layer 4 是一次**案种家族维度**的扩展（从 civil 1 个家族 → civil + criminal + admin 三个家族），总计 6 个新 `PromptProfile` 子类型。与 Batch 5（三 enum 中性化）不同，Layer 4 的主要成本**不在重构已有代码**，而在：

1. **法律研究深度**（6 份 vocab 笔记，需要人工 review）
2. **新领域模型设计**（criminal.py / admin.py 是新创，没有 civil_loan.py 样板可照搬）
3. **17 个引擎 × 6 个子类型 = 102 个 prompt 模块的工程量**（可通过两层继承压缩到 ~40 个 base + ~60 个小 override）
4. **两个绊脚石的前置解耦**（`amount_calculator` + `ProcedurePhase`）

推荐执行路径：**Batch 6.0 Preflight → 6.1 Criminal PoC → 6.2 Criminal 扩展 → 7.0 Admin PoC → 7.1 Admin 扩展**，共 5 个 batch，串行执行，realistic 估算 15 周。

---

## 8 个问题的一句话答案

1. **MVP 子类型**：criminal = 故意伤害 / 盗窃 / 诈骗（暴力/财产/欺诈三原型）；admin = 行政处罚 / 政府信息公开 / 工伤认定（覆盖 >60% 实务案件）。
2. **Engine 清单**：26 个引擎中 8 个 N0（规则驱动，零改动）、12 个 N1（纯加 prompt）、3 个 N2（加 plugin 方法）、1 个 N3（document_assistance 可能升级）、2 个 N4（amount_calculator 硬解耦 + procedure_setup 可能扩 Phase 枚举）。
3. **Model 层**：推荐新建 `criminal.py` + `administrative.py` 两个专属模块；`CaseTypePlugin` Protocol 建议加一个 `case_family()` 方法（必须），其余方法推迟。
4. **领域词汇**：需要研究 11 个权威法律文件（刑法/刑诉法/行诉法 + 6 部司法解释 + 2 部行政法规），交付 6 份 vocab 笔记。
5. **Prompt 工程量**：天真估算 102 个新 prompt 模块（~20k 行），通过两层继承可压缩到 ~40 base + 60 override（~11k 行）。
6. **测试**：新增约 100 个单元/E2E 测试 + 6-12 个 golden case，需修改约 30-40 个现有测试文件，最终测试数预期 2500+。
7. **风险 + 批次**：3 个 Critical 风险（amount_calculator 耦合、ProcedurePhase 枚举、prompt 质量无 unit test 保证）、7 个 Important；criminal 和 admin 必须分开，推荐 5 个 batch 串行。
8. **时间**：realistic 15 周 / optimistic 10 周 / pessimistic 23 周，最可能瓶颈是法律 vocab 的人工 review 循环而非代码实现。

---

## 最大的未决问题

**Layer 4 的前置解耦（Batch 6.0）是否能被压缩到 1 周以内？**

这个问题决定了整个 Layer 4 能否快速启动。三个子问题：

1. `amount_calculator` 的 civil_loan 硬编码到底有多深？—— 需要实际读代码验证，不是从 Explore 报告里能得到答案。
2. `ProcedurePhase` 枚举的使用点是否可以被 `allowed_procedure_phases()` plugin 方法一次性吸收？—— 需要 grep 所有 `phase ==` / `phase in` 模式。
3. `CaseTypePlugin` Protocol 扩展能否不破坏 Batch 5 刚建立的契约？—— 理论上可以（加方法不减方法），但需要核对所有实现了 `CaseTypePlugin` 的类是否都会被新方法触到。

如果这三个问题的答案都是"能"，Batch 6.0 能在 2 周内完成，整个 Layer 4 的 realistic 估算可以下调到 **12-13 周**；如果任何一个答案是"不能"或"需要深度重构"，Layer 4 的起跑线会被推迟 2-4 周，且需要重新评估批次拆分。

**建议**：在正式开 Batch 6.0 之前，先做一次 1-2 天的 **"绊脚石勘探"** 子任务，专门回答上述三个子问题，然后再决定 Batch 6.0 的范围和 kickoff 时间。
</stdin>
codex
Reviewing the attached plan as a hostile design review. I’m loading the adversarial document-review skill first, then I’ll map concrete failure modes against the nine dimensions and cite the plan precisely.
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "Get-Content -Path 'C:/Users/david/.codex/skills/adversarial-document-reviewer/SKILL.md'" in C:/Users/david/dev/case-adversarial-engine
 succeeded in 562ms:
---
name: adversarial-document-reviewer
description: Conditional document-review persona, selected when the document has >5 requirements or implementation units, makes significant architectural decisions, covers high-stakes domains, or proposes new abstractions. Challenges premises, surfaces unstated assumptions, and stress-tests decisions rather than evaluating document quality.
---

# Adversarial Reviewer

You challenge plans by trying to falsify them. Where other reviewers evaluate whether a document is clear, consistent, or feasible, you ask whether it's *right* -- whether the premises hold, the assumptions are warranted, and the decisions would survive contact with reality. You construct counterarguments, not checklists.

## Depth calibration

Before reviewing, estimate the size, complexity, and risk of the document.

**Size estimate:** Estimate the word count and count distinct requirements or implementation units from the document content.

**Risk signals:** Scan for domain keywords -- authentication, authorization, payment, billing, data migration, compliance, external API, personally identifiable information, cryptography. Also check for proposals of new abstractions, frameworks, or significant architectural patterns.

Select your depth:

- **Quick** (under 1000 words or fewer than 5 requirements, no risk signals): Run premise challenging + simplification pressure only. Produce at most 3 findings.
- **Standard** (medium document, moderate complexity): Run premise challenging + assumption surfacing + decision stress-testing + simplification pressure. Produce findings proportional to the document's decision density.
- **Deep** (over 3000 words or more than 10 requirements, or high-stakes domain): Run all five techniques including alternative blindness. Run multiple passes over major decisions. Trace assumption chains across sections.

## Analysis protocol

### 1. Premise challenging

Question whether the stated problem is the real problem and whether the goals are well-chosen.

- **Problem-solution mismatch** -- the document says the goal is X, but the requirements described actually solve Y. Which is it? Are the stated goals the right goals, or are they inherited assumptions from the conversation that produced the document?
- **Success criteria skepticism** -- would meeting every stated success criterion actually solve the stated problem? Or could all criteria pass while the real problem remains?
- **Framing effects** -- is the problem framed in a way that artificially narrows the solution space? Would reframing the problem lead to a fundamentally different approach?

### 2. Assumption surfacing

Force unstated assumptions into the open by finding claims that depend on conditions never stated or verified.

- **Environmental assumptions** -- the plan assumes a technology, service, or capability exists and works a certain way. Is that stated? What if it's different?
- **User behavior assumptions** -- the plan assumes users will use the feature in a specific way, follow a specific workflow, or have specific knowledge. What if they don't?
- **Scale assumptions** -- the plan is designed for a certain scale (data volume, request rate, team size, user count). What happens at 10x? At 0.1x?
- **Temporal assumptions** -- the plan assumes a certain execution order, timeline, or sequencing. What happens if things happen out of order or take longer than expected?

For each surfaced assumption, describe the specific condition being assumed and the consequence if that assumption is wrong.

### 3. Decision stress-testing

For each major technical or scope decision, construct the conditions under which it becomes the wrong choice.

- **Falsification test** -- what evidence would prove this decision wrong? Is that evidence available now? If no one looked for disconfirming evidence, the decision may be confirmation bias.
- **Reversal cost** -- if this decision turns out to be wrong, how expensive is it to reverse? High reversal cost + low evidence quality = risky decision.
- **Load-bearing decisions** -- which decisions do other decisions depend on? If a load-bearing decision is wrong, everything built on it falls. These deserve the most scrutiny.
- **Decision-scope mismatch** -- is this decision proportional to the problem? A heavyweight solution to a lightweight problem, or a lightweight solution to a heavyweight problem.

### 4. Simplification pressure

Challenge whether the proposed approach is as simple as it could be while still solving the stated problem.

- **Abstraction audit** -- does each proposed abstraction have more than one current consumer? An abstraction with one implementation is speculative complexity.
- **Minimum viable version** -- what is the simplest version that would validate whether this approach works? Is the plan building the final version before validating the approach?
- **Subtraction test** -- for each component, requirement, or implementation unit: what would happen if it were removed? If the answer is "nothing significant," it may not earn its keep.
- **Complexity budget** -- is the total complexity proportional to the problem's actual difficulty, or has the solution accumulated complexity from the exploration process?

### 5. Alternative blindness

Probe whether the document considered the obvious alternatives and whether the choice is well-justified.

- **Omitted alternatives** -- what approaches were not considered? For every "we chose X," ask "why not Y?" If Y is never mentioned, the choice may be path-dependent rather than deliberate.
- **Build vs. use** -- does a solution for this problem already exist (library, framework feature, existing internal tool)? Was it considered?
- **Do-nothing baseline** -- what happens if this plan is not executed? If the consequence of doing nothing is mild, the plan should justify why it's worth the investment.

## Confidence calibration

- **HIGH (0.80+):** Can quote specific text from the document showing the gap, construct a concrete scenario or counterargument, and trace the consequence.
- **MODERATE (0.60-0.79):** The gap is likely but confirming it would require information not in the document (codebase details, user research, production data).
- **Below 0.50:** Suppress.

## What you don't flag

- **Internal contradictions** or terminology drift -- coherence-reviewer owns these
- **Technical feasibility** or architecture conflicts -- feasibility-reviewer owns these
- **Scope-goal alignment** or priority dependency issues -- scope-guardian-reviewer owns these
- **UI/UX quality** or user flow completeness -- design-lens-reviewer owns these
- **Security implications** at plan level -- security-lens-reviewer owns these
- **Product framing** or business justification quality -- product-lens-reviewer owns these

Your territory is the *epistemological quality* of the document -- whether the premises, assumptions, and decisions are warranted, not whether the document is well-structured or technically feasible.
. : File C:\Users\david\Documents\WindowsPowerShell\Microsoft.PowerShell_profile.ps1 cannot be loaded because running 
scripts is disabled on this system. For more information, see about_Execution_Policies at 
https:/go.microsoft.com/fwlink/?LinkID=135170.
At line:1 char:3
+ . 'C:\Users\david\Documents\WindowsPowerShell\Microsoft.PowerShell_pr ...
+   ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : SecurityError: (:) [], PSSecurityException
    + FullyQualifiedErrorId : UnauthorizedAccess
Cannot set property. Property setting is supported only on core types in this language mode.
At line:1 char:1
+ [Console]::OutputEncoding=[System.Text.Encoding]::UTF8;
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : InvalidOperation: (:) [], RuntimeException
    + FullyQualifiedErrorId : PropertySetterNotSupportedInConstrainedLanguage
 

codex
I’ve loaded the review rubric. Next step is pinning the plan’s load-bearing claims to exact sections and line numbers so the findings are specific rather than generic.
2026-04-07T11:27:44.838246Z ERROR codex_core::tools::router: error=`"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -NoProfile -Command "@'
---
date: 2026-04-07
topic: layer-4-criminal-admin-expansion
type: plan
status: draft
author: Claude (plan-only, no code written)
---

# Layer 4 Plan：Criminal + Administrative 案种扩展

> **性质：plan-only 研究报告。** 本文档只回答问题、估算风险和工作量、推荐批次拆分；不写代码、不建 branch、不改源文件。
>
> **上游路线图：** "'`docs/01_product_roadmap.md §未来扩展` 列出了 Criminal Expansion 和 Administrative Expansion 两条未来线；`docs/archive/plans/2026-03-31-ce-brainstorm-phase4-5-assessment.md` 没有 Layer 4 章节（该文档只覆盖 Phase 4-5 的 Unit 12-22）。本计划是上述两条线的首次具体化设计。
>
> **样板参考：** `docs/archive/plans/2026-04-07-batch-5-unit-22-phase-c.md`（三 enum 中性化样板）、`engines/shared/models/civil_loan.py`（物理隔离样板）、`engines/simulation_run/issue_impact_ranker/prompts/*.py`（按案件类型一套 prompt 的样板）。

---

## 0. Layer 4 现状基线与架构发现

Batch 5 合并后（commit `50f28fe`），codebase 有三个关键结构性事实是 Layer 4 设计的前提：

1. **`CaseType` 枚举已经是三家族**：`engines/shared/models/core.py:20-25` 早已定义了
   ```python
   class CaseType(str, Enum):
       civil = "civil"
       criminal = "criminal"
       admin = "admin"
   ```
   但代码里**几乎没有任何地方**实际引用 `CaseType.criminal` / `CaseType.admin` 作值——它只是 schema 层占位。

2. **`PromptProfile` 与 `CaseType` 分离**：同一文件 `core.py:28-33`：
   ```python
   class PromptProfile(str, Enum):
       """提示模板 key（engine-level）。NOT a CaseType value."""
       civil_loan = "civil_loan"
       labor_dispute = "labor_dispute"
       real_estate = "real_estate"
   ```
   而且 `PromptProfile` 在整个 `engines/` 下只有 3 处引用（`core.py` 定义 + `__init__.py` 再导出 + `test_prompt_registry.py` 测试）。**真正跑在生产代码里的是裸字符串 `"civil_loan"` 等**，`PromptProfile` 并没有被作为类型约束使用。这是一把双刃剑：好处是加新值成本几乎为零；坏处是没有类型安全作为护栏，打字错误会在运行期才被发现。

3. **`Issue.impact_targets` 已经是 `list[str]`**（Batch 5 Phase C.3 的"不可逆点"）：模型层不再携带案件类型专属词汇，过滤发生在 `issue_impact_ranker` 层。这意味着 Layer 4 加新案种**不再需要改 `Issue` 模型本身** —— 只需要给每个新案种写一个 `ALLOWED_IMPACT_TARGETS` frozenset。

4. **`engines/shared/models/civil_loan.py` 是唯一的案种专属模块**：没有对应的 `labor_dispute.py` 或 `real_estate.py`，因为劳动争议和房屋买卖与民间借贷共用金额计算抽象（`AmountCalculationReport`、`ClaimCalculationEntry` 等）。这个样板可直接套用到 criminal/admin，但要警惕：**criminal 和 admin 的领域对象和"金额"概念差异极大**，照搬可能得不偿失。

5. **现有引擎清单**（来自 Explore agent 的 inventory）：
   - **17 个 engine 需要 Layer 4 prompt 扩展**（有 `prompts/` 子目录 + `PROMPT_REGISTRY`）
   - **8 个 engine 规则驱动，Layer 4 无需改**（`alternative_claim_generator`、`credibility_scorer`、`evidence_gap_roi_ranker`、`hearing_order`、`issue_dependency_graph`、`case_extraction`、`case_extractor`（使用 generic.py）、`similar_case_search`）
   - **1 个特殊引擎 `amount_calculator`**：硬编码 `if case_type == "civil_loan"` 专属逻辑（`calculator.py` 约第 140 行），对 criminal/admin 来说可能完全用不上金额复算，需要额外决策
   - **1 个特殊引擎 `document_assistance`**：`PROMPT_REGISTRY` 是 `(document_type, case_type)` 二元组键，加一个新案种意味着加 **3 × (文档类型数)** 个条目

---

## 问题 1：案种范围与 MVP 子类型

### 推荐的 MVP 子类型

**刑事（criminal）MVP：3 个子类型**

| 子类型 key | 中文 | 刑法条文 | 选它的理由 |
|---|---|---|---|
| `intentional_injury` | 故意伤害罪 | 《刑法》第 234 条 | 暴力犯罪原型；证据链靠伤情鉴定 + 现场证据，Evidence 模型很贴合；常见 Issue（正当防卫、因果关系、伤情等级） |
| `theft` | 盗窃罪 | 《刑法》第 264 条 + 法释〔2013〕8 号 | 财产犯罪原型；有清晰的"金额"概念（数额较大/巨大/特别巨大）—— 这是唯一一个现有 `AmountCalculationReport` 可以浅层复用的刑事子类型 |
| `fraud` | 诈骗罪 | 《刑法》第 266 条 + 法释〔2011〕7 号 | 欺诈原型；与民事合同纠纷有显著交叉（合同诈骗 vs 民事欺诈界限），对 hybrid 案件处理能力是加分项 |

**不选 MVP 的刑事子类型（及原因）**：
- 危险驾驶罪（§133-1）：案情单薄，90% 走速裁程序，分析价值低
- 交通肇事罪（§133）：核心是附带民事赔偿，已被 `civil_loan` / real_estate 部分覆盖
- 贪污受贿（§382/385）：领域知识门槛极高，公诉性质不适合对抗式模拟
- 毒品犯罪（§347）：证据结构特殊（控制下交付、线人），很难对标现有 Evidence 模型

**行政（administrative）MVP：3 个子类型**

| 子类型 key | 中文 | 法律依据 | 选它的理由 |
|---|---|---|---|
| `admin_penalty` | 行政处罚不服 | 《行政诉讼法》§12(1) + 《行政处罚法》 | 行政诉讼最大类（约 40%-50%），罚款/吊销/拘留/没收，"处罚明显不当可变更"（§77）有清晰的裁判方向 |
| `info_disclosure` | 政府信息公开 | 《政府信息公开条例》+ 法释〔2011〕17 号 | 法律框架最清晰的行政案由；请求-答复-诉讼链路规整；争点相对局限（是否属于政府信息、是否豁免、答复是否完整），对 Issue 模型友好 |
| `work_injury_recognition` | 工伤认定 | 《工伤保险条例》+ 法释〔2014〕9 号 | 跨"行政"与"社保"，既是工伤认定决定书的合法性审查，又带民事赔偿色彩；和现有 `labor_dispute` 能形成 natural companion，让用户能处理"工伤→认定→仲裁→赔偿"全链路 |

**不选 MVP 的行政子类型（及原因）**：
- 征地拆迁（《土地管理法》）：政治敏感且法条已经 2019 年改过一轮，案例分歧大
- 行政许可不服：许可门类太多（食品、药品、建设、环评…），每一种都是独立领域
- 行政不作为：争点结构单一（是否具有法定职责 + 是否履行），可能不需要独立 PromptProfile，留给 `admin_penalty` 的 variant 即可

### 推荐范围：刑事 3 + 行政 3 = 6 个新 `PromptProfile` 值

这个数量级保持和当前 civil kernel（3 个 civil 子类型）对称，也为"能不能按案种家族写一个 base prompt，子类型只 override 词汇"的架构选择留出空间。

---

## 问题 2：Engine 适配清单（26 个引擎 × Layer 4 工作量）

评级定义：
- **N0**：不需要改（规则驱动或案种无关）
- **N1**：只需加 prompt 模块 + 注册到 `PROMPT_REGISTRY`
- **N2**：N1 + 需要新的 `ALLOWED_IMPACT_TARGETS` 或 plugin 方法
- **N3**：N1/N2 + 需要新的领域字段或子模型
- **N4**：需要重构现有逻辑（硬编码 civil_loan 假设）

| # | Engine | 目录 | 评级 | 说明 |
|---|---|---|---|---|
| 1 | `action_recommender` | `simulation_run/` | **N1** | 现有 PROMPT_REGISTRY 模式，加 6 个 prompt 文件 |
| 2 | `alternative_claim_generator` | `simulation_run/` | **N0** | 规则驱动 |
| 3 | `attack_chain_optimizer` | `simulation_run/` | **N1** | PROMPT_REGISTRY 模式 |
| 4 | `credibility_scorer` | `simulation_run/` | **N0** | 规则驱动（职业放贷人检测是 civil_loan 专属但已经是可选分支） |
| 5 | `decision_path_tree` | `simulation_run/` | **N1** | PROMPT_REGISTRY 模式 |
| 6 | `defense_chain` | `simulation_run/` | **N1** | PROMPT_REGISTRY 模式 |
| 7 | `evidence_gap_roi_ranker` | `simulation_run/` | **N0** | 规则驱动 |
| 8 | `hearing_order` | `simulation_run/` | **N0** | 规则驱动 |
| 9 | `issue_category_classifier` | `simulation_run/` | **N1** | PROMPT_REGISTRY 模式 |
| 10 | `issue_dependency_graph` | `simulation_run/` | **N0** | 规则驱动 |
| 11 | `issue_impact_ranker` | `simulation_run/` | **N2** ⭐ | 需要 6 个 prompt 文件 + 6 个 ALLOWED_IMPACT_TARGETS + 6 个 few-shot JSON；这是 Layer 4 词汇研究的核心入口 |
| 12 | `case_extractor` | `case_structuring/` | **N0** | 已用 generic.py 一份 prompt 覆盖所有案种 |
| 13 | `admissibility_evaluator` | `case_structuring/` | **N1** | dict-based registry，加 6 个条目 |
| 14 | `amount_calculator` | `case_structuring/` | **N4** ⚠️ | 硬编码 civil_loan 逻辑；criminal/admin 绝大部分情况不需要金额复算；需要决策：(a) 扩展支持盗窃/诈骗的数额认定，(b) 支持行政处罚的罚款数额，或 (c) 在 runner 层直接 bypass |
| 15 | `evidence_indexer` | `case_structuring/` | **N1** | module-based |
| 16 | `evidence_weight_scorer` | `case_structuring/` | **N1** | dict-based |
| 17 | `issue_extractor` | `case_structuring/` | **N1** | module-based |
| 18 | `adversarial` | `engines/` | **N1** | PROMPT_REGISTRY；但刑事的"控辩"和"原被告"语义不同，需要在 prompt 层区分 |
| 19 | `case_extraction` | `engines/` | **N0** | 规则驱动 |
| 20 | `document_assistance` | `engines/` | **N1-N3** ⚠️ | `(doc_type, case_type)` 二元组键；新增 6 案种意味着 6 × (现有 doc_type 数 ≈ 3) = 18 个新条目；可能还要加刑事专属的 `doc_type`（起诉书/辩护词/上诉状）→ 升级到 N3 |
| 21 | `interactive_followup` | `engines/` | **N1** | PROMPT_REGISTRY 模式 |
| 22 | `pretrial_conference` | `engines/` | **N2** ⚠️ | 有 `judge.py` 独立模块；刑事庭前会议（刑诉法 §187）和民事庭前会议结构差异大，可能需要重写 judge.py 的 criminal 分支 |
| 23 | `procedure_setup` | `engines/` | **N2-N3** | 民事诉讼程序和刑事/行政程序不是同一个东西（刑事有侦查/起诉/审判三段式，行政有行政复议前置），procedure_setup 可能需要新增 stage 类型 |
| 24 | `report_generation` | `engines/` | **N1-N2** | PROMPT_REGISTRY；但刑事报告的"量刑建议"章节和民事"胜诉率评估"结构完全不同，v3 模板需要扩展 |
| 25 | `similar_case_search` | `engines/` | **N0** | 案种无关（关键词检索） |
| 26 | `report_generation/v3` | `engines/` (sub) | **N2** | 见 #24，v3 子目录需要对称扩展 |

### 汇总统计

- **N0 不改**：8 个引擎 → 工作量为 0（但可能需要 smoke test 验证新案种下行为一致）
- **N1 纯 prompt**：12 个引擎 → 单案种 1-2 天/engine
- **N2 prompt + plugin 方法**：3 个引擎（`issue_impact_ranker` / `pretrial_conference` / `report_generation`）→ 单案种 3-4 天/engine
- **N3 新领域字段**：1 个引擎（`document_assistance` 升级版）→ 单案种 4-5 天
- **N4 重构**：1 个引擎（`amount_calculator`）→ 一次性重构 5-7 天，独立于具体案种
- **N2/3 混合**：2 个引擎（`procedure_setup` / `report_generation` v3）→ 单案种 3-5 天

### 危险信号

- `amount_calculator` 的 civil_loan 硬耦合是 Layer 4 的**第一个绊脚石**，应当在开始任何案种扩展前作为"Batch 6.0"单独解耦
- `procedure_setup` 可能触发 `ProcedurePhase` 枚举（`core.py:118`）的扩展 —— 当前枚举是针对民事庭审流程设计的（`evidence_submission` / `evidence_challenge` / `judge_questions` / `rebuttal`），刑事的"法庭调查/法庭辩论/最后陈述"和行政的"陈述申辩/听证"可能需要新值

---

## 问题 3：Model 层需求

### 是否需要新的案种专属模块？

**推荐：是，但只创建必需的**。对 Batch 5 样板（`civil_loan.py` 承载了所有与放款/还款/金额复算相关的类型）的照搬没有意义，因为 criminal 和 admin 的领域对象完全不同。

#### `engines/shared/models/criminal.py`（推荐创建）

**承载**：
- `ChargeType`（罪名枚举，MVP 期只有 `intentional_injury` / `theft` / `fraud`；或者设计为 `tuple[str, str]` = (章节, 具体罪名)）
- `CriminalImpactTarget`（枚举或 frozenset，值：`conviction` / `charge_name` / `sentence_length` / `sentence_severity` / `incidental_civil_compensation` / `credibility`）
- `SentencingFactor`（量刑情节：法定/酌定 × 加重/减轻/从重/从轻）
- `ChargeElement`（犯罪构成要件：主体/客体/主观方面/客观方面）—— 可选，看 P0 是否真的需要结构化
- `EvidenceChainStatus`（证据链状态：`exclusive` 排他性认定 / `consistent` 相互印证 / `conflicting` 矛盾 / `insufficient` 不足）
- `IllegalEvidenceExclusionRecord`（非法证据排除记录）

**不承载**：刑事案件的"金额"概念（盗窃数额）应当作为 `Claim.amount` 或专门的 `CriminalAmount` 子类；不建议重用 `civil_loan.AmountCalculationReport`，因为盗窃数额不需要"本金/利息"拆分。

#### `engines/shared/models/administrative.py`（推荐创建）

**承载**：
- `AdminActionType`（被诉行政行为类型：`penalty` / `permit` / `coercion` / `inaction` / `info_disclosure_reply` / `compensation_decision`）
- `LegalBasisCheck`（合法性审查五要素：`authority` 职权 / `procedure` 程序 / `factual_basis` 事实 / `legal_basis` 法律依据 / `discretion` 裁量）
- `AdminReliefType`（判决类型：`revocation` / `declare_illegal` / `order_perform` / `alteration` / `compensation` / `dismiss`）
- `AdminImpactTarget`（枚举或 frozenset：`legality` 合法性 / `procedure_compliance` 程序合规 / `factual_accuracy` 事实认定 / `discretion_reasonableness` 裁量合理性 / `relief_type` 判决类型 / `credibility`）
- `ReconsiderationPrerequisite`（行政复议前置要求）

**不承载**：民事意义上的"赔偿金额"应当走 `state_compensation` 走一个独立的 `StateCompensationClaim`，不混入通用 `Claim`。

### CaseTypePlugin Protocol 需要扩展吗？

**当前 Protocol**（`case_type_plugin.py:42-89`）只有两个方法：
- `get_prompt(engine_name, case_type, context)`
- `allowed_impact_targets(case_type) -> frozenset[str]`

**推荐为 Layer 4 增加的方法**（按优先级排序）：

1. **`case_family(case_type) -> Literal["civil", "criminal", "admin"]`** 🔴 必须
   - 让引擎在不 hard-code 映射表的情况下把 `PromptProfile` 归一到 `CaseType.value`
   - 触发场景：报告生成要显示"本案属于刑事案件"；程序引擎要决定走民诉/刑诉/行诉流程

2. **`allowed_procedure_phases(case_type) -> tuple[ProcedurePhase, ...]`** 🟡 推荐
   - 因为 `ProcedurePhase` 是为民事庭审设计的，刑事/行政的阶段序列不同
   - 避免在每个引擎里重复写 `if case_family == "criminal": phases = [...]`

3. **`allowed_relief_types(case_type) -> frozenset[str]`** 🟢 可选
   - 民事是"判决支持/部分支持/驳回"，刑事是"有罪/无罪/发回"，行政是"撤销/确认违法/驳回"
   - 可以推迟到发现实际需要时再加

4. **`default_burden_allocation(case_type) -> dict[str, str]`** 🟢 可选
   - 刑事是"控方承担举证责任（无罪推定）"，行政是"被告承担主要举证责任"（《行政诉讼法》§34），民事是"谁主张谁举证"
   - 如果 `burden_allocator` 引擎能读到这个默认值，可以省掉每个案种一个 prompt

**推迟决策**：不推荐在 Layer 4 初期就扩展 Protocol，因为 Batch 5 刚刚才把 `allowed_impact_targets` 加进去。应当在 Batch 6.0（amount_calculator 解耦）之后、Batch 6.1（criminal 第一个子类型 PoC）之中再决定要不要加 `case_family()` 这样的方法。

---

## 问题 4：领域词汇研究清单

### 权威来源（要读的文件）

#### 刑事

1. **《中华人民共和国刑法》**（2020 修正版 = 刑法修正案十一）
   - 第二编 分则：§234（故意伤害）、§264（盗窃）、§266（诈骗）
   - 第一编 总则：§13-21（犯罪构成）、§22-26（故意过失）、§61-78（量刑）
2. **《中华人民共和国刑事诉讼法》**（2018 修正版）
   - §5（独立审判）、§12（无罪推定）、§50-56（证据）、§186-202（法庭审理）
3. **最高法 法释〔2021〕1 号**：最高人民法院关于适用《中华人民共和国刑事诉讼法》的解释
4. **各罪专属司法解释**：
   - 故意伤害：法释〔2013〕12 号、〔2015〕9 号（伤情鉴定标准）
   - 盗窃：法释〔2013〕8 号（数额认定）
   - 诈骗：法释〔2011〕7 号、〔2016〕25 号（电信网络诈骗）
5. **最高法指导性案例**（对照 CaseLaw Reasoner 能力）：第 3 号（潘玉梅诈骗）、第 13 号（王召成非法买卖爆炸物，定罪证据链样板）等

#### 行政

1. **《中华人民共和国行政诉讼法》**（2017 修正版）
   - §2-12（受案范围）、§25-27（当事人）、§34（被告举证责任）、§63-80（判决形式）
2. **最高法 法释〔2018〕1 号**：关于适用《中华人民共和国行政诉讼法》的解释
3. **《中华人民共和国行政处罚法》**（2021 修订）
   - §3-5（原则）、§8-15（处罚种类和设定）、§44-65（程序）
4. **《政府信息公开条例》**（2019 修订）+ 法释〔2011〕17 号
5. **《工伤保险条例》**（2010 修订）+ 法释〔2014〕9 号 + 人社部相关规范性文件
6. **《国家赔偿法》**（2012 修正版）— 涉及行政赔偿章节

### 需要研究的词汇维度（每个维度要填一个 frozenset）

| 维度 | civil 参考 | criminal 需查 | admin 需查 |
|---|---|---|---|
| `impact_targets` | principal/interest/penalty/attorney_fee/credibility | conviction / charge / sentence / incidental_civil / credibility | legality / procedure / factual / discretion / relief / credibility |
| `relief_types` | 支持/部分支持/驳回 | 有罪/无罪/发回/不起诉 | 撤销/确认违法/责令履行/变更/赔偿/驳回 |
| `evidence_categories` | 书证/物证/证人/视听/电子/鉴定/勘验 | + 被告人供述 + 被害人陈述 + 辨认笔录 + 侦查实验笔录 | + 行政卷宗 + 被诉行政行为底稿 + 听证记录 |
| `burden_keywords` | 谁主张谁举证 | 无罪推定 / 排除合理怀疑 | 被告举证行政行为合法 |
| `procedure_phases` | case_intake→opening→evidence→judge→rebuttal | 侦查→起诉→一审庭审（法庭调查→法庭辩论→最后陈述）→二审 | 复议前置→起诉→审理→判决 |

### 研究产出物（每个案种）

每个新案种应当产出**一份 vocab 研究笔记**（约 300-500 字），格式：
```
案种：故意伤害罪 (intentional_injury)
上级 CaseType：criminal
法律依据：《刑法》§234 / 法释〔2013〕12 号 / 人体损伤程度鉴定标准（2014）
核心争点类型：
  - 正当防卫与防卫过当的区分
  - 伤情等级认定（轻伤一级/二级、重伤一级/二级）
  - 因果关系（多因一果时的责任分配）
  - 故意 vs 过失（故意伤害 vs 过失致人重伤）
ALLOWED_IMPACT_TARGETS 候选：
  - conviction（定罪与否）
  - charge（罪名选择）
  - sentence_length（刑期长短）
  - sentence_severity（是否实刑/缓刑）
  - incidental_civil_compensation（附带民事赔偿金额）
  - credibility（可信度枢轴）
量刑情节（SentencingFactor）候选：
  法定：自首、立功、累犯、未成年人、限制责任能力…
  酌定：认罪认罚、退赃退赔、赔偿谅解、犯罪前科…
```

6 份这样的笔记（3 criminal + 3 admin）= Layer 4 的词汇研究交付物。

---

## 问题 5：Prompt 工程量估算

### 天真的全量估算（每个子类型一套 prompt）

- **17 个 N1+ 引擎 × 6 个新子类型 = 102 个新 prompt 模块**
- 每个模块平均 200 行 → **约 20,000 行新 prompt 代码**
- 加上 6 个 `issue_impact_ranker.{case_type}.json` few-shot 文件（约 50 行/文件）

这是**上限**。实际工程量可以显著压缩：

### 推荐：两层 prompt 继承策略

**层 1：案种家族 base prompt**
- 每个引擎每个家族一份：
  - `prompts/_criminal_base.py` — 刑事通用 system prompt + 通用 build_user_prompt
  - `prompts/_admin_base.py` — 行政通用 system prompt + 通用 build_user_prompt
- 覆盖 80% 通用结构（案件基本信息、证据清单、争点列表渲染）

**层 2：案种 override**
- 每个引擎每个子类型一份，但只定义变化部分：
  - `ALLOWED_IMPACT_TARGETS`（frozenset）
  - `DOMAIN_SPECIFIC_HINT`（案种专属 prompt 段落注入 base system prompt）
  - 可选的 `build_user_prompt` 覆盖（仅当需要专属 context 块）

**压缩后估算**：
- 17 个引擎 × 2 个 base（criminal base + admin base） = **34 个 base prompt 模块**
- 17 个引擎 × 6 个 subtype override = **102 个 override 文件，但平均只有 30-50 行**
- 总代码量 ≈ 34 × 200 + 102 × 40 = **约 10,880 行** （砍掉 ~45%）

### Few-shot 文件

- `issue_impact_ranker`：6 个新文件（critical，决定词汇过滤）
- `adversarial_plaintiff` / `adversarial_defendant`：**可能**需要按 criminal/admin 拆分，因为"控方/辩方"语义和"原告/被告"不一样；估 2 个新文件
- `defense_chain`：可能需要 criminal-specific（非法证据排除辩护 vs 民事合同无效辩护）；估 1 个新文件
- **合计 9 个新 few-shot JSON**（每个 50-100 行 = 450-900 行 JSON）

### Prompt 迭代成本

法律类 prompt 的**调优**通常比首写更费时间。根据 Batch 5 的经验（labor_dispute / real_estate 从对抗评审中暴露"例子和词汇不一致"的问题），每个新子类型的 prompt 在首次跑通后还需要 **2-3 轮 LLM-in-the-loop 调优**才能达到 civil_loan 的质量基线。这部分成本**不在代码行数里**，但是 Layer 4 最容易被低估的工作量。

---

## 问题 6：Test / Fixture / Golden 估算

### 现有测试状态（Batch 5 合并后）

- **2408 passed** on main
- **266 处**测试源文件中出现 `civil_loan` / `labor_dispute` / `real_estate` 字符串
- 约 **85 个测试文件**提到案件类型

### 新增测试估算

#### 单元测试（每个新子类型）

| 测试对象 | 每子类型新增数 | 6 个子类型合计 |
|---|---|---|
| 新 prompt 模块（build_user_prompt 结构） | ~3 | 18 |
| 新 ALLOWED_IMPACT_TARGETS（vocab lock-step） | ~2 | 12 |
| 新 few-shot JSON（example 与 vocab 一致） | ~2 | 12 |
| 新 model 类（criminal.py / administrative.py 的 pydantic 验证） | ~5-10（仅两个家族） | 10-20 |
| ranker `_resolve_impact_targets` 对新 vocab 过滤 | ~2 | 12 |
| CaseTypePlugin `allowed_impact_targets` 对新 case_type | ~1 | 6 |

**单元测试合计：约 70-80 个新测试**

#### 契约测试 / 参数化现有测试

- `test_prompt_registry.py` 需要扩展 `PromptProfile` 参数化 → +6 个 parametrize 展开
- `test_case_type_plugin.py` 需要为每个新案种跑一遍 UnsupportedCaseTypeError 反向测试 → +6 个
- 每个 N1+ 引擎的 `test_*.py`（如果当前是 hardcode `case_type="civil_loan"`）需要参数化 → **约 25-35 个测试文件需要重写**

#### E2E 测试（pipeline 穿透）

- 每个新子类型需要一条端到端 smoke test（输入 fixture → 跑完整 pipeline → 断言关键产物）
- 6 个新子类型 = **6 条新 E2E**
- 每条 E2E 需要一个 case fixture（模拟起诉书/判决书文本）+ golden output

#### Golden 文件

- `benchmarks/golden_outputs/` 当前有若干 civil 案例
- 每个新子类型需要 **1-2 个 golden case**（最小规模）
- 合计 **6-12 个新 golden case**

#### 受影响的现有测试

估计 **30-40 个现有测试文件需要更新**（主要是参数化、增加新 case_type 到 parametrize 列表、调整硬编码断言）。**不会破坏**的测试：所有使用 `LLM_MOCK=true` 的 unit test（约 2000+ 个），因为它们是 case_type-agnostic 的断言。

**总测试增量估算**：
- 新增：80 unit + 6 E2E + 12 golden ≈ **100 个新测试**
- 修改：30-40 个现有文件
- **预期最终测试数**：2408 → ~2500+

---

## 问题 7：风险 + 批次拆分

### 风险清单

#### 🔴 Critical

1. **`amount_calculator` 民事硬耦合** — 如果不先解耦，criminal/admin 引擎在 pipeline 层会被绊倒。**缓解**：Batch 6.0 专门解耦，在任何案种扩展前完成。

2. **`ProcedurePhase` 枚举不兼容** — 当前枚举只覆盖民事庭审阶段。刑事"法庭调查/法庭辩论/最后陈述"和行政"陈述申辩/听证"不在里面。如果 `procedure_setup` 或 `pretrial_conference` 访问了 phase 的具体值，扩展会引起回归。**缓解**：Batch 6.0 同时审查 `ProcedurePhase` 的所有使用点，决定是扩枚举还是让 `allowed_procedure_phases()` plugin 方法接管。

3. **Prompt 质量无法被单元测试保证** — LLM 输出在 `LLM_MOCK=true` 下是 mock 的，真实的 criminal/admin prompt 质量只能靠人工 review 和昂贵的 live LLM eval。如果没有 eval harness，每个子类型在生产环境都可能翻车。**缓解**：Batch 6.0 前置建立一个最小的 `benchmarks/layer4_eval/` 框架，至少每个新子类型有 3 个真实 LLM-driven 的 smoke test（打开 LLM live 标志运行）。

#### 🟡 Important

4. **`document_assistance` 的 (doc_type × case_type) 组合爆炸** — 刑事文书类型（起诉书/辩护词/上诉状/量刑建议书）和民事文书完全不同。如果每个组合都写独立 prompt，工程量会翻倍。**缓解**：Batch 6.0 前调研是否要从"组合键"切换到"工厂函数"模式。

5. **`adversarial` 引擎的"原被告"vs"控辩"语义错配** — `adversarial_plaintiff.json` / `adversarial_defendant.json` 的 few-shot 示例是民事语境。刑事的"控方/辩方"有完全不同的策略空间（控方不需要"诉请"，辩方有"罪轻辩护/无罪辩护"二选一）。**缓解**：criminal batch 需要一次性重写 adversarial 的 few-shot。

6. **`report_generation/v3` 模板分叉** — v3 模板是为民事对抗报告设计的（胜诉率评估、调解区间等已被删除）。刑事报告需要"量刑建议"章节，行政报告需要"合法性审查结论"章节。**缓解**：v3 需要三份并行的 section template，不能共用一份。

7. **研究深度不足导致设计返工** — 6 个新子类型的法律研究如果不到位，模型字段和 prompt 结构都会在编码过程中被推翻。**缓解**：Batch 6.0 前置一个纯研究 sprint（1-2 周），交付 6 份 vocab 研究笔记 + 模型字段草案，经过人类法律专家 review 后才开写代码。

#### 🟢 Minor

8. **Test 爆炸半径** — 现有 85 个提案件类型的测试文件，参数化成本不大但有 review 负担。
9. **CLI/API 层面的 case_type 参数暴露** — 需要更新 help text、API schema（OpenAPI）、CLI validation 列表。
10. **文档和 README 更新** — 低优先级但不可忽略。

### 批次拆分建议

**Criminal 和 administrative 应当完全分开，不能混合。** 理由：

- 两者领域模型差异巨大（criminal.py / admin.py 没有代码复用空间）
- 两者 vocab 研究不能互相参考（引用的法条完全不同）
- 两者的 prompt 调优回路独立，混在一个 batch 里会造成注意力分散和回归风险
- 批次越大，爆炸半径越大（Batch 5 的经验：一个 6 commit 的 batch 已经到了 adversarial review 能稳定审完的上限）

**建议的批次序列**：

#### Batch 6.0：Layer 4 Preflight（2 周）

**目标**：解耦和基础设施，不落地任何具体案种
- 6.0.1 解耦 `amount_calculator` 的 civil_loan 硬编码（让 pipeline 能跳过金额复算）
- 6.0.2 审查 `ProcedurePhase` 使用点，必要时扩展枚举或加 `allowed_procedure_phases()`
- 6.0.3 `CaseTypePlugin` Protocol 扩展：加 `case_family(case_type)` 方法
- 6.0.4 建立 `benchmarks/layer4_eval/` 最小 eval harness
- 6.0.5 完成 6 份 vocab 研究笔记（交付物 markdown，不碰代码）
- **Blast radius**：~10 文件，~30 测试
- **Gate**：人工 review vocab 笔记并签字

#### Batch 6.1：Criminal Foundation（2-3 周）

**目标**：criminal 第一个子类型跑通端到端
- 6.1.1 `engines/shared/models/criminal.py` 最小版（ChargeType、CriminalImpactTarget、SentencingFactor）
- 6.1.2 `intentional_injury` 的 `_criminal_base` + override prompt × 17 引擎
- 6.1.3 `issue_impact_ranker.intentional_injury.json` few-shot
- 6.1.4 端到端 smoke test + 1 个 golden case
- **Blast radius**：~30 文件，~40 新测试
- **Gate**：smoke test 在 LLM live 模式下通过

#### Batch 6.2：Criminal Expansion（2 周）

- 6.2.1 `theft` 子类型（包括对 amount_calculator 的可选扩展，支持盗窃数额认定）
- 6.2.2 `fraud` 子类型
- 6.2.3 adversarial few-shot 刑事化重写
- **Blast radius**：~40 文件

#### Batch 7.0：Administrative Foundation（2-3 周）

- 7.0.1 `engines/shared/models/administrative.py` 最小版
- 7.0.2 `admin_penalty` 第一个子类型端到端
- 7.0.3 report_generation v3 行政模板分叉
- **Blast radius**：~30 文件

#### Batch 7.1：Administrative Expansion（2 周）

- 7.1.1 `info_disclosure`
- 7.1.2 `work_injury_recognition`（与现有 labor_dispute 的协同集成）
- **Blast radius**：~30 文件

### 批次依赖图

```
6.0 Preflight ──┬──> 6.1 Criminal Foundation ──> 6.2 Criminal Expansion
                │
                └──> 7.0 Admin Foundation ──> 7.1 Admin Expansion
```

6.1 和 7.0 可以**并行**，但强烈**不建议** —— 因为人力上下文切换成本高于并行收益。串行执行更安全。

---

## 问题 8：时间估算

### 三档估算

| 批次 | Optimistic | Realistic | Pessimistic |
|---|---|---|---|
| 6.0 Preflight（含 vocab 研究） | 2 周（10 工作日） | 3 周（15 工作日） | 5 周（25 工作日） |
| 6.1 Criminal Foundation | 2 周 | 3 周 | 5 周 |
| 6.2 Criminal Expansion（2 子类型） | 2 周 | 3 周 | 4 周 |
| 7.0 Admin Foundation | 2 周 | 3 周 | 5 周 |
| 7.1 Admin Expansion（2 子类型） | 2 周 | 3 周 | 4 周 |
| **合计** | **10 周** | **15 周** | **23 周** |

换算成对话 turn（基于 Batch 5 的节奏：约 40-60 turn 完成一个类似 6.1 规模的 batch）：
- **Optimistic**：~200 turn
- **Realistic**：~300 turn
- **Pessimistic**：~450 turn

### 估算的假设和风险

**Optimistic 假设**：
- vocab 研究一次通过，不需要返工
- prompt 调优每个子类型不超过 2 轮
- `amount_calculator` 解耦能干净完成，无连锁回归
- 对抗评审每批只需要一轮

**Pessimistic 场景**：
- vocab 研究需要人工法律专家介入多轮（这是最可能发生的）
- `ProcedurePhase` 扩展触发 Batch 4 级别的全局回归
- `amount_calculator` 解耦涉及 civil pipeline 的意外依赖
- criminal 和 admin 报告模板需要重新设计（v4 模板）

**最可能的瓶颈**：**不是写代码，是法律研究的深度和人工 review 的响应速度**。Batch 5 的经验表明，AI 能一晚完成代码，但法律 vocab 的正确性需要人类签字。如果 review 循环是 2-3 天/轮，单个子类型的 wall-clock 时间会显著拉长。

---

## 总结

Layer 4 是一次**案种家族维度**的扩展（从 civil 1 个家族 → civil + criminal + admin 三个家族），总计 6 个新 `PromptProfile` 子类型。与 Batch 5（三 enum 中性化）不同，Layer 4 的主要成本**不在重构已有代码**，而在：

1. **法律研究深度**（6 份 vocab 笔记，需要人工 review）
2. **新领域模型设计**（criminal.py / admin.py 是新创，没有 civil_loan.py 样板可照搬）
3. **17 个引擎 × 6 个子类型 = 102 个 prompt 模块的工程量**（可通过两层继承压缩到 ~40 个 base + ~60 个小 override）
4. **两个绊脚石的前置解耦**（`amount_calculator` + `ProcedurePhase`）

推荐执行路径：**Batch 6.0 Preflight → 6.1 Criminal PoC → 6.2 Criminal 扩展 → 7.0 Admin PoC → 7.1 Admin 扩展**，共 5 个 batch，串行执行，realistic 估算 15 周。

---

## 8 个问题的一句话答案

1. **MVP 子类型**：criminal = 故意伤害 / 盗窃 / 诈骗（暴力/财产/欺诈三原型）；admin = 行政处罚 / 政府信息公开 / 工伤认定（覆盖 >60% 实务案件）。
2. **Engine 清单**：26 个引擎中 8 个 N0（规则驱动，零改动）、12 个 N1（纯加 prompt）、3 个 N2（加 plugin 方法）、1 个 N3（document_assistance 可能升级）、2 个 N4（amount_calculator 硬解耦 + procedure_setup 可能扩 Phase 枚举）。
3. **Model 层**：推荐新建 `criminal.py` + `administrative.py` 两个专属模块；`CaseTypePlugin` Protocol 建议加一个 `case_family()` 方法（必须），其余方法推迟。
4. **领域词汇**：需要研究 11 个权威法律文件（刑法/刑诉法/行诉法 + 6 部司法解释 + 2 部行政法规），交付 6 份 vocab 笔记。
5. **Prompt 工程量**：天真估算 102 个新 prompt 模块（~20k 行），通过两层继承可压缩到 ~40 base + 60 override（~11k 行）。
6. **测试**：新增约 100 个单元/E2E 测试 + 6-12 个 golden case，需修改约 30-40 个现有测试文件，最终测试数预期 2500+。
7. **风险 + 批次**：3 个 Critical 风险（amount_calculator 耦合、ProcedurePhase 枚举、prompt 质量无 unit test 保证）、7 个 Important；criminal 和 admin 必须分开，推荐 5 个 batch 串行。
8. **时间**：realistic 15 周 / optimistic 10 周 / pessimistic 23 周，最可能瓶颈是法律 vocab 的人工 review 循环而非代码实现。

---

## 最大的未决问题

**Layer 4 的前置解耦（Batch 6.0）是否能被压缩到 1 周以内？**

这个问题决定了整个 Layer 4 能否快速启动。三个子问题：

1. `amount_calculator` 的 civil_loan 硬编码到底有多深？—— 需要实际读代码验证，不是从 Explore 报告里能得到答案。
2. `ProcedurePhase` 枚举的使用点是否可以被 `allowed_procedure_phases()` plugin 方法一次性吸收？—— 需要 grep 所有 `phase ==` / `phase in` 模式。
3. `CaseTypePlugin` Protocol 扩展能否不破坏 Batch 5 刚建立的契约？—— 理论上可以（加方法不减方法），但需要核对所有实现了 `CaseTypePlugin` 的类是否都会被新方法触到。

如果这三个问题的答案都是"能"，Batch 6.0 能在 2 周内完成，整个 Layer 4 的 realistic 估算可以下调到 **12-13 周**；如果任何一个答案是"不能"或"需要深度重构"，Layer 4 的起跑线会被推迟 2-4 周，且需要重新评估批次拆分。

**建议**：在正式开 Batch 6.0 之前，先做一次 1-2 天的 **"绊脚石勘探"** 子任务，专门回答上述三个子问题，然后再决定 Batch 6.0 的范围和 kickoff 时间。
'"'@ | python -c \"import sys; text=sys.stdin.read().splitlines();
for i,line in enumerate(text,1):
    print(f'{i:4} {line}')\""` rejected: blocked by policy
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -NoProfile -Command "@'
---
date: 2026-04-07
topic: layer-4-criminal-admin-expansion
type: plan
status: draft
author: Claude (plan-only, no code written)
---

# Layer 4 Plan：Criminal + Administrative 案种扩展

> **性质：plan-only 研究报告。** 本文档只回答问题、估算风险和工作量、推荐批次拆分；不写代码、不建 branch、不改源文件。
>
> **上游路线图：** "'`docs/01_product_roadmap.md §未来扩展` 列出了 Criminal Expansion 和 Administrative Expansion 两条未来线；`docs/archive/plans/2026-03-31-ce-brainstorm-phase4-5-assessment.md` 没有 Layer 4 章节（该文档只覆盖 Phase 4-5 的 Unit 12-22）。本计划是上述两条线的首次具体化设计。
>
> **样板参考：** `docs/archive/plans/2026-04-07-batch-5-unit-22-phase-c.md`（三 enum 中性化样板）、`engines/shared/models/civil_loan.py`（物理隔离样板）、`engines/simulation_run/issue_impact_ranker/prompts/*.py`（按案件类型一套 prompt 的样板）。

---

## 0. Layer 4 现状基线与架构发现

Batch 5 合并后（commit `50f28fe`），codebase 有三个关键结构性事实是 Layer 4 设计的前提：

1. **`CaseType` 枚举已经是三家族**：`engines/shared/models/core.py:20-25` 早已定义了
   ```python
   class CaseType(str, Enum):
       civil = "civil"
       criminal = "criminal"
       admin = "admin"
   ```
   但代码里**几乎没有任何地方**实际引用 `CaseType.criminal` / `CaseType.admin` 作值——它只是 schema 层占位。

2. **`PromptProfile` 与 `CaseType` 分离**：同一文件 `core.py:28-33`：
   ```python
   class PromptProfile(str, Enum):
       """提示模板 key（engine-level）。NOT a CaseType value."""
       civil_loan = "civil_loan"
       labor_dispute = "labor_dispute"
       real_estate = "real_estate"
   ```
   而且 `PromptProfile` 在整个 `engines/` 下只有 3 处引用（`core.py` 定义 + `__init__.py` 再导出 + `test_prompt_registry.py` 测试）。**真正跑在生产代码里的是裸字符串 `"civil_loan"` 等**，`PromptProfile` 并没有被作为类型约束使用。这是一把双刃剑：好处是加新值成本几乎为零；坏处是没有类型安全作为护栏，打字错误会在运行期才被发现。

3. **`Issue.impact_targets` 已经是 `list[str]`**（Batch 5 Phase C.3 的"不可逆点"）：模型层不再携带案件类型专属词汇，过滤发生在 `issue_impact_ranker` 层。这意味着 Layer 4 加新案种**不再需要改 `Issue` 模型本身** —— 只需要给每个新案种写一个 `ALLOWED_IMPACT_TARGETS` frozenset。

4. **`engines/shared/models/civil_loan.py` 是唯一的案种专属模块**：没有对应的 `labor_dispute.py` 或 `real_estate.py`，因为劳动争议和房屋买卖与民间借贷共用金额计算抽象（`AmountCalculationReport`、`ClaimCalculationEntry` 等）。这个样板可直接套用到 criminal/admin，但要警惕：**criminal 和 admin 的领域对象和"金额"概念差异极大**，照搬可能得不偿失。

5. **现有引擎清单**（来自 Explore agent 的 inventory）：
   - **17 个 engine 需要 Layer 4 prompt 扩展**（有 `prompts/` 子目录 + `PROMPT_REGISTRY`）
   - **8 个 engine 规则驱动，Layer 4 无需改**（`alternative_claim_generator`、`credibility_scorer`、`evidence_gap_roi_ranker`、`hearing_order`、`issue_dependency_graph`、`case_extraction`、`case_extractor`（使用 generic.py）、`similar_case_search`）
   - **1 个特殊引擎 `amount_calculator`**：硬编码 `if case_type == "civil_loan"` 专属逻辑（`calculator.py` 约第 140 行），对 criminal/admin 来说可能完全用不上金额复算，需要额外决策
   - **1 个特殊引擎 `document_assistance`**：`PROMPT_REGISTRY` 是 `(document_type, case_type)` 二元组键，加一个新案种意味着加 **3 × (文档类型数)** 个条目

---

## 问题 1：案种范围与 MVP 子类型

### 推荐的 MVP 子类型

**刑事（criminal）MVP：3 个子类型**

| 子类型 key | 中文 | 刑法条文 | 选它的理由 |
|---|---|---|---|
| `intentional_injury` | 故意伤害罪 | 《刑法》第 234 条 | 暴力犯罪原型；证据链靠伤情鉴定 + 现场证据，Evidence 模型很贴合；常见 Issue（正当防卫、因果关系、伤情等级） |
| `theft` | 盗窃罪 | 《刑法》第 264 条 + 法释〔2013〕8 号 | 财产犯罪原型；有清晰的"金额"概念（数额较大/巨大/特别巨大）—— 这是唯一一个现有 `AmountCalculationReport` 可以浅层复用的刑事子类型 |
| `fraud` | 诈骗罪 | 《刑法》第 266 条 + 法释〔2011〕7 号 | 欺诈原型；与民事合同纠纷有显著交叉（合同诈骗 vs 民事欺诈界限），对 hybrid 案件处理能力是加分项 |

**不选 MVP 的刑事子类型（及原因）**：
- 危险驾驶罪（§133-1）：案情单薄，90% 走速裁程序，分析价值低
- 交通肇事罪（§133）：核心是附带民事赔偿，已被 `civil_loan` / real_estate 部分覆盖
- 贪污受贿（§382/385）：领域知识门槛极高，公诉性质不适合对抗式模拟
- 毒品犯罪（§347）：证据结构特殊（控制下交付、线人），很难对标现有 Evidence 模型

**行政（administrative）MVP：3 个子类型**

| 子类型 key | 中文 | 法律依据 | 选它的理由 |
|---|---|---|---|
| `admin_penalty` | 行政处罚不服 | 《行政诉讼法》§12(1) + 《行政处罚法》 | 行政诉讼最大类（约 40%-50%），罚款/吊销/拘留/没收，"处罚明显不当可变更"（§77）有清晰的裁判方向 |
| `info_disclosure` | 政府信息公开 | 《政府信息公开条例》+ 法释〔2011〕17 号 | 法律框架最清晰的行政案由；请求-答复-诉讼链路规整；争点相对局限（是否属于政府信息、是否豁免、答复是否完整），对 Issue 模型友好 |
| `work_injury_recognition` | 工伤认定 | 《工伤保险条例》+ 法释〔2014〕9 号 | 跨"行政"与"社保"，既是工伤认定决定书的合法性审查，又带民事赔偿色彩；和现有 `labor_dispute` 能形成 natural companion，让用户能处理"工伤→认定→仲裁→赔偿"全链路 |

**不选 MVP 的行政子类型（及原因）**：
- 征地拆迁（《土地管理法》）：政治敏感且法条已经 2019 年改过一轮，案例分歧大
- 行政许可不服：许可门类太多（食品、药品、建设、环评…），每一种都是独立领域
- 行政不作为：争点结构单一（是否具有法定职责 + 是否履行），可能不需要独立 PromptProfile，留给 `admin_penalty` 的 variant 即可

### 推荐范围：刑事 3 + 行政 3 = 6 个新 `PromptProfile` 值

这个数量级保持和当前 civil kernel（3 个 civil 子类型）对称，也为"能不能按案种家族写一个 base prompt，子类型只 override 词汇"的架构选择留出空间。

---

## 问题 2：Engine 适配清单（26 个引擎 × Layer 4 工作量）

评级定义：
- **N0**：不需要改（规则驱动或案种无关）
- **N1**：只需加 prompt 模块 + 注册到 `PROMPT_REGISTRY`
- **N2**：N1 + 需要新的 `ALLOWED_IMPACT_TARGETS` 或 plugin 方法
- **N3**：N1/N2 + 需要新的领域字段或子模型
- **N4**：需要重构现有逻辑（硬编码 civil_loan 假设）

| # | Engine | 目录 | 评级 | 说明 |
|---|---|---|---|---|
| 1 | `action_recommender` | `simulation_run/` | **N1** | 现有 PROMPT_REGISTRY 模式，加 6 个 prompt 文件 |
| 2 | `alternative_claim_generator` | `simulation_run/` | **N0** | 规则驱动 |
| 3 | `attack_chain_optimizer` | `simulation_run/` | **N1** | PROMPT_REGISTRY 模式 |
| 4 | `credibility_scorer` | `simulation_run/` | **N0** | 规则驱动（职业放贷人检测是 civil_loan 专属但已经是可选分支） |
| 5 | `decision_path_tree` | `simulation_run/` | **N1** | PROMPT_REGISTRY 模式 |
| 6 | `defense_chain` | `simulation_run/` | **N1** | PROMPT_REGISTRY 模式 |
| 7 | `evidence_gap_roi_ranker` | `simulation_run/` | **N0** | 规则驱动 |
| 8 | `hearing_order` | `simulation_run/` | **N0** | 规则驱动 |
| 9 | `issue_category_classifier` | `simulation_run/` | **N1** | PROMPT_REGISTRY 模式 |
| 10 | `issue_dependency_graph` | `simulation_run/` | **N0** | 规则驱动 |
| 11 | `issue_impact_ranker` | `simulation_run/` | **N2** ⭐ | 需要 6 个 prompt 文件 + 6 个 ALLOWED_IMPACT_TARGETS + 6 个 few-shot JSON；这是 Layer 4 词汇研究的核心入口 |
| 12 | `case_extractor` | `case_structuring/` | **N0** | 已用 generic.py 一份 prompt 覆盖所有案种 |
| 13 | `admissibility_evaluator` | `case_structuring/` | **N1** | dict-based registry，加 6 个条目 |
| 14 | `amount_calculator` | `case_structuring/` | **N4** ⚠️ | 硬编码 civil_loan 逻辑；criminal/admin 绝大部分情况不需要金额复算；需要决策：(a) 扩展支持盗窃/诈骗的数额认定，(b) 支持行政处罚的罚款数额，或 (c) 在 runner 层直接 bypass |
| 15 | `evidence_indexer` | `case_structuring/` | **N1** | module-based |
| 16 | `evidence_weight_scorer` | `case_structuring/` | **N1** | dict-based |
| 17 | `issue_extractor` | `case_structuring/` | **N1** | module-based |
| 18 | `adversarial` | `engines/` | **N1** | PROMPT_REGISTRY；但刑事的"控辩"和"原被告"语义不同，需要在 prompt 层区分 |
| 19 | `case_extraction` | `engines/` | **N0** | 规则驱动 |
| 20 | `document_assistance` | `engines/` | **N1-N3** ⚠️ | `(doc_type, case_type)` 二元组键；新增 6 案种意味着 6 × (现有 doc_type 数 ≈ 3) = 18 个新条目；可能还要加刑事专属的 `doc_type`（起诉书/辩护词/上诉状）→ 升级到 N3 |
| 21 | `interactive_followup` | `engines/` | **N1** | PROMPT_REGISTRY 模式 |
| 22 | `pretrial_conference` | `engines/` | **N2** ⚠️ | 有 `judge.py` 独立模块；刑事庭前会议（刑诉法 §187）和民事庭前会议结构差异大，可能需要重写 judge.py 的 criminal 分支 |
| 23 | `procedure_setup` | `engines/` | **N2-N3** | 民事诉讼程序和刑事/行政程序不是同一个东西（刑事有侦查/起诉/审判三段式，行政有行政复议前置），procedure_setup 可能需要新增 stage 类型 |
| 24 | `report_generation` | `engines/` | **N1-N2** | PROMPT_REGISTRY；但刑事报告的"量刑建议"章节和民事"胜诉率评估"结构完全不同，v3 模板需要扩展 |
| 25 | `similar_case_search` | `engines/` | **N0** | 案种无关（关键词检索） |
| 26 | `report_generation/v3` | `engines/` (sub) | **N2** | 见 #24，v3 子目录需要对称扩展 |

### 汇总统计

- **N0 不改**：8 个引擎 → 工作量为 0（但可能需要 smoke test 验证新案种下行为一致）
- **N1 纯 prompt**：12 个引擎 → 单案种 1-2 天/engine
- **N2 prompt + plugin 方法**：3 个引擎（`issue_impact_ranker` / `pretrial_conference` / `report_generation`）→ 单案种 3-4 天/engine
- **N3 新领域字段**：1 个引擎（`document_assistance` 升级版）→ 单案种 4-5 天
- **N4 重构**：1 个引擎（`amount_calculator`）→ 一次性重构 5-7 天，独立于具体案种
- **N2/3 混合**：2 个引擎（`procedure_setup` / `report_generation` v3）→ 单案种 3-5 天

### 危险信号

- `amount_calculator` 的 civil_loan 硬耦合是 Layer 4 的**第一个绊脚石**，应当在开始任何案种扩展前作为"Batch 6.0"单独解耦
- `procedure_setup` 可能触发 `ProcedurePhase` 枚举（`core.py:118`）的扩展 —— 当前枚举是针对民事庭审流程设计的（`evidence_submission` / `evidence_challenge` / `judge_questions` / `rebuttal`），刑事的"法庭调查/法庭辩论/最后陈述"和行政的"陈述申辩/听证"可能需要新值

---

## 问题 3：Model 层需求

### 是否需要新的案种专属模块？

**推荐：是，但只创建必需的**。对 Batch 5 样板（`civil_loan.py` 承载了所有与放款/还款/金额复算相关的类型）的照搬没有意义，因为 criminal 和 admin 的领域对象完全不同。

#### `engines/shared/models/criminal.py`（推荐创建）

**承载**：
- `ChargeType`（罪名枚举，MVP 期只有 `intentional_injury` / `theft` / `fraud`；或者设计为 `tuple[str, str]` = (章节, 具体罪名)）
- `CriminalImpactTarget`（枚举或 frozenset，值：`conviction` / `charge_name` / `sentence_length` / `sentence_severity` / `incidental_civil_compensation` / `credibility`）
- `SentencingFactor`（量刑情节：法定/酌定 × 加重/减轻/从重/从轻）
- `ChargeElement`（犯罪构成要件：主体/客体/主观方面/客观方面）—— 可选，看 P0 是否真的需要结构化
- `EvidenceChainStatus`（证据链状态：`exclusive` 排他性认定 / `consistent` 相互印证 / `conflicting` 矛盾 / `insufficient` 不足）
- `IllegalEvidenceExclusionRecord`（非法证据排除记录）

**不承载**：刑事案件的"金额"概念（盗窃数额）应当作为 `Claim.amount` 或专门的 `CriminalAmount` 子类；不建议重用 `civil_loan.AmountCalculationReport`，因为盗窃数额不需要"本金/利息"拆分。

#### `engines/shared/models/administrative.py`（推荐创建）

**承载**：
- `AdminActionType`（被诉行政行为类型：`penalty` / `permit` / `coercion` / `inaction` / `info_disclosure_reply` / `compensation_decision`）
- `LegalBasisCheck`（合法性审查五要素：`authority` 职权 / `procedure` 程序 / `factual_basis` 事实 / `legal_basis` 法律依据 / `discretion` 裁量）
- `AdminReliefType`（判决类型：`revocation` / `declare_illegal` / `order_perform` / `alteration` / `compensation` / `dismiss`）
- `AdminImpactTarget`（枚举或 frozenset：`legality` 合法性 / `procedure_compliance` 程序合规 / `factual_accuracy` 事实认定 / `discretion_reasonableness` 裁量合理性 / `relief_type` 判决类型 / `credibility`）
- `ReconsiderationPrerequisite`（行政复议前置要求）

**不承载**：民事意义上的"赔偿金额"应当走 `state_compensation` 走一个独立的 `StateCompensationClaim`，不混入通用 `Claim`。

### CaseTypePlugin Protocol 需要扩展吗？

**当前 Protocol**（`case_type_plugin.py:42-89`）只有两个方法：
- `get_prompt(engine_name, case_type, context)`
- `allowed_impact_targets(case_type) -> frozenset[str]`

**推荐为 Layer 4 增加的方法**（按优先级排序）：

1. **`case_family(case_type) -> Literal["civil", "criminal", "admin"]`** 🔴 必须
   - 让引擎在不 hard-code 映射表的情况下把 `PromptProfile` 归一到 `CaseType.value`
   - 触发场景：报告生成要显示"本案属于刑事案件"；程序引擎要决定走民诉/刑诉/行诉流程

2. **`allowed_procedure_phases(case_type) -> tuple[ProcedurePhase, ...]`** 🟡 推荐
   - 因为 `ProcedurePhase` 是为民事庭审设计的，刑事/行政的阶段序列不同
   - 避免在每个引擎里重复写 `if case_family == "criminal": phases = [...]`

3. **`allowed_relief_types(case_type) -> frozenset[str]`** 🟢 可选
   - 民事是"判决支持/部分支持/驳回"，刑事是"有罪/无罪/发回"，行政是"撤销/确认违法/驳回"
   - 可以推迟到发现实际需要时再加

4. **`default_burden_allocation(case_type) -> dict[str, str]`** 🟢 可选
   - 刑事是"控方承担举证责任（无罪推定）"，行政是"被告承担主要举证责任"（《行政诉讼法》§34），民事是"谁主张谁举证"
   - 如果 `burden_allocator` 引擎能读到这个默认值，可以省掉每个案种一个 prompt

**推迟决策**：不推荐在 Layer 4 初期就扩展 Protocol，因为 Batch 5 刚刚才把 `allowed_impact_targets` 加进去。应当在 Batch 6.0（amount_calculator 解耦）之后、Batch 6.1（criminal 第一个子类型 PoC）之中再决定要不要加 `case_family()` 这样的方法。

---

## 问题 4：领域词汇研究清单

### 权威来源（要读的文件）

#### 刑事

1. **《中华人民共和国刑法》**（2020 修正版 = 刑法修正案十一）
   - 第二编 分则：§234（故意伤害）、§264（盗窃）、§266（诈骗）
   - 第一编 总则：§13-21（犯罪构成）、§22-26（故意过失）、§61-78（量刑）
2. **《中华人民共和国刑事诉讼法》**（2018 修正版）
   - §5（独立审判）、§12（无罪推定）、§50-56（证据）、§186-202（法庭审理）
3. **最高法 法释〔2021〕1 号**：最高人民法院关于适用《中华人民共和国刑事诉讼法》的解释
4. **各罪专属司法解释**：
   - 故意伤害：法释〔2013〕12 号、〔2015〕9 号（伤情鉴定标准）
   - 盗窃：法释〔2013〕8 号（数额认定）
   - 诈骗：法释〔2011〕7 号、〔2016〕25 号（电信网络诈骗）
5. **最高法指导性案例**（对照 CaseLaw Reasoner 能力）：第 3 号（潘玉梅诈骗）、第 13 号（王召成非法买卖爆炸物，定罪证据链样板）等

#### 行政

1. **《中华人民共和国行政诉讼法》**（2017 修正版）
   - §2-12（受案范围）、§25-27（当事人）、§34（被告举证责任）、§63-80（判决形式）
2. **最高法 法释〔2018〕1 号**：关于适用《中华人民共和国行政诉讼法》的解释
3. **《中华人民共和国行政处罚法》**（2021 修订）
   - §3-5（原则）、§8-15（处罚种类和设定）、§44-65（程序）
4. **《政府信息公开条例》**（2019 修订）+ 法释〔2011〕17 号
5. **《工伤保险条例》**（2010 修订）+ 法释〔2014〕9 号 + 人社部相关规范性文件
6. **《国家赔偿法》**（2012 修正版）— 涉及行政赔偿章节

### 需要研究的词汇维度（每个维度要填一个 frozenset）

| 维度 | civil 参考 | criminal 需查 | admin 需查 |
|---|---|---|---|
| `impact_targets` | principal/interest/penalty/attorney_fee/credibility | conviction / charge / sentence / incidental_civil / credibility | legality / procedure / factual / discretion / relief / credibility |
| `relief_types` | 支持/部分支持/驳回 | 有罪/无罪/发回/不起诉 | 撤销/确认违法/责令履行/变更/赔偿/驳回 |
| `evidence_categories` | 书证/物证/证人/视听/电子/鉴定/勘验 | + 被告人供述 + 被害人陈述 + 辨认笔录 + 侦查实验笔录 | + 行政卷宗 + 被诉行政行为底稿 + 听证记录 |
| `burden_keywords` | 谁主张谁举证 | 无罪推定 / 排除合理怀疑 | 被告举证行政行为合法 |
| `procedure_phases` | case_intake→opening→evidence→judge→rebuttal | 侦查→起诉→一审庭审（法庭调查→法庭辩论→最后陈述）→二审 | 复议前置→起诉→审理→判决 |

### 研究产出物（每个案种）

每个新案种应当产出**一份 vocab 研究笔记**（约 300-500 字），格式：
```
案种：故意伤害罪 (intentional_injury)
上级 CaseType：criminal
法律依据：《刑法》§234 / 法释〔2013〕12 号 / 人体损伤程度鉴定标准（2014）
核心争点类型：
  - 正当防卫与防卫过当的区分
  - 伤情等级认定（轻伤一级/二级、重伤一级/二级）
  - 因果关系（多因一果时的责任分配）
  - 故意 vs 过失（故意伤害 vs 过失致人重伤）
ALLOWED_IMPACT_TARGETS 候选：
  - conviction（定罪与否）
  - charge（罪名选择）
  - sentence_length（刑期长短）
  - sentence_severity（是否实刑/缓刑）
  - incidental_civil_compensation（附带民事赔偿金额）
  - credibility（可信度枢轴）
量刑情节（SentencingFactor）候选：
  法定：自首、立功、累犯、未成年人、限制责任能力…
  酌定：认罪认罚、退赃退赔、赔偿谅解、犯罪前科…
```

6 份这样的笔记（3 criminal + 3 admin）= Layer 4 的词汇研究交付物。

---

## 问题 5：Prompt 工程量估算

### 天真的全量估算（每个子类型一套 prompt）

- **17 个 N1+ 引擎 × 6 个新子类型 = 102 个新 prompt 模块**
- 每个模块平均 200 行 → **约 20,000 行新 prompt 代码**
- 加上 6 个 `issue_impact_ranker.{case_type}.json` few-shot 文件（约 50 行/文件）

这是**上限**。实际工程量可以显著压缩：

### 推荐：两层 prompt 继承策略

**层 1：案种家族 base prompt**
- 每个引擎每个家族一份：
  - `prompts/_criminal_base.py` — 刑事通用 system prompt + 通用 build_user_prompt
  - `prompts/_admin_base.py` — 行政通用 system prompt + 通用 build_user_prompt
- 覆盖 80% 通用结构（案件基本信息、证据清单、争点列表渲染）

**层 2：案种 override**
- 每个引擎每个子类型一份，但只定义变化部分：
  - `ALLOWED_IMPACT_TARGETS`（frozenset）
  - `DOMAIN_SPECIFIC_HINT`（案种专属 prompt 段落注入 base system prompt）
  - 可选的 `build_user_prompt` 覆盖（仅当需要专属 context 块）

**压缩后估算**：
- 17 个引擎 × 2 个 base（criminal base + admin base） = **34 个 base prompt 模块**
- 17 个引擎 × 6 个 subtype override = **102 个 override 文件，但平均只有 30-50 行**
- 总代码量 ≈ 34 × 200 + 102 × 40 = **约 10,880 行** （砍掉 ~45%）

### Few-shot 文件

- `issue_impact_ranker`：6 个新文件（critical，决定词汇过滤）
- `adversarial_plaintiff` / `adversarial_defendant`：**可能**需要按 criminal/admin 拆分，因为"控方/辩方"语义和"原告/被告"不一样；估 2 个新文件
- `defense_chain`：可能需要 criminal-specific（非法证据排除辩护 vs 民事合同无效辩护）；估 1 个新文件
- **合计 9 个新 few-shot JSON**（每个 50-100 行 = 450-900 行 JSON）

### Prompt 迭代成本

法律类 prompt 的**调优**通常比首写更费时间。根据 Batch 5 的经验（labor_dispute / real_estate 从对抗评审中暴露"例子和词汇不一致"的问题），每个新子类型的 prompt 在首次跑通后还需要 **2-3 轮 LLM-in-the-loop 调优**才能达到 civil_loan 的质量基线。这部分成本**不在代码行数里**，但是 Layer 4 最容易被低估的工作量。

---

## 问题 6：Test / Fixture / Golden 估算

### 现有测试状态（Batch 5 合并后）

- **2408 passed** on main
- **266 处**测试源文件中出现 `civil_loan` / `labor_dispute` / `real_estate` 字符串
- 约 **85 个测试文件**提到案件类型

### 新增测试估算

#### 单元测试（每个新子类型）

| 测试对象 | 每子类型新增数 | 6 个子类型合计 |
|---|---|---|
| 新 prompt 模块（build_user_prompt 结构） | ~3 | 18 |
| 新 ALLOWED_IMPACT_TARGETS（vocab lock-step） | ~2 | 12 |
| 新 few-shot JSON（example 与 vocab 一致） | ~2 | 12 |
| 新 model 类（criminal.py / administrative.py 的 pydantic 验证） | ~5-10（仅两个家族） | 10-20 |
| ranker `_resolve_impact_targets` 对新 vocab 过滤 | ~2 | 12 |
| CaseTypePlugin `allowed_impact_targets` 对新 case_type | ~1 | 6 |

**单元测试合计：约 70-80 个新测试**

#### 契约测试 / 参数化现有测试

- `test_prompt_registry.py` 需要扩展 `PromptProfile` 参数化 → +6 个 parametrize 展开
- `test_case_type_plugin.py` 需要为每个新案种跑一遍 UnsupportedCaseTypeError 反向测试 → +6 个
- 每个 N1+ 引擎的 `test_*.py`（如果当前是 hardcode `case_type="civil_loan"`）需要参数化 → **约 25-35 个测试文件需要重写**

#### E2E 测试（pipeline 穿透）

- 每个新子类型需要一条端到端 smoke test（输入 fixture → 跑完整 pipeline → 断言关键产物）
- 6 个新子类型 = **6 条新 E2E**
- 每条 E2E 需要一个 case fixture（模拟起诉书/判决书文本）+ golden output

#### Golden 文件

- `benchmarks/golden_outputs/` 当前有若干 civil 案例
- 每个新子类型需要 **1-2 个 golden case**（最小规模）
- 合计 **6-12 个新 golden case**

#### 受影响的现有测试

估计 **30-40 个现有测试文件需要更新**（主要是参数化、增加新 case_type 到 parametrize 列表、调整硬编码断言）。**不会破坏**的测试：所有使用 `LLM_MOCK=true` 的 unit test（约 2000+ 个），因为它们是 case_type-agnostic 的断言。

**总测试增量估算**：
- 新增：80 unit + 6 E2E + 12 golden ≈ **100 个新测试**
- 修改：30-40 个现有文件
- **预期最终测试数**：2408 → ~2500+

---

## 问题 7：风险 + 批次拆分

### 风险清单

#### 🔴 Critical

1. **`amount_calculator` 民事硬耦合** — 如果不先解耦，criminal/admin 引擎在 pipeline 层会被绊倒。**缓解**：Batch 6.0 专门解耦，在任何案种扩展前完成。

2. **`ProcedurePhase` 枚举不兼容** — 当前枚举只覆盖民事庭审阶段。刑事"法庭调查/法庭辩论/最后陈述"和行政"陈述申辩/听证"不在里面。如果 `procedure_setup` 或 `pretrial_conference` 访问了 phase 的具体值，扩展会引起回归。**缓解**：Batch 6.0 同时审查 `ProcedurePhase` 的所有使用点，决定是扩枚举还是让 `allowed_procedure_phases()` plugin 方法接管。

3. **Prompt 质量无法被单元测试保证** — LLM 输出在 `LLM_MOCK=true` 下是 mock 的，真实的 criminal/admin prompt 质量只能靠人工 review 和昂贵的 live LLM eval。如果没有 eval harness，每个子类型在生产环境都可能翻车。**缓解**：Batch 6.0 前置建立一个最小的 `benchmarks/layer4_eval/` 框架，至少每个新子类型有 3 个真实 LLM-driven 的 smoke test（打开 LLM live 标志运行）。

#### 🟡 Important

4. **`document_assistance` 的 (doc_type × case_type) 组合爆炸** — 刑事文书类型（起诉书/辩护词/上诉状/量刑建议书）和民事文书完全不同。如果每个组合都写独立 prompt，工程量会翻倍。**缓解**：Batch 6.0 前调研是否要从"组合键"切换到"工厂函数"模式。

5. **`adversarial` 引擎的"原被告"vs"控辩"语义错配** — `adversarial_plaintiff.json` / `adversarial_defendant.json` 的 few-shot 示例是民事语境。刑事的"控方/辩方"有完全不同的策略空间（控方不需要"诉请"，辩方有"罪轻辩护/无罪辩护"二选一）。**缓解**：criminal batch 需要一次性重写 adversarial 的 few-shot。

6. **`report_generation/v3` 模板分叉** — v3 模板是为民事对抗报告设计的（胜诉率评估、调解区间等已被删除）。刑事报告需要"量刑建议"章节，行政报告需要"合法性审查结论"章节。**缓解**：v3 需要三份并行的 section template，不能共用一份。

7. **研究深度不足导致设计返工** — 6 个新子类型的法律研究如果不到位，模型字段和 prompt 结构都会在编码过程中被推翻。**缓解**：Batch 6.0 前置一个纯研究 sprint（1-2 周），交付 6 份 vocab 研究笔记 + 模型字段草案，经过人类法律专家 review 后才开写代码。

#### 🟢 Minor

8. **Test 爆炸半径** — 现有 85 个提案件类型的测试文件，参数化成本不大但有 review 负担。
9. **CLI/API 层面的 case_type 参数暴露** — 需要更新 help text、API schema（OpenAPI）、CLI validation 列表。
10. **文档和 README 更新** — 低优先级但不可忽略。

### 批次拆分建议

**Criminal 和 administrative 应当完全分开，不能混合。** 理由：

- 两者领域模型差异巨大（criminal.py / admin.py 没有代码复用空间）
- 两者 vocab 研究不能互相参考（引用的法条完全不同）
- 两者的 prompt 调优回路独立，混在一个 batch 里会造成注意力分散和回归风险
- 批次越大，爆炸半径越大（Batch 5 的经验：一个 6 commit 的 batch 已经到了 adversarial review 能稳定审完的上限）

**建议的批次序列**：

#### Batch 6.0：Layer 4 Preflight（2 周）

**目标**：解耦和基础设施，不落地任何具体案种
- 6.0.1 解耦 `amount_calculator` 的 civil_loan 硬编码（让 pipeline 能跳过金额复算）
- 6.0.2 审查 `ProcedurePhase` 使用点，必要时扩展枚举或加 `allowed_procedure_phases()`
- 6.0.3 `CaseTypePlugin` Protocol 扩展：加 `case_family(case_type)` 方法
- 6.0.4 建立 `benchmarks/layer4_eval/` 最小 eval harness
- 6.0.5 完成 6 份 vocab 研究笔记（交付物 markdown，不碰代码）
- **Blast radius**：~10 文件，~30 测试
- **Gate**：人工 review vocab 笔记并签字

#### Batch 6.1：Criminal Foundation（2-3 周）

**目标**：criminal 第一个子类型跑通端到端
- 6.1.1 `engines/shared/models/criminal.py` 最小版（ChargeType、CriminalImpactTarget、SentencingFactor）
- 6.1.2 `intentional_injury` 的 `_criminal_base` + override prompt × 17 引擎
- 6.1.3 `issue_impact_ranker.intentional_injury.json` few-shot
- 6.1.4 端到端 smoke test + 1 个 golden case
- **Blast radius**：~30 文件，~40 新测试
- **Gate**：smoke test 在 LLM live 模式下通过

#### Batch 6.2：Criminal Expansion（2 周）

- 6.2.1 `theft` 子类型（包括对 amount_calculator 的可选扩展，支持盗窃数额认定）
- 6.2.2 `fraud` 子类型
- 6.2.3 adversarial few-shot 刑事化重写
- **Blast radius**：~40 文件

#### Batch 7.0：Administrative Foundation（2-3 周）

- 7.0.1 `engines/shared/models/administrative.py` 最小版
- 7.0.2 `admin_penalty` 第一个子类型端到端
- 7.0.3 report_generation v3 行政模板分叉
- **Blast radius**：~30 文件

#### Batch 7.1：Administrative Expansion（2 周）

- 7.1.1 `info_disclosure`
- 7.1.2 `work_injury_recognition`（与现有 labor_dispute 的协同集成）
- **Blast radius**：~30 文件

### 批次依赖图

```
6.0 Preflight ──┬──> 6.1 Criminal Foundation ──> 6.2 Criminal Expansion
                │
                └──> 7.0 Admin Foundation ──> 7.1 Admin Expansion
```

6.1 和 7.0 可以**并行**，但强烈**不建议** —— 因为人力上下文切换成本高于并行收益。串行执行更安全。

---

## 问题 8：时间估算

### 三档估算

| 批次 | Optimistic | Realistic | Pessimistic |
|---|---|---|---|
| 6.0 Preflight（含 vocab 研究） | 2 周（10 工作日） | 3 周（15 工作日） | 5 周（25 工作日） |
| 6.1 Criminal Foundation | 2 周 | 3 周 | 5 周 |
| 6.2 Criminal Expansion（2 子类型） | 2 周 | 3 周 | 4 周 |
| 7.0 Admin Foundation | 2 周 | 3 周 | 5 周 |
| 7.1 Admin Expansion（2 子类型） | 2 周 | 3 周 | 4 周 |
| **合计** | **10 周** | **15 周** | **23 周** |

换算成对话 turn（基于 Batch 5 的节奏：约 40-60 turn 完成一个类似 6.1 规模的 batch）：
- **Optimistic**：~200 turn
- **Realistic**：~300 turn
- **Pessimistic**：~450 turn

### 估算的假设和风险

**Optimistic 假设**：
- vocab 研究一次通过，不需要返工
- prompt 调优每个子类型不超过 2 轮
- `amount_calculator` 解耦能干净完成，无连锁回归
- 对抗评审每批只需要一轮

**Pessimistic 场景**：
- vocab 研究需要人工法律专家介入多轮（这是最可能发生的）
- `ProcedurePhase` 扩展触发 Batch 4 级别的全局回归
- `amount_calculator` 解耦涉及 civil pipeline 的意外依赖
- criminal 和 admin 报告模板需要重新设计（v4 模板）

**最可能的瓶颈**：**不是写代码，是法律研究的深度和人工 review 的响应速度**。Batch 5 的经验表明，AI 能一晚完成代码，但法律 vocab 的正确性需要人类签字。如果 review 循环是 2-3 天/轮，单个子类型的 wall-clock 时间会显著拉长。

---

## 总结

Layer 4 是一次**案种家族维度**的扩展（从 civil 1 个家族 → civil + criminal + admin 三个家族），总计 6 个新 `PromptProfile` 子类型。与 Batch 5（三 enum 中性化）不同，Layer 4 的主要成本**不在重构已有代码**，而在：

1. **法律研究深度**（6 份 vocab 笔记，需要人工 review）
2. **新领域模型设计**（criminal.py / admin.py 是新创，没有 civil_loan.py 样板可照搬）
3. **17 个引擎 × 6 个子类型 = 102 个 prompt 模块的工程量**（可通过两层继承压缩到 ~40 个 base + ~60 个小 override）
4. **两个绊脚石的前置解耦**（`amount_calculator` + `ProcedurePhase`）

推荐执行路径：**Batch 6.0 Preflight → 6.1 Criminal PoC → 6.2 Criminal 扩展 → 7.0 Admin PoC → 7.1 Admin 扩展**，共 5 个 batch，串行执行，realistic 估算 15 周。

---

## 8 个问题的一句话答案

1. **MVP 子类型**：criminal = 故意伤害 / 盗窃 / 诈骗（暴力/财产/欺诈三原型）；admin = 行政处罚 / 政府信息公开 / 工伤认定（覆盖 >60% 实务案件）。
2. **Engine 清单**：26 个引擎中 8 个 N0（规则驱动，零改动）、12 个 N1（纯加 prompt）、3 个 N2（加 plugin 方法）、1 个 N3（document_assistance 可能升级）、2 个 N4（amount_calculator 硬解耦 + procedure_setup 可能扩 Phase 枚举）。
3. **Model 层**：推荐新建 `criminal.py` + `administrative.py` 两个专属模块；`CaseTypePlugin` Protocol 建议加一个 `case_family()` 方法（必须），其余方法推迟。
4. **领域词汇**：需要研究 11 个权威法律文件（刑法/刑诉法/行诉法 + 6 部司法解释 + 2 部行政法规），交付 6 份 vocab 笔记。
5. **Prompt 工程量**：天真估算 102 个新 prompt 模块（~20k 行），通过两层继承可压缩到 ~40 base + 60 override（~11k 行）。
6. **测试**：新增约 100 个单元/E2E 测试 + 6-12 个 golden case，需修改约 30-40 个现有测试文件，最终测试数预期 2500+。
7. **风险 + 批次**：3 个 Critical 风险（amount_calculator 耦合、ProcedurePhase 枚举、prompt 质量无 unit test 保证）、7 个 Important；criminal 和 admin 必须分开，推荐 5 个 batch 串行。
8. **时间**：realistic 15 周 / optimistic 10 周 / pessimistic 23 周，最可能瓶颈是法律 vocab 的人工 review 循环而非代码实现。

---

## 最大的未决问题

**Layer 4 的前置解耦（Batch 6.0）是否能被压缩到 1 周以内？**

这个问题决定了整个 Layer 4 能否快速启动。三个子问题：

1. `amount_calculator` 的 civil_loan 硬编码到底有多深？—— 需要实际读代码验证，不是从 Explore 报告里能得到答案。
2. `ProcedurePhase` 枚举的使用点是否可以被 `allowed_procedure_phases()` plugin 方法一次性吸收？—— 需要 grep 所有 `phase ==` / `phase in` 模式。
3. `CaseTypePlugin` Protocol 扩展能否不破坏 Batch 5 刚建立的契约？—— 理论上可以（加方法不减方法），但需要核对所有实现了 `CaseTypePlugin` 的类是否都会被新方法触到。

如果这三个问题的答案都是"能"，Batch 6.0 能在 2 周内完成，整个 Layer 4 的 realistic 估算可以下调到 **12-13 周**；如果任何一个答案是"不能"或"需要深度重构"，Layer 4 的起跑线会被推迟 2-4 周，且需要重新评估批次拆分。

**建议**：在正式开 Batch 6.0 之前，先做一次 1-2 天的 **"绊脚石勘探"** 子任务，专门回答上述三个子问题，然后再决定 Batch 6.0 的范围和 kickoff 时间。
'"'@ | python -c \"import sys; text=sys.stdin.read().splitlines();
for i,line in enumerate(text,1):
    print(f'{i:4} {line}')\"" in C:/Users/david/dev/case-adversarial-engine
 declined in 0ms:
`"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -NoProfile -Command "@'
---
date: 2026-04-07
topic: layer-4-criminal-admin-expansion
type: plan
status: draft
author: Claude (plan-only, no code written)
---

# Layer 4 Plan：Criminal + Administrative 案种扩展

> **性质：plan-only 研究报告。** 本文档只回答问题、估算风险和工作量、推荐批次拆分；不写代码、不建 branch、不改源文件。
>
> **上游路线图：** "'`docs/01_product_roadmap.md §未来扩展` 列出了 Criminal Expansion 和 Administrative Expansion 两条未来线；`docs/archive/plans/2026-03-31-ce-brainstorm-phase4-5-assessment.md` 没有 Layer 4 章节（该文档只覆盖 Phase 4-5 的 Unit 12-22）。本计划是上述两条线的首次具体化设计。
>
> **样板参考：** `docs/archive/plans/2026-04-07-batch-5-unit-22-phase-c.md`（三 enum 中性化样板）、`engines/shared/models/civil_loan.py`（物理隔离样板）、`engines/simulation_run/issue_impact_ranker/prompts/*.py`（按案件类型一套 prompt 的样板）。

---

## 0. Layer 4 现状基线与架构发现

Batch 5 合并后（commit `50f28fe`），codebase 有三个关键结构性事实是 Layer 4 设计的前提：

1. **`CaseType` 枚举已经是三家族**：`engines/shared/models/core.py:20-25` 早已定义了
   ```python
   class CaseType(str, Enum):
       civil = "civil"
       criminal = "criminal"
       admin = "admin"
   ```
   但代码里**几乎没有任何地方**实际引用 `CaseType.criminal` / `CaseType.admin` 作值——它只是 schema 层占位。

2. **`PromptProfile` 与 `CaseType` 分离**：同一文件 `core.py:28-33`：
   ```python
   class PromptProfile(str, Enum):
       """提示模板 key（engine-level）。NOT a CaseType value."""
       civil_loan = "civil_loan"
       labor_dispute = "labor_dispute"
       real_estate = "real_estate"
   ```
   而且 `PromptProfile` 在整个 `engines/` 下只有 3 处引用（`core.py` 定义 + `__init__.py` 再导出 + `test_prompt_registry.py` 测试）。**真正跑在生产代码里的是裸字符串 `"civil_loan"` 等**，`PromptProfile` 并没有被作为类型约束使用。这是一把双刃剑：好处是加新值成本几乎为零；坏处是没有类型安全作为护栏，打字错误会在运行期才被发现。

3. **`Issue.impact_targets` 已经是 `list[str]`**（Batch 5 Phase C.3 的"不可逆点"）：模型层不再携带案件类型专属词汇，过滤发生在 `issue_impact_ranker` 层。这意味着 Layer 4 加新案种**不再需要改 `Issue` 模型本身** —— 只需要给每个新案种写一个 `ALLOWED_IMPACT_TARGETS` frozenset。

4. **`engines/shared/models/civil_loan.py` 是唯一的案种专属模块**：没有对应的 `labor_dispute.py` 或 `real_estate.py`，因为劳动争议和房屋买卖与民间借贷共用金额计算抽象（`AmountCalculationReport`、`ClaimCalculationEntry` 等）。这个样板可直接套用到 criminal/admin，但要警惕：**criminal 和 admin 的领域对象和"金额"概念差异极大**，照搬可能得不偿失。

5. **现有引擎清单**（来自 Explore agent 的 inventory）：
   - **17 个 engine 需要 Layer 4 prompt 扩展**（有 `prompts/` 子目录 + `PROMPT_REGISTRY`）
   - **8 个 engine 规则驱动，Layer 4 无需改**（`alternative_claim_generator`、`credibility_scorer`、`evidence_gap_roi_ranker`、`hearing_order`、`issue_dependency_graph`、`case_extraction`、`case_extractor`（使用 generic.py）、`similar_case_search`）
   - **1 个特殊引擎 `amount_calculator`**：硬编码 `if case_type == "civil_loan"` 专属逻辑（`calculator.py` 约第 140 行），对 criminal/admin 来说可能完全用不上金额复算，需要额外决策
   - **1 个特殊引擎 `document_assistance`**：`PROMPT_REGISTRY` 是 `(document_type, case_type)` 二元组键，加一个新案种意味着加 **3 × (文档类型数)** 个条目

---

## 问题 1：案种范围与 MVP 子类型

### 推荐的 MVP 子类型

**刑事（criminal）MVP：3 个子类型**

| 子类型 key | 中文 | 刑法条文 | 选它的理由 |
|---|---|---|---|
| `intentional_injury` | 故意伤害罪 | 《刑法》第 234 条 | 暴力犯罪原型；证据链靠伤情鉴定 + 现场证据，Evidence 模型很贴合；常见 Issue（正当防卫、因果关系、伤情等级） |
| `theft` | 盗窃罪 | 《刑法》第 264 条 + 法释〔2013〕8 号 | 财产犯罪原型；有清晰的"金额"概念（数额较大/巨大/特别巨大）—— 这是唯一一个现有 `AmountCalculationReport` 可以浅层复用的刑事子类型 |
| `fraud` | 诈骗罪 | 《刑法》第 266 条 + 法释〔2011〕7 号 | 欺诈原型；与民事合同纠纷有显著交叉（合同诈骗 vs 民事欺诈界限），对 hybrid 案件处理能力是加分项 |

**不选 MVP 的刑事子类型（及原因）**：
- 危险驾驶罪（§133-1）：案情单薄，90% 走速裁程序，分析价值低
- 交通肇事罪（§133）：核心是附带民事赔偿，已被 `civil_loan` / real_estate 部分覆盖
- 贪污受贿（§382/385）：领域知识门槛极高，公诉性质不适合对抗式模拟
- 毒品犯罪（§347）：证据结构特殊（控制下交付、线人），很难对标现有 Evidence 模型

**行政（administrative）MVP：3 个子类型**

| 子类型 key | 中文 | 法律依据 | 选它的理由 |
|---|---|---|---|
| `admin_penalty` | 行政处罚不服 | 《行政诉讼法》§12(1) + 《行政处罚法》 | 行政诉讼最大类（约 40%-50%），罚款/吊销/拘留/没收，"处罚明显不当可变更"（§77）有清晰的裁判方向 |
| `info_disclosure` | 政府信息公开 | 《政府信息公开条例》+ 法释〔2011〕17 号 | 法律框架最清晰的行政案由；请求-答复-诉讼链路规整；争点相对局限（是否属于政府信息、是否豁免、答复是否完整），对 Issue 模型友好 |
| `work_injury_recognition` | 工伤认定 | 《工伤保险条例》+ 法释〔2014〕9 号 | 跨"行政"与"社保"，既是工伤认定决定书的合法性审查，又带民事赔偿色彩；和现有 `labor_dispute` 能形成 natural companion，让用户能处理"工伤→认定→仲裁→赔偿"全链路 |

**不选 MVP 的行政子类型（及原因）**：
- 征地拆迁（《土地管理法》）：政治敏感且法条已经 2019 年改过一轮，案例分歧大
- 行政许可不服：许可门类太多（食品、药品、建设、环评…），每一种都是独立领域
- 行政不作为：争点结构单一（是否具有法定职责 + 是否履行），可能不需要独立 PromptProfile，留给 `admin_penalty` 的 variant 即可

### 推荐范围：刑事 3 + 行政 3 = 6 个新 `PromptProfile` 值

这个数量级保持和当前 civil kernel（3 个 civil 子类型）对称，也为"能不能按案种家族写一个 base prompt，子类型只 override 词汇"的架构选择留出空间。

---

## 问题 2：Engine 适配清单（26 个引擎 × Layer 4 工作量）

评级定义：
- **N0**：不需要改（规则驱动或案种无关）
- **N1**：只需加 prompt 模块 + 注册到 `PROMPT_REGISTRY`
- **N2**：N1 + 需要新的 `ALLOWED_IMPACT_TARGETS` 或 plugin 方法
- **N3**：N1/N2 + 需要新的领域字段或子模型
- **N4**：需要重构现有逻辑（硬编码 civil_loan 假设）

| # | Engine | 目录 | 评级 | 说明 |
|---|---|---|---|---|
| 1 | `action_recommender` | `simulation_run/` | **N1** | 现有 PROMPT_REGISTRY 模式，加 6 个 prompt 文件 |
| 2 | `alternative_claim_generator` | `simulation_run/` | **N0** | 规则驱动 |
| 3 | `attack_chain_optimizer` | `simulation_run/` | **N1** | PROMPT_REGISTRY 模式 |
| 4 | `credibility_scorer` | `simulation_run/` | **N0** | 规则驱动（职业放贷人检测是 civil_loan 专属但已经是可选分支） |
| 5 | `decision_path_tree` | `simulation_run/` | **N1** | PROMPT_REGISTRY 模式 |
| 6 | `defense_chain` | `simulation_run/` | **N1** | PROMPT_REGISTRY 模式 |
| 7 | `evidence_gap_roi_ranker` | `simulation_run/` | **N0** | 规则驱动 |
| 8 | `hearing_order` | `simulation_run/` | **N0** | 规则驱动 |
| 9 | `issue_category_classifier` | `simulation_run/` | **N1** | PROMPT_REGISTRY 模式 |
| 10 | `issue_dependency_graph` | `simulation_run/` | **N0** | 规则驱动 |
| 11 | `issue_impact_ranker` | `simulation_run/` | **N2** ⭐ | 需要 6 个 prompt 文件 + 6 个 ALLOWED_IMPACT_TARGETS + 6 个 few-shot JSON；这是 Layer 4 词汇研究的核心入口 |
| 12 | `case_extractor` | `case_structuring/` | **N0** | 已用 generic.py 一份 prompt 覆盖所有案种 |
| 13 | `admissibility_evaluator` | `case_structuring/` | **N1** | dict-based registry，加 6 个条目 |
| 14 | `amount_calculator` | `case_structuring/` | **N4** ⚠️ | 硬编码 civil_loan 逻辑；criminal/admin 绝大部分情况不需要金额复算；需要决策：(a) 扩展支持盗窃/诈骗的数额认定，(b) 支持行政处罚的罚款数额，或 (c) 在 runner 层直接 bypass |
| 15 | `evidence_indexer` | `case_structuring/` | **N1** | module-based |
| 16 | `evidence_weight_scorer` | `case_structuring/` | **N1** | dict-based |
| 17 | `issue_extractor` | `case_structuring/` | **N1** | module-based |
| 18 | `adversarial` | `engines/` | **N1** | PROMPT_REGISTRY；但刑事的"控辩"和"原被告"语义不同，需要在 prompt 层区分 |
| 19 | `case_extraction` | `engines/` | **N0** | 规则驱动 |
| 20 | `document_assistance` | `engines/` | **N1-N3** ⚠️ | `(doc_type, case_type)` 二元组键；新增 6 案种意味着 6 × (现有 doc_type 数 ≈ 3) = 18 个新条目；可能还要加刑事专属的 `doc_type`（起诉书/辩护词/上诉状）→ 升级到 N3 |
| 21 | `interactive_followup` | `engines/` | **N1** | PROMPT_REGISTRY 模式 |
| 22 | `pretrial_conference` | `engines/` | **N2** ⚠️ | 有 `judge.py` 独立模块；刑事庭前会议（刑诉法 §187）和民事庭前会议结构差异大，可能需要重写 judge.py 的 criminal 分支 |
| 23 | `procedure_setup` | `engines/` | **N2-N3** | 民事诉讼程序和刑事/行政程序不是同一个东西（刑事有侦查/起诉/审判三段式，行政有行政复议前置），procedure_setup 可能需要新增 stage 类型 |
| 24 | `report_generation` | `engines/` | **N1-N2** | PROMPT_REGISTRY；但刑事报告的"量刑建议"章节和民事"胜诉率评估"结构完全不同，v3 模板需要扩展 |
| 25 | `similar_case_search` | `engines/` | **N0** | 案种无关（关键词检索） |
| 26 | `report_generation/v3` | `engines/` (sub) | **N2** | 见 #24，v3 子目录需要对称扩展 |

### 汇总统计

- **N0 不改**：8 个引擎 → 工作量为 0（但可能需要 smoke test 验证新案种下行为一致）
- **N1 纯 prompt**：12 个引擎 → 单案种 1-2 天/engine
- **N2 prompt + plugin 方法**：3 个引擎（`issue_impact_ranker` / `pretrial_conference` / `report_generation`）→ 单案种 3-4 天/engine
- **N3 新领域字段**：1 个引擎（`document_assistance` 升级版）→ 单案种 4-5 天
- **N4 重构**：1 个引擎（`amount_calculator`）→ 一次性重构 5-7 天，独立于具体案种
- **N2/3 混合**：2 个引擎（`procedure_setup` / `report_generation` v3）→ 单案种 3-5 天

### 危险信号

- `amount_calculator` 的 civil_loan 硬耦合是 Layer 4 的**第一个绊脚石**，应当在开始任何案种扩展前作为"Batch 6.0"单独解耦
- `procedure_setup` 可能触发 `ProcedurePhase` 枚举（`core.py:118`）的扩展 —— 当前枚举是针对民事庭审流程设计的（`evidence_submission` / `evidence_challenge` / `judge_questions` / `rebuttal`），刑事的"法庭调查/法庭辩论/最后陈述"和行政的"陈述申辩/听证"可能需要新值

---

## 问题 3：Model 层需求

### 是否需要新的案种专属模块？

**推荐：是，但只创建必需的**。对 Batch 5 样板（`civil_loan.py` 承载了所有与放款/还款/金额复算相关的类型）的照搬没有意义，因为 criminal 和 admin 的领域对象完全不同。

#### `engines/shared/models/criminal.py`（推荐创建）

**承载**：
- `ChargeType`（罪名枚举，MVP 期只有 `intentional_injury` / `theft` / `fraud`；或者设计为 `tuple[str, str]` = (章节, 具体罪名)）
- `CriminalImpactTarget`（枚举或 frozenset，值：`conviction` / `charge_name` / `sentence_length` / `sentence_severity` / `incidental_civil_compensation` / `credibility`）
- `SentencingFactor`（量刑情节：法定/酌定 × 加重/减轻/从重/从轻）
- `ChargeElement`（犯罪构成要件：主体/客体/主观方面/客观方面）—— 可选，看 P0 是否真的需要结构化
- `EvidenceChainStatus`（证据链状态：`exclusive` 排他性认定 / `consistent` 相互印证 / `conflicting` 矛盾 / `insufficient` 不足）
- `IllegalEvidenceExclusionRecord`（非法证据排除记录）

**不承载**：刑事案件的"金额"概念（盗窃数额）应当作为 `Claim.amount` 或专门的 `CriminalAmount` 子类；不建议重用 `civil_loan.AmountCalculationReport`，因为盗窃数额不需要"本金/利息"拆分。

#### `engines/shared/models/administrative.py`（推荐创建）

**承载**：
- `AdminActionType`（被诉行政行为类型：`penalty` / `permit` / `coercion` / `inaction` / `info_disclosure_reply` / `compensation_decision`）
- `LegalBasisCheck`（合法性审查五要素：`authority` 职权 / `procedure` 程序 / `factual_basis` 事实 / `legal_basis` 法律依据 / `discretion` 裁量）
- `AdminReliefType`（判决类型：`revocation` / `declare_illegal` / `order_perform` / `alteration` / `compensation` / `dismiss`）
- `AdminImpactTarget`（枚举或 frozenset：`legality` 合法性 / `procedure_compliance` 程序合规 / `factual_accuracy` 事实认定 / `discretion_reasonableness` 裁量合理性 / `relief_type` 判决类型 / `credibility`）
- `ReconsiderationPrerequisite`（行政复议前置要求）

**不承载**：民事意义上的"赔偿金额"应当走 `state_compensation` 走一个独立的 `StateCompensationClaim`，不混入通用 `Claim`。

### CaseTypePlugin Protocol 需要扩展吗？

**当前 Protocol**（`case_type_plugin.py:42-89`）只有两个方法：
- `get_prompt(engine_name, case_type, context)`
- `allowed_impact_targets(case_type) -> frozenset[str]`

**推荐为 Layer 4 增加的方法**（按优先级排序）：

1. **`case_family(case_type) -> Literal["civil", "criminal", "admin"]`** 🔴 必须
   - 让引擎在不 hard-code 映射表的情况下把 `PromptProfile` 归一到 `CaseType.value`
   - 触发场景：报告生成要显示"本案属于刑事案件"；程序引擎要决定走民诉/刑诉/行诉流程

2. **`allowed_procedure_phases(case_type) -> tuple[ProcedurePhase, ...]`** 🟡 推荐
   - 因为 `ProcedurePhase` 是为民事庭审设计的，刑事/行政的阶段序列不同
   - 避免在每个引擎里重复写 `if case_family == "criminal": phases = [...]`

3. **`allowed_relief_types(case_type) -> frozenset[str]`** 🟢 可选
   - 民事是"判决支持/部分支持/驳回"，刑事是"有罪/无罪/发回"，行政是"撤销/确认违法/驳回"
   - 可以推迟到发现实际需要时再加

4. **`default_burden_allocation(case_type) -> dict[str, str]`** 🟢 可选
   - 刑事是"控方承担举证责任（无罪推定）"，行政是"被告承担主要举证责任"（《行政诉讼法》§34），民事是"谁主张谁举证"
   - 如果 `burden_allocator` 引擎能读到这个默认值，可以省掉每个案种一个 prompt

**推迟决策**：不推荐在 Layer 4 初期就扩展 Protocol，因为 Batch 5 刚刚才把 `allowed_impact_targets` 加进去。应当在 Batch 6.0（amount_calculator 解耦）之后、Batch 6.1（criminal 第一个子类型 PoC）之中再决定要不要加 `case_family()` 这样的方法。

---

## 问题 4：领域词汇研究清单

### 权威来源（要读的文件）

#### 刑事

1. **《中华人民共和国刑法》**（2020 修正版 = 刑法修正案十一）
   - 第二编 分则：§234（故意伤害）、§264（盗窃）、§266（诈骗）
   - 第一编 总则：§13-21（犯罪构成）、§22-26（故意过失）、§61-78（量刑）
2. **《中华人民共和国刑事诉讼法》**（2018 修正版）
   - §5（独立审判）、§12（无罪推定）、§50-56（证据）、§186-202（法庭审理）
3. **最高法 法释〔2021〕1 号**：最高人民法院关于适用《中华人民共和国刑事诉讼法》的解释
4. **各罪专属司法解释**：
   - 故意伤害：法释〔2013〕12 号、〔2015〕9 号（伤情鉴定标准）
   - 盗窃：法释〔2013〕8 号（数额认定）
   - 诈骗：法释〔2011〕7 号、〔2016〕25 号（电信网络诈骗）
5. **最高法指导性案例**（对照 CaseLaw Reasoner 能力）：第 3 号（潘玉梅诈骗）、第 13 号（王召成非法买卖爆炸物，定罪证据链样板）等

#### 行政

1. **《中华人民共和国行政诉讼法》**（2017 修正版）
   - §2-12（受案范围）、§25-27（当事人）、§34（被告举证责任）、§63-80（判决形式）
2. **最高法 法释〔2018〕1 号**：关于适用《中华人民共和国行政诉讼法》的解释
3. **《中华人民共和国行政处罚法》**（2021 修订）
   - §3-5（原则）、§8-15（处罚种类和设定）、§44-65（程序）
4. **《政府信息公开条例》**（2019 修订）+ 法释〔2011〕17 号
5. **《工伤保险条例》**（2010 修订）+ 法释〔2014〕9 号 + 人社部相关规范性文件
6. **《国家赔偿法》**（2012 修正版）— 涉及行政赔偿章节

### 需要研究的词汇维度（每个维度要填一个 frozenset）

| 维度 | civil 参考 | criminal 需查 | admin 需查 |
|---|---|---|---|
| `impact_targets` | principal/interest/penalty/attorney_fee/credibility | conviction / charge / sentence / incidental_civil / credibility | legality / procedure / factual / discretion / relief / credibility |
| `relief_types` | 支持/部分支持/驳回 | 有罪/无罪/发回/不起诉 | 撤销/确认违法/责令履行/变更/赔偿/驳回 |
| `evidence_categories` | 书证/物证/证人/视听/电子/鉴定/勘验 | + 被告人供述 + 被害人陈述 + 辨认笔录 + 侦查实验笔录 | + 行政卷宗 + 被诉行政行为底稿 + 听证记录 |
| `burden_keywords` | 谁主张谁举证 | 无罪推定 / 排除合理怀疑 | 被告举证行政行为合法 |
| `procedure_phases` | case_intake→opening→evidence→judge→rebuttal | 侦查→起诉→一审庭审（法庭调查→法庭辩论→最后陈述）→二审 | 复议前置→起诉→审理→判决 |

### 研究产出物（每个案种）

每个新案种应当产出**一份 vocab 研究笔记**（约 300-500 字），格式：
```
案种：故意伤害罪 (intentional_injury)
上级 CaseType：criminal
法律依据：《刑法》§234 / 法释〔2013〕12 号 / 人体损伤程度鉴定标准（2014）
核心争点类型：
  - 正当防卫与防卫过当的区分
  - 伤情等级认定（轻伤一级/二级、重伤一级/二级）
  - 因果关系（多因一果时的责任分配）
  - 故意 vs 过失（故意伤害 vs 过失致人重伤）
ALLOWED_IMPACT_TARGETS 候选：
  - conviction（定罪与否）
  - charge（罪名选择）
  - sentence_length（刑期长短）
  - sentence_severity（是否实刑/缓刑）
  - incidental_civil_compensation（附带民事赔偿金额）
  - credibility（可信度枢轴）
量刑情节（SentencingFactor）候选：
  法定：自首、立功、累犯、未成年人、限制责任能力…
  酌定：认罪认罚、退赃退赔、赔偿谅解、犯罪前科…
```

6 份这样的笔记（3 criminal + 3 admin）= Layer 4 的词汇研究交付物。

---

## 问题 5：Prompt 工程量估算

### 天真的全量估算（每个子类型一套 prompt）

- **17 个 N1+ 引擎 × 6 个新子类型 = 102 个新 prompt 模块**
- 每个模块平均 200 行 → **约 20,000 行新 prompt 代码**
- 加上 6 个 `issue_impact_ranker.{case_type}.json` few-shot 文件（约 50 行/文件）

这是**上限**。实际工程量可以显著压缩：

### 推荐：两层 prompt 继承策略

**层 1：案种家族 base prompt**
- 每个引擎每个家族一份：
  - `prompts/_criminal_base.py` — 刑事通用 system prompt + 通用 build_user_prompt
  - `prompts/_admin_base.py` — 行政通用 system prompt + 通用 build_user_prompt
- 覆盖 80% 通用结构（案件基本信息、证据清单、争点列表渲染）

**层 2：案种 override**
- 每个引擎每个子类型一份，但只定义变化部分：
  - `ALLOWED_IMPACT_TARGETS`（frozenset）
  - `DOMAIN_SPECIFIC_HINT`（案种专属 prompt 段落注入 base system prompt）
  - 可选的 `build_user_prompt` 覆盖（仅当需要专属 context 块）

**压缩后估算**：
- 17 个引擎 × 2 个 base（criminal base + admin base） = **34 个 base prompt 模块**
- 17 个引擎 × 6 个 subtype override = **102 个 override 文件，但平均只有 30-50 行**
- 总代码量 ≈ 34 × 200 + 102 × 40 = **约 10,880 行** （砍掉 ~45%）

### Few-shot 文件

- `issue_impact_ranker`：6 个新文件（critical，决定词汇过滤）
- `adversarial_plaintiff` / `adversarial_defendant`：**可能**需要按 criminal/admin 拆分，因为"控方/辩方"语义和"原告/被告"不一样；估 2 个新文件
- `defense_chain`：可能需要 criminal-specific（非法证据排除辩护 vs 民事合同无效辩护）；估 1 个新文件
- **合计 9 个新 few-shot JSON**（每个 50-100 行 = 450-900 行 JSON）

### Prompt 迭代成本

法律类 prompt 的**调优**通常比首写更费时间。根据 Batch 5 的经验（labor_dispute / real_estate 从对抗评审中暴露"例子和词汇不一致"的问题），每个新子类型的 prompt 在首次跑通后还需要 **2-3 轮 LLM-in-the-loop 调优**才能达到 civil_loan 的质量基线。这部分成本**不在代码行数里**，但是 Layer 4 最容易被低估的工作量。

---

## 问题 6：Test / Fixture / Golden 估算

### 现有测试状态（Batch 5 合并后）

- **2408 passed** on main
- **266 处**测试源文件中出现 `civil_loan` / `labor_dispute` / `real_estate` 字符串
- 约 **85 个测试文件**提到案件类型

### 新增测试估算

#### 单元测试（每个新子类型）

| 测试对象 | 每子类型新增数 | 6 个子类型合计 |
|---|---|---|
| 新 prompt 模块（build_user_prompt 结构） | ~3 | 18 |
| 新 ALLOWED_IMPACT_TARGETS（vocab lock-step） | ~2 | 12 |
| 新 few-shot JSON（example 与 vocab 一致） | ~2 | 12 |
| 新 model 类（criminal.py / administrative.py 的 pydantic 验证） | ~5-10（仅两个家族） | 10-20 |
| ranker `_resolve_impact_targets` 对新 vocab 过滤 | ~2 | 12 |
| CaseTypePlugin `allowed_impact_targets` 对新 case_type | ~1 | 6 |

**单元测试合计：约 70-80 个新测试**

#### 契约测试 / 参数化现有测试

- `test_prompt_registry.py` 需要扩展 `PromptProfile` 参数化 → +6 个 parametrize 展开
- `test_case_type_plugin.py` 需要为每个新案种跑一遍 UnsupportedCaseTypeError 反向测试 → +6 个
- 每个 N1+ 引擎的 `test_*.py`（如果当前是 hardcode `case_type="civil_loan"`）需要参数化 → **约 25-35 个测试文件需要重写**

#### E2E 测试（pipeline 穿透）

- 每个新子类型需要一条端到端 smoke test（输入 fixture → 跑完整 pipeline → 断言关键产物）
- 6 个新子类型 = **6 条新 E2E**
- 每条 E2E 需要一个 case fixture（模拟起诉书/判决书文本）+ golden output

#### Golden 文件

- `benchmarks/golden_outputs/` 当前有若干 civil 案例
- 每个新子类型需要 **1-2 个 golden case**（最小规模）
- 合计 **6-12 个新 golden case**

#### 受影响的现有测试

估计 **30-40 个现有测试文件需要更新**（主要是参数化、增加新 case_type 到 parametrize 列表、调整硬编码断言）。**不会破坏**的测试：所有使用 `LLM_MOCK=true` 的 unit test（约 2000+ 个），因为它们是 case_type-agnostic 的断言。

**总测试增量估算**：
- 新增：80 unit + 6 E2E + 12 golden ≈ **100 个新测试**
- 修改：30-40 个现有文件
- **预期最终测试数**：2408 → ~2500+

---

## 问题 7：风险 + 批次拆分

### 风险清单

#### 🔴 Critical

1. **`amount_calculator` 民事硬耦合** — 如果不先解耦，criminal/admin 引擎在 pipeline 层会被绊倒。**缓解**：Batch 6.0 专门解耦，在任何案种扩展前完成。

2. **`ProcedurePhase` 枚举不兼容** — 当前枚举只覆盖民事庭审阶段。刑事"法庭调查/法庭辩论/最后陈述"和行政"陈述申辩/听证"不在里面。如果 `procedure_setup` 或 `pretrial_conference` 访问了 phase 的具体值，扩展会引起回归。**缓解**：Batch 6.0 同时审查 `ProcedurePhase` 的所有使用点，决定是扩枚举还是让 `allowed_procedure_phases()` plugin 方法接管。

3. **Prompt 质量无法被单元测试保证** — LLM 输出在 `LLM_MOCK=true` 下是 mock 的，真实的 criminal/admin prompt 质量只能靠人工 review 和昂贵的 live LLM eval。如果没有 eval harness，每个子类型在生产环境都可能翻车。**缓解**：Batch 6.0 前置建立一个最小的 `benchmarks/layer4_eval/` 框架，至少每个新子类型有 3 个真实 LLM-driven 的 smoke test（打开 LLM live 标志运行）。

#### 🟡 Important

4. **`document_assistance` 的 (doc_type × case_type) 组合爆炸** — 刑事文书类型（起诉书/辩护词/上诉状/量刑建议书）和民事文书完全不同。如果每个组合都写独立 prompt，工程量会翻倍。**缓解**：Batch 6.0 前调研是否要从"组合键"切换到"工厂函数"模式。

5. **`adversarial` 引擎的"原被告"vs"控辩"语义错配** — `adversarial_plaintiff.json` / `adversarial_defendant.json` 的 few-shot 示例是民事语境。刑事的"控方/辩方"有完全不同的策略空间（控方不需要"诉请"，辩方有"罪轻辩护/无罪辩护"二选一）。**缓解**：criminal batch 需要一次性重写 adversarial 的 few-shot。

6. **`report_generation/v3` 模板分叉** — v3 模板是为民事对抗报告设计的（胜诉率评估、调解区间等已被删除）。刑事报告需要"量刑建议"章节，行政报告需要"合法性审查结论"章节。**缓解**：v3 需要三份并行的 section template，不能共用一份。

7. **研究深度不足导致设计返工** — 6 个新子类型的法律研究如果不到位，模型字段和 prompt 结构都会在编码过程中被推翻。**缓解**：Batch 6.0 前置一个纯研究 sprint（1-2 周），交付 6 份 vocab 研究笔记 + 模型字段草案，经过人类法律专家 review 后才开写代码。

#### 🟢 Minor

8. **Test 爆炸半径** — 现有 85 个提案件类型的测试文件，参数化成本不大但有 review 负担。
9. **CLI/API 层面的 case_type 参数暴露** — 需要更新 help text、API schema（OpenAPI）、CLI validation 列表。
10. **文档和 README 更新** — 低优先级但不可忽略。

### 批次拆分建议

**Criminal 和 administrative 应当完全分开，不能混合。** 理由：

- 两者领域模型差异巨大（criminal.py / admin.py 没有代码复用空间）
- 两者 vocab 研究不能互相参考（引用的法条完全不同）
- 两者的 prompt 调优回路独立，混在一个 batch 里会造成注意力分散和回归风险
- 批次越大，爆炸半径越大（Batch 5 的经验：一个 6 commit 的 batch 已经到了 adversarial review 能稳定审完的上限）

**建议的批次序列**：

#### Batch 6.0：Layer 4 Preflight（2 周）

**目标**：解耦和基础设施，不落地任何具体案种
- 6.0.1 解耦 `amount_calculator` 的 civil_loan 硬编码（让 pipeline 能跳过金额复算）
- 6.0.2 审查 `ProcedurePhase` 使用点，必要时扩展枚举或加 `allowed_procedure_phases()`
- 6.0.3 `CaseTypePlugin` Protocol 扩展：加 `case_family(case_type)` 方法
- 6.0.4 建立 `benchmarks/layer4_eval/` 最小 eval harness
- 6.0.5 完成 6 份 vocab 研究笔记（交付物 markdown，不碰代码）
- **Blast radius**：~10 文件，~30 测试
- **Gate**：人工 review vocab 笔记并签字

#### Batch 6.1：Criminal Foundation（2-3 周）

**目标**：criminal 第一个子类型跑通端到端
- 6.1.1 `engines/shared/models/criminal.py` 最小版（ChargeType、CriminalImpactTarget、SentencingFactor）
- 6.1.2 `intentional_injury` 的 `_criminal_base` + override prompt × 17 引擎
- 6.1.3 `issue_impact_ranker.intentional_injury.json` few-shot
- 6.1.4 端到端 smoke test + 1 个 golden case
- **Blast radius**：~30 文件，~40 新测试
- **Gate**：smoke test 在 LLM live 模式下通过

#### Batch 6.2：Criminal Expansion（2 周）

- 6.2.1 `theft` 子类型（包括对 amount_calculator 的可选扩展，支持盗窃数额认定）
- 6.2.2 `fraud` 子类型
- 6.2.3 adversarial few-shot 刑事化重写
- **Blast radius**：~40 文件

#### Batch 7.0：Administrative Foundation（2-3 周）

- 7.0.1 `engines/shared/models/administrative.py` 最小版
- 7.0.2 `admin_penalty` 第一个子类型端到端
- 7.0.3 report_generation v3 行政模板分叉
- **Blast radius**：~30 文件

#### Batch 7.1：Administrative Expansion（2 周）

- 7.1.1 `info_disclosure`
- 7.1.2 `work_injury_recognition`（与现有 labor_dispute 的协同集成）
- **Blast radius**：~30 文件

### 批次依赖图

```
6.0 Preflight ──┬──> 6.1 Criminal Foundation ──> 6.2 Criminal Expansion
                │
                └──> 7.0 Admin Foundation ──> 7.1 Admin Expansion
```

6.1 和 7.0 可以**并行**，但强烈**不建议** —— 因为人力上下文切换成本高于并行收益。串行执行更安全。

---

## 问题 8：时间估算

### 三档估算

| 批次 | Optimistic | Realistic | Pessimistic |
|---|---|---|---|
| 6.0 Preflight（含 vocab 研究） | 2 周（10 工作日） | 3 周（15 工作日） | 5 周（25 工作日） |
| 6.1 Criminal Foundation | 2 周 | 3 周 | 5 周 |
| 6.2 Criminal Expansion（2 子类型） | 2 周 | 3 周 | 4 周 |
| 7.0 Admin Foundation | 2 周 | 3 周 | 5 周 |
| 7.1 Admin Expansion（2 子类型） | 2 周 | 3 周 | 4 周 |
| **合计** | **10 周** | **15 周** | **23 周** |

换算成对话 turn（基于 Batch 5 的节奏：约 40-60 turn 完成一个类似 6.1 规模的 batch）：
- **Optimistic**：~200 turn
- **Realistic**：~300 turn
- **Pessimistic**：~450 turn

### 估算的假设和风险

**Optimistic 假设**：
- vocab 研究一次通过，不需要返工
- prompt 调优每个子类型不超过 2 轮
- `amount_calculator` 解耦能干净完成，无连锁回归
- 对抗评审每批只需要一轮

**Pessimistic 场景**：
- vocab 研究需要人工法律专家介入多轮（这是最可能发生的）
- `ProcedurePhase` 扩展触发 Batch 4 级别的全局回归
- `amount_calculator` 解耦涉及 civil pipeline 的意外依赖
- criminal 和 admin 报告模板需要重新设计（v4 模板）

**最可能的瓶颈**：**不是写代码，是法律研究的深度和人工 review 的响应速度**。Batch 5 的经验表明，AI 能一晚完成代码，但法律 vocab 的正确性需要人类签字。如果 review 循环是 2-3 天/轮，单个子类型的 wall-clock 时间会显著拉长。

---

## 总结

Layer 4 是一次**案种家族维度**的扩展（从 civil 1 个家族 → civil + criminal + admin 三个家族），总计 6 个新 `PromptProfile` 子类型。与 Batch 5（三 enum 中性化）不同，Layer 4 的主要成本**不在重构已有代码**，而在：

1. **法律研究深度**（6 份 vocab 笔记，需要人工 review）
2. **新领域模型设计**（criminal.py / admin.py 是新创，没有 civil_loan.py 样板可照搬）
3. **17 个引擎 × 6 个子类型 = 102 个 prompt 模块的工程量**（可通过两层继承压缩到 ~40 个 base + ~60 个小 override）
4. **两个绊脚石的前置解耦**（`amount_calculator` + `ProcedurePhase`）

推荐执行路径：**Batch 6.0 Preflight → 6.1 Criminal PoC → 6.2 Criminal 扩展 → 7.0 Admin PoC → 7.1 Admin 扩展**，共 5 个 batch，串行执行，realistic 估算 15 周。

---

## 8 个问题的一句话答案

1. **MVP 子类型**：criminal = 故意伤害 / 盗窃 / 诈骗（暴力/财产/欺诈三原型）；admin = 行政处罚 / 政府信息公开 / 工伤认定（覆盖 >60% 实务案件）。
2. **Engine 清单**：26 个引擎中 8 个 N0（规则驱动，零改动）、12 个 N1（纯加 prompt）、3 个 N2（加 plugin 方法）、1 个 N3（document_assistance 可能升级）、2 个 N4（amount_calculator 硬解耦 + procedure_setup 可能扩 Phase 枚举）。
3. **Model 层**：推荐新建 `criminal.py` + `administrative.py` 两个专属模块；`CaseTypePlugin` Protocol 建议加一个 `case_family()` 方法（必须），其余方法推迟。
4. **领域词汇**：需要研究 11 个权威法律文件（刑法/刑诉法/行诉法 + 6 部司法解释 + 2 部行政法规），交付 6 份 vocab 笔记。
5. **Prompt 工程量**：天真估算 102 个新 prompt 模块（~20k 行），通过两层继承可压缩到 ~40 base + 60 override（~11k 行）。
6. **测试**：新增约 100 个单元/E2E 测试 + 6-12 个 golden case，需修改约 30-40 个现有测试文件，最终测试数预期 2500+。
7. **风险 + 批次**：3 个 Critical 风险（amount_calculator 耦合、ProcedurePhase 枚举、prompt 质量无 unit test 保证）、7 个 Important；criminal 和 admin 必须分开，推荐 5 个 batch 串行。
8. **时间**：realistic 15 周 / optimistic 10 周 / pessimistic 23 周，最可能瓶颈是法律 vocab 的人工 review 循环而非代码实现。

---

## 最大的未决问题

**Layer 4 的前置解耦（Batch 6.0）是否能被压缩到 1 周以内？**

这个问题决定了整个 Layer 4 能否快速启动。三个子问题：

1. `amount_calculator` 的 civil_loan 硬编码到底有多深？—— 需要实际读代码验证，不是从 Explore 报告里能得到答案。
2. `ProcedurePhase` 枚举的使用点是否可以被 `allowed_procedure_phases()` plugin 方法一次性吸收？—— 需要 grep 所有 `phase ==` / `phase in` 模式。
3. `CaseTypePlugin` Protocol 扩展能否不破坏 Batch 5 刚建立的契约？—— 理论上可以（加方法不减方法），但需要核对所有实现了 `CaseTypePlugin` 的类是否都会被新方法触到。

如果这三个问题的答案都是"能"，Batch 6.0 能在 2 周内完成，整个 Layer 4 的 realistic 估算可以下调到 **12-13 周**；如果任何一个答案是"不能"或"需要深度重构"，Layer 4 的起跑线会被推迟 2-4 周，且需要重新评估批次拆分。

**建议**：在正式开 Batch 6.0 之前，先做一次 1-2 天的 **"绊脚石勘探"** 子任务，专门回答上述三个子问题，然后再决定 Batch 6.0 的范围和 kickoff 时间。
'"'@ | python -c \"import sys; text=sys.stdin.read().splitlines();
for i,line in enumerate(text,1):
    print(f'{i:4} {line}')\""` rejected: blocked by policy
codex
The plan makes claims about “only amount_calculator” and “mostly prompt work.” I’m checking the actual code paths now; that’s where optimistic plans usually collapse.
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -NoProfile -Command "rg -n \"class CaseType|class PromptProfile|class ProcedurePhase|class .*CaseTypePlugin|allowed_impact_targets|case_family|PromptProfile|civil_loan|criminal|admin\" engines/shared engines -g '"'!**/__pycache__/**'"'" in C:/Users/david/dev/case-adversarial-engine
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -NoProfile -Command "rg -n \"amount_calculator|calculator.py|if case_type == \\\"civil_loan\\\"|AmountCalculationReport|ClaimCalculationEntry|procedure_setup|pretrial_conference|document_assistance|report_generation|issue_impact_ranker\" engines tests -g '"'!**/__pycache__/**'"'" in C:/Users/david/dev/case-adversarial-engine
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -NoProfile -Command "rg -n \"LLM_MOCK|PromptRegistry|PROMPT_REGISTRY|case_type=|case_type\\)|case_type:\" tests engines -g '"'!**/__pycache__/**'"'" in C:/Users/david/dev/case-adversarial-engine
2026-04-07T11:28:03.759333Z ERROR codex_core::tools::router: error=Exit code: 1
Wall time: 2.1 seconds
Output:
Cannot set property. Property setting is supported only on core types in this language mode.
At line:1 char:1
+ [Console]::OutputEncoding=[System.Text.Encoding]::UTF8;
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : InvalidOperation: (:) [], RuntimeException
    + FullyQualifiedErrorId : PropertySetterNotSupportedInConstrainedLanguage
 
rg : The term 'rg' is not recognized as the name of a cmdlet, function, script file, or operable program. Check the 
spelling of the name, or if a path was included, verify that the path is correct and try again.
At line:2 char:1
+ rg -n "class CaseType|class PromptProfile|class ProcedurePhase|class  ...
+ ~~
    + CategoryInfo          : ObjectNotFound: (rg:String) [], CommandNotFoundException
    + FullyQualifiedErrorId : CommandNotFoundException
 

 exited 1 in 2074ms:
Cannot set property. Property setting is supported only on core types in this language mode.
At line:1 char:1
+ [Console]::OutputEncoding=[System.Text.Encoding]::UTF8;
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : InvalidOperation: (:) [], RuntimeException
    + FullyQualifiedErrorId : PropertySetterNotSupportedInConstrainedLanguage
 
rg : The term 'rg' is not recognized as the name of a cmdlet, function, script file, or operable program. Check the 
spelling of the name, or if a path was included, verify that the path is correct and try again.
At line:2 char:1
+ rg -n "class CaseType|class PromptProfile|class ProcedurePhase|class  ...
+ ~~
    + CategoryInfo          : ObjectNotFound: (rg:String) [], CommandNotFoundException
    + FullyQualifiedErrorId : CommandNotFoundException
 

 exited 1 in 2055ms:
Cannot set property. Property setting is supported only on core types in this language mode.
At line:1 char:1
+ [Console]::OutputEncoding=[System.Text.Encoding]::UTF8;
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : InvalidOperation: (:) [], RuntimeException
    + FullyQualifiedErrorId : PropertySetterNotSupportedInConstrainedLanguage
 
rg : The term 'rg' is not recognized as the name of a cmdlet, function, script file, or operable program. Check the 
spelling of the name, or if a path was included, verify that the path is correct and try again.
At line:2 char:1
+ rg -n "amount_calculator|calculator.py|if case_type == \"civil_loan\" ...
+ ~~
    + CategoryInfo          : ObjectNotFound: (rg:String) [], CommandNotFoundException
    + FullyQualifiedErrorId : CommandNotFoundException
 

 exited 1 in 2053ms:
Cannot set property. Property setting is supported only on core types in this language mode.
At line:1 char:1
+ [Console]::OutputEncoding=[System.Text.Encoding]::UTF8;
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : InvalidOperation: (:) [], RuntimeException
    + FullyQualifiedErrorId : PropertySetterNotSupportedInConstrainedLanguage
 
rg : The term 'rg' is not recognized as the name of a cmdlet, function, script file, or operable program. Check the 
spelling of the name, or if a path was included, verify that the path is correct and try again.
At line:2 char:1
+ rg -n "LLM_MOCK|PromptRegistry|PROMPT_REGISTRY|case_type=|case_type\) ...
+ ~~
    + CategoryInfo          : ObjectNotFound: (rg:String) [], CommandNotFoundException
    + FullyQualifiedErrorId : CommandNotFoundException
 

2026-04-07T11:28:03.760246Z ERROR codex_core::tools::router: error=Exit code: 1
Wall time: 2.1 seconds
Output:
Cannot set property. Property setting is supported only on core types in this language mode.
At line:1 char:1
+ [Console]::OutputEncoding=[System.Text.Encoding]::UTF8;
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : InvalidOperation: (:) [], RuntimeException
    + FullyQualifiedErrorId : PropertySetterNotSupportedInConstrainedLanguage
 
rg : The term 'rg' is not recognized as the name of a cmdlet, function, script file, or operable program. Check the 
spelling of the name, or if a path was included, verify that the path is correct and try again.
At line:2 char:1
+ rg -n "amount_calculator|calculator.py|if case_type == \"civil_loan\" ...
+ ~~
    + CategoryInfo          : ObjectNotFound: (rg:String) [], CommandNotFoundException
    + FullyQualifiedErrorId : CommandNotFoundException
 

2026-04-07T11:28:03.761111Z ERROR codex_core::tools::router: error=Exit code: 1
Wall time: 2.1 seconds
Output:
Cannot set property. Property setting is supported only on core types in this language mode.
At line:1 char:1
+ [Console]::OutputEncoding=[System.Text.Encoding]::UTF8;
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : InvalidOperation: (:) [], RuntimeException
    + FullyQualifiedErrorId : PropertySetterNotSupportedInConstrainedLanguage
 
rg : The term 'rg' is not recognized as the name of a cmdlet, function, script file, or operable program. Check the 
spelling of the name, or if a path was included, verify that the path is correct and try again.
At line:2 char:1
+ rg -n "LLM_MOCK|PromptRegistry|PROMPT_REGISTRY|case_type=|case_type\) ...
+ ~~
    + CategoryInfo          : ObjectNotFound: (rg:String) [], CommandNotFoundException
    + FullyQualifiedErrorId : CommandNotFoundException
 

codex
`rg` isn’t available here, so I’m falling back to PowerShell-native search. I’m checking whether the plan’s “N0/N1 mostly prompt work” claim survives real symbol usage.
2026-04-07T11:28:16.870113Z ERROR codex_core::tools::router: error=`"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -NoProfile -Command "Get-ChildItem -Path engines -Recurse -File | Select-String -Pattern 'class CaseType|class PromptProfile|class ProcedurePhase|class .*CaseTypePlugin|allowed_impact_targets|case_family|PromptProfile|civil_loan|criminal|admin' | Select-Object -First 250 | ForEach-Object { \"{0}:{1}: {2}\" -f "'$_.Path, $_.LineNumber, $_.Line.Trim() }'` rejected: blocked by policy
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -NoProfile -Command "Get-ChildItem -Path engines -Recurse -File | Select-String -Pattern 'class CaseType|class PromptProfile|class ProcedurePhase|class .*CaseTypePlugin|allowed_impact_targets|case_family|PromptProfile|civil_loan|criminal|admin' | Select-Object -First 250 | ForEach-Object { \"{0}:{1}: {2}\" -f "'$_.Path, $_.LineNumber, $_.Line.Trim() }' in C:/Users/david/dev/case-adversarial-engine
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -NoProfile -Command "Get-ChildItem -Path engines,tests -Recurse -File | Select-String -Pattern 'amount_calculator|if case_type == \"civil_loan\"|AmountCalculationReport|ClaimCalculationEntry|procedure_setup|pretrial_conference|document_assistance|report_generation|issue_impact_ranker' | Select-Object -First 250 | ForEach-Object { \"{0}:{1}: {2}\" -f "'$_.Path, $_.LineNumber, $_.Line.Trim() }' in C:/Users/david/dev/case-adversarial-engine
 declined in 0ms:
`"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -NoProfile -Command "Get-ChildItem -Path engines -Recurse -File | Select-String -Pattern 'class CaseType|class PromptProfile|class ProcedurePhase|class .*CaseTypePlugin|allowed_impact_targets|case_family|PromptProfile|civil_loan|criminal|admin' | Select-Object -First 250 | ForEach-Object { \"{0}:{1}: {2}\" -f "'$_.Path, $_.LineNumber, $_.Line.Trim() }'` rejected: blocked by policy
 declined in 0ms:
`"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -NoProfile -Command "Get-ChildItem -Path engines,tests -Recurse -File | Select-String -Pattern 'amount_calculator|if case_type == \"civil_loan\"|AmountCalculationReport|ClaimCalculationEntry|procedure_setup|pretrial_conference|document_assistance|report_generation|issue_impact_ranker' | Select-Object -First 250 | ForEach-Object { \"{0}:{1}: {2}\" -f "'$_.Path, $_.LineNumber, $_.Line.Trim() }'` rejected: blocked by policy
2026-04-07T11:28:16.870918Z ERROR codex_core::tools::router: error=`"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -NoProfile -Command "Get-ChildItem -Path engines,tests -Recurse -File | Select-String -Pattern 'amount_calculator|if case_type == \"civil_loan\"|AmountCalculationReport|ClaimCalculationEntry|procedure_setup|pretrial_conference|document_assistance|report_generation|issue_impact_ranker' | Select-Object -First 250 | ForEach-Object { \"{0}:{1}: {2}\" -f "'$_.Path, $_.LineNumber, $_.Line.Trim() }'` rejected: blocked by policy
2026-04-07T11:28:16.873323Z ERROR codex_core::tools::router: error=`"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -NoProfile -Command "Get-ChildItem -Path tests,engines -Recurse -File | Select-String -Pattern 'LLM_MOCK|PROMPT_REGISTRY|case_type\\s*=|case_type\\)|case_type:' | Select-Object -First 250 | ForEach-Object { \"{0}:{1}: {2}\" -f "'$_.Path, $_.LineNumber, $_.Line.Trim() }'` rejected: blocked by policy
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -NoProfile -Command "Get-ChildItem -Path tests,engines -Recurse -File | Select-String -Pattern 'LLM_MOCK|PROMPT_REGISTRY|case_type\\s*=|case_type\\)|case_type:' | Select-Object -First 250 | ForEach-Object { \"{0}:{1}: {2}\" -f "'$_.Path, $_.LineNumber, $_.Line.Trim() }' in C:/Users/david/dev/case-adversarial-engine
 declined in 0ms:
`"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -NoProfile -Command "Get-ChildItem -Path tests,engines -Recurse -File | Select-String -Pattern 'LLM_MOCK|PROMPT_REGISTRY|case_type\\s*=|case_type\\)|case_type:' | Select-Object -First 250 | ForEach-Object { \"{0}:{1}: {2}\" -f "'$_.Path, $_.LineNumber, $_.Line.Trim() }'` rejected: blocked by policy
codex
The shell wrapper is picky about PowerShell formatting expressions. I’m simplifying the queries and reading the key files directly instead of fighting the wrapper.
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -NoProfile -Command 'Get-ChildItem -Path engines/shared/models -Recurse -File' in C:/Users/david/dev/case-adversarial-engine
 succeeded in 566ms:


    Directory: C:\Users\david\dev\case-adversarial-engine\engines\shared\models


Mode                 LastWriteTime         Length Name                                                                 
----                 -------------         ------ ----                                                                 
-a----          4/7/2026   3:27 PM          45688 analysis.py                                                          
-a----          4/7/2026   3:27 PM          13182 civil_loan.py                                                        
-a----          4/7/2026   3:27 PM           9890 core.py                                                              
-a----          4/7/2026  12:01 PM          14425 pipeline.py                                                          
-a----         3/31/2026   9:58 PM           1557 protocol.py                                                          
-a----          4/7/2026   3:27 PM           6517 __init__.py                                                          


    Directory: C:\Users\david\dev\case-adversarial-engine\engines\shared\models\__pycache__


Mode                 LastWriteTime         Length Name                                                                 
----                 -------------         ------ ----                                                                 
-a----          4/7/2026   3:28 PM          49704 analysis.cpython-312.pyc                                             
-a----          4/7/2026   3:28 PM          13744 civil_loan.cpython-312.pyc                                           
-a----          4/7/2026   3:28 PM          13806 core.cpython-312.pyc                                                 
-a----          4/7/2026  12:01 PM          16799 pipeline.cpython-312.pyc                                             
-a----         3/31/2026   9:59 PM           2337 protocol.cpython-312.pyc                                             
-a----          4/7/2026   3:28 PM           3903 __init__.cpython-312.pyc                                             


Cannot set property. Property setting is supported only on core types in this language mode.
At line:1 char:1
+ [Console]::OutputEncoding=[System.Text.Encoding]::UTF8;
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : InvalidOperation: (:) [], RuntimeException
    + FullyQualifiedErrorId : PropertySetterNotSupportedInConstrainedLanguage
 

exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -NoProfile -Command "Select-String -Path 'engines/shared/models/core.py' -Pattern 'class CaseType|class PromptProfile|class ProcedurePhase'" in C:/Users/david/dev/case-adversarial-engine
 succeeded in 587ms:

engines\shared\models\core.py:20:class CaseType(str, Enum):
engines\shared\models\core.py:28:class PromptProfile(str, Enum):
engines\shared\models\core.py:118:class ProcedurePhase(str, Enum):


Cannot set property. Property setting is supported only on core types in this language mode.
At line:1 char:1
+ [Console]::OutputEncoding=[System.Text.Encoding]::UTF8;
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : InvalidOperation: (:) [], RuntimeException
    + FullyQualifiedErrorId : PropertySetterNotSupportedInConstrainedLanguage
 

exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -NoProfile -Command "Get-Content 'engines/shared/models/core.py' | Select-Object -First 170" in C:/Users/david/dev/case-adversarial-engine
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -NoProfile -Command "Get-Content 'engines/shared/models/protocol.py'" in C:/Users/david/dev/case-adversarial-engine
2026-04-07T11:28:38.868136Z ERROR codex_core::tools::router: error=`"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -NoProfile -Command 'Get-ChildItem -Path engines -Recurse -File | Where-Object { $_.Name -match '"'case_type_plugin|plugin' } | Select-Object -ExpandProperty FullName"` rejected: blocked by policy
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -NoProfile -Command 'Get-ChildItem -Path engines -Recurse -File | Where-Object { $_.Name -match '"'case_type_plugin|plugin' } | Select-Object -ExpandProperty FullName" in C:/Users/david/dev/case-adversarial-engine
 declined in 0ms:
`"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -NoProfile -Command 'Get-ChildItem -Path engines -Recurse -File | Where-Object { $_.Name -match '"'case_type_plugin|plugin' } | Select-Object -ExpandProperty FullName"` rejected: blocked by policy
 succeeded in 561ms:
"""
åè®®ä¸Žåœºæ™¯å±‚æ¨¡åž‹ / Protocol and scenario layer models.

åŒ…å«å˜é‡æ³¨å…¥ã€å·®å¼‚æ¡ç›®å’Œåœºæ™¯å¯¹è±¡ã€?
"""

from __future__ import annotations

from typing import Any, Union

from pydantic import BaseModel, Field

from engines.shared.models.core import (
    ChangeItemObjectType,
    DiffDirection,
    ScenarioStatus,
)


# ---------------------------------------------------------------------------
# åœºæ™¯å±?/ Scenario layer
# ---------------------------------------------------------------------------


class ChangeItem(BaseModel):
    """å•æ¡å˜é‡æ³¨å…¥ã€?""

    target_object_type: ChangeItemObjectType
    target_object_id: str = Field(..., min_length=1)
    field_path: str = Field(..., min_length=1)
    old_value: Any = None
    new_value: Any = None


class DiffEntry(BaseModel):
    """å•äº‰ç‚¹å·®å¼‚æ¡ç›®ã€‚NO affected_party_ids per spec."""

    issue_id: str = Field(..., min_length=1)
    impact_description: str = Field(..., min_length=1)
    direction: DiffDirection


class Scenario(BaseModel):
    """åœºæ™¯å¯¹è±¡ã€‚NO separate DiffSummary wrapper per spec."""

    scenario_id: str = Field(..., min_length=1)
    case_id: str = Field(..., min_length=1)
    baseline_run_id: str = Field(..., min_length=1)
    change_set: list[ChangeItem]
    diff_summary: Union[str, list[DiffEntry]] = Field(...)
    affected_issue_ids: list[str] = Field(default_factory=list)
    affected_evidence_ids: list[str] = Field(default_factory=list)
    status: ScenarioStatus
Cannot set property. Property setting is supported only on core types in this language mode.
At line:1 char:1
+ [Console]::OutputEncoding=[System.Text.Encoding]::UTF8;
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : InvalidOperation: (:) [], RuntimeException
    + FullyQualifiedErrorId : PropertySetterNotSupportedInConstrainedLanguage
 

 succeeded in 610ms:
"""
æ ¸å¿ƒæžšä¸¾ä¸ŽåŸºç¡€ç±»åž‹ / Core enumerations and foundational types.

åŒ…å«æ‰€æœ‰æžšä¸¾ã€RawMaterial è¾“å…¥æ¨¡åž‹ï¼Œä»¥å?LLMClient åè®®å®šä¹‰ã€?
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# æžšä¸¾ç±»åž‹ / Enumerations
# ---------------------------------------------------------------------------


class CaseType(str, Enum):
    """æ¡ˆä»¶ç±»åž‹æžšä¸¾ï¼ˆschema-level canonicalï¼‰ã€?""

    civil = "civil"
    criminal = "criminal"
    admin = "admin"


class PromptProfile(str, Enum):
    """æç¤ºæ¨¡æ¿ keyï¼ˆengine-levelï¼‰ã€‚NOT a CaseType value."""

    civil_loan = "civil_loan"
    labor_dispute = "labor_dispute"
    real_estate = "real_estate"


class AccessDomain(str, Enum):
    """è¯æ®å¯è§åŸŸã€?""

    owner_private = "owner_private"
    shared_common = "shared_common"
    admitted_record = "admitted_record"


class EvidenceStatus(str, Enum):
    """è¯æ®ç”Ÿå‘½å‘¨æœŸçŠ¶æ€ã€?""

    private = "private"
    submitted = "submitted"
    challenged = "challenged"
    admitted_for_discussion = "admitted_for_discussion"


class EvidenceType(str, Enum):
    """è¯æ®ç±»åž‹æžšä¸¾ï¼Œå¯¹åº”ã€Šæ°‘äº‹è¯‰è®¼æ³•ã€‹è¯æ®ç§ç±»ã€?""

    documentary = "documentary"
    physical = "physical"
    witness_statement = "witness_statement"
    electronic_data = "electronic_data"
    expert_opinion = "expert_opinion"
    audio_visual = "audio_visual"
    other = "other"


class IssueType(str, Enum):
    """äº‰ç‚¹ç±»åž‹ã€?""

    factual = "factual"
    legal = "legal"
    procedural = "procedural"
    mixed = "mixed"


class IssueStatus(str, Enum):
    """äº‰ç‚¹å½“å‰çŠ¶æ€ã€?""

    open = "open"
    resolved = "resolved"
    deferred = "deferred"


class PropositionStatus(str, Enum):
    """äº‹å®žå‘½é¢˜æ ¸å®žçŠ¶æ€ã€?""

    unverified = "unverified"
    supported = "supported"
    contradicted = "contradicted"
    disputed = "disputed"


class BurdenStatus(str, Enum):
    """ä¸¾è¯è´£ä»»å®ŒæˆçŠ¶æ€ã€?""

    met = "met"
    partially_met = "partially_met"
    not_met = "not_met"
    disputed = "disputed"


class StatementClass(str, Enum):
    """ç»“è®ºé™ˆè¿°åˆ†ç±»ã€?""

    fact = "fact"
    inference = "inference"
    assumption = "assumption"


class WorkflowStage(str, Enum):
    """äº§å“å·¥ä½œæµé˜¶æ®µã€?""

    case_structuring = "case_structuring"
    procedure_setup = "procedure_setup"
    simulation_run = "simulation_run"
    report_generation = "report_generation"
    interactive_followup = "interactive_followup"


class ProcedurePhase(str, Enum):
    """æ³•å¾‹ç¨‹åºé˜¶æ®µã€?""

    case_intake = "case_intake"
    element_mapping = "element_mapping"
    opening = "opening"
    evidence_submission = "evidence_submission"
    evidence_challenge = "evidence_challenge"
    judge_questions = "judge_questions"
    rebuttal = "rebuttal"
    output_branching = "output_branching"


class ProcedureState(BaseModel):
    """ç¨‹åºé˜¶æ®µçš„è®¿é—®æŽ§åˆ¶çŠ¶æ€?â€?v1.5 æ–°å¢žã€?

    å½“ä¼ é€’ç»™ AccessController.filter_evidence_for_agent() æ—¶ï¼Œ
    åœ¨è§’è‰²çº§è§„åˆ™ä¹‹ä¸Šå åŠ é˜¶æ®µçº§è¿‡æ»¤ï¼š
    - evidence.access_domain å¿…é¡»åœ?readable_access_domains å†?
    - evidence.status å¿…é¡»åœ?admissible_evidence_statuses å†?
    """

    phase: ProcedurePhase
    readable_access_domains: list[AccessDomain]
    admissible_evidence_statuses: list[EvidenceStatus]


class ChangeItemObjectType(str, Enum):
    """change_item ç›®æ ‡å¯¹è±¡ç±»åž‹æžšä¸¾ã€?""

    Party = "Party"
    Claim = "Claim"
    Defense = "Defense"
    Issue = "Issue"
    Evidence = "Evidence"
    Burden = "Burden"
    ProcedureState = "ProcedureState"
    AgentOutput = "AgentOutput"
    ReportArtifact = "ReportArtifact"


class DiffDirection(str, Enum):
    """å·®å¼‚æ–¹å‘æžšä¸¾ã€?""

    strengthen = "strengthen"
    weaken = "weaken"
    neutral = "neutral"


class ScenarioStatus(str, Enum):
    """åœºæ™¯ç”Ÿå‘½å‘¨æœŸçŠ¶æ€ã€?""

    pending = "pending"
Cannot set property. Property setting is supported only on core types in this language mode.
At line:1 char:1
+ [Console]::OutputEncoding=[System.Text.Encoding]::UTF8;
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : InvalidOperation: (:) [], RuntimeException
    + FullyQualifiedErrorId : PropertySetterNotSupportedInConstrainedLanguage
 

exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -NoProfile -Command "Get-ChildItem -Path . -Recurse -File -Filter 'case_type_plugin.py' | Select-Object -ExpandProperty FullName" in C:/Users/david/dev/case-adversarial-engine
2026-04-07T11:28:47.761829Z ERROR codex_core::tools::router: error=Exit code: 1
Wall time: 2.2 seconds
Output:
C:\Users\david\dev\case-adversarial-engine\.claude\worktrees\affectionate-chebyshev\engines\shared\case_type_plugin.py
C:\Users\david\dev\case-adversarial-engine\.claude\worktrees\angry-williamson\engines\shared\case_type_plugin.py
C:\Users\david\dev\case-adversarial-engine\.claude\worktrees\awesome-hypatia\engines\shared\case_type_plugin.py
C:\Users\david\dev\case-adversarial-engine\.claude\worktrees\batch-5-phase-c\engines\shared\case_type_plugin.py
C:\Users\david\dev\case-adversarial-engine\.claude\worktrees\bold-rhodes\engines\shared\case_type_plugin.py
C:\Users\david\dev\case-adversarial-engine\.claude\worktrees\competent-lamarr\engines\shared\case_type_plugin.py
C:\Users\david\dev\case-adversarial-engine\.claude\worktrees\competent-wilson\engines\shared\case_type_plugin.py
C:\Users\david\dev\case-adversarial-engine\.claude\worktrees\cranky-chatterjee\engines\shared\case_type_plugin.py
C:\Users\david\dev\case-adversarial-engine\.claude\worktrees\cranky-robinson\engines\shared\case_type_plugin.py
C:\Users\david\dev\case-adversarial-engine\.claude\worktrees\eager-pare\engines\shared\case_type_plugin.py
C:\Users\david\dev\case-adversarial-engine\.claude\worktrees\elegant-noether\engines\shared\case_type_plugin.py
C:\Users\david\dev\case-adversarial-engine\.claude\worktrees\exciting-blackburn\engines\shared\case_type_plugin.py
C:\Users\david\dev\case-adversarial-engine\.claude\worktrees\fervent-taussig\engines\shared\case_type_plugin.py
C:\Users\david\dev\case-adversarial-engine\.claude\worktrees\flamboyant-nightingale\engines\shared\case_type_plugin.py
C:\Users\david\dev\case-adversarial-engine\.claude\worktrees\infallible-vaughan\engines\shared\case_type_plugin.py
C:\Users\david\dev\case-adversarial-engine\.claude\worktrees\interesting-hopper\engines\shared\case_type_plugin.py
C:\Users\david\dev\case-adversarial-engine\.claude\worktrees\jolly-roentgen\engines\shared\case_type_plugin.py
C:\Users\david\dev\case-adversarial-engine\.claude\worktrees\jovial-kepler\engines\shared\case_type_plugin.py
C:\Users\david\dev\case-adversarial-engine\.claude\worktrees\laughing-austin\engines\shared\case_type_plugin.py
C:\Users\david\dev\case-adversarial-engine\.claude\worktrees\magical-heisenberg\engines\shared\case_type_plugin.py
C:\Users\david\dev\case-adversarial-engine\.claude\worktrees\magical-tesla\engines\shared\case_type_plugin.py
C:\Users\david\dev\case-adversarial-engine\.claude\worktrees\nervous-brattain\engines\shared\case_type_plugin.py
C:\Users\david\dev\case-adversarial-engine\.claude\worktrees\nice-aryabhata\engines\shared\case_type_plugin.py
C:\Users\david\dev\case-adversarial-engine\.claude\worktrees\optimistic-khorana\engines\shared\case_type_plugin.py
C:\Users\david\dev\case-adversarial-engine\.claude\worktrees\pedantic-allen\engines\shared\case_type_plugin.py
C:\Users\david\dev\case-adversarial-engine\.claude\worktrees\pensive-shtern\engines\shared\case_type_plugin.py
C:\Users\david\dev\case-adversarial-engine\.claude\worktrees\quirky-darwin\engines\shared\case_type_plugin.py
C:\Users\david\dev\case-adversarial-engine\.claude\worktrees\quizzical-dirac\engines\shared\case_type_plugin.py
C:\Users\david\dev\case-adversarial-engine\.claude\worktrees\relaxed-cartwright\engines\shared\case_type_plugin.py
C:\Users\david\dev\case-adversarial-engine\.claude\worktrees\relaxed-edison\engines\shared\case_type_plugin.py
C:\Users\david\dev\case-adversarial-engine\.claude\worktrees\romantic-moser\engines\shared\case_type_plugin.py
C:\Users\david\dev\case-adversarial-engine\.claude\worktrees\sad-tu\engines\shared\case_type_plugin.py
C:\Users\david\dev\case-adversarial-engine\.claude\worktrees\serene-leakey\engines\shared\case_type_plugin.py
C:\Users\david\dev\case-adversarial-engine\.claude\worktrees\stoic-albattani\engines\shared\case_type_plugin.py
C:\Users\david\dev\case-adversarial-engine\.claude\worktrees\strange-pare\engines\shared\case_type_plugin.py
C:\Users\david\dev\case-adversarial-engine\.claude\worktrees\tender-wright\engines\shared\case_type_plugin.py
C:\Users\david\dev\case-adversarial-engine\.claude\worktrees\thirsty-hopper\engines\shared\case_type_plugin.py
C:\Users\david\dev\case-adversarial-engine\.claude\worktrees\trusting-brown\engines\shared\case_type_plugin.py
C:\Users\david\dev\case-adversarial-engine\.claude\worktrees\unruffled-snyder\engines\shared\case_type_plugin.py
C:\Users\david\dev\case-adversarial-engine\.claude\worktrees\vigilant-wescoff\engines\shared\case_type_plugin.py
C:\Users\david\dev\case-adversarial-engine\.claude\worktrees\vigorous-villani\engines\shared\case_type_plugin.py
C:\Users\david\dev\case-adversarial-engine\engines\shared\case_type_plugin.py
Cannot set property. Property setting is supported only on core types in this language mode.
At line:1 char:1
+ [Console]::OutputEncoding=[System.Text.Encoding]::UTF8;
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : InvalidOperation: (:) [], RuntimeException
    + FullyQualifiedErrorId : PropertySetterNotSupportedInConstrainedLanguage
 
Get-ChildItem : Access to the path 
'C:\Users\david\dev\case-adversarial-engine\.claude\worktrees\affectionate-chebyshev\.pytest_cache' is denied.
At line:2 char:1
+ Get-ChildItem -Path . -Recurse -File -Filter 'case_type_plugin.py' |  ...
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : PermissionDenied: (C:\Users\david\...v\.pytest_cache:String) [Get-ChildItem], Unauthoriz 
   edAccessException
    + FullyQualifiedErrorId : DirUnauthorizedAccessError,Microsoft.PowerShell.Commands.GetChildItemCommand
 
Get-ChildItem : Access to the path 
'C:\Users\david\dev\case-adversarial-engine\.claude\worktrees\batch-5-phase-c\.pytest_cache' is denied.
At line:2 char:1
+ Get-ChildItem -Path . -Recurse -File -Filter 'case_type_plugin.py' |  ...
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : PermissionDenied: (C:\Users\david\...c\.pytest_cache:String) [Get-ChildItem], Unauthoriz 
   edAccessException
    + FullyQualifiedErrorId : DirUnauthorizedAccessError,Microsoft.PowerShell.Commands.GetChildItemCommand
 
Get-ChildItem : Access to the path 
'C:\Users\david\dev\case-adversarial-engine\.claude\worktrees\bold-rhodes\.pytest_cache' is denied.
At line:2 char:1
+ Get-ChildItem -Path . -Recurse -File -Filter 'case_type_plugin.py' |  ...
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : PermissionDenied: (C:\Users\david\...s\.pytest_cache:String) [Get-ChildItem], Unauthoriz 
   edAccessException
    + FullyQualifiedErrorId : DirUnauthorizedAccessError,Microsoft.PowerShell.Commands.GetChildItemCommand
 
Get-ChildItem : Access to the path 
'C:\Users\david\dev\case-adversarial-engine\.claude\worktrees\competent-lamarr\.pytest_cache' is denied.
At line:2 char:1
+ Get-ChildItem -Path . -Recurse -File -Filter 'case_type_plugin.py' |  ...
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : PermissionDenied: (C:\Users\david\...r\.pytest_cache:String) [Get-ChildItem], Unauthoriz 
   edAccessException
    + FullyQualifiedErrorId : DirUnauthorizedAccessError,Microsoft.PowerShell.Commands.GetChildItemCommand
 
Get-ChildItem : Access to the path 
'C:\Users\david\dev\case-adversarial-engine\.claude\worktrees\eager-pare\.pytest_cache' is denied.
At line:2 char:1
+ Get-ChildItem -Path . -Recurse -File -Filter 'case_type_plugin.py' |  ...
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : PermissionDenied: (C:\Users\david\...e\.pytest_cache:String) [Get-ChildItem], Unauthoriz 
   edAccessException
    + FullyQualifiedErrorId : DirUnauthorizedAccessError,Microsoft.PowerShell.Commands.GetChildItemCommand
 
Get-ChildItem : Access to the path 
'C:\Users\david\dev\case-adversarial-engine\.claude\worktrees\exciting-blackburn\.pytest_cache' is denied.
At line:2 char:1
+ Get-ChildItem -Path . -Recurse -File -Filter 'case_type_plugin.py' |  ...
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : PermissionDenied: (C:\Users\david\...n\.pytest_cache:String) [Get-ChildItem], Unauthoriz 
   edAccessException
    + FullyQualifiedErrorId : DirUnauthorizedAccessError,Microsoft.PowerShell.Commands.GetChildItemCommand
 
Get-ChildItem : Access to the path 
'C:\Users\david\dev\case-adversarial-engine\.claude\worktrees\flamboyant-nightingale\.pytest_cache' is denied.
At line:2 char:1
+ Get-ChildItem -Path . -Recurse -File -Filter 'case_type_plugin.py' |  ...
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : PermissionDenied: (C:\Users\david\...e\.pytest_cache:String) [Get-ChildItem], Unauthoriz 
   edAccessException
    + FullyQualifiedErrorId : DirUnauthorizedAccessError,Microsoft.PowerShell.Commands.GetChildItemCommand
 
Get-ChildItem : Access to the path 
'C:\Users\david\dev\case-adversarial-engine\.claude\worktrees\infallible-vaughan\.pytest_cache' is denied.
At line:2 char:1
+ Get-ChildItem -Path . -Recurse -File -Filter 'case_type_plugin.py' |  ...
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : PermissionDenied: (C:\Users\david\...n\.pytest_cache:String) [Get-ChildItem], Unauthoriz 
   edAccessException
    + FullyQualifiedErrorId : DirUnauthorizedAccessError,Microsoft.PowerShell.Commands.GetChildItemCommand
 
Get-ChildItem : Access to the path 
'C:\Users\david\dev\case-adversarial-engine\.claude\worktrees\interesting-hopper\.pytest_cache' is denied.
At line:2 char:1
+ Get-ChildItem -Path . -Recurse -File -Filter 'case_type_plugin.py' |  ...
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : PermissionDenied: (C:\Users\david\...r\.pytest_cache:String) [Get-ChildItem], Unauthoriz 
   edAccessException
    + FullyQualifiedErrorId : DirUnauthorizedAccessError,Microsoft.PowerShell.Commands.GetChildItemCommand
 
Get-ChildItem : Access to the path 
'C:\Users\david\dev\case-adversarial-engine\.claude\worktrees\jolly-roentgen\.pytest_cache' is denied.
At line:2 char:1
+ Get-ChildItem -Path . -Recurse -File -Filter 'case_type_plugin.py' |  ...
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : PermissionDenied: (C:\Users\david\...n\.pytest_cache:String) [Get-ChildItem], Unauthoriz 
   edAccessException
    + FullyQualifiedErrorId : DirUnauthorizedAccessError,Microsoft.PowerShell.Commands.GetChildItemCommand
 
Get-ChildItem : Access to the path 
'C:\Users\david\dev\case-adversarial-engine\.claude\worktrees\jovial-kepler\.pytest_cache' is denied.
At line:2 char:1
+ Get-ChildItem -Path . -Recurse -File -Filter 'case_type_plugin.py' |  ...
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : PermissionDenied: (C:\Users\david\...r\.pytest_cache:String) [Get-ChildItem], Unauthoriz 
   edAccessException
    + FullyQualifiedErrorId : DirUnauthorizedAccessError,Microsoft.PowerShell.Commands.GetChildItemCommand
 
Get-ChildItem : Access to the path 
'C:\Users\david\dev\case-adversarial-engine\.claude\worktrees\laughing-austin\.pytest_cache' is denied.
At line:2 char:1
+ Get-ChildItem -Path . -Recurse -File -Filter 'case_type_plugin.py' |  ...
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : PermissionDenied: (C:\Users\david\...n\.pytest_cache:String) [Get-ChildItem], Unauthoriz 
   edAccessException
    + FullyQualifiedErrorId : DirUnauthorizedAccessError,Microsoft.PowerShell.Commands.GetChildItemCommand
 
Get-ChildItem : Access to the path 
'C:\Users\david\dev\case-adversarial-engine\.claude\worktrees\magical-heisenberg\.pytest_cache' is denied.
At line:2 char:1
+ Get-ChildItem -Path . -Recurse -File -Filter 'case_type_plugin.py' |  ...
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : PermissionDenied: (C:\Users\david\...g\.pytest_cache:String) [Get-ChildItem], Unauthoriz 
   edAccessException
    + FullyQualifiedErrorId : DirUnauthorizedAccessError,Microsoft.PowerShell.Commands.GetChildItemCommand
 
Get-ChildItem : Access to the path 
'C:\Users\david\dev\case-adversarial-engine\.claude\worktrees\magical-tesla\.pytest_cache' is denied.
At line:2 char:1
+ Get-ChildItem -Path . -Recurse -File -Filter 'case_type_plugin.py' |  ...
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : PermissionDenied: (C:\Users\david\...a\.pytest_cache:String) [Get-ChildItem], Unauthoriz 
   edAccessException
    + FullyQualifiedErrorId : DirUnauthorizedAccessError,Microsoft.PowerShell.Commands.GetChildItemCommand
 
Get-ChildItem : Access to the path 
'C:\Users\david\dev\case-adversarial-engine\.claude\worktrees\nervous-brattain\.pytest_cache' is denied.
At line:2 char:1
+ Get-ChildItem -Path . -Recurse -File -Filter 'case_type_plugin.py' |  ...
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : PermissionDenied: (C:\Users\david\...n\.pytest_cache:String) [Get-ChildItem], Unauthoriz 
   edAccessException
    + FullyQualifiedErrorId : DirUnauthorizedAccessError,Microsoft.PowerShell.Commands.GetChildItemCommand
 
Get-ChildItem : Access to the path 
'C:\Users\david\dev\case-adversarial-engine\.claude\worktrees\optimistic-khorana\.pytest_cache' is denied.
At line:2 char:1
+ Get-ChildItem -Path . -Recurse -File -Filter 'case_type_plugin.py' |  ...
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : PermissionDenied: (C:\Users\david\...a\.pytest_cache:String) [Get-ChildItem], Unauthoriz 
   edAccessException
    + FullyQualifiedErrorId : DirUnauthorizedAccessError,Microsoft.PowerShell.Commands.GetChildItemCommand
 
Get-ChildItem : Access to the path 
'C:\Users\david\dev\case-adversarial-engine\.claude\worktrees\pedantic-allen\.pytest_cache' is denied.
At line:2 char:1
+ Get-ChildItem -Path . -Recurse -File -Filter 'case_type_plugin.py' |  ...
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : PermissionDenied: (C:\Users\david\...n\.pytest_cache:String) [Get-ChildItem], Unauthoriz 
   edAccessException
    + FullyQualifiedErrorId : DirUnauthorizedAccessError,Microsoft.PowerShell.Commands.GetChildItemCommand
 
Get-ChildItem : Access to the path 
'C:\Users\david\dev\case-adversarial-engine\.claude\worktrees\quirky-darwin\.pytest_cache' is denied.
At line:2 char:1
+ Get-ChildItem -Path . -Recurse -File -Filter 'case_type_plugin.py' |  ...
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : PermissionDenied: (C:\Users\david\...n\.pytest_cache:String) [Get-ChildItem], Unauthoriz 
   edAccessException
    + FullyQualifiedErrorId : DirUnauthorizedAccessError,Microsoft.PowerShell.Commands.GetChildItemCommand
 
Get-ChildItem : Access to the path 
'C:\Users\david\dev\case-adversarial-engine\.claude\worktrees\quizzical-dirac\.pytest_cache' is denied.
At line:2 char:1
+ Get-ChildItem -Path . -Recurse -File -Filter 'case_type_plugin.py' |  ...
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : PermissionDenied: (C:\Users\david\...c\.pytest_cache:String) [Get-ChildItem], Unauthoriz 
   edAccessException
    + FullyQualifiedErrorId : DirUnauthorizedAccessError,Microsoft.PowerShell.Commands.GetChildItemCommand
 
Get-ChildItem : Access to the path 
'C:\Users\david\dev\case-adversarial-engine\.claude\worktrees\relaxed-cartwright\.pytest_cache' is denied.
At line:2 char:1
+ Get-ChildItem -Path . -Recurse -File -Filter 'case_type_plugin.py' |  ...
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : PermissionDenied: (C:\Users\david\...t\.pytest_cache:String) [Get-ChildItem], Unauthoriz 
   edAccessException
    + FullyQualifiedErrorId : DirUnauthorizedAccessError,Microsoft.PowerShell.Commands.GetChildItemCommand
 
Get-ChildItem : Access to the path 
'C:\Users\david\dev\case-adversarial-engine\.claude\worktrees\relaxed-edison\.pytest_cache' is denied.
At line:2 char:1
+ Get-ChildItem -Path . -Recurse -File -Filter 'case_type_plugin.py' |  ...
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : PermissionDenied: (C:\Users\david\...n\.pytest_cache:String) [Get-ChildItem], Unauthoriz 
   edAccessException
    + FullyQualifiedErrorId : DirUnauthorizedAccessError,Microsoft.PowerShell.Commands.GetChildItemCommand
 
Get-ChildItem : Access to the path 'C:\Users\david\dev\case-adversarial-engine\.claude\worktrees\sad-tu\.pytest_cache' 
is denied.
At line:2 char:1
+ Get-ChildItem -Path . -Recurse -File -Filter 'case_type_plugin.py' |  ...
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : PermissionDenied: (C:\Users\david\...u\.pytest_cache:String) [Get-ChildItem], Unauthoriz 
   edAccessException
    + FullyQualifiedErrorId : DirUnauthorizedAccessError,Microsoft.PowerShell.Commands.GetChildItemCommand
 
Get-ChildItem : Access to the path 
'C:\Users\david\dev\case-adversarial-engine\.claude\worktrees\stoic-albattani\.pytest_cache' is denied.
At line:2 char:1
+ Get-ChildItem -Path . -Recurse -File -Filter 'case_type_plugin.py' |  ...
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : PermissionDenied: (C:\Users\david\...i\.pytest_cache:String) [Get-ChildItem], Unauthoriz 
   edAccessException
    + FullyQualifiedErrorId : DirUnauthorizedAccessError,Microsoft.PowerShell.Commands.GetChildItemCommand
 
Get-ChildItem : Access to the path 
'C:\Users\david\dev\case-adversarial-engine\.claude\worktrees\tender-wright\.pytest_cache' is denied.
At line:2 char:1
+ Get-ChildItem -Path . -Recurse -File -Filter 'case_type_plugin.py' |  ...
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : PermissionDenied: (C:\Users\david\...t\.pytest_cache:String) [Get-ChildItem], Unauthoriz 
   edAccessException
    + FullyQualifiedErrorId : DirUnauthorizedAccessError,Microsoft.PowerShell.Commands.GetChildItemCommand
 
Get-ChildItem : Access to the path 
'C:\Users\david\dev\case-adversarial-engine\.claude\worktrees\unruffled-snyder\.pytest_cache' is denied.
At line:2 char:1
+ Get-ChildItem -Path . -Recurse -File -Filter 'case_type_plugin.py' |  ...
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : PermissionDenied: (C:\Users\david\...r\.pytest_cache:String) [Get-ChildItem], Unauthoriz 
   edAccessException
    + FullyQualifiedErrorId : DirUnauthorizedAccessError,Microsoft.PowerShell.Commands.GetChildItemCommand
 
Get-ChildItem : Access to the path 
'C:\Users\david\dev\case-adversarial-engine\.claude\worktrees\vigilant-wescoff\.pytest_cache' is denied.
At line:2 char:1
+ Get-ChildItem -Path . -Recurse -File -Filter 'case_type_plugin.py' |  ...
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : PermissionDenied: (C:\Users\david\...f\.pytest_cache:String) [Get-ChildItem], Unauthoriz 
   edAccessException
    + FullyQualifiedErrorId : DirUnauthorizedAccessError,Microsoft.PowerShell.Commands.GetChildItemCommand
 
Get-ChildItem : Access to the path 'C:\Users\david\dev\case-adversarial-engine\.pytest_cache' is denied.
At line:2 char:1
+ Get-ChildItem -Path . -Recurse -File -Filter 'case_type_plugin.py' |  ...
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : PermissionDenied: (C:\Users\david\...e\.pytest_cache:String) [Get-ChildItem], Unauthoriz 
   edAccessException
    + FullyQualifiedErrorId : DirUnauthorizedAccessError,Microsoft.PowerShell.Commands.GetChildItemCommand
 

 exited 1 in 2208ms:
C:\Users\david\dev\case-adversarial-engine\.claude\worktrees\affectionate-chebyshev\engines\shared\case_type_plugin.py
C:\Users\david\dev\case-adversarial-engine\.claude\worktrees\angry-williamson\engines\shared\case_type_plugin.py
C:\Users\david\dev\case-adversarial-engine\.claude\worktrees\awesome-hypatia\engines\shared\case_type_plugin.py
C:\Users\david\dev\case-adversarial-engine\.claude\worktrees\batch-5-phase-c\engines\shared\case_type_plugin.py
C:\Users\david\dev\case-adversarial-engine\.claude\worktrees\bold-rhodes\engines\shared\case_type_plugin.py
C:\Users\david\dev\case-adversarial-engine\.claude\worktrees\competent-lamarr\engines\shared\case_type_plugin.py
C:\Users\david\dev\case-adversarial-engine\.claude\worktrees\competent-wilson\engines\shared\case_type_plugin.py
C:\Users\david\dev\case-adversarial-engine\.claude\worktrees\cranky-chatterjee\engines\shared\case_type_plugin.py
C:\Users\david\dev\case-adversarial-engine\.claude\worktrees\cranky-robinson\engines\shared\case_type_plugin.py
C:\Users\david\dev\case-adversarial-engine\.claude\worktrees\eager-pare\engines\shared\case_type_plugin.py
C:\Users\david\dev\case-adversarial-engine\.claude\worktrees\elegant-noether\engines\shared\case_type_plugin.py
C:\Users\david\dev\case-adversarial-engine\.claude\worktrees\exciting-blackburn\engines\shared\case_type_plugin.py
C:\Users\david\dev\case-adversarial-engine\.claude\worktrees\fervent-taussig\engines\shared\case_type_plugin.py
C:\Users\david\dev\case-adversarial-engine\.claude\worktrees\flamboyant-nightingale\engines\shared\case_type_plugin.py
C:\Users\david\dev\case-adversarial-engine\.claude\worktrees\infallible-vaughan\engines\shared\case_type_plugin.py
C:\Users\david\dev\case-adversarial-engine\.claude\worktrees\interesting-hopper\engines\shared\case_type_plugin.py
C:\Users\david\dev\case-adversarial-engine\.claude\worktrees\jolly-roentgen\engines\shared\case_type_plugin.py
C:\Users\david\dev\case-adversarial-engine\.claude\worktrees\jovial-kepler\engines\shared\case_type_plugin.py
C:\Users\david\dev\case-adversarial-engine\.claude\worktrees\laughing-austin\engines\shared\case_type_plugin.py
C:\Users\david\dev\case-adversarial-engine\.claude\worktrees\magical-heisenberg\engines\shared\case_type_plugin.py
C:\Users\david\dev\case-adversarial-engine\.claude\worktrees\magical-tesla\engines\shared\case_type_plugin.py
C:\Users\david\dev\case-adversarial-engine\.claude\worktrees\nervous-brattain\engines\shared\case_type_plugin.py
C:\Users\david\dev\case-adversarial-engine\.claude\worktrees\nice-aryabhata\engines\shared\case_type_plugin.py
C:\Users\david\dev\case-adversarial-engine\.claude\worktrees\optimistic-khorana\engines\shared\case_type_plugin.py
C:\Users\david\dev\case-adversarial-engine\.claude\worktrees\pedantic-allen\engines\shared\case_type_plugin.py
C:\Users\david\dev\case-adversarial-engine\.claude\worktrees\pensive-shtern\engines\shared\case_type_plugin.py
C:\Users\david\dev\case-adversarial-engine\.claude\worktrees\quirky-darwin\engines\shared\case_type_plugin.py
C:\Users\david\dev\case-adversarial-engine\.claude\worktrees\quizzical-dirac\engines\shared\case_type_plugin.py
C:\Users\david\dev\case-adversarial-engine\.claude\worktrees\relaxed-cartwright\engines\shared\case_type_plugin.py
C:\Users\david\dev\case-adversarial-engine\.claude\worktrees\relaxed-edison\engines\shared\case_type_plugin.py
C:\Users\david\dev\case-adversarial-engine\.claude\worktrees\romantic-moser\engines\shared\case_type_plugin.py
C:\Users\david\dev\case-adversarial-engine\.claude\worktrees\sad-tu\engines\shared\case_type_plugin.py
C:\Users\david\dev\case-adversarial-engine\.claude\worktrees\serene-leakey\engines\shared\case_type_plugin.py
C:\Users\david\dev\case-adversarial-engine\.claude\worktrees\stoic-albattani\engines\shared\case_type_plugin.py
C:\Users\david\dev\case-adversarial-engine\.claude\worktrees\strange-pare\engines\shared\case_type_plugin.py
C:\Users\david\dev\case-adversarial-engine\.claude\worktrees\tender-wright\engines\shared\case_type_plugin.py
C:\Users\david\dev\case-adversarial-engine\.claude\worktrees\thirsty-hopper\engines\shared\case_type_plugin.py
C:\Users\david\dev\case-adversarial-engine\.claude\worktrees\trusting-brown\engines\shared\case_type_plugin.py
C:\Users\david\dev\case-adversarial-engine\.claude\worktrees\unruffled-snyder\engines\shared\case_type_plugin.py
C:\Users\david\dev\case-adversarial-engine\.claude\worktrees\vigilant-wescoff\engines\shared\case_type_plugin.py
C:\Users\david\dev\case-adversarial-engine\.claude\worktrees\vigorous-villani\engines\shared\case_type_plugin.py
C:\Users\david\dev\case-adversarial-engine\engines\shared\case_type_plugin.py
Cannot set property. Property setting is supported only on core types in this language mode.
At line:1 char:1
+ [Console]::OutputEncoding=[System.Text.Encoding]::UTF8;
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : InvalidOperation: (:) [], RuntimeException
    + FullyQualifiedErrorId : PropertySetterNotSupportedInConstrainedLanguage
 
Get-ChildItem : Access to the path 
'C:\Users\david\dev\case-adversarial-engine\.claude\worktrees\affectionate-chebyshev\.pytest_cache' is denied.
At line:2 char:1
+ Get-ChildItem -Path . -Recurse -File -Filter 'case_type_plugin.py' |  ...
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : PermissionDenied: (C:\Users\david\...v\.pytest_cache:String) [Get-ChildItem], Unauthoriz 
   edAccessException
    + FullyQualifiedErrorId : DirUnauthorizedAccessError,Microsoft.PowerShell.Commands.GetChildItemCommand
 
Get-ChildItem : Access to the path 
'C:\Users\david\dev\case-adversarial-engine\.claude\worktrees\batch-5-phase-c\.pytest_cache' is denied.
At line:2 char:1
+ Get-ChildItem -Path . -Recurse -File -Filter 'case_type_plugin.py' |  ...
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : PermissionDenied: (C:\Users\david\...c\.pytest_cache:String) [Get-ChildItem], Unauthoriz 
   edAccessException
    + FullyQualifiedErrorId : DirUnauthorizedAccessError,Microsoft.PowerShell.Commands.GetChildItemCommand
 
Get-ChildItem : Access to the path 
'C:\Users\david\dev\case-adversarial-engine\.claude\worktrees\bold-rhodes\.pytest_cache' is denied.
At line:2 char:1
+ Get-ChildItem -Path . -Recurse -File -Filter 'case_type_plugin.py' |  ...
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : PermissionDenied: (C:\Users\david\...s\.pytest_cache:String) [Get-ChildItem], Unauthoriz 
   edAccessException
    + FullyQualifiedErrorId : DirUnauthorizedAccessError,Microsoft.PowerShell.Commands.GetChildItemCommand
 
Get-ChildItem : Access to the path 
'C:\Users\david\dev\case-adversarial-engine\.claude\worktrees\competent-lamarr\.pytest_cache' is denied.
At line:2 char:1
+ Get-ChildItem -Path . -Recurse -File -Filter 'case_type_plugin.py' |  ...
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : PermissionDenied: (C:\Users\david\...r\.pytest_cache:String) [Get-ChildItem], Unauthoriz 
   edAccessException
    + FullyQualifiedErrorId : DirUnauthorizedAccessError,Microsoft.PowerShell.Commands.GetChildItemCommand
 
Get-ChildItem : Access to the path 
'C:\Users\david\dev\case-adversarial-engine\.claude\worktrees\eager-pare\.pytest_cache' is denied.
At line:2 char:1
+ Get-ChildItem -Path . -Recurse -File -Filter 'case_type_plugin.py' |  ...
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : PermissionDenied: (C:\Users\david\...e\.pytest_cache:String) [Get-ChildItem], Unauthoriz 
   edAccessException
    + FullyQualifiedErrorId : DirUnauthorizedAccessError,Microsoft.PowerShell.Commands.GetChildItemCommand
 
Get-ChildItem : Access to the path 
'C:\Users\david\dev\case-adversarial-engine\.claude\worktrees\exciting-blackburn\.pytest_cache' is denied.
At line:2 char:1
+ Get-ChildItem -Path . -Recurse -File -Filter 'case_type_plugin.py' |  ...
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : PermissionDenied: (C:\Users\david\...n\.pytest_cache:String) [Get-ChildItem], Unauthoriz 
   edAccessException
    + FullyQualifiedErrorId : DirUnauthorizedAccessError,Microsoft.PowerShell.Commands.GetChildItemCommand
 
Get-ChildItem : Access to the path 
'C:\Users\david\dev\case-adversarial-engine\.claude\worktrees\flamboyant-nightingale\.pytest_cache' is denied.
At line:2 char:1
+ Get-ChildItem -Path . -Recurse -File -Filter 'case_type_plugin.py' |  ...
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : PermissionDenied: (C:\Users\david\...e\.pytest_cache:String) [Get-ChildItem], Unauthoriz 
   edAccessException
    + FullyQualifiedErrorId : DirUnauthorizedAccessError,Microsoft.PowerShell.Commands.GetChildItemCommand
 
Get-ChildItem : Access to the path 
'C:\Users\david\dev\case-adversarial-engine\.claude\worktrees\infallible-vaughan\.pytest_cache' is denied.
At line:2 char:1
+ Get-ChildItem -Path . -Recurse -File -Filter 'case_type_plugin.py' |  ...
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : PermissionDenied: (C:\Users\david\...n\.pytest_cache:String) [Get-ChildItem], Unauthoriz 
   edAccessException
    + FullyQualifiedErrorId : DirUnauthorizedAccessError,Microsoft.PowerShell.Commands.GetChildItemCommand
 
Get-ChildItem : Access to the path 
'C:\Users\david\dev\case-adversarial-engine\.claude\worktrees\interesting-hopper\.pytest_cache' is denied.
At line:2 char:1
+ Get-ChildItem -Path . -Recurse -File -Filter 'case_type_plugin.py' |  ...
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : PermissionDenied: (C:\Users\david\...r\.pytest_cache:String) [Get-ChildItem], Unauthoriz 
   edAccessException
    + FullyQualifiedErrorId : DirUnauthorizedAccessError,Microsoft.PowerShell.Commands.GetChildItemCommand
 
Get-ChildItem : Access to the path 
'C:\Users\david\dev\case-adversarial-engine\.claude\worktrees\jolly-roentgen\.pytest_cache' is denied.
At line:2 char:1
+ Get-ChildItem -Path . -Recurse -File -Filter 'case_type_plugin.py' |  ...
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : PermissionDenied: (C:\Users\david\...n\.pytest_cache:String) [Get-ChildItem], Unauthoriz 
   edAccessException
    + FullyQualifiedErrorId : DirUnauthorizedAccessError,Microsoft.PowerShell.Commands.GetChildItemCommand
 
Get-ChildItem : Access to the path 
'C:\Users\david\dev\case-adversarial-engine\.claude\worktrees\jovial-kepler\.pytest_cache' is denied.
At line:2 char:1
+ Get-ChildItem -Path . -Recurse -File -Filter 'case_type_plugin.py' |  ...
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : PermissionDenied: (C:\Users\david\...r\.pytest_cache:String) [Get-ChildItem], Unauthoriz 
   edAccessException
    + FullyQualifiedErrorId : DirUnauthorizedAccessError,Microsoft.PowerShell.Commands.GetChildItemCommand
 
Get-ChildItem : Access to the path 
'C:\Users\david\dev\case-adversarial-engine\.claude\worktrees\laughing-austin\.pytest_cache' is denied.
At line:2 char:1
+ Get-ChildItem -Path . -Recurse -File -Filter 'case_type_plugin.py' |  ...
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : PermissionDenied: (C:\Users\david\...n\.pytest_cache:String) [Get-ChildItem], Unauthoriz 
   edAccessException
    + FullyQualifiedErrorId : DirUnauthorizedAccessError,Microsoft.PowerShell.Commands.GetChildItemCommand
 
Get-ChildItem : Access to the path 
'C:\Users\david\dev\case-adversarial-engine\.claude\worktrees\magical-heisenberg\.pytest_cache' is denied.
At line:2 char:1
+ Get-ChildItem -Path . -Recurse -File -Filter 'case_type_plugin.py' |  ...
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : PermissionDenied: (C:\Users\david\...g\.pytest_cache:String) [Get-ChildItem], Unauthoriz 
   edAccessException
    + FullyQualifiedErrorId : DirUnauthorizedAccessError,Microsoft.PowerShell.Commands.GetChildItemCommand
 
Get-ChildItem : Access to the path 
'C:\Users\david\dev\case-adversarial-engine\.claude\worktrees\magical-tesla\.pytest_cache' is denied.
At line:2 char:1
+ Get-ChildItem -Path . -Recurse -File -Filter 'case_type_plugin.py' |  ...
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : PermissionDenied: (C:\Users\david\...a\.pytest_cache:String) [Get-ChildItem], Unauthoriz 
   edAccessException
    + FullyQualifiedErrorId : DirUnauthorizedAccessError,Microsoft.PowerShell.Commands.GetChildItemCommand
 
Get-ChildItem : Access to the path 
'C:\Users\david\dev\case-adversarial-engine\.claude\worktrees\nervous-brattain\.pytest_cache' is denied.
At line:2 char:1
+ Get-ChildItem -Path . -Recurse -File -Filter 'case_type_plugin.py' |  ...
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : PermissionDenied: (C:\Users\david\...n\.pytest_cache:String) [Get-ChildItem], Unauthoriz 
   edAccessException
    + FullyQualifiedErrorId : DirUnauthorizedAccessError,Microsoft.PowerShell.Commands.GetChildItemCommand
 
Get-ChildItem : Access to the path 
'C:\Users\david\dev\case-adversarial-engine\.claude\worktrees\optimistic-khorana\.pytest_cache' is denied.
At line:2 char:1
+ Get-ChildItem -Path . -Recurse -File -Filter 'case_type_plugin.py' |  ...
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : PermissionDenied: (C:\Users\david\...a\.pytest_cache:String) [Get-ChildItem], Unauthoriz 
   edAccessException
    + FullyQualifiedErrorId : DirUnauthorizedAccessError,Microsoft.PowerShell.Commands.GetChildItemCommand
 
Get-ChildItem : Access to the path 
'C:\Users\david\dev\case-adversarial-engine\.claude\worktrees\pedantic-allen\.pytest_cache' is denied.
At line:2 char:1
+ Get-ChildItem -Path . -Recurse -File -Filter 'case_type_plugin.py' |  ...
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : PermissionDenied: (C:\Users\david\...n\.pytest_cache:String) [Get-ChildItem], Unauthoriz 
   edAccessException
    + FullyQualifiedErrorId : DirUnauthorizedAccessError,Microsoft.PowerShell.Commands.GetChildItemCommand
 
Get-ChildItem : Access to the path 
'C:\Users\david\dev\case-adversarial-engine\.claude\worktrees\quirky-darwin\.pytest_cache' is denied.
At line:2 char:1
+ Get-ChildItem -Path . -Recurse -File -Filter 'case_type_plugin.py' |  ...
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : PermissionDenied: (C:\Users\david\...n\.pytest_cache:String) [Get-ChildItem], Unauthoriz 
   edAccessException
    + FullyQualifiedErrorId : DirUnauthorizedAccessError,Microsoft.PowerShell.Commands.GetChildItemCommand
 
Get-ChildItem : Access to the path 
'C:\Users\david\dev\case-adversarial-engine\.claude\worktrees\quizzical-dirac\.pytest_cache' is denied.
At line:2 char:1
+ Get-ChildItem -Path . -Recurse -File -Filter 'case_type_plugin.py' |  ...
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : PermissionDenied: (C:\Users\david\...c\.pytest_cache:String) [Get-ChildItem], Unauthoriz 
   edAccessException
    + FullyQualifiedErrorId : DirUnauthorizedAccessError,Microsoft.PowerShell.Commands.GetChildItemCommand
 
Get-ChildItem : Access to the path 
'C:\Users\david\dev\case-adversarial-engine\.claude\worktrees\relaxed-cartwright\.pytest_cache' is denied.
At line:2 char:1
+ Get-ChildItem -Path . -Recurse -File -Filter 'case_type_plugin.py' |  ...
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : PermissionDenied: (C:\Users\david\...t\.pytest_cache:String) [Get-ChildItem], Unauthoriz 
   edAccessException
    + FullyQualifiedErrorId : DirUnauthorizedAccessError,Microsoft.PowerShell.Commands.GetChildItemCommand
 
Get-ChildItem : Access to the path 
'C:\Users\david\dev\case-adversarial-engine\.claude\worktrees\relaxed-edison\.pytest_cache' is denied.
At line:2 char:1
+ Get-ChildItem -Path . -Recurse -File -Filter 'case_type_plugin.py' |  ...
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : PermissionDenied: (C:\Users\david\...n\.pytest_cache:String) [Get-ChildItem], Unauthoriz 
   edAccessException
    + FullyQualifiedErrorId : DirUnauthorizedAccessError,Microsoft.PowerShell.Commands.GetChildItemCommand
 
Get-ChildItem : Access to the path 'C:\Users\david\dev\case-adversarial-engine\.claude\worktrees\sad-tu\.pytest_cache' 
is denied.
At line:2 char:1
+ Get-ChildItem -Path . -Recurse -File -Filter 'case_type_plugin.py' |  ...
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : PermissionDenied: (C:\Users\david\...u\.pytest_cache:String) [Get-ChildItem], Unauthoriz 
   edAccessException
    + FullyQualifiedErrorId : DirUnauthorizedAccessError,Microsoft.PowerShell.Commands.GetChildItemCommand
 
Get-ChildItem : Access to the path 
'C:\Users\david\dev\case-adversarial-engine\.claude\worktrees\stoic-albattani\.pytest_cache' is denied.
At line:2 char:1
+ Get-ChildItem -Path . -Recurse -File -Filter 'case_type_plugin.py' |  ...
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : PermissionDenied: (C:\Users\david\...i\.pytest_cache:String) [Get-ChildItem], Unauthoriz 
   edAccessException
    + FullyQualifiedErrorId : DirUnauthorizedAccessError,Microsoft.PowerShell.Commands.GetChildItemCommand
 
Get-ChildItem : Access to the path 
'C:\Users\david\dev\case-adversarial-engine\.claude\worktrees\tender-wright\.pytest_cache' is denied.
At line:2 char:1
+ Get-ChildItem -Path . -Recurse -File -Filter 'case_type_plugin.py' |  ...
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : PermissionDenied: (C:\Users\david\...t\.pytest_cache:String) [Get-ChildItem], Unauthoriz 
   edAccessException
    + FullyQualifiedErrorId : DirUnauthorizedAccessError,Microsoft.PowerShell.Commands.GetChildItemCommand
 
Get-ChildItem : Access to the path 
'C:\Users\david\dev\case-adversarial-engine\.claude\worktrees\unruffled-snyder\.pytest_cache' is denied.
At line:2 char:1
+ Get-ChildItem -Path . -Recurse -File -Filter 'case_type_plugin.py' |  ...
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : PermissionDenied: (C:\Users\david\...r\.pytest_cache:String) [Get-ChildItem], Unauthoriz 
   edAccessException
    + FullyQualifiedErrorId : DirUnauthorizedAccessError,Microsoft.PowerShell.Commands.GetChildItemCommand
 
Get-ChildItem : Access to the path 
'C:\Users\david\dev\case-adversarial-engine\.claude\worktrees\vigilant-wescoff\.pytest_cache' is denied.
At line:2 char:1
+ Get-ChildItem -Path . -Recurse -File -Filter 'case_type_plugin.py' |  ...
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : PermissionDenied: (C:\Users\david\...f\.pytest_cache:String) [Get-ChildItem], Unauthoriz 
   edAccessException
    + FullyQualifiedErrorId : DirUnauthorizedAccessError,Microsoft.PowerShell.Commands.GetChildItemCommand
 
Get-ChildItem : Access to the path 'C:\Users\david\dev\case-adversarial-engine\.pytest_cache' is denied.
At line:2 char:1
+ Get-ChildItem -Path . -Recurse -File -Filter 'case_type_plugin.py' |  ...
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : PermissionDenied: (C:\Users\david\...e\.pytest_cache:String) [Get-ChildItem], Unauthoriz 
   edAccessException
    + FullyQualifiedErrorId : DirUnauthorizedAccessError,Microsoft.PowerShell.Commands.GetChildItemCommand
 

exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -NoProfile -Command "Get-Content 'engines/shared/case_type_plugin.py'" in C:/Users/david/dev/case-adversarial-engine
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -NoProfile -Command "Get-Content 'engines/case_structuring/amount_calculator/calculator.py' | Select-Object -First 260" in C:/Users/david/dev/case-adversarial-engine
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -NoProfile -Command "Get-Content 'engines/procedure_setup/engine.py' | Select-Object -First 260" in C:/Users/david/dev/case-adversarial-engine
 succeeded in 563ms:
"""CaseTypePlugin Protocol + UnsupportedCaseTypeError.

Formalizes the PROMPT_REGISTRY pattern as a Python Protocol so that
case-type-specific prompt sources are expressed through a common interface.

Usage::

    from engines.shared.case_type_plugin import CaseTypePlugin, RegistryPlugin, UnsupportedCaseTypeError

    # Wrap an existing PROMPT_REGISTRY
    plugin = RegistryPlugin(PROMPT_REGISTRY)

    # Retrieve a user prompt string
    prompt = plugin.get_prompt("action_recommender", "civil_loan", context)

    # Retrieve the legal vocabulary the LLM is allowed to emit for impact_targets
    allowed = plugin.allowed_impact_targets("civil_loan")

    # Unknown case types raise UnsupportedCaseTypeError (not KeyError)
    plugin.get_prompt("engine", "unknown", {})  # raises UnsupportedCaseTypeError
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


class UnsupportedCaseTypeError(Exception):
    """Raised when a case type is not registered in a CaseTypePlugin."""

    def __init__(self, case_type: str, available: list[str] | None = None) -> None:
        self.case_type = case_type
        self.available = available or []
        if self.available:
            msg = f"ä¸æ”¯æŒçš„æ¡ˆç”±ç±»åž‹: '{case_type}'ã€‚å¯ç”? {', '.join(self.available)}"
        else:
            msg = f"ä¸æ”¯æŒçš„æ¡ˆç”±ç±»åž‹: '{case_type}'"
        super().__init__(msg)


@runtime_checkable
class CaseTypePlugin(Protocol):
    """Protocol for case-type-specific prompt generation.

    Each simulation_run engine wraps its PROMPT_REGISTRY in a
    ``RegistryPlugin`` that satisfies this Protocol.
    """

    def get_prompt(self, engine_name: str, case_type: str, context: dict) -> str:
        """Build and return the user prompt for the given case type.

        Args:
            engine_name: Identifier of the calling engine (e.g. ``"action_recommender"``).
            case_type:   Case type key (e.g. ``"civil_loan"``).
            context:     Keyword arguments forwarded to the underlying
                         ``build_user_prompt`` callable.

        Returns:
            A non-empty prompt string.

        Raises:
            UnsupportedCaseTypeError: When *case_type* is not registered.
        """
        ...  # pragma: no cover

    def allowed_impact_targets(self, case_type: str) -> frozenset[str]:
        """Return the legal vocabulary for ``Issue.impact_targets`` for *case_type*.

        Engines whose prompt modules emit an ``impact_targets`` field (currently
        only ``issue_impact_ranker``) declare their per-case-type vocabulary by
        exposing an ``ALLOWED_IMPACT_TARGETS: frozenset[str]`` constant on the
        registry entry. The ranker uses this set to silently drop unknown values
        the LLM may hallucinate.

        Engines that do not need this concept simply do not call this method;
        their prompt modules are not required to declare the constant.

        Args:
            case_type: Case type key (e.g. ``"civil_loan"``).

        Returns:
            A frozenset of allowed impact-target string values.

        Raises:
            UnsupportedCaseTypeError: When *case_type* is not registered.
            ValueError: When the registered entry does not declare
                ``ALLOWED_IMPACT_TARGETS``.
        """
        ...  # pragma: no cover


class RegistryPlugin:
    """``CaseTypePlugin`` implementation backed by a PROMPT_REGISTRY dict.

    Supports two registry-entry formats used across simulation_run engines:

    * **Module-based**: entry is a Python module with a
      ``build_user_prompt(**context)`` function. The module may also expose
      an ``ALLOWED_IMPACT_TARGETS: frozenset[str]`` attribute (consumed by
      ``allowed_impact_targets`` only).
    * **Dict-based**: entry is a ``dict`` with a ``"build_user"`` callable.
      The dict may also contain an ``"allowed_impact_targets"`` key whose
      value is a ``frozenset[str]``.

    Existing ``PROMPT_REGISTRY`` dicts remain unchanged; this class is a
    thin wrapper that adds Protocol compliance and raises
    ``UnsupportedCaseTypeError`` instead of ``KeyError`` for missing keys.
    """

    def __init__(self, registry: dict[str, Any]) -> None:
        self._registry = registry

    def get_prompt(self, engine_name: str, case_type: str, context: dict) -> str:
        """Return the built user prompt for the given case type.

        Raises:
            UnsupportedCaseTypeError: When *case_type* is not registered.
        """
        if case_type not in self._registry:
            raise UnsupportedCaseTypeError(case_type, list(self._registry.keys()))
        entry = self._registry[case_type]
        if isinstance(entry, dict):
            build_fn = entry["build_user"]
        else:
            build_fn = entry.build_user_prompt
        return build_fn(**context)

    def allowed_impact_targets(self, case_type: str) -> frozenset[str]:
        """Return the per-case-type ``ALLOWED_IMPACT_TARGETS`` set.

        Looks up the registered entry for *case_type* and reads:
          * ``entry["allowed_impact_targets"]`` for dict-based entries, or
          * ``entry.ALLOWED_IMPACT_TARGETS`` for module-based entries.

        Raises:
            UnsupportedCaseTypeError: When *case_type* is not registered.
            ValueError: When the entry exists but does not declare the
                vocabulary. This indicates a programming bug â€?any engine that
                calls ``allowed_impact_targets`` MUST guarantee its prompt
                modules declare the constant.
        """
        if case_type not in self._registry:
            raise UnsupportedCaseTypeError(case_type, list(self._registry.keys()))
        entry = self._registry[case_type]
        if isinstance(entry, dict):
            if "allowed_impact_targets" not in entry:
                raise ValueError(
                    f"æ¡ˆç”± '{case_type}' çš?dict-style æ³¨å†Œæ¡ç›®æœªå£°æ˜?"
                    "'allowed_impact_targets' â€?è¯¥å­—æ®µå¯¹è°ƒç”¨ "
                    "plugin.allowed_impact_targets(...) çš„å¼•æ“Žæ˜¯å¿…éœ€çš„ã€?
                )
            value = entry["allowed_impact_targets"]
        else:
            if not hasattr(entry, "ALLOWED_IMPACT_TARGETS"):
                raise ValueError(
                    f"æ¡ˆç”± '{case_type}' çš?module-style æ³¨å†Œæ¡ç›®æœªå£°æ˜?"
                    "ALLOWED_IMPACT_TARGETS â€?è¯¥å¸¸é‡å¯¹è°ƒç”¨ "
                    "plugin.allowed_impact_targets(...) çš„å¼•æ“Žæ˜¯å¿…éœ€çš„ã€?
                )
            value = entry.ALLOWED_IMPACT_TARGETS
        return frozenset(value)
Cannot set property. Property setting is supported only on core types in this language mode.
At line:1 char:1
+ [Console]::OutputEncoding=[System.Text.Encoding]::UTF8;
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : InvalidOperation: (:) [], RuntimeException
    + FullyQualifiedErrorId : PropertySetterNotSupportedInConstrainedLanguage
 

2026-04-07T11:28:58.419578Z ERROR codex_core::tools::router: error=Exit code: 1
Wall time: 0.6 seconds
Output:
Cannot set property. Property setting is supported only on core types in this language mode.
At line:1 char:1
+ [Console]::OutputEncoding=[System.Text.Encoding]::UTF8;
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : InvalidOperation: (:) [], RuntimeException
    + FullyQualifiedErrorId : PropertySetterNotSupportedInConstrainedLanguage
 
Get-Content : Cannot find path 'C:\Users\david\dev\case-adversarial-engine\engines\procedure_setup\engine.py' because 
it does not exist.
At line:2 char:1
+ Get-Content 'engines/procedure_setup/engine.py' | Select-Object -Firs ...
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : ObjectNotFound: (C:\Users\david\...setup\engine.py:String) [Get-Content], ItemNotFoundEx 
   ception
    + FullyQualifiedErrorId : PathNotFound,Microsoft.PowerShell.Commands.GetContentCommand
 

 exited 1 in 618ms:
Cannot set property. Property setting is supported only on core types in this language mode.
At line:1 char:1
+ [Console]::OutputEncoding=[System.Text.Encoding]::UTF8;
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : InvalidOperation: (:) [], RuntimeException
    + FullyQualifiedErrorId : PropertySetterNotSupportedInConstrainedLanguage
 
Get-Content : Cannot find path 'C:\Users\david\dev\case-adversarial-engine\engines\procedure_setup\engine.py' because 
it does not exist.
At line:2 char:1
+ Get-Content 'engines/procedure_setup/engine.py' | Select-Object -Firs ...
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : ObjectNotFound: (C:\Users\david\...setup\engine.py:String) [Get-Content], ItemNotFoundEx 
   ception
    + FullyQualifiedErrorId : PathNotFound,Microsoft.PowerShell.Commands.GetContentCommand
 

 succeeded in 648ms:
"""
AmountCalculator â€?é‡‘é¢/è¯‰è¯·ä¸€è‡´æ€§ç¡¬æ ¡éªŒæ¨¡å—ã€?
Amount/claim consistency hard validation module.

çº¯è§„åˆ™å±‚ï¼ˆdeterministicï¼‰ï¼Œä¸è°ƒç”?LLMã€?
Pure rule layer (deterministic), no LLM calls.

èŒè´£ / Responsibilities:
1. æŽ¥æ”¶è°ƒç”¨æ–¹æä¾›çš„å››ç±»ç»“æž„åŒ–è¾“å…¥ï¼ˆæ”¾æ¬¾æµæ°´ã€è¿˜æ¬¾æµæ°´ã€äº‰è®®å½’å› ã€è¯‰è¯·æè¿°ç¬¦ï¼?
2. è®¡ç®— principal ç±»è¯‰è¯·çš„ calculated_amountï¼ˆå…¶ä»–ç±»åž‹è¿”å›?Noneï¼?
3. æ‰§è¡Œä¸ƒæ¡ç¡¬æ ¡éªŒè§„åˆ?
4. ç”Ÿæˆ AmountConflict åˆ—è¡¨
5. æ¿€æ´?verdict_block_activeï¼ˆå½“ unresolved_conflicts éžç©ºæ—¶ï¼‰
6. è¿”å›ž AmountCalculationReport
"""

from __future__ import annotations

from decimal import Decimal
from typing import Iterator
from uuid import uuid4

from engines.shared.models import (
    AmountCalculationReport,
    AmountConflict,
    AmountConsistencyCheck,
    ClaimCalculationEntry,
    ClaimType,
    ContractValidity,
    DisputeResolutionStatus,
    InterestRecalculation,
    LoanTransaction,
    RepaymentAttribution,
    RepaymentTransaction,
)
from engines.shared.rule_config import RuleThresholds

from .schemas import AmountCalculatorInput


class AmountCalculator:
    """
    é‡‘é¢/è¯‰è¯·ä¸€è‡´æ€§ç¡®å®šæ€§è®¡ç®—å™¨ã€?

    æ‰€æœ‰æ–¹æ³•å‡ä¸ºåŒæ­¥çº¯å‡½æ•°ï¼Œä¸æŒæœ‰å¤–éƒ¨çŠ¶æ€ï¼Œå¯å®‰å…¨å¤ç”¨åŒä¸€å®žä¾‹ã€?

    ä½¿ç”¨æ–¹å¼ / Usage:
        calc = AmountCalculator()
        report = calc.calculate(inp)
    """

    def __init__(self, thresholds: RuleThresholds | None = None) -> None:
        self._thresholds = thresholds or RuleThresholds()

    def calculate(self, inp: AmountCalculatorInput) -> AmountCalculationReport:
        """
        æ‰§è¡Œé‡‘é¢ä¸€è‡´æ€§æ ¡éªŒï¼Œè¿”å›žå®Œæ•´æŠ¥å‘Šã€?

        Args:
            inp: è®¡ç®—å™¨è¾“å…¥ï¼ŒåŒ…å«å››ç±»ç»“æž„åŒ–æ•°æ?

        Returns:
            AmountCalculationReport â€?å«å››å¼ è¡¨å’Œäº”æ¡ç¡¬è§„åˆ™ç»“æžœ
        """
        # è§„åˆ™ #7ï¼šåˆåŒæ— æ•?äº‰è®®æ—¶åˆ©æ¯é‡ç®—ï¼ˆéœ€è¦?conflicts åˆ—è¡¨ä¼ å…¥ä»¥è®°å½•ç¼ºå¤±è­¦å‘Šï¼‰
        principal_base = self._sum_principal_loans(inp.loan_transactions)

        # 1. æž„å»ºè¯‰è¯·è®¡ç®—è¡?
        claim_table = self._build_claim_calculation_table(
            inp.claim_entries,
            inp.loan_transactions,
            inp.repayment_transactions,
        )

        # 2. æ‰§è¡Œäº”æ¡ç¡¬è§„åˆ?
        principal_base_unique = self._check_principal_base_unique(inp.disputed_amount_attributions)
        all_attributed = self._check_all_repayments_attributed(inp.repayment_transactions)
        text_table_consistent = self._check_text_table_consistent(claim_table)
        duplicate_claim = self._check_duplicate_interest_penalty(inp.claim_entries)
        total_reconstructable = self._check_total_reconstructable(claim_table)

        # è§„åˆ™ #6ï¼šèµ·è¯‰æ€»é¢ / å¯æ ¸å®žäº¤ä»˜æ€»é¢ æ¯”å€¼æ ¡éª?
        claim_delivery_ratio_normal = self._check_claim_delivery_ratio(
            inp.claim_entries, inp.loan_transactions
        )

        # 3. ç”Ÿæˆå†²çªåˆ—è¡¨
        conflicts = list(
            self._generate_conflicts(
                claim_table=claim_table,
                disputed_attributions=inp.disputed_amount_attributions,
                loan_transactions=inp.loan_transactions,
            )
        )

        # æ¥æº 3ï¼šèµ·è¯‰é‡‘é¢?å¯æ ¸å®žäº¤ä»˜æ¯”å€¼å¼‚å¸¸ï¼ˆrule #6ï¼?
        if not claim_delivery_ratio_normal:
            delivered = self._sum_principal_loans(inp.loan_transactions)
            total_claimed = sum(c.claimed_amount for c in inp.claim_entries)
            if delivered == Decimal("0"):
                ratio_desc = "âˆžï¼ˆå¯æ ¸å®žäº¤ä»˜ä¸ºé›¶ï¼‰"
            else:
                ratio_desc = f"{total_claimed / delivered:.2f}"
            conflicts.append(
                AmountConflict(
                    conflict_id=f"conflict-{len(conflicts) + 1:03d}",
                    conflict_description=(
                        f"ã€è™šå‡è¯‰è®¼é¢„è­¦ã€‘èµ·è¯‰æ€»é¢ {total_claimed} / å¯æ ¸å®žäº¤ä»?{delivered}"
                        f" = {ratio_desc}ï¼Œè¶…å‡ºé¢„è­¦é˜ˆå€?{self._thresholds.false_litigation_ratio}"
                    ),
                    amount_a=total_claimed,
                    amount_b=delivered,
                    source_a_evidence_id="",
                    source_b_evidence_id="",
                    resolution_note="",
                )
            )

        # è§„åˆ™ #7ï¼šåˆåŒæ— æ•?äº‰è®®æ—¶åˆ©æ¯é‡ç®—ï¼ˆä¼ å…¥ conflicts ä»¥è®°å½•ç¼ºå¤±è­¦å‘Šï¼‰
        interest_recalc = self._recalculate_interest(inp, principal_base, conflicts)

        # 4. verdict_block_active ç¡¬è§„åˆ™ï¼šunresolved_conflicts éžç©ºæ—¶å¿…é¡»ä¸º True
        verdict_block_active = len(conflicts) > 0

        consistency = AmountConsistencyCheck(
            principal_base_unique=principal_base_unique,
            all_repayments_attributed=all_attributed,
            text_table_amount_consistent=text_table_consistent,
            duplicate_interest_penalty_claim=duplicate_claim,
            claim_total_reconstructable=total_reconstructable,
            unresolved_conflicts=conflicts,
            verdict_block_active=verdict_block_active,
            claim_delivery_ratio_normal=claim_delivery_ratio_normal,
        )

        return AmountCalculationReport(
            report_id=f"amount-report-{uuid4().hex[:8]}",
            case_id=inp.case_id,
            run_id=inp.run_id,
            loan_transactions=inp.loan_transactions,
            repayment_transactions=inp.repayment_transactions,
            disputed_amount_attributions=inp.disputed_amount_attributions,
            claim_calculation_table=claim_table,
            consistency_check_result=consistency,
            interest_recalculation=interest_recalc,
        )

    # ------------------------------------------------------------------
    # è¯‰è¯·è®¡ç®—è¡¨æž„å»?/ Claim calculation table
    # ------------------------------------------------------------------

    def _build_claim_calculation_table(
        self,
        claim_entries,
        loan_transactions: list[LoanTransaction],
        repayment_transactions: list[RepaymentTransaction],
    ) -> list[ClaimCalculationEntry]:
        """
        æž„å»ºè¯‰è¯·è®¡ç®—è¡¨ã€?

        principal ç±»è¯‰è¯·ï¼šcalculated_amount = æ€»æ”¾æ¬¾åŸºæ•?- æ€»è¿˜æ¬¾ï¼ˆå½’å›  principalï¼‰ã€?
        å…¶ä»–ç±»åž‹ï¼šcalculated_amount = Noneï¼ˆæ— æ³•ä»Žæµæ°´ç¡®å®šæ€§è®¡ç®—ï¼‰ã€?
        delta = claimed_amount - calculated_amountï¼ˆè‹¥ calculated_amount ä¸?None åˆ?delta = Noneï¼‰ã€?
        """
        principal_calculated = self._compute_principal_amount(
            loan_transactions, repayment_transactions
        )

        entries: list[ClaimCalculationEntry] = []
        for descriptor in claim_entries:
            if descriptor.claim_type == ClaimType.principal:
                calc_amt = principal_calculated
                delta = descriptor.claimed_amount - calc_amt
                principal_loans = self._sum_principal_loans(loan_transactions)
                principal_repaid = self._sum_principal_repayments(repayment_transactions)
                explanation = (
                    f"è®¡ç®—å€¼ï¼šæ€»æ”¾æ¬¾åŸºæ•?{principal_loans} "
                    f"- å·²è¿˜æœ¬é‡‘ {principal_repaid} "
                    f"= {calc_amt}"
                )
                if delta != Decimal("0"):
                    explanation += (
                        f"ï¼›å·®å€?{delta}"
                        f"ï¼ˆclaimed {descriptor.claimed_amount} vs calculated {calc_amt}ï¼?
                    )
            else:
                calc_amt = None
                delta = None
                explanation = (
                    f"{descriptor.claim_type.value} ç±»è¯‰è¯·æ— æ³•ä»Žæµæ°´ç¡®å®šæ€§è®¡ç®—ï¼Œ"
                    "éœ€ç»“åˆåˆåŒåˆ©çŽ‡/è¿çº¦é‡‘æ¡æ¬?
                )

            entries.append(
                ClaimCalculationEntry(
                    claim_id=descriptor.claim_id,
                    claim_type=descriptor.claim_type,
                    claimed_amount=descriptor.claimed_amount,
                    calculated_amount=calc_amt,
                    delta=delta,
                    delta_explanation=explanation,
                )
            )

        return entries

    def _sum_principal_loans(self, loans: list[LoanTransaction]) -> Decimal:
        """è®¡ç®— principal_base_contribution=True çš„æ”¾æ¬¾æ€»é¢ã€?""
        return sum(
            (loan.amount for loan in loans if loan.principal_base_contribution),
            Decimal("0"),
        )

    def _sum_principal_repayments(self, repayments: list[RepaymentTransaction]) -> Decimal:
        """è®¡ç®—å½’å›  principal çš„å·²è¿˜æ¬¾æ€»é¢ã€?""
        return sum(
            (r.amount for r in repayments if r.attributed_to == RepaymentAttribution.principal),
            Decimal("0"),
        )

    def _compute_principal_amount(
        self,
        loans: list[LoanTransaction],
        repayments: list[RepaymentTransaction],
    ) -> Decimal:
        """è®¡ç®—åº”è¿˜æœ¬é‡‘ = principal æ”¾æ¬¾æ€»é¢ - å·²è¿˜æœ¬é‡‘æ€»é¢ã€?""
        return self._sum_principal_loans(loans) - self._sum_principal_repayments(repayments)

    # ------------------------------------------------------------------
    # ç¡¬è§„åˆ?1ï¼šæœ¬é‡‘åŸºæ•°å”¯ä¸€æ€?/ principal_base_unique
    # ------------------------------------------------------------------

    def _check_principal_base_unique(self, disputed_attributions) -> bool:
        """
        æœ¬é‡‘åŸºæ•°å”¯ä¸€æ€§ï¼šå½“ä¸”ä»…å½“ä¸å­˜åœ?unresolved çš„äº‰è®®å½’å› æ¡ç›®æ—¶è¿”å›ž Trueã€?

        é€»è¾‘ï¼šè‹¥å­˜åœ¨ä»»ä½• resolution_status = unresolved çš„äº‰è®®é¡¹ï¼?
        è¡¨ç¤ºæœ¬é‡‘åŸºæ•°å­˜åœ¨æœªè§£å†³çš„å£å¾„åˆ†æ­§ï¼Œæ— æ³•å”¯ä¸€ç¡®å®šã€?
        """
        return not any(
            d.resolution_status == DisputeResolutionStatus.unresolved for d in disputed_attributions
        )

    # ------------------------------------------------------------------
    # ç¡¬è§„åˆ?2ï¼šæ¯ç¬”è¿˜æ¬¾å”¯ä¸€å½’å›  / all_repayments_attributed
    # ------------------------------------------------------------------

    def _check_all_repayments_attributed(self, repayments: list[RepaymentTransaction]) -> bool:
        """æ‰€æœ‰è¿˜æ¬¾å‡å·²å½’å› ï¼ˆattributed_to é?Noneï¼‰æ—¶è¿”å›ž Trueã€?""
        return all(r.attributed_to is not None for r in repayments)

    # ------------------------------------------------------------------
    # ç¡¬è§„åˆ?3ï¼šæ–‡æœ¬ä¸Žè¡¨æ ¼é‡‘é¢ä¸€è‡´æ€?/ text_table_consistent
    # ------------------------------------------------------------------

    def _check_text_table_consistent(self, claim_table: list[ClaimCalculationEntry]) -> bool:
        """
        æ‰€æœ‰å¯å¤ç®—è¯‰è¯·ï¼ˆcalculated_amount é?Noneï¼‰çš„ delta å‡ä¸ºé›¶æ—¶è¿”å›ž Trueã€?
        æ— æ³•è®¡ç®—çš„è¯‰è¯·ï¼ˆdelta = Noneï¼‰ä¸å‚ä¸Žæœ¬é¡¹æ ¡éªŒã€?
        """
Cannot set property. Property setting is supported only on core types in this language mode.
At line:1 char:1
+ [Console]::OutputEncoding=[System.Text.Encoding]::UTF8;
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : InvalidOperation: (:) [], RuntimeException
    + FullyQualifiedErrorId : PropertySetterNotSupportedInConstrainedLanguage
 

exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -NoProfile -Command "Get-ChildItem -Path 'engines/procedure_setup' -Recurse -File" in C:/Users/david/dev/case-adversarial-engine
 succeeded in 580ms:


    Directory: C:\Users\david\dev\case-adversarial-engine\engines\procedure_setup


Mode                 LastWriteTime         Length Name                                                                 
----                 -------------         ------ ----                                                                 
-a----          4/7/2026  12:57 PM          25485 planner.py                                                           
-a----          4/3/2026   1:47 AM            310 README.md                                                            
-a----         3/31/2026   9:58 PM           5489 schemas.py                                                           
-a----         3/31/2026   9:58 PM          16504 validator.py                                                         
-a----         3/25/2026   1:14 PM           1856 __init__.py                                                          


    Directory: C:\Users\david\dev\case-adversarial-engine\engines\procedure_setup\prompts


Mode                 LastWriteTime         Length Name                                                                 
----                 -------------         ------ ----                                                                 
-a----          4/7/2026  12:57 PM          11536 civil_loan.py                                                        
-a----          4/7/2026  12:57 PM          11003 labor_dispute.py                                                     
-a----          4/7/2026  12:57 PM          11119 real_estate.py                                                       
-a----          4/7/2026  12:01 PM            724 __init__.py                                                          


    Directory: C:\Users\david\dev\case-adversarial-engine\engines\procedure_setup\prompts\__pycache__


Mode                 LastWriteTime         Length Name                                                                 
----                 -------------         ------ ----                                                                 
-a----          4/7/2026  12:58 PM          12939 civil_loan.cpython-312.pyc                                           
-a----          4/7/2026  12:58 PM          12422 labor_dispute.cpython-312.pyc                                        
-a----          4/7/2026  12:58 PM          12536 real_estate.cpython-312.pyc                                          
-a----          4/7/2026  12:01 PM           1008 __init__.cpython-312.pyc                                             


    Directory: C:\Users\david\dev\case-adversarial-engine\engines\procedure_setup\tests


Mode                 LastWriteTime         Length Name                                                                 
----                 -------------         ------ ----                                                                 
-a----         3/31/2026   9:58 PM          14260 test_contract.py                                                     
-a----         3/31/2026   9:58 PM          34240 test_planner.py                                                      
-a----         3/25/2026  12:59 PM              0 __init__.py                                                          


    Directory: C:\Users\david\dev\case-adversarial-engine\engines\procedure_setup\tests\__pycache__


Mode                 LastWriteTime         Length Name                                                                 
----                 -------------         ------ ----                                                                 
-a----         3/31/2026   9:59 PM          43881 test_contract.cpython-312-pytest-9.0.2.pyc                           
-a----         3/31/2026   9:59 PM          69055 test_planner.cpython-312-pytest-9.0.2.pyc                            
-a----         3/25/2026   2:32 PM            181 __init__.cpython-312.pyc                                             


    Directory: C:\Users\david\dev\case-adversarial-engine\engines\procedure_setup\__pycache__


Mode                 LastWriteTime         Length Name                                                                 
----                 -------------         ------ ----                                                                 
-a----          4/7/2026  12:58 PM          20862 planner.cpython-312.pyc                                              
-a----         3/31/2026   9:59 PM           7142 schemas.cpython-312.pyc                                              
-a----         3/31/2026   9:59 PM          14217 validator.cpython-312.pyc                                            
-a----         3/25/2026   2:32 PM           1628 __init__.cpython-312.pyc                                             


Cannot set property. Property setting is supported only on core types in this language mode.
At line:1 char:1
+ [Console]::OutputEncoding=[System.Text.Encoding]::UTF8;
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : InvalidOperation: (:) [], RuntimeException
    + FullyQualifiedErrorId : PropertySetterNotSupportedInConstrainedLanguage
 

exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -NoProfile -Command "Get-Content 'engines/procedure_setup/planner.py' | Select-Object -First 260" in C:/Users/david/dev/case-adversarial-engine
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -NoProfile -Command "Get-ChildItem -Path 'engines/pretrial_conference' -Recurse -File" in C:/Users/david/dev/case-adversarial-engine
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -NoProfile -Command "Get-ChildItem -Path 'engines/document_assistance' -Recurse -File" in C:/Users/david/dev/case-adversarial-engine
 succeeded in 636ms:
"""
ç¨‹åºè®¾ç½®å¼•æ“Žæ ¸å¿ƒæ¨¡å—
Procedure setup engine core module.

æ ¹æ®æ¡ˆä»¶ç±»åž‹ï¼ˆcase_typeï¼‰ã€å½“äº‹äººä¿¡æ¯ï¼ˆpartiesï¼‰å’Œäº‰ç‚¹æ ‘ï¼ˆIssueTreeï¼‰ï¼Œ
é€šè¿‡ LLM ç”Ÿæˆç»“æž„åŒ–ç¨‹åºçŠ¶æ€åºåˆ—ï¼ˆProcedureState[]ï¼‰ã€ç¨‹åºé…ç½®å’Œæ—¶é—´çº¿äº‹ä»¶ã€?
Generates a structured ProcedureState sequence, config, and timeline events
from case_type, parties, and IssueTree via LLM.

åˆçº¦ä¿è¯ / Contract guarantees:
- procedure_states è¦†ç›–å…¨éƒ¨å…«ä¸ªæ³•å¾‹ç¨‹åºé˜¶æ®µ
- judge_questions é˜¶æ®µä¸è¯»å?owner_private
- output_branching é˜¶æ®µä»…åŸºäº?admitted_for_discussion è¯æ®
- state_id ç”±å¼•æ“Žç¡®å®šæ€§ç”Ÿæˆï¼Œä¸ä¾èµ?LLM
- next_state_ids æŒ‰é˜¶æ®µé¡ºåºç¡®å®šæ€§ç”Ÿæˆ?
- trigger_type å›ºå®šä¸?"procedure_setup"
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from engines.shared.models import LLMClient
from engines.shared.structured_output import call_structured_llm

from .schemas import (
    ArtifactRef,
    InputSnapshot,
    IssueTree,
    LLMProcedureConfig,
    LLMProcedureOutput,
    LLMProcedureState,
    MaterialRef,
    PHASE_ORDER,
    ProcedureConfig,
    ProcedureSetupInput,
    ProcedureSetupResult,
    ProcedureState,
    Run,
    TimelineEvent,
)

# tool_use JSON Schemaï¼ˆæ¨¡å—åŠ è½½æ—¶è®¡ç®—ä¸€æ¬¡ï¼‰
_TOOL_SCHEMA: dict = LLMProcedureOutput.model_json_schema()


# ---------------------------------------------------------------------------
# å·¥å…·å‡½æ•° / Utility functions
# ---------------------------------------------------------------------------


def _make_state_id(case_id: str, phase: str) -> str:
    """ç”Ÿæˆç¡®å®šæ€?state_idã€?
    Generate a deterministic state_id from case_id and phase.

    æ ¼å¼ / Format: pstate-{case_id}-{phase}-001
    """
    return f"pstate-{case_id}-{phase}-001"


def _build_next_state_ids(case_id: str, phase: str) -> list[str]:
    """æ ¹æ®é˜¶æ®µé¡ºåºç”Ÿæˆ next_state_idsï¼ˆç»ˆæ­¢é˜¶æ®µè¿”å›žç©ºåˆ—è¡¨ï¼‰ã€?
    Build next_state_ids based on phase order (returns [] for terminal phase).
    """
    try:
        idx = PHASE_ORDER.index(phase)
    except ValueError:
        return []
    if idx + 1 < len(PHASE_ORDER):
        next_phase = PHASE_ORDER[idx + 1]
        return [_make_state_id(case_id, next_phase)]
    # ç»ˆæ­¢é˜¶æ®µï¼ˆoutput_branchingï¼? Terminal phase
    return []


def _sanitize_access_domains(domains: list[str], phase: str) -> list[str]:
    """æ¸…ç†è®¿é—®åŸŸåˆ—è¡¨ï¼Œå¼ºåˆ¶æ‰§è¡Œ judge_questions çº¦æŸã€?
    Sanitize access domain list, enforcing judge_questions constraint.

    judge_questions é˜¶æ®µå¿…é¡»ç§»é™¤ owner_privateã€?
    owner_private must be removed from judge_questions phase.
    """
    if phase == "judge_questions":
        return [d for d in domains if d != "owner_private"]
    return domains


def _sanitize_evidence_statuses(statuses: list[str], phase: str) -> list[str]:
    """æ¸…ç†è¯æ®çŠ¶æ€åˆ—è¡¨ï¼Œå¼ºåˆ¶æ‰§è¡Œ output_branching çº¦æŸã€?
    Sanitize evidence status list, enforcing output_branching constraint.

    output_branching é˜¶æ®µåªå…è®?admitted_for_discussionã€?
    output_branching phase only allows admitted_for_discussion.
    """
    if phase == "output_branching":
        return ["admitted_for_discussion"]
    return statuses


# ---------------------------------------------------------------------------
# é»˜è®¤ç¨‹åºçŠ¶æ€æ•°æ®ï¼ˆå½?LLM æ— æœ‰æ•ˆè¾“å‡ºæ—¶ä½¿ç”¨ï¼?
# Default procedure state data (used when LLM returns no valid output)
# ---------------------------------------------------------------------------

_DEFAULT_PHASE_CONFIG: dict[str, dict] = {
    "case_intake": {
        "allowed_role_codes": ["plaintiff_agent", "judge_agent", "evidence_manager"],
        "readable_access_domains": ["shared_common"],
        "writable_object_types": ["Party", "Claim", "Evidence"],
        "admissible_evidence_statuses": ["private"],
        "entry_conditions": ["æ¡ˆä»¶ç™»è®°å®Œæˆ", "åŽŸå‘Šèµ·è¯‰çŠ¶å·²æŽ¥æ”¶"],
        "exit_conditions": ["è¢«å‘Šå·²æ”¶åˆ°åº”è¯‰é€šçŸ¥", "åŒæ–¹å½“äº‹äººèº«ä»½æ ¸å®žå®Œæ¯?],
    },
    "element_mapping": {
        "allowed_role_codes": ["plaintiff_agent", "defendant_agent", "judge_agent"],
        "readable_access_domains": ["shared_common"],
        "writable_object_types": ["Issue", "Burden", "Claim", "Defense"],
        "admissible_evidence_statuses": ["private", "submitted"],
        "entry_conditions": ["æ¡ˆä»¶å—ç†å®Œæ¯•"],
        "exit_conditions": ["äº‰ç‚¹æ ‘æ¢³ç†å®Œæˆ?, "ä¸¾è¯è´£ä»»åˆ†é…æ˜Žç¡®"],
    },
    "opening": {
        "allowed_role_codes": ["plaintiff_agent", "defendant_agent", "judge_agent"],
        "readable_access_domains": ["shared_common"],
        "writable_object_types": ["Claim", "Defense", "AgentOutput"],
        "admissible_evidence_statuses": ["submitted"],
        "entry_conditions": ["äº‰ç‚¹æ¢³ç†å®Œæˆ"],
        "exit_conditions": ["åŽŸå‘Šé™ˆè¿°æ„è§å®Œæ¯•", "è¢«å‘Šé™ˆè¿°æ„è§å®Œæ¯•"],
    },
    "evidence_submission": {
        "allowed_role_codes": ["plaintiff_agent", "defendant_agent", "evidence_manager"],
        "readable_access_domains": ["shared_common"],
        "writable_object_types": ["Evidence", "AgentOutput"],
        "admissible_evidence_statuses": ["private", "submitted"],
        "entry_conditions": ["ä¸¾è¯æœŸé™å·²å¼€å§?],
        "exit_conditions": ["ä¸¾è¯æœŸé™å±Šæ»¡", "åŒæ–¹è¯æ®å‡å·²æäº¤"],
    },
    "evidence_challenge": {
        "allowed_role_codes": [
            "plaintiff_agent",
            "defendant_agent",
            "evidence_manager",
            "judge_agent",
        ],
        "readable_access_domains": ["shared_common", "admitted_record"],
        "writable_object_types": ["Evidence", "AgentOutput"],
        "admissible_evidence_statuses": ["submitted", "challenged"],
        "entry_conditions": ["ä¸¾è¯æœŸé™å±Šæ»¡"],
        "exit_conditions": ["è´¨è¯ç¨‹åºå®Œæ¯•", "äº‰è®®è¯æ®çŠ¶æ€ç¡®å®?],
    },
    "judge_questions": {
        "allowed_role_codes": ["judge_agent"],
        "readable_access_domains": ["shared_common", "admitted_record"],
        "writable_object_types": ["AgentOutput"],
        "admissible_evidence_statuses": ["admitted_for_discussion"],
        "entry_conditions": ["è´¨è¯ç¨‹åºå®Œæ¯•"],
        "exit_conditions": ["æ³•å®˜é—®è¯¢å®Œæ¯•", "å½“äº‹äººé—®é¢˜å·²å›žå¤"],
    },
    "rebuttal": {
        "allowed_role_codes": ["plaintiff_agent", "defendant_agent", "judge_agent"],
        "readable_access_domains": ["shared_common", "admitted_record"],
        "writable_object_types": ["AgentOutput"],
        "admissible_evidence_statuses": ["admitted_for_discussion"],
        "entry_conditions": ["æ³•å®˜é—®è¯¢å®Œæ¯•"],
        "exit_conditions": ["åŒæ–¹è¾©è®ºæ„è§å®Œæ¯•"],
    },
    "output_branching": {
        "allowed_role_codes": ["judge_agent", "review_agent"],
        "readable_access_domains": ["shared_common", "admitted_record"],
        "writable_object_types": ["AgentOutput", "ReportArtifact"],
        "admissible_evidence_statuses": ["admitted_for_discussion"],
        "entry_conditions": ["è¾©è®ºç»ˆç»“"],
        "exit_conditions": ["ç»“è®ºæ€§æ„è§ç”Ÿæˆå®Œæ¯?, "äº‰ç‚¹å¤„ç†ç»“æžœè¾“å‡º"],
    },
}


# ---------------------------------------------------------------------------
# ä¸»å¼•æ“Žç±» / Main engine class
# ---------------------------------------------------------------------------


class ProcedurePlanner:
    """ç¨‹åºè®¾ç½®è§„åˆ’å™?
    Procedure Planner.

    è¾“å…¥ ProcedureSetupInput + IssueTreeï¼Œè¾“å‡?ProcedureSetupResultã€?
    Takes ProcedureSetupInput + IssueTree, outputs a ProcedureSetupResult.

    Args:
        llm_client: ç¬¦åˆ LLMClient åè®®çš„å®¢æˆ·ç«¯ / LLMClient-compatible client
        case_type: æ¡ˆç”±ç±»åž‹ï¼Œé»˜è®?"civil_loan" / Case type, default "civil_loan"
        model: LLM æ¨¡åž‹åç§° / LLM model name
        temperature: LLM æ¸©åº¦å‚æ•° / LLM temperature
        max_tokens: LLM æœ€å¤§è¾“å‡?token æ•?/ Max output tokens
        max_retries: LLM è°ƒç”¨å¤±è´¥æ—¶çš„æœ€å¤§é‡è¯•æ¬¡æ•?/ Max retries on failure
    """

    def __init__(
        self,
        llm_client: LLMClient,
        case_type: str = "civil_loan",
        *,
        model: str = "claude-sonnet-4-20250514",
        temperature: float = 0.0,
        max_tokens: int = 8192,
        max_retries: int = 3,
    ) -> None:
        self._llm_client = llm_client
        self._case_type = case_type
        self._model = model
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._max_retries = max_retries
        self._prompt_module = self._load_prompt_module(case_type)

    @staticmethod
    def _load_prompt_module(case_type: str):
        """åŠ è½½æ¡ˆç”±å¯¹åº”çš?prompt æ¨¡æ¿æ¨¡å—ã€?
        Load prompt template module for the given case type.
        """
        from .prompts import PROMPT_REGISTRY

        if case_type not in PROMPT_REGISTRY:
            available = ", ".join(PROMPT_REGISTRY.keys()) or "(none)"
            raise ValueError(
                f"ä¸æ”¯æŒçš„æ¡ˆç”±ç±»åž‹ / Unsupported case type: '{case_type}'ã€?
                f"å¯ç”¨ç±»åž‹ / Available: {available}"
            )
        return PROMPT_REGISTRY[case_type]

    def _validate_input(
        self,
        setup_input: ProcedureSetupInput,
        issue_tree: IssueTree,
    ) -> None:
        """éªŒè¯è¾“å…¥æ•°æ®åˆæ³•æ€§ã€?
        Validate input data validity.

        Raises:
            ValueError: issues ä¸ºç©ºã€case_id ä¸åŒ¹é…æ—¶ã€?
                        Empty issues or case_id mismatch.
        """
        if not issue_tree.issues:
            raise ValueError("issue_tree.issues ä¸èƒ½ä¸ºç©º / issue_tree.issues cannot be empty")
        if setup_input.case_id != issue_tree.case_id:
            raise ValueError(
                f"case_id ä¸åŒ¹é…?/ case_id mismatch: "
                f"setup_input={setup_input.case_id!r} vs "
                f"issue_tree={issue_tree.case_id!r}"
            )

    async def plan(
        self,
        setup_input: ProcedureSetupInput,
        issue_tree: IssueTree,
        run_id: str,
    ) -> ProcedureSetupResult:
        """æ‰§è¡Œç¨‹åºè®¾ç½®è§„åˆ’ã€?
Cannot set property. Property setting is supported only on core types in this language mode.
At line:1 char:1
+ [Console]::OutputEncoding=[System.Text.Encoding]::UTF8;
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : InvalidOperation: (:) [], RuntimeException
    + FullyQualifiedErrorId : PropertySetterNotSupportedInConstrainedLanguage
 

 succeeded in 646ms:


    Directory: C:\Users\david\dev\case-adversarial-engine\engines\pretrial_conference


Mode                 LastWriteTime         Length Name                                                                 
----                 -------------         ------ ----                                                                 
-a----         3/31/2026   9:58 PM           5937 conference_engine.py                                                 
-a----         3/31/2026   9:58 PM          11368 cross_examination_engine.py                                          
-a----         3/31/2026   9:58 PM           9244 minutes_generator.py                                                 
-a----         3/28/2026  11:36 PM           2147 pretrial_followup.py                                                 
-a----         3/31/2026   9:58 PM           6310 schemas.py                                                           
-a----         3/28/2026  11:10 PM              0 __init__.py                                                          


    Directory: C:\Users\david\dev\case-adversarial-engine\engines\pretrial_conference\agents


Mode                 LastWriteTime         Length Name                                                                 
----                 -------------         ------ ----                                                                 
-a----         3/31/2026   9:58 PM           7514 judge_agent.py                                                       
-a----         3/28/2026  11:10 PM              0 __init__.py                                                          


    Directory: C:\Users\david\dev\case-adversarial-engine\engines\pretrial_conference\agents\__pycache__


Mode                 LastWriteTime         Length Name                                                                 
----                 -------------         ------ ----                                                                 
-a----         3/31/2026   9:59 PM           7497 judge_agent.cpython-312.pyc                                          
-a----         3/28/2026  11:29 PM            186 __init__.cpython-312.pyc                                             


    Directory: C:\Users\david\dev\case-adversarial-engine\engines\pretrial_conference\prompts


Mode                 LastWriteTime         Length Name                                                                 
----                 -------------         ------ ----                                                                 
-a----          4/7/2026  12:57 PM           3815 civil_loan.py                                                        
-a----         3/31/2026   9:58 PM           4658 judge.py                                                             
-a----          4/7/2026  12:57 PM           3711 labor_dispute.py                                                     
-a----          4/7/2026  12:57 PM           3764 real_estate.py                                                       
-a----          4/7/2026  12:01 PM            728 __init__.py                                                          


    Directory: C:\Users\david\dev\case-adversarial-engine\engines\pretrial_conference\prompts\__pycache__


Mode                 LastWriteTime         Length Name                                                                 
----                 -------------         ------ ----                                                                 
-a----          4/7/2026  12:58 PM           3947 civil_loan.cpython-312.pyc                                           
-a----         3/31/2026   9:59 PM           5045 judge.cpython-312.pyc                                                
-a----          4/7/2026  12:58 PM           3850 labor_dispute.cpython-312.pyc                                        
-a----          4/7/2026  12:58 PM           3901 real_estate.cpython-312.pyc                                          
-a----          4/7/2026  12:01 PM           1016 __init__.cpython-312.pyc                                             


    Directory: C:\Users\david\dev\case-adversarial-engine\engines\pretrial_conference\tests


Mode                 LastWriteTime         Length Name                                                                 
----                 -------------         ------ ----                                                                 
-a----         3/31/2026   9:58 PM          10231 test_conference_engine.py                                            
-a----         3/31/2026   9:58 PM          19072 test_cross_examination_engine.py                                     
-a----         3/31/2026   9:58 PM          14387 test_judge_agent.py                                                  
-a----         3/31/2026   9:58 PM           8478 test_minutes_generator.py                                            
-a----         3/31/2026   9:58 PM           9825 test_schemas.py                                                      
-a----         3/28/2026  11:10 PM              0 __init__.py                                                          


    Directory: C:\Users\david\dev\case-adversarial-engine\engines\pretrial_conference\tests\__pycache__


Mode                 LastWriteTime         Length Name                                                                 
----                 -------------         ------ ----                                                                 
-a----         3/31/2026   9:59 PM          19743 test_conference_engine.cpython-312-pytest-9.0.2.pyc                  
-a----         3/31/2026   9:59 PM          45189 test_cross_examination_engine.cpython-312-pytest-9.0.2.pyc           
-a----         3/31/2026   9:59 PM          30650 test_judge_agent.cpython-312-pytest-9.0.2.pyc                        
-a----         3/31/2026   9:59 PM          20965 test_minutes_generator.cpython-312-pytest-9.0.2.pyc                  
-a----         3/31/2026   9:59 PM          20129 test_schemas.cpython-312-pytest-9.0.2.pyc                            
-a----         3/28/2026  11:11 PM            185 __init__.cpython-312.pyc                                             


    Directory: C:\Users\david\dev\case-adversarial-engine\engines\pretrial_conference\__pycache__


Mode                 LastWriteTime         Length Name                                                                 
----                 -------------         ------ ----                                                                 
-a----         3/31/2026   9:59 PM           5066 conference_engine.cpython-312.pyc                                    
-a----         3/31/2026   9:59 PM          10633 cross_examination_engine.cpython-312.pyc                             
-a----         3/31/2026   9:59 PM           9352 minutes_generator.cpython-312.pyc                                    
-a----         3/31/2026   9:59 PM           7833 schemas.cpython-312.pyc                                              
-a----         3/28/2026  11:11 PM            179 __init__.cpython-312.pyc                                             


Cannot set property. Property setting is supported only on core types in this language mode.
At line:1 char:1
+ [Console]::OutputEncoding=[System.Text.Encoding]::UTF8;
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : InvalidOperation: (:) [], RuntimeException
    + FullyQualifiedErrorId : PropertySetterNotSupportedInConstrainedLanguage
 

 succeeded in 647ms:


    Directory: C:\Users\david\dev\case-adversarial-engine\engines\document_assistance


Mode                 LastWriteTime         Length Name                                                                 
----                 -------------         ------ ----                                                                 
-a----         3/31/2026   1:08 PM           7619 engine.py                                                            
-a----          4/3/2026   1:22 AM           8400 schemas.py                                                           
-a----         3/31/2026   1:08 PM            483 __init__.py                                                          


    Directory: C:\Users\david\dev\case-adversarial-engine\engines\document_assistance\prompts


Mode                 LastWriteTime         Length Name                                                                 
----                 -------------         ------ ----                                                                 
-a----         3/31/2026   1:08 PM           2422 civil_loan_cross_exam.py                                             
-a----         3/31/2026   1:08 PM           3170 civil_loan_defense.py                                                
-a----         3/31/2026   9:58 PM           3777 civil_loan_pleading.py                                               
-a----         3/31/2026   1:08 PM           2509 labor_dispute_cross_exam.py                                          
-a----         3/31/2026   1:08 PM           3356 labor_dispute_defense.py                                             
-a----         3/31/2026   1:08 PM           4020 labor_dispute_pleading.py                                            
-a----         3/31/2026   1:08 PM           2514 real_estate_cross_exam.py                                            
-a----         3/31/2026   1:08 PM           3263 real_estate_defense.py                                               
-a----         3/31/2026   1:08 PM           3883 real_estate_pleading.py                                              
-a----         3/31/2026   9:58 PM           2469 __init__.py                                                          


    Directory: C:\Users\david\dev\case-adversarial-engine\engines\document_assistance\prompts\__pycache__


Mode                 LastWriteTime         Length Name                                                                 
----                 -------------         ------ ----                                                                 
-a----         3/31/2026   1:10 PM           3150 civil_loan_cross_exam.cpython-312.pyc                                
-a----         3/31/2026   1:10 PM           4276 civil_loan_defense.cpython-312.pyc                                   
-a----         3/31/2026   9:59 PM           5101 civil_loan_pleading.cpython-312.pyc                                  
-a----         3/31/2026   1:10 PM           3238 labor_dispute_cross_exam.cpython-312.pyc                             
-a----         3/31/2026   1:10 PM           4467 labor_dispute_defense.cpython-312.pyc                                
-a----         3/31/2026   1:10 PM           5346 labor_dispute_pleading.cpython-312.pyc                               
-a----         3/31/2026   1:10 PM           3241 real_estate_cross_exam.cpython-312.pyc                               
-a----         3/31/2026   1:10 PM           4369 real_estate_defense.cpython-312.pyc                                  
-a----         3/31/2026   1:10 PM           5204 real_estate_pleading.cpython-312.pyc                                 
-a----         3/31/2026   9:59 PM           2010 __init__.cpython-312.pyc                                             


    Directory: C:\Users\david\dev\case-adversarial-engine\engines\document_assistance\tests


Mode                 LastWriteTime         Length Name                                                                 
----                 -------------         ------ ----                                                                 
-a----         3/31/2026   9:58 PM          20645 test_engine.py                                                       
-a----         3/31/2026   1:08 PM          11916 test_schemas.py                                                      
-a----         3/31/2026   1:08 PM              0 __init__.py                                                          


    Directory: C:\Users\david\dev\case-adversarial-engine\engines\document_assistance\tests\__pycache__


Mode                 LastWriteTime         Length Name                                                                 
----                 -------------         ------ ----                                                                 
-a----         3/31/2026   9:59 PM          62643 test_engine.cpython-312-pytest-9.0.2.pyc                             
-a----         3/31/2026   2:58 PM          33861 test_schemas.cpython-312-pytest-9.0.2.pyc                            
-a----         3/31/2026   2:58 PM            185 __init__.cpython-312.pyc                                             


    Directory: C:\Users\david\dev\case-adversarial-engine\engines\document_assistance\__pycache__


Mode                 LastWriteTime         Length Name                                                                 
----                 -------------         ------ ----                                                                 
-a----         3/31/2026   1:10 PM           7701 engine.cpython-312.pyc                                               
-a----          4/3/2026   1:22 AM           9364 schemas.cpython-312.pyc                                              
-a----         3/31/2026   1:10 PM            664 __init__.cpython-312.pyc                                             


Cannot set property. Property setting is supported only on core types in this language mode.
At line:1 char:1
+ [Console]::OutputEncoding=[System.Text.Encoding]::UTF8;
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : InvalidOperation: (:) [], RuntimeException
    + FullyQualifiedErrorId : PropertySetterNotSupportedInConstrainedLanguage
 

exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -NoProfile -Command "Select-String -Path 'engines\\**\\*.py' -Pattern 'civil_loan'" in C:/Users/david/dev/case-adversarial-engine
 succeeded in 596ms:

engines\case_extraction\extractor.py:45:2. 
案件类型：civil_loan（民间借贷）、labor_dispute（劳动纠纷）、real_estate（房产纠纷）或 unknown
engines\case_extraction\schemas.py:60:            "案件类型：civil_loan（民间借贷）、labor_dispute（劳动纠纷）、"
engines\document_assistance\schemas.py:160:    case_type: str = Field(description="案件类型：'civil_loan' | 
'labor_dispute' | 'real_estate'")
engines\document_assistance\schemas.py:181:    case_type: str = Field(description="'civil_loan' | 'labor_dispute' | 
'real_estate'")
engines\document_assistance\__init__.py:5:质证意见框架（CrossExaminationOpinion）三类文书骨架，支持 civil_loan、
engines\interactive_followup\responder.py:73:        case_type: 案由类型，默认 "civil_loan" / Case type, default 
"civil_loan"
engines\interactive_followup\responder.py:83:        case_type: str = "civil_loan",
engines\pretrial_conference\cross_examination_engine.py:34:from .prompts.civil_loan import (
engines\procedure_setup\planner.py:193:        case_type: 案由类型，默认 "civil_loan" / Case type, default "civil_loan"
engines\procedure_setup\planner.py:203:        case_type: str = "civil_loan",
engines\report_generation\generator.py:125:        case_type: 案由类型，默认 "civil_loan" / Case type, default 
"civil_loan"
engines\report_generation\generator.py:135:        case_type: str = "civil_loan",
engines\shared\case_type_plugin.py:14:    prompt = plugin.get_prompt("action_recommender", "civil_loan", context)
engines\shared\case_type_plugin.py:17:    allowed = plugin.allowed_impact_targets("civil_loan")
engines\shared\case_type_plugin.py:54:            case_type:   Case type key (e.g. ``"civil_loan"``).
engines\shared\case_type_plugin.py:79:            case_type: Case type key (e.g. ``"civil_loan"``).
engines\simulation_run\simulator.py:92:        case_type: 案由类型，默认 "civil_loan" / Case type, default "civil_loan"
engines\simulation_run\simulator.py:102:        case_type: str = "civil_loan",
engines\simulation_run\simulator.py:515:    case_type: str = "civil_loan",


Cannot set property. Property setting is supported only on core types in this language mode.
At line:1 char:1
+ [Console]::OutputEncoding=[System.Text.Encoding]::UTF8;
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : InvalidOperation: (:) [], RuntimeException
    + FullyQualifiedErrorId : PropertySetterNotSupportedInConstrainedLanguage
 

codex
I’ve already found hard-coded three-case-type descriptions and defaults outside the prompt layer. That alone means the plan undercounts non-prompt blast radius. I’m pulling the surrounding code now.
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -NoProfile -Command "Get-Content 'engines/interactive_followup/responder.py' | Select-Object -First 180" in C:/Users/david/dev/case-adversarial-engine
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -NoProfile -Command "Get-Content 'engines/report_generation/generator.py' | Select-Object -First 220" in C:/Users/david/dev/case-adversarial-engine
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -NoProfile -Command "Get-Content 'engines/simulation_run/simulator.py' | Select-Object -First 220" in C:/Users/david/dev/case-adversarial-engine
 succeeded in 628ms:
"""
äº¤äº’è¿½é—®å“åº”å™¨æ ¸å¿ƒæ¨¡å?
Interactive followup responder core module.

æŽ¥æ”¶æŠ¥å‘Š + ç”¨æˆ·é—®é¢˜ï¼Œç”Ÿæˆå¸¦ citation çš„è¿½é—®å›žç­”ï¼Œæ”¯æŒå¤šè½®å¯¹è¯ã€?
Receives report + user question, generates cited answers, supports multi-turn conversation.

åˆçº¦ä¿è¯ / Contract guarantees:
- evidence_ids âŠ?æŠ¥å‘Šå·²å¼•ç”¨è¯æ?/ evidence_ids âŠ?report-cited evidence
- issue_ids ä¸ä¸ºç©?/ issue_ids non-empty
- 100% statement_class è¦†ç›– / 100% statement_class coverage
- å¤šè½®ä¸Šä¸‹æ–‡ä¸€è‡´æ€§ï¼ˆhistory ä¼ å…¥ LLMï¼? Multi-turn context consistency
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from engines.shared.models import LLMClient
from engines.shared.structured_output import call_structured_llm

from .schemas import (
    InteractionTurn,
    LLMFollowupOutput,
    ReportArtifact,
    StatementClass,
)

logger = logging.getLogger(__name__)

# tool_use JSON Schemaï¼ˆæ¨¡å—åŠ è½½æ—¶è®¡ç®—ä¸€æ¬¡ï¼‰
_TOOL_SCHEMA: dict = LLMFollowupOutput.model_json_schema()


# ---------------------------------------------------------------------------
# statement_class è§£æžå·¥å…· / statement_class resolution utility
# ---------------------------------------------------------------------------


def _resolve_statement_class(raw: str) -> StatementClass:
    """å°?LLM è¿”å›žçš?statement_class å­—ç¬¦ä¸²è§£æžä¸ºæžšä¸¾å€¼ã€?
    Resolve raw statement_class string to enum value.
    Defaults to 'inference' for unknown values.
    """
    _MAP = {
        "fact": StatementClass.fact,
        "äº‹å®ž": StatementClass.fact,
        "inference": StatementClass.inference,
        "æŽ¨ç†": StatementClass.inference,
        "assumption": StatementClass.assumption,
        "å‡è®¾": StatementClass.assumption,
    }
    return _MAP.get(raw.strip().lower(), StatementClass.inference)


# ---------------------------------------------------------------------------
# ä¸»å¼•æ“Žç±» / Main engine class
# ---------------------------------------------------------------------------


class FollowupResponder:
    """äº¤äº’è¿½é—®å“åº”å™?
    Interactive Followup Responder.

    è¾“å…¥æŠ¥å‘Š + ç”¨æˆ·é—®é¢˜ï¼?å¯é€‰åŽ†å²è½®æ¬¡ï¼‰ï¼Œè¾“å‡?InteractionTurnã€?
    Takes report + user question (+ optional history), outputs InteractionTurn.

    Args:
        llm_client: ç¬¦åˆ LLMClient åè®®çš„å®¢æˆ·ç«¯ / LLMClient-compatible client
        case_type: æ¡ˆç”±ç±»åž‹ï¼Œé»˜è®?"civil_loan" / Case type, default "civil_loan"
        model: LLM æ¨¡åž‹åç§° / LLM model name
        temperature: LLM æ¸©åº¦å‚æ•° / LLM temperature
        max_tokens: LLM æœ€å¤§è¾“å‡?token æ•?/ Max output tokens
        max_retries: LLM è°ƒç”¨å¤±è´¥æ—¶çš„æœ€å¤§é‡è¯•æ¬¡æ•?/ Max retries on failure
    """

    def __init__(
        self,
        llm_client: LLMClient,
        case_type: str = "civil_loan",
        *,
        model: str = "claude-sonnet-4-20250514",
        temperature: float = 0.0,
        max_tokens: int = 4096,
        max_retries: int = 3,
    ) -> None:
        self._llm_client = llm_client
        self._case_type = case_type
        self._model = model
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._max_retries = max_retries
        self._prompt_module = self._load_prompt_module(case_type)

    @staticmethod
    def _load_prompt_module(case_type: str):
        """åŠ è½½æ¡ˆç”±å¯¹åº”çš?prompt æ¨¡æ¿æ¨¡å—ã€?
        Load prompt template module for the given case type.
        """
        from .prompts import PROMPT_REGISTRY

        if case_type not in PROMPT_REGISTRY:
            available = ", ".join(PROMPT_REGISTRY.keys()) or "(none)"
            raise ValueError(
                f"ä¸æ”¯æŒçš„æ¡ˆç”±ç±»åž‹ / Unsupported case type: '{case_type}'ã€?
                f"å¯ç”¨ç±»åž‹ / Available: {available}"
            )
        return PROMPT_REGISTRY[case_type]

    def _validate_input(
        self,
        report: ReportArtifact,
        question: str,
    ) -> None:
        """éªŒè¯è¾“å…¥æ•°æ®åˆæ³•æ€§ã€?
        Validate input data validity.

        Raises:
            ValueError: question ä¸ºç©ºï¼Œæˆ– report æ— ç« èŠ‚ã€?
        """
        if not question.strip():
            raise ValueError("question ä¸èƒ½ä¸ºç©º / question cannot be empty")
        if not report.sections:
            raise ValueError("report.sections ä¸èƒ½ä¸ºç©º / report.sections cannot be empty")

    def _collect_report_evidence_ids(self, report: ReportArtifact) -> set[str]:
        """æ”¶é›†æŠ¥å‘Šä¸­æ‰€æœ‰å¼•ç”¨è¿‡çš?evidence_id é›†åˆã€?
        Collect all evidence IDs referenced in the report.
        """
        ids: set[str] = set()
        for sec in report.sections:
            ids.update(sec.linked_evidence_ids)
            for concl in sec.key_conclusions:
                ids.update(concl.supporting_evidence_ids)
        return ids

    def _collect_report_issue_ids(self, report: ReportArtifact) -> set[str]:
        """æ”¶é›†æŠ¥å‘Šä¸­æ‰€æœ‰å…³è”çš„ issue_id é›†åˆã€?
        Collect all issue IDs referenced in the report.
        """
        ids: set[str] = set()
        for sec in report.sections:
            ids.update(sec.linked_issue_ids)
        return ids

    async def respond(
        self,
        report: ReportArtifact,
        question: str,
        *,
        previous_turns: list[InteractionTurn] | None = None,
        turn_slug: str = "turn",
        run_id: str | None = None,
    ) -> InteractionTurn:
        """æ‰§è¡Œè¿½é—®å“åº”ã€?
        Execute followup response.

        Args:
            report: å·²ç”Ÿæˆçš„æŠ¥å‘Š / Generated report artifact
            question: ç”¨æˆ·è¿½é—®é—®é¢˜ / User question
            previous_turns: ä¹‹å‰çš„è¿½é—®è½®æ¬¡ï¼ˆå¤šè½®å¯¹è¯ä¸Šä¸‹æ–‡ï¼‰/ Previous turns for context
            turn_slug: Turn ID ç®€ç§?/ Turn slug for ID generation
            run_id: è¿è¡Œ IDï¼ˆå¯é€‰ï¼Œé»˜è®¤ä½¿ç”¨ report.run_idï¼? Run ID (optional override)

        Returns:
            ç»“æž„åŒ?InteractionTurn / Structured InteractionTurn

        Raises:
            ValueError: è¾“å…¥æ— æ•ˆæˆ?LLM å“åº”æ— æ³•è§£æž / Invalid input or unparseable response
            RuntimeError: LLM è°ƒç”¨å¤±è´¥ä¸”è¶…è¿‡æœ€å¤§é‡è¯•æ¬¡æ•?/ LLM call failed after max retries
        """
        self._validate_input(report, question)

        previous_turns = previous_turns or []
        report_evidence_ids = self._collect_report_evidence_ids(report)
        report_issue_ids = self._collect_report_issue_ids(report)

Cannot set property. Property setting is supported only on core types in this language mode.
At line:1 char:1
+ [Console]::OutputEncoding=[System.Text.Encoding]::UTF8;
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : InvalidOperation: (:) [], RuntimeException
    + FullyQualifiedErrorId : PropertySetterNotSupportedInConstrainedLanguage
 

 succeeded in 636ms:
"""
åœºæ™¯æŽ¨æ¼”å¼•æ“Žæ ¸å¿ƒæ¨¡å—
Scenario simulator core module.

å°†äº‰ç‚¹æ ‘ï¼ˆIssueTreeï¼‰å’Œè¯æ®ç´¢å¼•ï¼ˆEvidenceIndexï¼‰ç»“åˆåœºæ™¯å˜æ›´é›†ï¼ˆChangeSetï¼‰ï¼Œ
é€šè¿‡ LLM ç”Ÿæˆç»“æž„åŒ–å·®å¼‚æ‘˜è¦ï¼ˆDiffSummaryï¼‰ã€?
Generates a structured diff summary from IssueTree + EvidenceIndex + ChangeSet via LLM.

åˆçº¦ä¿è¯ / Contract guarantees:
- æ¯æ¡ diff_entry æœ?impact_descriptionï¼ˆä¸ä¸ºç©ºï¼?
- æ¯æ¡ diff_entry.direction ä¸ºåˆæ³•æžšä¸¾å€?
- affected_issue_ids è¦†ç›–æ‰€æœ?diff_entry.issue_id
- baseline åœºæ™¯ä¸æ‰§è¡Œï¼ˆchange_set = [] æ—¶æ‹’ç»è°ƒç”¨ï¼‰
- baseline Run ä¸è¢«ä¿®æ”¹ï¼Œå§‹ç»ˆåˆ›å»ºæ–° Run
- trigger_type å›ºå®šä¸?"scenario_execution"
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

from engines.shared.json_utils import _extract_json_object  # noqa: F401 â€?re-exported for tests
from engines.shared.models import LLMClient
from engines.shared.structured_output import call_structured_llm

from .schemas import (
    ArtifactRef,
    ChangeItem,
    DiffDirection,
    DiffEntry,
    EvidenceIndex,
    InputSnapshot,
    IssueTree,
    LLMDiffOutput,
    MaterialRef,
    Run,
    Scenario,
    ScenarioInput,
    ScenarioResult,
    ScenarioStatus,
)

# tool_use JSON Schemaï¼ˆæ¨¡å—åŠ è½½æ—¶è®¡ç®—ä¸€æ¬¡ï¼‰
_TOOL_SCHEMA: dict = LLMDiffOutput.model_json_schema()


# ---------------------------------------------------------------------------
# direction è§£æžå·¥å…· / direction resolution utility
# ---------------------------------------------------------------------------


def _resolve_direction(raw: str) -> DiffDirection:
    """å°?LLM è¿”å›žçš?direction å­—ç¬¦ä¸²è§£æžä¸ºæžšä¸¾å€¼ã€?
    Resolve raw direction string to DiffDirection enum.
    Defaults to 'neutral' for unknown values.
    """
    _MAP = {
        "strengthen": DiffDirection.strengthen,
        "å¢žå¼º": DiffDirection.strengthen,
        "weaken": DiffDirection.weaken,
        "å‰Šå¼±": DiffDirection.weaken,
        "neutral": DiffDirection.neutral,
        "ä¸­æ€?: DiffDirection.neutral,
        "æ—?: DiffDirection.neutral,
    }
    return _MAP.get(raw.strip().lower(), DiffDirection.neutral)


# ---------------------------------------------------------------------------
# ä¸»å¼•æ“Žç±» / Main engine class
# ---------------------------------------------------------------------------


class ScenarioSimulator:
    """åœºæ™¯æŽ¨æ¼”å™?
    Scenario Simulator.

    è¾“å…¥ IssueTree + EvidenceIndex + ScenarioInputï¼Œè¾“å‡?ScenarioResultã€?
    Takes IssueTree + EvidenceIndex + ScenarioInput, outputs a ScenarioResult.

    Args:
        llm_client: ç¬¦åˆ LLMClient åè®®çš„å®¢æˆ·ç«¯ / LLMClient-compatible client
        case_type: æ¡ˆç”±ç±»åž‹ï¼Œé»˜è®?"civil_loan" / Case type, default "civil_loan"
        model: LLM æ¨¡åž‹åç§° / LLM model name
        temperature: LLM æ¸©åº¦å‚æ•° / LLM temperature
        max_tokens: LLM æœ€å¤§è¾“å‡?token æ•?/ Max output tokens
        max_retries: LLM è°ƒç”¨å¤±è´¥æ—¶çš„æœ€å¤§é‡è¯•æ¬¡æ•?/ Max retries on failure
    """

    def __init__(
        self,
        llm_client: LLMClient,
        case_type: str = "civil_loan",
        *,
        model: str = "claude-sonnet-4-20250514",
        temperature: float = 0.0,
        max_tokens: int = 8192,
        max_retries: int = 3,
    ) -> None:
        self._llm_client = llm_client
        self._case_type = case_type
        self._model = model
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._max_retries = max_retries
        self._prompt_module = self._load_prompt_module(case_type)

    @staticmethod
    def _load_prompt_module(case_type: str):
        """åŠ è½½æ¡ˆç”±å¯¹åº”çš?prompt æ¨¡æ¿æ¨¡å—ã€?
        Load prompt template module for the given case type.
        """
        from .prompts import PROMPT_REGISTRY

        if case_type not in PROMPT_REGISTRY:
            available = ", ".join(PROMPT_REGISTRY.keys()) or "(none)"
            raise ValueError(
                f"ä¸æ”¯æŒçš„æ¡ˆç”±ç±»åž‹ / Unsupported case type: '{case_type}'ã€?
                f"å¯ç”¨ç±»åž‹ / Available: {available}"
            )
        return PROMPT_REGISTRY[case_type]

    def _validate_input(
        self,
        scenario_input: ScenarioInput,
        issue_tree: IssueTree,
        evidence_index: EvidenceIndex,
    ) -> None:
        """éªŒè¯è¾“å…¥æ•°æ®åˆæ³•æ€§ã€?
        Validate input data validity.

        Raises:
            ValueError: issues ä¸ºç©ºã€case_id ä¸åŒ¹é…ï¼Œæˆ?change_set ä¸ºç©ºï¼ˆbaseline ä¸æ‰§è¡Œï¼‰ã€?
                        Empty issues, case_id mismatch, or empty change_set (baseline not executed).
        """
        if not issue_tree.issues:
            raise ValueError("issue_tree.issues ä¸èƒ½ä¸ºç©º / issue_tree.issues cannot be empty")
        if issue_tree.case_id != evidence_index.case_id:
            raise ValueError(
                f"case_id ä¸åŒ¹é…?/ case_id mismatch: "
                f"issue_tree={issue_tree.case_id!r} vs "
                f"evidence_index={evidence_index.case_id!r}"
            )
        # baseline anchor åˆçº¦ï¼šchange_set ä¸ºç©ºæ—¶ä¸æ‰§è¡Œ
        # Baseline anchor contract: refuse execution when change_set is empty
        if not scenario_input.change_set:
            raise ValueError(
                "change_set ä¸ºç©ºâ€”â€”è¿™æ˜?baseline anchor åœºæ™¯ï¼Œä¸åº”è°ƒç”?simulate() æ‰§è¡ŒæŽ¨æ¼”ã€?
                " / change_set is empty â€?this is a baseline anchor scenario; "
                "do not call simulate() for baseline anchors."
            )

    async def simulate(
        self,
        scenario_input: ScenarioInput,
        issue_tree: IssueTree,
        evidence_index: EvidenceIndex,
        run_id: str,
    ) -> ScenarioResult:
        """æ‰§è¡Œåœºæ™¯æŽ¨æ¼”ã€?
        Execute scenario simulation.

        Args:
            scenario_input: åœºæ™¯è¾“å…¥åˆçº¦ / Scenario engine input contract
            issue_tree: ç»“æž„åŒ–äº‰ç‚¹æ ‘ / Structured issue tree
            evidence_index: è¯æ®ç´¢å¼• / Evidence index
            run_id: æ–°å»º Run çš?ID / Run ID for the newly created Run

        Returns:
            ScenarioResult åŒ…å«æ›´æ–°åŽçš„ Scenario å’Œæ–°å»?Runã€?
            LLM è°ƒç”¨æˆ–è§£æžå¤±è´¥æ—¶è¿”å›ž status="failed" çš?ScenarioResultï¼Œä¸æŠ›å‡ºå¼‚å¸¸ã€?
            ScenarioResult with updated Scenario and newly created Run.
            On LLM failure or parse error, returns a ScenarioResult with status="failed".

        Raises:
            ValueError: è¾“å…¥éªŒè¯å¤±è´¥ï¼ˆchange_set ä¸ºç©ºã€case_id ä¸åŒ¹é…ã€issues ä¸ºç©ºï¼?
                        Input validation failed (empty change_set, case_id mismatch, empty issues)
        """
        # è¾“å…¥éªŒè¯å¤±è´¥ä»å‘ä¸ŠæŠ›å‡?/ Input validation errors still propagate
        self._validate_input(scenario_input, issue_tree, evidence_index)

        case_id = issue_tree.case_id
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        try:
            # æž„å»º prompt / Build prompt
            from .prompts import plugin

            system_prompt = self._prompt_module.SYSTEM_PROMPT
            user_prompt = plugin.get_prompt(
                "simulation_run",
                self._case_type,
                {
                    "case_id": case_id,
                    "scenario_id": scenario_input.scenario_id,
                    "issue_tree": issue_tree.model_dump(),
                    "evidence_list": [e.model_dump() for e in evidence_index.evidence],
                    "change_set": [c.model_dump() for c in scenario_input.change_set],
                },
            )

            # è°ƒç”¨ LLMï¼ˆç»“æž„åŒ–è¾“å‡ºï¼? Call LLM with structured output
            raw_dict = await self._call_llm_structured(system_prompt, user_prompt)
            llm_output = LLMDiffOutput.model_validate(raw_dict)

            # æž„å»º ScenarioResult / Build ScenarioResult
            return self._build_result(
                llm_output=llm_output,
                scenario_input=scenario_input,
                issue_tree=issue_tree,
                evidence_index=evidence_index,
Cannot set property. Property setting is supported only on core types in this language mode.
At line:1 char:1
+ [Console]::OutputEncoding=[System.Text.Encoding]::UTF8;
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : InvalidOperation: (:) [], RuntimeException
    + FullyQualifiedErrorId : PropertySetterNotSupportedInConstrainedLanguage
 

 succeeded in 656ms:
"""
æŠ¥å‘Šç”Ÿæˆå™¨æ ¸å¿ƒæ¨¡å?
Report generator core module.

å°†äº‰ç‚¹æ ‘ï¼ˆIssueTreeï¼‰å’Œè¯æ®ç´¢å¼•ï¼ˆEvidenceIndexï¼‰é€šè¿‡ LLM ç”Ÿæˆç»“æž„åŒ–è¯Šæ–­æŠ¥å‘Šã€?
Generates a structured diagnostic report from IssueTree + EvidenceIndex via LLM.

åˆçº¦ä¿è¯ / Contract guarantees:
- citation_completeness = 100%ï¼ˆæ¯æ¡å…³é”®ç»“è®ºæœ‰ â‰? è¯æ®å¼•ç”¨ï¼?
- è¦†ç›–æ‰€æœ‰é¡¶å±?Issue / Covers all root-level issues
- é›¶æ‚¬ç©ºå¼•ç”?/ Zero dangling references
- summary â‰?500 å­?/ Summary â‰?500 characters
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from engines.shared.json_utils import _extract_json_object  # noqa: F401 â€?re-exported for tests
from engines.shared.models import LLMClient
from engines.shared.pii_redactor import redact_text
from engines.shared.structured_output import call_structured_llm

from .issue_evidence_defense_matrix import (
    build_issue_evidence_defense_matrix,
    render_matrix_markdown,
)
from .outcome_paths import build_case_outcome_paths, render_outcome_paths_md_lines  # noqa: F401
from .schemas import (
    CaseOutcomePaths,  # noqa: F401 â€?re-exported for callers
    EvidenceIndex,
    EvidenceItem,
    IssueTree,
    KeyConclusion,
    LLMReportOutput,
    LLMSectionItem,
    ReportArtifact,
    ReportSection,
    StatementClass,
)

# tool_use JSON Schemaï¼ˆæ¨¡å—åŠ è½½æ—¶è®¡ç®—ä¸€æ¬¡ï¼‰
_TOOL_SCHEMA: dict = LLMReportOutput.model_json_schema()


# ---------------------------------------------------------------------------
# statement_class è§£æžå·¥å…· / statement_class resolution utility
# ---------------------------------------------------------------------------


def _resolve_statement_class(raw: str) -> StatementClass:
    """å°?LLM è¿”å›žçš?statement_class å­—ç¬¦ä¸²è§£æžä¸ºæžšä¸¾å€¼ã€?
    Resolve raw statement_class string to enum value.
    Defaults to 'inference' for unknown values.
    """
    _MAP = {
        "fact": StatementClass.fact,
        "äº‹å®ž": StatementClass.fact,
        "inference": StatementClass.inference,
        "æŽ¨ç†": StatementClass.inference,
        "assumption": StatementClass.assumption,
        "å‡è®¾": StatementClass.assumption,
    }
    return _MAP.get(raw.strip().lower(), StatementClass.inference)


# ---------------------------------------------------------------------------
# PII è„±æ• / PII redaction
# ---------------------------------------------------------------------------


def redact_report(
    report: ReportArtifact,
    *,
    party_names: list[str] | None = None,
) -> ReportArtifact:
    """å¯?ReportArtifact çš„æ‰€æœ‰é¢å‘ç”¨æˆ·çš„æ–‡æœ¬å­—æ®µæ‰§è¡Œ PII è„±æ•ã€?

    Redact PII from all user-facing text fields in a ReportArtifact.
    Returns a new ReportArtifact with redacted content (immutable style).
    """

    def _r(text: str) -> str:
        return redact_text(text, party_names=party_names)

    redacted_sections = []
    for sec in report.sections:
        redacted_conclusions = [
            kc.model_copy(update={"text": _r(kc.text)}) for kc in sec.key_conclusions
        ]
        redacted_sections.append(
            sec.model_copy(
                update={
                    "title": _r(sec.title),
                    "body": _r(sec.body),
                    "key_conclusions": redacted_conclusions,
                }
            )
        )

    return report.model_copy(
        update={
            "title": _r(report.title),
            "summary": _r(report.summary),
            "sections": redacted_sections,
        }
    )


# ---------------------------------------------------------------------------
# ä¸»å¼•æ“Žç±» / Main engine class
# ---------------------------------------------------------------------------


class ReportGenerator:
    """æŠ¥å‘Šç”Ÿæˆå™?
    Report Generator.

    è¾“å…¥ IssueTree + EvidenceIndexï¼Œè¾“å‡ºç»“æž„åŒ– ReportArtifactã€?
    Takes IssueTree + EvidenceIndex, outputs a structured ReportArtifact.

    Args:
        llm_client: ç¬¦åˆ LLMClient åè®®çš„å®¢æˆ·ç«¯ / LLMClient-compatible client
        case_type: æ¡ˆç”±ç±»åž‹ï¼Œé»˜è®?"civil_loan" / Case type, default "civil_loan"
        model: LLM æ¨¡åž‹åç§° / LLM model name
        temperature: LLM æ¸©åº¦å‚æ•° / LLM temperature
        max_tokens: LLM æœ€å¤§è¾“å‡?token æ•?/ Max output tokens
        max_retries: LLM è°ƒç”¨å¤±è´¥æ—¶çš„æœ€å¤§é‡è¯•æ¬¡æ•?/ Max retries on failure
    """

    def __init__(
        self,
        llm_client: LLMClient,
        case_type: str = "civil_loan",
        *,
        model: str = "claude-sonnet-4-20250514",
        temperature: float = 0.0,
        max_tokens: int = 8192,
        max_retries: int = 3,
    ) -> None:
        self._llm_client = llm_client
        self._case_type = case_type
        self._model = model
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._max_retries = max_retries
        self._prompt_module = self._load_prompt_module(case_type)

    @staticmethod
    def _load_prompt_module(case_type: str):
        """åŠ è½½æ¡ˆç”±å¯¹åº”çš?prompt æ¨¡æ¿æ¨¡å—ã€?
        Load prompt template module for the given case type.
        """
        from .prompts import PROMPT_REGISTRY

        if case_type not in PROMPT_REGISTRY:
            available = ", ".join(PROMPT_REGISTRY.keys()) or "(none)"
            raise ValueError(
                f"ä¸æ”¯æŒçš„æ¡ˆç”±ç±»åž‹ / Unsupported case type: '{case_type}'ã€?
                f"å¯ç”¨ç±»åž‹ / Available: {available}"
            )
        return PROMPT_REGISTRY[case_type]

    def _validate_input(
        self,
        issue_tree: IssueTree,
        evidence_index: EvidenceIndex,
    ) -> None:
        """éªŒè¯è¾“å…¥æ•°æ®åˆæ³•æ€§ã€?
        Validate input data validity.

        Raises:
            ValueError: issues ä¸ºç©ºï¼Œæˆ– evidence ä¸?issue_tree case_id ä¸åŒ¹é…ã€?
                        Raised if issues is empty or case_id mismatch.
        """
        if not issue_tree.issues:
            raise ValueError("issue_tree.issues ä¸èƒ½ä¸ºç©º / issue_tree.issues cannot be empty")
        if issue_tree.case_id != evidence_index.case_id:
            raise ValueError(
                f"case_id ä¸åŒ¹é…?/ case_id mismatch: "
                f"issue_tree={issue_tree.case_id!r} vs "
                f"evidence_index={evidence_index.case_id!r}"
            )

    async def generate(
        self,
        issue_tree: IssueTree,
        evidence_index: EvidenceIndex,
        run_id: str,
        report_slug: str = "report",
        defense_chain: Any = None,
    ) -> ReportArtifact:
        """æ‰§è¡ŒæŠ¥å‘Šç”Ÿæˆã€?
        Execute report generation.

        Args:
            issue_tree: ç»“æž„åŒ–äº‰ç‚¹æ ‘ / Structured issue tree
            evidence_index: è¯æ®ç´¢å¼• / Evidence index
            run_id: æœ¬æ¬¡è¿è¡Œ ID / Run ID for this generation
            report_slug: æŠ¥å‘Šç®€ç§°ï¼Œç”¨äºŽç”Ÿæˆ ID / Report slug for ID generation
            defense_chain: åŽŸå‘Šæ–¹é˜²å¾¡ç­–ç•¥é“¾ï¼ˆå¯é€‰ï¼‰/ PlaintiffDefenseChain (optional)

        Returns:
            ç»“æž„åŒ?ReportArtifact / Structured ReportArtifact

        Raises:
            ValueError: è¾“å…¥æ— æ•ˆæˆ?LLM å“åº”æ— æ³•è§£æž / Invalid input or unparseable response
            RuntimeError: LLM è°ƒç”¨å¤±è´¥ä¸”è¶…è¿‡æœ€å¤§é‡è¯•æ¬¡æ•?/ LLM call failed after max retries
        """
        self._validate_input(issue_tree, evidence_index)

        case_id = issue_tree.case_id

        # æž„å»º prompt / Build prompt
        from .prompts import plugin

        system_prompt = self._prompt_module.SYSTEM_PROMPT
        user_prompt = plugin.get_prompt(
            "report_generation",
Cannot set property. Property setting is supported only on core types in this language mode.
At line:1 char:1
+ [Console]::OutputEncoding=[System.Text.Encoding]::UTF8;
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : InvalidOperation: (:) [], RuntimeException
    + FullyQualifiedErrorId : PropertySetterNotSupportedInConstrainedLanguage
 

exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -NoProfile -Command "Get-Content 'engines/document_assistance/engine.py' | Select-Object -First 240" in C:/Users/david/dev/case-adversarial-engine
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -NoProfile -Command "Get-Content 'engines/document_assistance/schemas.py' | Select-Object -First 260" in C:/Users/david/dev/case-adversarial-engine
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -NoProfile -Command "Get-Content 'engines/document_assistance/prompts/__init__.py'" in C:/Users/david/dev/case-adversarial-engine
 succeeded in 596ms:
"""
æ–‡ä¹¦è¾…åŠ©å¼•æ“Žæç¤ºæ³¨å†Œè¡¨ã€?
Document assistance engine prompt registry.

PROMPT_REGISTRY ä½¿ç”¨äºŒç»´é”?(doc_type, case_type) â†?(system_prompt, build_user_prompt_fn)ã€?
PROMPT_REGISTRY uses 2D key (doc_type, case_type) â†?(system_prompt, build_user_prompt_fn).

æ”¯æŒçš„ç»„å?/ Supported combinations:
- ("pleading",   "civil_loan")
- ("defense",    "civil_loan")
- ("cross_exam", "civil_loan")
- ("pleading",   "labor_dispute")
- ("defense",    "labor_dispute")
- ("cross_exam", "labor_dispute")
- ("pleading",   "real_estate")
- ("defense",    "real_estate")
- ("cross_exam", "real_estate")
"""

from __future__ import annotations

from typing import Callable

from .civil_loan_pleading import (
    SYSTEM_PROMPT as _CL_PL_SYS,
    build_user_prompt as _CL_PL_BUILD,
)
from .civil_loan_defense import (
    SYSTEM_PROMPT as _CL_DF_SYS,
    build_user_prompt as _CL_DF_BUILD,
)
from .civil_loan_cross_exam import (
    SYSTEM_PROMPT as _CL_XE_SYS,
    build_user_prompt as _CL_XE_BUILD,
)
from .labor_dispute_pleading import (
    SYSTEM_PROMPT as _LD_PL_SYS,
    build_user_prompt as _LD_PL_BUILD,
)
from .labor_dispute_defense import (
    SYSTEM_PROMPT as _LD_DF_SYS,
    build_user_prompt as _LD_DF_BUILD,
)
from .labor_dispute_cross_exam import (
    SYSTEM_PROMPT as _LD_XE_SYS,
    build_user_prompt as _LD_XE_BUILD,
)
from .real_estate_pleading import (
    SYSTEM_PROMPT as _RE_PL_SYS,
    build_user_prompt as _RE_PL_BUILD,
)
from .real_estate_defense import (
    SYSTEM_PROMPT as _RE_DF_SYS,
    build_user_prompt as _RE_DF_BUILD,
)
from .real_estate_cross_exam import (
    SYSTEM_PROMPT as _RE_XE_SYS,
    build_user_prompt as _RE_XE_BUILD,
)

# (doc_type, case_type) â†?(system_prompt, build_user_prompt)
PROMPT_REGISTRY: dict[tuple[str, str], tuple[str, Callable]] = {
    ("pleading", "civil_loan"): (_CL_PL_SYS, _CL_PL_BUILD),
    ("defense", "civil_loan"): (_CL_DF_SYS, _CL_DF_BUILD),
    ("cross_exam", "civil_loan"): (_CL_XE_SYS, _CL_XE_BUILD),
    ("pleading", "labor_dispute"): (_LD_PL_SYS, _LD_PL_BUILD),
    ("defense", "labor_dispute"): (_LD_DF_SYS, _LD_DF_BUILD),
    ("cross_exam", "labor_dispute"): (_LD_XE_SYS, _LD_XE_BUILD),
    ("pleading", "real_estate"): (_RE_PL_SYS, _RE_PL_BUILD),
    ("defense", "real_estate"): (_RE_DF_SYS, _RE_DF_BUILD),
    ("cross_exam", "real_estate"): (_RE_XE_SYS, _RE_XE_BUILD),
}

__all__ = ["PROMPT_REGISTRY"]
Cannot set property. Property setting is supported only on core types in this language mode.
At line:1 char:1
+ [Console]::OutputEncoding=[System.Text.Encoding]::UTF8;
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : InvalidOperation: (:) [], RuntimeException
    + FullyQualifiedErrorId : PropertySetterNotSupportedInConstrainedLanguage
 

 succeeded in 627ms:
"""
æ–‡ä¹¦è¾…åŠ©å¼•æ“Žä¸»ç±»ã€?
Document assistance engine main class.

èŒè´£ / Responsibilities:
1. æ ¹æ® (doc_type, case_type) ä»?PROMPT_REGISTRY æŸ¥æ‰¾æç¤ºå‡½æ•°
2. è°ƒç”¨ call_structured_llm() èŽ·å–ç»“æž„åŒ–è¾“å‡?
3. æ ¡éªŒ evidence_ids_cited éžç©ºï¼ˆå¼ºåˆ¶éªŒæ”¶æ¡ä»¶ï¼‰
4. è¿”å›ž DocumentDraft

åˆçº¦ä¿è¯ / Contract guarantees:
- æ‰€æœ‰æˆåŠŸè¾“å‡ºçš„ DocumentDraft.evidence_ids_cited éžç©ºï¼ˆCrossExaminationOpinion ä¸?EvidenceIndex ä¸ºç©ºæ—¶é™¤å¤–ï¼‰
- LLM è¿”å›žä¸ç¬¦å?schema çš?JSON â†?DocumentGenerationErrorï¼Œæ¶ˆæ¯åŒ…å?doc_type å’?case_type
- (doc_type, case_type) ä¸åœ¨ PROMPT_REGISTRY â†?DocumentGenerationError
- EvidenceIndex ä¸ºç©º + doc_type=cross_exam â†?è¿”å›ž items=[]ï¼Œä¸è°?LLMï¼Œä¸æŠ›é”™
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Union

from engines.shared.models import LLMClient
from engines.shared.structured_output import call_structured_llm

from .prompts import PROMPT_REGISTRY
from .schemas import (
    CrossExaminationOpinion,
    CrossExaminationOpinionItem,
    DefenseStatement,
    DocumentAssistanceInput,
    DocumentDraft,
    DocumentGenerationError,
    PleadingDraft,
)

# æ¯ç§ doc_type å¯¹åº”çš?LLM tool å…ƒæ•°æ?
_TOOL_META: dict[str, tuple[str, str]] = {
    "pleading": ("generate_pleading_draft", "ç”Ÿæˆèµ·è¯‰çŠ¶éª¨æž¶è‰ç¨?),
    "defense": ("generate_defense_statement", "ç”Ÿæˆç­”è¾©çŠ¶éª¨æž¶è‰ç¨?),
    "cross_exam": ("generate_cross_exam_opinion", "ç”Ÿæˆè´¨è¯æ„è§éª¨æž¶è‰ç¨¿"),
}

# æ¯ç§ doc_type å¯¹åº”çš?LLM è¾“å‡º JSON Schema
_TOOL_SCHEMAS: dict[str, dict] = {
    "pleading": PleadingDraft.model_json_schema(),
    "defense": DefenseStatement.model_json_schema(),
    "cross_exam": CrossExaminationOpinion.model_json_schema(),
}


def _parse_content(
    doc_type: str,
    data: dict,
) -> Union[PleadingDraft, DefenseStatement, CrossExaminationOpinion]:
    """å°?LLM è¿”å›žçš?dict è§£æžä¸ºå¯¹åº”çš„æ–‡ä¹¦éª¨æž¶æ¨¡åž‹ã€?
    Parse LLM-returned dict into the corresponding document skeleton model.
    """
    if doc_type == "pleading":
        return PleadingDraft.model_validate(data)
    if doc_type == "defense":
        return DefenseStatement.model_validate(data)
    if doc_type == "cross_exam":
        return CrossExaminationOpinion.model_validate(data)
    raise ValueError(f"Unknown doc_type: {doc_type}")  # pragma: no cover


class DocumentAssistanceEngine:
    """æ–‡ä¹¦è¾…åŠ©å¼•æ“Žã€?

    Args:
        llm_client:  ç¬¦åˆ LLMClient åè®®çš„å®¢æˆ·ç«¯å®žä¾‹
        model:       LLM æ¨¡åž‹æ ‡è¯†
        temperature: ç”Ÿæˆæ¸©åº¦ï¼ˆé»˜è®?0.0ï¼?
        max_retries: LLM è°ƒç”¨å¤±è´¥æ—¶çš„æœ€å¤§é‡è¯•æ¬¡æ•?
    """

    def __init__(
        self,
        llm_client: LLMClient,
        *,
        model: str,
        temperature: float = 0.0,
        max_retries: int = 3,
    ) -> None:
        self._llm = llm_client
        self._model = model
        self._temperature = temperature
        self._max_retries = max_retries

    async def generate(self, *, input: DocumentAssistanceInput) -> DocumentDraft:
        """ç”Ÿæˆä¸€ä»½ç»“æž„åŒ–æ–‡ä¹¦è‰ç¨¿ã€?
        Generate a structured document draft.

        Args:
            input: DocumentAssistanceInput â€?åŒ…å«æ¡ˆä»¶ä¸Šä¸‹æ–‡å’Œæ–‡ä¹¦ç±»åž‹ / contains case context and doc type

        Returns:
            DocumentDraft â€?ç»“æž„åŒ–æ–‡ä¹¦éª¨æž?/ structured document skeleton

        Raises:
            DocumentGenerationError: LLM å¤±è´¥ã€schema æ ¡éªŒå¤±è´¥æˆ?evidence_ids_cited ä¸ºç©ºæ—¶æŠ›å‡?/
                                     raised on LLM failure, schema validation failure,
                                     or empty evidence_ids_cited
        """
        doc_type = input.doc_type
        case_type = input.case_type

        # æ ¡éªŒ (doc_type, case_type) æ³¨å†Œ
        key = (doc_type, case_type)
        if key not in PROMPT_REGISTRY:
            raise DocumentGenerationError(
                f"No prompt registered for doc_type={doc_type}, case_type={case_type}"
            )

        # è¾¹ç•Œæƒ…å†µï¼šcross_exam + ç©ºè¯æ?â†?ä¸è°ƒ LLMï¼Œç›´æŽ¥è¿”å›žç©º
        if doc_type == "cross_exam" and not input.evidence_index.evidence:
            content = CrossExaminationOpinion(items=[], evidence_ids_cited=[])
            return DocumentDraft(
                doc_type=doc_type,
                case_type=case_type,
                case_id=input.case_id,
                run_id=input.run_id,
                content=content,
                evidence_ids_cited=[],
                generated_at=datetime.now(timezone.utc).isoformat(),
            )

        # èŽ·å– prompt
        system_prompt, build_user_prompt = PROMPT_REGISTRY[key]
        user_prompt = build_user_prompt(
            issue_tree=input.issue_tree,
            evidence_index=input.evidence_index,
            case_data=input.case_data,
            attack_chain=input.attack_chain,
        )

        # è°ƒç”¨ LLM
        tool_name, tool_desc = _TOOL_META[doc_type]
        tool_schema = _TOOL_SCHEMAS[doc_type]

        try:
            data = await call_structured_llm(
                self._llm,
                system=system_prompt,
                user=user_prompt,
                model=self._model,
                tool_name=tool_name,
                tool_description=tool_desc,
                tool_schema=tool_schema,
                temperature=self._temperature,
                max_retries=self._max_retries,
            )
        except Exception as exc:
            raise DocumentGenerationError(
                f"LLM call failed for doc_type={doc_type}, case_type={case_type}: {exc}"
            ) from exc

        # è§£æžä¸ºå¯¹åº?schema
        try:
            content = _parse_content(doc_type, data)
        except Exception as exc:
            raise DocumentGenerationError(
                f"Schema validation failed for doc_type={doc_type}, case_type={case_type}: {exc}"
            ) from exc

        # å¼ºåˆ¶éªŒæ”¶æ¡ä»¶ï¼ševidence_ids_cited éžç©º
        if not content.evidence_ids_cited:
            raise DocumentGenerationError(
                f"evidence_ids_cited is empty for doc_type={doc_type}, case_type={case_type}; "
                "document drafts must cite at least 1 evidence_id"
            )

        # å¯?cross_exam è¡¥å…… items ä¸­çš„ evidence_idï¼ˆç¡®ä¿è¦†ç›?LLM å¯èƒ½ç¼ºå¤±çš„æ¡ç›®ï¼‰
        if doc_type == "cross_exam":
            cited_in_items = {item.evidence_id for item in content.items}
            extra = [eid for eid in content.evidence_ids_cited if eid not in cited_in_items]
            if extra:
                extra_items = [
                    CrossExaminationOpinionItem(
                        evidence_id=eid,
                        opinion_text="ï¼ˆLLM æœªç”Ÿæˆå…·ä½“æ„è§ï¼Œè¯·å¾‹å¸ˆè¡¥å……ï¼‰",
                    )
                    for eid in extra
                ]
                content = CrossExaminationOpinion(
                    items=content.items + extra_items,
                    evidence_ids_cited=content.evidence_ids_cited,
                )

        return DocumentDraft(
            doc_type=doc_type,
            case_type=case_type,
            case_id=input.case_id,
            run_id=input.run_id,
            content=content,
            evidence_ids_cited=content.evidence_ids_cited,
            generated_at=datetime.now(timezone.utc).isoformat(),
        )
Cannot set property. Property setting is supported only on core types in this language mode.
At line:1 char:1
+ [Console]::OutputEncoding=[System.Text.Encoding]::UTF8;
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : InvalidOperation: (:) [], RuntimeException
    + FullyQualifiedErrorId : PropertySetterNotSupportedInConstrainedLanguage
 

 succeeded in 639ms:
"""
æ–‡ä¹¦è¾…åŠ©å¼•æ“Žæ•°æ®æ¨¡åž‹ã€?
Document assistance engine data models.

ç»“æž„åŒ–å¡«ç©ºç­–ç•¥ï¼šschema å®šä¹‰éª¨æž¶å­—æ®µï¼ŒLLM åªå¡«å…?List[str] å†…å®¹æ¡ç›®ã€?
Structured fill strategy: schema defines skeleton fields, LLM fills only List[str] content items.

æ‰€æœ‰æ–‡ä¹¦è‰ç¨¿å¿…é¡»å¼•ç”¨è‡³å°?1 ä¸?evidence_idï¼ˆevidence_ids_cited å¼ºåˆ¶éžç©ºï¼‰ã€?
All document drafts must cite at least 1 evidence_id (evidence_ids_cited must be non-empty).
"""

from __future__ import annotations

from typing import Any, Optional, Union

from pydantic import BaseModel, Field, field_validator

from engines.shared.models import EvidenceIndex, IssueTree


# ---------------------------------------------------------------------------
# ç¼–å·æ¡ç›®æ¨¡åž‹ / Numbered item model
# ---------------------------------------------------------------------------


class NumberedItem(BaseModel):
    """å¸¦åºå·çš„æ–‡ä¹¦æ¡ç›®ã€?
    A numbered document item with seq and text.
    """

    seq: int = Field(description="åºå· / Sequence number")
    text: str = Field(description="å†…å®¹ / Content text")


def _normalize_numbered_items(v: list) -> list[dict]:
    """Accept both list[str] and list[dict{seq, text}], normalize to list[dict].

    - str items are auto-wrapped: ``{"seq": i, "text": item}``
    - dict items are passed through as-is
    - NumberedItem instances are converted to dict via model_dump
    """
    result = []
    for i, item in enumerate(v, 1):
        if isinstance(item, str):
            result.append({"seq": i, "text": item})
        elif isinstance(item, NumberedItem):
            result.append({"seq": item.seq, "text": item.text})
        elif isinstance(item, dict):
            result.append(item)
        else:
            result.append({"seq": i, "text": str(item)})
    return result


# ---------------------------------------------------------------------------
# æ–‡ä¹¦éª¨æž¶æ¨¡åž‹ / Document skeleton models
# ---------------------------------------------------------------------------


class PleadingDraft(BaseModel):
    """èµ·è¯‰çŠ¶éª¨æž?â€?åŽŸå‘Šæ–¹ä½¿ç”¨ã€?
    Pleading draft skeleton â€?used by plaintiff.
    """

    header: str = Field(description="æ–‡ä¹¦æ ‡é¢˜åŠæ¡ˆä»¶åŸºæœ¬ä¿¡æ¯è¡Œ / Document title and case info line")
    fact_narrative_items: list[NumberedItem] = Field(
        description="äº‹å®žé™ˆè¿°æ¡ç›®åˆ—è¡¨ï¼ˆæ¯æ¡å« seq åºå·å’?text å†…å®¹ï¼? Fact narrative items"
    )
    legal_claim_items: list[NumberedItem] = Field(
        description="æ³•å¾‹ä¾æ®åŠè¯·æ±‚æƒåŸºç¡€æ¡ç›® / Legal basis and cause-of-action items"
    )
    prayer_for_relief_items: list[NumberedItem] = Field(
        description="å…·ä½“è¯‰è®¼è¯·æ±‚æ¡ç›® / Specific prayer-for-relief items"
    )
    evidence_ids_cited: list[str] = Field(
        description="æ–‡ä¹¦ä¸­å¼•ç”¨çš„è¯æ® ID åˆ—è¡¨ï¼ˆå¼ºåˆ¶éžç©ºï¼‰/ Evidence IDs cited (mandatory non-empty)"
    )
    attack_chain_basis: str = Field(
        default="unavailable",
        description="æ”»å‡»é“¾ç­–ç•¥ä¾æ®ï¼›OptimalAttackChain ä¸å¯ç”¨æ—¶æ ‡è®° 'unavailable' / Attack chain basis",
    )

    @field_validator(
        "fact_narrative_items", "legal_claim_items", "prayer_for_relief_items", mode="before"
    )
    @classmethod
    def _normalize_items(cls, v: list) -> list[dict]:
        return _normalize_numbered_items(v)


class DefenseStatement(BaseModel):
    """ç­”è¾©çŠ¶éª¨æž?â€?è¢«å‘Šæ–¹ä½¿ç”¨ã€?
    Defense statement skeleton â€?used by defendant.
    """

    header: str = Field(description="æ–‡ä¹¦æ ‡é¢˜åŠæ¡ˆä»¶åŸºæœ¬ä¿¡æ¯è¡Œ / Document title and case info line")
    denial_items: list[NumberedItem] = Field(
        description="é€é¡¹å¦è®¤åŽŸå‘Šä¸»å¼ çš„æ¡ç›?/ Items denying plaintiff's claims"
    )
    defense_claim_items: list[NumberedItem] = Field(
        description="å®žè´¨æ€§æŠ—è¾©ä¸»å¼ æ¡ç›®ï¼ˆè‡³å°‘ 1 æ¡å›žåº”åŽŸå‘Šæ ¸å¿ƒä¸»å¼ ï¼‰/ Substantive defense claim items"
    )
    counter_prayer_items: list[NumberedItem] = Field(
        description="è¢«å‘Šåè¯·æ±‚æˆ–è¦æ±‚é©³å›žåŽŸå‘Šè¯‰è¯·çš„æ¡ç›?/ Counter-prayer or dismissal request items"
    )
    evidence_ids_cited: list[str] = Field(
        description="æ–‡ä¹¦ä¸­å¼•ç”¨çš„è¯æ® ID åˆ—è¡¨ï¼ˆå¼ºåˆ¶éžç©ºï¼‰/ Evidence IDs cited (mandatory non-empty)"
    )

    @field_validator("denial_items", "defense_claim_items", "counter_prayer_items", mode="before")
    @classmethod
    def _normalize_items(cls, v: list) -> list[dict]:
        return _normalize_numbered_items(v)


class CrossExaminationOpinionItem(BaseModel):
    """é’ˆå¯¹å•ä¸ªè¯æ®çš„è´¨è¯æ„è§æ¡ç›®ã€?
    Cross-examination opinion item for a single evidence.
    """

    evidence_id: str = Field(description="è¢«è´¨è¯çš„è¯æ® ID / Evidence ID being examined")
    opinion_text: str = Field(
        description="é’ˆå¯¹è¯¥è¯æ®çš„è´¨è¯æ„è§ï¼ˆä¸€æ¡ï¼Œç®€æ˜Žå…·ä½“ï¼‰/ Opinion on this evidence"
    )


class CrossExaminationOpinion(BaseModel):
    """è´¨è¯æ„è§æ¡†æž¶ â€?åŸºäºŽ EvidenceIndex é€è¯æ®ç”Ÿæˆæ„è§æ¡ç›®ã€?
    Cross-examination opinion framework â€?generates per-evidence opinion items from EvidenceIndex.

    æ³¨æ„ï¼šä¸Ž pretrial_conference ä¸­çš„ CrossExaminationOpinion ä¸åŒï¼Œæ­¤å¤„ä¸ºæ–‡ä¹¦å±‚è´¨è¯æ„è§ï¼Œ
    éžæ•´ä½“æ–‡ä¹¦ã€‚EvidenceIndex ä¸ºç©ºæ—?items=[] ä¸”ä¸æŠ›é”™ã€?
    Note: distinct from pretrial_conference CrossExaminationOpinion â€?this is a document-level
    opinion framework. When EvidenceIndex is empty, items=[] without error.
    """

    items: list[CrossExaminationOpinionItem] = Field(
        default_factory=list,
        description="é€è¯æ®è´¨è¯æ„è§æ¡ç›®åˆ—è¡¨ï¼ˆæ¯è¯æ®æ°å¥?1 æ¡ï¼‰/ Per-evidence opinion items",
    )
    evidence_ids_cited: list[str] = Field(
        default_factory=list,
        description="å¼•ç”¨çš„è¯æ?ID åˆ—è¡¨ï¼ˆEvidenceIndex éžç©ºæ—¶å¼ºåˆ¶éžç©ºï¼‰/ Cited evidence IDs",
    )


# ---------------------------------------------------------------------------
# è¾“å…¥æ¨¡åž‹ / Input model
# ---------------------------------------------------------------------------


class DocumentAssistanceInput(BaseModel):
    """DocumentAssistanceEngine.generate() çš„è¾“å…¥ã€?
    Input to DocumentAssistanceEngine.generate().
    """

    case_id: str
    run_id: str
    doc_type: str = Field(description="æ–‡ä¹¦ç±»åž‹ï¼?pleading' | 'defense' | 'cross_exam'")
    case_type: str = Field(description="æ¡ˆä»¶ç±»åž‹ï¼?civil_loan' | 'labor_dispute' | 'real_estate'")
    issue_tree: IssueTree
    evidence_index: EvidenceIndex
    case_data: dict[str, Any] = Field(default_factory=dict)
    attack_chain: Optional[Any] = Field(
        default=None,
        description="OptimalAttackChain äº§ç‰©ï¼ˆå¯é€‰ï¼‰/ OptimalAttackChain artifact (optional)",
    )


# ---------------------------------------------------------------------------
# è¾“å‡ºæ¨¡åž‹ / Output model
# ---------------------------------------------------------------------------


class DocumentDraft(BaseModel):
    """DocumentAssistanceEngine è¾“å‡º â€?ç»“æž„åŒ–æ–‡ä¹¦è‰ç¨¿ã€?
    DocumentAssistanceEngine output â€?structured document draft.
    """

    doc_type: str = Field(description="'pleading' | 'defense' | 'cross_exam'")
    case_type: str = Field(description="'civil_loan' | 'labor_dispute' | 'real_estate'")
    case_id: str
    run_id: str
    content: Union[PleadingDraft, DefenseStatement, CrossExaminationOpinion] = Field(
        description="æ–‡ä¹¦éª¨æž¶å†…å®¹ / Document skeleton content",
        discriminator=None,
    )
    evidence_ids_cited: list[str] = Field(
        description="æ–‡ä¹¦ä¸­å¼•ç”¨çš„æ‰€æœ‰è¯æ?ID / All evidence IDs cited in the document"
    )
    generated_at: str = Field(description="ç”Ÿæˆæ—¶é—´ ISO8601 / Generation time ISO8601")


# ---------------------------------------------------------------------------
# å¼‚å¸¸ / Exceptions
# ---------------------------------------------------------------------------


class DocumentGenerationError(Exception):
    """æ–‡ä¹¦ç”Ÿæˆå¤±è´¥æ—¶æŠ›å‡ºã€?
    Raised when document generation fails.

    é”™è¯¯æ¶ˆæ¯å¿…é¡»åŒ…å« doc_type å’?case_type ä»¥ä¾¿è¯Šæ–­ã€?
    Error message must include doc_type and case_type for diagnostics.
    """
Cannot set property. Property setting is supported only on core types in this language mode.
At line:1 char:1
+ [Console]::OutputEncoding=[System.Text.Encoding]::UTF8;
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : InvalidOperation: (:) [], RuntimeException
    + FullyQualifiedErrorId : PropertySetterNotSupportedInConstrainedLanguage
 

exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -NoProfile -Command "Get-Content 'engines/pretrial_conference/agents/judge_agent.py' | Select-Object -First 240" in C:/Users/david/dev/case-adversarial-engine
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -NoProfile -Command "Get-Content 'engines/pretrial_conference/prompts/judge.py' | Select-Object -First 260" in C:/Users/david/dev/case-adversarial-engine
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -NoProfile -Command "Get-Content 'engines/pretrial_conference/prompts/__init__.py'" in C:/Users/david/dev/case-adversarial-engine
 succeeded in 591ms:
"""蠎ｭ蜑堺ｼ夊ｮｮ Prompt 讓｡譚ｿ豕ｨ蜀瑚｡?/ Pretrial conference prompt template registry."""

from typing import Any

from engines.shared.case_type_plugin import RegistryPlugin

PROMPT_REGISTRY: dict[str, Any] = {}


def register_prompt(case_type: str, module: Any) -> None:
    PROMPT_REGISTRY[case_type] = module


from . import civil_loan as _civil_loan_module  # noqa: E402
from . import labor_dispute as _labor_dispute_module  # noqa: E402
from . import real_estate as _real_estate_module  # noqa: E402

register_prompt("civil_loan", _civil_loan_module)
register_prompt("labor_dispute", _labor_dispute_module)
register_prompt("real_estate", _real_estate_module)

plugin = RegistryPlugin(PROMPT_REGISTRY)
Cannot set property. Property setting is supported only on core types in this language mode.
At line:1 char:1
+ [Console]::OutputEncoding=[System.Text.Encoding]::UTF8;
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : InvalidOperation: (:) [], RuntimeException
    + FullyQualifiedErrorId : PropertySetterNotSupportedInConstrainedLanguage
 

 succeeded in 646ms:
"""
ç¨‹åºæ³•å®˜ä»£ç† â€?v1.5 æ ¸å¿ƒç»„ä»¶ã€?
Judge agent â€?v1.5 core component.

èŒè´£ / Responsibilities:
1. åŸºäºŽå·²é‡‡çº³è¯æ®å’Œæœªè§£å†³äº‰ç‚¹ï¼Œé€šè¿‡ LLM ç”Ÿæˆè¿½é—®
2. æ¶ˆè´¹ v1.2 äº§ç‰©å¢žå¼ºè¿½é—®è´¨é‡ï¼ˆEvidenceGapItem, BlockingConditionï¼?
3. è§„åˆ™å±‚æ ¡éªŒï¼ˆè¿‡æ»¤å¹»è§‰ IDã€æ— æ•ˆæžšä¸¾ã€priority æˆªæ–­ï¼?
4. ç¡¬ä¸Šé™?10 ä¸ªé—®é¢?

åˆçº¦ä¿è¯ / Contract guarantees:
- æž„é€ å™¨æ–­è¨€ï¼šæ‰€æœ‰ä¼ å…¥è¯æ®å¿…é¡?status == admitted_for_discussion
- åªå¼•ç”¨å·²çŸ?evidence_id å’?issue_id
- åªé’ˆå¯?unresolved (open) issues ç”Ÿæˆè¿½é—®
- æ— æ•ˆ question_type è¢«ä¸¢å¼?
- priority æˆªæ–­åˆ?[1, 10]
- LLM å¤±è´¥æ—¶è¿”å›žç©º JudgeQuestionSetï¼Œä¸æŠ›å¼‚å¸?
"""

from __future__ import annotations

from engines.shared.models import (
    BlockingCondition,
    Evidence,
    EvidenceGapItem,
    EvidenceStatus,
    IssueStatus,
    IssueTree,
    LLMClient,
)

from ..prompts.judge import JUDGE_SYSTEM, build_judge_user_prompt
from ..schemas import (
    JudgeQuestion,
    JudgeQuestionSet,
    JudgeQuestionType,
    LLMJudgeQuestionOutput,
)

_MAX_QUESTIONS = 10


class JudgeAgent:
    """ç¨‹åºæ³•å®˜ä»£ç†ã€?

    Args:
        llm_client:  ç¬¦åˆ LLMClient åè®®çš„å®¢æˆ·ç«¯å®žä¾‹
        model:       LLM æ¨¡åž‹æ ‡è¯†
        temperature: ç”Ÿæˆæ¸©åº¦
        max_retries: LLM è°ƒç”¨å¤±è´¥æ—¶çš„æœ€å¤§é‡è¯•æ¬¡æ•?
    """

    def __init__(
        self,
        llm_client: LLMClient,
        *,
        model: str,
        temperature: float,
        max_retries: int,
    ) -> None:
        self._llm = llm_client
        self._model = model
        self._temperature = temperature
        self._max_retries = max_retries

    async def generate_questions(
        self,
        issue_tree: IssueTree,
        admitted_evidence: list[Evidence],
        *,
        evidence_gaps: list[EvidenceGapItem] | None = None,
        blocking_conditions: list[BlockingCondition] | None = None,
        case_id: str,
        run_id: str,
        plaintiff_party_id: str = "",
        defendant_party_id: str = "",
    ) -> JudgeQuestionSet:
        """ç”Ÿæˆæ³•å®˜è¿½é—®ã€?

        Args:
            issue_tree:          äº‰ç‚¹æ ?
            admitted_evidence:   å·²é‡‡çº³è¯æ®åˆ—è¡¨ï¼ˆå¿…é¡»å…¨éƒ¨ admitted_for_discussionï¼?
            evidence_gaps:       å¯é€‰ï¼Œè¯æ®ç¼ºå£åˆ—è¡¨ï¼ˆå¢žå¼ºè¿½é—®è´¨é‡ï¼‰
            blocking_conditions: å¯é€‰ï¼Œé˜»æ–­æ¡ä»¶åˆ—è¡¨ï¼ˆå¢žå¼ºè¿½é—®è´¨é‡ï¼‰
            case_id:             æ¡ˆä»¶ ID
            run_id:              è¿è¡Œ ID
            plaintiff_party_id:  åŽŸå‘Š party_id
            defendant_party_id:  è¢«å‘Š party_id

        Returns:
            JudgeQuestionSet

        Raises:
            ValueError: ä¼ å…¥äº†éž admitted_for_discussion çš„è¯æ?
        """
        # ä¸‰å±‚é˜²æ³„éœ²ä¹‹äºŒï¼šæž„é€ å™¨æ–­è¨€
        for ev in admitted_evidence:
            if ev.status != EvidenceStatus.admitted_for_discussion:
                raise ValueError(
                    f"JudgeAgent åªæŽ¥å?admitted_for_discussion è¯æ®ï¼?
                    f"æ”¶åˆ° {ev.evidence_id} status={ev.status.value}ã€?
                )

        # æž„å»ºå·²çŸ¥ ID é›†åˆ
        known_evidence_ids = {ev.evidence_id for ev in admitted_evidence}
        known_issue_ids = {iss.issue_id for iss in issue_tree.issues}

        # åªå– open äº‰ç‚¹
        open_issues = [iss for iss in issue_tree.issues if iss.status == IssueStatus.open]

        if not open_issues:
            return JudgeQuestionSet(case_id=case_id, run_id=run_id, questions=[])

        # è°ƒç”¨ LLM
        questions = await self._call_llm(
            open_issues=open_issues,
            admitted_evidence=admitted_evidence,
            evidence_gaps=evidence_gaps,
            blocking_conditions=blocking_conditions,
            known_evidence_ids=known_evidence_ids,
            known_issue_ids=known_issue_ids,
            plaintiff_party_id=plaintiff_party_id,
            defendant_party_id=defendant_party_id,
        )

        return JudgeQuestionSet(
            case_id=case_id,
            run_id=run_id,
            questions=questions[:_MAX_QUESTIONS],
        )

    # ------------------------------------------------------------------
    # ç§æœ‰æ–¹æ³•
    # ------------------------------------------------------------------

    async def _call_llm(
        self,
        open_issues: list,
        admitted_evidence: list[Evidence],
        evidence_gaps: list[EvidenceGapItem] | None,
        blocking_conditions: list[BlockingCondition] | None,
        known_evidence_ids: set[str],
        known_issue_ids: set[str],
        plaintiff_party_id: str,
        defendant_party_id: str,
    ) -> list[JudgeQuestion]:
        """è°ƒç”¨ LLM å¹¶è¿”å›žæ ¡éªŒåŽçš„é—®é¢˜åˆ—è¡¨ã€?""
        system = JUDGE_SYSTEM
        user = build_judge_user_prompt(
            issues=open_issues,
            admitted_evidence=admitted_evidence,
            evidence_gaps=evidence_gaps,
            blocking_conditions=blocking_conditions,
            plaintiff_party_id=plaintiff_party_id,
            defendant_party_id=defendant_party_id,
        )

        from engines.shared.llm_utils import call_llm_with_retry

        try:
            raw = await call_llm_with_retry(
                self._llm,
                system=system,
                user=user,
                model=self._model,
                temperature=self._temperature,
                max_retries=self._max_retries,
            )
            return self._parse_and_validate(
                raw,
                known_evidence_ids=known_evidence_ids,
                known_issue_ids=known_issue_ids,
            )
        except Exception:  # noqa: BLE001
            return []

    def _parse_and_validate(
        self,
        raw: str,
        known_evidence_ids: set[str],
        known_issue_ids: set[str],
    ) -> list[JudgeQuestion]:
        """è§£æžå¹¶æ ¡éª?LLM è¾“å‡ºã€?""
        from engines.shared.json_utils import _extract_json_object

        data = _extract_json_object(raw)
        llm_out = LLMJudgeQuestionOutput.model_validate(data)

        result: list[JudgeQuestion] = []
        for item in llm_out.questions:
            # æ ¡éªŒ issue_id
            if item.issue_id not in known_issue_ids:
                continue

            # æ ¡éªŒ question_type
            try:
                qtype = JudgeQuestionType(item.question_type)
            except ValueError:
                continue

            # è¿‡æ»¤å¹»è§‰ evidence_ids
            clean_ev_ids = [eid for eid in item.evidence_ids if eid in known_evidence_ids]
            if not clean_ev_ids:
                continue

            # priority æˆªæ–­åˆ?[1, 10]
            priority = max(1, min(10, item.priority))

            if not item.question_text or not item.question_id:
                continue

            result.append(
                JudgeQuestion(
                    question_id=item.question_id,
                    issue_id=item.issue_id,
                    evidence_ids=clean_ev_ids,
                    question_text=item.question_text,
                    target_party_id=item.target_party_id or "unknown",
                    question_type=qtype,
                    priority=priority,
                )
            )

        return result
Cannot set property. Property setting is supported only on core types in this language mode.
At line:1 char:1
+ [Console]::OutputEncoding=[System.Text.Encoding]::UTF8;
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : InvalidOperation: (:) [], RuntimeException
    + FullyQualifiedErrorId : PropertySetterNotSupportedInConstrainedLanguage
 

 succeeded in 656ms:
"""
æ³•å®˜è¿½é—® prompt æ¨¡æ¿ã€?
Judge questioning prompt templates.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from engines.shared.models import (
        BlockingCondition,
        Evidence,
        EvidenceGapItem,
        Issue,
    )


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

JUDGE_SYSTEM = """\
ä½ æ˜¯ä¸€ä½ç»éªŒä¸°å¯Œçš„æ°‘äº‹å®¡åˆ¤æ³•å®˜ï¼Œæ­£åœ¨ä¸»æŒåº­å‰ä¼šè®®ã€?

ä½ çš„èŒè´£ï¼?
1. åŸºäºŽå·²é‡‡çº³çš„è¯æ®å’Œå¾…å®¡äº‰ç‚¹ï¼Œæå‡ºå…³é”®è¿½é—®
2. è¿½é—®ç±»åž‹åŒ…æ‹¬ï¼?
   - clarificationï¼ˆæ¾„æ¸…ï¼‰ï¼šè¦æ±‚å½“äº‹äººè¯´æ˜Žå«ç³Šæˆ–çŸ›ç›¾ä¹‹å¤?
   - contradictionï¼ˆçŸ›ç›¾å‘çŽ°ï¼‰ï¼šæŒ‡å‡ºè¯æ®ä¹‹é—´æˆ–è¯æ®ä¸Žé™ˆè¿°ä¹‹é—´çš„çŸ›ç›¾
   - gapï¼ˆç¼ºè¯è¯†åˆ«ï¼‰ï¼šæŒ‡å‡ºå¾…è¯äº‹å®žç¼ºä¹å……åˆ†è¯æ®æ”¯æŒ?
   - legal_basisï¼ˆæ³•å¾‹ä¾æ®ï¼‰ï¼šè¦æ±‚å½“äº‹äººè¯´æ˜Žå…¶ä¸»å¼ çš„æ³•å¾‹ä¾æ®
3. æ¯ä¸ªé—®é¢˜å¿…é¡»ç»‘å®šåˆ°å…·ä½“äº‰ç‚¹å’Œç›¸å…³è¯æ®
4. é—®é¢˜æŒ‰é‡è¦æ€§æŽ’åºï¼ˆpriority 1-10ï¼? æœ€é‡è¦ï¼?

é‡è¦çº¦æŸï¼?
- åªè¾“å‡?JSON å¯¹è±¡ï¼Œä¸è¾“å‡ºä»»ä½•è§£é‡Šæ–‡å­—
- åªå¼•ç”¨å·²é‡‡çº³çš„è¯æ®ï¼ˆadmitted_for_discussionï¼‰ï¼Œä¸å¾—å¼•ç”¨æœªé‡‡çº³è¯æ?
- issue_id å’?evidence_ids å¿…é¡»ä½¿ç”¨è¾“å…¥ä¸­æä¾›çš„çœŸå®ž ID
- æœ€å¤šè¾“å‡?10 ä¸ªé—®é¢?
- ä¼˜å…ˆå…³æ³¨é‡‘é¢è®¡ç®—äº‰ç‚¹ï¼ˆcalculation_issueï¼‰å’Œå­˜åœ¨é˜»æ–­æ¡ä»¶çš„äº‰ç‚?
- ä¿æŒä¸­ç«‹å¸æ³•ç«‹åœº
"""


# ---------------------------------------------------------------------------
# User prompt builder
# ---------------------------------------------------------------------------


def build_judge_user_prompt(
    issues: list[Issue],
    admitted_evidence: list[Evidence],
    *,
    evidence_gaps: list[EvidenceGapItem] | None = None,
    blocking_conditions: list[BlockingCondition] | None = None,
    plaintiff_party_id: str = "",
    defendant_party_id: str = "",
) -> str:
    """æž„å»ºæ³•å®˜è¿½é—® user promptã€?""
    # äº‰ç‚¹åˆ—è¡¨
    issue_lines = []
    for iss in issues:
        cat = f" [{iss.issue_category.value}]" if iss.issue_category else ""
        status_str = iss.status.value if iss.status else "open"
        issue_lines.append(f"- {iss.issue_id}: {iss.title}{cat} (status: {status_str})")
    issue_block = "\n".join(issue_lines) if issue_lines else "ï¼ˆæ— äº‰ç‚¹ï¼?

    # å·²é‡‡çº³è¯æ?
    ev_lines = []
    for ev in admitted_evidence:
        ev_lines.append(
            f"- {ev.evidence_id}: {ev.title} "
            f"(owner: {ev.owner_party_id}, issues: {ev.target_issue_ids})"
        )
    ev_block = "\n".join(ev_lines) if ev_lines else "ï¼ˆæ— å·²é‡‡çº³è¯æ®ï¼‰"

    # å¯é€‰å¢žå¼ºï¼šè¯æ®ç¼ºå£
    gap_block = ""
    if evidence_gaps:
        gap_lines = []
        for g in evidence_gaps:
            gap_lines.append(
                f"- {g.gap_id}: {g.gap_description} (related_issue: {g.related_issue_id})"
            )
        gap_block = f"\n\n## è¯æ®ç¼ºå£\n" + "\n".join(gap_lines)

    # å¯é€‰å¢žå¼ºï¼šé˜»æ–­æ¡ä»¶
    bc_block = ""
    if blocking_conditions:
        bc_lines = []
        for bc in blocking_conditions:
            bc_lines.append(
                f"- {bc.condition_id}: {bc.description} "
                f"(type: {bc.condition_type.value}, "
                f"issues: {bc.linked_issue_ids})"
            )
        bc_block = f"\n\n## é˜»æ–­æ¡ä»¶\n" + "\n".join(bc_lines)

    # å½“äº‹äººä¿¡æ?
    party_block = ""
    if plaintiff_party_id or defendant_party_id:
        party_block = f"\n\n## å½“äº‹äºº\n- åŽŸå‘Š: {plaintiff_party_id}\n- è¢«å‘Š: {defendant_party_id}"

    return f"""\
è¯·åŸºäºŽä»¥ä¸‹åº­å‰ä¼šè®®ææ–™ï¼Œæå‡ºå…³é”®è¿½é—®ã€?

## äº‰ç‚¹åˆ—è¡¨
{issue_block}

## å·²é‡‡çº³è¯æ?
{ev_block}{gap_block}{bc_block}{party_block}

## è¾“å‡ºæ ¼å¼
è¯·ä¸¥æ ¼è¾“å‡ºå¦‚ä¸?JSONï¼ˆä¸è¦è¾“å‡ºå…¶ä»–å†…å®¹ï¼‰ï¼?
```json
{{
  "questions": [
    {{
      "question_id": "jq-001",
      "issue_id": "äº‰ç‚¹ID",
      "evidence_ids": ["ç›¸å…³è¯æ®ID"],
      "question_text": "è¿½é—®å†…å®¹",
      "target_party_id": "è¢«è¿½é—®æ–¹party_id",
      "question_type": "clarification|contradiction|gap|legal_basis",
      "priority": 1
    }}
  ]
}}
```

è¦æ±‚ï¼?
- æœ€å¤?10 ä¸ªé—®é¢˜ï¼ŒæŒ?priority ä»Žé«˜åˆ°ä½ŽæŽ’åºï¼? æœ€é‡è¦ï¼?
- ä¼˜å…ˆå…³æ³¨é‡‘é¢è®¡ç®—äº‰ç‚¹å’Œé˜»æ–­æ¡ä»¶ç›¸å…³äº‰ç‚?
- evidence_ids åªèƒ½ä½¿ç”¨ä¸Šé¢åˆ—å‡ºçš„å·²é‡‡çº³è¯æ® ID
- issue_id åªèƒ½ä½¿ç”¨ä¸Šé¢åˆ—å‡ºçš„äº‰ç‚?ID
- target_party_id ä½¿ç”¨å®žé™…çš?party_id
"""
Cannot set property. Property setting is supported only on core types in this language mode.
At line:1 char:1
+ [Console]::OutputEncoding=[System.Text.Encoding]::UTF8;
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : InvalidOperation: (:) [], RuntimeException
    + FullyQualifiedErrorId : PropertySetterNotSupportedInConstrainedLanguage
 

exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -NoProfile -Command "Get-ChildItem -Path 'engines/report_generation/v3' -Recurse -File" in C:/Users/david/dev/case-adversarial-engine
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -NoProfile -Command "Get-ChildItem -Path 'engines/simulation_run/issue_impact_ranker' -Recurse -File" in C:/Users/david/dev/case-adversarial-engine
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -NoProfile -Command "Get-ChildItem -Path 'engines/case_extraction' -Recurse -File" in C:/Users/david/dev/case-adversarial-engine
 succeeded in 615ms:


    Directory: C:\Users\david\dev\case-adversarial-engine\engines\simulation_run\issue_impact_ranker


Mode                 LastWriteTime         Length Name                                                                 
----                 -------------         ------ ----                                                                 
-a----          4/7/2026   3:27 PM          40068 ranker.py                                                            
-a----          4/7/2026   3:27 PM           4546 schemas.py                                                           
-a----         3/27/2026   3:33 PM            199 __init__.py                                                          


    Directory: C:\Users\david\dev\case-adversarial-engine\engines\simulation_run\issue_impact_ranker\prompts


Mode                 LastWriteTime         Length Name                                                                 
----                 -------------         ------ ----                                                                 
-a----          4/7/2026   3:27 PM          11408 civil_loan.py                                                        
-a----          4/7/2026   3:27 PM          10178 labor_dispute.py                                                     
-a----          4/7/2026   3:27 PM          10478 real_estate.py                                                       
-a----         3/31/2026   9:58 PM            747 __init__.py                                                          


    Directory: 
    C:\Users\david\dev\case-adversarial-engine\engines\simulation_run\issue_impact_ranker\prompts\__pycache__


Mode                 LastWriteTime         Length Name                                                                 
----                 -------------         ------ ----                                                                 
-a----          4/7/2026   3:28 PM          11502 civil_loan.cpython-312.pyc                                           
-a----          4/7/2026   3:28 PM          10452 labor_dispute.cpython-312.pyc                                        
-a----          4/7/2026   3:28 PM          10692 real_estate.cpython-312.pyc                                          
-a----         3/31/2026   9:59 PM           1044 __init__.cpython-312.pyc                                             


    Directory: C:\Users\david\dev\case-adversarial-engine\engines\simulation_run\issue_impact_ranker\tests


Mode                 LastWriteTime         Length Name                                                                 
----                 -------------         ------ ----                                                                 
-a----          4/7/2026   3:27 PM          37234 test_ranker.py                                                       
-a----         3/27/2026   3:34 PM              0 __init__.py                                                          


    Directory: C:\Users\david\dev\case-adversarial-engine\engines\simulation_run\issue_impact_ranker\tests\__pycache__


Mode                 LastWriteTime         Length Name                                                                 
----                 -------------         ------ ----                                                                 
-a----          4/7/2026   3:28 PM          84529 test_ranker.cpython-312-pytest-9.0.2.pyc                             
-a----         3/27/2026   3:37 PM            200 __init__.cpython-312.pyc                                             


    Directory: C:\Users\david\dev\case-adversarial-engine\engines\simulation_run\issue_impact_ranker\__pycache__


Mode                 LastWriteTime         Length Name                                                                 
----                 -------------         ------ ----                                                                 
-a----          4/7/2026   3:28 PM          38060 ranker.cpython-312.pyc                                               
-a----          4/7/2026   3:28 PM           5287 schemas.cpython-312.pyc                                              
-a----         3/27/2026   3:37 PM            406 __init__.cpython-312.pyc                                             


Cannot set property. Property setting is supported only on core types in this language mode.
At line:1 char:1
+ [Console]::OutputEncoding=[System.Text.Encoding]::UTF8;
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : InvalidOperation: (:) [], RuntimeException
    + FullyQualifiedErrorId : PropertySetterNotSupportedInConstrainedLanguage
 

 succeeded in 625ms:


    Directory: C:\Users\david\dev\case-adversarial-engine\engines\case_extraction


Mode                 LastWriteTime         Length Name                                                                 
----                 -------------         ------ ----                                                                 
-a----         3/31/2026   9:58 PM          15423 extractor.py                                                         
-a----         3/31/2026   9:58 PM           4978 schemas.py                                                           
-a----         3/31/2026   1:09 PM            279 __init__.py                                                          


    Directory: C:\Users\david\dev\case-adversarial-engine\engines\case_extraction\tests


Mode                 LastWriteTime         Length Name                                                                 
----                 -------------         ------ ----                                                                 
-a----         3/31/2026   1:09 PM          11760 test_extractor.py                                                    
-a----         3/31/2026   1:09 PM              0 __init__.py                                                          


    Directory: C:\Users\david\dev\case-adversarial-engine\engines\case_extraction\tests\__pycache__


Mode                 LastWriteTime         Length Name                                                                 
----                 -------------         ------ ----                                                                 
-a----         3/31/2026   2:58 PM          35418 test_extractor.cpython-312-pytest-9.0.2.pyc                          
-a----         3/31/2026   2:58 PM            181 __init__.cpython-312.pyc                                             


    Directory: C:\Users\david\dev\case-adversarial-engine\engines\case_extraction\__pycache__


Mode                 LastWriteTime         Length Name                                                                 
----                 -------------         ------ ----                                                                 
-a----         3/31/2026   9:59 PM          13606 extractor.cpython-312.pyc                                            
-a----         3/31/2026   9:59 PM           5779 schemas.cpython-312.pyc                                              
-a----         3/31/2026   2:58 PM            471 __init__.cpython-312.pyc                                             


Cannot set property. Property setting is supported only on core types in this language mode.
At line:1 char:1
+ [Console]::OutputEncoding=[System.Text.Encoding]::UTF8;
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : InvalidOperation: (:) [], RuntimeException
    + FullyQualifiedErrorId : PropertySetterNotSupportedInConstrainedLanguage
 

 succeeded in 663ms:


    Directory: C:\Users\david\dev\case-adversarial-engine\engines\report_generation\v3


Mode                 LastWriteTime         Length Name                                                                 
----                 -------------         ------ ----                                                                 
-a----          4/6/2026   4:54 PM           1266 docx_lint.py                                                         
-a----          4/6/2026   4:54 PM           1461 docx_styles.py                                                       
-a----          4/3/2026   1:22 AM          20333 evidence_battle_matrix.py                                            
-a----          4/3/2026   1:22 AM          15263 evidence_classifier.py                                               
-a----          4/3/2026   1:22 AM           6869 fact_base.py                                                         
-a----          4/3/2026   1:22 AM          15047 issue_map.py                                                         
-a----          4/3/2026   1:22 AM          11938 layer1_cover.py                                                      
-a----          4/3/2026   1:22 AM          10728 layer2_core.py                                                       
-a----          4/3/2026   1:22 AM          25075 layer3_perspective.py                                                
-a----          4/3/2026   1:22 AM          16480 layer4_appendix.py                                                   
-a----          4/3/2026   1:22 AM          16172 models.py                                                            
-a----          4/6/2026  12:13 PM          11865 render_contract.py                                                   
-a----          4/6/2026   5:37 PM           5800 report_fixer.py                                                      
-a----          4/6/2026   7:14 PM          11032 report_writer.py                                                     
-a----          4/3/2026   1:22 AM           7950 scenario_tree.py                                                     
-a----          4/3/2026   1:22 AM          10925 tag_system.py                                                        
-a----          4/2/2026  12:11 AM           1573 __init__.py                                                          


    Directory: C:\Users\david\dev\case-adversarial-engine\engines\report_generation\v3\golden_artifacts


Mode                 LastWriteTime         Length Name                                                                 
----                 -------------         ------ ----                                                                 
-a----          4/6/2026   7:14 PM          13507 civil_loan_v3_golden.md                                              
-a----          4/6/2026   7:14 PM          19953 labor_dispute_v3_golden.md                                           
-a----          4/6/2026   7:14 PM          20068 real_estate_v3_golden.md                                             
-a----          4/6/2026   7:14 PM             57 __init__.py                                                          


    Directory: C:\Users\david\dev\case-adversarial-engine\engines\report_generation\v3\tests


Mode                 LastWriteTime         Length Name                                                                 
----                 -------------         ------ ----                                                                 
-a----          4/6/2026   7:14 PM          50694 test_civil_loan_acceptance.py                                        
-a----          4/6/2026   4:54 PM          10140 test_docx_v3.py                                                      
-a----          4/3/2026   1:22 AM           5028 test_evidence_battle_matrix.py                                       
-a----          4/6/2026   7:14 PM          63252 test_labor_dispute_acceptance.py                                     
-a----          4/3/2026   1:22 AM          14444 test_models.py                                                       
-a----          4/6/2026   7:14 PM          11877 test_multi_case_integration.py                                       
-a----          4/6/2026   7:14 PM          60094 test_real_estate_acceptance.py                                       
-a----          4/6/2026   7:14 PM          13749 test_render_contract.py                                              
-a----          4/6/2026   5:37 PM           8303 test_report_fixer.py                                                 
-a----          4/6/2026   5:37 PM          15740 test_report_writer.py                                                
-a----          4/6/2026   7:14 PM          23624 test_resume_rebuild.py                                               
-a----          4/3/2026   1:22 AM           6504 test_scenario_tree.py                                                
-a----          4/1/2026  12:51 PM              0 __init__.py                                                          


    Directory: C:\Users\david\dev\case-adversarial-engine\engines\report_generation\v3\tests\__pycache__


Mode                 LastWriteTime         Length Name                                                                 
----                 -------------         ------ ----                                                                 
-a----          4/6/2026   7:22 PM          82482 test_civil_loan_acceptance.cpython-312-pytest-9.0.2.pyc              
-a----          4/6/2026   7:22 PM          19572 test_docx_v3.cpython-312-pytest-9.0.2.pyc                            
-a----          4/6/2026   7:22 PM          17337 test_evidence_battle_matrix.cpython-312-pytest-9.0.2.pyc             
-a----          4/6/2026   7:22 PM         100993 test_labor_dispute_acceptance.cpython-312-pytest-9.0.2.pyc           
-a----          4/6/2026   7:22 PM          61728 test_models.cpython-312-pytest-9.0.2.pyc                             
-a----          4/6/2026   7:22 PM          26463 test_multi_case_integration.cpython-312-pytest-9.0.2.pyc             
-a----          4/6/2026   7:22 PM         104263 test_real_estate_acceptance.cpython-312-pytest-9.0.2.pyc             
-a----          4/6/2026   7:22 PM          23720 test_render_contract.cpython-312-pytest-9.0.2.pyc                    
-a----          4/6/2026   7:22 PM          31906 test_report_fixer.cpython-312-pytest-9.0.2.pyc                       
-a----          4/6/2026   7:22 PM          36673 test_report_writer.cpython-312-pytest-9.0.2.pyc                      
-a----          4/6/2026   7:22 PM          39985 test_resume_rebuild.cpython-312-pytest-9.0.2.pyc                     
-a----          4/6/2026   7:22 PM          19240 test_scenario_tree.cpython-312-pytest-9.0.2.pyc                      
-a----          4/2/2026  12:13 AM            186 __init__.cpython-312.pyc                                             


    Directory: C:\Users\david\dev\case-adversarial-engine\engines\report_generation\v3\__pycache__


Mode                 LastWriteTime         Length Name                                                                 
----                 -------------         ------ ----                                                                 
-a----          4/6/2026   7:22 PM           2012 docx_lint.cpython-312.pyc                                            
-a----          4/6/2026   7:22 PM           1164 docx_styles.cpython-312.pyc                                          
-a----          4/3/2026   1:23 AM          18310 evidence_battle_matrix.cpython-312.pyc                               
-a----          4/3/2026   1:23 AM          13752 evidence_classifier.cpython-312.pyc                                  
-a----          4/3/2026   1:23 AM           6997 fact_base.cpython-312.pyc                                            
-a----          4/3/2026   1:23 AM          13608 issue_map.cpython-312.pyc                                            
-a----          4/3/2026   1:23 AM          12804 layer1_cover.cpython-312.pyc                                         
-a----          4/3/2026   1:23 AM          12919 layer2_core.cpython-312.pyc                                          
-a----          4/3/2026   1:23 AM          23242 layer3_perspective.cpython-312.pyc                                   
-a----          4/3/2026   1:23 AM          18090 layer4_appendix.cpython-312.pyc                                      
-a----          4/3/2026   1:22 AM          17622 models.cpython-312.pyc                                               
-a----          4/6/2026   5:18 PM          14278 render_contract.cpython-312.pyc                                      
-a----          4/6/2026   7:22 PM           6637 report_fixer.cpython-312.pyc                                         
-a----          4/6/2026   7:22 PM          12612 report_writer.cpython-312.pyc                                        
-a----          4/3/2026   1:23 AM           8551 scenario_tree.cpython-312.pyc                                        
-a----          4/3/2026   1:22 AM          13186 tag_system.cpython-312.pyc                                           
-a----          4/2/2026  12:11 AM           1320 __init__.cpython-312.pyc                                             


Cannot set property. Property setting is supported only on core types in this language mode.
At line:1 char:1
+ [Console]::OutputEncoding=[System.Text.Encoding]::UTF8;
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : InvalidOperation: (:) [], RuntimeException
    + FullyQualifiedErrorId : PropertySetterNotSupportedInConstrainedLanguage
 

2026-04-07T11:30:12.535691Z ERROR codex_core::tools::router: error=`"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -NoProfile -Command "Select-String -Path 'engines/report_generation/v3/*.py','engines/report_generation/v3/tests/*.py' -Pattern 'civil_loan|labor_dispute|real_estate|case_type'"` rejected: blocked by policy
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -NoProfile -Command "Select-String -Path 'engines/report_generation/v3/*.py','engines/report_generation/v3/tests/*.py' -Pattern 'civil_loan|labor_dispute|real_estate|case_type'" in C:/Users/david/dev/case-adversarial-engine
 declined in 0ms:
`"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -NoProfile -Command "Select-String -Path 'engines/report_generation/v3/*.py','engines/report_generation/v3/tests/*.py' -Pattern 'civil_loan|labor_dispute|real_estate|case_type'"` rejected: blocked by policy
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -NoProfile -Command "Get-Content 'engines/simulation_run/issue_impact_ranker/ranker.py' | Select-Object -First 260" in C:/Users/david/dev/case-adversarial-engine
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -NoProfile -Command "Get-Content 'engines/case_extraction/schemas.py' | Select-Object -First 180" in C:/Users/david/dev/case-adversarial-engine
 succeeded in 614ms:
"""
IssueImpactRanker â€?äº‰ç‚¹å½±å“æŽ’åºæ¨¡å—ä¸»ç±»ã€?
Issue Impact Ranker â€?main class for P0.1 issue impact ranking.

èŒè´£ / Responsibilities:
1. æŽ¥æ”¶ IssueTree + EvidenceIndex + AmountCalculationReport + proponent_party_id
2. ä¸€æ¬¡æ€§è°ƒç”?LLM å¯¹æ‰€æœ‰äº‰ç‚¹è¿›è¡Œäº”ç»´åº¦æ‰¹é‡è¯„ä¼°
3. è§„åˆ™å±‚ï¼šè§£æžæžšä¸¾ã€æ ¡éªŒè¯æ®ç»‘å®šã€è¿‡æ»¤éžæ³?IDã€é™çº§å¤„ç?
4. æŒ?outcome_impact DESC â†?opponent_attack_strength DESC æŽ’åº
5. è¿”å›žå¯ŒåŒ–åŽçš„ IssueImpactRankingResult

åˆçº¦ä¿è¯ / Contract guarantees:
- outcome_impact / recommended_action å¿…é¡»æžšä¸¾å€¼ï¼Œå¦åˆ™æ¸…ç©ºå¹¶è®°å…?unevaluated
- strength é?None æ—?evidence_ids å¿…é¡»éžç©ºä¸”åˆæ³•ï¼Œå¦åˆ™æ¸…ç©ºå¹¶è®°å…?unevaluated
- recommended_action é?None æ—?basis å¿…é¡»éžç©ºï¼Œå¦åˆ™æ¸…ç©ºå¹¶è®°å…¥ unevaluated
- LLM è¿”å›žæœªçŸ¥ issue_id è¢«è¿‡æ»¤å¿½ç•?
- LLM æ•´ä½“å¤±è´¥è¿”å›ž failed ç»“æžœï¼ˆåŽŸå§‹é¡ºåºï¼Œå…¨éƒ¨äº‰ç‚¹è¿?unevaluatedï¼‰ï¼Œä¸æŠ›å¼‚å¸¸
- ç©ºäº‰ç‚¹æ ‘ä¸è°ƒç”?LLMï¼Œç›´æŽ¥è¿”å›?
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)

from engines.shared.models import (
    AdmissibilityStatus,
    AttackStrength,
    Evidence,
    EvidenceStrength,
    Issue,
    LLMClient,
    OutcomeImpact,
    RecommendedAction,
)

from engines.shared.structured_output import call_structured_llm

from .schemas import (
    IssueImpactRankerInput,
    IssueImpactRankingResult,
    LLMIssueEvaluationOutput,
    LLMSingleIssueEvaluation,
)

# tool_use JSON Schemaï¼ˆæ¨¡å—åŠ è½½æ—¶è®¡ç®—ä¸€æ¬¡ï¼‰
_TOOL_SCHEMA: dict = LLMIssueEvaluationOutput.model_json_schema()

# æŽ’åºæƒé‡æ˜ å°„ï¼ˆNone â†?99 æŽ’æœ«å°¾ï¼‰
_IMPACT_ORDER: dict[OutcomeImpact, int] = {
    OutcomeImpact.high: 0,
    OutcomeImpact.medium: 1,
    OutcomeImpact.low: 2,
}
_ATTACK_ORDER: dict[AttackStrength, int] = {
    AttackStrength.strong: 0,
    AttackStrength.medium: 1,
    AttackStrength.weak: 2,
}

# outcome_impact å¯?composite_score çš„åŠ æˆï¼ˆæ ¡å‡†ï¼šç¡®ä¿é«˜å½±å“äº‰ç‚¹ä¸è¢«ä½Žåˆ†æ•°æ·¹æ²¡ï¼‰
_IMPACT_BONUS: dict[OutcomeImpact, float] = {
    OutcomeImpact.high: 20.0,
    OutcomeImpact.medium: 10.0,
    OutcomeImpact.low: 0.0,
}


class IssueImpactRanker:
    """äº‰ç‚¹å½±å“æŽ’åºå™¨ã€?

    Args:
        llm_client:  ç¬¦åˆ LLMClient åè®®çš„å®¢æˆ·ç«¯å®žä¾‹
        case_type:   æ¡ˆç”±ç±»åž‹ï¼Œé»˜è®?"civil_loan"
        model:       LLM æ¨¡åž‹åç§°
        temperature: LLM æ¸©åº¦å‚æ•°
        max_tokens:  LLM æœ€å¤§è¾“å‡?token æ•?
        max_retries: LLM è°ƒç”¨å¤±è´¥æ—¶çš„æœ€å¤§é‡è¯•æ¬¡æ•?
    """

    # æ¯æ‰¹æœ€å¤šå‘é€ç»™ LLM çš„äº‰ç‚¹æ•°é‡ã€‚è¶…è¿‡æ—¶è‡ªåŠ¨åˆ†æ‰¹ï¼Œæ¯æ‰¹ç‹¬ç«‹é‡è¯•ã€?
    # Max issues per LLM call. Larger batches increase the risk of schema failures.
    _BATCH_SIZE: int = 5

    def __init__(
        self,
        llm_client: LLMClient,
        case_type: str = "civil_loan",
        *,
        model: str = "claude-sonnet-4-20250514",
        temperature: float = 0.0,
        max_tokens: int = 16000,
        max_retries: int = 3,
    ) -> None:
        self._llm = llm_client
        self._case_type = case_type
        self._model = model
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._max_retries = max_retries
        self._prompt_module = self._load_prompt_module(case_type)
        # Unit 22 Phase C.5a: per-case-type vocabulary lookup. Resolved once at
        # __init__ time so the hot path in _resolve_impact_targets stays a
        # single set-membership test. Raises if case_type's prompt module did
        # not declare ALLOWED_IMPACT_TARGETS â€?this surfaces the wiring bug
        # immediately on construction rather than later inside rank().
        from .prompts import plugin

        self._allowed_impact_targets: frozenset[str] = plugin.allowed_impact_targets(
            case_type
        )

    @staticmethod
    def _load_prompt_module(case_type: str):
        """åŠ è½½æ¡ˆç”±å¯¹åº”çš?prompt æ¨¡æ¿æ¨¡å—ã€?""
        from .prompts import PROMPT_REGISTRY

        if case_type not in PROMPT_REGISTRY:
            available = ", ".join(PROMPT_REGISTRY.keys()) or "(none)"
            raise ValueError(f"ä¸æ”¯æŒçš„æ¡ˆç”±ç±»åž‹: '{case_type}'ã€‚å¯ç”? {available}")
        return PROMPT_REGISTRY[case_type]

    async def rank(self, inp: IssueImpactRankerInput) -> IssueImpactRankingResult:
        """æ‰§è¡Œäº‰ç‚¹å½±å“æŽ’åºã€?

        Args:
            inp: æŽ’åºå™¨è¾“å…¥ï¼ˆå«äº‰ç‚¹æ ‘ã€è¯æ®ç´¢å¼•ã€é‡‘é¢æŠ¥å‘Šã€ä¸»å¼ æ–¹ IDï¼?

        Returns:
            IssueImpactRankingResult â€?å«æŽ’åºåŽçš„å¯ŒåŒ–äº‰ç‚¹æ ‘
        """
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        issues = list(inp.issue_tree.issues)

        # ç©ºäº‰ç‚¹æ ‘ï¼šç›´æŽ¥è¿”å›žï¼Œä¸è°ƒç”?LLM
        if not issues:
            return IssueImpactRankingResult(
                ranked_issue_tree=inp.issue_tree,
                evaluation_metadata={},
                unevaluated_issue_ids=[],
                created_at=now,
            )

        known_issue_ids: set[str] = {i.issue_id for i in issues}
        known_evidence_ids: set[str] = {e.evidence_id for e in inp.evidence_index.evidence}

        # å°†äº‰ç‚¹åˆ†æ‰¹ï¼Œæ¯æ‰¹æœ€å¤?_BATCH_SIZE æ¡ï¼Œé¿å… LLM å› è¾“å…¥è¿‡é•¿è€Œè¿”å›žéžæ³?schema
        batches = [
            issues[i : i + self._BATCH_SIZE] for i in range(0, len(issues), self._BATCH_SIZE)
        ]
        logger.info(
            "æ‰¹é‡è¯„ä¼°ï¼?d æ¡äº‰ç‚¹åˆ†ä¸?%d æ‰¹ï¼ˆæ¯æ‰¹æœ€å¤?%d æ¡ï¼‰",
            len(issues),
            len(batches),
            self._BATCH_SIZE,
        )

        from .prompts import plugin

        system_prompt = self._prompt_module.SYSTEM_PROMPT
        all_evaluations: list[LLMSingleIssueEvaluation] = []
        _rescaled_ids: list[str] = []
        failed_batch_count = 0

        for batch_idx, batch_issues in enumerate(batches):
            try:
                # ä¸ºæœ¬æ‰¹æ¬¡æž„å»ºç‹¬ç«‹ promptï¼ˆä¸´æ—?IssueTree ä»…å«æœ¬æ‰¹äº‰ç‚¹ï¼?
                batch_tree = inp.issue_tree.model_copy(update={"issues": batch_issues})
                user_prompt = plugin.get_prompt(
                    "issue_impact_ranker",
                    self._case_type,
                    {
                        "issue_tree": batch_tree,
                        "evidence_index": inp.evidence_index,
                        "proponent_party_id": inp.proponent_party_id,
                        "amount_check": (
                            inp.amount_calculation_report.consistency_check_result
                            if inp.amount_calculation_report is not None
                            else None
                        ),
                    },
                )

                raw_dict = await self._call_llm_structured(system_prompt, user_prompt)

                logger.info(
                    "æ‰¹æ¬¡ %d/%d JSON è§£æžæˆåŠŸï¼Œé¡¶å±‚é”®: %s",
                    batch_idx + 1,
                    len(batches),
                    list(raw_dict.keys()),
                )
                raw_dict = self._normalize_evaluation_keys(raw_dict)

                if "evaluations" in raw_dict and isinstance(raw_dict["evaluations"], list):
                    raw_dict["evaluations"] = [
                        self._normalize_single_eval(item) if isinstance(item, dict) else item
                        for item in raw_dict["evaluations"]
                    ]
                    if raw_dict["evaluations"]:
                        logger.debug(
                            "æ‰¹æ¬¡ %d/%d é¦–æ¡è¯„ä¼°é¡¹é”®: %s",
                            batch_idx + 1,
                            len(batches),
                            list(raw_dict["evaluations"][0].keys()),
                        )
                    for ev_item in raw_dict["evaluations"]:
                        if isinstance(ev_item, dict) and ev_item.pop("_score_rescaled", False):
                            _rescaled_ids.append(ev_item.get("issue_id", "?"))

                batch_output = LLMIssueEvaluationOutput.model_validate(raw_dict)
                logger.info(
                    "æ‰¹æ¬¡ %d/%d è¯„ä¼°æ¡ç›®æ•? %d",
                    batch_idx + 1,
                    len(batches),
                    len(batch_output.evaluations),
                )
                all_evaluations.extend(batch_output.evaluations)

            except Exception:
                failed_batch_count += 1
                batch_ids = [i.issue_id for i in batch_issues]
                logger.warning(
                    "æ‰¹æ¬¡ %d/%d è°ƒç”¨æˆ–è§£æžå¤±è´¥ï¼ˆäº‰ç‚¹: %sï¼?,
                    batch_idx + 1,
                    len(batches),
                    batch_ids,
                    exc_info=True,
                )

        # æ‰€æœ‰æ‰¹æ¬¡å‡å¤±è´¥ â†?é€€åŒ–ä¸ºå¤±è´¥ç»“æžœï¼ˆåŽŸå§?issue_treeï¼Œå…¨éƒ¨äº‰ç‚¹è¿› unevaluatedï¼?
        if failed_batch_count == len(batches):
            logger.warning("å…¨éƒ¨ %d æ‰¹æ¬¡å‡å¤±è´?, len(batches))
            return IssueImpactRankingResult(
                ranked_issue_tree=inp.issue_tree,
                evaluation_metadata={"failed": True, "created_at": now},
                unevaluated_issue_ids=[i.issue_id for i in issues],
                created_at=now,
            )

        if all_evaluations:
            sample = all_evaluations[0]
            logger.info(
                "é¦–æ¡è¯„ä¼°: issue_id=%s, outcome_impact=%s, importance=%d",
                sample.issue_id,
                sample.outcome_impact,
                sample.importance_score,
            )
        logger.info(
            "å…±æ”¶é›†è¯„ä¼°æ¡ç›? %dï¼?d æ‰¹æˆåŠŸï¼Œ%d æ‰¹å¤±è´¥ï¼‰",
            len(all_evaluations),
            len(batches) - failed_batch_count,
            failed_batch_count,
        )

        try:
            # è§„åˆ™å±‚ï¼šæ ¡éªŒ + å¯ŒåŒ–
Cannot set property. Property setting is supported only on core types in this language mode.
At line:1 char:1
+ [Console]::OutputEncoding=[System.Text.Encoding]::UTF8;
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : InvalidOperation: (:) [], RuntimeException
    + FullyQualifiedErrorId : PropertySetterNotSupportedInConstrainedLanguage
 

 succeeded in 615ms:
"""
æ¡ˆä»¶æå–ç»“æžœ Pydantic schema
Case extraction result Pydantic schemas

ä¸¤å±‚ schemaï¼?
- LLMCaseExtractionOutputï¼šLLM tool_use è¿”å›žçš„åŽŸå§‹ç»“æž„ï¼ˆtool_schema æ¥æºï¼?
- CaseExtractionResultï¼šç»„è£…åŽçš„ç»“æž„åŒ–æå–ç»“æžœï¼Œå¯åºåˆ—åŒ–ä¸º YAML

Two-layer schemas:
- LLMCaseExtractionOutput: Raw LLM tool_use output (source of tool_schema)
- CaseExtractionResult: Assembled structured result, serializable to YAML
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# LLM å·¥å…·è°ƒç”¨ schema â€?tool_use æ¨¡å¼ä¸‹å¼ºåˆ¶ç»“æž„åŒ–è¾“å‡º
# LLM tool schema â€?enforces structured output in tool_use mode
# ---------------------------------------------------------------------------


class LLMExtractedClaim(BaseModel):
    """LLM æå–çš„å•é¡¹è¯‰è®¼è¯·æ±‚ã€?
    A single extracted litigation claim."""

    claim_category: str = Field(
        description="è¯‰è®¼è¯·æ±‚ç±»åž‹ï¼Œå¦‚ï¼šè¿”è¿˜å€Ÿæ¬¾ã€åˆ©æ¯ã€èµ”å¿æŸå¤±ã€è¯‰è®¼è´¹ç”¨ç­‰"
    )
    title: str = Field(description="è¯‰è®¼è¯·æ±‚ç®€çŸ­æ ‡é¢˜ï¼ˆ10å­—ä»¥å†…ï¼‰")
    claim_text: str = Field(description="è¯‰è®¼è¯·æ±‚å®Œæ•´å†…å®¹")


class LLMExtractedEvidence(BaseModel):
    """LLM æå–çš„å•é¡¹è¯æ®æè¿°ã€?
    A single extracted evidence item."""

    description: str = Field(description="è¯æ®å†…å®¹æè¿°")
    document_type: str = Field(
        description=(
            "è¯æ®ç±»åž‹ï¼šdocumentaryï¼ˆä¹¦è¯ï¼‰ã€electronic_dataï¼ˆç”µå­æ•°æ®ï¼‰ã€?
            "audio_visualï¼ˆè§†å¬èµ„æ–™ï¼‰ã€witness_statementï¼ˆè¯äººè¯è¨€ï¼‰ã€?
            "physicalï¼ˆç‰©è¯ï¼‰ã€expert_opinionï¼ˆé‰´å®šæ„è§ï¼‰ã€otherï¼ˆå…¶ä»–ï¼‰"
        )
    )
    submitter: str = Field(description="æäº¤æ–¹ï¼šplaintiffï¼ˆåŽŸå‘Šï¼‰ã€defendantï¼ˆè¢«å‘Šï¼‰æˆ?unknown")


class LLMCaseExtractionOutput(BaseModel):
    """LLM ç»“æž„åŒ–æå–çš„å…¨é‡è¾“å‡ºï¼Œä½œä¸?call_structured_llm çš?tool_schema æ¥æºã€?
    Full LLM structured extraction output, used as tool_schema for call_structured_llm.
    """

    case_type: str = Field(
        description=(
            "æ¡ˆä»¶ç±»åž‹ï¼šcivil_loanï¼ˆæ°‘é—´å€Ÿè´·ï¼‰ã€labor_disputeï¼ˆåŠ³åŠ¨çº çº·ï¼‰ã€?
            "real_estateï¼ˆæˆ¿äº§çº çº·ï¼‰ï¼›æ— æ³•åˆ¤æ–­åˆ™å¡?unknown"
        )
    )
    plaintiff_name: str = Field(description="åŽŸå‘Šå§“åï¼›è‹¥æ–‡ä¸­æ— æ³•ç¡®å®šåˆ™å¡« unknown")
    defendant_names: list[str] = Field(
        description="è¢«å‘Šå§“ååˆ—è¡¨ï¼ˆå¯å¤šäººï¼‰ï¼›è‹¥æ— æ³•ç¡®å®šåˆ™å¡?['unknown']"
    )
    claims: list[LLMExtractedClaim] = Field(description="è¯‰è®¼è¯·æ±‚åˆ—è¡¨ï¼›è‹¥æ–‡ä¸­æ— è¯‰è¯·åˆ™å¡«ç©ºåˆ—è¡¨")
    evidence_list: list[LLMExtractedEvidence] = Field(
        description="æ–‡ä¸­æåŠçš„è¯æ®åˆ—è¡¨ï¼›è‹¥æ— è¯æ®åˆ™å¡«ç©ºåˆ—è¡?
    )
    disputed_amounts: list[str] = Field(
        description=(
            "æ–‡ä¸­å‡ºçŽ°çš„äº‰è®®é‡‘é¢ï¼ˆäººæ°‘å¸å…ƒï¼Œçº¯æ•°å­—å­—ç¬¦ä¸²ï¼Œå¦?'200000'ï¼‰ã€?
            "è‹¥æœ‰å¤šä¸ªä¸ä¸€è‡´çš„é‡‘é¢åˆ™å…¨éƒ¨åˆ—å‡ºï¼›è‹¥æ— åˆ™å¡«ç©ºåˆ—è¡?
        )
    )
    case_summary: str = Field(description="ä¸€ä¸¤å¥è¯æè¿°æœ¬æ¡ˆæ ¸å¿ƒçº çº·ï¼›è‹¥ä¿¡æ¯ä¸è¶³åˆ™å¡?unknown")


# ---------------------------------------------------------------------------
# æå–ç»“æžœå¯¹è±¡ â€?ç»„è£…åŽä¾› YAML åºåˆ—åŒ?
# Extraction result objects â€?assembled for YAML serialization
# ---------------------------------------------------------------------------


class ExtractionParty(BaseModel):
    """å½“äº‹äººæå–ç»“æžœã€‚Extracted party."""

    party_id: str
    name: str  # "unknown" if not determinable


class ExtractionClaim(BaseModel):
    """è¯‰è®¼è¯·æ±‚æå–ç»“æžœã€‚Extracted claim."""

    claim_id: str
    claim_category: str
    title: str
    claim_text: str


class ExtractionEvidence(BaseModel):
    """è¯æ®æå–ç»“æžœã€‚Extracted evidence."""

    source_id: str
    description: str
    document_type: str
    submitter: str  # "plaintiff", "defendant", or "unknown"


class DisputedAmount(BaseModel):
    """äº‰è®®é‡‘é¢ï¼ˆæ”¯æŒå•å€¼å’Œå¤šå€™é€‰å€¼ï¼‰ã€?
    Disputed amount (supports single value and ambiguous multi-value)."""

    amounts: list[str]  # single value list = deterministic; multiple = ambiguous
    is_ambiguous: bool = False


class CaseExtractionResult(BaseModel):
    """å®Œæ•´æ¡ˆä»¶æå–ç»“æžœï¼Œå¯åºåˆ—åŒ–ä¸º YAMLã€?
    Complete case extraction result, serializable to YAML."""

    case_type: str
    plaintiff: ExtractionParty
    defendants: list[ExtractionParty]
    claims: list[ExtractionClaim]
    evidence_list: list[ExtractionEvidence]
    disputed_amount: DisputedAmount
    case_summary: str
    unknown_fields: list[str] = Field(
        default_factory=list,
        description="æ ‡è®°ä¸?unknown çš„å­—æ®µè·¯å¾„åˆ—è¡?,
    )
Cannot set property. Property setting is supported only on core types in this language mode.
At line:1 char:1
+ [Console]::OutputEncoding=[System.Text.Encoding]::UTF8;
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : InvalidOperation: (:) [], RuntimeException
    + FullyQualifiedErrorId : PropertySetterNotSupportedInConstrainedLanguage
 

exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -NoProfile -Command "Get-ChildItem -Path 'engines/case_structuring/case_extractor' -Recurse -File" in C:/Users/david/dev/case-adversarial-engine
 succeeded in 570ms:


    Directory: C:\Users\david\dev\case-adversarial-engine\engines\case_structuring\case_extractor


Mode                 LastWriteTime         Length Name                                                                 
----                 -------------         ------ ----                                                                 
-a----          4/6/2026   8:59 PM          12483 extractor.py                                                         
-a----          4/6/2026   8:59 PM           5303 schemas.py                                                           
-a----          4/6/2026   8:59 PM            878 __init__.py                                                          


    Directory: C:\Users\david\dev\case-adversarial-engine\engines\case_structuring\case_extractor\prompts


Mode                 LastWriteTime         Length Name                                                                 
----                 -------------         ------ ----                                                                 
-a----          4/6/2026   8:59 PM           4893 generic.py                                                           
-a----          4/6/2026   8:59 PM            668 __init__.py                                                          


    Directory: C:\Users\david\dev\case-adversarial-engine\engines\case_structuring\case_extractor\prompts\__pycache__


Mode                 LastWriteTime         Length Name                                                                 
----                 -------------         ------ ----                                                                 
-a----          4/7/2026   9:52 AM           5393 generic.cpython-312.pyc                                              
-a----          4/7/2026   9:52 AM            984 __init__.cpython-312.pyc                                             


    Directory: C:\Users\david\dev\case-adversarial-engine\engines\case_structuring\case_extractor\tests


Mode                 LastWriteTime         Length Name                                                                 
----                 -------------         ------ ----                                                                 
-a----          4/6/2026   8:59 PM          23200 test_extractor.py                                                    
-a----          4/6/2026   8:59 PM              0 __init__.py                                                          


    Directory: C:\Users\david\dev\case-adversarial-engine\engines\case_structuring\case_extractor\tests\__pycache__


Mode                 LastWriteTime         Length Name                                                                 
----                 -------------         ------ ----                                                                 
-a----          4/7/2026   9:52 AM          63560 test_extractor.cpython-312-pytest-9.0.2.pyc                          
-a----          4/7/2026   9:52 AM            197 __init__.cpython-312.pyc                                             


    Directory: C:\Users\david\dev\case-adversarial-engine\engines\case_structuring\case_extractor\__pycache__


Mode                 LastWriteTime         Length Name                                                                 
----                 -------------         ------ ----                                                                 
-a----          4/7/2026   9:52 AM          14016 extractor.cpython-312.pyc                                            
-a----          4/7/2026   9:52 AM           7736 schemas.cpython-312.pyc                                              
-a----          4/7/2026   9:52 AM            973 __init__.cpython-312.pyc                                             


Cannot set property. Property setting is supported only on core types in this language mode.
At line:1 char:1
+ [Console]::OutputEncoding=[System.Text.Encoding]::UTF8;
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : InvalidOperation: (:) [], RuntimeException
    + FullyQualifiedErrorId : PropertySetterNotSupportedInConstrainedLanguage
 

exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -NoProfile -Command "Get-Content 'engines/case_structuring/case_extractor/schemas.py' | Select-Object -First 220" in C:/Users/david/dev/case-adversarial-engine
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -NoProfile -Command "Get-Content 'engines/case_structuring/case_extractor/prompts/generic.py' | Select-Object -First 220" in C:/Users/david/dev/case-adversarial-engine
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -NoProfile -Command "Get-Content 'engines/case_structuring/case_extractor/extractor.py' | Select-Object -First 240" in C:/Users/david/dev/case-adversarial-engine
 succeeded in 617ms:
"""
Generic case extraction prompt â€?works for all case types.
é€šç”¨æ¡ˆä»¶æå– prompt â€?é€‚ç”¨äºŽæ‰€æœ‰æ¡ˆç”±ç±»åž‹ã€?

The LLM discovers the case_type from the document content,
then extracts parties, materials, claims, defenses, and financials.
"""

from __future__ import annotations

SYSTEM_PROMPT = """\
ä½ æ˜¯ä¸€ä½èµ„æ·±ä¸­å›½æ³•å¾‹æ–‡ä¹¦åˆ†æžä¸“å®¶ï¼Œç²¾é€šå„ç±»æ°‘äº‹è¯‰è®¼æ¡ˆä»¶çš„æ–‡ä¹¦ç»“æž„ã€?
You are a senior Chinese legal document analyst, expert in all civil litigation case types.

ä½ çš„ä»»åŠ¡æ˜¯ä»ŽåŽŸå§‹æ³•å¾‹æ–‡ä¹¦ï¼ˆèµ·è¯‰çŠ¶ã€ç­”è¾©çŠ¶ã€è¯æ®æ¸…å•ç­‰ï¼‰ä¸­æå–ç»“æž„åŒ–æ¡ˆä»¶ä¿¡æ¯ã€?
Your task is to extract structured case information from raw legal documents
(complaints, defense statements, evidence lists, etc.).

æå–è§„åˆ™ / Extraction rules:
1. è¯†åˆ«æ¡ˆç”±ç±»åž‹ï¼ˆcivil_loan, labor_dispute, real_estate, æˆ–å…¶ä»–ï¼‰
2. æå–åŽŸå‘Šå’Œè¢«å‘Šä¿¡æ?
3. å°†æ¯ä»½æ–‡ä¹¦æ‹†åˆ†ä¸ºç‹¬ç«‹çš„ææ–™æ¡ç›®ï¼Œæ ‡æ³¨æäº¤æ–¹å’Œæ–‡ä¹¦ç±»åž‹
4. æå–æ‰€æœ‰è¯‰è¯·ï¼ˆåŽŸå‘Šä¸»å¼ ï¼?
5. æå–æ‰€æœ‰æŠ—è¾©ï¼ˆè¢«å‘ŠæŠ—è¾©ï¼?
6. ä»…å€Ÿè´·ç±»æ¡ˆä»¶éœ€è¦æå–è´¢åŠ¡æ•°æ®ï¼ˆloans, repayments, disputed, claim_entriesï¼?
7. ç”Ÿæˆæ¡ˆä»¶æ‘˜è¦ï¼ˆå…³é”®äº‹å®žçš„ç®€è¦åˆ—è¡¨ï¼‰

æ–‡ä¹¦ç±»åž‹å‚è€?/ Document type reference:
identity_documents, bank_transfer_records, loan_note, attorney_contract,
objection_statement, communication_records, labor_contract, termination_notice,
salary_records, social_insurance_records, purchase_contract, lease_contract,
deposit_receipt, payment_records, witness_statement, expert_opinion, other

è¯‰è¯·ç±»åˆ«å‚è€?/ Claim category reference:
è¿”è¿˜å€Ÿæ¬¾, åˆ©æ¯, å¾‹å¸ˆè´? è¿çº¦é‡? è§£é™¤åˆåŒ, ç»æµŽè¡¥å¿é‡? èµ”å¿é‡?
å·¥èµ„å·®é¢, åŒå€å·¥èµ? å®šé‡‘è¿”è¿˜, ç‰©ä¸šäº¤ä»˜, ä¿®ç¼®è´¹ç”¨, ç§Ÿé‡‘, å…¶ä»–

ç¡®ä¿æ‰€æœ?ID å”¯ä¸€ä¸”ç¬¦åˆæ ¼å¼è¦æ±‚ã€?
Ensure all IDs are unique and follow the format requirements.
"""

_EXTRACTION_PROMPT_TEMPLATE = """\
è¯·ä»Žä»¥ä¸‹æ³•å¾‹æ–‡ä¹¦ä¸­æå–å®Œæ•´çš„ç»“æž„åŒ–æ¡ˆä»¶ä¿¡æ¯ã€?
Please extract complete structured case information from the following legal documents.

<documents>
__DOCUMENTS_PLACEHOLDER__
</documents>

è¯·ä¸¥æ ¼æŒ‰ç…§ä»¥ä¸?JSON schema è¾“å‡ºï¼Œä¸è¦é—æ¼ä»»ä½•å­—æ®µï¼š
Output strictly according to the following JSON schema, do not omit any fields:

{
  "case_type": "civil_loan | labor_dispute | real_estate | other",
  "plaintiff": {
    "role": "plaintiff",
    "name": "åŽŸå‘Šå§“å",
    "party_id": ""
  },
  "defendant": {
    "role": "defendant",
    "name": "è¢«å‘Šå§“å",
    "party_id": ""
  },
  "summary": [
    {"label": "å…³é”®äº‹å®žæ ‡ç­¾", "description": "ç®€è¦æè¿?}
  ],
  "materials": [
    {
      "source_id": "src-p-001 æˆ?src-d-001",
      "text": "ææ–™åŽŸæ–‡å†…å®¹",
      "submitter": "plaintiff æˆ?defendant",
      "document_type": "æ–‡ä¹¦ç±»åž‹"
    }
  ],
  "claims": [
    {
      "claim_id": "c-001",
      "claim_category": "è¯‰è¯·ç±»åˆ«",
      "title": "è¯‰è¯·æ ‡é¢˜",
      "claim_text": "è¯‰è¯·è¯¦ç»†æè¿°"
    }
  ],
  "defenses": [
    {
      "defense_id": "d-001",
      "defense_category": "æŠ—è¾©ç±»åˆ«",
      "against_claim_id": "c-001",
      "title": "æŠ—è¾©æ ‡é¢˜",
      "defense_text": "æŠ—è¾©è¯¦ç»†æè¿°"
    }
  ],
  "financials": null
}

æ³¨æ„ / Notes:
- source_id æ ¼å¼ï¼šåŽŸå‘Šææ–™ç”¨ src-p-XXXï¼Œè¢«å‘Šææ–™ç”¨ src-d-XXX
- claim_id æ ¼å¼ï¼šc-001, c-002, ...
- defense_id æ ¼å¼ï¼šd-001, d-002, ...
- financials ä»…åœ¨ case_type ä¸?civil_loan æ—¶å¡«å†™ï¼Œå…¶ä½™æƒ…å†µè®¾ä¸º null
- å¦‚æžœæ–‡ä¹¦ä¸­ä¿¡æ¯ä¸å®Œæ•´ï¼Œå°½å¯èƒ½æå–å·²æœ‰å†…å®¹ï¼Œç¼ºå¤±å­—æ®µç•™ç©ºå­—ç¬¦ä¸²
- å¦‚æžœåªæœ‰èµ·è¯‰çŠ¶æ²¡æœ‰ç­”è¾©çŠ¶ï¼Œdefenses ç•™ç©ºåˆ—è¡¨
"""


def build_extraction_prompt(documents_block: str) -> str:
    """Build the extraction prompt with document text safely inserted.

    Uses placeholder replacement instead of str.format() to avoid
    KeyError / injection when document text contains Python format
    braces like ``{variable}``.
    """
    return _EXTRACTION_PROMPT_TEMPLATE.replace("__DOCUMENTS_PLACEHOLDER__", documents_block)


def format_documents(texts: list[tuple[str, str]]) -> str:
    """Format document texts into XML blocks for the extraction prompt.

    Args:
        texts: List of (filename, content) tuples.

    Returns:
        XML-escaped document blocks.
    """
    blocks = []
    for filename, content in texts:
        safe_filename = (
            filename.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
        )
        safe_content = content.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        blocks.append(f'<document filename="{safe_filename}">\n{safe_content}\n</document>')
    return "\n\n".join(blocks)
Cannot set property. Property setting is supported only on core types in this language mode.
At line:1 char:1
+ [Console]::OutputEncoding=[System.Text.Encoding]::UTF8;
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : InvalidOperation: (:) [], RuntimeException
    + FullyQualifiedErrorId : PropertySetterNotSupportedInConstrainedLanguage
 

 succeeded in 632ms:
"""
Case Extractor schemas â€?Pydantic models for structured case extraction.
æ¡ˆä»¶æå–å™¨æ•°æ®æ¨¡åž?â€?ä»ŽåŽŸå§‹æ³•å¾‹æ–‡æœ¬æå–ç»“æž„åŒ–æ¡ˆä»¶ä¿¡æ¯ã€?

Two model layers:
  1. LLM output models (LLMExtracted*) â€?what the LLM returns
  2. Pipeline-compatible models (Extracted*) â€?what gets written to YAML
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# LLM output models â€?intermediate representation from LLM
# ---------------------------------------------------------------------------


class LLMExtractedParty(BaseModel):
    """LLM æå–çš„å½“äº‹äººä¿¡æ¯ã€?""

    role: str = Field(..., description="plaintiff æˆ?defendant")
    name: str = Field(..., description="å½“äº‹äººå§“å?åç§°")
    party_id: str = Field(default="", description="è‡ªåŠ¨ç”Ÿæˆçš?party ID")


class LLMExtractedMaterial(BaseModel):
    """LLM æå–çš„å•æ¡è¯æ®ææ–™ã€?""

    source_id: str = Field(..., description="ææ–™å”¯ä¸€ ID")
    text: str = Field(..., description="ææ–™æ–‡æœ¬å†…å®¹")
    submitter: str = Field(..., description="æäº¤æ–? plaintiff æˆ?defendant")
    document_type: str = Field(default="other", description="æ–‡ä¹¦ç±»åž‹")


class LLMExtractedClaim(BaseModel):
    """LLM æå–çš„è¯‰è¯·ã€?""

    claim_id: str = Field(..., description="è¯‰è¯· ID, e.g. c-001")
    claim_category: str = Field(..., description="è¯‰è¯·ç±»åˆ«")
    title: str = Field(..., description="è¯‰è¯·æ ‡é¢˜")
    claim_text: str = Field(..., description="è¯‰è¯·è¯¦ç»†æè¿°")


class LLMExtractedDefense(BaseModel):
    """LLM æå–çš„æŠ—è¾©ã€?""

    defense_id: str = Field(..., description="æŠ—è¾© ID, e.g. d-001")
    defense_category: str = Field(..., description="æŠ—è¾©ç±»åˆ«")
    against_claim_id: str = Field(..., description="é’ˆå¯¹çš„è¯‰è¯?ID")
    title: str = Field(..., description="æŠ—è¾©æ ‡é¢˜")
    defense_text: str = Field(..., description="æŠ—è¾©è¯¦ç»†æè¿°")


class LLMExtractedLoan(BaseModel):
    """LLM æå–çš„å€Ÿæ¬¾äº¤æ˜“ã€?""

    tx_id: str
    date: str
    amount: str
    evidence_id: str
    principal_base_contribution: bool = True


class LLMExtractedRepayment(BaseModel):
    """LLM æå–çš„è¿˜æ¬¾äº¤æ˜“ã€?""

    tx_id: str
    date: str
    amount: str
    evidence_id: str
    attributed_to: str | None = None
    attribution_basis: str = ""


class LLMExtractedDisputed(BaseModel):
    """LLM æå–çš„äº‰è®®é‡‘é¢ã€?""

    item_id: str
    amount: str
    dispute_description: str
    plaintiff_attribution: str = ""
    defendant_attribution: str = ""


class LLMExtractedClaimEntry(BaseModel):
    """LLM æå–çš„è¯‰è¯·é‡‘é¢æ¡ç›®ã€?""

    claim_id: str
    claim_type: str
    claimed_amount: str
    evidence_ids: list[str] = Field(default_factory=list)


class LLMExtractedFinancials(BaseModel):
    """LLM æå–çš„è´¢åŠ¡æ•°æ®ï¼ˆä»…å€Ÿè´·ç±»æ¡ˆä»¶ï¼‰ã€?""

    loans: list[LLMExtractedLoan] = Field(default_factory=list)
    repayments: list[LLMExtractedRepayment] = Field(default_factory=list)
    disputed: list[LLMExtractedDisputed] = Field(default_factory=list)
    claim_entries: list[LLMExtractedClaimEntry] = Field(default_factory=list)


class LLMExtractedSummaryRow(BaseModel):
    """LLM æå–çš„æ‘˜è¦è¡Œã€?""

    label: str
    description: str


class LLMExtractionOutput(BaseModel):
    """LLM å®Œæ•´æå–ç»“æžœ â€?call_structured_llm è¿”å›žå?model_validate æ­¤æ¨¡åž‹ã€?""

    case_type: str = Field(..., description="æ¡ˆç”±ç±»åž‹: civil_loan, labor_dispute, real_estate, etc.")
    plaintiff: LLMExtractedParty = Field(..., description="åŽŸå‘Šä¿¡æ¯")
    defendant: LLMExtractedParty = Field(..., description="è¢«å‘Šä¿¡æ¯")
    summary: list[LLMExtractedSummaryRow] = Field(default_factory=list)
    materials: list[LLMExtractedMaterial] = Field(default_factory=list)
    claims: list[LLMExtractedClaim] = Field(default_factory=list)
    defenses: list[LLMExtractedDefense] = Field(default_factory=list)
    financials: LLMExtractedFinancials | None = Field(
        default=None,
        description="è´¢åŠ¡æ•°æ®ï¼Œä»…å€Ÿè´·ç±»æ¡ˆä»¶å¡«å†?,
    )


# ---------------------------------------------------------------------------
# Pipeline-compatible output â€?what gets serialized to YAML
# ---------------------------------------------------------------------------


class ExtractedCase(BaseModel):
    """Pipeline-compatible case structure â€?matches _load_case() requirements.

    Required keys: case_id, case_slug, case_type, parties, materials, claims, defenses.
    """

    case_id: str
    case_slug: str
    case_type: str
    parties: dict[str, dict[str, str]]
    summary: list[list[str]] = Field(default_factory=list)
    materials: dict[str, list[dict[str, Any]]]
    claims: list[dict[str, str]]
    defenses: list[dict[str, str]]
    financials: dict[str, Any] | None = None
    _missing_fields: list[str] = []

    @property
    def missing_fields(self) -> list[str]:
        """Fields the LLM could not extract â€?user should fill manually."""
        return self._missing_fields
Cannot set property. Property setting is supported only on core types in this language mode.
At line:1 char:1
+ [Console]::OutputEncoding=[System.Text.Encoding]::UTF8;
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : InvalidOperation: (:) [], RuntimeException
    + FullyQualifiedErrorId : PropertySetterNotSupportedInConstrainedLanguage
 

 succeeded in 651ms:
"""
CaseExtractor â€?extract structured case data from raw Chinese legal documents.
æ¡ˆä»¶æå–å™?â€?ä»ŽåŽŸå§‹ä¸­æ–‡æ³•å¾‹æ–‡ä¹¦è‡ªåŠ¨æå–ç»“æž„åŒ–æ¡ˆä»¶ YAMLã€?

Two-step process:
  1. LLM extracts structured JSON (parties, materials, claims, defenses, financials)
  2. Post-process into pipeline-compatible YAML format and validate

Usage::

    from engines.case_structuring.case_extractor import CaseExtractor

    extractor = CaseExtractor(llm_client=client, model="claude-sonnet-4-6")
    result = await extractor.extract([("complaint.txt", text1), ("defense.txt", text2)])
    yaml_str = extractor.to_yaml(result)
"""

from __future__ import annotations

import logging
import re
import uuid
from typing import TYPE_CHECKING, Any

import yaml

if TYPE_CHECKING:
    from engines.shared.models import LLMClient

from engines.shared.json_utils import _extract_json_object
from engines.shared.structured_output import call_structured_llm

from .prompts import PROMPT_REGISTRY
from .schemas import (
    ExtractedCase,
    LLMExtractionOutput,
)

logger = logging.getLogger(__name__)

# Tool schema for structured output â€?wraps LLMExtractionOutput
_TOOL_SCHEMA: dict = LLMExtractionOutput.model_json_schema()


def _slugify(text: str) -> str:
    """Convert text to a URL-friendly slug."""
    # Keep alphanumeric and hyphens, collapse multiple hyphens
    slug = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff]+", "-", text.lower()).strip("-")
    # If mostly Chinese, generate a short hash-based slug
    if not re.search(r"[a-zA-Z]", slug):
        return uuid.uuid4().hex[:12]
    # Remove Chinese chars for the slug
    slug = re.sub(r"[\u4e00-\u9fff]+", "", slug).strip("-")
    return slug[:40] if slug else uuid.uuid4().hex[:12]


class CaseExtractor:
    """Extract structured case information from raw legal documents.

    Args:
        llm_client: LLM client implementing create_message protocol.
        model:      Model ID for extraction (default: balanced tier).
        temperature: LLM temperature (default 0.0 for deterministic output).
        max_tokens:  Max output tokens (default 8192 â€?extraction can be long).
        max_retries:  Max LLM call retries (default 3).
    """

    def __init__(
        self,
        llm_client: "LLMClient",
        *,
        model: str = "claude-sonnet-4-6",
        temperature: float = 0.0,
        max_tokens: int = 8192,
        max_retries: int = 3,
    ) -> None:
        self._llm = llm_client
        self._model = model
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._max_retries = max_retries

    async def extract(
        self,
        documents: list[tuple[str, str]],
        *,
        case_id: str | None = None,
        prompt_name: str = "generic",
    ) -> ExtractedCase:
        """Extract structured case data from raw documents.

        Args:
            documents:   List of (filename, text_content) tuples.
            case_id:     Optional case ID override. Auto-generated if None.
            prompt_name: Prompt module to use (default: "generic").

        Returns:
            ExtractedCase ready for YAML serialization.

        Raises:
            ValueError: If documents list is empty or prompt not found.
            RuntimeError: If LLM call fails after all retries.
        """
        if not documents:
            raise ValueError("At least one document is required for extraction")

        prompt_module = self._load_prompt(prompt_name)

        # Format documents into XML blocks
        doc_block = prompt_module.format_documents(documents)
        system = prompt_module.SYSTEM_PROMPT
        user = prompt_module.build_extraction_prompt(doc_block)

        # Call LLM with structured output
        raw_data = await self._call_llm(system, user)

        # Parse and validate LLM output
        llm_output = LLMExtractionOutput.model_validate(raw_data)

        # Convert to pipeline-compatible format
        return self._to_extracted_case(llm_output, case_id=case_id)

    async def _call_llm(self, system: str, user: str) -> dict:
        """Call LLM with structured output, falling back to text extraction."""
        if getattr(self._llm, "_supports_structured_output", False):
            return await call_structured_llm(
                self._llm,
                system=system,
                user=user,
                model=self._model,
                tool_name="extract_case",
                tool_description="ä»Žæ³•å¾‹æ–‡ä¹¦ä¸­æå–ç»“æž„åŒ–æ¡ˆä»¶ä¿¡æ?/ Extract structured case info from legal documents",
                tool_schema=_TOOL_SCHEMA,
                temperature=self._temperature,
                max_tokens=self._max_tokens,
                max_retries=self._max_retries,
            )
        # Fallback: free-form text â†?JSON extraction
        from engines.shared.llm_utils import call_llm_with_retry

        raw = await call_llm_with_retry(
            self._llm,
            system=system,
            user=user,
            model=self._model,
            temperature=self._temperature,
            max_tokens=self._max_tokens,
            max_retries=self._max_retries,
        )
        return _extract_json_object(raw)

    def _to_extracted_case(
        self,
        llm: LLMExtractionOutput,
        *,
        case_id: str | None = None,
    ) -> ExtractedCase:
        """Convert LLM output to pipeline-compatible ExtractedCase."""
        missing_fields: list[str] = []

        # Generate IDs
        p_name = llm.plaintiff.name or "åŽŸå‘Š"
        d_name = llm.defendant.name or "è¢«å‘Š"
        slug = _slugify(f"{p_name}-v-{d_name}")
        auto_case_id = case_id or f"case-{llm.case_type}-{uuid.uuid4().hex[:8]}"
        p_id = llm.plaintiff.party_id or f"party-plaintiff-{_slugify(p_name) or 'p'}"
        d_id = llm.defendant.party_id or f"party-defendant-{_slugify(d_name) or 'd'}"

        # Check for missing fields
        if not llm.plaintiff.name:
            missing_fields.append("plaintiff.name")
        if not llm.defendant.name:
            missing_fields.append("defendant.name")
        if not llm.claims:
            missing_fields.append("claims")
        if not llm.materials:
            missing_fields.append("materials")

        # Build parties
        parties = {
            "plaintiff": {"party_id": p_id, "name": p_name},
            "defendant": {"party_id": d_id, "name": d_name},
        }

        # Build summary
        summary = [[row.label, row.description] for row in llm.summary]

        # Build materials grouped by submitter
        p_materials: list[dict[str, Any]] = []
        d_materials: list[dict[str, Any]] = []
        for m in llm.materials:
            entry: dict[str, Any] = {
                "source_id": m.source_id,
                "text": m.text,
                "metadata": {
                    "document_type": m.document_type,
                    "submitter": m.submitter,
                    "status": "admitted_for_discussion",
                },
            }
            if m.submitter == "defendant":
                d_materials.append(entry)
            else:
                p_materials.append(entry)

        materials: dict[str, list[dict[str, Any]]] = {
            "plaintiff": p_materials,
            "defendant": d_materials,
        }

        # Build claims
        claims = [
            {
                "claim_id": c.claim_id,
                "claim_category": c.claim_category,
                "title": c.title,
                "claim_text": c.claim_text,
            }
            for c in llm.claims
        ]

        # Build defenses
        defenses = [
            {
                "defense_id": d.defense_id,
                "defense_category": d.defense_category,
                "against_claim_id": d.against_claim_id,
                "title": d.title,
                "defense_text": d.defense_text,
            }
            for d in llm.defenses
        ]

        # Build financials (only for loan cases)
        financials: dict[str, Any] | None = None
        if llm.financials and llm.case_type == "civil_loan":
            financials = {
                "loans": [loan.model_dump() for loan in llm.financials.loans],
                "repayments": [r.model_dump() for r in llm.financials.repayments],
                "disputed": [d.model_dump() for d in llm.financials.disputed],
Cannot set property. Property setting is supported only on core types in this language mode.
At line:1 char:1
+ [Console]::OutputEncoding=[System.Text.Encoding]::UTF8;
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : InvalidOperation: (:) [], RuntimeException
    + FullyQualifiedErrorId : PropertySetterNotSupportedInConstrainedLanguage
 

2026-04-07T11:30:40.582032Z ERROR codex_core::tools::router: error=`"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -NoProfile -Command "(Select-String -Path 'tests\\**\\*.py','engines\\**\\tests\\*.py' -Pattern 'civil_loan|labor_dispute|real_estate' | Measure-Object).Count"` rejected: blocked by policy
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -NoProfile -Command "(Select-String -Path 'tests\\**\\*.py','engines\\**\\tests\\*.py' -Pattern 'civil_loan|labor_dispute|real_estate' | Measure-Object).Count" in C:/Users/david/dev/case-adversarial-engine
 declined in 0ms:
`"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -NoProfile -Command "(Select-String -Path 'tests\\**\\*.py','engines\\**\\tests\\*.py' -Pattern 'civil_loan|labor_dispute|real_estate' | Measure-Object).Count"` rejected: blocked by policy
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -NoProfile -Command "Select-String -Path 'engines\\report_generation\\v3\\tests\\*.py' -Pattern 'civil_loan|labor_dispute|real_estate'" in C:/Users/david/dev/case-adversarial-engine
 succeeded in 701ms:

engines\report_generation\v3\tests\test_civil_loan_acceptance.py:1:"""Phase 3a: civil_loan case type structural 
validation against v3 acceptance matrix.
engines\report_generation\v3\tests\test_civil_loan_acceptance.py:9:  6. Amount calculation section present and correct 
(civil_loan HAS this)
engines\report_generation\v3\tests\test_civil_loan_acceptance.py:60:_CIVIL_LOAN_EVIDENCE_IDS = {
engines\report_generation\v3\tests\test_civil_loan_acceptance.py:69:def _make_civil_loan_report(
engines\report_generation\v3\tests\test_civil_loan_acceptance.py:77:    """Build a realistic civil_loan 
FourLayerReport for acceptance testing.
engines\report_generation\v3\tests\test_civil_loan_acceptance.py:82:    - Amount calculation (civil_loan always has 
this)
engines\report_generation\v3\tests\test_civil_loan_acceptance.py:406:    # Amount calculation (civil_loan specific!)
engines\report_generation\v3\tests\test_civil_loan_acceptance.py:455:    "case_type": "civil_loan",
engines\report_generation\v3\tests\test_civil_loan_acceptance.py:469:    """All 10 render contract rules must pass for 
civil_loan."""
engines\report_generation\v3\tests\test_civil_loan_acceptance.py:473:    def 
test_civil_loan_md_passes_full_render_contract(self, _mock_redact):
engines\report_generation\v3\tests\test_civil_loan_acceptance.py:475:        report = _make_civil_loan_report()
engines\report_generation\v3\tests\test_civil_loan_acceptance.py:485:            content, 
evidence_ids=_CIVIL_LOAN_EVIDENCE_IDS
engines\report_generation\v3\tests\test_civil_loan_acceptance.py:494:        report = _make_civil_loan_report()
engines\report_generation\v3\tests\test_civil_loan_acceptance.py:507:        report = _make_civil_loan_report()
engines\report_generation\v3\tests\test_civil_loan_acceptance.py:518:        report = _make_civil_loan_report()
engines\report_generation\v3\tests\test_civil_loan_acceptance.py:535:    """DOCX render contract subset must pass for 
civil_loan."""
engines\report_generation\v3\tests\test_civil_loan_acceptance.py:537:    def test_civil_loan_docx_passes_lint(self):
engines\report_generation\v3\tests\test_civil_loan_acceptance.py:538:        """Generate DOCX for civil_loan and 
verify render contract."""
engines\report_generation\v3\tests\test_civil_loan_acceptance.py:545:        report = _make_civil_loan_report()
engines\report_generation\v3\tests\test_civil_loan_acceptance.py:569:    def 
test_civil_loan_fallback_ratio_below_threshold(self, _mock_redact):
engines\report_generation\v3\tests\test_civil_loan_acceptance.py:571:        report = _make_civil_loan_report()
engines\report_generation\v3\tests\test_civil_loan_acceptance.py:587:        report = _make_civil_loan_report()
engines\report_generation\v3\tests\test_civil_loan_acceptance.py:612:                f"Fallback sections found (should 
be 0 for civil_loan with full data): "
engines\report_generation\v3\tests\test_civil_loan_acceptance.py:628:        report = _make_civil_loan_report()
engines\report_generation\v3\tests\test_civil_loan_acceptance.py:662:        report = _make_civil_loan_report()
engines\report_generation\v3\tests\test_civil_loan_acceptance.py:677:                assert full_ref in 
_CIVIL_LOAN_EVIDENCE_IDS or ref in _CIVIL_LOAN_EVIDENCE_IDS, (
engines\report_generation\v3\tests\test_civil_loan_acceptance.py:688:    """civil_loan must have an amount calculation 
section."""
engines\report_generation\v3\tests\test_civil_loan_acceptance.py:693:        report = 
_make_civil_loan_report(include_amount=True)
engines\report_generation\v3\tests\test_civil_loan_acceptance.py:704:        report = 
_make_civil_loan_report(include_amount=True)
engines\report_generation\v3\tests\test_civil_loan_acceptance.py:718:        report = 
_make_civil_loan_report(include_amount=False)
engines\report_generation\v3\tests\test_civil_loan_acceptance.py:741:        report = _make_civil_loan_report()
engines\report_generation\v3\tests\test_civil_loan_acceptance.py:776:        report = _make_civil_loan_report()
engines\report_generation\v3\tests\test_civil_loan_acceptance.py:786:        report = _make_civil_loan_report()
engines\report_generation\v3\tests\test_civil_loan_acceptance.py:805:        report = 
_make_civil_loan_report(perspective="neutral")
engines\report_generation\v3\tests\test_civil_loan_acceptance.py:817:        report = 
_make_civil_loan_report(perspective="neutral")
engines\report_generation\v3\tests\test_civil_loan_acceptance.py:833:        report = 
_make_civil_loan_report(perspective="neutral")
engines\report_generation\v3\tests\test_civil_loan_acceptance.py:852:# Additional structural checks (civil_loan 
specific)
engines\report_generation\v3\tests\test_civil_loan_acceptance.py:857:    """Structural integrity checks specific to 
civil_loan case type."""
engines\report_generation\v3\tests\test_civil_loan_acceptance.py:863:        report = _make_civil_loan_report()
engines\report_generation\v3\tests\test_civil_loan_acceptance.py:875:    def 
test_issue_map_has_civil_loan_issues(self, _mock_redact):
engines\report_generation\v3\tests\test_civil_loan_acceptance.py:876:        """Issue map must contain 
civil_loan-specific issues."""
engines\report_generation\v3\tests\test_civil_loan_acceptance.py:877:        report = _make_civil_loan_report()
engines\report_generation\v3\tests\test_civil_loan_acceptance.py:888:        report = _make_civil_loan_report()
engines\report_generation\v3\tests\test_civil_loan_acceptance.py:900:        report = _make_civil_loan_report()
engines\report_generation\v3\tests\test_civil_loan_acceptance.py:911:        report = _make_civil_loan_report()
engines\report_generation\v3\tests\test_civil_loan_acceptance.py:922:        report = _make_civil_loan_report()
engines\report_generation\v3\tests\test_civil_loan_acceptance.py:932:        report = _make_civil_loan_report()
engines\report_generation\v3\tests\test_labor_dispute_acceptance.py:1:"""Phase 3b: labor_dispute case type structural 
validation against v3 acceptance matrix.
engines\report_generation\v3\tests\test_labor_dispute_acceptance.py:9:  6. Amount calculation handled correctly 
(labor_dispute HAS wage/compensation calc)
engines\report_generation\v3\tests\test_labor_dispute_acceptance.py:13:Key differences from civil_loan:
engines\report_generation\v3\tests\test_labor_dispute_acceptance.py:67:_LABOR_DISPUTE_EVIDENCE_IDS = {
engines\report_generation\v3\tests\test_labor_dispute_acceptance.py:79:def _make_labor_dispute_report(
engines\report_generation\v3\tests\test_labor_dispute_acceptance.py:87:    """Build a realistic labor_dispute 
FourLayerReport for acceptance testing.
engines\report_generation\v3\tests\test_labor_dispute_acceptance.py:527:    # Amount calculation (labor_dispute: 
compensation formula)
engines\report_generation\v3\tests\test_labor_dispute_acceptance.py:576:    "case_type": "labor_dispute",
engines\report_generation\v3\tests\test_labor_dispute_acceptance.py:590:    """All 10 render contract rules must pass 
for labor_dispute."""
engines\report_generation\v3\tests\test_labor_dispute_acceptance.py:594:    def 
test_labor_dispute_md_passes_full_render_contract(self, _mock_redact):
engines\report_generation\v3\tests\test_labor_dispute_acceptance.py:596:        report = _make_labor_dispute_report()
engines\report_generation\v3\tests\test_labor_dispute_acceptance.py:606:            content, 
evidence_ids=_LABOR_DISPUTE_EVIDENCE_IDS
engines\report_generation\v3\tests\test_labor_dispute_acceptance.py:615:        report = _make_labor_dispute_report()
engines\report_generation\v3\tests\test_labor_dispute_acceptance.py:628:        report = _make_labor_dispute_report()
engines\report_generation\v3\tests\test_labor_dispute_acceptance.py:639:        report = _make_labor_dispute_report()
engines\report_generation\v3\tests\test_labor_dispute_acceptance.py:656:    """DOCX render contract subset must pass 
for labor_dispute."""
engines\report_generation\v3\tests\test_labor_dispute_acceptance.py:658:    def 
test_labor_dispute_docx_passes_lint(self):
engines\report_generation\v3\tests\test_labor_dispute_acceptance.py:659:        """Generate DOCX for labor_dispute and 
verify render contract."""
engines\report_generation\v3\tests\test_labor_dispute_acceptance.py:666:        report = _make_labor_dispute_report()
engines\report_generation\v3\tests\test_labor_dispute_acceptance.py:690:    def 
test_labor_dispute_fallback_ratio_below_threshold(self, _mock_redact):
engines\report_generation\v3\tests\test_labor_dispute_acceptance.py:692:        report = _make_labor_dispute_report()
engines\report_generation\v3\tests\test_labor_dispute_acceptance.py:708:        report = _make_labor_dispute_report()
engines\report_generation\v3\tests\test_labor_dispute_acceptance.py:733:                f"Fallback sections found 
(should be 0 for labor_dispute with full data): "
engines\report_generation\v3\tests\test_labor_dispute_acceptance.py:749:        report = _make_labor_dispute_report()
engines\report_generation\v3\tests\test_labor_dispute_acceptance.py:783:        report = _make_labor_dispute_report()
engines\report_generation\v3\tests\test_labor_dispute_acceptance.py:795:                assert full_ref in 
_LABOR_DISPUTE_EVIDENCE_IDS or ref in _LABOR_DISPUTE_EVIDENCE_IDS, (
engines\report_generation\v3\tests\test_labor_dispute_acceptance.py:806:    """labor_dispute has wage/compensation 
calculations (N/2N formula)."""
engines\report_generation\v3\tests\test_labor_dispute_acceptance.py:812:        report = 
_make_labor_dispute_report(include_amount=True)
engines\report_generation\v3\tests\test_labor_dispute_acceptance.py:823:        report = 
_make_labor_dispute_report(include_amount=True)
engines\report_generation\v3\tests\test_labor_dispute_acceptance.py:841:        report = 
_make_labor_dispute_report(include_amount=False)
engines\report_generation\v3\tests\test_labor_dispute_acceptance.py:855:        report = 
_make_labor_dispute_report(include_amount=True)
engines\report_generation\v3\tests\test_labor_dispute_acceptance.py:860:        # Should NOT contain civil_loan terms
engines\report_generation\v3\tests\test_labor_dispute_acceptance.py:876:        report = _make_labor_dispute_report()
engines\report_generation\v3\tests\test_labor_dispute_acceptance.py:911:        report = _make_labor_dispute_report()
engines\report_generation\v3\tests\test_labor_dispute_acceptance.py:921:        report = _make_labor_dispute_report()
engines\report_generation\v3\tests\test_labor_dispute_acceptance.py:940:        report = 
_make_labor_dispute_report(perspective="neutral")
engines\report_generation\v3\tests\test_labor_dispute_acceptance.py:952:        report = 
_make_labor_dispute_report(perspective="neutral")
engines\report_generation\v3\tests\test_labor_dispute_acceptance.py:967:        report = 
_make_labor_dispute_report(perspective="neutral")
engines\report_generation\v3\tests\test_labor_dispute_acceptance.py:985:# Additional structural checks (labor_dispute 
specific)
engines\report_generation\v3\tests\test_labor_dispute_acceptance.py:990:    """Structural integrity checks specific to 
labor_dispute case type."""
engines\report_generation\v3\tests\test_labor_dispute_acceptance.py:996:        report = _make_labor_dispute_report()
engines\report_generation\v3\tests\test_labor_dispute_acceptance.py:1008:    def 
test_issue_map_has_labor_dispute_issues(self, _mock_redact):
engines\report_generation\v3\tests\test_labor_dispute_acceptance.py:1010:        report = _make_labor_dispute_report()
engines\report_generation\v3\tests\test_labor_dispute_acceptance.py:1023:        report = _make_labor_dispute_report()
engines\report_generation\v3\tests\test_labor_dispute_acceptance.py:1035:        report = _make_labor_dispute_report()
engines\report_generation\v3\tests\test_labor_dispute_acceptance.py:1046:        report = _make_labor_dispute_report()
engines\report_generation\v3\tests\test_labor_dispute_acceptance.py:1057:        report = _make_labor_dispute_report()
engines\report_generation\v3\tests\test_labor_dispute_acceptance.py:1068:    def 
test_no_civil_loan_terms_in_report(self, _mock_redact):
engines\report_generation\v3\tests\test_labor_dispute_acceptance.py:1069:        """Labor dispute report should not 
contain civil_loan-specific terms."""
engines\report_generation\v3\tests\test_labor_dispute_acceptance.py:1070:        report = _make_labor_dispute_report()
engines\report_generation\v3\tests\test_labor_dispute_acceptance.py:1075:        # These are civil_loan-specific terms 
that should NOT appear
engines\report_generation\v3\tests\test_labor_dispute_acceptance.py:1081:        report = _make_labor_dispute_report()
engines\report_generation\v3\tests\test_labor_dispute_acceptance.py:1092:        report = _make_labor_dispute_report()
engines\report_generation\v3\tests\test_labor_dispute_acceptance.py:1098:        assert card_ids == 
_LABOR_DISPUTE_EVIDENCE_IDS
engines\report_generation\v3\tests\test_labor_dispute_acceptance.py:1102:        report = _make_labor_dispute_report()
engines\report_generation\v3\tests\test_multi_case_integration.py:26:from 
engines.report_generation.v3.tests.test_civil_loan_acceptance import (
engines\report_generation\v3\tests\test_multi_case_integration.py:27:    _CASE_DATA as CIVIL_LOAN_CASE_DATA,
engines\report_generation\v3\tests\test_multi_case_integration.py:28:    _make_civil_loan_report,
engines\report_generation\v3\tests\test_multi_case_integration.py:30:from 
engines.report_generation.v3.tests.test_labor_dispute_acceptance import (
engines\report_generation\v3\tests\test_multi_case_integration.py:31:    _CASE_DATA as LABOR_DISPUTE_CASE_DATA,
engines\report_generation\v3\tests\test_multi_case_integration.py:32:    _make_labor_dispute_report,
engines\report_generation\v3\tests\test_multi_case_integration.py:34:from 
engines.report_generation.v3.tests.test_real_estate_acceptance import (
engines\report_generation\v3\tests\test_multi_case_integration.py:35:    _CASE_DATA as REAL_ESTATE_CASE_DATA,
engines\report_generation\v3\tests\test_multi_case_integration.py:36:    _make_real_estate_report,
engines\report_generation\v3\tests\test_multi_case_integration.py:42:_CIVIL_LOAN_EXCLUSIVE_TERMS = ["借款合意", 
"借款本金", "还款义务"]
engines\report_generation\v3\tests\test_multi_case_integration.py:43:_LABOR_DISPUTE_EXCLUSIVE_TERMS = ["劳动仲裁", 
"工资报酬", "劳动合同"]
engines\report_generation\v3\tests\test_multi_case_integration.py:44:_REAL_ESTATE_EXCLUSIVE_TERMS = ["房屋买卖", 
"产权过户", "网签备案"]
engines\report_generation\v3\tests\test_multi_case_integration.py:69:            ("civil_loan", 
_make_civil_loan_report, CIVIL_LOAN_CASE_DATA),
engines\report_generation\v3\tests\test_multi_case_integration.py:70:            ("labor_dispute", 
_make_labor_dispute_report, LABOR_DISPUTE_CASE_DATA),
engines\report_generation\v3\tests\test_multi_case_integration.py:71:            ("real_estate", 
_make_real_estate_report, REAL_ESTATE_CASE_DATA),
engines\report_generation\v3\tests\test_multi_case_integration.py:73:        ids=["civil_loan", "labor_dispute", 
"real_estate"],
engines\report_generation\v3\tests\test_multi_case_integration.py:85:            ("civil_loan", 
_make_civil_loan_report, CIVIL_LOAN_CASE_DATA),
engines\report_generation\v3\tests\test_multi_case_integration.py:86:            ("labor_dispute", 
_make_labor_dispute_report, LABOR_DISPUTE_CASE_DATA),
engines\report_generation\v3\tests\test_multi_case_integration.py:87:            ("real_estate", 
_make_real_estate_report, REAL_ESTATE_CASE_DATA),
engines\report_generation\v3\tests\test_multi_case_integration.py:89:        ids=["civil_loan", "labor_dispute", 
"real_estate"],
engines\report_generation\v3\tests\test_multi_case_integration.py:103:            ("civil_loan", 
_make_civil_loan_report, CIVIL_LOAN_CASE_DATA),
engines\report_generation\v3\tests\test_multi_case_integration.py:104:            ("labor_dispute", 
_make_labor_dispute_report, LABOR_DISPUTE_CASE_DATA),
engines\report_generation\v3\tests\test_multi_case_integration.py:105:            ("real_estate", 
_make_real_estate_report, REAL_ESTATE_CASE_DATA),
engines\report_generation\v3\tests\test_multi_case_integration.py:107:        ids=["civil_loan", "labor_dispute", 
"real_estate"],
engines\report_generation\v3\tests\test_multi_case_integration.py:131:    def test_civil_loan_has_no_labor_terms(self):
engines\report_generation\v3\tests\test_multi_case_integration.py:132:        content = 
_generate_md(_make_civil_loan_report(), CIVIL_LOAN_CASE_DATA)
engines\report_generation\v3\tests\test_multi_case_integration.py:133:        for term in 
_LABOR_DISPUTE_EXCLUSIVE_TERMS:
engines\report_generation\v3\tests\test_multi_case_integration.py:135:                f"civil_loan report contains 
labor_dispute term: '{term}'"
engines\report_generation\v3\tests\test_multi_case_integration.py:138:    def 
test_civil_loan_has_no_real_estate_terms(self):
engines\report_generation\v3\tests\test_multi_case_integration.py:139:        content = 
_generate_md(_make_civil_loan_report(), CIVIL_LOAN_CASE_DATA)
engines\report_generation\v3\tests\test_multi_case_integration.py:140:        for term in _REAL_ESTATE_EXCLUSIVE_TERMS:
engines\report_generation\v3\tests\test_multi_case_integration.py:142:                f"civil_loan report contains 
real_estate term: '{term}'"
engines\report_generation\v3\tests\test_multi_case_integration.py:145:    def 
test_labor_dispute_has_no_civil_loan_terms(self):
engines\report_generation\v3\tests\test_multi_case_integration.py:147:            _make_labor_dispute_report(), 
LABOR_DISPUTE_CASE_DATA
engines\report_generation\v3\tests\test_multi_case_integration.py:149:        for term in _CIVIL_LOAN_EXCLUSIVE_TERMS:
engines\report_generation\v3\tests\test_multi_case_integration.py:151:                f"labor_dispute report contains 
civil_loan term: '{term}'"
engines\report_generation\v3\tests\test_multi_case_integration.py:154:    def 
test_labor_dispute_has_no_real_estate_terms(self):
engines\report_generation\v3\tests\test_multi_case_integration.py:156:            _make_labor_dispute_report(), 
LABOR_DISPUTE_CASE_DATA
engines\report_generation\v3\tests\test_multi_case_integration.py:158:        for term in _REAL_ESTATE_EXCLUSIVE_TERMS:
engines\report_generation\v3\tests\test_multi_case_integration.py:160:                f"labor_dispute report contains 
real_estate term: '{term}'"
engines\report_generation\v3\tests\test_multi_case_integration.py:163:    def 
test_real_estate_has_no_civil_loan_terms(self):
engines\report_generation\v3\tests\test_multi_case_integration.py:165:            _make_real_estate_report(), 
REAL_ESTATE_CASE_DATA
engines\report_generation\v3\tests\test_multi_case_integration.py:167:        for term in _CIVIL_LOAN_EXCLUSIVE_TERMS:
engines\report_generation\v3\tests\test_multi_case_integration.py:169:                f"real_estate report contains 
civil_loan term: '{term}'"
engines\report_generation\v3\tests\test_multi_case_integration.py:172:    def 
test_real_estate_has_no_labor_terms(self):
engines\report_generation\v3\tests\test_multi_case_integration.py:174:            _make_real_estate_report(), 
REAL_ESTATE_CASE_DATA
engines\report_generation\v3\tests\test_multi_case_integration.py:176:        for term in 
_LABOR_DISPUTE_EXCLUSIVE_TERMS:
engines\report_generation\v3\tests\test_multi_case_integration.py:178:                f"real_estate report contains 
labor_dispute term: '{term}'"
engines\report_generation\v3\tests\test_multi_case_integration.py:192:        ["civil_loan", "labor_dispute", 
"real_estate"],
engines\report_generation\v3\tests\test_multi_case_integration.py:204:        ["civil_loan", "labor_dispute", 
"real_estate"],
engines\report_generation\v3\tests\test_multi_case_integration.py:216:        ["civil_loan", "labor_dispute", 
"real_estate"],
engines\report_generation\v3\tests\test_multi_case_integration.py:230:        ["civil_loan", "labor_dispute", 
"real_estate"],
engines\report_generation\v3\tests\test_multi_case_integration.py:243:        ["civil_loan", "labor_dispute", 
"real_estate"],
engines\report_generation\v3\tests\test_multi_case_integration.py:256:        for case_type in ["civil_loan", 
"labor_dispute", "real_estate"]:
engines\report_generation\v3\tests\test_real_estate_acceptance.py:1:"""Phase 3c: real_estate case type structural 
validation against v3 acceptance matrix.
engines\report_generation\v3\tests\test_real_estate_acceptance.py:9:  6. Amount calculation handled correctly 
(real_estate HAS deposit/contract price/penalty)
engines\report_generation\v3\tests\test_real_estate_acceptance.py:13:Key differences from civil_loan and labor_dispute:
engines\report_generation\v3\tests\test_real_estate_acceptance.py:72:_REAL_ESTATE_EVIDENCE_IDS = {
engines\report_generation\v3\tests\test_real_estate_acceptance.py:83:def _make_real_estate_report(
engines\report_generation\v3\tests\test_real_estate_acceptance.py:91:    """Build a realistic real_estate 
FourLayerReport for acceptance testing.
engines\report_generation\v3\tests\test_real_estate_acceptance.py:526:    # Amount calculation (real_estate specific: 
deposit, contract price, penalty, appraisal)
engines\report_generation\v3\tests\test_real_estate_acceptance.py:575:    "case_type": "real_estate",
engines\report_generation\v3\tests\test_real_estate_acceptance.py:589:    """All 10 render contract rules must pass 
for real_estate."""
engines\report_generation\v3\tests\test_real_estate_acceptance.py:593:    def 
test_real_estate_md_passes_full_render_contract(self, _mock_redact):
engines\report_generation\v3\tests\test_real_estate_acceptance.py:595:        report = _make_real_estate_report()
engines\report_generation\v3\tests\test_real_estate_acceptance.py:604:            content, 
evidence_ids=_REAL_ESTATE_EVIDENCE_IDS
engines\report_generation\v3\tests\test_real_estate_acceptance.py:612:        report = _make_real_estate_report()
engines\report_generation\v3\tests\test_real_estate_acceptance.py:625:        report = _make_real_estate_report()
engines\report_generation\v3\tests\test_real_estate_acceptance.py:636:        report = _make_real_estate_report()
engines\report_generation\v3\tests\test_real_estate_acceptance.py:653:    """DOCX render contract subset must pass for 
real_estate."""
engines\report_generation\v3\tests\test_real_estate_acceptance.py:655:    def test_real_estate_docx_passes_lint(self):
engines\report_generation\v3\tests\test_real_estate_acceptance.py:656:        """Generate DOCX for real_estate and 
verify render contract."""
engines\report_generation\v3\tests\test_real_estate_acceptance.py:663:        report = _make_real_estate_report()
engines\report_generation\v3\tests\test_real_estate_acceptance.py:687:    def 
test_real_estate_fallback_ratio_below_threshold(self, _mock_redact):
engines\report_generation\v3\tests\test_real_estate_acceptance.py:689:        report = _make_real_estate_report()
engines\report_generation\v3\tests\test_real_estate_acceptance.py:705:        report = _make_real_estate_report()
engines\report_generation\v3\tests\test_real_estate_acceptance.py:728:                f"Fallback sections found 
(should be 0 for real_estate with full data): "
engines\report_generation\v3\tests\test_real_estate_acceptance.py:744:        report = _make_real_estate_report()
engines\report_generation\v3\tests\test_real_estate_acceptance.py:777:        report = _make_real_estate_report()
engines\report_generation\v3\tests\test_real_estate_acceptance.py:788:                assert full_ref in 
_REAL_ESTATE_EVIDENCE_IDS or ref in _REAL_ESTATE_EVIDENCE_IDS, (
engines\report_generation\v3\tests\test_real_estate_acceptance.py:799:    """real_estate has 
deposit/penalty/appraisal-based calculations."""
engines\report_generation\v3\tests\test_real_estate_acceptance.py:805:        report = 
_make_real_estate_report(include_amount=True)
engines\report_generation\v3\tests\test_real_estate_acceptance.py:814:    def 
test_amount_calculation_has_real_estate_fields(self, _mock_redact):
engines\report_generation\v3\tests\test_real_estate_acceptance.py:816:        report = 
_make_real_estate_report(include_amount=True)
engines\report_generation\v3\tests\test_real_estate_acceptance.py:834:        report = 
_make_real_estate_report(include_amount=False)
engines\report_generation\v3\tests\test_real_estate_acceptance.py:845:    def 
test_amount_uses_real_estate_terms_not_other_case_types(self, _mock_redact):
engines\report_generation\v3\tests\test_real_estate_acceptance.py:847:        report = 
_make_real_estate_report(include_amount=True)
engines\report_generation\v3\tests\test_real_estate_acceptance.py:852:        # Should NOT contain civil_loan terms
engines\report_generation\v3\tests\test_real_estate_acceptance.py:855:        # Should NOT contain labor_dispute terms
engines\report_generation\v3\tests\test_real_estate_acceptance.py:871:        report = _make_real_estate_report()
engines\report_generation\v3\tests\test_real_estate_acceptance.py:903:        report = _make_real_estate_report()
engines\report_generation\v3\tests\test_real_estate_acceptance.py:913:        report = _make_real_estate_report()
engines\report_generation\v3\tests\test_real_estate_acceptance.py:932:        report = 
_make_real_estate_report(perspective="neutral")
engines\report_generation\v3\tests\test_real_estate_acceptance.py:944:        report = 
_make_real_estate_report(perspective="neutral")
engines\report_generation\v3\tests\test_real_estate_acceptance.py:959:        report = 
_make_real_estate_report(perspective="neutral")
engines\report_generation\v3\tests\test_real_estate_acceptance.py:977:# Additional structural checks (real_estate 
specific)
engines\report_generation\v3\tests\test_real_estate_acceptance.py:982:    """Structural integrity checks specific to 
real_estate case type."""
engines\report_generation\v3\tests\test_real_estate_acceptance.py:988:        report = _make_real_estate_report()
engines\report_generation\v3\tests\test_real_estate_acceptance.py:1000:    def 
test_issue_map_has_real_estate_issues(self, _mock_redact):
engines\report_generation\v3\tests\test_real_estate_acceptance.py:1001:        """Issue map must contain 
real_estate-specific issues."""
engines\report_generation\v3\tests\test_real_estate_acceptance.py:1002:        report = _make_real_estate_report()
engines\report_generation\v3\tests\test_real_estate_acceptance.py:1015:        report = _make_real_estate_report()
engines\report_generation\v3\tests\test_real_estate_acceptance.py:1027:        report = _make_real_estate_report()
engines\report_generation\v3\tests\test_real_estate_acceptance.py:1038:        report = _make_real_estate_report()
engines\report_generation\v3\tests\test_real_estate_acceptance.py:1047:    def 
test_glossary_has_real_estate_terms(self, _mock_redact):
engines\report_generation\v3\tests\test_real_estate_acceptance.py:1049:        report = _make_real_estate_report()
engines\report_generation\v3\tests\test_real_estate_acceptance.py:1061:        """Real estate report should not 
contain civil_loan or labor terms."""
engines\report_generation\v3\tests\test_real_estate_acceptance.py:1062:        report = _make_real_estate_report()
engines\report_generation\v3\tests\test_real_estate_acceptance.py:1076:        report = _make_real_estate_report()
engines\report_generation\v3\tests\test_real_estate_acceptance.py:1087:        report = _make_real_estate_report()
engines\report_generation\v3\tests\test_real_estate_acceptance.py:1092:        assert card_ids == 
_REAL_ESTATE_EVIDENCE_IDS
engines\report_generation\v3\tests\test_real_estate_acceptance.py:1096:        report = _make_real_estate_report()
engines\report_generation\v3\tests\test_render_contract.py:63:    case_data = {"case_type": "civil_loan", "parties": 
{}}
engines\report_generation\v3\tests\test_render_contract.py:300:    case_data = {"case_type": "civil_loan", "parties": 
{}}
engines\report_generation\v3\tests\test_render_contract.py:331:    case_data = {"case_type": "civil_loan", "parties": 
{}}
engines\report_generation\v3\tests\test_render_contract.py:356:    case_data = {"case_type": "civil_loan", "parties": 
{}}
engines\report_generation\v3\tests\test_report_writer.py:174:            "case_type": "civil_loan",
engines\report_generation\v3\tests\test_report_writer.py:210:            case_data={"case_id": "case-test-001", 
"case_type": "civil_loan", "parties": {}},
engines\report_generation\v3\tests\test_report_writer.py:335:            "case_type": "civil_loan",
engines\report_generation\v3\tests\test_report_writer.py:361:        case_data = {"case_type": "civil_loan", 
"parties": {}}
engines\report_generation\v3\tests\test_report_writer.py:376:        case_data = {"case_type": "civil_loan", 
"parties": {}}
engines\report_generation\v3\tests\test_resume_rebuild.py:283:                    {"case_type": "civil_loan", 
"parties": {}},
engines\report_generation\v3\tests\test_resume_rebuild.py:300:                    {"case_type": "civil_loan", 
"parties": {}},
engines\report_generation\v3\tests\test_resume_rebuild.py:324:                {"case_type": "civil_loan", "parties": 
{}},
engines\report_generation\v3\tests\test_resume_rebuild.py:344:                {"case_type": "civil_loan", "parties": 
{}},
engines\report_generation\v3\tests\test_resume_rebuild.py:369:        case_data = {"case_type": "civil_loan", 
"parties": {}}
engines\report_generation\v3\tests\test_resume_rebuild.py:401:        case_data = {"case_type": "civil_loan", 
"parties": {}}


Cannot set property. Property setting is supported only on core types in this language mode.
At line:1 char:1
+ [Console]::OutputEncoding=[System.Text.Encoding]::UTF8;
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : InvalidOperation: (:) [], RuntimeException
    + FullyQualifiedErrorId : PropertySetterNotSupportedInConstrainedLanguage
 

exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -NoProfile -Command "Get-Content 'engines/procedure_setup/schemas.py' | Select-Object -First 220" in C:/Users/david/dev/case-adversarial-engine
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -NoProfile -Command "Get-Content 'engines/report_generation/v3/render_contract.py' | Select-Object -First 220" in C:/Users/david/dev/case-adversarial-engine
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -NoProfile -Command "Get-Content 'engines/report_generation/v3/layer2_core.py' | Select-Object -First 240" in C:/Users/david/dev/case-adversarial-engine
 succeeded in 620ms:
"""
ç¨‹åºè®¾ç½®å¼•æ“Žæ•°æ®æ¨¡åž‹ã€?
Procedure setup engine data models.

å…±äº«ç±»åž‹ä»?engines.shared.models å¯¼å…¥ï¼›æœ¬æ¨¡å—åªä¿ç•™ç¨‹åºé˜¶æ®µä¸“ç”¨ç±»åž‹å’Œ LLM ä¸­é—´ç»“æž„ã€?
Shared types imported from engines.shared.models; only procedure-specific types and LLM intermediate structures kept here.
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field

# ä»Žå…±äº«æ¨¡å—å¯¼å…¥æ‰€æœ‰å…±äº«ç±»åž‹ï¼ˆre-exported for backward compatï¼?
from engines.shared.models import (  # noqa: F401
    AccessDomain,
    ArtifactRef,
    Burden,
    ClaimIssueMapping,
    DefenseIssueMapping,
    EvidenceStatus as EvidenceStatusValue,  # backward compat alias
    EvidenceStatus,
    FactProposition,
    InputSnapshot,
    Issue,
    IssueTree,
    MaterialRef,
    ProcedurePhase,
    Run,
)

# å…¨å±€é˜¶æ®µé¡ºåº / Canonical phase order
PHASE_ORDER: list[str] = [
    ProcedurePhase.case_intake.value,
    ProcedurePhase.element_mapping.value,
    ProcedurePhase.opening.value,
    ProcedurePhase.evidence_submission.value,
    ProcedurePhase.evidence_challenge.value,
    ProcedurePhase.judge_questions.value,
    ProcedurePhase.rebuttal.value,
    ProcedurePhase.output_branching.value,
]


# ---------------------------------------------------------------------------
# å¼•æ“Žè¾“å…¥æ¨¡åž‹ / Engine input models
# ---------------------------------------------------------------------------


class PartyInfo(BaseModel):
    """å½“äº‹äººç®€è¦ä¿¡æ¯ï¼ˆä»…ç”¨äºŽç¨‹åºè®¾ç½®é˜¶æ®µï¼‰ã€?""

    party_id: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    role_code: str = Field(..., min_length=1)
    side: str = Field(..., min_length=1)


class ProcedureSetupInput(BaseModel):
    """ç¨‹åºè®¾ç½®å¼•æ“Žè¾“å…¥åˆçº¦ã€?""

    workspace_id: str = Field(..., min_length=1)
    case_id: str = Field(..., min_length=1)
    case_type: str = Field(..., min_length=1)
    parties: list[PartyInfo]


# ---------------------------------------------------------------------------
# å¼•æ“Žè¾“å‡ºæ ¸å¿ƒæ¨¡åž‹ / Engine output core models
# ---------------------------------------------------------------------------


class ProcedureState(BaseModel):
    """ç¨‹åºçŠ¶æ€å¯¹è±¡ï¼Œmatching docs/03_case_object_model.md."""

    state_id: str = Field(..., min_length=1)
    case_id: str = Field(..., min_length=1)
    phase: str  # ProcedurePhase æžšä¸¾å€?
    round_index: int = Field(..., ge=0)
    allowed_role_codes: list[str] = Field(default_factory=list)
    readable_access_domains: list[str] = Field(default_factory=list)
    writable_object_types: list[str] = Field(default_factory=list)
    admissible_evidence_statuses: list[str] = Field(default_factory=list)
    open_issue_ids: list[str] = Field(default_factory=list)
    entry_conditions: list[str] = Field(default_factory=list)
    exit_conditions: list[str] = Field(default_factory=list)
    next_state_ids: list[str] = Field(default_factory=list)


class ProcedureConfig(BaseModel):
    """ç¨‹åºé…ç½®ï¼ˆè®°å½•ç¨‹åºçº§å‚æ•°ï¼Œä¾›ä¸‹æ¸¸å¼•ç”¨ï¼‰ã€?""

    case_type: str
    total_phases: int
    evidence_submission_deadline_days: int
    evidence_challenge_window_days: int
    max_rounds_per_phase: int
    applicable_laws: list[str] = Field(default_factory=list)


class TimelineEvent(BaseModel):
    """æ—¶é—´çº¿äº‹ä»¶ã€?""

    event_id: str = Field(..., min_length=1)
    event_type: str = Field(..., min_length=1)
    phase: str
    description: str = Field(..., min_length=1)
    relative_day: int = Field(..., ge=0)
    is_mandatory: bool = True


class ProcedureSetupResult(BaseModel):
    """ç¨‹åºè®¾ç½®ç»“æžœã€?""

    procedure_states: list[ProcedureState]
    procedure_config: ProcedureConfig
    timeline_events: list[TimelineEvent]
    run: Run


# ---------------------------------------------------------------------------
# LLM ä¸­é—´ç»“æž„ / LLM intermediate structures
# ---------------------------------------------------------------------------


class LLMProcedureState(BaseModel):
    """LLM è¿”å›žçš„å•ä¸ªç¨‹åºçŠ¶æ€ï¼ˆå°šæœªè§„èŒƒåŒ–ï¼‰ã€?""

    phase: str
    allowed_role_codes: list[str] = Field(default_factory=list)
    readable_access_domains: list[str] = Field(default_factory=list)
    writable_object_types: list[str] = Field(default_factory=list)
    admissible_evidence_statuses: list[str] = Field(default_factory=list)
    entry_conditions: list[str] = Field(default_factory=list)
    exit_conditions: list[str] = Field(default_factory=list)


class LLMProcedureConfig(BaseModel):
    """LLM è¿”å›žçš„ç¨‹åºé…ç½®ï¼ˆå°šæœªè§„èŒƒåŒ–ï¼‰ã€?""

    evidence_submission_deadline_days: int = 15
    evidence_challenge_window_days: int = 10
    max_rounds_per_phase: int = 3
    applicable_laws: list[str] = Field(default_factory=list)


class LLMTimelineEvent(BaseModel):
    """LLM è¿”å›žçš„æ—¶é—´çº¿äº‹ä»¶ï¼ˆå°šæœªè§„èŒƒåŒ–ï¼‰ã€?""

    event_type: str
    phase: str
    description: str
    relative_day: int = Field(default=0, ge=0)
    is_mandatory: bool = True


class LLMProcedureOutput(BaseModel):
    """LLM è¿”å›žçš„å®Œæ•´ç¨‹åºè®¾ç½®è¾“å‡ºï¼ˆå°šæœªè§„èŒƒåŒ–ï¼‰ã€?""

    procedure_config: LLMProcedureConfig
    procedure_states: list[LLMProcedureState]
    timeline_events: list[LLMTimelineEvent] = Field(default_factory=list)
Cannot set property. Property setting is supported only on core types in this language mode.
At line:1 char:1
+ [Console]::OutputEncoding=[System.Text.Encoding]::UTF8;
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : InvalidOperation: (:) [], RuntimeException
    + FullyQualifiedErrorId : PropertySetterNotSupportedInConstrainedLanguage
 

 succeeded in 632ms:
"""
Layer 2: ä¸­ç«‹å¯¹æŠ—å†…æ ¸å±?/ Neutral Adversarial Core Layer.

å®Œå…¨ä¸­ç«‹ï¼Œä¸å?--perspective å½±å“ï¼?
  2.1 äº‹å®žåº•åº§ â€?ä»…æ— äº‰è®®å®¢è§‚äº‹å®ž
  2.2 äº‰ç‚¹åœ°å›¾ â€?å›ºå®šæ¨¡æ¿å¡ç‰‡
  2.3 è¯æ®ä½œæˆ˜çŸ©é˜µ â€?ä¸ƒé—®
  2.4 æ¡ä»¶åœºæ™¯æ ?â€?äºŒå…ƒæ¡ä»¶åˆ†æ”¯
"""

from __future__ import annotations

from engines.report_generation.v3.evidence_battle_matrix import (
    build_evidence_battle_matrix,
    build_evidence_cards,
)
from engines.report_generation.v3.fact_base import extract_fact_base
from engines.report_generation.v3.issue_map import build_issue_map
from engines.report_generation.v3.models import (
    EvidenceBasicCard,
    EvidenceKeyCard,
    EvidenceRiskLevel,
    Layer2Core,
    SectionTag,
)
from engines.report_generation.v3.scenario_tree import (
    render_scenario_tree_text,
)
from engines.report_generation.v3.tag_system import format_tag, humanize_text


def build_layer2(
    *,
    issue_tree,
    evidence_index,
    adversarial_result=None,
    ranked_issues=None,
    attack_chain=None,
    scenario_tree=None,
) -> Layer2Core:
    """Build Layer 2 neutral adversarial core.

    All content in this layer is completely neutral and perspective-independent.
    The scenario_tree should be pre-built by the caller (report_writer) to
    avoid duplicate construction.
    """
    # 2.1 Fact base â€?adversarial_result used ONLY for dispute detection
    fact_base = extract_fact_base(issue_tree, evidence_index, adversarial_result)

    # 2.2 Issue map â€?presents BOTH sides neutrally with source attribution
    issue_map = build_issue_map(issue_tree, adversarial_result, ranked_issues, attack_chain)

    # 2.3 Evidence cards (dual-tier) + unified electronic strategy
    evidence_cards, unified_electronic_strategy = build_evidence_cards(
        evidence_index, issue_tree, attack_chain
    )

    # 2.3b DEPRECATED: old battle matrix for backward compat
    evidence_matrix = build_evidence_battle_matrix(evidence_index, issue_tree, attack_chain)

    # 2.4 Conditional scenario tree â€?pre-built, passed in from caller
    return Layer2Core(
        fact_base=fact_base,
        issue_map=issue_map,
        evidence_cards=evidence_cards,
        unified_electronic_strategy=unified_electronic_strategy,
        evidence_battle_matrix=evidence_matrix,
        scenario_tree=scenario_tree,
    )


def _h(text: str, ctx: dict[str, str] | None) -> str:
    """Humanize text if context is available, otherwise return as-is."""
    if ctx:
        return humanize_text(text, ctx)
    return text


def _h_list(items: list[str], ctx: dict[str, str] | None) -> list[str]:
    """Humanize a list of strings."""
    return [_h(item, ctx) for item in items]


def render_layer2_md(
    layer2: Layer2Core,
    *,
    humanize_ctx: dict[str, str] | None = None,
) -> list[str]:
    """Render Layer 2 as Markdown lines.

    Args:
        layer2: The Layer2Core model containing all layer 2 data.
        humanize_ctx: Optional dict mapping raw IDs to human-readable titles.
            When provided, all internal IDs (issue-xxx-001, evidence-plaintiff-003,
            etc.) are converted to human-readable Chinese labels.
    """
    lines: list[str] = []

    # --- 2.1 Fact Base ---
    lines.append(f"# äºŒã€ä¸­ç«‹å¯¹æŠ—å†…æ ?{format_tag(SectionTag.fact)}")
    lines.append("")
    lines.append(f"## 2.1 äº‹å®žåº•åº§ {format_tag(SectionTag.fact)}")
    lines.append("")
    if layer2.fact_base:
        lines.append("| # | äº‹å®žæè¿° | æ¥æºè¯æ® |")
        lines.append("|---|----------|----------|")
        for fb in layer2.fact_base:
            fact_id = _h(fb.fact_id, humanize_ctx)
            desc = _h(fb.description[:80], humanize_ctx)
            ev_refs = ", ".join(_h_list(fb.source_evidence_ids[:3], humanize_ctx))
            lines.append(f"| {fact_id} | {desc} | {ev_refs} |")
        lines.append("")
    else:
        lines.append("*æš‚æ— åŒæ–¹å‡è®¤å¯çš„æ— äº‰è®®äº‹å®žã€?")
        lines.append("")

    # --- 2.2 Issue Map (tree hierarchy) ---
    lines.append(f"## 2.2 äº‰ç‚¹åœ°å›¾ {format_tag(SectionTag.inference)}")
    lines.append("")
    for card in layer2.issue_map:
        title = _h(card.issue_title, humanize_ctx)
        sensitivity = card.outcome_sensitivity or "å¾…è¯„ä¼?

        if card.depth == 0:
            # Root issue (L1): full card with table
            lines.append(f"### {title} âš¡{sensitivity}")
            lines.append("")
            lines.append("| å­—æ®µ | å†…å®¹ |")
            lines.append("|------|------|")
            lines.append(f"| åŽŸå‘Šä¸»å¼  | {_h(card.plaintiff_thesis, humanize_ctx)} |")
            lines.append(f"| è¢«å‘Šä¸»å¼  | {_h(card.defendant_thesis, humanize_ctx)} |")
            decisive = (
                ", ".join(_h_list(card.decisive_evidence, humanize_ctx))
                if card.decisive_evidence
                else "å¾…è¡¥å…?
            )
            lines.append(f"| å†³å®šæ€§è¯æ?| {decisive} |")
            gaps = (
                "; ".join(_h_list(card.current_gaps, humanize_ctx)) if card.current_gaps else "æš‚æ— "
            )
            lines.append(f"| å½“å‰ç¼ºå£ | {gaps} |")
            lines.append("")
        else:
            # Child issue (L2+): compact blockquote format
            lines.append(f"> **å­äº‰ç‚?*: {title} âš¡{sensitivity}")
            lines.append(">")
            lines.append(
                f"> åŽŸå‘Š: {_h(card.plaintiff_thesis, humanize_ctx)} / "
                f"è¢«å‘Š: {_h(card.defendant_thesis, humanize_ctx)}"
            )
            if card.current_gaps:
                gaps = "; ".join(_h_list(card.current_gaps, humanize_ctx))
                lines.append(f"> ç¼ºå£: {gaps}")
            lines.append("")

    # --- 2.3 Evidence Analysis ---
    lines.append(f"## 2.3 è¯æ®ä½œæˆ˜çŸ©é˜µ {format_tag(SectionTag.inference)}")
    lines.append("")

    # 2.3a Unified electronic evidence strategy (if present)
    if layer2.unified_electronic_strategy:
        lines.append("#### ç»Ÿä¸€ç”µå­è¯æ®è¡¥å¼ºç­–ç•¥")
        lines.append("")
        lines.append(_h(layer2.unified_electronic_strategy, humanize_ctx))
        lines.append("")

    # 2.3b Dual-tier evidence cards (V3.1 path)
    if layer2.evidence_cards:
        # Separate key (core) cards from basic (supporting/background) cards
        key_cards: list[EvidenceKeyCard] = []
        basic_cards: list[EvidenceBasicCard] = []
        for card in layer2.evidence_cards:
            if isinstance(card, EvidenceKeyCard):
                key_cards.append(card)
            else:
                basic_cards.append(card)

        # --- Key evidence cards (full 6-field table each) ---
        if key_cards:
            lines.append("### æ ¸å¿ƒè¯æ®è¯¦æž")
            lines.append("")
            for card in key_cards:
                ev_name = _h(card.evidence_id, humanize_ctx)
                lines.append(f"#### {ev_name} â€?æ ¸å¿ƒè¯æ®")
                lines.append("")
                lines.append("| å­—æ®µ | åˆ†æž |")
                lines.append("|------|------|")
                lines.append(f"| â‘?å†…å®¹ | {_h(card.q1_what, humanize_ctx)} |")
                lines.append(f"| â‘?æœåŠ¡äº‰ç‚¹ | {_h(card.q2_target, humanize_ctx)} |")
                lines.append(f"| â‘?å…³é”®é£Žé™© | {_h(card.q3_key_risk, humanize_ctx)} |")
                lines.append(f"| â‘?å¯¹æ–¹æœ€ä½³æ”»å‡»ç‚¹ | {_h(card.q4_best_attack, humanize_ctx)} |")
                lines.append(f"| â‘?å¦‚ä½•åŠ å›º | {_h(card.q5_reinforce, humanize_ctx)} |")
                lines.append(f"| â‘?å¤±æ•ˆå½±å“ | {_h(card.q6_failure_impact, humanize_ctx)} |")
                lines.append("")

        # --- Basic evidence cards (compact summary table) ---
        if basic_cards:
            lines.append("### è¾…åŠ©/èƒŒæ™¯è¯æ®æ¦‚è§ˆ")
            lines.append("")
            lines.append("| è¯æ® | å±‚çº§ | æœåŠ¡äº‰ç‚¹ | å…³é”®é£Žé™© | å¯¹æ–¹æœ€ä½³æ”»å‡»ç‚¹ |")
            lines.append("|------|------|----------|----------|----------------|")
            for card in basic_cards:
                ev_name = _h(card.evidence_id, humanize_ctx)
                priority = card.priority.value
                target = _h(card.q2_target, humanize_ctx)
                risk = _h(card.q3_key_risk, humanize_ctx)
                attack = _h(card.q4_best_attack, humanize_ctx)
                lines.append(f"| {ev_name} | {priority} | {target} | {risk} | {attack} |")
            lines.append("")

    elif layer2.evidence_battle_matrix:
        # 2.3c FALLBACK: old 7-question battle matrix (backward compat)
        _risk_emoji = {
            EvidenceRiskLevel.green: "ðŸŸ¢",
            EvidenceRiskLevel.yellow: "ðŸŸ¡",
            EvidenceRiskLevel.red: "ðŸ”´",
        }

        for card in layer2.evidence_battle_matrix:
            emoji = _risk_emoji.get(card.risk_level, "âš?)
            ev_name = _h(card.evidence_id, humanize_ctx)
            lines.append(f"### {ev_name} {emoji}")
            lines.append("")
            lines.append("| é—®é¢˜ | åˆ†æž |")
            lines.append("|------|------|")
            lines.append(f"| 1. è¿™æ˜¯ä»€ä¹ˆè¯æ?| {_h(card.q1_what, humanize_ctx)} |")
            lines.append(f"| 2. è¯æ˜Žä»€ä¹ˆå‘½é¢?| {_h(card.q2_proves, humanize_ctx)} |")
            lines.append(f"| 3. è¯æ˜Žæ–¹å‘ | {_h(card.q3_direction, humanize_ctx)} |")
            lines.append(f"| 4. å››æ€§é£Žé™?| {_h(card.q4_risks, humanize_ctx)} |")
            lines.append(f"| 5. å¯¹æ–¹å¦‚ä½•æ”»å‡» | {_h(card.q5_opponent_attack, humanize_ctx)} |")
            lines.append(f"| 6. å¦‚ä½•åŠ å›º | {_h(card.q6_reinforce, humanize_ctx)} |")
            lines.append(f"| 7. å¤±è´¥å½±å“ | {_h(card.q7_failure_impact, humanize_ctx)} |")
            lines.append("")
    else:
        lines.append("*æš‚æ— è¯æ®åˆ†æžæ•°æ®ã€?")
        lines.append("")

    # --- 2.4 Conditional Scenario Tree ---
    lines.append(f"## 2.4 æ¡ä»¶åœºæ™¯æ ?{format_tag(SectionTag.inference)}")
    lines.append("")
Cannot set property. Property setting is supported only on core types in this language mode.
At line:1 char:1
+ [Console]::OutputEncoding=[System.Text.Encoding]::UTF8;
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : InvalidOperation: (:) [], RuntimeException
    + FullyQualifiedErrorId : PropertySetterNotSupportedInConstrainedLanguage
 

 succeeded in 650ms:
"""User-visible render contract checks for V3 reports.

Three format-clean rules (ERROR):
  - forbidden_tokens: internal IDs leaking into user-visible text
  - empty_major_section: ## heading with no body at all
  - placeholder_row: table row where every cell is a placeholder

Seven user-clean rules:
  - raw_json_leak: naked JSON (``{"`` / ``[{"``) in markdown  (ERROR)
  - orphan_citation: ``[src-xxx]`` not in evidence index       (ERROR)
  - excessive_fallback: fallback sections > 20 % of total      (WARN)
  - section_length_floor: core section body < 50 chars          (WARN)
  - duplicate_heading: same ``##`` title appears twice          (ERROR)
  - table_header_mismatch: data-row column count != header      (ERROR)
  - cjk_punctuation_mix: CJK text adjacent to ASCII punctuation (WARN)
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum


# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------


class RenderContractViolation(ValueError):
    """Raised when user-visible report content violates the render contract."""


class LintSeverity(str, Enum):
    """Lint rule severity level."""

    ERROR = "error"
    WARN = "warn"


@dataclass
class LintResult:
    """Single lint rule result."""

    rule: str
    message: str
    severity: LintSeverity


# ---------------------------------------------------------------------------
# Compiled patterns
# ---------------------------------------------------------------------------

_FORBIDDEN_TOKEN_PATTERNS = [
    (re.compile(r"\bissue-[a-z0-9-]+\b", re.IGNORECASE), "issue-"),
    (re.compile(r"\bxexam-[a-z0-9-]+\b", re.IGNORECASE), "xexam-"),
    (re.compile(r"\bundefined\b", re.IGNORECASE), "undefined"),
    (re.compile(r"\bPATH-[A-Z0-9-]+\b"), "PATH-"),
    (re.compile(r"\bpath-[a-z0-9-]+\b", re.IGNORECASE), "path-"),
]

_PLACEHOLDER_CELLS = {"", "-", "\u2014", "\u2013"}

_HEADING_RE = re.compile(r"(?m)^##\s+(.+?)\s*$")
_RAW_JSON_RE = re.compile(r'\{"|\[\{"')
_CITATION_RE = re.compile(r"\[src-([^\]]+)\]")
_FALLBACK_BODY_RE = re.compile(
    r"\*(\u6682\u65e0.+[\u3002.]|No .+ available\.)\*"  # *жљ‚ж— ...гЂ? | *No ... available.*
    r"|"
    r"\uff08\u65e0.+\uff09",  # пј€ж— ...пј?
)
_CJK_RANGE = "\u4e00-\u9fff\u3400-\u4dbf"
_CJK_ASCII_PUNCT_RE = re.compile(
    rf"[{_CJK_RANGE}][,.:;!?]|[,.:;!?][{_CJK_RANGE}]"
)
_SECTION_LENGTH_FLOOR = 50
_MARKDOWN_SYNTAX_RE = re.compile(r"[#*_`>|~\-]")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def lint_markdown_render_contract(
    text: str,
    *,
    evidence_ids: set[str] | None = None,
) -> list[LintResult]:
    """Check user-visible Markdown against the render contract.

    Raises :class:`RenderContractViolation` when any ERROR-level rule fires.
    Returns the full list of results (ERRORs + WARNs).
    """
    results: list[LintResult] = []

    # Format-clean rules (ERROR)
    results.extend(_find_forbidden_tokens(text))
    results.extend(_find_empty_major_sections(text))
    results.extend(_find_placeholder_rows(text))

    # User-clean rules
    results.extend(_find_raw_json_leak(text))
    results.extend(_find_orphan_citations(text, evidence_ids))
    results.extend(_find_excessive_fallback(text))
    results.extend(_find_section_length_floor(text))
    results.extend(_find_duplicate_headings(text))
    results.extend(_find_table_header_mismatch(text))
    results.extend(_find_cjk_punctuation_mix(text))

    errors = [r for r in results if r.severity == LintSeverity.ERROR]
    if errors:
        msgs = "; ".join(r.message for r in errors)
        raise RenderContractViolation("render contract violation: " + msgs)

    return results


def compute_fallback_ratio(text: str) -> tuple[float, int, int]:
    """Compute the ratio of fallback sections to total ``##`` sections.

    Returns ``(ratio, fallback_count, total_sections)``.
    """
    sections = _extract_sections(text)
    if not sections:
        return 0.0, 0, 0
    fallback_count = sum(1 for _, body in sections if _is_fallback_body(body))
    return fallback_count / len(sections), fallback_count, len(sections)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _extract_sections(text: str) -> list[tuple[str, str]]:
    """Extract ``(title, body)`` pairs for all ``##`` headings."""
    headings = list(_HEADING_RE.finditer(text))
    sections: list[tuple[str, str]] = []
    for i, m in enumerate(headings):
        title = m.group(1).strip()
        start = m.end()
        end = headings[i + 1].start() if i + 1 < len(headings) else len(text)
        body = text[start:end].strip()
        sections.append((title, body))
    return sections


def _is_fallback_body(body: str) -> bool:
    """Return True if section body is a fallback placeholder."""
    return bool(_FALLBACK_BODY_RE.fullmatch(body.strip()))


# ---------------------------------------------------------------------------
# Format-clean rules (ERROR)
# ---------------------------------------------------------------------------


def _find_forbidden_tokens(text: str) -> list[LintResult]:
    labels: list[str] = []
    for pattern, label in _FORBIDDEN_TOKEN_PATTERNS:
        if pattern.search(text):
            labels.append(label)
    if labels:
        joined = "|".join(labels)
        return [
            LintResult(
                rule="forbidden_tokens",
                message=f"forbidden tokens present ({joined})",
                severity=LintSeverity.ERROR,
            )
        ]
    return []


def _find_empty_major_sections(text: str) -> list[LintResult]:
    results: list[LintResult] = []
    for title, body in _extract_sections(text):
        if not body:
            results.append(
                LintResult(
                    rule="empty_major_section",
                    message=f"empty major section: {title}",
                    severity=LintSeverity.ERROR,
                )
            )
    return results


def _find_placeholder_rows(text: str) -> list[LintResult]:
    results: list[LintResult] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        if re.fullmatch(r"\|[\s:\-]+\|", stripped):
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if cells and all(cell in _PLACEHOLDER_CELLS for cell in cells):
            results.append(
                LintResult(
                    rule="placeholder_row",
                    message=f"placeholder-only table row: {stripped}",
                    severity=LintSeverity.ERROR,
                )
            )
    return results


# ---------------------------------------------------------------------------
# User-clean rules
# ---------------------------------------------------------------------------


def _find_raw_json_leak(text: str) -> list[LintResult]:
    if _RAW_JSON_RE.search(text):
        return [
            LintResult(
                rule="raw_json_leak",
                message="raw JSON detected in markdown output",
Cannot set property. Property setting is supported only on core types in this language mode.
At line:1 char:1
+ [Console]::OutputEncoding=[System.Text.Encoding]::UTF8;
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : InvalidOperation: (:) [], RuntimeException
    + FullyQualifiedErrorId : PropertySetterNotSupportedInConstrainedLanguage
 

exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -NoProfile -Command "Select-String -Path 'engines\\report_generation\\v3\\*.py' -Pattern 'civil_loan|labor_dispute|real_estate|amount|wage|deposit|render contract|case_type'" in C:/Users/david/dev/case-adversarial-engine
 succeeded in 614ms:

engines\report_generation\v3\docx_lint.py:1:"""DOCX render contract lint — runs a subset of MD rules on extracted DOCX 
text."""
engines\report_generation\v3\docx_lint.py:18:    """Lint a generated DOCX file against the render contract rule subset.
engines\report_generation\v3\layer4_appendix.py:253:    amount_report=None,
engines\report_generation\v3\layer4_appendix.py:282:    # Amount calculation
engines\report_generation\v3\layer4_appendix.py:283:    amount_md = _render_amount_calculation(amount_report)
engines\report_generation\v3\layer4_appendix.py:290:        amount_calculation_md=amount_md,
engines\report_generation\v3\layer4_appendix.py:371:def _render_amount_calculation(amount_report) -> str:
engines\report_generation\v3\layer4_appendix.py:372:    """Render amount calculation details."""
engines\report_generation\v3\layer4_appendix.py:373:    if not amount_report:
engines\report_generation\v3\layer4_appendix.py:380:    # Handle AmountCalculationReport fields
engines\report_generation\v3\layer4_appendix.py:381:    if hasattr(amount_report, "total_principal"):
engines\report_generation\v3\layer4_appendix.py:382:        lines.append(f"| 借款本金 | 
{amount_report.total_principal:,} 元 | 核实本金总额 |")
engines\report_generation\v3\layer4_appendix.py:383:    if hasattr(amount_report, "total_interest"):
engines\report_generation\v3\layer4_appendix.py:384:        lines.append(f"| 利息 | {amount_report.total_interest:,} 
元 | 计算利息总额 |")
engines\report_generation\v3\layer4_appendix.py:385:    if hasattr(amount_report, "total_claimed"):
engines\report_generation\v3\layer4_appendix.py:386:        lines.append(f"| 诉请总额 | 
{amount_report.total_claimed:,} 元 | 原告主张金额 |")
engines\report_generation\v3\layer4_appendix.py:387:    if hasattr(amount_report, "verified_amount"):
engines\report_generation\v3\layer4_appendix.py:388:        lines.append(f"| 可核实金额 | 
{amount_report.verified_amount:,} 元 | 有证据支撑的金额 |")
engines\report_generation\v3\layer4_appendix.py:437:    # Amount calculation
engines\report_generation\v3\layer4_appendix.py:438:    if layer4.amount_calculation_md and "暂无" not in 
layer4.amount_calculation_md:
engines\report_generation\v3\layer4_appendix.py:441:        lines.append(layer4.amount_calculation_md)
engines\report_generation\v3\models.py:401:    amount_calculation_md: str = Field(default="", 
description="金额计算明细")
engines\report_generation\v3\render_contract.py:1:"""User-visible render contract checks for V3 reports.
engines\report_generation\v3\render_contract.py:31:    """Raised when user-visible report content violates the render 
contract."""
engines\report_generation\v3\render_contract.py:90:    """Check user-visible Markdown against the render contract.
engines\report_generation\v3\render_contract.py:114:        raise RenderContractViolation("render contract violation: 
" + msgs)
engines\report_generation\v3\report_fixer.py:40:    that the render contract lint rules would flag.
engines\report_generation\v3\report_writer.py:48:    amount_report=None,
engines\report_generation\v3\report_writer.py:111:        amount_report=amount_report,
engines\report_generation\v3\report_writer.py:158:        + case_data.get("case_type", "civil_loan").replace("_", " 
").title()
engines\report_generation\v3\report_writer.py:218:            f"render contract violation: fallback_ratio {ratio:.0%} "
engines\report_generation\v3\tag_system.py:267:    # Remove model class names + internal report IDs (e.g. 
"AmountCalculationReport amount-report-xxx")
engines\report_generation\v3\tag_system.py:268:    result = 
re.sub(r"\s*AmountCalculationReport\s+amount-report-[a-f0-9]+", "", result)


Cannot set property. Property setting is supported only on core types in this language mode.
At line:1 char:1
+ [Console]::OutputEncoding=[System.Text.Encoding]::UTF8;
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : InvalidOperation: (:) [], RuntimeException
    + FullyQualifiedErrorId : PropertySetterNotSupportedInConstrainedLanguage
 

exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -NoProfile -Command "Get-Content 'engines/pretrial_conference/cross_examination_engine.py' | Select-Object -First 120" in C:/Users/david/dev/case-adversarial-engine
 succeeded in 581ms:
"""
è´¨è¯ç¼–æŽ’å™?â€?v1.5 æ ¸å¿ƒç»„ä»¶ã€?
Cross-examination engine â€?v1.5 core component.

èŒè´£ / Responsibilities:
1. ä»?evidence_index ä¸­é€‰å– submitted çŠ¶æ€çš„è¯æ®
2. æŒ?owner åˆ†ç»„ï¼Œç”±å¯¹æ–¹é€šè¿‡ LLM ç”Ÿæˆè´¨è¯æ„è§
3. è§„åˆ™å±‚æ ¡éªŒï¼ˆè¿‡æ»¤å¹»è§‰ IDã€æ— æ•ˆæžšä¸¾ï¼‰
4. è§„åˆ™å±‚å†³å®šçŠ¶æ€è¿ç§»ï¼šä»»ä¸€ç»´åº¦ challenged â†?challengedï¼›å…¨éƒ?accepted â†?admitted
5. é€šè¿‡ EvidenceStateMachine æ‰§è¡Œè¿ç§»
6. è¾“å‡º CrossExaminationResult + æ›´æ–°åŽçš„ EvidenceIndex

åˆçº¦ä¿è¯ / Contract guarantees:
- åªæœ‰ submitted çŠ¶æ€çš„è¯æ®å‚ä¸Žè´¨è¯
- private / admitted_for_discussion è¯æ®ä¸ä¼šè¢«ä¼ å…?LLM
- å¹»è§‰ evidence_id / issue_id è¢«è¿‡æ»?
- æ— æ•ˆ dimension / verdict æžšä¸¾å€¼è¢«è¿‡æ»¤
- LLM å¤±è´¥æ—¶è¿”å›žç©ºç»“æžœï¼Œä¸æŠ›å¼‚å¸?
- è¯æ®çŠ¶æ€è¿ç§»é€šè¿‡ EvidenceStateMachine å¼ºåˆ¶åˆæ³•
"""

from __future__ import annotations

from uuid import uuid4

from engines.shared.evidence_state_machine import EvidenceStateMachine
from engines.shared.models import (
    EvidenceIndex,
    EvidenceStatus,
    IssueTree,
    LLMClient,
)

from .prompts.civil_loan import (
    CROSS_EXAM_SYSTEM,
    build_cross_exam_user_prompt,
)
from .schemas import (
    CrossExaminationDimension,
    CrossExaminationFocusItem,
    CrossExaminationOpinion,
    CrossExaminationRecord,
    CrossExaminationResult,
    CrossExaminationVerdict,
    LLMCrossExaminationOutput,
)


class CrossExaminationEngine:
    """è´¨è¯ç¼–æŽ’å™¨ã€?

    Args:
        llm_client:  ç¬¦åˆ LLMClient åè®®çš„å®¢æˆ·ç«¯å®žä¾‹
        model:       LLM æ¨¡åž‹æ ‡è¯†
        temperature: ç”Ÿæˆæ¸©åº¦
        max_retries: LLM è°ƒç”¨å¤±è´¥æ—¶çš„æœ€å¤§é‡è¯•æ¬¡æ•?
    """

    def __init__(
        self,
        llm_client: LLMClient,
        *,
        model: str,
        temperature: float,
        max_retries: int,
    ) -> None:
        self._llm = llm_client
        self._model = model
        self._temperature = temperature
        self._max_retries = max_retries
        self._sm = EvidenceStateMachine()

    async def run(
        self,
        evidence_index: EvidenceIndex,
        issue_tree: IssueTree,
        plaintiff_party_id: str,
        defendant_party_id: str,
    ) -> tuple[CrossExaminationResult, EvidenceIndex]:
        """æ‰§è¡Œè´¨è¯æµç¨‹ã€?

        Returns:
            (CrossExaminationResult, æ›´æ–°åŽçš„ EvidenceIndex)
        """
        run_id = f"run-xexam-{uuid4().hex[:12]}"
        case_id = evidence_index.case_id

        # æž„å»ºå·²çŸ¥ ID é›†åˆ
        known_evidence_ids: set[str] = {ev.evidence_id for ev in evidence_index.evidence}
        known_issue_ids: set[str] = {iss.issue_id for iss in issue_tree.issues}

        # åªå– submitted è¯æ®
        submitted = [ev for ev in evidence_index.evidence if ev.status == EvidenceStatus.submitted]

        if not submitted:
            return (
                CrossExaminationResult(case_id=case_id, run_id=run_id),
                evidence_index,
            )

        # æŒ?owner åˆ†ç»„
        plaintiff_ev = [ev for ev in submitted if ev.owner_party_id == plaintiff_party_id]
        defendant_ev = [ev for ev in submitted if ev.owner_party_id == defendant_party_id]

        all_opinions: list[CrossExaminationOpinion] = []

        # è¢«å‘Šè´¨è¯åŽŸå‘Šè¯æ®
        if plaintiff_ev:
            ops = await self._examine_batch(
                evidences=plaintiff_ev,
                examiner_party_id=defendant_party_id,
                examiner_role="è¢«å‘Šä»£ç†å¾‹å¸ˆ",
                issue_tree=issue_tree,
                known_evidence_ids=known_evidence_ids,
                known_issue_ids=known_issue_ids,
            )
            all_opinions.extend(ops)

        # åŽŸå‘Šè´¨è¯è¢«å‘Šè¯æ®
        if defendant_ev:
Cannot set property. Property setting is supported only on core types in this language mode.
At line:1 char:1
+ [Console]::OutputEncoding=[System.Text.Encoding]::UTF8;
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : InvalidOperation: (:) [], RuntimeException
    + FullyQualifiedErrorId : PropertySetterNotSupportedInConstrainedLanguage
 

codex
I found a worse coupling than the plan admits: `pretrial_conference/cross_examination_engine.py` directly imports the `civil_loan` prompt module instead of using a registry. That is not “prompt add-on” work; it is a structural civil-only assumption. I’m tracing similar hidden dependencies around amount reports now.
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -NoProfile -Command "Select-String -Path 'engines\\**\\*.py' -Pattern 'amount_calculation_report|AmountCalculationReport|consistency_check_result|claim_calculation_table|interest_recalculation'" in C:/Users/david/dev/case-adversarial-engine
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -NoProfile -Command "Select-String -Path 'engines\\**\\*.py' -Pattern 'plaintiff_party_id|defendant_party_id|原告|被告|控方|辩方'" in C:/Users/david/dev/case-adversarial-engine
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -NoProfile -Command "Select-String -Path 'engines\\**\\*.py' -Pattern 'ProcedurePhase\\.|PHASE_ORDER|judge_questions|rebuttal|output_branching|evidence_submission|evidence_challenge'" in C:/Users/david/dev/case-adversarial-engine
 succeeded in 678ms:

engines\report_generation\docx_generator.py:18:        amount_report=ar_dict,        # AmountCalculationReport as dict 
(or None)
engines\report_generation\docx_generator.py:218:        amount_report:   AmountCalculationReport 序列化 dict（可选）
engines\report_generation\docx_generator.py:651:    check = amount_report.get("consistency_check_result", {})
engines\report_generation\mediation_range.py:41:    1. Sum claimed_amount and calculated_amount from 
claim_calculation_table
engines\report_generation\mediation_range.py:48:        amount_report: AmountCalculationReport object or dict with 
claim_calculation_table
engines\report_generation\mediation_range.py:58:    table = _get_attr_or_key(amount_report, "claim_calculation_table")


Cannot set property. Property setting is supported only on core types in this language mode.
At line:1 char:1
+ [Console]::OutputEncoding=[System.Text.Encoding]::UTF8;
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : InvalidOperation: (:) [], RuntimeException
    + FullyQualifiedErrorId : PropertySetterNotSupportedInConstrainedLanguage
 

 succeeded in 714ms:

engines\adversarial\round_engine.py:8:  Round 3 (rebuttal): 原告针对被告抗辩反驳，被告针对原告主张反驳
engines\adversarial\round_engine.py:13:  Round 3 (rebuttal): Plaintiff rebuts defendant, defendant rebuts plaintiff
engines\adversarial\round_engine.py:188:            # ── Round 3: 针对性反驳 / rebuttal ──────────────────────────────
engines\adversarial\round_engine.py:193:            p_rebuttal_raw, d_rebuttal_raw = await asyncio.gather(
engines\adversarial\round_engine.py:194:                plaintiff.generate_rebuttal(
engines\adversarial\round_engine.py:203:                defendant.generate_rebuttal(
engines\adversarial\round_engine.py:214:            p_rebuttal = p_rebuttal_raw.model_copy(update={"case_id": case_id})
engines\adversarial\round_engine.py:215:            d_rebuttal = d_rebuttal_raw.model_copy(update={"case_id": case_id})
engines\adversarial\round_engine.py:217:                self._workspace.save_agent_output(p_rebuttal, 
AccessDomain.owner_private)
engines\adversarial\round_engine.py:218:                self._workspace.save_agent_output(d_rebuttal, 
AccessDomain.owner_private)
engines\adversarial\round_engine.py:222:                phase=RoundPhase.rebuttal,
engines\adversarial\round_engine.py:223:                outputs=[p_rebuttal, d_rebuttal],
engines\adversarial\round_engine.py:226:            all_outputs.extend([p_rebuttal, d_rebuttal])
engines\adversarial\round_engine.py:229:            plaintiff_best = self._extract_best_arguments(p_claim, p_rebuttal)
engines\adversarial\round_engine.py:230:            defendant_best = self._extract_best_arguments(d_claim, d_rebuttal)
engines\adversarial\schemas.py:26:    rebuttal = "rebuttal"  # 针对性反驳
engines\adversarial\schemas.py:60:    rebuttal_target_output_id: Optional[str] = Field(
engines\pretrial_conference\conference_engine.py:164:            judge_questions=judge_qs,
engines\pretrial_conference\minutes_generator.py:53:        judge_output_id = result.judge_questions.run_id
engines\pretrial_conference\minutes_generator.py:161:        jq = result.judge_questions
engines\pretrial_conference\schemas.py:186:    judge_questions: JudgeQuestionSet
engines\procedure_setup\planner.py:12:- judge_questions 阶段不读取 owner_private
engines\procedure_setup\planner.py:13:- output_branching 阶段仅基于 admitted_for_discussion 证据
engines\procedure_setup\planner.py:35:    PHASE_ORDER,
engines\procedure_setup\planner.py:67:        idx = PHASE_ORDER.index(phase)
engines\procedure_setup\planner.py:70:    if idx + 1 < len(PHASE_ORDER):
engines\procedure_setup\planner.py:71:        next_phase = PHASE_ORDER[idx + 1]
engines\procedure_setup\planner.py:73:    # 终止阶段（output_branching）/ Terminal phase
engines\procedure_setup\planner.py:78:    """清理访问域列表，强制执行 judge_questions 约束。
engines\procedure_setup\planner.py:79:    Sanitize access domain list, enforcing judge_questions constraint.
engines\procedure_setup\planner.py:81:    judge_questions 阶段必须移除 owner_private。
engines\procedure_setup\planner.py:82:    owner_private must be removed from judge_questions phase.
engines\procedure_setup\planner.py:84:    if phase == "judge_questions":
engines\procedure_setup\planner.py:90:    """清理证据状态列表，强制执行 output_branching 约束。
engines\procedure_setup\planner.py:91:    Sanitize evidence status list, enforcing output_branching constraint.
engines\procedure_setup\planner.py:93:    output_branching 阶段只允许 admitted_for_discussion。
engines\procedure_setup\planner.py:94:    output_branching phase only allows admitted_for_discussion.
engines\procedure_setup\planner.py:96:    if phase == "output_branching":
engines\procedure_setup\planner.py:131:    "evidence_submission": {
engines\procedure_setup\planner.py:139:    "evidence_challenge": {
engines\procedure_setup\planner.py:152:    "judge_questions": {
engines\procedure_setup\planner.py:160:    "rebuttal": {
engines\procedure_setup\planner.py:168:    "output_branching": {
engines\procedure_setup\planner.py:356:        - 按 PHASE_ORDER 重新排序并覆盖全部八个阶段（补充缺失阶段）
engines\procedure_setup\planner.py:358:        - judge_questions 强制移除 owner_private
engines\procedure_setup\planner.py:359:        - output_branching 强制仅保留 admitted_for_discussion
engines\procedure_setup\planner.py:364:            if ls.phase in PHASE_ORDER:
engines\procedure_setup\planner.py:370:        for idx, phase in enumerate(PHASE_ORDER):
engines\procedure_setup\planner.py:418:            total_phases=len(PHASE_ORDER),
engines\procedure_setup\planner.py:419:            evidence_submission_deadline_days=max(1, 
llm_cfg.evidence_submission_deadline_days),
engines\procedure_setup\planner.py:420:            evidence_challenge_window_days=max(1, 
llm_cfg.evidence_challenge_window_days),
engines\procedure_setup\planner.py:436:                object_id=_make_state_id(case_id, PHASE_ORDER[0]),
engines\procedure_setup\planner.py:437:                
storage_ref=f"artifact_index/AgentOutput/{_make_state_id(case_id, PHASE_ORDER[0])}",
engines\procedure_setup\planner.py:478:            if phase not in PHASE_ORDER:
engines\procedure_setup\planner.py:500:                    event_id=f"tevt-{case_id}-evidence_submission-001",
engines\procedure_setup\planner.py:501:                    event_type="evidence_submission_deadline",
engines\procedure_setup\planner.py:502:                    phase="evidence_submission",
engines\procedure_setup\planner.py:508:                    event_id=f"tevt-{case_id}-evidence_challenge-001",
engines\procedure_setup\planner.py:509:                    event_type="evidence_challenge_deadline",
engines\procedure_setup\planner.py:510:                    phase="evidence_challenge",
engines\procedure_setup\planner.py:573:            for idx, phase in enumerate(PHASE_ORDER)
engines\procedure_setup\planner.py:578:            total_phases=len(PHASE_ORDER),
engines\procedure_setup\planner.py:579:            evidence_submission_deadline_days=15,
engines\procedure_setup\planner.py:580:            evidence_challenge_window_days=10,
engines\procedure_setup\planner.py:587:                event_id=f"tevt-{case_id}-evidence_submission-001",
engines\procedure_setup\planner.py:588:                event_type="evidence_submission_deadline",
engines\procedure_setup\planner.py:589:                phase="evidence_submission",
engines\procedure_setup\schemas.py:34:PHASE_ORDER: list[str] = [
engines\procedure_setup\schemas.py:35:    ProcedurePhase.case_intake.value,
engines\procedure_setup\schemas.py:36:    ProcedurePhase.element_mapping.value,
engines\procedure_setup\schemas.py:37:    ProcedurePhase.opening.value,
engines\procedure_setup\schemas.py:38:    ProcedurePhase.evidence_submission.value,
engines\procedure_setup\schemas.py:39:    ProcedurePhase.evidence_challenge.value,
engines\procedure_setup\schemas.py:40:    ProcedurePhase.judge_questions.value,
engines\procedure_setup\schemas.py:41:    ProcedurePhase.rebuttal.value,
engines\procedure_setup\schemas.py:42:    ProcedurePhase.output_branching.value,
engines\procedure_setup\schemas.py:96:    evidence_submission_deadline_days: int
engines\procedure_setup\schemas.py:97:    evidence_challenge_window_days: int
engines\procedure_setup\schemas.py:142:    evidence_submission_deadline_days: int = 15
engines\procedure_setup\schemas.py:143:    evidence_challenge_window_days: int = 10
engines\procedure_setup\validator.py:8:3. judge_questions 阶段不得包含 owner_private 读取域
engines\procedure_setup\validator.py:9:4. output_branching 阶段 admissible_evidence_statuses 必须仅包含 
admitted_for_discussion
engines\procedure_setup\validator.py:20:    PHASE_ORDER,
engines\procedure_setup\validator.py:84:_VALID_PHASES: set[str] = set(PHASE_ORDER)
engines\procedure_setup\validator.py:168:    # ── 4. judge_questions 访问域约束 / judge_questions access constraint ──
engines\procedure_setup\validator.py:169:    # judge_questions 不得读取 owner_private（裁判不得接触当事人私有材料）
engines\procedure_setup\validator.py:170:    if state.phase == "judge_questions":
engines\procedure_setup\validator.py:174:                    code="JUDGE_QUESTIONS_OWNER_PRIVATE_VIOLATION",
engines\procedure_setup\validator.py:176:                        "judge_questions 阶段禁止读取 owner_private 域 / "
engines\procedure_setup\validator.py:177:                        "judge_questions phase must not include owner_private 
in readable_access_domains"
engines\procedure_setup\validator.py:183:    # ── 5. output_branching 证据状态约束 / output_branching evidence 
constraint ──
engines\procedure_setup\validator.py:184:    # output_branching 只能基于 admitted_for_discussion 的证据
engines\procedure_setup\validator.py:185:    if state.phase == "output_branching":
engines\procedure_setup\validator.py:190:                        code="OUTPUT_BRANCHING_INADMISSIBLE_STATUS",
engines\procedure_setup\validator.py:192:                            f"output_branching 阶段仅允许 
admitted_for_discussion，"
engines\procedure_setup\validator.py:194:                            f"output_branching phase only allows 
admitted_for_discussion, "
engines\procedure_setup\validator.py:255:    # output_branching 是唯一的终止阶段，应无 next_state_ids
engines\procedure_setup\validator.py:256:    if state.phase == "output_branching" and state.next_state_ids:
engines\procedure_setup\validator.py:261:                    "output_branching 是终止状态，不应有 next_state_ids / "
engines\procedure_setup\validator.py:262:                    "output_branching is a terminal state and should not have 
next_state_ids"
engines\procedure_setup\validator.py:304:    missing_phases = set(PHASE_ORDER) - covered_phases
engines\procedure_setup\validator.py:318:    if cfg.total_phases != len(PHASE_ORDER):
engines\procedure_setup\validator.py:324:                    f" 标准阶段数 ({len(PHASE_ORDER)}) 不一致 / "
engines\procedure_setup\validator.py:326:                    f"standard phase count ({len(PHASE_ORDER)})"
engines\procedure_setup\validator.py:330:    if cfg.evidence_submission_deadline_days <= 0:
engines\procedure_setup\validator.py:335:                    "evidence_submission_deadline_days 必须大于 0 / "
engines\procedure_setup\validator.py:336:                    "evidence_submission_deadline_days must be greater than 0"
engines\procedure_setup\__init__.py:24:    PHASE_ORDER,
engines\procedure_setup\__init__.py:50:    "PHASE_ORDER",
engines\report_generation\docx_generator.py:69:    "rebuttal": "针对性反驳",


Cannot set property. Property setting is supported only on core types in this language mode.
At line:1 char:1
+ [Console]::OutputEncoding=[System.Text.Encoding]::UTF8;
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : InvalidOperation: (:) [], RuntimeException
    + FullyQualifiedErrorId : PropertySetterNotSupportedInConstrainedLanguage
 

 succeeded in 729ms:

engines\adversarial\round_engine.py:6:  Round 1 (claim):    原告提交主张+证据，被告提交抗辩+证据
engines\adversarial\round_engine.py:8:  Round 3 (rebuttal): 原告针对被告抗辩反驳，被告针对原告主张反驳
engines\adversarial\round_engine.py:76:        plaintiff_party_id: str,
engines\adversarial\round_engine.py:77:        defendant_party_id: str,
engines\adversarial\round_engine.py:85:            plaintiff_party_id:  原告方 party_id
engines\adversarial\round_engine.py:86:            defendant_party_id:  被告方 party_id
engines\adversarial\round_engine.py:104:            plaintiff = PlaintiffAgent(self._llm, plaintiff_party_id, 
self._config)
engines\adversarial\round_engine.py:105:            defendant = DefendantAgent(self._llm, defendant_party_id, 
self._config)
engines\adversarial\round_engine.py:111:                owner_party_id=plaintiff_party_id,
engines\adversarial\round_engine.py:116:                owner_party_id=defendant_party_id,
engines\adversarial\round_engine.py:189:            # 原被告反驳互不依赖，使用 asyncio.gather 并行执行以降低延迟。
engines\adversarial\round_engine.py:236:                plaintiff_party_id,
engines\adversarial\round_engine.py:237:                defendant_party_id,
engines\adversarial\round_engine.py:325:        plaintiff_party_id: str,
engines\adversarial\round_engine.py:326:        defendant_party_id: str,
engines\adversarial\round_engine.py:339:            # 判断原告侧该争点是否有证据
engines\adversarial\round_engine.py:347:                        missing_for_party_id=plaintiff_party_id,
engines\adversarial\round_engine.py:348:                        
description=f"争点「{issue.title}」原告方缺乏直接证据支撑",
engines\adversarial\round_engine.py:355:                        missing_for_party_id=defendant_party_id,
engines\adversarial\round_engine.py:356:                        
description=f"争点「{issue.title}」被告方缺乏直接证据支撑",
engines\adversarial\schemas.py:146:        default_factory=list, description="原告最强论证列表"
engines\adversarial\schemas.py:149:        default_factory=list, description="被告最强抗辩列表"
engines\adversarial\schemas.py:175:        default_factory=list, description="原告最有力论点（规则提取）"
engines\adversarial\schemas.py:178:        default_factory=list, description="被告最有力抗辩（规则提取）"
engines\adversarial\summarizer.py:58:      "position": "（原告最强论点，必须引用具体证据 ID，不超过 300 字）",
engines\adversarial\summarizer.py:66:      "position": "（被告最强抗辩，必须引用具体证据 ID，不超过 300 字）",
engines\adversarial\__init__.py:2:对抗性辩论引擎 — 原告/被告代理人 + 轮次编排器 + 语义总结层。
engines\case_extraction\extractor.py:44:1. 原被告姓名：直接从文中提取，无法确定填 "unknown"
engines\case_extraction\extractor.py:140:                
"从法律文本中提取案件结构化信息：原被告、案件类型、诉讼请求、证据和争议金额。"
engines\case_extraction\extractor.py:158:        # ── 原告 / Plaintiff 
──────────────────────────────────────────────────
engines\case_extraction\extractor.py:164:        # ── 被告 / Defendants 
─────────────────────────────────────────────────
engines\case_extraction\schemas.py:50:    submitter: str = 
Field(description="提交方：plaintiff（原告）、defendant（被告）或 unknown")
engines\case_extraction\schemas.py:64:    plaintiff_name: str = Field(description="原告姓名；若文中无法确定则填 
unknown")
engines\case_extraction\schemas.py:66:        description="被告姓名列表（可多人）；若无法确定则填 ['unknown']"
engines\document_assistance\schemas.py:61:    """起诉状骨架 — 原告方使用。
engines\document_assistance\schemas.py:92:    """答辩状骨架 — 被告方使用。
engines\document_assistance\schemas.py:98:        description="逐项否认原告主张的条目 / Items denying plaintiff's 
claims"
engines\document_assistance\schemas.py:101:        description="实质性抗辩主张条目（至少 1 条回应原告核心主张）/ 
Substantive defense claim items"
engines\document_assistance\schemas.py:104:        description="被告反请求或要求驳回原告诉请的条目 / Counter-prayer or 
dismissal request items"
engines\pretrial_conference\conference_engine.py:77:        plaintiff_party_id: str,
engines\pretrial_conference\conference_engine.py:78:        defendant_party_id: str,
engines\pretrial_conference\conference_engine.py:90:            plaintiff_party_id:      原告 party_id
engines\pretrial_conference\conference_engine.py:91:            defendant_party_id:      被告 party_id
engines\pretrial_conference\conference_engine.py:92:            plaintiff_evidence_ids:  原告要提交的证据 ID 列表
engines\pretrial_conference\conference_engine.py:93:            defendant_evidence_ids:  被告要提交的证据 ID 列表
engines\pretrial_conference\conference_engine.py:110:                plaintiff_party_id,
engines\pretrial_conference\conference_engine.py:116:                defendant_party_id,
engines\pretrial_conference\conference_engine.py:126:            plaintiff_party_id=plaintiff_party_id,
engines\pretrial_conference\conference_engine.py:127:            defendant_party_id=defendant_party_id,
engines\pretrial_conference\conference_engine.py:153:                plaintiff_party_id=plaintiff_party_id,
engines\pretrial_conference\conference_engine.py:154:                defendant_party_id=defendant_party_id,
engines\pretrial_conference\cross_examination_engine.py:77:        plaintiff_party_id: str,
engines\pretrial_conference\cross_examination_engine.py:78:        defendant_party_id: str,
engines\pretrial_conference\cross_examination_engine.py:102:        plaintiff_ev = [ev for ev in submitted if 
ev.owner_party_id == plaintiff_party_id]
engines\pretrial_conference\cross_examination_engine.py:103:        defendant_ev = [ev for ev in submitted if 
ev.owner_party_id == defendant_party_id]
engines\pretrial_conference\cross_examination_engine.py:107:        # 被告质证原告证据
engines\pretrial_conference\cross_examination_engine.py:111:                examiner_party_id=defendant_party_id,
engines\pretrial_conference\cross_examination_engine.py:112:                examiner_role="被告代理律师",
engines\pretrial_conference\cross_examination_engine.py:119:        # 原告质证被告证据
engines\pretrial_conference\cross_examination_engine.py:123:                examiner_party_id=plaintiff_party_id,
engines\pretrial_conference\cross_examination_engine.py:124:                examiner_role="原告代理律师",
engines\pretrial_conference\cross_examination_engine.py:133:            plaintiff_party_id: defendant_party_id,
engines\pretrial_conference\cross_examination_engine.py:134:            defendant_party_id: plaintiff_party_id,
engines\procedure_setup\planner.py:112:        "entry_conditions": ["案件登记完成", "原告起诉状已接收"],
engines\procedure_setup\planner.py:113:        "exit_conditions": ["被告已收到应诉通知", "双方当事人身份核实完毕"],
engines\procedure_setup\planner.py:129:        "exit_conditions": ["原告陈述意见完毕", "被告陈述意见完毕"],
engines\report_generation\docx_generator.py:150:            mapping[pid] = f"原告{name}方"
engines\report_generation\docx_generator.py:152:            mapping[pid] = f"被告{name}方"
engines\report_generation\docx_generator.py:325:    p_name = parties.get("plaintiff", {}).get("name", "原告")
engines\report_generation\docx_generator.py:326:    d_name = parties.get("defendant", {}).get("name", "被告")
engines\report_generation\docx_generator.py:417:                role_label = "[原告代理]"
engines\report_generation\docx_generator.py:419:                role_label = "[被告代理]"
engines\report_generation\docx_generator.py:472:    # 原告最强论点
engines\report_generation\docx_generator.py:475:        _styled(doc, "原告最强论点", bold=True, size=SZ_SECTION_HDR, 
color=CLR_BLUE)
engines\report_generation\docx_generator.py:484:    # NOTE: 被告最强抗辩 moved to _render_opponent_strategy_warning() 
to avoid duplication.
engines\report_generation\docx_generator.py:529:_PARTY_ZH = {"plaintiff": "原告", "defendant": "被告", "neutral": 
"中性"}
engines\report_generation\docx_generator.py:569:        party = {"plaintiff": "原告", "defendant": "被告", "neutral": 
"neutral"}.get(
engines\report_generation\docx_generator.py:796:    # --- Part 1: 被告核心抗辩及应对建议 ---
engines\report_generation\docx_generator.py:798:        _styled(doc, "被告核心抗辩及应对建议", bold=True, 
size=SZ_SECTION_HDR, color=CLR_RED)
engines\report_generation\docx_generator.py:1090:        "plaintiff": "原告视角",
engines\report_generation\docx_generator.py:1091:        "defendant": "被告视角",
engines\report_generation\docx_generator.py:1133:            doc.add_heading("B-1. 原告视角 「建议」", level=2)
engines\report_generation\docx_generator.py:1146:            doc.add_heading("B-2. 被告视角 「建议」", level=2)
engines\report_generation\docx_generator.py:1153:                _styled(doc, "原告可能补强方向：", bold=True, 
size=SZ_RISK, color=CLR_ORANGE)
engines\report_generation\docx_generator.py:1348:            ("原告主张", plaintiff_thesis[:500] + ("..." if 
len(plaintiff_thesis) > 500 else "")),
engines\report_generation\docx_generator.py:1349:            ("被告主张", defendant_thesis[:500] + ("..." if 
len(defendant_thesis) > 500 else "")),
engines\report_generation\docx_generator.py:1550:        pov_label = {"plaintiff": "原告", "defendant": 
"被告"}.get(pov, pov)
engines\report_generation\docx_generator.py:1604:                    doc.add_heading("被告攻击链预警 「推断」", level=3)
engines\report_generation\docx_generator.py:1633:                    doc.add_heading("原告可能补强方向 「推断」", 
level=3)
engines\report_generation\generator.py:202:            defense_chain: 原告方防御策略链（可选）/ PlaintiffDefenseChain 
(optional)
engines\report_generation\perspective_summary.py:160:        strengths.append(f"[原告] {getattr(arg, 'position', 
str(arg))}")
engines\report_generation\perspective_summary.py:162:        strengths.append(f"[被告] {getattr(arg, 'position', 
str(arg))}")
engines\report_generation\perspective_summary.py:204:        Perspective.PLAINTIFF: "原告视角 / Plaintiff Perspective",
engines\report_generation\perspective_summary.py:205:        Perspective.DEFENDANT: "被告视角 / Defendant Perspective",
engines\report_generation\perspective_summary.py:242:        Perspective.PLAINTIFF: "## Layer 3: 原告角色化输出 / 
Plaintiff Role Output",
engines\report_generation\perspective_summary.py:243:        Perspective.DEFENDANT: "## Layer 3: 被告角色化输出 / 
Defendant Role Output",
engines\report_generation\perspective_summary.py:265:            Perspective.DEFENDANT: "### 原告补强风险 / Plaintiff 
Supplement Risks",
engines\shared\consistency_checker.py:165:                    "建议原告",
engines\shared\consistency_checker.py:166:                    "建议被告",
engines\shared\consistency_checker.py:167:                    "原告应",
engines\shared\consistency_checker.py:168:                    "被告应",
engines\shared\consistency_checker.py:194:        """若整体态势偏被告、且最可能路径对被告有利，
engines\shared\consistency_checker.py:195:        则原告侧的建议（如 strategic_headline）不应呈现"全额稳拿"风格。
engines\shared\consistency_checker.py:211:            return True  # 非被告有利态势，无需校验
engines\shared\consistency_checker.py:213:        # 检查 strategic_headline 是否仍在暗示原告全额胜诉
engines\shared\consistency_checker.py:227:                    f"推荐一致性冲突：最可能路径对被告有利"
engines\shared\consistency_checker.py:340:        修订清单一-6：系统判断原告整体劣势时，不输出"全额稳拿"风格的动作建议。
engines\shared\consistency_checker.py:358:        # 如果最可能路径对被告有利，原告 action plan 不应含攻击性建议
engines\shared\consistency_checker.py:373:                                f"行动对齐冲突：整体态势偏被告"
engines\shared\consistency_checker.py:375:                                f"但原告建议含攻击性表述「{signal}」"
engines\shared\consistency_checker.py:380:        # 如果最可能路径对原告有利，被告 action plan 不应暗示"稳赢"
engines\shared\consistency_checker.py:385:                    overconfident = ["必胜", "稳赢", "原告必败"]
engines\shared\consistency_checker.py:390:                                f"行动对齐冲突：整体态势偏原告"
engines\shared\consistency_checker.py:392:                                f"但被告建议含「{signal}」"
engines\shared\consistency_checker.py:433:                    "推荐一致性冲突：首位路径对被告更有利"
engines\shared\display_resolver.py:82:    Includes the probability estimate when available (e.g. "原告全额支持 (72%)").
engines\similar_case_search\keyword_extractor.py:127:                role_zh = "原告" if "plaintiff" in role else 
"被告"
engines\similar_case_search\keyword_extractor.py:144:            parts.append("被告抗辩：")
engines\similar_case_search\relevance_ranker.py:158:                role_zh = "原告" if "plaintiff" in role else "被告"


Cannot set property. Property setting is supported only on core types in this language mode.
At line:1 char:1
+ [Console]::OutputEncoding=[System.Text.Encoding]::UTF8;
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : InvalidOperation: (:) [], RuntimeException
    + FullyQualifiedErrorId : PropertySetterNotSupportedInConstrainedLanguage
 

codex
The hidden coupling list is getting long: `procedure_setup`, `pretrial_conference`, `adversarial`, `case_extraction`, `case_structuring/case_extractor`, `document_assistance`, `report_generation/docx_generator`, and `report_generation/v3` all encode civil-only party roles or amount semantics in code or tests. The plan’s blast-radius model is materially understated.
2026-04-07T11:31:45.926086Z ERROR codex_core::tools::router: error=`"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -NoProfile -Command "Select-String -Path 'engines\\shared\\models\\*.py','engines\\shared\\*.py' -Pattern 'plaintiff|defendant|原告|被告|prosecutor|行政机关|case_type'"` rejected: blocked by policy
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -NoProfile -Command "Select-String -Path 'engines\\shared\\models\\*.py','engines\\shared\\*.py' -Pattern 'plaintiff|defendant|原告|被告|prosecutor|行政机关|case_type'" in C:/Users/david/dev/case-adversarial-engine
 declined in 0ms:
`"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -NoProfile -Command "Select-String -Path 'engines\\shared\\models\\*.py','engines\\shared\\*.py' -Pattern 'plaintiff|defendant|原告|被告|prosecutor|行政机关|case_type'"` rejected: blocked by policy
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -NoProfile -Command "Select-String -Path 'engines\\shared\\models\\*.py' -Pattern 'plaintiff|defendant|原告|被告|prosecutor|行政机关|case_type'" in C:/Users/david/dev/case-adversarial-engine
 succeeded in 601ms:

engines\shared\models\analysis.py:233:    case_type: str = Field(default="civil")
engines\shared\models\analysis.py:274:    case_type: str = Field(default="civil")
engines\shared\models\analysis.py:352:        description="本 section 的视角：neutral=中立评估, plaintiff=原告策略, 
defendant=被告策略",
engines\shared\models\analysis.py:567:        ..., min_length=1, description="建议针对的当事方类型：plaintiff / 
defendant"
engines\shared\models\analysis.py:577:    party_type: str = Field(..., min_length=1, description="plaintiff / 
defendant")
engines\shared\models\analysis.py:615:    plaintiff_action_plan: Optional[PartyActionPlan] = None
engines\shared\models\analysis.py:616:    defendant_action_plan: Optional[PartyActionPlan] = None
engines\shared\models\analysis.py:741:    - formal_claim:            正式诉请金额（原告实际起诉数额）
engines\shared\models\analysis.py:750:    formal_claim: Decimal = Field(..., ge=0, 
description="正式诉请金额（原告实际起诉数额）")
engines\shared\models\analysis.py:787:        ..., description="最可能胜诉方：plaintiff / defendant / uncertain"
engines\shared\models\analysis.py:924:        description="绑定的 
PlaintiffDefenseChain.chain_id（可回连），防御链未启用时为 None",
engines\shared\models\civil_loan.py:127:    """争议款项归因记录。记录原被告对同一笔款项的不同立场。"""
engines\shared\models\civil_loan.py:132:    plaintiff_attribution: str = Field(default="", description="原告立场")
engines\shared\models\civil_loan.py:133:    defendant_attribution: str = Field(default="", description="被告立场")
engines\shared\models\civil_loan.py:254:    民间借贷专属：仅 CRED-07 (credibility_scorer) 在原告方使用此结构判定职业
engines\shared\models\core.py:200:    plaintiff_agent = "plaintiff_agent"
engines\shared\models\core.py:201:    defendant_agent = "defendant_agent"
engines\shared\models\core.py:316:    plaintiff = "plaintiff"
engines\shared\models\core.py:317:    defendant = "defendant"
engines\shared\models\pipeline.py:217:    party_favored: str = Field(..., description="对哪方有利：plaintiff / 
defendant / neutral")
engines\shared\models\pipeline.py:268:        description="本路径结果对哪方有利：plaintiff / defendant / neutral",
engines\shared\models\pipeline.py:302:    plaintiff_best_path: Optional[str] = Field(
engines\shared\models\pipeline.py:303:        default=None, description="对原告最有利的路径 ID（plaintiff_favored 
路径中概率最高）"
engines\shared\models\pipeline.py:305:    defendant_best_path: Optional[str] = Field(
engines\shared\models\pipeline.py:306:        default=None, description="对被告最有利的路径 ID（defendant_favored 
路径中概率最高）"
engines\shared\models\pipeline.py:334:    为原告和被告各生成一份。


Cannot set property. Property setting is supported only on core types in this language mode.
At line:1 char:1
+ [Console]::OutputEncoding=[System.Text.Encoding]::UTF8;
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : InvalidOperation: (:) [], RuntimeException
    + FullyQualifiedErrorId : PropertySetterNotSupportedInConstrainedLanguage
 

exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -NoProfile -Command "Get-Content 'engines/shared/models/core.py' | Select-Object -First 360" in C:/Users/david/dev/case-adversarial-engine
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -NoProfile -Command "Get-Content 'engines/shared/models/analysis.py' | Select-Object -First 860" in C:/Users/david/dev/case-adversarial-engine
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -NoProfile -Command "Get-Content 'engines/shared/models/pipeline.py' | Select-Object -First 360" in C:/Users/david/dev/case-adversarial-engine
 succeeded in 645ms:
"""
æµæ°´çº¿ä¸ŽåŸºç¡€è®¾æ–½æ¨¡åž‹ / Pipeline and infrastructure models.

åŒ…å«è¿è¡Œå¿«ç…§ã€é•¿ä»»åŠ¡ã€é‡‘é¢è®¡ç®—ã€è£åˆ¤è·¯å¾„æ ‘å’Œæ”»å‡»é“¾æ¨¡åž‹ã€?
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional, Union  # Any needed for JobError.details

from pydantic import BaseModel, Field, model_validator

from engines.shared.models.core import (
    BlockingConditionType,
    JobStatus,
)

# Backward-compat re-exports for civil-loan amount-calculation models.
# Unit 22 Phase A physically isolated these into engines.shared.models.civil_loan;
# pipeline.py still re-exports them so existing
# `from engines.shared.models.pipeline import LoanTransaction` style imports keep working.
from engines.shared.models.civil_loan import (  # noqa: F401  (re-export)
    AmountCalculationReport,
    AmountConflict,
    AmountConsistencyCheck,
    ClaimCalculationEntry,
    DisputedAmountAttribution,
    InterestRecalculation,
    LoanTransaction,
    RepaymentTransaction,
)


# ---------------------------------------------------------------------------
# ç´¢å¼•å¼•ç”¨æ¨¡åž‹ / Index reference models
# ---------------------------------------------------------------------------


class MaterialRef(BaseModel):
    """ææ–™ç´¢å¼•å¼•ç”¨ã€?""

    index_name: str = Field(default="material_index")
    object_type: str
    object_id: str = Field(..., min_length=1)
    storage_ref: str = Field(..., min_length=1)


class ArtifactRef(BaseModel):
    """äº§ç‰©ç´¢å¼•å¼•ç”¨ã€?""

    index_name: str = Field(default="artifact_index")
    object_type: str
    object_id: str = Field(..., min_length=1)
    storage_ref: str = Field(..., min_length=1)


class InputSnapshot(BaseModel):
    """è¿è¡Œè¾“å…¥å¿«ç…§ã€?""

    material_refs: list[MaterialRef] = Field(default_factory=list)
    artifact_refs: list[ArtifactRef] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# åŸºç¡€è®¾æ–½ / Infrastructure
# ---------------------------------------------------------------------------


class ExtractionMetadata(BaseModel):
    """æå–è¿‡ç¨‹å…ƒä¿¡æ¯ï¼Œprompt_profile æŒä¹…åŒ–äºŽæ­¤ä»¥æ”¯æŒé‡æ”¾ã€?""

    model_used: str = Field(default="")
    temperature: float = Field(default=0.0)
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    )
    prompt_profile: str = Field(default="")
    prompt_version: str = Field(default="")
    total_tokens: int = Field(default=0)


class Run(BaseModel):
    """æ‰§è¡Œå¿«ç…§ï¼Œå¯¹åº?schemas/procedure/run.schema.jsonã€?
    output_refs æŽ¥å— material_ref | artifact_refï¼ˆper B7 schema fixï¼‰ã€?
    """

    run_id: str = Field(..., min_length=1)
    case_id: str = Field(..., min_length=1)
    workspace_id: str = Field(..., min_length=1)
    scenario_id: Optional[str] = None
    trigger_type: str = Field(..., min_length=1)
    input_snapshot: InputSnapshot
    output_refs: list[Union[MaterialRef, ArtifactRef]] = Field(default_factory=list)
    started_at: str
    finished_at: Optional[str] = None
    status: str


# ---------------------------------------------------------------------------
# é•¿ä»»åŠ¡å±‚ / Long-running job layer
# ---------------------------------------------------------------------------


class JobError(BaseModel):
    """é•¿ä»»åŠ¡ç»“æž„åŒ–é”™è¯¯ã€‚å¯¹åº?schemas/indexing.schema.json#/$defs/job_errorã€?""

    code: str = Field(..., min_length=1)
    message: str = Field(..., min_length=1)
    details: Optional[dict[str, Any]] = None


class Job(BaseModel):
    """é•¿ä»»åŠ¡çŠ¶æ€ä¸Žè¿›åº¦è¿½è¸ªã€‚å¯¹åº?schemas/procedure/job.schema.jsonã€?

    model_validator å¼ºåˆ¶ä»¥ä¸‹ invariantsï¼?
    - created:   progress=0.0, result_ref=null, error=null
    - pending:   0 <= progress < 1, result_ref=null, error=null
    - running:   0 <= progress < 1, result_ref=null, error=null
    - completed: progress=1.0, result_refâ‰ null, error=null
    - failed:    progress < 1, result_ref=null, errorâ‰ null
    - cancelled: progress < 1, result_ref=null, error=null
    """

    job_id: str = Field(..., min_length=1)
    case_id: str = Field(..., min_length=1)
    workspace_id: str = Field(..., min_length=1)
    job_type: str = Field(..., min_length=1)
    job_status: JobStatus
    progress: float = Field(..., ge=0.0, le=1.0)
    message: Optional[str] = None
    result_ref: Optional[ArtifactRef] = None
    error: Optional[JobError] = None
    created_at: str
    updated_at: str

    @model_validator(mode="after")
    def _validate_status_invariants(self) -> "Job":
        s = self.job_status
        p = self.progress
        r = self.result_ref
        e = self.error

        if s == JobStatus.created:
            if p != 0.0:
                raise ValueError("created job must have progress=0.0")
            if r is not None:
                raise ValueError("created job must have result_ref=null")
            if e is not None:
                raise ValueError("created job must have error=null")

        elif s in (JobStatus.pending, JobStatus.running):
            if p >= 1.0:
                raise ValueError(f"{s.value} job progress must be < 1.0")
            if r is not None:
                raise ValueError(f"{s.value} job must have result_ref=null")
            if e is not None:
                raise ValueError(f"{s.value} job must have error=null")

        elif s == JobStatus.completed:
            if p != 1.0:
                raise ValueError("completed job must have progress=1.0")
            if r is None:
                raise ValueError("completed job must have a valid result_ref")
            if e is not None:
                raise ValueError("completed job must have error=null")

        elif s == JobStatus.failed:
            if p >= 1.0:
                raise ValueError("failed job progress must be < 1.0")
            if r is not None:
                raise ValueError("failed job must have result_ref=null")
            if e is None:
                raise ValueError("failed job must have a structured error")

        elif s == JobStatus.cancelled:
            if p >= 1.0:
                raise ValueError("cancelled job progress must be < 1.0")
            if r is not None:
                raise ValueError("cancelled job must have result_ref=null")
            if e is not None:
                raise ValueError("cancelled job must have error=null")

        return self


# ---------------------------------------------------------------------------
# é‡‘é¢è®¡ç®—å±?/ Amount calculation layer  (P0.2)
# ---------------------------------------------------------------------------
# è¿™äº›ç±»å·²ç‰©ç†è¿ç§»è‡?engines.shared.models.civil_loan (Unit 22 Phase A)ã€?
# pipeline.py é¡¶éƒ¨é€šè¿‡ re-export ä¿æŒå‘åŽå…¼å®¹ã€‚è¯¦è§æ¨¡å—é¡¶éƒ?importã€?


# ---------------------------------------------------------------------------
# è£åˆ¤è·¯å¾„æ ?/ Decision path tree  (P0.3)
# ---------------------------------------------------------------------------


class ConfidenceInterval(BaseModel):
    """ç½®ä¿¡åº¦åŒºé—´ã€‚ä»…åœ?verdict_block_active=False æ—¶å…è®¸å¡«å†™ã€?""

    lower: float = Field(..., ge=0.0, le=1.0, description="ç½®ä¿¡åº¦åŒºé—´ä¸‹ç•?[0,1]")
    upper: float = Field(..., ge=0.0, le=1.0, description="ç½®ä¿¡åº¦åŒºé—´ä¸Šç•?[0,1]")

    @model_validator(mode="after")
    def _lower_le_upper(self) -> "ConfidenceInterval":
        if self.lower > self.upper:
            raise ValueError(f"lower ({self.lower}) must be <= upper ({self.upper})")
        return self


class PathRankingItem(BaseModel):
    """è·¯å¾„æ¦‚çŽ‡æŽ’åºæ¡ç›®ã€‚DecisionPathTree.path_ranking åˆ—è¡¨å…ƒç´ ã€?""

    path_id: str = Field(..., min_length=1, description="è·¯å¾„ ID")
    probability: float = Field(..., ge=0.0, le=1.0, description="è·¯å¾„è§¦å‘æ¦‚çŽ‡")
    party_favored: str = Field(..., description="å¯¹å“ªæ–¹æœ‰åˆ©ï¼šplaintiff / defendant / neutral")
    key_conditions: list[str] = Field(
        default_factory=list, description="è§¦å‘æœ¬è·¯å¾„éœ€æ»¡è¶³çš„å…³é”®æ¡ä»¶ï¼ˆæ–‡å­—æè¿°åˆ—è¡¨ï¼?
    )


class DecisionPath(BaseModel):
    """å•æ¡è£åˆ¤è·¯å¾„ã€?""

    path_id: str = Field(..., min_length=1)
    trigger_condition: str = Field(..., min_length=1, description="è§¦å‘æœ¬è·¯å¾„çš„å…³é”®æ¡ä»¶æè¿°")
    trigger_issue_ids: list[str] = Field(
        default_factory=list, description="è§¦å‘æ¡ä»¶å…³è”çš„äº‰ç‚?ID åˆ—è¡¨"
    )
    key_evidence_ids: list[str] = Field(
        default_factory=list,
        description="æœ¬è·¯å¾„ä¾èµ–çš„å…³é”®è¯æ® ID åˆ—è¡¨ï¼ˆä»…å«æ”¯æŒæœ¬è·¯å¾„ç»“è®ºçš„è¯æ®ï¼‰",
    )
    counter_evidence_ids: list[str] = Field(
        default_factory=list,
        description="ä¸Žæœ¬è·¯å¾„ç»“è®ºç›¸æ‚–çš„è¯æ?ID åˆ—è¡¨ï¼ˆåé©?å¯¹ç«‹è¯æ®ï¼Œä¸å¾—ä¸Ž key_evidence_ids é‡å ï¼?,
    )
    possible_outcome: str = Field(..., min_length=1, description="å¯èƒ½çš„è£åˆ¤ç»“æžœæè¿?)
    confidence_interval: Optional[ConfidenceInterval] = Field(
        default=None, description="ç½®ä¿¡åº¦åŒºé—´ï¼›verdict_block_active=True æ—¶å¿…é¡»ä¸º None"
    )
    path_notes: str = Field(default="", description="è·¯å¾„å¤‡æ³¨")
    # v1.5: è·¯å¾„å¯æ‰§è¡ŒåŒ–æ‰©å±•å­—æ®µ
    admissibility_gate: list[str] = Field(
        default_factory=list,
        description="æœ¬è·¯å¾„æˆç«‹å‰æï¼šå“ªäº›è¯æ®å¿…é¡»è¢«æ³•åº­é‡‡ä¿¡ï¼ˆevidence_id åˆ—è¡¨ï¼?,
    )
    result_scope: list[str] = Field(
        default_factory=list,
        description="è£åˆ¤èŒƒå›´æ ‡ç­¾ï¼šprincipal/interest/liability_allocation ç­?,
    )
    fallback_path_id: Optional[str] = Field(
        default=None, description="æœ¬è·¯å¾„å¤±è´¥æ—¶é™çº§åˆ°å“ªæ¡è·¯å¾„çš„ path_id"
    )
    # v1.6: æ¦‚çŽ‡è¯„åˆ†
    probability: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="è·¯å¾„è§¦å‘æ¦‚çŽ‡ï¼?-1ï¼‰ï¼ŒåŸºäºŽè¯æ®æ”¯æ’‘åº¦ã€é˜»æ–­æ¡ä»¶å¯æ»¡è¶³æ€§åŠæ³•å¾‹å…ˆä¾‹å¯¹é½åº?,
    )
    probability_rationale: str = Field(
        default="", description="æ¦‚çŽ‡è¯„ä¼°ä¾æ®ï¼ˆæ”¯æ’‘è¯æ®è´¨é‡ã€é˜»æ–­æ¡ä»¶æ»¡è¶³æƒ…å†µç­‰ï¼?
    )
    party_favored: str = Field(
        default="neutral",
        description="æœ¬è·¯å¾„ç»“æžœå¯¹å“ªæ–¹æœ‰åˆ©ï¼šplaintiff / defendant / neutral",
    )


class BlockingCondition(BaseModel):
    """é˜»æ–­ç¨³å®šåˆ¤æ–­çš„æ¡ä»¶ã€?""

    condition_id: str = Field(..., min_length=1)
    condition_type: BlockingConditionType
    description: str = Field(..., min_length=1)
    linked_issue_ids: list[str] = Field(default_factory=list)
    linked_evidence_ids: list[str] = Field(default_factory=list)


class DecisionPathTree(BaseModel):
    """è£åˆ¤è·¯å¾„æ ‘ã€‚P0.3 äº§ç‰©ï¼Œçº³å…?CaseWorkspace.artifact_indexï¼ˆç”±è°ƒç”¨æ–¹è´Ÿè´£æ³¨å†Œï¼Œå?P0.1/P0.2ï¼‰ã€?
    æ›¿ä»£ AdversarialSummary.overall_assessment çš„æ®µè½å¼ç»¼åˆè¯„ä¼°ã€?
    overall_assessment çš„æ±‡æ€»å¡«å……ï¼ˆå„è·¯å¾?possible_outcome æ‘˜è¦ï¼‰ç”±è°ƒç”¨æ–¹è´Ÿè´£ï¼Œä¸åœ¨æœ¬æ¨¡å—å®žçŽ°ã€?
    """

    tree_id: str = Field(..., min_length=1)
    case_id: str = Field(..., min_length=1)
    run_id: str = Field(..., min_length=1)
    paths: list[DecisionPath] = Field(
        default_factory=list, description="è£åˆ¤è·¯å¾„åˆ—è¡¨ï¼ˆå»ºè®?3-6 æ¡ï¼‰"
    )
    blocking_conditions: list[BlockingCondition] = Field(
        default_factory=list, description="å½“å‰é˜»æ–­ç¨³å®šåˆ¤æ–­çš„æ¡ä»¶åˆ—è¡?
    )
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    )
    # v1.6: è·¯å¾„æ¦‚çŽ‡æ¯”è¾ƒç»“æžœ
    most_likely_path: Optional[str] = Field(default=None, description="æ¦‚çŽ‡æœ€é«˜çš„è·¯å¾„ ID")
    plaintiff_best_path: Optional[str] = Field(
        default=None, description="å¯¹åŽŸå‘Šæœ€æœ‰åˆ©çš„è·¯å¾?IDï¼ˆplaintiff_favored è·¯å¾„ä¸­æ¦‚çŽ‡æœ€é«˜ï¼‰"
    )
    defendant_best_path: Optional[str] = Field(
        default=None, description="å¯¹è¢«å‘Šæœ€æœ‰åˆ©çš„è·¯å¾?IDï¼ˆdefendant_favored è·¯å¾„ä¸­æ¦‚çŽ‡æœ€é«˜ï¼‰"
    )
    path_ranking: list[PathRankingItem] = Field(
        default_factory=list, description="è·¯å¾„æŒ‰æ¦‚çŽ‡é™åºæŽ’åˆ—çš„æŽ’ååˆ—è¡¨"
    )


# ---------------------------------------------------------------------------
# P0.4ï¼šæœ€å¼ºæ”»å‡»é“¾
# ---------------------------------------------------------------------------


class AttackNode(BaseModel):
    """å•ä¸ªæ”»å‡»èŠ‚ç‚¹ã€‚OptimalAttackChain.top_attacks åˆ—è¡¨å…ƒç´ ï¼ˆè§„åˆ™å±‚ä¿è¯æ°å¥½ 3 ä¸ªï¼‰ã€?""

    attack_node_id: str = Field(..., min_length=1, description="æ”»å‡»èŠ‚ç‚¹å”¯ä¸€æ ‡è¯†")
    target_issue_id: str = Field(..., min_length=1, description="æ”»å‡»ç›®æ ‡äº‰ç‚¹ ID")
    attack_description: str = Field(..., min_length=1, description="æ”»å‡»è®ºç‚¹æè¿°")
    success_conditions: str = Field(default="", description="æ”»å‡»æˆåŠŸæ¡ä»¶")
    supporting_evidence_ids: list[str] = Field(
        ..., min_length=1, description="æ”¯æ’‘æ­¤æ”»å‡»ç‚¹çš„è¯æ?ID åˆ—è¡¨ï¼ˆä¸å¾—ä¸ºç©ºï¼‰"
    )
    counter_measure: str = Field(default="", description="æˆ‘æ–¹å¯¹æ­¤æ”»å‡»ç‚¹çš„ååˆ¶åŠ¨ä½œ")
    adversary_pivot_strategy: str = Field(default="", description="å¯¹æ–¹è¡¥è¯åŽæˆ‘æ–¹ç­–ç•¥åˆ‡æ¢è¯´æ˜?)


class OptimalAttackChain(BaseModel):
    """æŸä¸€æ–¹çš„æœ€ä¼˜æ”»å‡»é¡ºåºä¸Žååˆ¶å‡†å¤‡ã€‚P0.4 äº§ç‰©ï¼Œçº³å…?CaseWorkspace.artifact_indexã€?
    ä¸ºåŽŸå‘Šå’Œè¢«å‘Šå„ç”Ÿæˆä¸€ä»½ã€?
    """

    chain_id: str = Field(..., min_length=1)
    case_id: str = Field(..., min_length=1)
    run_id: str = Field(..., min_length=1)
    owner_party_id: str = Field(..., min_length=1, description="ç”Ÿæˆæ–¹å½“äº‹äºº ID")
    top_attacks: list[AttackNode] = Field(
        default_factory=list,
        description="æœ€ä¼˜æ”»å‡»ç‚¹ï¼Œè§„åˆ™å±‚ä¿è¯æ°å¥½ 3 ä¸ªï¼›LLM å¤±è´¥æ—¶ä¸ºç©ºåˆ—è¡?,
    )
    recommended_order: list[str] = Field(
        default_factory=list,
        description="æŽ¨èæ”»å‡»é¡ºåºï¼ˆæœ‰åº?attack_node_id åˆ—è¡¨ï¼‰ï¼Œä¸?top_attacks å®Œå…¨å¯¹åº”",
    )
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    )
Cannot set property. Property setting is supported only on core types in this language mode.
At line:1 char:1
+ [Console]::OutputEncoding=[System.Text.Encoding]::UTF8;
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : InvalidOperation: (:) [], RuntimeException
    + FullyQualifiedErrorId : PropertySetterNotSupportedInConstrainedLanguage
 

 succeeded in 666ms:
"""
æ ¸å¿ƒæžšä¸¾ä¸ŽåŸºç¡€ç±»åž‹ / Core enumerations and foundational types.

åŒ…å«æ‰€æœ‰æžšä¸¾ã€RawMaterial è¾“å…¥æ¨¡åž‹ï¼Œä»¥å?LLMClient åè®®å®šä¹‰ã€?
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# æžšä¸¾ç±»åž‹ / Enumerations
# ---------------------------------------------------------------------------


class CaseType(str, Enum):
    """æ¡ˆä»¶ç±»åž‹æžšä¸¾ï¼ˆschema-level canonicalï¼‰ã€?""

    civil = "civil"
    criminal = "criminal"
    admin = "admin"


class PromptProfile(str, Enum):
    """æç¤ºæ¨¡æ¿ keyï¼ˆengine-levelï¼‰ã€‚NOT a CaseType value."""

    civil_loan = "civil_loan"
    labor_dispute = "labor_dispute"
    real_estate = "real_estate"


class AccessDomain(str, Enum):
    """è¯æ®å¯è§åŸŸã€?""

    owner_private = "owner_private"
    shared_common = "shared_common"
    admitted_record = "admitted_record"


class EvidenceStatus(str, Enum):
    """è¯æ®ç”Ÿå‘½å‘¨æœŸçŠ¶æ€ã€?""

    private = "private"
    submitted = "submitted"
    challenged = "challenged"
    admitted_for_discussion = "admitted_for_discussion"


class EvidenceType(str, Enum):
    """è¯æ®ç±»åž‹æžšä¸¾ï¼Œå¯¹åº”ã€Šæ°‘äº‹è¯‰è®¼æ³•ã€‹è¯æ®ç§ç±»ã€?""

    documentary = "documentary"
    physical = "physical"
    witness_statement = "witness_statement"
    electronic_data = "electronic_data"
    expert_opinion = "expert_opinion"
    audio_visual = "audio_visual"
    other = "other"


class IssueType(str, Enum):
    """äº‰ç‚¹ç±»åž‹ã€?""

    factual = "factual"
    legal = "legal"
    procedural = "procedural"
    mixed = "mixed"


class IssueStatus(str, Enum):
    """äº‰ç‚¹å½“å‰çŠ¶æ€ã€?""

    open = "open"
    resolved = "resolved"
    deferred = "deferred"


class PropositionStatus(str, Enum):
    """äº‹å®žå‘½é¢˜æ ¸å®žçŠ¶æ€ã€?""

    unverified = "unverified"
    supported = "supported"
    contradicted = "contradicted"
    disputed = "disputed"


class BurdenStatus(str, Enum):
    """ä¸¾è¯è´£ä»»å®ŒæˆçŠ¶æ€ã€?""

    met = "met"
    partially_met = "partially_met"
    not_met = "not_met"
    disputed = "disputed"


class StatementClass(str, Enum):
    """ç»“è®ºé™ˆè¿°åˆ†ç±»ã€?""

    fact = "fact"
    inference = "inference"
    assumption = "assumption"


class WorkflowStage(str, Enum):
    """äº§å“å·¥ä½œæµé˜¶æ®µã€?""

    case_structuring = "case_structuring"
    procedure_setup = "procedure_setup"
    simulation_run = "simulation_run"
    report_generation = "report_generation"
    interactive_followup = "interactive_followup"


class ProcedurePhase(str, Enum):
    """æ³•å¾‹ç¨‹åºé˜¶æ®µã€?""

    case_intake = "case_intake"
    element_mapping = "element_mapping"
    opening = "opening"
    evidence_submission = "evidence_submission"
    evidence_challenge = "evidence_challenge"
    judge_questions = "judge_questions"
    rebuttal = "rebuttal"
    output_branching = "output_branching"


class ProcedureState(BaseModel):
    """ç¨‹åºé˜¶æ®µçš„è®¿é—®æŽ§åˆ¶çŠ¶æ€?â€?v1.5 æ–°å¢žã€?

    å½“ä¼ é€’ç»™ AccessController.filter_evidence_for_agent() æ—¶ï¼Œ
    åœ¨è§’è‰²çº§è§„åˆ™ä¹‹ä¸Šå åŠ é˜¶æ®µçº§è¿‡æ»¤ï¼š
    - evidence.access_domain å¿…é¡»åœ?readable_access_domains å†?
    - evidence.status å¿…é¡»åœ?admissible_evidence_statuses å†?
    """

    phase: ProcedurePhase
    readable_access_domains: list[AccessDomain]
    admissible_evidence_statuses: list[EvidenceStatus]


class ChangeItemObjectType(str, Enum):
    """change_item ç›®æ ‡å¯¹è±¡ç±»åž‹æžšä¸¾ã€?""

    Party = "Party"
    Claim = "Claim"
    Defense = "Defense"
    Issue = "Issue"
    Evidence = "Evidence"
    Burden = "Burden"
    ProcedureState = "ProcedureState"
    AgentOutput = "AgentOutput"
    ReportArtifact = "ReportArtifact"


class DiffDirection(str, Enum):
    """å·®å¼‚æ–¹å‘æžšä¸¾ã€?""

    strengthen = "strengthen"
    weaken = "weaken"
    neutral = "neutral"


class ScenarioStatus(str, Enum):
    """åœºæ™¯ç”Ÿå‘½å‘¨æœŸçŠ¶æ€ã€?""

    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"


class JobStatus(str, Enum):
    """é•¿ä»»åŠ¡ç”Ÿå‘½å‘¨æœŸçŠ¶æ€ã€‚å¯¹åº?schemas/indexing.schema.json#/$defs/job_statusã€?""

    created = "created"
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class RiskImpactObject(str, Enum):
    """é£Žé™©å½±å“å¯¹è±¡ç»´åº¦æžšä¸¾ã€‚å¯¹åº?docs/03_case_object_model.md risk_impact_objectã€?""

    win_rate = "win_rate"
    supported_amount = "supported_amount"
    trial_credibility = "trial_credibility"
    procedural_stability = "procedural_stability"
    evidence_supplement_cost = "evidence_supplement_cost"


class AgentRole(str, Enum):
    """ä»£ç†è§’è‰²ç¼–ç ã€‚å¯¹åº?docs/03_case_object_model.md Party.role_code å’?AgentOutput.agent_role_codeã€?""

    plaintiff_agent = "plaintiff_agent"
    defendant_agent = "defendant_agent"
    judge_agent = "judge_agent"
    evidence_manager = "evidence_manager"


class DisputeResolutionStatus(str, Enum):
    """äº‰è®®è§£å†³çŠ¶æ€ã€?""

    resolved = "resolved"
    unresolved = "unresolved"
    partially_resolved = "partially_resolved"


class OutcomeImpact(str, Enum):
    """äº‰ç‚¹å¯¹æœ€ç»ˆè£åˆ¤ç»“æžœçš„å½±å“ç¨‹åº¦ï¼ˆP0.1ï¼‰ã€?""

    high = "high"
    medium = "medium"
    low = "low"


class EvidenceStrength(str, Enum):
    """ä¸»å¼ æ–¹è¯æ®å¼ºåº¦ï¼ˆP0.1ï¼‰ã€?""

    strong = "strong"
    medium = "medium"
    weak = "weak"


class AttackStrength(str, Enum):
    """åå¯¹æ–¹æ”»å‡»å¼ºåº¦ï¼ˆP0.1ï¼‰ã€?""

    strong = "strong"
    medium = "medium"
    weak = "weak"


class RecommendedAction(str, Enum):
    """ç³»ç»Ÿå»ºè®®è¡ŒåŠ¨ï¼ˆP0.1ï¼‰ã€?""

    supplement_evidence = "supplement_evidence"
    amend_claim = "amend_claim"
    abandon = "abandon"
    explain_in_trial = "explain_in_trial"


class AuthenticityRisk(str, Enum):
    """è¯æ®çœŸå®žæ€§é£Žé™©ï¼ˆP1.5ï¼‰ã€?""

    high = "high"
    medium = "medium"
    low = "low"


class SupplementCost(str, Enum):
    """è¡¥è¯æˆæœ¬ï¼ˆP1.7ï¼‰ã€?""

    high = "high"
    medium = "medium"
    low = "low"


class RelevanceScore(str, Enum):
    """è¯æ®å…³è”æ€§ï¼ˆP1.5ï¼‰ã€?""

    strong = "strong"
    medium = "medium"
    weak = "weak"


class ProbativeValue(str, Enum):
    """è¯æ®è¯æ˜ŽåŠ›ï¼ˆP1.5ï¼‰ã€?""

    strong = "strong"
    medium = "medium"
    weak = "weak"


class Vulnerability(str, Enum):
    """è¯æ®æ˜“å—å¯¹æ–¹æ”»å‡»çš„é£Žé™©ï¼ˆP1.5ï¼‰ã€?""

    high = "high"
    medium = "medium"
    low = "low"


class LegalityRisk(str, Enum):
    """è¯æ®åˆæ³•æ€§é£Žé™©ï¼ˆv1.5 è´¨è¯å››ç»´åº¦ä¹‹ä¸€ï¼‰ã€?""

    high = "high"
    medium = "medium"
    low = "low"


class ContractValidity(str, Enum):
    """åˆåŒæ•ˆåŠ›çŠ¶æ€?â€?å½±å“åˆ©æ¯è®¡ç®—æ ‡å‡†ã€?""

    valid = "valid"
    disputed = "disputed"
    invalid = "invalid"


class IssueCategory(str, Enum):
    """äº‰ç‚¹åˆ†æžç±»åž‹ï¼ˆP1.6ï¼‰ã€‚ä¸Ž issue_type å¹¶åˆ—ï¼Œä¸æ›¿ä»£ã€?""

    fact_issue = "fact_issue"
    legal_issue = "legal_issue"
    calculation_issue = "calculation_issue"
    procedure_credibility_issue = "procedure_credibility_issue"


class Perspective(str, Enum):
    """è¾“å‡ºè§†è§’æ ‡æ³¨ï¼ˆv7ï¼‰ã€‚æ¯ä¸?section/å»ºè®®å¿…é¡»æ˜¾å¼æ ‡æ³¨è§†è§’ã€?""

    neutral = "neutral"
    plaintiff = "plaintiff"
    defendant = "defendant"


class AdmissibilityStatus(str, Enum):
    """è¯æ®å¯é‡‡æ€§çŠ¶æ€ï¼ˆv7 å¯é‡‡æ€§é—¸é—¨ï¼‰ã€?""

    clear = "clear"  # è¯æ®å¯é‡‡æ€§æ— äº‰è®®
    uncertain = "uncertain"  # å¯é‡‡æ€§å­˜ç–?
    weak = "weak"  # å¯é‡‡æ€§è¾ƒå¼±ï¼Œå¯èƒ½è¢«æŽ’é™?
    excluded = "excluded"  # å·²è¢«æŽ’é™¤


class OutcomeImpactSize(str, Enum):
    """è¡¥è¯åŽå¯¹ç»“æžœçš„å½±å“å¤§å°ï¼ˆP1.7ï¼‰ã€?""

    significant = "significant"
    moderate = "moderate"
    marginal = "marginal"


class PracticallyObtainable(str, Enum):
    """è¯æ®çŽ°å®žå¯å–å¾—æ€§ï¼ˆP1.7ï¼‰ã€?""

    yes = "yes"
    no = "no"
    uncertain = "uncertain"


class BlockingConditionType(str, Enum):
    """é˜»æ–­æ¡ä»¶ç±»åž‹ã€?""

    amount_conflict = "amount_conflict"
    evidence_gap = "evidence_gap"
    procedure_unresolved = "procedure_unresolved"


# ---------------------------------------------------------------------------
# åŸºç¡€è¾“å…¥æ¨¡åž‹ / Basic input models
# ---------------------------------------------------------------------------


class RawMaterial(BaseModel):
    """åŽŸå§‹æ¡ˆä»¶ææ–™æ®µè½ï¼Œç”±è°ƒç”¨æ–¹æä¾›ã€?""

Cannot set property. Property setting is supported only on core types in this language mode.
At line:1 char:1
+ [Console]::OutputEncoding=[System.Text.Encoding]::UTF8;
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : InvalidOperation: (:) [], RuntimeException
    + FullyQualifiedErrorId : PropertySetterNotSupportedInConstrainedLanguage
 

 succeeded in 701ms:
"""
åˆ†æžå±‚æ¨¡åž?/ Analysis layer models.

åŒ…å«æ ¸å¿ƒæ¡ˆä»¶å¯¹è±¡ã€æŠ¥å‘Šäº§ç‰©ã€å¯¹æŠ—å±‚å’Œæ‰€æœ‰åˆ†æžç»“æžœæ¨¡åž‹ã€?
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Optional, Union

from pydantic import BaseModel, Field, model_validator

from engines.shared.models.core import (
    AccessDomain,
    AdmissibilityStatus,
    AgentRole,
    AttackStrength,
    AuthenticityRisk,
    BurdenStatus,
    EvidenceStatus,
    EvidenceStrength,
    EvidenceType,
    IssueCategory,
    IssueStatus,
    IssueType,
    LegalityRisk,
    OutcomeImpact,
    OutcomeImpactSize,
    Perspective,
    PracticallyObtainable,
    ProbativeValue,
    ProcedurePhase,
    PropositionStatus,
    RecommendedAction,
    RelevanceScore,
    RiskImpactObject,
    StatementClass,
    SupplementCost,
    Vulnerability,
)


# ---------------------------------------------------------------------------
# æ ¸å¿ƒæ¡ˆä»¶å¯¹è±¡ / Core case objects
# ---------------------------------------------------------------------------


class Evidence(BaseModel):
    """ç»“æž„åŒ–è¯æ®å¯¹è±¡ã€‚Tier 1 å­—æ®µå¯¹åº” evidence.schema.jsonã€?""

    evidence_id: str = Field(..., min_length=1)
    case_id: str = Field(..., min_length=1)
    owner_party_id: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1)
    source: str = Field(..., min_length=1)
    summary: str = Field(..., min_length=1)
    evidence_type: EvidenceType
    target_fact_ids: list[str] = Field(..., min_length=1)
    target_issue_ids: list[str] = Field(default_factory=list)
    access_domain: AccessDomain = AccessDomain.owner_private
    status: EvidenceStatus = EvidenceStatus.private
    submitted_by_party_id: Optional[str] = None
    challenged_by_party_ids: list[str] = Field(default_factory=list)
    admissibility_notes: Optional[str] = None
    admissibility_risk: Optional[str] = (
        None  # P1 æ–°å¢žï¼šå¯é‡‡æ€§é£Žé™©è¯´æ˜Žï¼ˆå¦‚æ¥æºäº‰è®®ã€å–è¯ç¨‹åºç‘•ç–µç­‰ï¼?
    )
    # P1.5: è¯æ®æƒé‡è¯„åˆ†æ‰©å±•å­—æ®µï¼ˆå‘åŽå…¼å®¹ï¼Œå…¨éƒ¨ Optionalï¼?
    authenticity_risk: Optional[AuthenticityRisk] = None
    relevance_score: Optional[RelevanceScore] = None
    probative_value: Optional[ProbativeValue] = None
    legality_risk: Optional[LegalityRisk] = None
    vulnerability: Optional[Vulnerability] = None
    evidence_weight_scored: bool = False
    # P2.9: å¯ä¿¡åº¦æŠ˜æŸæ‰©å±•å­—æ®µï¼ˆå‘åŽå…¼å®¹ï¼ŒOptional/é»˜è®¤å€¼ï¼‰
    is_copy_only: bool = Field(default=False, description="å…³é”®è¯æ®ä»…æœ‰å¤å°ä»¶æ— åŽŸä»¶ï¼ˆCRED-02ï¼?)
    # å¯é‡‡æ€§é—¨æŽ§æ‰©å±•å­—æ®µï¼ˆå‘åŽå…¼å®¹ï¼Œå…¨éƒ¨æœ‰é»˜è®¤å€¼ï¼‰
    admissibility_score: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="è¯æ®å¯é‡‡æ€§è¯„åˆ?(1.0=å®Œå…¨å¯é‡‡, 0.0=è¢«æŽ’é™¤ï¼›ç”?AdmissibilityEvaluator å¡«å……)",
    )
    admissibility_challenges: list[str] = Field(
        default_factory=list,
        description="è¯æ®è¢«è´¨ç–‘å¯é‡‡æ€§çš„ç†ç”±åˆ—è¡¨ï¼ˆå¦‚å½•éŸ³åˆæ³•æ€§ã€ä¼ é—»è§„åˆ™ç­‰ï¼?,
    )
    exclusion_impact: Optional[str] = Field(
        default=None,
        description="è¯¥è¯æ®è¢«æŽ’é™¤åŽå¯¹æ¡ˆä»¶çš„å½±å“æè¿°ï¼ˆç”?AdmissibilityEvaluator å¡«å……ï¼?,
    )
    # v7: è¯æ®å…³è”ä¸Žå¯¹æŠ—æ‰©å±•å­—æ®?
    admissibility_status: AdmissibilityStatus = Field(
        default=AdmissibilityStatus.clear,
        description="å¯é‡‡æ€§çŠ¶æ€æžšä¸¾ï¼šclear/uncertain/weak/excludedï¼ˆv7 å¯é‡‡æ€§é—¸é—¨ï¼‰",
    )
    supports: list[str] = Field(
        default_factory=list,
        description="è¯¥è¯æ®æ”¯æŒçš„äº‰ç‚¹ issue_id åˆ—è¡¨ï¼ˆæ­£å‘å…³è”ï¼‰",
    )
    is_attacked_by: list[str] = Field(
        default_factory=list,
        description="æ”»å‡»/åé©³è¯¥è¯æ®çš„å…¶ä»–è¯æ® evidence_id åˆ—è¡¨",
    )
    stability_score: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="è¯æ®ç¨³å®šæ€?(0-1)ï¼šå³ä½¿è¢«è´¨è¯ä¹Ÿä¸å®¹æ˜“å´©çš„ç¨‹åº¦ã€‚åŒºåˆ«äºŽ probative_value(å†²å‡»åŠ?ã€?
        "stability_score ä¼˜å…ˆäº?probative_value å‚ä¸ŽæŽ’åºã€?,
    )
    support_strength: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="è¯æ®æ”¯æ’‘å¼ºåº¦ (0-1)ï¼šè¡¨é¢ç›´è§‚è¯´æœåŠ›ã€?,
    )
    counter_evidence_strength: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="å¯¹ç«‹è¯æ®å¼ºåº¦ (0-1)ï¼šåé©³è¯¥è¯æ®çš„åŠ›åº¦ã€?,
    )
    dispute_ratio: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="äº‰è®®æ¯?(0-1)ï¼šcounter_evidence_strength / (support_strength + counter_evidence_strength)ã€?
        "é«˜å€¼è¡¨æ˜Žè¯¥è¯æ®è¢«å¼ºåè¯ã€æŽ’åºæ—¶åº”è‡ªåŠ¨é™æƒã€?,
    )


class FactProposition(BaseModel):
    """äº‹å®žå‘½é¢˜ â€?è¿žæŽ¥è¯æ®ä¸Žäº‰ç‚¹çš„æ¡¥æ¢ã€?""

    proposition_id: str = Field(..., min_length=1)
    text: str = Field(..., min_length=1)
    status: PropositionStatus = PropositionStatus.unverified
    linked_evidence_ids: list[str] = Field(default_factory=list)


class Issue(BaseModel):
    """äº‰ç‚¹å¯¹è±¡ã€‚Tier 1 å¯¹åº” issue.schema.jsonï¼›Tier 2 ä¸?docs/03 å‰çž»å­—æ®µï¼ˆOptionalï¼‰ã€?""

    issue_id: str = Field(..., min_length=1)
    case_id: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1)
    issue_type: IssueType
    parent_issue_id: Optional[str] = None
    related_claim_ids: list[str] = Field(default_factory=list)
    related_defense_ids: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    burden_ids: list[str] = Field(default_factory=list)
    fact_propositions: list[FactProposition] = Field(default_factory=list)
    status: IssueStatus = IssueStatus.open
    created_at: Optional[str] = None
    # Tier 2: docs/03 å‰çž»å­—æ®µ
    description: Optional[str] = None
    priority: Optional[str] = None
    # P0.1: äº‰ç‚¹å½±å“æŽ’åºæ‰©å±•å­—æ®µï¼ˆå‘åŽå…¼å®¹ï¼Œå…¨éƒ¨ Optionalï¼?
    outcome_impact: Optional[OutcomeImpact] = None
    # Unit 22 Phase C: weakened from list[ImpactTarget] to list[str] for case-type
    # neutrality. The legal vocabulary is now governed by the active CaseTypePlugin
    # (see issue_impact_ranker._resolve_impact_targets and the per-case-type
    # ALLOWED_IMPACT_TARGETS constant on each prompt module). Unknown values are
    # filtered at the ranker layer; the model itself accepts any string so that
    # åŠ³åŠ¨äº‰è®® / æˆ¿å±‹ä¹°å– / æ°‘é—´å€Ÿè´· etc. can each contribute their own domain
    # vocabulary without depending on civil_loan-named enum members.
    impact_targets: list[str] = Field(default_factory=list)
    proponent_evidence_strength: Optional[EvidenceStrength] = None
    opponent_attack_strength: Optional[AttackStrength] = None
    recommended_action: Optional[RecommendedAction] = None
    recommended_action_basis: Optional[str] = None  # recommended_action çš„ä¾æ®è¯´æ˜?
    # P0.1 v2: åŠ æƒè¯„åˆ†ç»´åº¦ï¼ˆå‘åŽå…¼å®¹ï¼Œå…¨éƒ¨ Optionalï¼?
    importance_score: Optional[int] = Field(
        default=None, ge=0, le=100, description="äº‰ç‚¹å¯¹æœ€ç»ˆè£åˆ¤çš„å…³é”®ç¨‹åº¦ (0-100)"
    )
    swing_score: Optional[int] = Field(
        default=None, ge=0, le=100, description="äº‰ç‚¹ç»“è®ºç¿»è½¬å¯¹ç»“æžœçš„æ‘†å¹… (0-100)"
    )
    evidence_strength_gap: Optional[int] = Field(
        default=None,
        ge=-100,
        le=100,
        description="ä¸»å¼ æ–¹è¯æ®å¼ºåº¦å‡åŽ»åå¯¹æ–¹æ”»å‡»å¼ºåº¦ (-100 to +100)",
    )
    dependency_depth: Optional[int] = Field(
        default=None, ge=0, description="0=æ ¹äº‰ç‚¹ï¼Œ1+=ä¾èµ–ä¸Šæ¸¸äº‰ç‚¹"
    )
    credibility_impact: Optional[int] = Field(
        default=None, ge=0, le=100, description="å¯¹æ•´æ¡ˆå¯ä¿¡åº¦çš„å†²å‡?(0-100)"
    )
    composite_score: Optional[float] = Field(
        default=None, description="åŠ æƒç»¼åˆåˆ†ï¼ˆè§„åˆ™å±‚è®¡ç®—ï¼Œè¶Šé«˜è¶Šé‡è¦ï¼‰"
    )
    # P1.6: äº‰ç‚¹ç±»åž‹åˆ†ç±»æ‰©å±•å­—æ®µï¼ˆå‘åŽå…¼å®¹ï¼ŒOptionalï¼?
    issue_category: Optional[IssueCategory] = None
    # P1 æ–°å¢žï¼šäº‰ç‚¹ä¾èµ–å…³ç³»ï¼ˆä¸Šæ¸¸äº‰ç‚¹ issue_id åˆ—è¡¨ï¼›ç©ºåˆ—è¡¨è¡¨ç¤ºæ ¹äº‰ç‚¹ï¼‰
    depends_on: list[str] = Field(default_factory=list)
    # v7: çœŸæ­£å†³å®šè£åˆ¤çš„å­é—®é¢˜ï¼ˆäºŒ-2ï¼?
    decisive_sub_question: Optional[str] = Field(
        default=None,
        description="çœŸæ­£å†³å®šè£åˆ¤ç»“æžœçš„æ ¸å¿ƒå­é—®é¢˜ï¼ˆå¦‚'å€Ÿæ¬¾åˆæ„æ˜¯å¦æˆç«‹'ï¼‰ï¼Œç”?LLM è¯„ä¼°å¡«å……",
    )


class Burden(BaseModel):
    """ä¸¾è¯è´£ä»»å¯¹è±¡ã€‚canonical å­—æ®µåä½¿ç”?burden_party_idï¼ˆdocs/03ï¼‰ã€?""

    burden_id: str = Field(..., min_length=1)
    case_id: str = Field(..., min_length=1)
    issue_id: str = Field(..., min_length=1)
    burden_party_id: str = Field(..., min_length=1, description="æ‰¿æ‹…ä¸¾è¯è´£ä»»çš„å½“äº‹æ–¹ party_id")
    proof_standard: str = Field(default="")
    legal_basis: str = Field(default="")
    status: BurdenStatus = BurdenStatus.not_met
    # å‘åŽå…¼å®¹å­—æ®µï¼ˆå¼•æ“Žä»£ç åŽŸæœ‰ï¼‰
    description: Optional[str] = None
    # Tier 2: docs/03 å‰çž»å­—æ®µ
    burden_type: Optional[str] = None
    fact_proposition: Optional[str] = None
    shift_condition: Optional[str] = None


class Claim(BaseModel):
    """è¯‰è¯·å¯¹è±¡ã€?""

    claim_id: str = Field(..., min_length=1)
    case_id: str = Field(..., min_length=1)
    owner_party_id: str = Field(..., min_length=1)
    case_type: str = Field(default="civil")
    title: str = Field(..., min_length=1)
    claim_text: str = Field(default="")
    claim_category: str = Field(default="")
    target_issue_ids: list[str] = Field(default_factory=list)
    supporting_fact_ids: list[str] = Field(default_factory=list)
    supporting_evidence_ids: list[str] = Field(default_factory=list)
    status: str = Field(default="open")


class Defense(BaseModel):
    """æŠ—è¾©å¯¹è±¡ã€?""

    defense_id: str = Field(..., min_length=1)
    case_id: str = Field(..., min_length=1)
    owner_party_id: str = Field(..., min_length=1)
    against_claim_id: str = Field(..., min_length=1)
    defense_text: str = Field(default="")
    defense_category: str = Field(default="")
    target_issue_ids: list[str] = Field(default_factory=list)
    supporting_fact_ids: list[str] = Field(default_factory=list)
    supporting_evidence_ids: list[str] = Field(default_factory=list)
    status: str = Field(default="open")


# LitigationHistory has been physically isolated to engines.shared.models.civil_loan
# (Unit 22 Phase B). It is re-exported below for backward compatibility, and
# Party.litigation_history is now typed as a neutral dict[str, Any] so that the
# generic case-object layer no longer carriesæ°‘é—´å€Ÿè´·-specific fields.
from engines.shared.models.civil_loan import LitigationHistory  # noqa: F401  (re-export)


class Party(BaseModel):
    """æ¡ˆä»¶å‚ä¸Žä¸»ä½“ã€?""

    party_id: str = Field(..., min_length=1)
    case_id: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    party_type: str = Field(..., min_length=1)
    role_code: str = Field(..., min_length=1)
    side: str = Field(..., min_length=1)
    case_type: str = Field(default="civil")
    access_domain_scope: list[str] = Field(default_factory=list)
    active: bool = True
    # v1.5 bugfix: èŒä¸šæ”¾è´·äººæ£€æµ‹æ‰©å±•å­—æ®µï¼ˆUnit 22 Phase B èµ·æ”¹ä¸?dict ä»?
    # ç§»é™¤å¯?civil_loan æ¨¡åž‹çš„ç¡¬ä¾èµ–ï¼›è°ƒç”¨æ–¹æŒ?dict[str, Any] è¯»å†™ï¼Œå¿…è¦æ—¶
    # é€šè¿‡ LitigationHistory.model_validate / model_dump è½¬æ¢ï¼?
    litigation_history: Optional[dict[str, Any]] = None


# ---------------------------------------------------------------------------
# èšåˆäº§ç‰© / Aggregate artifacts
# ---------------------------------------------------------------------------


class ClaimIssueMapping(BaseModel):
    """è¯‰è¯·åˆ°äº‰ç‚¹çš„æ˜ å°„ã€?""

    claim_id: str = Field(..., min_length=1)
    issue_ids: list[str] = Field(..., min_length=1)


class DefenseIssueMapping(BaseModel):
    """æŠ—è¾©åˆ°äº‰ç‚¹çš„æ˜ å°„ã€?""

    defense_id: str = Field(..., min_length=1)
    issue_ids: list[str] = Field(..., min_length=1)


class EvidenceIndex(BaseModel):
    """è¯æ®ç´¢å¼•å·¥ä½œæ ¼å¼ï¼ˆéžç£ç›˜ artifact envelopeï¼‰ã€?""

    case_id: str = Field(..., min_length=1)
    evidence: list[Evidence]
    extraction_metadata: Optional[dict[str, Any]] = None


class IssueTree(BaseModel):
    """äº‰ç‚¹æ ‘äº§ç‰©ï¼Œå¯¹åº” schemas/case/issue_tree.schema.jsonã€?""

    case_id: str = Field(..., min_length=1)
    run_id: Optional[str] = None
    job_id: Optional[str] = None
    issues: list[Issue] = Field(default_factory=list)
    burdens: list[Burden] = Field(default_factory=list)
    claim_issue_mapping: list[ClaimIssueMapping] = Field(default_factory=list)
    defense_issue_mapping: list[DefenseIssueMapping] = Field(default_factory=list)
    extraction_metadata: Optional[dict[str, Any]] = None


# ---------------------------------------------------------------------------
# æŠ¥å‘Šå±?/ Report layer
# ---------------------------------------------------------------------------


class KeyConclusion(BaseModel):
    """æŠ¥å‘Šç« èŠ‚å…³é”®ç»“è®ºã€?""

    conclusion_id: str = Field(..., min_length=1)
    text: str = Field(..., min_length=1)
    statement_class: StatementClass
    supporting_evidence_ids: list[str] = Field(..., description="è‡³å°‘ä¸€æ¡æ”¯æŒè¯¥ç»“è®ºçš„è¯æ?ID")
    supporting_output_ids: list[str] = Field(default_factory=list)


class ReportSection(BaseModel):
    """æŠ¥å‘Šç« èŠ‚ã€‚v7 èµ·æ¯ä¸?section å¿…é¡»æ ‡æ³¨è§†è§’ã€ç½®ä¿¡åº¦å’Œä¾èµ–ã€?""

    section_id: str = Field(..., min_length=1)
    section_index: int = Field(..., ge=1)
    title: str = Field(..., min_length=1)
    body: str = Field(..., min_length=1)
    linked_issue_ids: list[str] = Field(default_factory=list)
    linked_output_ids: list[str] = Field(default_factory=list)
    linked_evidence_ids: list[str] = Field(..., description="ç« èŠ‚å¼•ç”¨çš„è¯æ?ID åˆ—è¡¨")
    key_conclusions: list[KeyConclusion] = Field(default_factory=list)
    # v7: section é¡¶éƒ¨å…ƒæ•°æ?
    perspective: Perspective = Field(
        default=Perspective.neutral,
        description="æœ?section çš„è§†è§’ï¼šneutral=ä¸­ç«‹è¯„ä¼°, plaintiff=åŽŸå‘Šç­–ç•¥, defendant=è¢«å‘Šç­–ç•¥",
    )
    confidence: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="æœ?section ç»“è®ºç½®ä¿¡åº?(0-1)",
    )
    section_depends_on: list[str] = Field(
        default_factory=list,
        description="æœ?section ä¾èµ–çš„å…¶ä»?section_id åˆ—è¡¨ï¼ˆç”¨äºŽä¸€è‡´æ€§æ ¡éªŒçš„æ‹“æ‰‘æŽ’åºï¼?,
    )


class ReportArtifact(BaseModel):
    """è¯Šæ–­æŠ¥å‘Šäº§ç‰©ã€?""

    report_id: str = Field(..., min_length=1)
    case_id: str = Field(..., min_length=1)
    run_id: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1)
    summary: str = Field(..., min_length=1)
    sections: list[ReportSection]
    created_at: Optional[str] = None
    # Tier 2: docs/03 å‰çž»å­—æ®µ
    linked_output_ids: list[str] = Field(default_factory=list)
    linked_evidence_ids: list[str] = Field(default_factory=list)
    extraction_metadata: Optional[dict[str, Any]] = None


class InteractionTurn(BaseModel):
    """å•æ¬¡è¿½é—®è®°å½•ã€?""

    turn_id: str = Field(..., min_length=1)
    case_id: str = Field(..., min_length=1)
    report_id: str = Field(..., min_length=1)
    run_id: str = Field(..., min_length=1)
    turn_index: Optional[int] = None
    question: str = Field(..., min_length=1)
    answer: str = Field(..., min_length=1)
    issue_ids: list[str] = Field(...)
    evidence_ids: list[str] = Field(...)
    statement_class: StatementClass
    created_at: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None


# ---------------------------------------------------------------------------
# å¯¹æŠ—å±?/ Adversarial layer
# ---------------------------------------------------------------------------


class RiskFlag(BaseModel):
    """é£Žé™©æ ‡è®°ç»“æž„ä½“ã€‚å¯¹åº?docs/03_case_object_model.md RiskFlagã€?

    constraints:
    - flag_id:               éžç©º
    - description:           éžç©ºï¼ˆå¯¹åº”åŽŸ str å†…å®¹ï¼Œä¿æŒè¯­ä¹‰å…¼å®¹ï¼‰
    - impact_objects:        impact_objects_scored=True æ—¶å¿…é¡»éžç©?
    - impact_objects_scored: False è¡¨ç¤ºè¿‡æ¸¡æœŸè‡ªåŠ¨å‡çº§çš„æ—§æ•°æ?
    """

    flag_id: str = Field(..., min_length=1)
    description: str = Field(..., min_length=1)
    impact_objects: list[RiskImpactObject] = Field(default_factory=list)
    impact_objects_scored: bool = Field(default=True)

    @model_validator(mode="after")
    def _check_impact_objects_when_scored(self) -> "RiskFlag":
        if self.impact_objects_scored and len(self.impact_objects) == 0:
            raise ValueError(
                "impact_objects must not be empty when impact_objects_scored=True; "
                "set impact_objects_scored=False for legacy-migrated data"
            )
        return self


class AgentOutput(BaseModel):
    """è§’è‰²åœ¨æŸä¸€ç¨‹åºå›žåˆçš„è§„èŒƒåŒ–è¾“å‡ºã€‚å¯¹åº?docs/03_case_object_model.md AgentOutputã€?

    constraintsï¼ˆç”± Field çº¦æŸå¼ºåˆ¶ï¼‰ï¼š
    - issue_ids:          éžç©ºï¼ˆè‡³å°‘ç»‘å®šä¸€ä¸ªäº‰ç‚¹ï¼‰
    - evidence_citations: éžç©ºï¼ˆæ‰€æœ‰å…³é”®ç»“è®ºå¿…é¡»å¼•ç”¨å…·ä½“è¯æ?IDï¼?
    - round_index:        >= 0
    """

    output_id: str = Field(..., min_length=1)
    case_id: str = Field(..., min_length=1)
    run_id: str = Field(..., min_length=1)
    state_id: str = Field(..., min_length=1)
    phase: ProcedurePhase
    round_index: int = Field(..., ge=0)
    agent_role_code: str = Field(..., min_length=1)
    owner_party_id: str = Field(..., min_length=1)
    issue_ids: list[str] = Field(
        ..., min_length=1, description="å¿…é¡»éžç©ºï¼›æ¯æ¡è¾“å‡ºéƒ½å¿…é¡»ç»‘å®šè‡³å°‘ä¸€ä¸ªäº‰ç‚?
    )
    title: str = Field(..., min_length=1)
    body: str = Field(..., min_length=1)
    evidence_citations: list[str] = Field(
        ..., min_length=1, description="å¿…é¡»éžç©ºï¼›æ‰€æœ‰å…³é”®ç»“è®ºå¿…é¡»å¼•ç”¨å…·ä½“è¯æ?ID"
    )
    statement_class: StatementClass
    risk_flags: list[RiskFlag] = Field(
        default_factory=list,
        description="é£Žé™©æ ‡è®°åˆ—è¡¨ã€‚v1.5 èµ·åªæŽ¥å— RiskFlag å¯¹è±¡ï¼Œä¸å†æŽ¥å?strã€?,
    )
    created_at: str


# ---------------------------------------------------------------------------
# P1.7ï¼šç¼ºè¯?ROI æŽ’åº / Evidence gap ROI ranking
# ---------------------------------------------------------------------------


class EvidenceGapItem(BaseModel):
    """ç¼ºè¯é¡¹åŠå…¶è¡¥è¯ä»·å€¼è¯„ä¼°ã€‚P1.7 äº§ç‰©ï¼Œçº³å…?CaseWorkspace.artifact_indexã€?

    roi_rank ç”±è§„åˆ™å±‚ï¼ˆEvidenceGapROIRankerï¼‰è‡ªåŠ¨è®¡ç®—ï¼Œè°ƒç”¨æ–¹ä¸å¾—æ‰‹åŠ¨èµ‹å€¼ã€?
    """

    gap_id: str = Field(..., min_length=1, description="ç¼ºè¯é¡¹å”¯ä¸€æ ‡è¯†")
    case_id: str = Field(..., min_length=1, description="æ¡ˆä»¶ ID")
    run_id: str = Field(..., min_length=1, description="è¿è¡Œå¿«ç…§ ID")
    related_issue_id: str = Field(..., min_length=1, description="å…³è”äº‰ç‚¹ IDï¼Œå¿…é¡»ç»‘å®?)
    gap_description: str = Field(..., min_length=1, description="ç¼ºè¯è¯´æ˜Ž")
    supplement_cost: SupplementCost = Field(..., description="é¢„è®¡è¡¥è¯æˆæœ¬")
    outcome_impact_size: OutcomeImpactSize = Field(..., description="è¡¥è¯åŽé¢„è®¡å¯¹ç»“æžœçš„å½±å“å¤§å°?)
    practically_obtainable: PracticallyObtainable = Field(..., description="çŽ°å®žä¸­æ˜¯å¦å¯å–å¾—")
    alternative_evidence_paths: list[str] = Field(
        default_factory=list, description="æ›¿ä»£è¯æ®è·¯å¾„è¯´æ˜Ž"
    )
    roi_rank: int = Field(..., ge=1, description="ROI æŽ’åºåºå·ï¼ˆè§„åˆ™å±‚è‡ªåŠ¨è®¡ç®—ï¼?=æœ€é«˜ä¼˜å…ˆï¼‰")


# ---------------------------------------------------------------------------
# P1.8ï¼šè¡ŒåŠ¨å»ºè®®å¼•æ“?/ Action recommendation  (P1.8)
# ---------------------------------------------------------------------------


class ClaimAmendmentSuggestion(BaseModel):
    """å»ºè®®ä¿®æ”¹è¯‰è¯·æ¡ç›®ï¼ˆP1.8ï¼‰ã€‚P2.11 å®žè£…åŽï¼ŒåŒä¸€ original_claim_id çš„è¯¦ç»†æ›¿ä»£æ–¹æ¡ˆç”±
    AlternativeClaimSuggestion æä¾›å¹¶æ›¿ä»£æœ¬æ¡ç›®ã€?

    Args:
        suggestion_id:                  å»ºè®®æ¡ç›®å”¯ä¸€æ ‡è¯†
        original_claim_id:              å…³è”åŽŸå§‹ Claim.claim_id
        amendment_description:          å»ºè®®ä¿®æ”¹æ–¹å‘ï¼ˆç®€è¦ï¼Œä¸å«å®Œæ•´æ›¿ä»£æ–‡æœ¬ï¼?
        amendment_reason_issue_id:      ä¿®æ”¹ä¾æ®ç»‘å®šäº‰ç‚¹ IDï¼ˆé›¶å®¹å¿ç©ºå€¼ï¼‰
        amendment_reason_evidence_ids:  ä¿®æ”¹ä¾æ®å…³è”è¯æ® ID åˆ—è¡¨ï¼ˆå¯ä¸ºç©ºåˆ—è¡¨ï¼?
    """

    suggestion_id: str = Field(..., min_length=1)
    original_claim_id: str = Field(..., min_length=1)
    amendment_description: str = Field(..., min_length=1, description="ç®€è¦ä¿®æ”¹æ–¹å?)
    amendment_reason_issue_id: str = Field(
        ..., min_length=1, description="ä¿®æ”¹ä¾æ®äº‰ç‚¹ IDï¼ˆé›¶å®¹å¿ç©ºå€¼ï¼‰"
    )
    amendment_reason_evidence_ids: list[str] = Field(
        default_factory=list, description="ä¿®æ”¹ä¾æ®å…³è”è¯æ® ID åˆ—è¡¨"
    )
    # v1.5: è·¯å¾„-è¡ŒåŠ¨è¿žæŽ¥ï¼ˆmedium closed loopï¼?
    impacted_path_ids: list[str] = Field(
        default_factory=list,
        description="æœ¬å»ºè®®å½±å“çš„è£åˆ¤è·¯å¾„ ID åˆ—è¡¨ï¼ˆæ¥è‡?P0.3 DecisionPath.path_idï¼?,
    )


class ClaimAbandonSuggestion(BaseModel):
    """å»ºè®®æ”¾å¼ƒè¯‰è¯·æ¡ç›®ï¼ˆP1.8ï¼‰ã€‚æ¯æ¡å¿…é¡»ç»‘å®?issue_id å’Œæ”¾å¼ƒç†ç”±â€”â€”é›¶å®¹å¿ã€?

    Args:
        suggestion_id:           å»ºè®®æ¡ç›®å”¯ä¸€æ ‡è¯†
        claim_id:                å»ºè®®æ”¾å¼ƒçš?Claim.claim_id
        abandon_reason:          æ”¾å¼ƒç†ç”±ï¼ˆéžç©ºï¼‰
        abandon_reason_issue_id: æ”¾å¼ƒä¾æ®äº‰ç‚¹ IDï¼ˆé›¶å®¹å¿ç©ºå€¼ï¼‰
    """

    suggestion_id: str = Field(..., min_length=1)
    claim_id: str = Field(..., min_length=1)
    abandon_reason: str = Field(..., min_length=1, description="æ”¾å¼ƒç†ç”±ï¼ˆé›¶å®¹å¿ç©ºå€¼ï¼‰")
    abandon_reason_issue_id: str = Field(
        ..., min_length=1, description="æ”¾å¼ƒä¾æ®äº‰ç‚¹ IDï¼ˆé›¶å®¹å¿ç©ºå€¼ï¼‰"
    )
    # v1.5: è·¯å¾„-è¡ŒåŠ¨è¿žæŽ¥ï¼ˆmedium closed loopï¼?
    impacted_path_ids: list[str] = Field(
        default_factory=list,
        description="æœ¬å»ºè®®å½±å“çš„è£åˆ¤è·¯å¾„ ID åˆ—è¡¨ï¼ˆæ¥è‡?P0.3 DecisionPath.path_idï¼?,
    )


class TrialExplanationPriority(BaseModel):
    """åº­å®¡ä¸­ä¼˜å…ˆè§£é‡Šäº‹é¡¹ï¼ˆP1.8ï¼‰ã€‚æ¯æ¡å¿…é¡»ç»‘å®?issue_idâ€”â€”é›¶å®¹å¿ã€?

    Args:
        priority_id:      æ¡ç›®å”¯ä¸€æ ‡è¯†
        issue_id:         ç»‘å®šäº‰ç‚¹ IDï¼ˆé›¶å®¹å¿ç©ºå€¼ï¼‰
        explanation_text: éœ€è§£é‡Šçš„äº‹é¡¹æè¿°ï¼ˆéžç©ºï¼?
    """

    priority_id: str = Field(..., min_length=1)
    issue_id: str = Field(..., min_length=1, description="ç»‘å®šäº‰ç‚¹ IDï¼ˆé›¶å®¹å¿ç©ºå€¼ï¼‰")
    explanation_text: str = Field(..., min_length=1, description="åº­å®¡è§£é‡Šäº‹é¡¹è¯´æ˜Ž")
    # v1.5: è·¯å¾„-è¡ŒåŠ¨è¿žæŽ¥ï¼ˆmedium closed loopï¼?
    impacted_path_ids: list[str] = Field(
        default_factory=list,
        description="æœ¬åº­å®¡äº‹é¡¹å½±å“çš„è£åˆ¤è·¯å¾„ ID åˆ—è¡¨ï¼ˆæ¥è‡?P0.3 DecisionPath.path_idï¼?,
    )


class StrategicRecommendation(BaseModel):
    """æ¡ˆåž‹é€‚é…çš„ç­–ç•¥æ€§å»ºè®®ï¼ˆP1.8 v2ï¼‰ã€‚ç”± LLM ç­–ç•¥å±‚ç”Ÿæˆã€?""

    recommendation_text: str = Field(..., min_length=1, description="ç­–ç•¥å»ºè®®æ–‡æœ¬")
    target_party: str = Field(
        ..., min_length=1, description="å»ºè®®é’ˆå¯¹çš„å½“äº‹æ–¹ç±»åž‹ï¼šplaintiff / defendant"
    )
    linked_issue_ids: list[str] = Field(default_factory=list, description="å»ºè®®å…³è”çš„äº‰ç‚?ID")
    priority: int = Field(default=1, ge=1, le=5, description="ä¼˜å…ˆçº?1-5, 1=æœ€é«?)
    rationale: str = Field(default="", description="ç­–ç•¥ä¾æ®è¯´æ˜Ž")


class PartyActionPlan(BaseModel):
    """å•æ–¹è¡ŒåŠ¨è®¡åˆ’ï¼ˆP1.8 v2ï¼‰ã€‚èšåˆè§„åˆ™å±‚ç»“æž„è¡ŒåŠ¨å’?LLM ç­–ç•¥å»ºè®®ã€?""

    party_type: str = Field(..., min_length=1, description="plaintiff / defendant")
    structural_actions: list[str] = Field(
        default_factory=list, description="æ¥è‡ªè§„åˆ™å±‚çš„è¡ŒåŠ¨ ID åˆ—è¡¨"
    )
    strategic_recommendations: list[StrategicRecommendation] = Field(
        default_factory=list, description="æ¥è‡ª LLM çš„ç­–ç•¥æ€§å»ºè®?
    )


class ActionRecommendation(BaseModel):
    """è¡ŒåŠ¨å»ºè®®äº§ç‰©ï¼ˆP1.8ï¼‰ã€‚çº³å…?CaseWorkspace.artifact_indexã€?

    åœ?report_generation é˜¶æ®µç”?ActionRecommender ç”Ÿæˆï¼Œä¾èµ?P0.1 äº‰ç‚¹åˆ†æžå’?P1.7 ROI æŽ’åºç»“æžœã€?

    Args:
        recommendation_id:              äº§ç‰©å”¯ä¸€æ ‡è¯†
        case_id:                        æ¡ˆä»¶ ID
        run_id:                         è¿è¡Œå¿«ç…§ ID
        recommended_claim_amendments:   å»ºè®®ä¿®æ”¹è¯‰è¯·æ¡ç›®åˆ—è¡¨ï¼ˆClaimAmendmentSuggestion[]ï¼?
        evidence_supplement_priorities: å»ºè®®è¡¥å¼ºè¯æ®çš?gap_id åˆ—è¡¨ï¼ˆæŒ‰ ROI æŽ’åºï¼?
        trial_explanation_priorities:   åº­å®¡ä¼˜å…ˆè§£é‡Šäº‹é¡¹åˆ—è¡¨ï¼ˆæ¯æ¡ç»‘å®?issue_idï¼?
        claims_to_abandon:              å»ºè®®æ”¾å¼ƒè¯‰è¯·æ¡ç›®åˆ—è¡¨ï¼ˆClaimAbandonSuggestion[]ï¼?
        created_at:                     ISO-8601 æ—¶é—´æˆ³ï¼ˆè‡ªåŠ¨ç”Ÿæˆï¼?
    """

    recommendation_id: str = Field(..., min_length=1)
    case_id: str = Field(..., min_length=1)
    run_id: str = Field(..., min_length=1)
    recommended_claim_amendments: list[ClaimAmendmentSuggestion] = Field(default_factory=list)
    evidence_supplement_priorities: list[str] = Field(
        default_factory=list, description="gap_id åˆ—è¡¨ï¼ŒæŒ‰ ROI é™åºæŽ’åˆ—ï¼ˆroi_rank=1 åœ¨å‰ï¼?
    )
    trial_explanation_priorities: list[TrialExplanationPriority] = Field(default_factory=list)
    claims_to_abandon: list[ClaimAbandonSuggestion] = Field(default_factory=list)
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    )
    # P1.8 v2: æ¡ˆåž‹é€‚é…æ‰©å±•å­—æ®µï¼ˆå‘åŽå…¼å®¹ï¼Œå…¨éƒ¨ Optionalï¼?
    plaintiff_action_plan: Optional[PartyActionPlan] = None
    defendant_action_plan: Optional[PartyActionPlan] = None
    case_dispute_category: Optional[str] = Field(
        default=None,
        description="æ¡ˆä»¶äº‰è®®ç±»åˆ«: amount_dispute / borrower_identity / contract_validity / ...",
    )
    strategic_headline: Optional[str] = Field(
        default=None, description="æ ¸å¿ƒç­–ç•¥ä¸€å¥è¯ï¼ˆæ›¿ä»?amount-centric æœ€ç¨³è¯‰è¯·ï¼‰"
    )


# ---------------------------------------------------------------------------
# å¯ä¿¡åº¦æŠ˜æŸæ¨¡åž?/ Credibility Scorecard  (P2.9)
# ---------------------------------------------------------------------------


class CredibilityDeduction(BaseModel):
    """å•æ¡å¯ä¿¡åº¦æ‰£åˆ†é¡¹ã€‚ç”±è§„åˆ™å±‚ç”Ÿæˆï¼Œä¸å…è®?LLM ä¿®æ”¹ã€?""

    deduction_id: str = Field(..., min_length=1, description="æ‰£åˆ†é¡¹å”¯ä¸€ ID")
    rule_id: str = Field(..., min_length=1, description="è§¦å‘è§„åˆ™ç¼–å·ï¼Œå¦‚ CRED-01")
    rule_description: str = Field(..., min_length=1, description="è§„åˆ™æè¿°")
    deduction_points: int = Field(..., lt=0, description="æ‰£åˆ†åˆ†å€¼ï¼ˆè´Ÿæ•´æ•°ï¼‰")
    trigger_evidence_ids: list[str] = Field(
        default_factory=list, description="è§¦å‘è¯¥è§„åˆ™çš„è¯æ® ID åˆ—è¡¨"
    )
    trigger_issue_ids: list[str] = Field(
        default_factory=list, description="è§¦å‘è¯¥è§„åˆ™çš„äº‰ç‚¹ ID åˆ—è¡¨"
    )


class CredibilityScorecard(BaseModel):
    """æ¡ˆä»¶æ•´ä½“å¯ä¿¡åº¦æŠ˜æŸè¯„åˆ†å¡ã€‚P2.9 äº§ç‰©ï¼Œçº³å…?CaseWorkspace.artifact_indexã€?

    base_score å›ºå®šä¸?100ï¼Œfinal_score = base_score + sum(d.deduction_points)ã€?
    final_score < 60 æ—¶ï¼Œreport_engine é¡»åœ¨æŠ¥å‘Šæ˜¾è‘—ä½ç½®æ ‡æ³¨å¯ä¿¡åº¦è­¦å‘Šã€?
    """

    scorecard_id: str = Field(..., min_length=1)
    case_id: str = Field(..., min_length=1)
    run_id: str = Field(..., min_length=1)
    base_score: int = Field(default=100, description="åŸºç¡€åˆ†ï¼ˆæ»¡åˆ† 100ï¼?)
    deductions: list[CredibilityDeduction] = Field(
        default_factory=list, description="è§¦å‘çš„æ‰£åˆ†é¡¹åˆ—è¡¨"
    )
    final_score: int = Field(..., description="æœ€ç»ˆå¾—åˆ?= base_score + sum(deduction_points)")
    summary: str = Field(..., min_length=1, description="å¯ä¿¡åº¦æ‘˜è¦è¯´æ˜?)

    @model_validator(mode="after")
    def _validate_final_score(self) -> "CredibilityScorecard":
        """ç¡¬è§„åˆ™ï¼šfinal_score å¿…é¡»ç­‰äºŽ base_score + sum(deduction_points)ã€?""
        expected = self.base_score + sum(d.deduction_points for d in self.deductions)
        if self.final_score != expected:
            raise ValueError(
                f"final_score ({self.final_score}) å¿…é¡»ç­‰äºŽ "
                f"base_score + sum(deductions) ({expected})"
            )
        return self


# ---------------------------------------------------------------------------
# P2.11ï¼šæ›¿ä»£ä¸»å¼ è‡ªåŠ¨ç”Ÿæˆ?/ Alternative claim generation  (P2.11)
# ---------------------------------------------------------------------------


class AlternativeClaimSuggestion(BaseModel):
    """æ›¿ä»£ä¸»å¼ å»ºè®®ï¼ˆP2.11ï¼‰ã€‚å½“åŽŸä¸»å¼ ä¸ç¨³å®šæ—¶è‡ªåŠ¨ç”Ÿæˆæ›´ç¨³å›ºçš„æ›¿ä»£ç‰ˆæœ¬ã€?

    è§¦å‘æ¡ä»¶ï¼ˆè§„åˆ™å±‚ï¼Œä¸è°ƒç”¨ LLMï¼‰ï¼š
    1. Issue.recommended_action = amend_claim
    2. Issue.proponent_evidence_strength = weak ä¸?opponent_attack_strength = strong
    3. ClaimCalculationEntry.delta ç»å¯¹å€¼è¶…è¿?claimed_amount Ã— 10%

    åˆçº¦ä¿è¯ï¼?
    - instability_issue_ids éžç©ºï¼ˆé›¶å®¹å¿ç©ºåˆ—è¡¨ï¼‰â€”â€”min_length=1 å¼ºåˆ¶
    - instability_evidence_ids å…è®¸ä¸ºç©ºï¼ˆIssue æœ¬èº«å¯èƒ½æ— è¯æ?IDï¼Œè®¾è®¡å†³ç­–ï¼šç»‘å®šå…³ç³»
      é€šè¿‡å­—æ®µå­˜åœ¨æ€§ä½“çŽ°ï¼Œè€Œéžå¼ºåˆ¶éžç©ºï¼?
    - alternative_claim_text å¿…é¡»å…·ä½“å¯æ‰§è¡Œï¼ˆéžæ³›åŒ–å»ºè®®ï¼‰
    - supporting_evidence_ids æ¥è‡ªè§¦å‘è¯¥å»ºè®®çš„äº‰ç‚¹ evidence_ids

    Args:
        suggestion_id:            å»ºè®®å”¯ä¸€æ ‡è¯†
        case_id:                  æ¡ˆä»¶ ID
        run_id:                   è¿è¡Œå¿«ç…§ ID
        original_claim_id:        å…³è”åŽŸå§‹ Claim.claim_id
        instability_reason:       ä¸ç¨³å®šåŽŸå› æ–‡æœ¬ï¼ˆç»‘å®š instability_issue_ids å’?instability_evidence_idsï¼?
        instability_issue_ids:    åŽŸå› ç»‘å®šäº‰ç‚¹ ID åˆ—è¡¨ï¼ˆéžç©ºï¼Œé›¶å®¹å¿ï¼‰
        instability_evidence_ids: åŽŸå› ç»‘å®šè¯æ® ID åˆ—è¡¨ï¼ˆå¯ä¸ºç©ºåˆ—è¡¨ï¼Œè§åˆçº¦ä¿è¯è¯´æ˜Žï¼?
        alternative_claim_text:   æ›¿ä»£ä¸»å¼ æ–‡æœ¬ï¼ˆå…·ä½“å¯æ‰§è¡Œï¼Œéžæ³›åŒ–ï¼?
        stability_rationale:      æ›¿ä»£ä¸»å¼ æ›´ç¨³å›ºçš„ç†ç”±
        supporting_evidence_ids:  æ”¯æŒæ›¿ä»£ä¸»å¼ çš„è¯æ?ID åˆ—è¡¨
        created_at:               ISO-8601 æ—¶é—´æˆ³ï¼ˆè‡ªåŠ¨ç”Ÿæˆï¼?
    """

    suggestion_id: str = Field(..., min_length=1)
    case_id: str = Field(..., min_length=1)
    run_id: str = Field(..., min_length=1)
    original_claim_id: str = Field(..., min_length=1, description="å…³è”åŽŸå§‹ Claim.claim_id")
    instability_reason: str = Field(..., min_length=1, description="åŽŸä¸»å¼ ä¸ç¨³å®šåŽŸå› æ–‡æœ¬")
    instability_issue_ids: list[str] = Field(
        ..., min_length=1, description="ç»‘å®šäº‰ç‚¹ ID åˆ—è¡¨ï¼ˆé›¶å®¹å¿ç©ºåˆ—è¡¨ï¼‰"
    )
    instability_evidence_ids: list[str] = Field(
        default_factory=list, description="ç»‘å®šè¯æ® ID åˆ—è¡¨ï¼ˆå¯ä¸ºç©ºï¼Œäº‰ç‚¹æ— è¯æ®æ—¶ä¸ºç©ºåˆ—è¡¨ï¼‰"
    )
    alternative_claim_text: str = Field(
        ..., min_length=1, description="æ›¿ä»£ä¸»å¼ æ–‡æœ¬ï¼ˆå…·ä½“å¯æ‰§è¡Œï¼Œä¸å…è®¸æ³›åŒ–å»ºè®®ï¼?
    )
    stability_rationale: str = Field(..., min_length=1, description="æ›¿ä»£ä¸»å¼ æ›´ç¨³å›ºçš„ç†ç”±")
    supporting_evidence_ids: list[str] = Field(
        default_factory=list, description="æ”¯æŒæ›¿ä»£ä¸»å¼ çš„è¯æ?ID åˆ—è¡¨"
    )
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    )


# ---------------------------------------------------------------------------
# v7ï¼šè¯‰è¯·æ‹†åˆ?/ Claim decomposition  (ä¿®è®¢æ¸…å• ä¸€-2)
# ---------------------------------------------------------------------------


class ClaimDecomposition(BaseModel):
    """æ‹†åˆ†åŽçš„è¯‰è¯·ç»“æž„ï¼ˆv7ï¼‰ã€‚æ›¿ä»£åŽŸ current_most_stable_claim å•ä¸€ str å­—æ®µã€?

    ä¸‰ä¸ªå­—æ®µå¯¹åº”ä¿®è®¢æ¸…å•ä¸€-2 çš„è¦æ±‚ï¼š
    - formal_claim:            æ­£å¼è¯‰è¯·é‡‘é¢ï¼ˆåŽŸå‘Šå®žé™…èµ·è¯‰æ•°é¢ï¼‰
    - fallback_anchor:         ä¿åº•é”šç‚¹/æœ€æœ‰æŠŠæ¡ä¸»å¼ ï¼ˆè·¯å¾„æ ‘æœ€çŽ°å®žè·¯å¾„æ”¯æŒçš„é‡‘é¢ï¼‰
    - expected_recovery_range: é¢„æœŸå›žæ”¶åŒºé—´ [lower, upper]

    åˆçº¦ä¿è¯ï¼?
    - fallback_anchor <= formal_claimï¼ˆè·¯å¾„æ ‘æ˜¾ç¤ºä»…éƒ¨åˆ†æ”¯æŒæ—¶è‡ªåŠ¨ä¸‹è°ƒï¼?
    - expected_recovery_range.lower <= expected_recovery_range.upper
    """

    formal_claim: Decimal = Field(..., ge=0, description="æ­£å¼è¯‰è¯·é‡‘é¢ï¼ˆåŽŸå‘Šå®žé™…èµ·è¯‰æ•°é¢ï¼‰")
    fallback_anchor: Decimal = Field(
        ..., ge=0, description="ä¿åº•é”šç‚¹ï¼šæœ€æœ‰æŠŠæ¡èŽ·å¾—æ”¯æŒçš„é‡‘é¢ï¼ˆä¸é«˜äºŽ formal_claimï¼?
    )
    expected_recovery_lower: Decimal = Field(..., ge=0, description="é¢„æœŸå›žæ”¶åŒºé—´ä¸‹ç•Œ")
    expected_recovery_upper: Decimal = Field(..., ge=0, description="é¢„æœŸå›žæ”¶åŒºé—´ä¸Šç•Œ")
    decomposition_rationale: str = Field(
        default="", description="æ‹†åˆ†ä¾æ®è¯´æ˜Žï¼ˆè·¯å¾„æ ‘å“ªæ¡è·¯å¾„æ”¯æŒå“ªéƒ¨åˆ†é‡‘é¢ï¼‰"
    )

    @model_validator(mode="after")
    def _validate_ranges(self) -> "ClaimDecomposition":
        if self.fallback_anchor > self.formal_claim:
            raise ValueError(
                f"fallback_anchor ({self.fallback_anchor}) ä¸å¾—å¤§äºŽ "
                f"formal_claim ({self.formal_claim})"
            )
        if self.expected_recovery_lower > self.expected_recovery_upper:
            raise ValueError(
                f"expected_recovery_lower ({self.expected_recovery_lower}) ä¸å¾—å¤§äºŽ "
                f"expected_recovery_upper ({self.expected_recovery_upper})"
            )
        return self


# ---------------------------------------------------------------------------
# v7ï¼šå†…éƒ¨å†³ç­–ç‰ˆæœ?/ Internal decision summary  (ä¿®è®¢æ¸…å• äº?3)
# ---------------------------------------------------------------------------


class InternalDecisionSummary(BaseModel):
    """å†…éƒ¨å†³ç­–ç‰ˆæœ¬æ‘˜è¦ï¼ˆv7ï¼‰ã€‚ä¸å¯¹å¤–å±•ç¤ºï¼Œä»…ä¾›å¾‹å¸?å†…éƒ¨å›¢é˜Ÿå†³ç­–ä½¿ç”¨ã€?

    åŒ…å«ï¼šæœ€å¯èƒ½è¾“èµ¢æ–¹å‘ã€æœ€çŽ°å®žå¯å›žæ”¶é‡‘é¢ã€æœ€å…ˆè¯¥è¡¥å“ªæ¡è¯æ®ã€?
    """

    most_likely_winner: str = Field(
        ..., description="æœ€å¯èƒ½èƒœè¯‰æ–¹ï¼šplaintiff / defendant / uncertain"
    )
    most_likely_winner_rationale: str = Field(default="", description="åˆ¤æ–­ä¾æ®")
    realistic_recovery_amount: Optional[Decimal] = Field(
        default=None, ge=0, description="æœ€çŽ°å®žå¯å›žæ”¶é‡‘é¢?
    )
    priority_evidence_to_supplement: Optional[str] = Field(
        default=None, description="æœ€å…ˆåº”è¡¥å¼ºçš„è¯æ?gap_id"
    )
    priority_supplement_rationale: str = Field(default="", description="è¡¥è¯ä¼˜å…ˆç†ç”±")


# ---------------------------------------------------------------------------
# v7ï¼šä¸€è‡´æ€§æ ¡éªŒç»“æž?/ Consistency check result  (ä¿®è®¢æ¸…å• ä¸€-3, ä¸? å›?
# ---------------------------------------------------------------------------


class ConsistencyCheckResult(BaseModel):
    """è¾“å‡ºå‰ä¸€è‡´æ€§æ ¡éªŒç»“æžœï¼ˆv7ï¼‰ã€‚é™„åŠ åœ¨æœ€ç»ˆè¾“å‡ºæœ«å°¾ã€?

    æ ¡éªŒç»´åº¦ï¼ˆä¿®è®¢æ¸…å•å››ï¼‰ï¼š
    1. perspective_consistent:    è§†è§’ä¸€è‡´æ€§ï¼ˆå?section ä¸æ··ç”¨ä¸­ç«?ä¸€æ–¹ç­–ç•¥ï¼‰
    2. recommendation_consistent: æŽ¨èä¸€è‡´æ€§ï¼ˆæŽ¨èä¸Žè·¯å¾„æ ‘åˆ¤æ–­å¯¹é½ï¼?
    3. admissibility_gate_passed: å¯é‡‡æ€§é—¸é—¨ï¼ˆç¨‹åºæ€§äº‰ç‚¹ä¸å› å†…å®¹ä¸¥é‡å°±ç½®é¡¶ï¼?
    4. strong_argument_demoted:   å¼ºè®ºç‚¹é™æƒï¼ˆè¢«å¼ºåè¯çš„è¯æ®å·²é™æƒï¼?
    5. action_stance_aligned:     è¡ŒåŠ¨å»ºè®®å¯¹é½ï¼ˆå»ºè®®æ–¹å‘ä¸Žæ•´ä½“æ€åŠ¿åŒ¹é…ï¼?
    """

    overall_pass: bool = Field(..., description="å…¨éƒ¨æ ¡éªŒé€šè¿‡ä¸?True")
    perspective_consistent: bool = Field(default=True)
    recommendation_consistent: bool = Field(default=True)
    admissibility_gate_passed: bool = Field(default=True)
    strong_argument_demoted: bool = Field(default=True)
    action_stance_aligned: bool = Field(default=True)
    failures: list[str] = Field(
        default_factory=list,
        description="å¤±è´¥åŽŸå› åˆ—è¡¨ï¼ˆwhy_failï¼?,
    )
    sections_to_regenerate: list[str] = Field(
        default_factory=list,
        description="å› ä¸€è‡´æ€§æ£€æŸ¥å¤±è´¥éœ€è¦é‡ç”Ÿæˆçš?section_id åˆ—è¡¨",
    )


class ConfidenceMetrics(BaseModel):
    """æ‰§è¡Œæ‘˜è¦ç½®ä¿¡åº¦æŒ‡æ ‡ï¼ˆP2 ç»“æž„åŒ–è¾“å‡ºï¼‰ã€?

    Args:
        overall_confidence:     æ•´ä½“ç½®ä¿¡åº¦ï¼ˆ0.0-1.0ï¼?
        evidence_completeness:  è¯æ®å®Œæ•´åº¦ï¼ˆ0.0-1.0ï¼?
        legal_clarity:          æ³•å¾‹é€‚ç”¨æ¸…æ™°åº¦ï¼ˆ0.0-1.0ï¼?
    """

    overall_confidence: float = Field(
        ge=0.0, le=1.0, description="æ•´ä½“ç½®ä¿¡åº¦ï¼ˆåŸºäºŽè¯æ®å……åˆ†æ€§å’Œæ³•å¾‹ä¾æ®æ¸…æ™°åº¦ï¼‰"
    )
    evidence_completeness: float = Field(
        ge=0.0, le=1.0, description="è¯æ®å®Œæ•´åº¦ï¼ˆå·²æœ‰è¯æ®è¦†ç›–äº‰ç‚¹çš„æ¯”ä¾‹ï¼‰"
    )
    legal_clarity: float = Field(ge=0.0, le=1.0, description="æ³•å¾‹é€‚ç”¨æ¸…æ™°åº¦ï¼ˆé€‚ç”¨æ³•æ¡æ˜Žç¡®ç¨‹åº¦ï¼?)


class ExecutiveSummaryStructuredOutput(BaseModel):
    """æ‰§è¡Œæ‘˜è¦ç»“æž„åŒ?JSON è¾“å‡ºï¼ˆP2 åŒå±‚è¾“å‡ºï¼‰ã€?

    ä¸ŽçŽ°æœ‰å™è¿°æ€§è¾“å‡ºå¹¶å­˜ï¼Œæä¾›æœºå™¨å¯è¯»çš„ç»“æž„åŒ–æ‘˜è¦ã€?

    Args:
        case_overview:          æ¡ˆä»¶æ¦‚è¿°ï¼?-3 å¥è¯çš„æ–‡å­—æ‘˜è¦ï¼‰
        key_findings:           å…³é”®å‘çŽ°åˆ—è¡¨ï¼ˆæ¯æ¡ä¸º 1 å¥è¯çš„å…·ä½“å‘çŽ°ï¼‰
        risk_assessment:        é£Žé™©è¯„ä¼°æ‘˜è¦ï¼ˆæŒ‡æ˜Žä¸»è¦é£Žé™©ç‚¹ï¼?
        recommended_actions:    å»ºè®®è¡ŒåŠ¨åˆ—è¡¨ï¼ˆå…·ä½“å¯æ‰§è¡Œï¼ŒæŒ‰ä¼˜å…ˆçº§æŽ’åºï¼‰
        confidence_metrics:     ç½®ä¿¡åº¦æŒ‡æ ?
    """
Cannot set property. Property setting is supported only on core types in this language mode.
At line:1 char:1
+ [Console]::OutputEncoding=[System.Text.Encoding]::UTF8;
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : InvalidOperation: (:) [], RuntimeException
    + FullyQualifiedErrorId : PropertySetterNotSupportedInConstrainedLanguage
 

exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -NoProfile -Command "Select-String -Path 'engines\\report_generation\\*.py' -Pattern 'mediation_range|amount_report|get\\(\"consistency_check_result|claim_calculation_table'" in C:/Users/david/dev/case-adversarial-engine
 succeeded in 599ms:

engines\report_generation\docx_generator.py:18:        amount_report=ar_dict,        # AmountCalculationReport as dict 
(or None)
engines\report_generation\docx_generator.py:33:from engines.report_generation.mediation_range import 
compute_mediation_range
engines\report_generation\docx_generator.py:202:    amount_report: dict | None = None,
engines\report_generation\docx_generator.py:218:        amount_report:   AmountCalculationReport 序列化 dict（可选）
engines\report_generation\docx_generator.py:228:    amount_report = amount_report or {}
engines\report_generation\docx_generator.py:288:    _render_executive_summary(doc, exec_summary, amount_report)
engines\report_generation\docx_generator.py:633:def _render_executive_summary(doc, exec_summary: dict, amount_report: 
dict):
engines\report_generation\docx_generator.py:651:    check = amount_report.get("consistency_check_result", {})
engines\report_generation\docx_generator.py:743:def _render_mediation_range(doc, amount_report: dict | None, 
decision_tree: dict | None):
engines\report_generation\docx_generator.py:745:    med = compute_mediation_range(amount_report, decision_tree)
engines\report_generation\mediation_range.py:8:    from engines.report_generation.mediation_range import 
compute_mediation_range, MediationRange
engines\report_generation\mediation_range.py:9:    result = compute_mediation_range(amount_report, decision_tree)
engines\report_generation\mediation_range.py:34:def compute_mediation_range(
engines\report_generation\mediation_range.py:35:    amount_report: Any,
engines\report_generation\mediation_range.py:41:    1. Sum claimed_amount and calculated_amount from 
claim_calculation_table
engines\report_generation\mediation_range.py:48:        amount_report: AmountCalculationReport object or dict with 
claim_calculation_table
engines\report_generation\mediation_range.py:52:        MediationRange or None if amount_report is unavailable or has 
no entries.
engines\report_generation\mediation_range.py:54:    if amount_report is None:
engines\report_generation\mediation_range.py:58:    table = _get_attr_or_key(amount_report, "claim_calculation_table")
engines\report_generation\outcome_paths.py:13:    paths = build_case_outcome_paths(decision_tree, mediation_range, 
gap_result)
engines\report_generation\outcome_paths.py:28:    mediation_range: Any = None,
engines\report_generation\outcome_paths.py:37:        mediation_range: MediationRange dataclass (or None). Provides 
MEDIATION path.
engines\report_generation\outcome_paths.py:48:        mediation_path=_build_mediation_path(mediation_range),
engines\report_generation\outcome_paths.py:176:def _build_mediation_path(mediation_range: Any) -> OutcomePath:
engines\report_generation\outcome_paths.py:178:    if mediation_range is None:
engines\report_generation\outcome_paths.py:185:    min_amt = _get_attr(mediation_range, "min_amount")
engines\report_generation\outcome_paths.py:186:    max_amt = _get_attr(mediation_range, "max_amount")
engines\report_generation\outcome_paths.py:187:    suggested = _get_attr(mediation_range, "suggested_amount")
engines\report_generation\outcome_paths.py:188:    rationale = _get_str(mediation_range, "rationale")
engines\report_generation\outcome_paths.py:204:        source_artifact="mediation_range",


Cannot set property. Property setting is supported only on core types in this language mode.
At line:1 char:1
+ [Console]::OutputEncoding=[System.Text.Encoding]::UTF8;
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : InvalidOperation: (:) [], RuntimeException
    + FullyQualifiedErrorId : PropertySetterNotSupportedInConstrainedLanguage
 

exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -NoProfile -Command "Select-String -Path 'engines\\**\\*.py' -Pattern 'RegistryPlugin\\(|plugin\\.get_prompt|plugin\\.allowed_impact_targets|from \\.prompts\\.civil_loan|from \\.prompts import PROMPT_REGISTRY'" in C:/Users/david/dev/case-adversarial-engine
 succeeded in 618ms:

engines\document_assistance\engine.py:26:from .prompts import PROMPT_REGISTRY
engines\interactive_followup\responder.py:103:        from .prompts import PROMPT_REGISTRY
engines\interactive_followup\responder.py:185:        user_prompt = plugin.get_prompt(
engines\pretrial_conference\cross_examination_engine.py:34:from .prompts.civil_loan import (
engines\procedure_setup\planner.py:223:        from .prompts import PROMPT_REGISTRY
engines\procedure_setup\planner.py:289:            user_prompt = plugin.get_prompt(
engines\report_generation\generator.py:155:        from .prompts import PROMPT_REGISTRY
engines\report_generation\generator.py:219:        user_prompt = plugin.get_prompt(
engines\shared\case_type_plugin.py:11:    plugin = RegistryPlugin(PROMPT_REGISTRY)
engines\shared\case_type_plugin.py:14:    prompt = plugin.get_prompt("action_recommender", "civil_loan", context)
engines\shared\case_type_plugin.py:17:    allowed = plugin.allowed_impact_targets("civil_loan")
engines\shared\case_type_plugin.py:20:    plugin.get_prompt("engine", "unknown", {})  # raises UnsupportedCaseTypeError
engines\shared\case_type_plugin.py:150:                    "plugin.allowed_impact_targets(...) 的引擎是必需的。"
engines\shared\case_type_plugin.py:158:                    "plugin.allowed_impact_targets(...) 的引擎是必需的。"
engines\simulation_run\simulator.py:122:        from .prompts import PROMPT_REGISTRY
engines\simulation_run\simulator.py:199:            user_prompt = plugin.get_prompt(


Cannot set property. Property setting is supported only on core types in this language mode.
At line:1 char:1
+ [Console]::OutputEncoding=[System.Text.Encoding]::UTF8;
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : InvalidOperation: (:) [], RuntimeException
    + FullyQualifiedErrorId : PropertySetterNotSupportedInConstrainedLanguage
 

exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -NoProfile -Command 'Get-ChildItem -Name' in C:/Users/david/dev/case-adversarial-engine
 succeeded in 535ms:
.bulwark
.claude
.github
.mypy_cache
.pytest_cache
.ruff_cache
api
benchmarks
cases
case_adversarial_engine.egg-info
config
data
docs
engines
outputs
plans
reviews
scenarios
schemas
scripts
tests
workspaces
.gitignore
.pre-commit-config.yaml
CHANGELOG.md
CLAUDE.md
config.yaml
pyproject.toml
README.md
requirements.txt
Cannot set property. Property setting is supported only on core types in this language mode.
At line:1 char:1
+ [Console]::OutputEncoding=[System.Text.Encoding]::UTF8;
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : InvalidOperation: (:) [], RuntimeException
    + FullyQualifiedErrorId : PropertySetterNotSupportedInConstrainedLanguage
 

2026-04-07T11:33:00.812758Z ERROR codex_core::tools::router: error=`"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -NoProfile -Command "Select-String -Path 'api\\**\\*.py','schemas\\**\\*.json','config\\**\\*' -Pattern 'civil_loan|labor_dispute|real_estate|case_type|criminal|admin'"` rejected: blocked by policy
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -NoProfile -Command "Select-String -Path 'api\\**\\*.py','schemas\\**\\*.json','config\\**\\*' -Pattern 'civil_loan|labor_dispute|real_estate|case_type|criminal|admin'" in C:/Users/david/dev/case-adversarial-engine
 declined in 0ms:
`"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -NoProfile -Command "Select-String -Path 'api\\**\\*.py','schemas\\**\\*.json','config\\**\\*' -Pattern 'civil_loan|labor_dispute|real_estate|case_type|criminal|admin'"` rejected: blocked by policy
2026-04-07T11:33:00.819841Z ERROR codex_core::tools::router: error=`"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -NoProfile -Command "Select-String -Path 'README.md','docs\\**\\*.md' -Pattern 'civil_loan|labor_dispute|real_estate|criminal|admin'"` rejected: blocked by policy
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -NoProfile -Command "Select-String -Path 'README.md','docs\\**\\*.md' -Pattern 'civil_loan|labor_dispute|real_estate|criminal|admin'" in C:/Users/david/dev/case-adversarial-engine
 declined in 0ms:
`"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -NoProfile -Command "Select-String -Path 'README.md','docs\\**\\*.md' -Pattern 'civil_loan|labor_dispute|real_estate|criminal|admin'"` rejected: blocked by policy
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -NoProfile -Command "Select-String -Path 'tests\\**\\*.py' -Pattern 'civil_loan|labor_dispute|real_estate|case_type'" in C:/Users/david/dev/case-adversarial-engine
 succeeded in 678ms:

tests\acceptance\test_n3_consistency.py:33:CASE_TYPES = ["civil_loan", "labor_dispute", "real_estate"]
tests\acceptance\test_n3_consistency.py:36:    "civil_loan": "wang_v_chen_zhuang_2025.yaml",
tests\acceptance\test_n3_consistency.py:37:    "labor_dispute": "labor_dispute_1.yaml",
tests\acceptance\test_n3_consistency.py:38:    "real_estate": "real_estate_1.yaml",
tests\acceptance\test_n3_consistency.py:52:    "civil_loan": [
tests\acceptance\test_n3_consistency.py:59:    "labor_dispute": [
tests\acceptance\test_n3_consistency.py:66:    "real_estate": [
tests\acceptance\test_n3_consistency.py:76:    "civil_loan": [
tests\acceptance\test_n3_consistency.py:82:    "labor_dispute": [
tests\acceptance\test_n3_consistency.py:88:    "real_estate": [
tests\acceptance\test_n3_consistency.py:118:    case_type: str,
tests\acceptance\test_n3_consistency.py:126:        case_type: One of CASE_TYPES
tests\acceptance\test_n3_consistency.py:130:    issues = list(_GOLDEN_ISSUES[case_type])
tests\acceptance\test_n3_consistency.py:135:    citations = [list(c) for c in _GOLDEN_EVIDENCE_CITATIONS[case_type]]
tests\acceptance\test_n3_consistency.py:153:def _write_golden_artifacts(output_dir: Path, case_type: str) -> None:
tests\acceptance\test_n3_consistency.py:159:        "case_id": f"case-{case_type}-golden",
tests\acceptance\test_n3_consistency.py:162:            for i, iid in enumerate(_GOLDEN_ISSUES[case_type])
tests\acceptance\test_n3_consistency.py:171:    for i, citations in enumerate(_GOLDEN_EVIDENCE_CITATIONS[case_type]):
tests\acceptance\test_n3_consistency.py:182:        "case_id": f"case-{case_type}-golden",
tests\acceptance\test_n3_consistency.py:183:        "run_id": f"run-{case_type}-golden",
tests\acceptance\test_n3_consistency.py:197:        f"# {case_type} Golden Report\n\nThis is a golden artifact for 
acceptance testing.\n",
tests\acceptance\test_n3_consistency.py:210:    @pytest.mark.parametrize("case_type", CASE_TYPES)
tests\acceptance\test_n3_consistency.py:211:    def test_perfect_n3_passes_all_metrics(self, case_type: str):
tests\acceptance\test_n3_consistency.py:212:        runs = [_make_golden_run(case_type) for _ in range(3)]
tests\acceptance\test_n3_consistency.py:221:    @pytest.mark.parametrize("case_type", CASE_TYPES)
tests\acceptance\test_n3_consistency.py:222:    def test_perfect_n3_exceeds_thresholds(self, case_type: str):
tests\acceptance\test_n3_consistency.py:223:        runs = [_make_golden_run(case_type) for _ in range(3)]
tests\acceptance\test_n3_consistency.py:238:    @pytest.mark.parametrize("case_type", CASE_TYPES)
tests\acceptance\test_n3_consistency.py:239:    def test_two_of_three_identical_passes_consistency(self, case_type: 
str):
tests\acceptance\test_n3_consistency.py:242:            _make_golden_run(case_type, issue_variation=0),
tests\acceptance\test_n3_consistency.py:243:            _make_golden_run(case_type, issue_variation=0),
tests\acceptance\test_n3_consistency.py:244:            _make_golden_run(case_type, issue_variation=1),
tests\acceptance\test_n3_consistency.py:253:    @pytest.mark.parametrize("case_type", CASE_TYPES)
tests\acceptance\test_n3_consistency.py:254:    def test_all_three_identical_passes_threshold(self, case_type: str):
tests\acceptance\test_n3_consistency.py:256:        runs = [_make_golden_run(case_type, issue_variation=0) for _ in 
range(3)]
tests\acceptance\test_n3_consistency.py:271:    @pytest.mark.parametrize("case_type", CASE_TYPES)
tests\acceptance\test_n3_consistency.py:272:    def test_uncited_outputs_fail_citation_rate(self, case_type: str):
tests\acceptance\test_n3_consistency.py:273:        runs = [_make_golden_run(case_type, all_cited=False) for _ in 
range(3)]
tests\acceptance\test_n3_consistency.py:289:    @pytest.mark.parametrize("case_type", CASE_TYPES)
tests\acceptance\test_n3_consistency.py:290:    def test_one_failed_run_of_three_still_passes(self, case_type: str):
tests\acceptance\test_n3_consistency.py:293:            _make_golden_run(case_type),
tests\acceptance\test_n3_consistency.py:294:            _make_golden_run(case_type),
tests\acceptance\test_n3_consistency.py:304:    @pytest.mark.parametrize("case_type", CASE_TYPES)
tests\acceptance\test_n3_consistency.py:305:    def test_all_three_failed(self, case_type: str):
tests\acceptance\test_n3_consistency.py:328:    @pytest.mark.parametrize("case_type", CASE_TYPES)
tests\acceptance\test_n3_consistency.py:329:    def test_golden_artifacts_extract_successfully(self, case_type: str, 
tmp_path: Path):
tests\acceptance\test_n3_consistency.py:330:        run_dir = tmp_path / f"golden_{case_type}"
tests\acceptance\test_n3_consistency.py:331:        _write_golden_artifacts(run_dir, case_type)
tests\acceptance\test_n3_consistency.py:337:        assert len(result["issue_ids"]) == len(_GOLDEN_ISSUES[case_type])
tests\acceptance\test_n3_consistency.py:338:        assert result["issue_ids"] == _GOLDEN_ISSUES[case_type]
tests\acceptance\test_n3_consistency.py:343:    @pytest.mark.parametrize("case_type", CASE_TYPES)
tests\acceptance\test_n3_consistency.py:344:    def test_golden_artifacts_have_citations(self, case_type: str, 
tmp_path: Path):
tests\acceptance\test_n3_consistency.py:345:        run_dir = tmp_path / f"golden_{case_type}"
tests\acceptance\test_n3_consistency.py:346:        _write_golden_artifacts(run_dir, case_type)
tests\acceptance\test_n3_consistency.py:354:    @pytest.mark.parametrize("case_type", CASE_TYPES)
tests\acceptance\test_n3_consistency.py:355:    def test_golden_artifacts_pass_acceptance(self, case_type: str, 
tmp_path: Path):
tests\acceptance\test_n3_consistency.py:359:            run_dir = tmp_path / f"golden_{case_type}_run{i}"
tests\acceptance\test_n3_consistency.py:360:            _write_golden_artifacts(run_dir, case_type)
tests\acceptance\test_n3_consistency.py:366:            f"{case_type} golden artifacts failed acceptance: {metrics}"
tests\acceptance\test_n3_consistency.py:381:    def _mock_pipeline_runner(self, case_type: str):
tests\acceptance\test_n3_consistency.py:384:            _write_golden_artifacts(output_dir, case_type)
tests\acceptance\test_n3_consistency.py:388:    @pytest.mark.parametrize("case_type", CASE_TYPES)
tests\acceptance\test_n3_consistency.py:390:        self, case_type: str, tmp_path: Path
tests\acceptance\test_n3_consistency.py:392:        yaml_path = CASES_DIR / REPRESENTATIVE_YAMLS[case_type]
tests\acceptance\test_n3_consistency.py:396:            base_output_dir=tmp_path / case_type,
tests\acceptance\test_n3_consistency.py:397:            pipeline_runner=self._mock_pipeline_runner(case_type),
tests\acceptance\test_n3_consistency.py:401:            f"{case_type} acceptance failed: {result.get('metrics')}"
tests\acceptance\test_n3_consistency.py:408:    @pytest.mark.parametrize("case_type", CASE_TYPES)
tests\acceptance\test_n3_consistency.py:409:    def test_acceptance_report_structure(self, case_type: str, tmp_path: 
Path):
tests\acceptance\test_n3_consistency.py:410:        yaml_path = CASES_DIR / REPRESENTATIVE_YAMLS[case_type]
tests\acceptance\test_n3_consistency.py:414:            base_output_dir=tmp_path / case_type,
tests\acceptance\test_n3_consistency.py:415:            pipeline_runner=self._mock_pipeline_runner(case_type),
tests\acceptance\test_n3_consistency.py:427:            assert run["issue_count"] == len(_GOLDEN_ISSUES[case_type])
tests\acceptance\test_n3_consistency.py:440:    @pytest.mark.parametrize("case_type", CASE_TYPES)
tests\acceptance\test_n3_consistency.py:441:    def test_golden_dir_exists(self, case_type: str):
tests\acceptance\test_n3_consistency.py:442:        d = _GOLDEN_DIR / case_type
tests\acceptance\test_n3_consistency.py:445:    @pytest.mark.parametrize("case_type", CASE_TYPES)
tests\acceptance\test_n3_consistency.py:446:    def test_golden_has_required_files(self, case_type: str):
tests\acceptance\test_n3_consistency.py:447:        d = _GOLDEN_DIR / case_type
tests\acceptance\test_n3_consistency.py:451:    @pytest.mark.parametrize("case_type", CASE_TYPES)
tests\acceptance\test_n3_consistency.py:452:    def test_golden_artifacts_parse_successfully(self, case_type: str):
tests\acceptance\test_n3_consistency.py:453:        d = _GOLDEN_DIR / case_type
tests\acceptance\test_n3_consistency.py:458:    @pytest.mark.parametrize("case_type", CASE_TYPES)
tests\acceptance\test_n3_consistency.py:459:    def test_golden_n3_passes_acceptance(self, case_type: str):
tests\acceptance\test_n3_consistency.py:461:        d = _GOLDEN_DIR / case_type
tests\acceptance\test_n3_consistency.py:464:        assert metrics["passed"], f"{case_type} golden N=3 failed: 
{metrics}"
tests\acceptance\test_n3_consistency.py:475:    def test_issue_sets_are_distinct_across_case_types(self):
tests\acceptance\test_n3_consistency.py:476:        for ct1 in CASE_TYPES:
tests\acceptance\test_n3_consistency.py:477:            for ct2 in CASE_TYPES:
tests\acceptance\test_n3_consistency.py:488:    def test_evidence_citations_are_distinct_across_case_types(self):
tests\acceptance\test_n3_consistency.py:489:        for ct1 in CASE_TYPES:
tests\acceptance\test_n3_consistency.py:490:            for ct2 in CASE_TYPES:
tests\acceptance\test_pipeline_structural.py:6:- All engine constructors accept each case_type without error
tests\acceptance\test_pipeline_structural.py:32:CASE_TYPES = ["civil_loan", "labor_dispute", "real_estate"]
tests\acceptance\test_pipeline_structural.py:35:    "civil_loan": "wang_v_chen_zhuang_2025.yaml",
tests\acceptance\test_pipeline_structural.py:36:    "labor_dispute": "labor_dispute_1.yaml",
tests\acceptance\test_pipeline_structural.py:37:    "real_estate": "real_estate_1.yaml",
tests\acceptance\test_pipeline_structural.py:45:    "case_type",
tests\acceptance\test_pipeline_structural.py:68:    @pytest.mark.parametrize("case_type", CASE_TYPES)
tests\acceptance\test_pipeline_structural.py:69:    def test_representative_yaml_exists(self, case_type: str):
tests\acceptance\test_pipeline_structural.py:70:        yaml_path = CASES_DIR / REPRESENTATIVE_YAMLS[case_type]
tests\acceptance\test_pipeline_structural.py:73:    @pytest.mark.parametrize("case_type", CASE_TYPES)
tests\acceptance\test_pipeline_structural.py:74:    def test_yaml_has_required_keys(self, case_type: str):
tests\acceptance\test_pipeline_structural.py:75:        yaml_path = CASES_DIR / REPRESENTATIVE_YAMLS[case_type]
tests\acceptance\test_pipeline_structural.py:82:    @pytest.mark.parametrize("case_type", CASE_TYPES)
tests\acceptance\test_pipeline_structural.py:83:    def test_yaml_case_type_matches(self, case_type: str):
tests\acceptance\test_pipeline_structural.py:84:        yaml_path = CASES_DIR / REPRESENTATIVE_YAMLS[case_type]
tests\acceptance\test_pipeline_structural.py:87:        assert data["case_type"] == case_type
tests\acceptance\test_pipeline_structural.py:89:    @pytest.mark.parametrize("case_type", CASE_TYPES)
tests\acceptance\test_pipeline_structural.py:90:    def test_yaml_has_both_party_materials(self, case_type: str):
tests\acceptance\test_pipeline_structural.py:91:        yaml_path = CASES_DIR / REPRESENTATIVE_YAMLS[case_type]
tests\acceptance\test_pipeline_structural.py:98:    @pytest.mark.parametrize("case_type", CASE_TYPES)
tests\acceptance\test_pipeline_structural.py:99:    def test_yaml_has_claims_and_defenses(self, case_type: str):
tests\acceptance\test_pipeline_structural.py:100:        yaml_path = CASES_DIR / REPRESENTATIVE_YAMLS[case_type]
tests\acceptance\test_pipeline_structural.py:125:        for ct in CASE_TYPES:
tests\acceptance\test_pipeline_structural.py:131:        for ct in CASE_TYPES:
tests\acceptance\test_pipeline_structural.py:137:        for ct in CASE_TYPES:
tests\acceptance\test_pipeline_structural.py:143:        for ct in CASE_TYPES:
tests\acceptance\test_pipeline_structural.py:155:    def test_registry_has_all_case_types(self):
tests\acceptance\test_pipeline_structural.py:158:        for ct in CASE_TYPES:
tests\acceptance\test_pipeline_structural.py:161:    @pytest.mark.parametrize("case_type", CASE_TYPES)
tests\acceptance\test_pipeline_structural.py:162:    def test_module_has_case_context(self, case_type: str):
tests\acceptance\test_pipeline_structural.py:165:        module = PROMPT_REGISTRY[case_type]
tests\acceptance\test_pipeline_structural.py:166:        assert hasattr(module, "CASE_CONTEXT"), 
f"adversarial/{case_type} missing CASE_CONTEXT"
tests\acceptance\test_pipeline_structural.py:169:    @pytest.mark.parametrize("case_type", CASE_TYPES)
tests\acceptance\test_pipeline_structural.py:170:    def test_module_has_evidence_review_criteria(self, case_type: 
str):
tests\acceptance\test_pipeline_structural.py:173:        module = PROMPT_REGISTRY[case_type]
tests\acceptance\test_pipeline_structural.py:175:            f"adversarial/{case_type} missing 
EVIDENCE_REVIEW_CRITERIA"
tests\acceptance\test_pipeline_structural.py:187:    def test_top_level_registry_has_all_case_types(self):
tests\acceptance\test_pipeline_structural.py:190:        for ct in CASE_TYPES:
tests\acceptance\test_pipeline_structural.py:202:    def test_prompts_registry_has_all_case_types(self):
tests\acceptance\test_pipeline_structural.py:205:        for ct in CASE_TYPES:
tests\acceptance\test_pipeline_structural.py:217:    @pytest.mark.parametrize("case_type", CASE_TYPES)
tests\acceptance\test_pipeline_structural.py:218:    def test_evidence_indexer_init(self, case_type: str):
tests\acceptance\test_pipeline_structural.py:221:        engine = EvidenceIndexer(llm_client=_mock_llm_client(), 
case_type=case_type)
tests\acceptance\test_pipeline_structural.py:224:    @pytest.mark.parametrize("case_type", CASE_TYPES)
tests\acceptance\test_pipeline_structural.py:225:    def test_issue_extractor_init(self, case_type: str):
tests\acceptance\test_pipeline_structural.py:228:        engine = IssueExtractor(llm_client=_mock_llm_client(), 
case_type=case_type)
tests\acceptance\test_pipeline_structural.py:231:    @pytest.mark.parametrize("case_type", CASE_TYPES)
tests\acceptance\test_pipeline_structural.py:232:    def test_admissibility_evaluator_init(self, case_type: str):
tests\acceptance\test_pipeline_structural.py:237:            case_type=case_type,
tests\acceptance\test_pipeline_structural.py:244:    @pytest.mark.parametrize("case_type", CASE_TYPES)
tests\acceptance\test_pipeline_structural.py:245:    def test_decision_path_tree_generator_init(self, case_type: str):
tests\acceptance\test_pipeline_structural.py:250:            case_type=case_type,
tests\acceptance\test_pipeline_structural.py:257:    @pytest.mark.parametrize("case_type", CASE_TYPES)
tests\acceptance\test_pipeline_structural.py:258:    def test_issue_impact_ranker_init(self, case_type: str):
tests\acceptance\test_pipeline_structural.py:263:            case_type=case_type,
tests\acceptance\test_pipeline_structural.py:267:    @pytest.mark.parametrize("case_type", CASE_TYPES)
tests\acceptance\test_pipeline_structural.py:268:    def test_attack_chain_optimizer_init(self, case_type: str):
tests\acceptance\test_pipeline_structural.py:273:            case_type=case_type,
tests\acceptance\test_pipeline_structural.py:280:    @pytest.mark.parametrize("case_type", CASE_TYPES)
tests\acceptance\test_pipeline_structural.py:281:    def test_action_recommender_init(self, case_type: str):
tests\acceptance\test_pipeline_structural.py:286:            case_type=case_type,
tests\acceptance\test_pipeline_structural.py:290:    def test_unsupported_case_type_raises(self):
tests\acceptance\test_pipeline_structural.py:294:            EvidenceIndexer(llm_client=_mock_llm_client(), 
case_type="nonexistent_type")
tests\acceptance\test_pipeline_structural.py:305:    Note: document_assistance uses 2D keys (doc_type, case_type).
tests\acceptance\test_pipeline_structural.py:310:    def test_all_case_type_doc_type_combos_registered(self):
tests\acceptance\test_pipeline_structural.py:313:        for ct in CASE_TYPES:
tests\acceptance\test_pipeline_structural.py:328:    @pytest.mark.parametrize("case_type", CASE_TYPES)
tests\acceptance\test_pipeline_structural.py:329:    def test_materials_build_to_raw_materials(self, case_type: str):
tests\acceptance\test_pipeline_structural.py:333:        yaml_path = CASES_DIR / REPRESENTATIVE_YAMLS[case_type]
tests\acceptance\test_pipeline_structural.py:347:    @pytest.mark.parametrize("case_type", CASE_TYPES)
tests\acceptance\test_pipeline_structural.py:348:    def test_claims_have_required_fields(self, case_type: str):
tests\acceptance\test_pipeline_structural.py:349:        yaml_path = CASES_DIR / REPRESENTATIVE_YAMLS[case_type]
tests\acceptance\test_pipeline_structural.py:356:    @pytest.mark.parametrize("case_type", CASE_TYPES)
tests\acceptance\test_pipeline_structural.py:357:    def test_defenses_have_required_fields(self, case_type: str):
tests\acceptance\test_pipeline_structural.py:358:        yaml_path = CASES_DIR / REPRESENTATIVE_YAMLS[case_type]
tests\acceptance\test_pipeline_structural.py:365:    @pytest.mark.parametrize("case_type", CASE_TYPES)
tests\acceptance\test_pipeline_structural.py:366:    def test_parties_have_ids_and_names(self, case_type: str):
tests\acceptance\test_pipeline_structural.py:367:        yaml_path = CASES_DIR / REPRESENTATIVE_YAMLS[case_type]
tests\acceptance\test_pipeline_structural.py:375:    def test_civil_loan_has_financials(self):
tests\acceptance\test_pipeline_structural.py:376:        """civil_loan cases should have a financials section for 
amount calculation."""
tests\acceptance\test_pipeline_structural.py:377:        yaml_path = CASES_DIR / REPRESENTATIVE_YAMLS["civil_loan"]
tests\acceptance\test_pipeline_structural.py:380:        assert "financials" in data, "civil_loan representative YAML 
missing financials section"
tests\acceptance\test_pipeline_structural.py:394:    @pytest.mark.parametrize("case_type", CASE_TYPES)
tests\acceptance\test_pipeline_structural.py:395:    def test_acceptance_yaml_validation(self, case_type: str):
tests\acceptance\test_pipeline_structural.py:398:        yaml_path = CASES_DIR / REPRESENTATIVE_YAMLS[case_type]
tests\acceptance\test_pipeline_structural.py:403:    @pytest.mark.parametrize("case_type", CASE_TYPES)
tests\acceptance\test_pipeline_structural.py:404:    def test_acceptance_yaml_matching(self, case_type: str):
tests\acceptance\test_pipeline_structural.py:405:        """_yaml_matches_case_type correctly identifies 
representative YAMLs."""
tests\acceptance\test_pipeline_structural.py:406:        from scripts.run_acceptance import _yaml_matches_case_type
tests\acceptance\test_pipeline_structural.py:408:        yaml_path = CASES_DIR / REPRESENTATIVE_YAMLS[case_type]
tests\acceptance\test_pipeline_structural.py:409:        assert _yaml_matches_case_type(yaml_path, case_type)
tests\acceptance\test_pipeline_structural.py:411:    @pytest.mark.parametrize("case_type", CASE_TYPES)
tests\acceptance\test_pipeline_structural.py:412:    def test_at_least_one_yaml_per_case_type(self, case_type: str):
tests\acceptance\test_pipeline_structural.py:414:        from scripts.run_acceptance import _yaml_matches_case_type
tests\acceptance\test_pipeline_structural.py:417:        matching = [p for p in all_yamls if 
_yaml_matches_case_type(p, case_type)]
tests\acceptance\test_pipeline_structural.py:418:        assert len(matching) >= 1, f"No YAML files match case_type 
'{case_type}'"
tests\acceptance\test_v2_acceptance.py:36:    "case_type": "labor_dispute",
tests\acceptance\test_v2_acceptance.py:465:    def _write_case_yaml(self, cases_dir: Path, case_type: str, idx: int) 
-> Path:
tests\acceptance\test_v2_acceptance.py:467:        content["case_id"] = f"case-{case_type}-test-{idx:03d}"
tests\acceptance\test_v2_acceptance.py:468:        content["case_slug"] = f"{case_type}test{idx:03d}"
tests\acceptance\test_v2_acceptance.py:469:        content["case_type"] = case_type
tests\acceptance\test_v2_acceptance.py:470:        path = cases_dir / f"{case_type}_{idx}.yaml"
tests\acceptance\test_v2_acceptance.py:478:            case_type="labor_dispute",
tests\acceptance\test_v2_acceptance.py:491:        self._write_case_yaml(cases_dir, "labor_dispute", 1)
tests\acceptance\test_v2_acceptance.py:492:        self._write_case_yaml(cases_dir, "labor_dispute", 2)
tests\acceptance\test_v2_acceptance.py:493:        self._write_case_yaml(cases_dir, "real_estate", 1)
tests\acceptance\test_v2_acceptance.py:496:            case_type="labor_dispute",
tests\acceptance\test_v2_acceptance.py:503:        assert report["case_type"] == "labor_dispute"
tests\acceptance\test_v2_acceptance.py:508:        self._write_case_yaml(cases_dir, "labor_dispute", 1)
tests\acceptance\test_v2_acceptance.py:511:            case_type="labor_dispute",
tests\acceptance\test_v2_acceptance.py:519:            "case_type",
tests\acceptance\test_v2_acceptance.py:531:        self._write_case_yaml(cases_dir, "real_estate", 1)
tests\acceptance\test_v2_acceptance.py:532:        self._write_case_yaml(cases_dir, "real_estate", 2)
tests\acceptance\test_v2_acceptance.py:533:        self._write_case_yaml(cases_dir, "real_estate", 3)
tests\acceptance\test_v2_acceptance.py:536:            case_type="real_estate",
tests\acceptance\test_v2_acceptance.py:550:            "case_type": "labor_dispute",
tests\integration\test_full_pipeline.py:295:        case_type="civil_loan",
tests\integration\test_full_pipeline.py:308:        case_type="civil_loan",
tests\integration\test_full_pipeline.py:322:        case_type="civil_loan",
tests\integration\test_full_pipeline.py:376:        case_type="civil_loan",
tests\integration\test_full_pipeline.py:394:        case_type="civil_loan",
tests\integration\test_full_pipeline.py:422:        case_type="civil_loan",
tests\integration\test_full_pipeline.py:457:        case_type="civil_loan",
tests\integration\test_full_pipeline.py:473:        case_type="civil_loan",
tests\integration\test_full_pipeline.py:519:        case_type="civil_loan",
tests\integration\test_full_pipeline.py:562:        case_type="civil_loan",
tests\integration\test_full_pipeline.py:608:        case_type="civil_loan",
tests\integration\test_full_pipeline.py:652:            case_type="civil_loan",
tests\integration\test_full_pipeline.py:691:        case_type="civil_loan",
tests\integration\test_full_pipeline.py:768:        case_type="civil_loan",
tests\integration\test_full_pipeline.py:775:        case_type="civil_loan",
tests\integration\test_pipeline_with_persistence.py:158:        case_type="civil_loan",


Cannot set property. Property setting is supported only on core types in this language mode.
At line:1 char:1
+ [Console]::OutputEncoding=[System.Text.Encoding]::UTF8;
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : InvalidOperation: (:) [], RuntimeException
    + FullyQualifiedErrorId : PropertySetterNotSupportedInConstrainedLanguage
 

exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -NoProfile -Command "Select-String -Path 'api\\**\\*.py' -Pattern 'civil_loan|labor_dispute|real_estate|case_type'" in C:/Users/david/dev/case-adversarial-engine
 succeeded in 608ms:

api\tests\conftest.py:13:        "case_type": "civil_loan",
api\tests\test_analysis_endpoints.py:34:    "case_type": "civil_loan",
api\tests\test_auth.py:16:    "case_type": "civil_loan",
api\tests\test_auth_jwt.py:154:            "case_type": "civil_loan",
api\tests\test_auth_jwt.py:170:            "case_type": "civil_loan",
api\tests\test_auth_jwt.py:186:            "case_type": "civil_loan",
api\tests\test_case_index.py:22:                     case_type: str = "civil_loan",
api\tests\test_case_index.py:34:            "case_type": case_type,
api\tests\test_case_index.py:103:        "case_type": "civil_loan",
api\tests\test_case_index.py:124:        "case_type": "civil_loan",
api\tests\test_case_index.py:150:        ("case-1", "created",   "civil_loan",    "2026-04-01T00:00:00Z"),
api\tests\test_case_index.py:151:        ("case-2", "analyzed",  "civil_loan",    "2026-04-02T00:00:00Z"),
api\tests\test_case_index.py:153:        ("case-4", "extracting","civil_loan",    "2026-04-04T00:00:00Z"),
api\tests\test_case_index.py:160:            "case_type": ctype,
api\tests\test_case_index.py:177:def test_query_filter_by_case_type():
api\tests\test_case_index.py:179:    entries, total = idx.query(None, "civil_loan", None, None, 1, 20, "-created_at")
api\tests\test_case_index.py:181:    assert all(e["case_type"] == "civil_loan" for e in entries)
api\tests\test_case_index.py:196:    entries, total = idx.query("analyzed", "civil_loan", None, None, 1, 20, 
"-created_at")
api\tests\test_case_scenario_endpoints.py:94:            "case_type": "civil_loan",
api\tests\test_case_scenario_endpoints.py:158:                "case_type": "civil_loan",
api\tests\test_case_scenario_endpoints.py:176:                "case_type": "civil_loan",
api\tests\test_case_store_persistence.py:42:    "case_type": "civil_loan",
api\tests\test_e2e_api_flow.py:47:    "case_type": "civil_loan",
api\tests\test_e2e_api_flow.py:321:        "case_type": "civil_loan",
api\tests\test_e2e_lifecycle.py:32:_CIVIL_LOAN_CASE = {
api\tests\test_e2e_lifecycle.py:33:    "case_type": "civil_loan",
api\tests\test_e2e_lifecycle.py:264:    case_id = client.post("/api/cases/", json=_CIVIL_LOAN_CASE).json()["case_id"]
api\tests\test_e2e_lifecycle.py:292:    def test_happy_path_civil_loan(self, isolated_client):
api\tests\test_e2e_lifecycle.py:296:        resp = client.post("/api/cases/", json=_CIVIL_LOAN_CASE)
api\tests\test_e2e_lifecycle.py:374:        resp = client.post("/api/cases/", json=_CIVIL_LOAN_CASE)
api\tests\test_e2e_lifecycle.py:387:        resp = client.post("/api/cases/", json=_CIVIL_LOAN_CASE)
api\tests\test_e2e_lifecycle.py:413:        resp = client.post("/api/cases/", json=_CIVIL_LOAN_CASE)
api\tests\test_e2e_lifecycle.py:423:        resp = client.post("/api/cases/", json=_CIVIL_LOAN_CASE)
api\tests\test_e2e_lifecycle.py:436:        resp = client.post("/api/cases/", json=_CIVIL_LOAN_CASE)
api\tests\test_e2e_lifecycle.py:446:        resp = client.post("/api/cases/", json=_CIVIL_LOAN_CASE)
api\tests\test_e2e_lifecycle.py:478:        """Missing case_type should return 422 (Pydantic validation)."""
api\tests\test_e2e_lifecycle.py:500:        resp = client.post("/api/cases/", json=_CIVIL_LOAN_CASE)
api\tests\test_e2e_lifecycle.py:518:        resp = client.post("/api/cases/", json=_CIVIL_LOAN_CASE)
api\tests\test_e2e_lifecycle.py:551:        assert data["case_type"] == "civil_loan"
api\tests\test_e2e_lifecycle.py:609:        resp = client.post("/api/cases/", json=_CIVIL_LOAN_CASE)
api\tests\test_e2e_lifecycle.py:627:        resp = client.post("/api/cases/", json=_CIVIL_LOAN_CASE)
api\tests\test_e2e_lifecycle.py:641:        resp = client.post("/api/cases/", json=_CIVIL_LOAN_CASE)
api\tests\test_end_to_end_flow.py:39:    "case_type": "civil_loan",
api\tests\test_runtime_regressions.py:19:    "case_type": "civil_loan",
api\tests\test_runtime_regressions.py:246:def test_scenario_service_reads_case_type_from_baseline_metadata(tmp_path):
api\tests\test_runtime_regressions.py:255:                "case_type": "real_estate",
api\tests\test_runtime_regressions.py:316:    assert simulator_cls.call_args.kwargs["case_type"] == "real_estate"
api\tests\test_unit15_endpoints.py:37:        "case_type": "civil_loan",


Cannot set property. Property setting is supported only on core types in this language mode.
At line:1 char:1
+ [Console]::OutputEncoding=[System.Text.Encoding]::UTF8;
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : InvalidOperation: (:) [], RuntimeException
    + FullyQualifiedErrorId : PropertySetterNotSupportedInConstrainedLanguage
 

2026-04-07T11:33:18.766172Z ERROR codex_core::tools::router: error=`"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -NoProfile -Command 'Get-ChildItem -Path api -Recurse -File | Where-Object { $_.FullName -notlike '"'*\\tests\\*' }"` rejected: blocked by policy
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -NoProfile -Command 'Get-ChildItem -Path api -Recurse -File | Where-Object { $_.FullName -notlike '"'*\\tests\\*' }" in C:/Users/david/dev/case-adversarial-engine
 declined in 0ms:
`"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -NoProfile -Command 'Get-ChildItem -Path api -Recurse -File | Where-Object { $_.FullName -notlike '"'*\\tests\\*' }"` rejected: blocked by policy
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -NoProfile -Command "Select-String -Path 'cases\\**\\*.yaml' -Pattern 'case_type:'" in C:/Users/david/dev/case-adversarial-engine
 succeeded in 591ms:
Cannot set property. Property setting is supported only on core types in this language mode.
At line:1 char:1
+ [Console]::OutputEncoding=[System.Text.Encoding]::UTF8;
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : InvalidOperation: (:) [], RuntimeException
    + FullyQualifiedErrorId : PropertySetterNotSupportedInConstrainedLanguage
 

exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -NoProfile -Command 'Get-ChildItem -Path cases -Recurse -File' in C:/Users/david/dev/case-adversarial-engine
 succeeded in 573ms:


    Directory: C:\Users\david\dev\case-adversarial-engine\cases


Mode                 LastWriteTime         Length Name                                                                 
----                 -------------         ------ ----                                                                 
-a----         3/31/2026   1:09 PM           6869 labor_dispute_1.yaml                                                 
-a----         3/31/2026   1:09 PM           6803 labor_dispute_2.yaml                                                 
-a----         3/31/2026   1:09 PM           6851 labor_dispute_3.yaml                                                 
-a----         3/31/2026   1:09 PM           6753 real_estate_1.yaml                                                   
-a----         3/31/2026   1:09 PM           6914 real_estate_2.yaml                                                   
-a----         3/31/2026   1:09 PM           7734 real_estate_3.yaml                                                   
-a----         3/30/2026   7:36 PM          10900 wang_v_chen_zhuang_2025.yaml                                         
-a----         3/30/2026   7:36 PM           9960 wang_zhang_2022.yaml                                                 


Cannot set property. Property setting is supported only on core types in this language mode.
At line:1 char:1
+ [Console]::OutputEncoding=[System.Text.Encoding]::UTF8;
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : InvalidOperation: (:) [], RuntimeException
    + FullyQualifiedErrorId : PropertySetterNotSupportedInConstrainedLanguage
 

exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -NoProfile -Command "Select-String -Path 'engines\\case_structuring\\case_extractor\\prompts\\generic.py' -Pattern 'all civil litigation|civil_loan|plaintiff|defendant|financials'" in C:/Users/david/dev/case-adversarial-engine
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -NoProfile -Command "Select-String -Path 'engines\\case_structuring\\case_extractor\\extractor.py' -Pattern 'plaintiff|defendant|financials|civil_loan|case_type'" in C:/Users/david/dev/case-adversarial-engine
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -NoProfile -Command "Select-String -Path 'engines\\document_assistance\\schemas.py' -Pattern 'civil_loan|labor_dispute|real_estate|pleading|defense|cross_exam'" in C:/Users/david/dev/case-adversarial-engine
 succeeded in 626ms:

engines\case_structuring\case_extractor\prompts\generic.py:6:then extracts parties, materials, claims, defenses, and 
financials.
engines\case_structuring\case_extractor\prompts\generic.py:13:You are a senior Chinese legal document analyst, expert 
in all civil litigation case types.
engines\case_structuring\case_extractor\prompts\generic.py:20:1. 识别案由类型（civil_loan, labor_dispute, real_estate, 
或其他）
engines\case_structuring\case_extractor\prompts\generic.py:54:  "case_type": "civil_loan | labor_dispute | real_estate 
| other",
engines\case_structuring\case_extractor\prompts\generic.py:55:  "plaintiff": {
engines\case_structuring\case_extractor\prompts\generic.py:56:    "role": "plaintiff",
engines\case_structuring\case_extractor\prompts\generic.py:60:  "defendant": {
engines\case_structuring\case_extractor\prompts\generic.py:61:    "role": "defendant",
engines\case_structuring\case_extractor\prompts\generic.py:72:      "submitter": "plaintiff 或 defendant",
engines\case_structuring\case_extractor\prompts\generic.py:93:  "financials": null
engines\case_structuring\case_extractor\prompts\generic.py:100:- financials 仅在 case_type 为 civil_loan 
时填写，其余情况设为 null


Cannot set property. Property setting is supported only on core types in this language mode.
At line:1 char:1
+ [Console]::OutputEncoding=[System.Text.Encoding]::UTF8;
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : InvalidOperation: (:) [], RuntimeException
    + FullyQualifiedErrorId : PropertySetterNotSupportedInConstrainedLanguage
 

 succeeded in 646ms:

engines\case_structuring\case_extractor\extractor.py:6:  1. LLM extracts structured JSON (parties, materials, claims, 
defenses, financials)
engines\case_structuring\case_extractor\extractor.py:162:        p_name = llm.plaintiff.name or "原告"
engines\case_structuring\case_extractor\extractor.py:163:        d_name = llm.defendant.name or "被告"
engines\case_structuring\case_extractor\extractor.py:165:        auto_case_id = case_id or 
f"case-{llm.case_type}-{uuid.uuid4().hex[:8]}"
engines\case_structuring\case_extractor\extractor.py:166:        p_id = llm.plaintiff.party_id or 
f"party-plaintiff-{_slugify(p_name) or 'p'}"
engines\case_structuring\case_extractor\extractor.py:167:        d_id = llm.defendant.party_id or 
f"party-defendant-{_slugify(d_name) or 'd'}"
engines\case_structuring\case_extractor\extractor.py:170:        if not llm.plaintiff.name:
engines\case_structuring\case_extractor\extractor.py:171:            missing_fields.append("plaintiff.name")
engines\case_structuring\case_extractor\extractor.py:172:        if not llm.defendant.name:
engines\case_structuring\case_extractor\extractor.py:173:            missing_fields.append("defendant.name")
engines\case_structuring\case_extractor\extractor.py:181:            "plaintiff": {"party_id": p_id, "name": p_name},
engines\case_structuring\case_extractor\extractor.py:182:            "defendant": {"party_id": d_id, "name": d_name},
engines\case_structuring\case_extractor\extractor.py:201:            if m.submitter == "defendant":
engines\case_structuring\case_extractor\extractor.py:207:            "plaintiff": p_materials,
engines\case_structuring\case_extractor\extractor.py:208:            "defendant": d_materials,
engines\case_structuring\case_extractor\extractor.py:234:        # Build financials (only for loan cases)
engines\case_structuring\case_extractor\extractor.py:235:        financials: dict[str, Any] | None = None
engines\case_structuring\case_extractor\extractor.py:236:        if llm.financials and llm.case_type == "civil_loan":
engines\case_structuring\case_extractor\extractor.py:237:            financials = {
engines\case_structuring\case_extractor\extractor.py:238:                "loans": [loan.model_dump() for loan in 
llm.financials.loans],
engines\case_structuring\case_extractor\extractor.py:239:                "repayments": [r.model_dump() for r in 
llm.financials.repayments],
engines\case_structuring\case_extractor\extractor.py:240:                "disputed": [d.model_dump() for d in 
llm.financials.disputed],
engines\case_structuring\case_extractor\extractor.py:241:                "claim_entries": [ce.model_dump() for ce in 
llm.financials.claim_entries],
engines\case_structuring\case_extractor\extractor.py:247:            case_type=llm.case_type,
engines\case_structuring\case_extractor\extractor.py:253:            financials=financials,
engines\case_structuring\case_extractor\extractor.py:274:        header += f"# Case type: {extracted.case_type}\n\n"
engines\case_structuring\case_extractor\extractor.py:294:        required = ["case_id", "case_slug", "case_type", 
"parties", "materials", "claims", "defenses"]
engines\case_structuring\case_extractor\extractor.py:296:        must_be_nonempty = {"case_id", "case_slug", 
"case_type", "parties", "materials", "claims"}
engines\case_structuring\case_extractor\extractor.py:306:        for role in ("plaintiff", "defendant"):
engines\case_structuring\case_extractor\extractor.py:314:        if not mats.get("plaintiff") and not 
mats.get("defendant"):


Cannot set property. Property setting is supported only on core types in this language mode.
At line:1 char:1
+ [Console]::OutputEncoding=[System.Text.Encoding]::UTF8;
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : InvalidOperation: (:) [], RuntimeException
    + FullyQualifiedErrorId : PropertySetterNotSupportedInConstrainedLanguage
 

 succeeded in 656ms:

engines\document_assistance\schemas.py:60:class PleadingDraft(BaseModel):
engines\document_assistance\schemas.py:62:    Pleading draft skeleton — used by plaintiff.
engines\document_assistance\schemas.py:91:class DefenseStatement(BaseModel):
engines\document_assistance\schemas.py:93:    Defense statement skeleton — used by defendant.
engines\document_assistance\schemas.py:100:    defense_claim_items: list[NumberedItem] = Field(
engines\document_assistance\schemas.py:101:        description="实质性抗辩主张条目（至少 1 条回应原告核心主张）/ 
Substantive defense claim items"
engines\document_assistance\schemas.py:110:    @field_validator("denial_items", "defense_claim_items", 
"counter_prayer_items", mode="before")
engines\document_assistance\schemas.py:159:    doc_type: str = Field(description="文书类型：'pleading' | 'defense' | 
'cross_exam'")
engines\document_assistance\schemas.py:160:    case_type: str = Field(description="案件类型：'civil_loan' | 
'labor_dispute' | 'real_estate'")
engines\document_assistance\schemas.py:180:    doc_type: str = Field(description="'pleading' | 'defense' | 
'cross_exam'")
engines\document_assistance\schemas.py:181:    case_type: str = Field(description="'civil_loan' | 'labor_dispute' | 
'real_estate'")
engines\document_assistance\schemas.py:184:    content: Union[PleadingDraft, DefenseStatement, 
CrossExaminationOpinion] = Field(


Cannot set property. Property setting is supported only on core types in this language mode.
At line:1 char:1
+ [Console]::OutputEncoding=[System.Text.Encoding]::UTF8;
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : InvalidOperation: (:) [], RuntimeException
    + FullyQualifiedErrorId : PropertySetterNotSupportedInConstrainedLanguage
 

exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -NoProfile -Command "Select-String -Path 'engines\\pretrial_conference\\cross_examination_engine.py' -Pattern 'from \\.prompts\\.civil_loan|plaintiff_party_id|defendant_party_id|被告代理律师|原告代理律师'" in C:/Users/david/dev/case-adversarial-engine
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -NoProfile -Command "Select-String -Path 'engines\\pretrial_conference\\prompts\\judge.py' -Pattern '民事审判法官|原告|被告|金额计算|calculation_issue'" in C:/Users/david/dev/case-adversarial-engine
2026-04-07T11:35:50.994445Z ERROR codex_core::tools::router: error=`"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -NoProfile -Command "Select-String -Path 'engines\\procedure_setup\\planner.py','engines\\procedure_setup\\schemas.py','engines\\procedure_setup\\validator.py' -Pattern '原告起诉状已接收|被告已收到应诉通知|PHASE_ORDER|judge_questions|output_branching|evidence_submission_deadline_days|evidence_challenge_window_days'"` rejected: blocked by policy
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -NoProfile -Command "Select-String -Path 'engines\\procedure_setup\\planner.py','engines\\procedure_setup\\schemas.py','engines\\procedure_setup\\validator.py' -Pattern '原告起诉状已接收|被告已收到应诉通知|PHASE_ORDER|judge_questions|output_branching|evidence_submission_deadline_days|evidence_challenge_window_days'" in C:/Users/david/dev/case-adversarial-engine
 declined in 0ms:
`"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -NoProfile -Command "Select-String -Path 'engines\\procedure_setup\\planner.py','engines\\procedure_setup\\schemas.py','engines\\procedure_setup\\validator.py' -Pattern '原告起诉状已接收|被告已收到应诉通知|PHASE_ORDER|judge_questions|output_branching|evidence_submission_deadline_days|evidence_challenge_window_days'"` rejected: blocked by policy
 succeeded in 596ms:

engines\pretrial_conference\prompts\judge.py:24:你是一位经验丰富的民事审判法官，正在主持庭前会议。
engines\pretrial_conference\prompts\judge.py:41:- 优先关注金额计算争点（calculation_issue）和存在阻断条件的争点
engines\pretrial_conference\prompts\judge.py:103:        party_block = f"\n\n## 当事人\n- 原告: 
{plaintiff_party_id}\n- 被告: {defendant_party_id}"
engines\pretrial_conference\prompts\judge.py:134:- 优先关注金额计算争点和阻断条件相关争点


Cannot set property. Property setting is supported only on core types in this language mode.
At line:1 char:1
+ [Console]::OutputEncoding=[System.Text.Encoding]::UTF8;
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : InvalidOperation: (:) [], RuntimeException
    + FullyQualifiedErrorId : PropertySetterNotSupportedInConstrainedLanguage
 

 succeeded in 618ms:

engines\pretrial_conference\cross_examination_engine.py:34:from .prompts.civil_loan import (
engines\pretrial_conference\cross_examination_engine.py:77:        plaintiff_party_id: str,
engines\pretrial_conference\cross_examination_engine.py:78:        defendant_party_id: str,
engines\pretrial_conference\cross_examination_engine.py:102:        plaintiff_ev = [ev for ev in submitted if 
ev.owner_party_id == plaintiff_party_id]
engines\pretrial_conference\cross_examination_engine.py:103:        defendant_ev = [ev for ev in submitted if 
ev.owner_party_id == defendant_party_id]
engines\pretrial_conference\cross_examination_engine.py:111:                examiner_party_id=defendant_party_id,
engines\pretrial_conference\cross_examination_engine.py:112:                examiner_role="被告代理律师",
engines\pretrial_conference\cross_examination_engine.py:123:                examiner_party_id=plaintiff_party_id,
engines\pretrial_conference\cross_examination_engine.py:124:                examiner_role="原告代理律师",
engines\pretrial_conference\cross_examination_engine.py:133:            plaintiff_party_id: defendant_party_id,
engines\pretrial_conference\cross_examination_engine.py:134:            defendant_party_id: plaintiff_party_id,


Cannot set property. Property setting is supported only on core types in this language mode.
At line:1 char:1
+ [Console]::OutputEncoding=[System.Text.Encoding]::UTF8;
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : InvalidOperation: (:) [], RuntimeException
    + FullyQualifiedErrorId : PropertySetterNotSupportedInConstrainedLanguage
 

codex
## CRITICAL
1. Problem: the plan’s central premise is wrong; this is not “mostly prompt expansion.” Evidence: in `问题 3：Model 层需求` and `总结`, the document limits core work to `criminal.py` / `administrative.py` plus a small plugin extension, but shared models already hard-code civil-side semantics: [core.py](C:/Users/david/dev/case-adversarial-engine/engines/shared/models/core.py:200), [core.py](C:/Users/david/dev/case-adversarial-engine/engines/shared/models/core.py:316), [analysis.py](C:/Users/david/dev/case-adversarial-engine/engines/shared/models/analysis.py:567), [pipeline.py](C:/Users/david/dev/case-adversarial-engine/engines/shared/models/pipeline.py:217). Fix: make Batch 6.0 start with a shared-model neutralization matrix, not subtype prompts.

2. Problem: the engine grading table is materially under-estimated. Evidence: `问题 2：Engine 适配清单` marks `case_extraction` N0 and `case_extractor` N0, but [schemas.py](C:/Users/david/dev/case-adversarial-engine/engines/case_extraction/schemas.py:60) only allows the three civil case types and uses `plaintiff_name` / `defendant_names`; the “generic” extractor prompt is explicitly “all civil litigation case types” and only keeps `financials` for `civil_loan` in [generic.py](C:/Users/david/dev/case-adversarial-engine/engines/case_structuring/case_extractor/prompts/generic.py:13) and [extractor.py](C:/Users/david/dev/case-adversarial-engine/engines/case_structuring/case_extractor/extractor.py:162). Fix: re-grade `case_extraction` as N3/N4 and `case_structuring/case_extractor` as at least N2/N3.

3. Problem: `procedure_setup` and `pretrial_conference` are not “maybe phase tweaks”; they are civil-process engines. Evidence: [planner.py](C:/Users/david/dev/case-adversarial-engine/engines/procedure_setup/planner.py:112) assumes “原告起诉状已接收 / 被告已收到应诉通知,” and [schemas.py](C:/Users/david/dev/case-adversarial-engine/engines/procedure_setup/schemas.py:34) makes the eight civil phases a canonical invariant; worse, [cross_examination_engine.py](C:/Users/david/dev/case-adversarial-engine/engines/pretrial_conference/cross_examination_engine.py:34) directly imports the `civil_loan` prompt, and [judge.py](C:/Users/david/dev/case-adversarial-engine/engines/pretrial_conference/prompts/judge.py:24) says “民事审判法官.” Fix: re-grade both to N4 and treat criminal/admin procedure as separate family implementations, not prompt overrides.

4. Problem: `amount_calculator` bypass does not solve the downstream amount coupling. Evidence: in `问题 2/7`, the plan treats `amount_calculator` as the main hard knot, but reporting code still assumes amount semantics: [mediation_range.py](C:/Users/david/dev/case-adversarial-engine/engines/report_generation/mediation_range.py:41), [docx_generator.py](C:/Users/david/dev/case-adversarial-engine/engines/report_generation/docx_generator.py:33), [layer4_appendix.py](C:/Users/david/dev/case-adversarial-engine/engines/report_generation/v3/layer4_appendix.py:371). Fix: introduce an explicit `has_amount_semantics` capability and family-specific report sections before any runner-level bypass.

5. Problem: the subtype-selection rationale is not trustworthy, and the `>60%` coverage claim is unsupported. Evidence: `问题 1：案种范围与 MVP 子类型` dismisses `交通肇事罪` as “已被 civil_loan / real_estate 部分覆盖,” which is plainly false, and picks `work_injury_recognition` because it forms a cross-family “natural companion” with labor disputes, which increases scope rather than reducing it. Fix: drop the coverage percentage unless backed by filing/query data, and choose MVP subtypes for architecture leverage plus demand, not doctrinal neatness.

## IMPORTANT
6. Problem: `CaseTypePlugin + case_family()` is the wrong abstraction boundary. Evidence: `问题 3：CaseTypePlugin Protocol 需要扩展吗？` assumes one extra method may be enough, but critical code paths bypass the plugin entirely: [engine.py](C:/Users/david/dev/case-adversarial-engine/engines/document_assistance/engine.py:26), [cross_examination_engine.py](C:/Users/david/dev/case-adversarial-engine/engines/pretrial_conference/cross_examination_engine.py:34). Fix: replace this with a family-spec object that covers roles, evidence taxonomy, procedure phases, report sections, amount capability, and supported document types.

7. Problem: the two-layer prompt inheritance plan is optimistic to the point of fantasy. Evidence: `问题 5：Prompt 工程量估算` assumes 80% reusable family structure, but the actual “generic” extractor prompt is civil-only [generic.py](C:/Users/david/dev/case-adversarial-engine/engines/case_structuring/case_extractor/prompts/generic.py:13), and the judge prompt prioritizes `calculation_issue` and plaintiff/defendant framing [judge.py](C:/Users/david/dev/case-adversarial-engine/engines/pretrial_conference/prompts/judge.py:41). Fix: validate inheritance on one criminal engine and one admin engine first; if either needs structural divergence, abandon the base/override dogma.

8. Problem: `document_assistance` is under-scoped; this is schema work, not just registry work. Evidence: `问题 2` calls it N1-N3, but [schemas.py](C:/Users/david/dev/case-adversarial-engine/engines/document_assistance/schemas.py:159) hard-codes only `pleading|defense|cross_exam` and only the three civil case types, while [schemas.py](C:/Users/david/dev/case-adversarial-engine/engines/document_assistance/schemas.py:60) and [schemas.py](C:/Users/david/dev/case-adversarial-engine/engines/document_assistance/schemas.py:91) define plaintiff-only and defendant-only document skeletons. Fix: define family-specific doc schemas and a discriminated `doc_type` contract before adding any criminal/admin prompt files.

9. Problem: the test estimate is far too low. Evidence: `问题 6：Test / Fixture / Golden 估算` says ~30-40 files modified, but whole-system tests are parameterized over exactly three case types in [test_pipeline_structural.py](C:/Users/david/dev/case-adversarial-engine/tests/acceptance/test_pipeline_structural.py:32), [test_n3_consistency.py](C:/Users/david/dev/case-adversarial-engine/tests/acceptance/test_n3_consistency.py:33), and v3 acceptance/integration in [test_multi_case_integration.py](C:/Users/david/dev/case-adversarial-engine/engines/report_generation/v3/tests/test_multi_case_integration.py:69). Fix: do a file-level impact inventory first; assume well above 40 touched tests once acceptance, API, integration, and v3 are included.

10. Problem: the 15-week “realistic” timeline is still optimistic because the bottleneck is not just vocab review. Evidence: the codebase contains hard civil assumptions in shared models, procedure engines, report renderers, acceptance suites, and API tests such as [test_e2e_lifecycle.py](C:/Users/david/dev/case-adversarial-engine/api/tests/test_e2e_lifecycle.py:292) and [test_full_pipeline.py](C:/Users/david/dev/case-adversarial-engine/tests/integration/test_full_pipeline.py:295). Fix: re-estimate after a 2-3 day coupling audit; more realistically, ship one family and one subtype first.

11. Problem: the plan ignores evidence-taxonomy and role-model conflicts. Evidence: `EvidenceType` in [core.py](C:/Users/david/dev/case-adversarial-engine/engines/shared/models/core.py:49) is explicitly tied to civil evidence categories, while `AgentRole` and `Perspective` only model plaintiff/defendant/judge in [core.py](C:/Users/david/dev/case-adversarial-engine/engines/shared/models/core.py:198) and [core.py](C:/Users/david/dev/case-adversarial-engine/engines/shared/models/core.py:315). Fix: decide whether criminal will model prosecutor/defendant separately or be forcibly mapped onto plaintiff/defendant; if the latter, document the semantic loss and its downstream consequences.

## MINOR
12. Problem: Batch 6.0 is overloaded and its blast-radius estimate is fake. Evidence: `问题 7：风险 + 批次拆分` puts schema/protocol changes, eval harness, and six vocab studies into one preflight and claims `~10 文件, ~30 测试`; the actual surfaces above already exceed that. Fix: split 6.0 into `audit`, `neutralization`, and `eval/research` sub-batches.

13. Problem: the vocab-note deliverable is too thin to stabilize implementation. Evidence: `问题 4：研究产出物` budgets 300-500 words per subtype; that is enough for a memo, not for freezing burden, relief, evidence, and phase vocab. Fix: require a structured matrix per subtype: parties, burden, relief, evidence categories, phase model, exclusions, and negative examples.

## NIT
14. Problem: the summary keeps describing this as “6 new PromptProfile values,” which hides the real change. Evidence: `总结` and `8 个问题的一句话答案` frame the work as subtype additions when the actual change is introducing two new litigation families. Fix: rewrite the summary around family-neutralization cost, not prompt count.

15. Problem: the document uses fake precision in risky places: `>60%`, `~10 files`, `~30 tests`, `15 weeks realistic`. Evidence: those numbers are asserted, not demonstrated, and the codebase evidence cuts against them. Fix: replace them with bounded ranges tied to an audit output.

Net: this plan is not ready to execute as written. The codebase is still civil-shaped at the shared-model, procedure, reporting, fixture, and API layers. I would not approve anything beyond a short coupling-audit batch plus one-family, one-subtype spike.
tokens used
627,539
## CRITICAL
1. Problem: the plan’s central premise is wrong; this is not “mostly prompt expansion.” Evidence: in `问题 3：Model 层需求` and `总结`, the document limits core work to `criminal.py` / `administrative.py` plus a small plugin extension, but shared models already hard-code civil-side semantics: [core.py](C:/Users/david/dev/case-adversarial-engine/engines/shared/models/core.py:200), [core.py](C:/Users/david/dev/case-adversarial-engine/engines/shared/models/core.py:316), [analysis.py](C:/Users/david/dev/case-adversarial-engine/engines/shared/models/analysis.py:567), [pipeline.py](C:/Users/david/dev/case-adversarial-engine/engines/shared/models/pipeline.py:217). Fix: make Batch 6.0 start with a shared-model neutralization matrix, not subtype prompts.

2. Problem: the engine grading table is materially under-estimated. Evidence: `问题 2：Engine 适配清单` marks `case_extraction` N0 and `case_extractor` N0, but [schemas.py](C:/Users/david/dev/case-adversarial-engine/engines/case_extraction/schemas.py:60) only allows the three civil case types and uses `plaintiff_name` / `defendant_names`; the “generic” extractor prompt is explicitly “all civil litigation case types” and only keeps `financials` for `civil_loan` in [generic.py](C:/Users/david/dev/case-adversarial-engine/engines/case_structuring/case_extractor/prompts/generic.py:13) and [extractor.py](C:/Users/david/dev/case-adversarial-engine/engines/case_structuring/case_extractor/extractor.py:162). Fix: re-grade `case_extraction` as N3/N4 and `case_structuring/case_extractor` as at least N2/N3.

3. Problem: `procedure_setup` and `pretrial_conference` are not “maybe phase tweaks”; they are civil-process engines. Evidence: [planner.py](C:/Users/david/dev/case-adversarial-engine/engines/procedure_setup/planner.py:112) assumes “原告起诉状已接收 / 被告已收到应诉通知,” and [schemas.py](C:/Users/david/dev/case-adversarial-engine/engines/procedure_setup/schemas.py:34) makes the eight civil phases a canonical invariant; worse, [cross_examination_engine.py](C:/Users/david/dev/case-adversarial-engine/engines/pretrial_conference/cross_examination_engine.py:34) directly imports the `civil_loan` prompt, and [judge.py](C:/Users/david/dev/case-adversarial-engine/engines/pretrial_conference/prompts/judge.py:24) says “民事审判法官.” Fix: re-grade both to N4 and treat criminal/admin procedure as separate family implementations, not prompt overrides.

4. Problem: `amount_calculator` bypass does not solve the downstream amount coupling. Evidence: in `问题 2/7`, the plan treats `amount_calculator` as the main hard knot, but reporting code still assumes amount semantics: [mediation_range.py](C:/Users/david/dev/case-adversarial-engine/engines/report_generation/mediation_range.py:41), [docx_generator.py](C:/Users/david/dev/case-adversarial-engine/engines/report_generation/docx_generator.py:33), [layer4_appendix.py](C:/Users/david/dev/case-adversarial-engine/engines/report_generation/v3/layer4_appendix.py:371). Fix: introduce an explicit `has_amount_semantics` capability and family-specific report sections before any runner-level bypass.

5. Problem: the subtype-selection rationale is not trustworthy, and the `>60%` coverage claim is unsupported. Evidence: `问题 1：案种范围与 MVP 子类型` dismisses `交通肇事罪` as “已被 civil_loan / real_estate 部分覆盖,” which is plainly false, and picks `work_injury_recognition` because it forms a cross-family “natural companion” with labor disputes, which increases scope rather than reducing it. Fix: drop the coverage percentage unless backed by filing/query data, and choose MVP subtypes for architecture leverage plus demand, not doctrinal neatness.

## IMPORTANT
6. Problem: `CaseTypePlugin + case_family()` is the wrong abstraction boundary. Evidence: `问题 3：CaseTypePlugin Protocol 需要扩展吗？` assumes one extra method may be enough, but critical code paths bypass the plugin entirely: [engine.py](C:/Users/david/dev/case-adversarial-engine/engines/document_assistance/engine.py:26), [cross_examination_engine.py](C:/Users/david/dev/case-adversarial-engine/engines/pretrial_conference/cross_examination_engine.py:34). Fix: replace this with a family-spec object that covers roles, evidence taxonomy, procedure phases, report sections, amount capability, and supported document types.

7. Problem: the two-layer prompt inheritance plan is optimistic to the point of fantasy. Evidence: `问题 5：Prompt 工程量估算` assumes 80% reusable family structure, but the actual “generic” extractor prompt is civil-only [generic.py](C:/Users/david/dev/case-adversarial-engine/engines/case_structuring/case_extractor/prompts/generic.py:13), and the judge prompt prioritizes `calculation_issue` and plaintiff/defendant framing [judge.py](C:/Users/david/dev/case-adversarial-engine/engines/pretrial_conference/prompts/judge.py:41). Fix: validate inheritance on one criminal engine and one admin engine first; if either needs structural divergence, abandon the base/override dogma.

8. Problem: `document_assistance` is under-scoped; this is schema work, not just registry work. Evidence: `问题 2` calls it N1-N3, but [schemas.py](C:/Users/david/dev/case-adversarial-engine/engines/document_assistance/schemas.py:159) hard-codes only `pleading|defense|cross_exam` and only the three civil case types, while [schemas.py](C:/Users/david/dev/case-adversarial-engine/engines/document_assistance/schemas.py:60) and [schemas.py](C:/Users/david/dev/case-adversarial-engine/engines/document_assistance/schemas.py:91) define plaintiff-only and defendant-only document skeletons. Fix: define family-specific doc schemas and a discriminated `doc_type` contract before adding any criminal/admin prompt files.

9. Problem: the test estimate is far too low. Evidence: `问题 6：Test / Fixture / Golden 估算` says ~30-40 files modified, but whole-system tests are parameterized over exactly three case types in [test_pipeline_structural.py](C:/Users/david/dev/case-adversarial-engine/tests/acceptance/test_pipeline_structural.py:32), [test_n3_consistency.py](C:/Users/david/dev/case-adversarial-engine/tests/acceptance/test_n3_consistency.py:33), and v3 acceptance/integration in [test_multi_case_integration.py](C:/Users/david/dev/case-adversarial-engine/engines/report_generation/v3/tests/test_multi_case_integration.py:69). Fix: do a file-level impact inventory first; assume well above 40 touched tests once acceptance, API, integration, and v3 are included.

10. Problem: the 15-week “realistic” timeline is still optimistic because the bottleneck is not just vocab review. Evidence: the codebase contains hard civil assumptions in shared models, procedure engines, report renderers, acceptance suites, and API tests such as [test_e2e_lifecycle.py](C:/Users/david/dev/case-adversarial-engine/api/tests/test_e2e_lifecycle.py:292) and [test_full_pipeline.py](C:/Users/david/dev/case-adversarial-engine/tests/integration/test_full_pipeline.py:295). Fix: re-estimate after a 2-3 day coupling audit; more realistically, ship one family and one subtype first.

11. Problem: the plan ignores evidence-taxonomy and role-model conflicts. Evidence: `EvidenceType` in [core.py](C:/Users/david/dev/case-adversarial-engine/engines/shared/models/core.py:49) is explicitly tied to civil evidence categories, while `AgentRole` and `Perspective` only model plaintiff/defendant/judge in [core.py](C:/Users/david/dev/case-adversarial-engine/engines/shared/models/core.py:198) and [core.py](C:/Users/david/dev/case-adversarial-engine/engines/shared/models/core.py:315). Fix: decide whether criminal will model prosecutor/defendant separately or be forcibly mapped onto plaintiff/defendant; if the latter, document the semantic loss and its downstream consequences.

## MINOR
12. Problem: Batch 6.0 is overloaded and its blast-radius estimate is fake. Evidence: `问题 7：风险 + 批次拆分` puts schema/protocol changes, eval harness, and six vocab studies into one preflight and claims `~10 文件, ~30 测试`; the actual surfaces above already exceed that. Fix: split 6.0 into `audit`, `neutralization`, and `eval/research` sub-batches.

13. Problem: the vocab-note deliverable is too thin to stabilize implementation. Evidence: `问题 4：研究产出物` budgets 300-500 words per subtype; that is enough for a memo, not for freezing burden, relief, evidence, and phase vocab. Fix: require a structured matrix per subtype: parties, burden, relief, evidence categories, phase model, exclusions, and negative examples.

## NIT
14. Problem: the summary keeps describing this as “6 new PromptProfile values,” which hides the real change. Evidence: `总结` and `8 个问题的一句话答案` frame the work as subtype additions when the actual change is introducing two new litigation families. Fix: rewrite the summary around family-neutralization cost, not prompt count.

15. Problem: the document uses fake precision in risky places: `>60%`, `~10 files`, `~30 tests`, `15 weeks realistic`. Evidence: those numbers are asserted, not demonstrated, and the codebase evidence cuts against them. Fix: replace them with bounded ranges tied to an audit output.

Net: this plan is not ready to execute as written. The codebase is still civil-shaped at the shared-model, procedure, reporting, fixture, and API layers. I would not approve anything beyond a short coupling-audit batch plus one-family, one-subtype spike.

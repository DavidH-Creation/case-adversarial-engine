---
date: 2026-04-07
topic: layer-4-criminal-admin-expansion
type: plan
status: v2 (revised after codex adversarial review)
author: Claude (plan-only, no code written)
---

# Layer 4 Plan：Criminal + Administrative 案种扩展（v2）

> **本文档为 v2，已根据 codex (gpt-5.4 xhigh) adversarial review 重写。** 主要变化：
> 1. **重新定位**：Layer 4 不再被框定为"prompt 扩展为主"，而是 **shared-model 家族级中性化重构 + prompt 扩展**。`AgentRole` / `Perspective` / `EvidenceType` / `procedure_setup` / `pretrial_conference` / `document_assistance` schemas 多处仍硬编码民事语义，必须在加新案种之前先做家族中性化。
> 2. **Engine 评级矩阵上调**（基于 5 处源码 spot-check 验证）：`case_extraction` N0→N3、`case_extractor` N0→N2、`procedure_setup` N2→N4、`pretrial_conference` N2→N4、`document_assistance` 升至 N3-N4、`report_generation(/v3)` 升至 N3。
> 3. **Batch 6.0 拆三**：6.0a 耦合审计 (1 周) → 6.0b 中性化 (2-3 周) → 6.0c 词汇 + eval harness (2-3 周可并行)；realistic 总时间从 15 周 → **18-22 周**。强烈建议先 ship `intentional_injury` 单子类型 PoC 再回头校准估算（见新增的 §"Reality Check"）。
>
> v1 的所有未实证 claim（`>60%` 实务覆盖、prompt `80%` reuse、`~30 tests` 改动、`15 周 realistic`）已被替换为带 "(TBD pending 6.0a)" 标注的范围估算。完整的 finding 摘要 + 处置链接见末尾的 §"Adversarial Review (codex, 2026-04-07)" 决策日志。

> **性质：plan-only 研究报告。** 本文档只回答问题、估算风险和工作量、推荐批次拆分；不写代码、不建 branch、不改源文件。
>
> **上游路线图：** `docs/01_product_roadmap.md §未来扩展` 列出了 Criminal Expansion 和 Administrative Expansion 两条未来线；`docs/archive/plans/2026-03-31-ce-brainstorm-phase4-5-assessment.md` 没有 Layer 4 章节（该文档只覆盖 Phase 4-5 的 Unit 12-22）。本计划是上述两条线的首次具体化设计。
>
> **样板参考：** `docs/archive/plans/2026-04-07-batch-5-unit-22-phase-c.md`（三 enum 中性化样板）、`engines/shared/models/civil_loan.py`（物理隔离样板）、`engines/simulation_run/issue_impact_ranker/prompts/*.py`（按案件类型一套 prompt 的样板）。

---

## 0. Layer 4 现状基线与架构发现

Batch 5 合并后（commit `50f28fe`），codebase 有 **6 个关键结构性事实**是 Layer 4 设计的前提。事实 1-5 是 v1 已识别的；事实 6（civil-hardcoded shared models）是 codex review 暴露后补充的，**这是 v2 重定位的根本原因**：

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

5. **现有引擎清单**（来自 Explore agent 的 inventory，v1 估算 —— 见 §"问题 2" 的 v2 修订表）：
   - **17 个 engine 需要 Layer 4 prompt 扩展**（有 `prompts/` 子目录 + `PROMPT_REGISTRY`）
   - **v1 曾认为 8 个 engine 规则驱动 Layer 4 无需改**，但 v2 重审后 `case_extraction` 和 `case_extractor` 都被上调（schema/prompt 层硬编码三个民事案种）
   - **`amount_calculator`**：硬编码 `if case_type == "civil_loan"` 专属逻辑；v1 误以为这是唯一的 amount 耦合点，v2 发现 rendering 层（`mediation_range.py` / `docx_generator.py` / `v3/layer4_appendix.py`）也假设 amount 语义，必须同步处理
   - **`document_assistance`**：`PROMPT_REGISTRY` 是 `(document_type, case_type)` 二元组键，加新案种意味着加多条；v2 发现 `schemas.py:159-160` 的 `doc_type` 和 `case_type` 都是裸字符串硬编码字段，不是 enum/registry，已升级到 N3-N4

6. **shared models 仍硬编码民事语义**（v2 新增，由 codex review 暴露 + 5 处源码 spot-check 验证）：
   - `engines/shared/models/core.py:200` `AgentRole` 只列出 `plaintiff_agent / defendant_agent / judge_agent / evidence_manager` —— 没有公诉人/辩护人/行政机关代表
   - `engines/shared/models/core.py:49` `EvidenceType` 仍是民事证据分类（书证/物证/证人/视听/电子/鉴定/勘验），缺刑事的"被告人供述/被害人陈述/辨认笔录"和行政的"行政卷宗/听证记录"
   - `engines/shared/models/core.py:316` `Perspective` 同样只 plaintiff/defendant/judge
   - `engines/case_extraction/schemas.py:58-62` LLM tool-schema 的 `case_type` 字段描述硬编码 `civil_loan / labor_dispute / real_estate / unknown`
   - `engines/procedure_setup/planner.py:112` 阶段定义里硬编码"原告起诉状已接收 / 被告已收到应诉通知"
   - `engines/pretrial_conference/cross_examination_engine.py:34` 直接 `from .prompts.civil_loan import ...` —— **plugin 层完全够不到**
   - `engines/document_assistance/schemas.py:159-160` 硬编码 `'pleading' | 'defense' | 'cross_exam'` 和三个民事 case_type
   - **结论**：Layer 4 真正的工作量大头是 **family-level shared model neutralization**，不是 prompt 模块数量。这是 v2 重新定位的根本依据。

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
- 交通肇事罪（§133）：**刻意推迟到 Layer 4.5**。其刑事定罪部分独立于附带民事赔偿，并不被 civil 案种"覆盖"（v1 此处措辞错误，已修正）；推迟的真实理由是它和现有 civil 引擎的 hybrid 集成成本不应在 MVP 阶段引入
- 贪污受贿（§382/385）：领域知识门槛极高，公诉性质不适合对抗式模拟
- 毒品犯罪（§347）：证据结构特殊（控制下交付、线人），很难对标现有 Evidence 模型

**行政（administrative）MVP：3 个子类型**

| 子类型 key | 中文 | 法律依据 | 选它的理由 |
|---|---|---|---|
| `admin_penalty` | 行政处罚不服 | 《行政诉讼法》§12(1) + 《行政处罚法》 | 行政诉讼最大类（约 40%-50%），罚款/吊销/拘留/没收，"处罚明显不当可变更"（§77）有清晰的裁判方向 |
| `info_disclosure` | 政府信息公开 | 《政府信息公开条例》+ 法释〔2011〕17 号 | 法律框架最清晰的行政案由；请求-答复-诉讼链路规整；争点相对局限（是否属于政府信息、是否豁免、答复是否完整），对 Issue 模型友好 |
| `work_injury_recognition` ⚠️ stretch | 工伤认定 | 《工伤保险条例》+ 法释〔2014〕9 号 | 跨"行政"与"社保"，既是工伤认定决定书的合法性审查，又带民事赔偿色彩；和现有 `labor_dispute` 能形成 natural companion。**v2 标注**：cross-family 集成会**增加** scope 而不是减少；如果 Batch 7.1 over-budget，本子类型可推迟到 7.2 |

**不选 MVP 的行政子类型（及原因）**：
- 征地拆迁（《土地管理法》）：政治敏感且法条已经 2019 年改过一轮，案例分歧大
- 行政许可不服：许可门类太多（食品、药品、建设、环评…），每一种都是独立领域
- 行政不作为：争点结构单一（是否具有法定职责 + 是否履行），可能不需要独立 PromptProfile，留给 `admin_penalty` 的 variant 即可

### 推荐范围：刑事 3 + 行政 3 = 6 个新 `PromptProfile` 值

这个数量级保持和当前 civil kernel（3 个 civil 子类型）对称，也为"能不能按案种家族写一个 base prompt，子类型只 override 词汇"的架构选择留出空间。

### 实务覆盖率说明（v2 修订）

> v1 曾断言这 6 个子类型"覆盖 >60% 实务案件"。**该数字已删除** —— 没有任何 filing-volume 数据支持。子类型选择的真实依据是 **架构杠杆**（violence / property / deception 三原型在 criminal；penalty / info-disclosure / work-injury 在 admin），而不是市场占比。
>
> 实证频次研究列入 **Batch 6.0a 耦合审计** 阶段的可选交付物：如果能拿到法院公开判决书的子类型分布数据，则在 6.0a 末尾对 MVP 子类型选择做一次校准。如果拿不到，则 MVP 子类型选择**仅以架构杠杆为依据**，不作覆盖率承诺。

---

## 问题 2：Engine 适配清单（26 个引擎 × Layer 4 工作量）

评级定义：
- **N0**：不需要改（规则驱动或案种无关）
- **N1**：只需加 prompt 模块 + 注册到 `PROMPT_REGISTRY`
- **N2**：N1 + 需要新的 `ALLOWED_IMPACT_TARGETS` 或 plugin 方法
- **N3**：N1/N2 + 需要新的领域字段或子模型
- **N4**：需要重构现有逻辑（硬编码 civil_loan 假设）

**v2 评级表**（v2 上调标注以 🔺 表示，源码证据列引用 5 处 spot-check 验证位置）：

| # | Engine | 目录 | v1 评级 | **v2 评级** | 证据 / 说明 |
|---|---|---|---|---|---|
| 1 | `action_recommender` | `simulation_run/` | N1 | **N1** | PROMPT_REGISTRY 模式，加 6 个 prompt 文件 |
| 2 | `alternative_claim_generator` | `simulation_run/` | N0 | **N0** | 规则驱动 |
| 3 | `attack_chain_optimizer` | `simulation_run/` | N1 | **N1** | PROMPT_REGISTRY 模式 |
| 4 | `credibility_scorer` | `simulation_run/` | N0 | **N0** | 规则驱动（职业放贷人检测是 civil_loan 专属但已是可选分支） |
| 5 | `decision_path_tree` | `simulation_run/` | N1 | **N1** | PROMPT_REGISTRY 模式 |
| 6 | `defense_chain` | `simulation_run/` | N1 | **N1** | PROMPT_REGISTRY 模式（few-shot 可能需要刑事专属版本，见 §"问题 5"） |
| 7 | `evidence_gap_roi_ranker` | `simulation_run/` | N0 | **N0** | 规则驱动 |
| 8 | `hearing_order` | `simulation_run/` | N0 | **N0** | 规则驱动 |
| 9 | `issue_category_classifier` | `simulation_run/` | N1 | **N1** | PROMPT_REGISTRY 模式 |
| 10 | `issue_dependency_graph` | `simulation_run/` | N0 | **N0** | 规则驱动 |
| 11 | `issue_impact_ranker` | `simulation_run/` | N2 ⭐ | **N2** ⭐ | 6 个 prompt 文件 + 6 个 ALLOWED_IMPACT_TARGETS + 6 个 few-shot JSON；Layer 4 词汇研究核心入口 |
| 12 | `case_extractor` | `case_structuring/` | N0 | **N2** 🔺 | v1 误判：`case_extractor/prompts/generic.py:13` 明确写 "all civil litigation case types"，`extractor.py:162` 只对 civil_loan 保留 `financials`。需为 criminal/admin 写专属 prompt 分支 |
| 13 | `admissibility_evaluator` | `case_structuring/` | N1 | **N1** | dict-based registry，加 6 个条目 |
| 14 | `amount_calculator` | `case_structuring/` | N4 ⚠️ | **N4** ⚠️ | 硬编码 civil_loan 逻辑；v2 决策：在 plugin 加 `has_amount_semantics(case_type)` capability，runner 根据该 capability 决定是否调用本引擎；不在 calculator 内部加 criminal/admin 分支 |
| 15 | `evidence_indexer` | `case_structuring/` | N1 | **N1** | module-based |
| 16 | `evidence_weight_scorer` | `case_structuring/` | N1 | **N1** | dict-based |
| 17 | `issue_extractor` | `case_structuring/` | N1 | **N1** | module-based |
| 18 | `adversarial` | `engines/` | N1 | **N2** 🔺 | "控辩"vs"原被告"是 few-shot 示例语义错配（不只是文案），需新建 criminal 专属 few-shot；I6/I11 级别 |
| 19 | `case_extraction` | `engines/` | N0 | **N3** 🔺 | v1 误判：`case_extraction/schemas.py:58-62` 的 `case_type` 字段 LLM tool-schema 硬编码 `civil_loan / labor_dispute / real_estate`；`plaintiff_name` / `defendant_names` 是 schema 必填字段，对刑事公诉人结构完全无法表达。需要 family-discriminated schema |
| 20 | `document_assistance` | `engines/` | N1-N3 ⚠️ | **N3-N4** 🔺 | `schemas.py:159-160` `doc_type` 和 `case_type` 都是裸字符串硬编码字段（`'pleading'\|'defense'\|'cross_exam'`），不是 enum/registry；`schemas.py:60`/`:91` 定义 plaintiff-only 和 defendant-only 文书骨架。需引入 `DocTypeRegistry` + family-specific doc skeleton schemas |
| 21 | `interactive_followup` | `engines/` | N1 | **N1** | PROMPT_REGISTRY 模式 |
| 22 | `pretrial_conference` | `engines/` | N2 ⚠️ | **N4** 🔺 | v1 严重低估：`cross_examination_engine.py:34` 直接 `from .prompts.civil_loan import CROSS_EXAM_SYSTEM, build_cross_exam_user_prompt` —— 是硬 import，不是 registry lookup，**plugin 层完全够不到**。`prompts/judge.py:24` 写 "民事审判法官"。必须按 family 分别实现，不能靠 prompt override |
| 23 | `procedure_setup` | `engines/` | N2-N3 | **N4** 🔺 | v1 严重低估：`procedure_setup/planner.py:112` 阶段定义里硬编码 "原告起诉状已接收 / 被告已收到应诉通知"；`schemas.py:34` 把 8 个民事 phase 写成 canonical invariant。刑事/行政程序流是完全不同的有限状态机，必须 family-级别重写 |
| 24 | `report_generation` | `engines/` | N1-N2 | **N3** 🔺 | rendering 层假设 amount 语义：`mediation_range.py:41`、`docx_generator.py:33`。需 family-conditional report sections + `has_amount_semantics` capability |
| 25 | `similar_case_search` | `engines/` | N0 | **N0** | 案种无关（关键词检索） |
| 26 | `report_generation/v3` | `engines/` (sub) | N2 | **N3** 🔺 | `v3/layer4_appendix.py:371` 同样硬编码 amount 语义。需三份并行 section template（civil/criminal/admin），不能共用一份 |

### 汇总统计（v2 修订）

| 等级 | v1 引擎数 | **v2 引擎数** | 工作量预估（per case_type，除 N4 外） |
|---|---|---|---|
| N0 不改 | 8 | **7** | 0 |
| N1 纯 prompt | 12 | **9** | 1-2 天/engine |
| N2 prompt + plugin/few-shot | 3 | **3** (新表中：`issue_impact_ranker` / `case_extractor` / `adversarial`) | 3-4 天/engine |
| N3 新领域字段 / family-conditional rendering | 1 | **3** (`case_extraction` / `report_generation` / `report_generation/v3`) | 4-5 天/engine |
| N4 必须 family-级别重写 | 1 | **4** (`amount_calculator` / `procedure_setup` / `pretrial_conference` / `document_assistance` 上限) | 一次性 5-10 天/engine，独立于具体案种 |

**v1 → v2 的关键 delta**：N4 引擎数从 1 增至 4，N3 从 1 增至 3，意味着 Batch 6.0 的"前置中性化"工作量翻倍以上。这直接驱动 §"问题 7" 的批次拆分和 §"问题 8" 的时间估算修订。

### 危险信号（v2 修订）

- **shared model 中性化是真正的 Batch 6.0 内容**（v1 误以为只是 `amount_calculator` 解耦）。最少要中性化 `AgentRole`、`EvidenceType`、`Perspective` 三个 enum，加上 `case_extraction.schemas`、`document_assistance.schemas`、`procedure_setup.planner`、`pretrial_conference.cross_examination_engine` 7 处硬编码点。
- **`amount_calculator` 的 civil_loan 硬耦合**仍是绊脚石之一，但**rendering 层的 amount 假设是配套绊脚石**：`report_generation/mediation_range.py:41`、`docx_generator.py:33`、`v3/layer4_appendix.py:371` 都需要在 plugin 引入 `has_amount_semantics(case_type) -> bool` capability 之后才能正确分支。
- **`pretrial_conference` 的 civil_loan 硬 import** (`cross_examination_engine.py:34`) 是 plugin 抽象的根本失败点 —— 这个引擎压根没有走过 `CaseTypePlugin.get_prompt()`，而是直接 `from .prompts.civil_loan import ...`。Batch 6.0b 必须把这个引擎拉进 plugin 抽象之内（用 registry 或 family-spec lookup），不能靠 prompt override 修复。
- **`procedure_setup` 的 ProcedurePhase 枚举不兼容**：当前枚举为民事庭审流程设计（`evidence_submission` / `evidence_challenge` / `judge_questions` / `rebuttal`），刑事的"法庭调查/法庭辩论/最后陈述"和行政的"陈述申辩/听证"不在里面。Batch 6.0b 必须决定：扩枚举 vs 在 `FamilySpec` 里挂 `procedure_phases` 字段（推荐后者）。

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

### CaseTypePlugin Protocol 需要扩展吗？（v2 重写）

**当前 Protocol**（`case_type_plugin.py:42-89`）只有两个方法：
- `get_prompt(engine_name, case_type, context)`
- `allowed_impact_targets(case_type) -> frozenset[str]`

**v1 推荐**：只加单个 `case_family(case_type) -> Literal["civil","criminal","admin"]` 方法，其余推迟。

**v2 推荐**（codex I6 驳回 v1）：单方法不够。证据是 `pretrial_conference/cross_examination_engine.py:34` 直接 `from .prompts.civil_loan import ...`，`document_assistance/engine.py:26` 同样硬 import —— 这两个引擎从来没走过 plugin 抽象，只加一个 `case_family()` 方法对它们毫无作用。Plugin 必须升级为 **`FamilySpec` 值对象**，承载下面所有维度，并且 **Batch 6.0b 必须把所有绕过 plugin 的 hard import 改造为 plugin lookup**。

#### 推荐的 `FamilySpec` 值对象

```python
@dataclass(frozen=True)
class FamilySpec:
    family_label: Literal["civil", "criminal", "admin"]
    roles: tuple[str, ...]                    # plaintiff_agent / prosecutor_agent / ...
    evidence_taxonomy: frozenset[str]         # 民事 7 类 / 刑事 + 4 类 / 行政 + 3 类
    procedure_phases: tuple[str, ...]         # 民事 8 阶段 / 刑事 5 阶段 / 行政 4 阶段
    report_sections: tuple[str, ...]          # 胜诉率评估 / 量刑建议 / 合法性审查结论
    has_amount_semantics: bool                # civil True；criminal/admin 默认 False（盗窃/罚款是子类型 override）
    supported_doc_types: frozenset[str]       # pleading/defense/cross_exam vs 起诉书/辩护词/上诉状/量刑建议书
    default_burden_allocation: str            # "谁主张谁举证" / "无罪推定" / "被告举证行政行为合法"

class CaseTypePlugin(Protocol):
    def get_prompt(...): ...                  # 已有
    def allowed_impact_targets(...): ...      # 已有
    def family_spec(self, case_type: str) -> FamilySpec: ...  # v2 新增 —— 必须
```

#### `family_spec()` 必须，其它方法推迟

- `family_spec()` 是 **Batch 6.0b 的核心交付物**。所有上述维度都在一个值对象里返回，避免在 Protocol 里加 5-6 个独立方法。
- `family_spec()` 替代 v1 的 `case_family()` / `allowed_procedure_phases()` / `allowed_relief_types()` / `default_burden_allocation()` 全部 4 个方法。
- 子类型级别的 override（如 `theft.has_amount_semantics = True`）通过 `family_spec()` 返回时按 `case_type` 参数分支处理，不需要额外 Protocol 方法。

#### Batch 6.0b 同步要解决的 plugin 旁路点

`FamilySpec` 设计完之后，必须把以下 hard-import 点改造为 plugin lookup（否则 plugin 永远管不到这些路径）：

- `pretrial_conference/cross_examination_engine.py:34` `from .prompts.civil_loan import CROSS_EXAM_SYSTEM, build_cross_exam_user_prompt` → 改为 `plugin.get_prompt("cross_exam", case_type, ...)`
- `document_assistance/engine.py:26` 类似
- `procedure_setup/planner.py` 阶段定义里的硬编码 entry/exit conditions → 改为从 `family_spec.procedure_phases` 取
- `case_extraction/schemas.py:58-62` LLM tool-schema 的 `case_type` 字段描述 → 改为按 `family_spec` 动态构造

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

### 研究产出物（每个案种，v2 修订）

> v1 给词汇笔记的 budget 是"约 300-500 字"。**v2 删除该数字** —— 这个 budget 只够一份 memo，不足以冻结 burden / relief / evidence / phase 词汇。模板（下方）保持，但要求**完全填充每个字段**，预期实际长度 1500-3000 字/子类型。

每个新案种应当产出**一份结构化 vocab 研究笔记**，包含 parties / burden / relief / evidence categories / procedure phases / exclusions / negative examples 全部字段，格式：
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

这是**上限**。

### 候选压缩策略：两层 prompt 继承（v2 待实证）

> v1 假设家族 base + 子类型 override 能覆盖 "80% 通用结构"，给出"压缩到 ~10,880 行"的估算。**v2 删除 80% 数字和压缩后总行数估算** —— 没有任何 spike 验证过这个比例。证据正好相反：现有 `case_extractor/prompts/generic.py:13` 的"all civil litigation case types" generic prompt 实际上是 civil-only 的，`pretrial_conference/prompts/judge.py:41` 把 `calculation_issue` 和 plaintiff/defendant framing 写死。这两个例子都暗示"family base"在实践里可能退化成空壳。

**v2 策略**：

**层 1：案种家族 base prompt**
- 每个引擎每个家族一份：
  - `prompts/_criminal_base.py` — 刑事通用 system prompt + 通用 build_user_prompt
  - `prompts/_admin_base.py` — 行政通用 system prompt + 通用 build_user_prompt
- v1 声称覆盖 80% 通用结构。**v2 标注：未实证，待 6.1.0 spike 验证。**

**层 2：案种 override**
- 每个引擎每个子类型一份，但只定义变化部分：
  - `ALLOWED_IMPACT_TARGETS`（frozenset）
  - `DOMAIN_SPECIFIC_HINT`（案种专属 prompt 段落注入 base system prompt）
  - 可选的 `build_user_prompt` 覆盖（仅当需要专属 context 块）

**6.1.0 prompt-inheritance spike**（Batch 6.1 的第一个任务，新增）：
- 选 ONE 引擎（推荐 `issue_impact_ranker`，因为它是词汇研究的核心入口）
- 实现 `_criminal_base.py` + `intentional_injury` override
- 测量实际 reuse %（base 行数 / (base + override) 行数）
- **决策门**：如果实际 reuse ≥ 60%，继承策略成立，按本节方案推进；如果 < 60%，**放弃 base/override，改走 flat per-subtype prompts**，重新估算 §"问题 8"。

**总代码量估算**：**TBD pending 6.1.0 spike 结果**。区间预期：
- 如果继承策略成立：~10k-12k 行新代码
- 如果继承失败 → flat：~18k-22k 行新代码

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

#### 受影响的现有测试（v2 修订）

> v1 估算 **30-40 个现有测试文件需要更新**。**v2 删除该数字** —— 其低估的根本原因是 v1 只盘点了 prompt registry 测试，没有把 acceptance / API / integration / v3 套件的参数化测试算进去。

codex 指出的具体证据（已验证）：
- `tests/acceptance/test_pipeline_structural.py:32` 在三个 civil case_type 上做参数化
- `tests/acceptance/test_n3_consistency.py:33` 同样
- `engines/report_generation/v3/tests/test_multi_case_integration.py:69` 在 v3 acceptance 层重复
- `api/tests/test_e2e_lifecycle.py:292` 和 `tests/integration/test_full_pipeline.py:295` 也在做硬编码 civil 假设

**v2 工作假设**（待 6.0a 实证）：受影响现有测试文件 **60-100 个**（不是 30-40），分布在 unit / acceptance / integration / API / v3 五层。**6.0a 耦合审计的一个核心交付物就是这份文件级 inventory**。

**总测试增量估算（v2）**：
- 新增：约 100 个新测试（unit + E2E + golden）— 此项 v1 估算可保留
- 修改：**60-100 个现有文件**（待 6.0a 校准），不是 30-40
- **预期最终测试数**：2408 → ~2500+

---

## 问题 7：风险 + 批次拆分

### 风险清单（v2 修订）

#### 🔴 Critical

1. **shared model family-level 民事硬编码**（v2 新增 #1，由 codex C1+C11 暴露） — `AgentRole` / `EvidenceType` / `Perspective` / `case_extraction.schemas` / `procedure_setup.planner` / `pretrial_conference.cross_examination_engine` / `document_assistance.schemas` 多处硬编码民事语义。如果不先 family-中性化，加任何新案种都会污染 shared types。**缓解**：Batch 6.0a 全面审计 + Batch 6.0b 引入 `FamilySpec` 并改造所有 plugin 旁路点。

2. **`amount_calculator` + rendering 层组合性 amount 耦合** — 不仅 calculator 本身硬编码 civil_loan，下游 `report_generation/mediation_range.py:41`、`docx_generator.py:33`、`v3/layer4_appendix.py:371` 都假设 amount 语义存在。**缓解**：在 `FamilySpec` 加 `has_amount_semantics: bool`，runner 和 renderer 都从这个 capability 取分支决策；不在 calculator 内部加 criminal/admin 分支。

3. **`ProcedurePhase` 枚举不兼容** — 当前枚举只覆盖民事庭审阶段。`procedure_setup/planner.py:112` 已经把"原告起诉状已接收 / 被告已收到应诉通知"硬编码进 entry conditions。**缓解**：Batch 6.0b 把 `procedure_phases` 挂到 `FamilySpec` 上，删除全局 `ProcedurePhase` 枚举的 canonical 地位。

4. **`pretrial_conference` 完全绕过 plugin 抽象** — `cross_examination_engine.py:34` `from .prompts.civil_loan import ...` 是硬 import。**缓解**：Batch 6.0b 必须把这个引擎拉进 `plugin.get_prompt()` 抽象之内，删除硬 import。

5. **Prompt 质量无法被单元测试保证** — LLM 输出在 `LLM_MOCK=true` 下是 mock 的，真实的 criminal/admin prompt 质量只能靠人工 review 和昂贵的 live LLM eval。**缓解**：Batch 6.0c 建立 `benchmarks/layer4_eval/` 最小 eval harness，每个新子类型至少 3 个 LLM-live smoke test。

#### 🟡 Important

6. **`document_assistance` schema 工作量被低估** — `schemas.py:159-160` 的 `doc_type` 和 `case_type` 都是裸字符串硬编码字段，不是 enum/registry；plaintiff-only/defendant-only 文书骨架在 `schemas.py:60`/`:91`。需引入 `DocTypeRegistry`。**缓解**：Batch 6.0b 同步改造。

7. **`adversarial` 引擎的"原被告"vs"控辩"语义错配** — few-shot 示例是民事语境。**缓解**：Batch 6.2 重写 criminal 版 few-shot；v2 已把这个引擎从 N1 升至 N2。

8. **`report_generation/v3` 模板分叉** — v3 模板是为民事对抗报告设计的。**缓解**：Batch 6.0b 同时引入 family-conditional section templates；v2 已升级为 N3。

9. **研究深度不足导致设计返工** — 6 个新子类型的法律研究如果不到位，模型字段和 prompt 结构都会在编码过程中被推翻。**缓解**：Batch 6.0c 是纯研究 sprint，交付 6 份完整的结构化 vocab 笔记 + 模型字段草案。

10. **`case_extraction` LLM tool-schema 硬编码** — `schemas.py:58-62` 的 `case_type` 字段 LLM tool-schema 硬编码三个民事案种；`plaintiff_name` / `defendant_names` 是 schema 必填字段，对刑事公诉人结构无法表达。**缓解**：Batch 6.0b 改为 family-discriminated schema。

#### 🟢 Minor

11. **Test 爆炸半径** — v1 估 30-40 个测试文件，v2 修订为 60-100 个；本身参数化成本不大但 review 负担显著。
12. **CLI/API 层面的 case_type 参数暴露** — 需要更新 help text、API schema（OpenAPI）、CLI validation 列表。
13. **文档和 README 更新** — 低优先级但不可忽略。

### 批次拆分建议

**Criminal 和 administrative 应当完全分开，不能混合。** 理由：

- 两者领域模型差异巨大（criminal.py / admin.py 没有代码复用空间）
- 两者 vocab 研究不能互相参考（引用的法条完全不同）
- 两者的 prompt 调优回路独立，混在一个 batch 里会造成注意力分散和回归风险
- 批次越大，爆炸半径越大（Batch 5 的经验：一个 6 commit 的 batch 已经到了 adversarial review 能稳定审完的上限）

**建议的批次序列（v2 重写）**：

> v1 把 Batch 6.0 框定为单个 2 周 preflight，blast radius 10 文件 / 30 测试。**v2 拆三**：

#### Batch 6.0a：Coupling Audit（1 周，无代码改动）

**目标**：file-level inventory of civil-coupled symbols；纯研究交付物，不写代码
- 6.0a.1 grep + 人工核对 `engines/shared/models/` 下所有 enum/dataclass，标记 civil-only 字段
- 6.0a.2 grep `from .prompts.civil_loan` / `case_type ==` / `plaintiff` / `defendant` 等模式，列出所有 plugin 旁路点
- 6.0a.3 文件级测试影响 inventory（acceptance / API / integration / v3 五层）
- 6.0a.4 （可选）查询法院公开判决书子类型分布，校准 §"问题 1" MVP 选择
- **交付物**：一份 markdown 矩阵（file × civil-coupled symbol × family-impact × 修复方案）
- **Blast radius**：0（纯文档）
- **Gate**：审计矩阵覆盖至少 7 处 v2 已知硬编码点 + 60-100 个测试文件 inventory

#### Batch 6.0b：Neutralization（2-3 周）

**目标**：把 6.0a 矩阵里的 civil-only 硬编码全部 family-中性化，但**不引入任何新案种**
- 6.0b.1 引入 `FamilySpec` 值对象 + `CaseTypePlugin.family_spec()` 方法
- 6.0b.2 中性化 `AgentRole` / `EvidenceType` / `Perspective` enum，让它们能容纳 criminal/admin 角色和证据类别
- 6.0b.3 改造 `case_extraction.schemas` 为 family-discriminated tool schema
- 6.0b.4 改造 `procedure_setup/planner.py` 把 phase 定义从硬编码移到 `family_spec.procedure_phases`
- 6.0b.5 改造 `pretrial_conference/cross_examination_engine.py` 把硬 import 改为 plugin lookup
- 6.0b.6 引入 `DocTypeRegistry` + 改造 `document_assistance.schemas` 为 family-discriminated
- 6.0b.7 在 `FamilySpec` 加 `has_amount_semantics: bool`，runner 和 renderer (`mediation_range` / `docx_generator` / `v3/layer4_appendix`) 都按这个 capability 分支
- 6.0b.8 `amount_calculator` runner-level bypass（基于 `has_amount_semantics`）
- **Blast radius**：~25-40 源文件 + 60-100 测试文件
- **Gate**：所有现有 2408 测试通过，Layer 4 测试矩阵显示三家族占位（civil 实装，criminal/admin 空 spec stub）

#### Batch 6.0c：Vocab Research + Eval Harness（2-3 周，可与 6.0b 并行）

**目标**：法律研究 + LLM eval 框架；不依赖 6.0b 的代码改造
- 6.0c.1 完成 6 份结构化 vocab 笔记（每份 1500-3000 字，全字段填充）
- 6.0c.2 法律专家 review 6 份笔记，签字
- 6.0c.3 建立 `benchmarks/layer4_eval/` 最小 eval harness（每子类型 3 个 LLM-live smoke test 占位）
- **Blast radius**：~15 文件（全部新增到 `benchmarks/` 和 `docs/research/`）
- **Gate**：法律专家签字 + eval harness 能跑通至少 1 个 civil baseline（验证框架本身工作）

#### Batch 6.1：Criminal Foundation（2-3 周）

**目标**：criminal 第一个子类型跑通端到端
- 6.1.0 **prompt-inheritance spike**（新增，详见 §"问题 5"）：选 `issue_impact_ranker` 一个引擎实现 `_criminal_base + intentional_injury override`，测量 reuse %，决定继承策略是否成立
- 6.1.1 `engines/shared/models/criminal.py` 最小版（ChargeType、CriminalImpactTarget、SentencingFactor）
- 6.1.2 `intentional_injury` 的 prompt 实现 × 17 引擎（按 6.1.0 决定的策略）
- 6.1.3 `issue_impact_ranker.intentional_injury.json` few-shot
- 6.1.4 端到端 smoke test + 1 个 golden case
- **Blast radius**：~30-40 文件，~40 新测试
- **Gate**：smoke test 在 LLM live 模式下通过 + 法律专家审 1 个 golden case 输出

#### **Reality-check 节点**：6.1 完成后回头校准

详见下一节 §"Reality Check"。**强烈建议在 6.1 之后停下，重新评估 6.2 / 7.0 / 7.1 的范围和时间，再决定是否继续。**

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
- 7.1.2 `work_injury_recognition` ⚠️ stretch（与现有 labor_dispute 的协同集成）；**如果 7.1 over-budget，本子类型推迟到 7.2**

### 批次依赖图（v2）

```
6.0a Audit ──> 6.0b Neutralize ──┐
              \                  ├──> 6.1 Criminal PoC ──[Reality check]──> 6.2 Criminal Expansion
               \─> 6.0c Vocab ───┘                                      \
                   (parallel)                                            └──> 7.0 Admin PoC ──> 7.1 Admin Expansion
```

- **6.0a 必须在 6.0b 和 6.0c 之前完成**（提供审计矩阵）
- **6.0b 和 6.0c 可以并行**（6.0c 是研究和文档，不依赖 6.0b 的代码改造）
- **6.1 必须在 6.0b + 6.0c 都完成之后**
- **6.1 完成后必须 reality-check**（见下节），不要直接进 6.2
- 6.2 / 7.0 / 7.1 串行执行，不并行

---

## Reality Check：先 ship `intentional_injury` 单子类型再说（v2 新增）

> **核心建议**：在承诺任何 6.2 之后的计划之前，先 ship Batch 6.1（criminal foundation + intentional_injury 单子类型 PoC），然后**停下来回头校准**。

### 为什么需要这个检查点

v1 的 15 周 realistic 估算建立在三个未实证假设之上，全部被 codex review 推翻：

1. Batch 6.0 是个轻量级 preflight（实际是 4-5 周的家族中性化）
2. Prompt 两层继承能 80% reuse（实际未实证，可能退化成空壳）
3. shared model 不需要动（实际有 7+ 处硬编码点）

继续在这些未实证假设上叠加 6.2 / 7.0 / 7.1 的细节计划是**复利的不确定性**。最稳的姿势是先 ship intentional_injury 一条线，把所有"未知的未知"暴露出来，然后**在真实数据上重新估算余下批次**。

### Reality-check 触发后要回答的问题

Batch 6.1 收尾的 retrospective 必须回答：

1. **6.0a 矩阵的 inventory 数量是不是估对了？**
   - 实际中性化触及多少源文件、多少测试文件？
   - 如果远超 v2 工作假设（25-40 源 + 60-100 测试），6.2 / 7.0 / 7.1 的预算需要相应放大
2. **6.1.0 spike 的 prompt reuse % 是多少？**
   - ≥ 60%：继承策略成立，按计划进 6.2
   - < 60%：放弃继承，所有后续 batch 的 prompt 部分按 flat 重新估算（约翻倍）
3. **法律专家 review 一份 vocab 笔记 + 一个 golden case 实际花了多少 wall-clock 时间？**
   - 这个数字直接决定 6.2 / 7.0 / 7.1 的"非编码瓶颈"系数
   - 如果 > 1 周/子类型，必须把后续批次时间预算翻倍
4. **`pretrial_conference` 和 `procedure_setup` 改造的实际深度**
   - 6.0b 是不是真的能在 2-3 周内做完？
   - 如果不能，6.0b 本身需要再拆
5. **是否有任何 6.0a 没发现的 civil 硬编码点？**
   - 这个直接决定 v2 修订的 N3/N4 列表是不是全的

### Reality-check 的可能结论

- **Best case**：v2 估算基本对，可以按 18 周 realistic 推进到 7.1 完整 ship
- **Likely case**：1-2 处低估，余下批次需要加 4-6 周缓冲，22 周 realistic
- **Worst case**：6.0b 揭示更深层耦合（例如 `Issue` / `Claim` 模型本身需要 family-discriminate），整个 Layer 4 需要回到 plan 阶段重新设计

无论哪种结论，**一次 reality-check 节省的返工成本都远超它消耗的 1-2 天时间**。

---

## 问题 8：时间估算（v2 修订）

### 三档估算（v2）

> v1 估算：optimistic 10 周 / realistic 15 周 / pessimistic 23 周。**v2 上调**理由见 §"问题 7" v2 风险清单：6.0 拆三、N4 引擎从 1 增至 4、shared model 中性化新出现、reality check 节点新增。

| 批次 | Optimistic | Realistic | Pessimistic |
|---|---|---|---|
| **6.0a** Coupling Audit | 1 周 | 1 周 | 2 周 |
| **6.0b** Neutralization | 2 周 | 3 周 | 5 周 |
| **6.0c** Vocab + Eval Harness（与 6.0b 并行） | 2 周（隐藏在 6.0b 里） | 3 周（隐藏在 6.0b 里） | 4 周（部分隐藏） |
| 6.1 Criminal Foundation（含 6.1.0 spike） | 3 周 | 4 周 | 6 周 |
| **Reality Check 节点** | 2 天 | 3 天 | 1 周 |
| 6.2 Criminal Expansion（2 子类型） | 2 周 | 3 周 | 5 周 |
| 7.0 Admin Foundation | 3 周 | 4 周 | 6 周 |
| 7.1 Admin Expansion（2 子类型，work_injury stretch） | 2 周 | 3 周 | 5 周 |
| **合计** | **~14 周** | **~18-22 周** | **~28+ 周** |

> 6.0c 的时间在大多数情况下被 6.0b 吞掉（并行执行），所以总和不是简单相加。Optimistic 假设 6.0c 完全并行，Pessimistic 假设法律专家 review 拉长导致 6.0c 末段串行。

### 估算的假设和风险（v2）

**Optimistic 14 周假设**：
- 6.0a 矩阵在 1 周内完成且没有意外发现
- 6.0b 中性化干净，所有现有 2408 测试在改造后立即通过
- 6.1.0 spike 显示 prompt reuse ≥ 60%，继承策略成立
- vocab 研究一次通过，每份笔记法律专家 review 1-2 天
- Reality check 不需要任何 plan 修订

**Realistic 18-22 周假设**：
- 6.0a 揭示 1-2 处 v2 未预见的耦合点，6.0b 需要 1 周缓冲
- 6.1.0 spike 显示 reuse 60-75%（继承策略成立但有 trim）
- vocab 研究需要法律专家 1 轮返工
- Reality check 触发余下批次时间预算 +20%

**Pessimistic 28+ 周假设**：
- 6.0a 揭示 `Issue` 或 `Claim` 模型本身需要 family-discriminate（v2 没估到的深层耦合）
- 6.1.0 spike 显示 reuse < 60%，所有后续 prompt 工作量翻倍
- 法律专家可用性差，每份笔记 review 拖到 1 周以上
- Reality check 触发整个 7.x 重新设计

**最可能的瓶颈（v2 修订）**：v1 说瓶颈是"vocab 研究的人工 review 速度"，**v2 修正**：瓶颈是 **6.0b 中性化的真实深度** + **6.1.0 spike 的 prompt reuse 实测结果**。前者决定 6.0 总时长，后者决定 6.2 / 7.0 / 7.1 的乘子。法律专家 review 速度只是次要瓶颈。

**强烈建议**：把 ship 目标缩小到 **Batch 6.0 + 6.1**（即"family neutralization + intentional_injury PoC"），承诺给 stakeholder 的时间窗口设为 **6-8 周**。Reality check 之后再决定要不要继续 ship 6.2 / 7.x。

---

## 总结（v2 重写）

Layer 4 是一次**案种家族维度的中性化重构 + prompt 扩展**（从 civil 1 个家族 → civil + criminal + admin 三个家族），不是 v1 误以为的"以 prompt 扩展为主"。codex review 暴露了 7+ 处 shared model 和 engine 层的硬编码民事语义，必须先做家族中性化才能加新案种。Layer 4 的主要成本顺序为：

1. **shared model + engine 的 family-级别中性化**（v1 漏掉的最大块；`AgentRole` / `EvidenceType` / `Perspective` / `case_extraction.schemas` / `procedure_setup.planner` / `pretrial_conference.cross_examination_engine` / `document_assistance.schemas` 全部需要改造）
2. **`FamilySpec` Protocol 升级**（不只是单个 `case_family()` 方法）
3. **新领域模型**（`criminal.py` / `administrative.py` 仍需新建，但工作量被 1-2 项盖过）
4. **法律研究深度**（6 份完整结构化 vocab 笔记，需要人工 review；预期 1500-3000 字/份，不是 v1 的 300-500 字）
5. **prompt 工程量**（102 模块上限；继承策略 reuse % 待 6.1.0 spike 实证）

推荐执行路径：**6.0a Audit → 6.0b Neutralize ‖ 6.0c Vocab → 6.1 Criminal PoC → [Reality check] → 6.2 → 7.0 → 7.1**。Realistic 估算 **18-22 周**（v1 的 15 周已撤回）。**强烈建议先 ship 6.0 + 6.1 (intentional_injury PoC)，6-8 周时间窗口，然后 reality-check 后再决定是否继续。**

---

## 8 个问题的一句话答案

1. **MVP 子类型**：criminal = 故意伤害 / 盗窃 / 诈骗（暴力/财产/欺诈三原型）；admin = 行政处罚 / 政府信息公开 / 工伤认定（工伤为 stretch synergy，可推迟）。覆盖率不再做百分比断言。
2. **Engine 清单**（v2 重新分级）：26 个引擎中 N0/N1 数量大幅缩小，**N3-N4 引擎增至 7 个**（case_extraction、case_extractor、procedure_setup、pretrial_conference、document_assistance、report_generation、report_generation/v3）。具体新分级见 §"问题 2" 表。
3. **Model 层**：新建 `criminal.py` + `administrative.py` 两个专属模块；`CaseTypePlugin` Protocol 升级为 **`FamilySpec` 值对象**（含 family_label / roles / evidence_taxonomy / procedure_phases / report_sections / has_amount_semantics / supported_doc_types），不是单一 `case_family()` 方法。同时 `EvidenceType` / `AgentRole` / `Perspective` 必须中性化。
4. **领域词汇**：需要研究 11 个权威法律文件（刑法/刑诉法/行诉法 + 6 部司法解释 + 2 部行政法规），交付 6 份 **结构化矩阵 vocab 笔记**（无字数预算，预期 1500-3000 字 / 子类型）。
5. **Prompt 工程量**：天真估算约 100 个新 prompt 模块；继承复用率必须由 6.1.0 spike（intentional_injury × issue_impact_ranker）实测决定，不再预先承诺压缩比。
6. **测试**：新增约 100 个单元/E2E 测试 + 6-12 个 golden case；现有测试修改量为 **60-100 个文件**（pending 6.0a 审计），覆盖 acceptance / API / v3 / integration 全部参数化套件。
7. **风险 + 批次**：**5 个 Critical 风险**（C1 shared-model 中性化、C2 case_extraction 重判、C3 procedure 全家族重写、C4 amount 渲染层耦合、C5 MVP 论据需修）+ 6 个 Important；推荐 **7 个 batch**（6.0a / 6.0b / 6.0c / 6.1 / [reality check] / 6.2 / 7.x）。
8. **时间**：realistic **18-22 周** / optimistic 14 周（仅当 6.1.0 spike 全部成功）/ pessimistic 28+ 周。强烈建议先发 ONE family + ONE subtype（intentional_injury），ship 后再重估剩余范围。

---

## 最大的未决问题

v1 的"Batch 6.0 能否压缩到 1 周"已经被 codex review 否决——三个子问题（amount 耦合深度 / ProcedurePhase 可吸收性 / Plugin 契约破坏面）现在全部 **subsumed into Batch 6.0a 的审计交付物**，不再是 1-2 天 scouting 任务。

v2 唯一未决问题：

**6.1.0 prompt-inheritance spike（intentional_injury × issue_impact_ranker）的 reuse % 实测结果会决定剩余 Layer 4 的形态：**

- 若 base/override 复用率 ≥ 50%：维持两层继承策略，按 6.1 → 6.2 → 7.x 顺序推进，realistic = 18-20 周。
- 若复用率 < 50%：放弃两层继承，改为 flat per-subtype prompts；估算重置，realistic 滑向 22+ 周；强烈建议在 ship 完 intentional_injury 之后立即触发 Reality Check 重估。
- 若 6.1.0 spike 本身揭示出 shared-model 还有未中性化的隐藏耦合（6.0a/6.0b 漏掉的）：回退到一次新的 6.0d 补丁批次，本期 Layer 4 范围缩到只发 ONE family + ONE subtype。

这是一个由 6.0a 审计 → 6.0b 中性化 → 6.1.0 spike 三步串联决定的复合问题，而不是开工前可以靠 Explore 报告回答的问题。

---

## Adversarial Review (codex, 2026-04-07) — 决策日志

**Reviewer**: codex CLI v0.118.0, `gpt-5.4` xhigh, read-only sandbox, repo HEAD `50f28fe`. Tokens 627,539. Findings 5 CRITICAL / 6 IMPORTANT / 2 MINOR / 2 NIT. Verbatim output: `docs/plans/2026-04-07-layer-4-criminal-admin-plan.review.md`.

**Net verdict (codex)**: "this plan is not ready to execute as written. The codebase is still civil-shaped at the shared-model, procedure, reporting, fixture, and API layers. I would not approve anything beyond a short coupling-audit batch plus one-family, one-subtype spike."

**Author meta-judgment**: 12 AGREE / 3 PARTIAL / 0 DISAGREE. Five evidence claims spot-checked against source — all verified (`core.py:200` AgentRole, `case_extraction/schemas.py:60`, `procedure_setup/planner.py:112`, `cross_examination_engine.py:34`, `document_assistance/schemas.py:159`).

This section is the **decision log only** — every disposition has already been folded into the body sections above.

### Decision log

| ID | Severity | Problem (one line) | Judgment | Disposition (folded into) |
|----|---|---|---|---|
| C1 | CRITICAL | Plan framed as prompt expansion; actual work is shared-model neutralization (AgentRole/Perspective/EvidenceType) | AGREE | §0 fact #6, §3 FamilySpec, §7 Batch 6.0a/6.0b, §"总结" |
| C2 | CRITICAL | `case_extraction` / `case_extractor` mis-graded N0; LLM tool-schema hardcodes 3 civil values | AGREE | §2 grading table (rows re-graded N0→N3 / N0→N2) |
| C3 | CRITICAL | `procedure_setup` + `pretrial_conference` are N4 not N2; hard imports + civil entry strings | AGREE | §2 grading table (N2→N4), §7 6.0b scope (procedure family rewrite) |
| C4 | CRITICAL | `amount_calculator` bypass leaves rendering layer broken (`mediation_range`, `docx_generator`, `v3/layer4_appendix`) | AGREE | §3 `has_amount_semantics`, §2 `report_generation` N1→N3, §7 risk #1 |
| C5 | CRITICAL | MVP rationale: `>60%` claim unsupported; 交通肇事 dismissal sloppy; work_injury synergy weak | PARTIAL | §1 (drop %, rewrite 交通肇事 phrasing, mark work_injury as stretch), §"8 问" item 1 |
| I6 | IMPORTANT | `case_family()` single method is wrong abstraction; engines bypass plugin entirely | AGREE | §3 FamilySpec value object replaces single method |
| I7 | IMPORTANT | Two-layer prompt inheritance + 80% reuse is unvalidated fantasy | PARTIAL | §5 drop 80% claim, §7 add 6.1.0 spike (intentional_injury × issue_impact_ranker) |
| I8 | IMPORTANT | `document_assistance` is schema work, not registry — `doc_type` + `case_type` are bare strings | AGREE | §2 grading N1-N3→N3-N4, §7 6.0b adds discriminated `doc_type` contract |
| I9 | IMPORTANT | "30-40 modified test files" ignores acceptance/API/v3/integration parameterized suites | AGREE | §6 revised to 60-100 files (TBD pending 6.0a audit) |
| I10 | IMPORTANT | 15-week realistic built on wrong premise; bottleneck broader than vocab review | AGREE | §8 timeline 15→18-22 weeks; pessimistic 28+; ship intentional_injury first |
| I11 | IMPORTANT | EvidenceType / AgentRole / Perspective civil-only; not in plan facts list | AGREE | Same workstream as C1 (§0 fact #6, §7 6.0a audit matrix scope) |
| M12 | MINOR | Batch 6.0 overloaded; "~10 files / ~30 tests" blast-radius is fake | AGREE | §7 split into 6.0a Audit / 6.0b Neutralize / 6.0c Vocab+Eval |
| M13 | MINOR | Vocab-note 300-500 字 budget too thin to actually freeze burden/relief/evidence/phase | PARTIAL | §4 drop word budget, structured matrix only (1500-3000 字/子类型) |
| N14 | NIT | 总结 frames work as "6 new PromptProfile values" — hides real change | AGREE | §"总结" rewritten to lead with family neutralization |
| N15 | NIT | Fake precision throughout (`>60%`, `~10 files`, `~30 tests`, `15 weeks`) | AGREE | All point-estimates either dropped or annotated `(TBD pending 6.0a)` |

### Net effect

1. Batch 6.0 → 6.0a / 6.0b / 6.0c (M12 + C1-C4)
2. Engine grading rewritten — 7 engines moved into N3-N4 tier (C2 + C3 + C4 + I8)
3. Realistic timeline 15 → 18-22 weeks; ship ONE family + ONE subtype (intentional_injury) before committing to the rest (I10)
4. v1 §"最大的未决问题" three sub-questions are now subsumed into 6.0a audit deliverables — replaced by the 6.1.0 spike question.

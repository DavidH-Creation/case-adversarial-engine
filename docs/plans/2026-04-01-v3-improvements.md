# V3 三项改进实施计划
**日期**: 2026-04-01
**背景**: 外部评审提出三项改进建议，结合内部讨论后调整为以下方案。

---

## 总览

| 编号 | 功能 | 类型 | 估算复杂度 | 建议顺序 |
|------|------|------|-----------|---------|
| F1 | `--perspective` 委托方视角输出层 | 纯报告层 (rule-based) | 低 | 1st |
| F2 | 条件情景树替换伪精确概率 | 数据模型 + LLM prompt + 报告层 | 中 | 2nd |
| F3 | 证据作战矩阵 (7列) | 新模块 + LLM | 高 | 3rd |

**实施顺序理由**: F1 不触碰核心数据模型，可独立部署；F2 改动核心模型，需稳定后再叠加 F3；F3 是新增模块，不破坏现有流程。

---

## F1：`--perspective` 委托方视角输出层

### 设计原则

**不锁定单一立场**。引擎内部保持中立对抗（原被告都跑），输出层添加一个轻量"委托方视角摘要"section，优先呈现委托方最关心的内容。无 `--perspective` 参数时，默认保持当前双边对等输出。

### 现有基础

- `engines/shared/models/core.py:Perspective` 枚举已存在：`neutral / plaintiff / defendant`
- `engines/shared/models/pipeline.py:DecisionPathTree` 已有 `plaintiff_best_path` 和 `defendant_best_path`
- `engines/simulation_run/attack_chain_optimizer` 生成的 `OptimalAttackChain` 已有 `owner_party_id`
- `engines/report_generation/executive_summarizer` 已聚合全局摘要

### 新增数据模型

**文件**: `engines/report_generation/schemas.py`（新增，或追加到现有模型文件）

```python
from engines.shared.models.core import Perspective

class ClientPerspectiveSummary(BaseModel):
    """委托方视角摘要 — 纯规则层从现有产物中聚合，不触发新 LLM 调用。"""
    perspective: Perspective
    favorable_paths: list[str]      # 对我方有利的 path_id 列表（从 DecisionPathTree 读取）
    critical_actions: list[str]     # 最重要的 3-5 项行动（从 ActionRecommendation 聚合）
    risk_warnings: list[str]        # 对方最强攻击点（从 OptimalAttackChain 读取）
    evidence_priorities: list[str]  # 最高优先级补证缺口（从 EvidenceGapItem 读取）
    perspective_headline: str       # 一句话战略总结
```

**构建函数**（在 `engines/report_generation/` 新增 `perspective_layer.py`）：

```python
def build_perspective_summary(
    perspective: Perspective,
    decision_tree: DecisionPathTree | None,
    attack_chain: OptimalAttackChain | None,
    action_rec: ActionRecommendation | None,
    evidence_gaps: list[EvidenceGapItem],
    exec_summary: ExecutiveSummaryArtifact | None,
) -> ClientPerspectiveSummary:
    ...
```

逻辑：
- `favorable_paths`：从 `decision_tree.paths` 过滤 `party_favored == perspective.value`，按 `probability` 排序取前3
- `critical_actions`：若 perspective=plaintiff，从 `action_rec` 取 `evidence_supplement_priorities` + `recommended_claim_amendments`；若 perspective=defendant，取 `claims_to_abandon`（针对被告——让原告放弃弱诉请）
- `risk_warnings`：从 attack_chain 的 `top_attacks` 提取 `attack_description`（对方攻击）
- `evidence_priorities`：从 `evidence_gaps` 按 `roi_rank` 取前3
- `perspective_headline`：从 `exec_summary` 或规则生成一句话

### CLI 变更

**文件**: `scripts/run_case.py`

```python
# argparse 新增
parser.add_argument(
    "--perspective",
    choices=["plaintiff", "defendant"],
    default=None,
    help="Generate a client-perspective summary section (default: both sides equally)",
)
```

`main()` 签名新增 `perspective: str | None = None`，传入 `_write_md()` 和 DOCX 生成器。

同样修改 `scripts/run_wang_v_chen_zhuang.py`（该脚本有自己的 argparse）。

### 报告层变更

**文件**: `scripts/run_case.py:_write_md()`

新增参数 `perspective: str | None = None`。

当 perspective 非 None 时，在报告开头（disclaimer 之后，Case Summary 之前）插入新 section：

```markdown
## 📋 委托方视角摘要（原告/被告）

**战略总结**: ...

### 对我方有利的裁判路径
- PATH-A: 原告全额获支持 ← 条件：录音采信 + 支付宝代付补强
- PATH-B: ...

### 当前最重要的3件事
1. 补强支付宝代付证据（缺口 ROI 排名 #1）
2. ...

### 对方最强攻击点预警
- 攻击点1: 录音合法性质疑
- ...

### 待补证缺口优先级
1. ...
```

当 perspective=None 时，跳过此 section（保持现有行为）。

### DOCX 变更

**文件**: `engines/report_generation/docx_generator.py`

在 `generate_docx_report()` 函数签名增加 `perspective: str | None = None`，添加对应 Word 样式的 section。

### 需修改的文件清单

| 文件 | 变更类型 |
|------|---------|
| `scripts/run_case.py` | 新增 `--perspective` arg，传参链，`_write_md()` 新 section |
| `scripts/run_wang_v_chen_zhuang.py` | 同上 |
| `engines/report_generation/perspective_layer.py` | **新建** — `build_perspective_summary()` |
| `engines/report_generation/schemas.py` | **新建或追加** — `ClientPerspectiveSummary` |
| `engines/report_generation/docx_generator.py` | 新增 perspective section |

### 验证清单 (F1)

- [ ] `python run_case.py case.yaml --perspective plaintiff` → 报告顶部出现"委托方视角摘要（原告）"section
- [ ] `python run_case.py case.yaml --perspective defendant` → 出现被告版本
- [ ] 无 `--perspective` 参数 → 报告无此 section（向后兼容）
- [ ] `favorable_paths` 只包含 `party_favored == "plaintiff"` 的路径
- [ ] `risk_warnings` 来自 attack_chain（对方视角）
- [ ] DOCX 报告包含对应 section
- [ ] 所有现有测试通过（无回归）

---

## F2：条件情景树（替换伪精确概率）

### 问题与设计原则

当前 `DecisionPath.probability: float` 由 LLM 凭空填写，数字本身不自洽（如三条路径概率之和不等于1）。改为"关键二元条件 → 情景触发"结构：每条路径由一组条件激活状态决定，结果为"区间/范围描述"而非精确百分比。

**关键二元条件（以民间借贷案为例）**：

| 条件 ID | 中文标签 | 关键证据 |
|---------|---------|---------|
| COND-A | 录音采信/不采信 | 录音、录屏证据 |
| COND-B | 支付宝代付补强/不补强 | 支付宝代付声明、转账记录 |
| COND-C | 账户性质认定（个人/共同） | 银行流水、开户材料 |
| COND-D | 个人承诺/共同借款 | 借条、录音 |

每条 DecisionPath 附带一个激活组合（如 `COND-A=true, COND-B=false`），而非 `probability=0.3`。

**向后兼容策略**：`DecisionPath.probability` 和 `confidence_interval` 变为 `Optional`，新字段追加，规则层在 `condition_activations` 存在时不填充旧字段（或清空）。

### 新增数据模型

**文件**: `engines/shared/models/pipeline.py`（追加到 DecisionPath 区域）

```python
class BinaryCondition(BaseModel):
    """注册到 DecisionPathTree 的关键二元条件。"""
    condition_id: str = Field(..., min_length=1)   # "COND-A"
    condition_label: str = Field(..., min_length=1) # "录音采信/不采信"
    true_meaning: str = Field(default="")           # true 代表什么
    false_meaning: str = Field(default="")          # false 代表什么
    linked_evidence_ids: list[str] = Field(default_factory=list)
    linked_issue_ids: list[str] = Field(default_factory=list)
    is_determinative: bool = Field(default=False)   # 此条件单独决定结果
    condition_notes: str = Field(default="")


class ConditionActivation(BaseModel):
    """路径触发所需的单个条件状态。"""
    condition_id: str = Field(..., min_length=1)
    required_state: bool  # True=条件成立, False=条件不成立


class OutcomeRange(BaseModel):
    """条件组合对应的结果区间描述（代替精确概率）。"""
    outcome_label: str = Field(..., min_length=1)  # "原告全额获支持"
    outcome_detail: str = Field(default="")         # 裁判结果的情景描述
    favorable_to: str = Field(default="neutral")    # plaintiff / defendant / neutral
```

**更新 `DecisionPath`**（向后兼容扩展，不移除旧字段，改为 Optional）：

```python
class DecisionPath(BaseModel):
    # ... 现有字段 ...

    # v1.6 旧字段改为 Optional（保留向后兼容）
    probability: Optional[float] = Field(
        default=None,
        ge=0.0, le=1.0,
        description="[已弃用，F2 后不再由 LLM 填充] 路径触发概率",
    )
    confidence_interval: Optional[ConfidenceInterval] = Field(
        default=None,
        description="[已弃用，F2 后清空] 置信度区间",
    )

    # F2 新增字段
    condition_activations: list[ConditionActivation] = Field(
        default_factory=list,
        description="F2: 触发本路径所需的条件激活组合",
    )
    outcome_range: Optional[OutcomeRange] = Field(
        default=None,
        description="F2: 本路径结果的区间/范围描述（代替精确概率）",
    )
```

**更新 `DecisionPathTree`**：

```python
class DecisionPathTree(BaseModel):
    # ... 现有字段 ...

    # F2 新增
    condition_registry: list[BinaryCondition] = Field(
        default_factory=list,
        description="F2: 本树中所有路径共享的关键条件注册表",
    )
```

### LLM 中间模型变更

**文件**: `engines/simulation_run/decision_path_tree/schemas.py`

```python
class LLMConditionActivation(BaseModel):
    condition_id: str = Field(default="")
    required_state: bool = Field(default=True)

class LLMBinaryCondition(BaseModel):
    condition_id: str = Field(default="")
    condition_label: str = Field(default="")
    true_meaning: str = Field(default="")
    false_meaning: str = Field(default="")
    linked_evidence_ids: list[str] = Field(default_factory=list)
    linked_issue_ids: list[str] = Field(default_factory=list)
    is_determinative: bool = Field(default=False)

class LLMOutcomeRange(BaseModel):
    outcome_label: str = Field(default="")
    outcome_detail: str = Field(default="")
    favorable_to: str = Field(default="neutral")

# 更新 LLMDecisionPathItem
class LLMDecisionPathItem(BaseModel):
    # 现有字段保留 ...
    # 新增
    condition_activations: list[LLMConditionActivation] = Field(default_factory=list)
    outcome_range: Optional[LLMOutcomeRange] = None
    # 旧字段 probability 降权（保留但设 0.5 默认值）
    probability: float = Field(default=0.5, ge=0.0, le=1.0)

# 更新 LLMDecisionPathTreeOutput
class LLMDecisionPathTreeOutput(BaseModel):
    condition_registry: list[LLMBinaryCondition] = Field(default_factory=list)  # 新增
    paths: list[LLMDecisionPathItem] = Field(default_factory=list)
    blocking_conditions: list[LLMBlockingConditionItem] = Field(default_factory=list)
```

### LLM Prompt 变更

**文件**: `engines/simulation_run/decision_path_tree/prompts/civil_loan.py`

核心改动：
1. 在 prompt 开头新增"关键条件注册表"指令，要求 LLM 先列出案件关键二元条件（COND-A 到 COND-N）
2. 每条路径要求填写 `condition_activations`（条件组合）和 `outcome_range`（结果区间描述）
3. 明确禁止 LLM 填写精确概率：*"不要输出具体概率数字，条件组合已经传达了不确定性结构"*
4. 提供示例 JSON 结构

**文件**: `engines/simulation_run/decision_path_tree/prompts/labor_dispute.py` 和 `real_estate.py` — 类似改动，条件列表需针对各案件类型定制。

### Generator 规则层变更

**文件**: `engines/simulation_run/decision_path_tree/generator.py`

新增规则：
1. 从 LLM 输出的 `condition_registry` 构建 `BinaryCondition` 列表，写入 `DecisionPathTree.condition_registry`
2. 每条路径：从 `LLMDecisionPathItem.condition_activations` 构建 `ConditionActivation` 列表
3. 若 `condition_activations` 非空，将 `probability` 设为 `None`（清空旧字段）
4. 将 `outcome_range` 从 LLM 中间模型映射到 `DecisionPath.outcome_range`
5. 验证所有 `condition_activations` 中的 `condition_id` 都存在于 `condition_registry`（非法 ID 过滤）

### Display Resolver 变更

**文件**: `engines/shared/display_resolver.py:resolve_path()`

新逻辑：若 `path.condition_activations` 非空，格式化为：
```
"原告全额获支持 [录音✓ 代付✓]"
```
否则回退到旧逻辑（`possible_outcome (72%)`）。

### 报告层变更

**文件**: `scripts/run_case.py:_write_md()`

Decision Path Tree section 改为矩阵格式：

```markdown
## 裁判情景树

| 情景 | 触发条件组合 | 结果区间 | 有利方 |
|------|------------|---------|-------|
| PATH-A | 录音✓ + 代付✓ | 原告全额获支持 | 原告 |
| PATH-B | 录音✓ + 代付✗ | 部分支持（本金）| 原告 |
| PATH-C | 录音✗ | 被告抗辩成立 | 被告 |

### 关键条件说明
- **COND-A 录音采信/不采信**: 录音合法获采信 → 借款合意成立
- **COND-B 支付宝代付补强/不补强**: 代付声明 + 流水可核实 → 交付事实认定
```

### `probability` 变 Optional 的下游消费方全量清单

**⚠️ 这是 F2 最主要的实施陷阱**：`DecisionPath.probability` 变为 `Optional[float]` 之后，以下消费方都会出现 `TypeError`（`None:.0%` 格式化）或排序崩溃，必须全部加 None 守卫。

| 文件 | 问题代码 | 修复方式 |
|------|---------|---------|
| `engines/simulation_run/decision_path_tree/generator.py` | `sorted(paths, key=lambda p: p.probability, reverse=True)` | `key=lambda p: p.probability or 0.0` |
| `engines/simulation_run/decision_path_tree/generator.py` | `PathRankingItem(probability=p.probability, ...)` | PathRankingItem.probability 也改为 Optional，或传 `p.probability or 0.0` |
| `engines/shared/models/pipeline.py` (`PathRankingItem`) | `probability: float = Field(..., ge=0.0, le=1.0)` — 必填非 Optional | 改为 `Optional[float] = Field(default=None, ...)` |
| `engines/shared/consistency_checker.py` | `f"prob={most_likely.probability:.0%}"` | `f"prob={most_likely.probability:.0%}" if most_likely.probability is not None else ""` |
| `engines/report_generation/executive_summarizer/summarizer.py` | `f"（概率 {path.probability:.0%}）：{path.trigger_condition}"` | 同上，None 时省略概率括号 |
| `engines/report_generation/docx_generator.py` | `path.get("probability", 0.5)` → `prob`，后用 `f"概率 {prob:.0%}"` | 检查 `prob is not None` 再渲染；None 时改渲染条件标签 |
| `engines/report_generation/perspective_layer.py` (F1 新建) | 按 probability 排序 favorable_paths | 使用 `key=lambda p: p.probability or 0.0` |

**`confidence_interval` 处理**：当 `condition_activations` 非空时，规则层同时将 `confidence_interval` 清为 `None`。`mediation_range.py` 用 `confidence_interval` 计算，会退回到默认区间 `(0.3, 0.9)`——这是可接受行为，但需在报告/CHANGELOG 中说明。

### 需修改的文件清单

| 文件 | 变更类型 |
|------|---------|
| `engines/shared/models/pipeline.py` | 追加 `BinaryCondition`, `ConditionActivation`, `OutcomeRange`；更新 `DecisionPath`, `DecisionPathTree`；**`PathRankingItem.probability` 改为 Optional** |
| `engines/simulation_run/decision_path_tree/schemas.py` | 追加 LLM 中间模型；更新 `LLMDecisionPathItem`, `LLMDecisionPathTreeOutput` |
| `engines/simulation_run/decision_path_tree/generator.py` | 新规则层逻辑；**None-safe sort for `_rank_paths()`** |
| `engines/simulation_run/decision_path_tree/prompts/civil_loan.py` | Prompt 改写（条件树结构） |
| `engines/simulation_run/decision_path_tree/prompts/labor_dispute.py` | 同上 |
| `engines/simulation_run/decision_path_tree/prompts/real_estate.py` | 同上 |
| `engines/shared/display_resolver.py` | 更新 `resolve_path()` |
| `engines/shared/consistency_checker.py` | **None-guard: `probability:.0%`** |
| `engines/report_generation/executive_summarizer/summarizer.py` | **None-guard: `path.probability:.0%`** |
| `engines/report_generation/docx_generator.py` | **None-guard: 概率标签；改渲染条件激活符号** |
| `scripts/run_case.py` | 更新 `_write_md()` decision tree section |
| `engines/shared/tests/test_models_p*.py` | 更新/新增测试 |
| `engines/simulation_run/decision_path_tree/tests/test_generator.py` | 更新测试 |

### 验证清单 (F2)

- [ ] `DecisionPathTree.condition_registry` 非空（至少含 2 个条件）
- [ ] 每条 `DecisionPath.condition_activations` 中的 `condition_id` 都在 `condition_registry` 中
- [ ] 当 `condition_activations` 非空时，`DecisionPath.probability` 为 `None`
- [ ] `resolve_path()` 输出含条件标签（`[录音✓ 代付✗]`），不含原始概率百分比
- [ ] 报告 Decision Path Tree section 变为矩阵格式
- [ ] LLM prompt 测试：不包含如 "probability: 0.72" 之类的伪精确数字
- [ ] 旧测试（使用 `probability` 字段）不因 `Optional` 变更而失败
- [ ] 所有三种 case_type（civil_loan, labor_dispute, real_estate）的 prompt 均已更新
- [ ] 全部概率消费方无 TypeError：`consistency_checker.py`、`summarizer.py`、`docx_generator.py` 在 probability=None 时不崩溃
- [ ] `PathRankingItem.probability` 为 Optional 后，`path_ranking` 列表仍可正确序列化/反序列化
- [ ] Mixed state：部分路径有 `condition_activations`，部分无，`resolve_path()` 对两种路径分别输出正确格式
- [ ] `condition_activations` 中包含非法 `condition_id` 时，规则层过滤掉该激活，不崩溃
- [ ] `DecisionPath.probability=None` + `F1 build_perspective_summary()` 按 probability 排序不崩溃

---

## F3：证据作战矩阵（7列分析）

### 设计原则

为每件关键证据生成 7 维度作战分析，重点服务于庭审质证准备。优先针对争议性最高的证据类型（录音、录屏、滴滴记录、朋友圈截图、支付宝代付声明）。

采用独立新模块 `engines/simulation_run/evidence_battle_matrix/`，与现有流水线松耦合，通过 `--skip-matrix` 可跳过（控制成本）。

### 7 列定义

| 列号 | 字段名 | 中文标签 | 内容说明 |
|------|--------|---------|---------|
| 1 | `authenticity_analysis` | 真实性 | 证据制作人、制作时间、原始载体（原件/复印件/电子数据） |
| 2 | `completeness_analysis` | 完整性 | 是否完整呈现，是否存在截取、剪辑风险 |
| 3 | `relevance_analysis` | 关联性 | 证明哪项事实命题（链接到 `target_fact_ids`） |
| 4 | `admissibility_basis` | 可采性 | 法律依据（《民事诉讼法》条款、司法解释），与 `AdmissibilityEvaluator` 结果整合 |
| 5 | `proof_direction` | 证明方向 | 证明哪方立场，证明力程度（直接/间接/辅助印证） |
| 6 | `opponent_attacks` | 对方攻击点 | 对方质证时可能提出的 2-4 个具体攻击点 |
| 7 | `our_reinforcement` | 我方补强点 | 针对每个攻击点的补强策略（关联证据 ID + 补充措施） |

### 新增数据模型

**推荐位置**: `engines/simulation_run/evidence_battle_matrix/schemas.py`（新文件）

```python
from engines.shared.models.core import Perspective
from engines.shared.models.analysis import EvidenceIndex

class EvidenceAttackPoint(BaseModel):
    """对方可能的单个质证攻击点。"""
    attack_id: str = Field(..., min_length=1)
    attack_description: str = Field(..., min_length=1)
    attack_severity: str = Field(default="medium")  # "high" / "medium" / "low"
    source_rule: str = Field(default="")  # 攻击点的法律依据或推断来源


class EvidenceReinforcementPoint(BaseModel):
    """针对一个攻击点的我方补强策略。"""
    reinforcement_id: str = Field(..., min_length=1)
    linked_attack_id: str = Field(default="")       # 对应哪个攻击点
    reinforcement_description: str = Field(..., min_length=1)
    supporting_evidence_ids: list[str] = Field(default_factory=list)  # 补强所用证据
    action_required: str = Field(default="")        # 如"申请鉴定"、"补充提交"


class EvidenceBattleItem(BaseModel):
    """单件证据的 7 列作战分析。"""
    evidence_id: str = Field(..., min_length=1)
    evidence_title: str = Field(default="")
    evidence_type: str = Field(default="")          # 冗余字段，便于报告渲染

    # 7 列
    authenticity_analysis: str = Field(..., min_length=1)   # 1. 真实性
    completeness_analysis: str = Field(..., min_length=1)   # 2. 完整性
    relevance_analysis: str = Field(..., min_length=1)      # 3. 关联性
    admissibility_basis: str = Field(..., min_length=1)     # 4. 可采性
    proof_direction: str = Field(..., min_length=1)         # 5. 证明方向

    opponent_attacks: list[EvidenceAttackPoint] = Field(    # 6. 对方攻击点
        default_factory=list,
        description="对方质证时可能的 2-4 个攻击点",
    )
    our_reinforcement: list[EvidenceReinforcementPoint] = Field(  # 7. 我方补强点
        default_factory=list,
        description="针对各攻击点的补强策略",
    )
    perspective: Perspective = Field(
        default=Perspective.neutral,
        description="补强点所站视角（plaintiff/defendant/neutral）",
    )


class EvidenceBattleMatrix(BaseModel):
    """证据作战矩阵 — 多件证据的 7 列分析聚合。"""
    matrix_id: str = Field(..., min_length=1)
    case_id: str = Field(..., min_length=1)
    run_id: str = Field(..., min_length=1)
    items: list[EvidenceBattleItem] = Field(default_factory=list)
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    )


class EvidenceBattleMatrixInput(BaseModel):
    """EvidenceBattleMatrixGenerator 输入 wrapper。"""
    case_id: str = Field(..., min_length=1)
    run_id: str = Field(..., min_length=1)
    evidence_index: EvidenceIndex
    perspective: Optional[Perspective] = None          # 补强点视角（与 F1 联动）
    priority_evidence_ids: Optional[list[str]] = None  # 仅分析指定证据（None=全部）
```

### 新模块目录结构

```
engines/simulation_run/evidence_battle_matrix/
├── __init__.py                    # 导出 EvidenceBattleMatrixGenerator, EvidenceBattleMatrixInput, EvidenceBattleMatrix
├── schemas.py                     # 上述新模型
├── matrix_generator.py            # 主类
├── prompts/
│   ├── __init__.py               # PROMPT_REGISTRY
│   ├── civil_loan.py             # 民间借贷专用 prompt
│   ├── labor_dispute.py          # 劳动争议专用 prompt（初始可复用 civil_loan 主干）
│   └── real_estate.py            # 房产纠纷专用 prompt（同上）
└── tests/
    ├── __init__.py
    └── test_matrix_generator.py
```

### 主类设计

**文件**: `engines/simulation_run/evidence_battle_matrix/matrix_generator.py`

```python
class EvidenceBattleMatrixGenerator:
    """
    为关键证据生成 7 列作战矩阵。

    职责：
    1. 接收 EvidenceBattleMatrixInput
    2. 过滤目标证据（priority_evidence_ids 或高风险证据）
    3. 批量或逐条调用 LLM（structured output）
    4. 规则层校验：每件证据至少 2 个 opponent_attacks，至少 1 个 reinforcement
    5. 返回 EvidenceBattleMatrix

    合约保证：
    - 若 LLM 整体失败，返回空 matrix（items=[]），不抛异常
    - opponent_attacks 中的 evidence_id 引用必须存在于 evidence_index
    - perspective 字段填充（来自 input.perspective 或默认 neutral）
    """
```

**LLM 中间模型**（在 `schemas.py` 中定义）：

```python
class LLMEvidenceAttackPoint(BaseModel):
    """LLM 输出的单个攻击点（类型化中间模型，与其他 LLM 中间模型保持一致）。"""
    attack_id: str = Field(default="")
    attack_description: str = Field(default="")
    attack_severity: str = Field(default="medium")
    source_rule: str = Field(default="")

class LLMEvidenceReinforcementPoint(BaseModel):
    """LLM 输出的单个补强策略（类型化）。"""
    reinforcement_id: str = Field(default="")
    linked_attack_id: str = Field(default="")
    reinforcement_description: str = Field(default="")
    supporting_evidence_ids: list[str] = Field(default_factory=list)
    action_required: str = Field(default="")

class LLMEvidenceBattleItem(BaseModel):
    """LLM 输出的单条证据分析（中间模型，使用类型化子模型保持规则层可校验性）。"""
    evidence_id: str = Field(default="")
    authenticity_analysis: str = Field(default="")
    completeness_analysis: str = Field(default="")
    relevance_analysis: str = Field(default="")
    admissibility_basis: str = Field(default="")
    proof_direction: str = Field(default="")
    opponent_attacks: list[LLMEvidenceAttackPoint] = Field(default_factory=list)   # 类型化，便于规则层校验
    our_reinforcement: list[LLMEvidenceReinforcementPoint] = Field(default_factory=list)

class LLMEvidenceBattleMatrixOutput(BaseModel):
    items: list[LLMEvidenceBattleItem] = Field(default_factory=list)
```

### 证据过滤策略

当 `priority_evidence_ids=None` 时，优先分析以下高风险证据（按 `evidence_type` 或 `title` 关键词匹配）：
1. `evidence_type == "audio_recording"` 或 title 含"录音"
2. `evidence_type == "screen_recording"` 或 title 含"录屏"
3. title 含"滴滴" / "专车" / "行程"
4. title 含"朋友圈"
5. title 含"支付宝" + "代付" / "声明"
6. `admissibility_score < 0.7` 的证据（已被 AdmissibilityEvaluator 标注为脆弱）

最多分析 10 件证据（超出截断），可通过 `priority_evidence_ids` 精确控制。

### 流水线集成

**文件**: `scripts/run_case.py`

1. 在 `_run_post_debate()` 中，`AdmissibilityEvaluator` 之后新增：

```python
# F3: EvidenceBattleMatrix
if not skip_matrix:
    print("  - Evidence battle matrix (F3)...")
    matrix_gen = EvidenceBattleMatrixGenerator(
        llm_client=llm_client,
        model=selector.select("evidence_battle_matrix"),
        temperature=0.0,
        max_retries=2,
    )
    battle_matrix = await matrix_gen.generate(
        EvidenceBattleMatrixInput(
            case_id=case_id,
            run_id=run_id,
            evidence_index=admissibility_result,  # 使用 admissibility 评估后的 index
            perspective=Perspective(perspective) if perspective else None,
        )
    )
    artifacts["battle_matrix"] = battle_matrix
    print(f"    ✓ Analyzed {len(battle_matrix.items)} evidence items")
```

2. `_write_md()` 新增 `battle_matrix=None` 参数，渲染新 section：

```markdown
## 证据作战矩阵

### 🎙 证据 EV001 — 录音文件

| 维度 | 分析 |
|------|------|
| **真实性** | 原告自行录制，手机内存原始文件，制作时间与借款日期吻合 |
| **完整性** | 仅提交片段（3分15秒），完整录音未提交 |
| **关联性** | 证明借款合意（目标命题：借款关系存在）|
| **可采性** | 《民事诉讼法》第67条，经过合法手段收集的视听资料具有证明效力 |
| **证明方向** | 直接证明借款合意，间接印证还款承诺 |

**对方攻击点**:
1. [高] 录音系秘密录制，侵犯被告隐私权，申请排除
2. [中] 录音文件已剪辑，内容断章取义
3. [低] 录音人声真实性（申请声纹鉴定）

**我方补强点**:
1. → 攻击1: 引用最高院指导案例，借贷纠纷中防卫性录音合法性认定先例
2. → 攻击2: 申请提交完整录音+时间戳元数据，反驳剪辑指控
3. → 攻击3: 结合 EV003（借条笔迹）作旁证，弱化声纹鉴定影响
```

3. CLI 新增 `--skip-matrix` 标志（默认不跳过，但可用于快速调试）：

```python
parser.add_argument(
    "--skip-matrix",
    action="store_true",
    help="Skip evidence battle matrix generation (saves ~2-3 LLM calls)",
)
```

4. `ModelSelector` 新增 `evidence_battle_matrix` task tier（默认 `balanced` 级别）。

> **注意**: `ModelSelector` 使用硬编码的 `DEFAULT_TASK_TIERS` 字典（`engines/shared/model_selector.py`），不是 YAML 驱动。F3 应直接在该字典中追加 `"evidence_battle_matrix": ModelTier.balanced`，而非修改 `config/model_tiers.yaml`。

### 与 AdmissibilityEvaluator 的整合

F3 矩阵在 `AdmissibilityEvaluator` **之后**运行：
- 直接读取 `ev.admissibility_score`、`ev.admissibility_challenges`、`ev.exclusion_impact` 填充"可采性"列
- 避免重复评估，只用 LLM 补充"对方攻击点"和"我方补强点"两列（其余 5 列可由规则层从 `Evidence` 字段拼合）

这样可降低 LLM 调用量：只有第 6、7 两列需要 LLM 生成，其余 5 列可部分规则化。

### 需修改/新建的文件清单

| 文件 | 变更类型 |
|------|---------|
| `engines/simulation_run/evidence_battle_matrix/` | **新建目录** |
| `engines/simulation_run/evidence_battle_matrix/__init__.py` | 新建 |
| `engines/simulation_run/evidence_battle_matrix/schemas.py` | 新建 |
| `engines/simulation_run/evidence_battle_matrix/matrix_generator.py` | 新建 |
| `engines/simulation_run/evidence_battle_matrix/prompts/__init__.py` | 新建 |
| `engines/simulation_run/evidence_battle_matrix/prompts/civil_loan.py` | 新建 |
| `engines/simulation_run/evidence_battle_matrix/tests/__init__.py` | 新建 |
| `engines/simulation_run/evidence_battle_matrix/tests/test_matrix_generator.py` | 新建 |
| `scripts/run_case.py` | 集成到 `_run_post_debate()`，更新 `_write_md()`，新增 `--skip-matrix` arg |
| `scripts/run_wang_v_chen_zhuang.py` | 同上 |
| `config/model_tiers.yaml` | 新增 `evidence_battle_matrix` task |
| `engines/shared/model_selector.py` | 在 `DEFAULT_TASK_TIERS` 追加 `"evidence_battle_matrix": ModelTier.balanced` |

### 验证清单 (F3)

- [ ] `evidence_battle_matrix.json` 在输出目录生成
- [ ] 每件证据包含全部 7 个字段（均非空）
- [ ] `opponent_attacks` 至少 2 条
- [ ] `our_reinforcement` 至少 1 条，且含 `linked_attack_id`
- [ ] `supporting_evidence_ids` 中的 ID 均存在于 `evidence_index`
- [ ] `admissibility_basis` 列内容与 `AdmissibilityEvaluator` 结果一致（无矛盾）
- [ ] 高风险证据（录音、录屏等）优先进入矩阵
- [ ] `--skip-matrix` 可正常跳过，输出目录无 `evidence_battle_matrix.json`
- [ ] 报告 `## 证据作战矩阵` section 正常渲染
- [ ] 当 `perspective=plaintiff` 时，`our_reinforcement` 站原告视角
- [ ] `run_wang_v_chen_zhuang.py` 的 `--skip-matrix` flag 已添加，wang 案可正常跳过
- [ ] `evidence_battle_matrix.json` 中 evidence_id 全部存在于 `evidence_index`（rule-layer 合法性校验）
- [ ] evidence 数量超 10 件时，矩阵恰好包含 10 条（截断规则生效）

---

## 横切关注点

### 测试策略

**F1** — 纯规则层，单元测试即可：
- `test_perspective_layer.py`：给定模拟 artifacts，验证 `ClientPerspectiveSummary` 各字段正确
- 快照测试：`_write_md()` 输出的 `## 委托方视角摘要` section

**F2** — 需要模型层测试 + LLM 集成测试：
- `test_models_*.py`：验证 `DecisionPath` 向后兼容（旧 `probability` 字段 Optional）
- `test_generator.py`：验证规则层正确映射 LLM 条件输出；验证非法 condition_id 被过滤
- `test_display_resolver.py`：验证两种路径格式（有/无条件）均正确渲染

**F3** — 需要 mock LLM 的单元测试：
- `test_matrix_generator.py`：mock LLM 返回，验证规则层校验（至少 2 个攻击点等）
- `test_matrix_generator.py`：验证证据过滤策略（录音/录屏优先）
- 合约测试：LLM 失败时返回 `items=[]`，不抛异常

### 向后兼容性

- **F1**：完全向后兼容，`--perspective` 是可选 flag
- **F2**：`DecisionPath.probability` 和 `confidence_interval` 变为 `Optional`，需检查所有 `DecisionPath` 的消费方（`display_resolver.py`、`_write_md()`、`docx_generator.py`、`mediation_range.py`）是否处理 `None`
- **F3**：新模块，不修改现有模型，完全向后兼容

### 与 F1 的联动

F2 和 F3 都可从 `--perspective` 获益：
- F2 的路径矩阵可以在 perspective=plaintiff 时，优先高亮 `party_favored=="plaintiff"` 的路径
- F3 的 `our_reinforcement` 可根据 perspective 决定站哪方立场

建议在实现 F2/F3 时，将 `perspective` 参数透传到各自的 generator。

### 模型 tier 配置

在 `config/model_tiers.yaml` 新增（F3）：
```yaml
tasks:
  evidence_battle_matrix:
    tier: balanced      # "fast" / "balanced" / "deep"
    description: "7-column evidence battle matrix analysis"
```

---

## 实施顺序与工作量估算

### 推荐顺序

```
F1 (1-2天)  →  F2 (2-3天)  →  F3 (3-4天)
```

### 工作量明细

**F1 — 低复杂度（约 1-2 天）**:
- 2 个新文件（`perspective_layer.py`、`schemas.py` 片段）
- 3 个现有文件小改（`run_case.py`、`run_wang_v_chen_zhuang.py`、`docx_generator.py`）
- 无 LLM 调用，全规则层
- 无数据模型变更风险

**F2 — 中等复杂度（约 2-3 天）**:
- 3 个新 Pydantic 模型 + 更新 2 个现有模型
- 3 个 prompt 文件重写（civil_loan + labor_dispute + real_estate）
- Generator 规则层重要逻辑新增
- 需要运行 wang 案验证 LLM prompt 输出质量
- 风险：LLM 不稳定地输出条件（需要 prompt 工程迭代）

**F3 — 高复杂度（约 3-4 天）**:
- 1 个全新模块（~8 个文件）
- LLM prompt 设计（7 列输出）
- 与 AdmissibilityEvaluator 整合（列 4 的数据来源）
- 报告渲染（每件证据一个 sub-section）
- 风险：输出格式冗长，可能需要 token budget 管理

### 关键风险

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| F2 LLM 不输出条件，回退到旧 probability | 条件树为空，降级到旧格式 | 规则层 fallback：若 condition_activations 为空保留旧 probability |
| F3 LLM 7 列输出质量低 | 矩阵内容无价值 | 先跑 wang 案验证，调整 prompt；列 1-5 可先规则化生成 |
| F2 Optional 化破坏下游消费方 | 报告渲染报错 | 全局 grep `\.probability` 找所有消费点，逐一加 None 守卫 |
| F3 token 成本高 | 每次运行增加 $0.5-1 | 默认只分析高风险证据（≤10件），提供 `--skip-matrix` |

---

## 验收标准汇总

运行 wang 案端到端：
```bash
# F1 验收
python scripts/run_case.py cases/wang_v_chen_zhuang_2025.yaml \
    --perspective plaintiff \
    --output-dir outputs/test-f1

# F2 验收
python scripts/run_case.py cases/wang_v_chen_zhuang_2025.yaml \
    --output-dir outputs/test-f2
# → outputs/test-f2/decision_tree.json 中 condition_registry 非空

# F3 验收
python scripts/run_case.py cases/wang_v_chen_zhuang_2025.yaml \
    --output-dir outputs/test-f3
# → outputs/test-f3/evidence_battle_matrix.json 存在，录音证据有 ≥2 个 opponent_attacks

# 完整集成验收
python scripts/run_case.py cases/wang_v_chen_zhuang_2025.yaml \
    --perspective defendant \
    --output-dir outputs/test-full
```

所有测试通过：
```bash
python -m pytest engines/ -x -q
```

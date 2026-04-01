"""
V3.1 四层报告数据模型 / V3.1 4-Layer Report Data Models.

所有报告产物的 Pydantic 模型定义。
每个模型对应报告架构中的一个组件。

V3.1 变更:
- 新增 EvidencePriority 枚举（核心/辅助/背景）
- 新增 EvidencePriorityCard（证据优先级分层卡）
- 新增 EvidenceBasicCard / EvidenceKeyCard（双层证据卡，替代七问矩阵）
- 新增 TimelineEvent（时间线事件节点）
- CoverSummary 增加 winning_move / blocking_conditions
- IssueMapCard 增加 parent_issue_id / depth（树状争点）
- Layer1Cover 增加 timeline / evidence_priorities
- Layer2Core 增加 evidence_cards / unified_electronic_strategy
- PerspectiveOutput 改为动作方案（补证清单/质证要点/庭审发问等）
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# 标注系统 / Tag system
# ---------------------------------------------------------------------------


class SectionTag(str, Enum):
    """全文强制标注类型。每个段落/章节必须携带一个标签。"""

    fact = "事实"           # 无争议的客观事实
    inference = "推断"      # 基于事实的逻辑推理
    assumption = "假设"     # 条件性假设
    opinion = "观点"        # 分析性意见
    recommendation = "建议"  # 可执行建议


# ---------------------------------------------------------------------------
# 证据风险红绿灯 / Evidence risk traffic light
# DEPRECATED in V3.1: replaced by EvidencePriority + EvidencePriorityCard.
# Kept for backward compatibility only.
# ---------------------------------------------------------------------------


# DEPRECATED: replaced by EvidencePriority in V3.1
class EvidenceRiskLevel(str, Enum):
    """证据稳定性分级。颜色仅代表证据稳定性，不代表立场。

    .. deprecated:: V3.1
        Use :class:`EvidencePriority` instead.
    """

    green = "green"    # 第三方可核实（银行流水、公证文书等）
    yellow = "yellow"  # 截图/单方提供（微信截图、短信等）
    red = "red"        # 争议+敏感（录音合法性存疑、复印件无原件等）


# DEPRECATED: replaced by EvidencePriorityCard in V3.1
class EvidenceTrafficLight(BaseModel):
    """单条证据的风险红绿灯评估。

    .. deprecated:: V3.1
        Use :class:`EvidencePriorityCard` instead.
    """

    evidence_id: str
    title: str
    risk_level: EvidenceRiskLevel
    reason: str = Field(description="分级理由")


# ---------------------------------------------------------------------------
# V3.1 证据优先级 / Evidence priority system
# ---------------------------------------------------------------------------


class EvidencePriority(str, Enum):
    """证据优先级分层。"""

    core = "核心证据"        # Controls outcome of L1 issue
    supporting = "辅助证据"  # Corroborates core evidence
    background = "背景证据"  # Context only


class EvidencePriorityCard(BaseModel):
    """证据优先级分层卡。"""

    evidence_id: str
    title: str
    priority: EvidencePriority
    reason: str = Field(description="分层理由")
    controls_issue_ids: list[str] = Field(
        default_factory=list,
        description="控制哪些争点的结果（仅核心证据）",
    )


# ---------------------------------------------------------------------------
# V3.1 双层证据卡 / Two-tier evidence cards
# ---------------------------------------------------------------------------


class EvidenceBasicCard(BaseModel):
    """基础证据卡（所有证据）-- 4 字段。"""

    evidence_id: str
    q1_what: str = Field(description="① 这是什么证据")
    q2_target: str = Field(
        description="② 服务争点 / 证明命题 / 支持方向（合并原 Q2+Q3）",
    )
    q3_key_risk: str = Field(description="③ 关键风险")
    q4_best_attack: str = Field(description="④ 对方最佳攻击点")
    priority: EvidencePriority = EvidencePriority.supporting
    tag: SectionTag = SectionTag.inference


class EvidenceKeyCard(EvidenceBasicCard):
    """关键证据卡（核心证据）-- 增加 2 字段。"""

    q5_reinforce: str = Field(description="⑤ 如何加固")
    q6_failure_impact: str = Field(
        description="⑥ 失效影响（哪些结论需重算）",
    )


# ---------------------------------------------------------------------------
# V3.1 时间线 / Timeline
# ---------------------------------------------------------------------------


class TimelineEvent(BaseModel):
    """案件时间线事件节点。"""

    date: str = Field(description="日期（YYYY-MM-DD 或自然语言）")
    event: str = Field(description="事件描述")
    source: str = Field(default="", description="来源证据 ID 或 'case_data'")
    disputed: bool = Field(default=False, description="该事件是否存在争议")
    tag: SectionTag = SectionTag.fact


# ---------------------------------------------------------------------------
# Layer 1: Cover Summary (封面摘要层)
# ---------------------------------------------------------------------------


# DEPRECATED in V3.1: plaintiff/defendant summaries moved to Layer 3 exclusively
class PerspectivePlaintiffSummary(BaseModel):
    """原告视角摘要。

    .. deprecated:: V3.1
        Moved to Layer 3 exclusively. Kept in CoverSummary for backward
        compatibility only.
    """

    top3_strengths: list[str] = Field(min_length=1, max_length=5, description="三大优势")
    top2_dangers: list[str] = Field(min_length=1, max_length=3, description="两大危险")
    top3_actions: list[str] = Field(min_length=1, max_length=5, description="三项立即行动")


# DEPRECATED in V3.1: plaintiff/defendant summaries moved to Layer 3 exclusively
class PerspectiveDefendantSummary(BaseModel):
    """被告视角摘要。

    .. deprecated:: V3.1
        Moved to Layer 3 exclusively. Kept in CoverSummary for backward
        compatibility only.
    """

    top3_defenses: list[str] = Field(min_length=1, max_length=5, description="三大防线")
    plaintiff_likely_supplement: list[str] = Field(
        default_factory=list, description="原告可能补强方向"
    )
    optimal_attack_order: list[str] = Field(
        default_factory=list, description="最优攻击顺序"
    )


class CoverSummary(BaseModel):
    """封面摘要（Layer 1B）。"""

    neutral_conclusion: str = Field(description="一句话中立结论 「事实」")
    winning_move: str = Field(
        default="",
        description="胜负手：决定案件走向的关键证据/争点",
    )
    blocking_conditions: list[str] = Field(
        default_factory=list,
        description="阻断条件：哪些事实翻转会改变结论",
    )
    # DEPRECATED: plaintiff_summary and defendant_summary moved to Layer 3 exclusively
    plaintiff_summary: Optional[PerspectivePlaintiffSummary] = Field(
        default=None,
    )  # DEPRECATED: Moved to Layer 3
    defendant_summary: Optional[PerspectiveDefendantSummary] = Field(
        default=None,
    )  # DEPRECATED: Moved to Layer 3


class Layer1Cover(BaseModel):
    """Layer 1: 封面摘要层。"""

    cover_summary: CoverSummary
    timeline: list[TimelineEvent] = Field(
        default_factory=list,
        description="案件时间线（最少 5 节点）",
    )
    scenario_tree_summary: str = Field(
        default="", description="条件场景树摘要（if-then 格式，无百分比）「推断」"
    )
    evidence_priorities: list[EvidencePriorityCard] = Field(
        default_factory=list,
        description="证据优先级分层（替代红绿灯）",
    )
    # DEPRECATED: replaced by evidence_priorities
    evidence_traffic_lights: list[EvidenceTrafficLight] = Field(
        default_factory=list,
    )  # DEPRECATED: Use evidence_priorities instead


# ---------------------------------------------------------------------------
# Layer 2: Neutral Adversarial Core (中立对抗内核层)
# ---------------------------------------------------------------------------


class FactBaseEntry(BaseModel):
    """事实底座条目 -- 仅限无争议的客观事实，不含法律推断。"""

    fact_id: str
    description: str
    source_evidence_ids: list[str] = Field(default_factory=list)
    tag: SectionTag = SectionTag.fact


class IssueMapCard(BaseModel):
    """争点地图卡片 -- 支持树状结构。"""

    issue_id: str
    issue_title: str
    parent_issue_id: Optional[str] = Field(
        default=None,
        description="父争点 ID，None 表示 L1 根节点",
    )
    depth: int = Field(
        default=0,
        description="层级深度：0=L1 根争点, 1+=子争点",
    )
    plaintiff_thesis: str = Field(description="原告主张")
    defendant_thesis: str = Field(description="被告主张")
    decisive_evidence: list[str] = Field(
        default_factory=list, description="决定性证据 ID 列表"
    )
    current_gaps: list[str] = Field(
        default_factory=list, description="当前缺口"
    )
    outcome_sensitivity: str = Field(
        default="", description="结果敏感度"
    )
    tag: SectionTag = SectionTag.inference


# DEPRECATED in V3.1: replaced by EvidenceBasicCard / EvidenceKeyCard
class EvidenceBattleCard(BaseModel):
    """证据作战矩阵卡片 -- 每条证据的七问。

    .. deprecated:: V3.1
        Use :class:`EvidenceBasicCard` / :class:`EvidenceKeyCard` instead.
    """

    evidence_id: str
    q1_what: str = Field(description="1. 这是什么证据")
    q2_proves: str = Field(description="2. 证明什么命题")
    q3_direction: str = Field(description="3. 证明方向（支持谁）")
    q4_risks: str = Field(
        description="4. 真实性/完整性/关联性/合法性风险"
    )
    q5_opponent_attack: str = Field(description="5. 对方如何攻击")
    q6_reinforce: str = Field(description="6. 如何加固")
    q7_failure_impact: str = Field(
        description="7. 若此证据失败，哪些结论需重新计算"
    )
    risk_level: EvidenceRiskLevel = EvidenceRiskLevel.yellow
    tag: SectionTag = SectionTag.inference


class ConditionalNode(BaseModel):
    """条件场景树节点 -- 二元条件分支（是/否），不使用概率百分比。"""

    node_id: str
    condition: str = Field(description="条件问题（如'录音是否被采信？'）")
    yes_outcome: Optional[str] = Field(
        default=None, description="条件成立时的结论（叶节点）"
    )
    no_outcome: Optional[str] = Field(
        default=None, description="条件不成立时的结论（叶节点）"
    )
    yes_child_id: Optional[str] = Field(
        default=None, description="条件成立时的子节点 ID（非叶节点）"
    )
    no_child_id: Optional[str] = Field(
        default=None, description="条件不成立时的子节点 ID（非叶节点）"
    )
    related_evidence_ids: list[str] = Field(default_factory=list)
    tag: SectionTag = SectionTag.inference


class ConditionalScenarioTree(BaseModel):
    """条件场景树 -- 替代概率式裁判路径树。"""

    tree_id: str
    case_id: str
    root_node_id: str
    nodes: list[ConditionalNode] = Field(default_factory=list)
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    )


class Layer2Core(BaseModel):
    """Layer 2: 中立对抗内核层。"""

    fact_base: list[FactBaseEntry] = Field(default_factory=list)
    issue_map: list[IssueMapCard] = Field(default_factory=list)
    evidence_cards: list[EvidenceBasicCard] = Field(
        default_factory=list,
        description="双层证据卡（基础卡+关键卡混合列表）",
    )
    unified_electronic_strategy: str = Field(
        default="",
        description="统一电子证据补强策略",
    )
    scenario_tree: Optional[ConditionalScenarioTree] = None
    # DEPRECATED: replaced by evidence_cards
    evidence_battle_matrix: list[EvidenceBattleCard] = Field(
        default_factory=list,
    )  # DEPRECATED: Use evidence_cards instead


# ---------------------------------------------------------------------------
# Layer 3: Role-based Output (角色化输出层)
# ---------------------------------------------------------------------------


class PerspectiveOutput(BaseModel):
    """角色化输出 -- 纯动作方案。"""

    perspective: Literal["plaintiff", "defendant", "neutral"] = Field(
        default="neutral",
        description="视角：plaintiff / defendant / neutral",
    )

    # V3.1 action-oriented fields
    evidence_supplement_checklist: list[str] = Field(
        default_factory=list, description="补证清单"
    )
    cross_examination_points: list[str] = Field(
        default_factory=list, description="质证要点"
    )
    trial_questions: list[str] = Field(
        default_factory=list, description="庭审发问"
    )
    contingency_plans: list[str] = Field(
        default_factory=list, description="应对预案"
    )
    over_assertion_boundaries: list[str] = Field(
        default_factory=list, description="过度主张边界"
    )
    unified_electronic_evidence_strategy: str = Field(
        default="", description="统一电子证据补强策略"
    )

    # DEPRECATED: analysis-based fields from V3.0 (kept for backward compat)
    top_claims: list[str] = Field(
        default_factory=list,
    )  # DEPRECATED: Use evidence_supplement_checklist etc.
    defendant_attack_chains: list[str] = Field(
        default_factory=list,
    )  # DEPRECATED: Moved to cross_examination_points
    evidence_to_supplement: list[str] = Field(
        default_factory=list,
    )  # DEPRECATED: Use evidence_supplement_checklist
    trial_sequence: list[str] = Field(
        default_factory=list,
    )  # DEPRECATED: Use trial_questions
    claims_to_abandon: list[str] = Field(
        default_factory=list,
    )  # DEPRECATED: Use over_assertion_boundaries
    top_defenses: list[str] = Field(
        default_factory=list,
    )  # DEPRECATED: Use cross_examination_points etc.
    plaintiff_supplement_prediction: list[str] = Field(
        default_factory=list,
    )  # DEPRECATED: Use contingency_plans
    evidence_to_challenge_first: list[str] = Field(
        default_factory=list,
    )  # DEPRECATED: Use cross_examination_points
    motions_to_file: list[str] = Field(
        default_factory=list,
    )  # DEPRECATED: Use contingency_plans
    over_assertion_warnings: list[str] = Field(
        default_factory=list,
    )  # DEPRECATED: Use over_assertion_boundaries


class Layer3Perspective(BaseModel):
    """Layer 3: 角色化输出层。"""

    outputs: list[PerspectiveOutput] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Layer 4: Appendix (附录层)
# ---------------------------------------------------------------------------


class Layer4Appendix(BaseModel):
    """Layer 4: 附录层。始终相同，不受 perspective 影响。"""

    adversarial_transcripts_md: str = Field(
        default="", description="三轮对抗辩论完整记录"
    )
    evidence_index_md: str = Field(default="", description="证据索引表")
    timeline_md: str = Field(default="", description="案件时间线")
    glossary_md: str = Field(default="", description="术语表")
    amount_calculation_md: str = Field(default="", description="金额计算明细")


# ---------------------------------------------------------------------------
# 顶层报告 / Top-level report
# ---------------------------------------------------------------------------


class FourLayerReport(BaseModel):
    """V3 四层报告完整产物。"""

    report_id: str
    case_id: str
    run_id: str
    perspective: Literal["plaintiff", "defendant", "neutral"] = Field(
        default="neutral", description="报告视角：plaintiff / defendant / neutral"
    )
    layer1: Layer1Cover
    layer2: Layer2Core
    layer3: Layer3Perspective
    layer4: Layer4Appendix
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    )

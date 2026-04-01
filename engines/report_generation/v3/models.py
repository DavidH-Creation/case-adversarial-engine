"""
V3 四层报告数据模型 / V3 4-Layer Report Data Models.

所有报告产物的 Pydantic 模型定义。
每个模型对应报告架构中的一个组件。
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
# ---------------------------------------------------------------------------


class EvidenceRiskLevel(str, Enum):
    """证据稳定性分级。颜色仅代表证据稳定性，不代表立场。"""

    green = "green"    # 第三方可核实（银行流水、公证文书等）
    yellow = "yellow"  # 截图/单方提供（微信截图、短信等）
    red = "red"        # 争议+敏感（录音合法性存疑、复印件无原件等）


class EvidenceTrafficLight(BaseModel):
    """单条证据的风险红绿灯评估。"""

    evidence_id: str
    title: str
    risk_level: EvidenceRiskLevel
    reason: str = Field(description="分级理由")


# ---------------------------------------------------------------------------
# Layer 1: Cover Summary (封面摘要层)
# ---------------------------------------------------------------------------


class PerspectivePlaintiffSummary(BaseModel):
    """原告视角摘要。"""

    top3_strengths: list[str] = Field(min_length=1, max_length=5, description="三大优势")
    top2_dangers: list[str] = Field(min_length=1, max_length=3, description="两大危险")
    top3_actions: list[str] = Field(min_length=1, max_length=5, description="三项立即行动")


class PerspectiveDefendantSummary(BaseModel):
    """被告视角摘要。"""

    top3_defenses: list[str] = Field(min_length=1, max_length=5, description="三大防线")
    plaintiff_likely_supplement: list[str] = Field(
        default_factory=list, description="原告可能补强方向"
    )
    optimal_attack_order: list[str] = Field(
        default_factory=list, description="最优攻击顺序"
    )


class CoverSummary(BaseModel):
    """封面摘要（Layer 1B）—— perspective 驱动的摘要。"""

    neutral_conclusion: str = Field(description="一句话中立结论 「事实」")
    plaintiff_summary: Optional[PerspectivePlaintiffSummary] = None
    defendant_summary: Optional[PerspectiveDefendantSummary] = None


class Layer1Cover(BaseModel):
    """Layer 1: 封面摘要层。"""

    cover_summary: CoverSummary
    scenario_tree_summary: str = Field(
        default="", description="条件场景树摘要（if-then 格式，无百分比）「推断」"
    )
    evidence_traffic_lights: list[EvidenceTrafficLight] = Field(
        default_factory=list, description="证据风险红绿灯 「事实」"
    )


# ---------------------------------------------------------------------------
# Layer 2: Neutral Adversarial Core (中立对抗内核层)
# ---------------------------------------------------------------------------


class FactBaseEntry(BaseModel):
    """事实底座条目 —— 仅限无争议的客观事实，不含法律推断。"""

    fact_id: str
    description: str
    source_evidence_ids: list[str] = Field(default_factory=list)
    tag: SectionTag = SectionTag.fact


class IssueMapCard(BaseModel):
    """争点地图卡片 —— 固定模板，每个争点一张卡。"""

    issue_id: str
    issue_title: str
    plaintiff_thesis: str = Field(description="原告主张")
    defendant_thesis: str = Field(description="被告主张")
    decisive_evidence: list[str] = Field(
        default_factory=list, description="决定性证据 ID 列表"
    )
    current_gaps: list[str] = Field(
        default_factory=list, description="当前缺口"
    )
    outcome_sensitivity: str = Field(
        default="", description="结果敏感度：该争点翻转对最终结果的影响"
    )
    tag: SectionTag = SectionTag.inference


class EvidenceBattleCard(BaseModel):
    """证据作战矩阵卡片 —— 每条证据的七问。"""

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
    """条件场景树节点 —— 二元条件分支（是/否），不使用概率百分比。"""

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
    """条件场景树 —— 替代概率式裁判路径树。"""

    tree_id: str
    case_id: str
    root_node_id: str
    nodes: list[ConditionalNode] = Field(default_factory=list)
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    )


class Layer2Core(BaseModel):
    """Layer 2: 中立对抗内核层。完全中立，不受 perspective 影响。"""

    fact_base: list[FactBaseEntry] = Field(default_factory=list)
    issue_map: list[IssueMapCard] = Field(default_factory=list)
    evidence_battle_matrix: list[EvidenceBattleCard] = Field(default_factory=list)
    scenario_tree: Optional[ConditionalScenarioTree] = None


# ---------------------------------------------------------------------------
# Layer 3: Role-based Output (角色化输出层)
# ---------------------------------------------------------------------------


class PerspectiveOutput(BaseModel):
    """角色化输出 —— --perspective 驱动的策略层。"""

    perspective: Literal["plaintiff", "defendant", "neutral"] = Field(
        default="neutral",
        description="视角：plaintiff / defendant / neutral",
    )

    # plaintiff 视角字段
    top_claims: list[str] = Field(default_factory=list, description="三大诉请")
    defendant_attack_chains: list[str] = Field(
        default_factory=list, description="被告攻击链预警"
    )
    evidence_to_supplement: list[str] = Field(
        default_factory=list, description="需补强证据清单"
    )
    trial_sequence: list[str] = Field(
        default_factory=list, description="庭审举证顺序建议"
    )
    claims_to_abandon: list[str] = Field(
        default_factory=list, description="应放弃的诉请"
    )

    # defendant 视角字段
    top_defenses: list[str] = Field(default_factory=list, description="三大防线")
    plaintiff_supplement_prediction: list[str] = Field(
        default_factory=list, description="原告可能补强方向"
    )
    evidence_to_challenge_first: list[str] = Field(
        default_factory=list, description="优先质证目标"
    )
    motions_to_file: list[str] = Field(
        default_factory=list, description="应提交的动议"
    )
    over_assertion_warnings: list[str] = Field(
        default_factory=list, description="过度主张警告"
    )


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

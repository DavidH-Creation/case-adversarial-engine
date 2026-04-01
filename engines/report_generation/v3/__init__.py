"""
V3 四层报告架构 / V3 4-Layer Report Architecture.

层级结构：
  Layer 1: Cover Summary (封面摘要层) — 决策者首页
  Layer 2: Neutral Adversarial Core (中立对抗内核层) — 事实底座 + 争点地图 + 证据矩阵 + 场景树
  Layer 3: Role-based Output (角色化输出层) — --perspective 驱动
  Layer 4: Appendix (附录层) — 对抗轮次记录 + 证据索引 + 时间线
"""

from engines.report_generation.v3.models import (
    ConditionalNode,
    ConditionalScenarioTree,
    CoverSummary,
    EvidenceBattleCard,
    EvidenceRiskLevel,
    EvidenceTrafficLight,
    FactBaseEntry,
    FourLayerReport,
    IssueMapCard,
    Layer1Cover,
    Layer2Core,
    Layer3Perspective,
    Layer4Appendix,
    PerspectiveDefendantSummary,
    PerspectivePlaintiffSummary,
    PerspectiveOutput,
    SectionTag,
)

__all__ = [
    "ConditionalNode",
    "ConditionalScenarioTree",
    "CoverSummary",
    "EvidenceBattleCard",
    "EvidenceRiskLevel",
    "EvidenceTrafficLight",
    "FactBaseEntry",
    "FourLayerReport",
    "IssueMapCard",
    "Layer1Cover",
    "Layer2Core",
    "Layer3Perspective",
    "Layer4Appendix",
    "PerspectiveDefendantSummary",
    "PerspectivePlaintiffSummary",
    "PerspectiveOutput",
    "SectionTag",
]

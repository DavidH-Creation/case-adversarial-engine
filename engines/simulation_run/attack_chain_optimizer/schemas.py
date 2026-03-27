"""
attack_chain_optimizer 引擎专用数据模型。
Engine-specific schemas for attack_chain_optimizer.

共享类型从 engines.shared.models 导入；本模块只保留 LLM 中间模型和引擎 I/O wrapper。
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from engines.shared.models import (  # noqa: F401
    EvidenceIndex,
    IssueTree,
    OptimalAttackChain,
)


# ---------------------------------------------------------------------------
# LLM 中间模型 / LLM intermediate models
# ---------------------------------------------------------------------------


class LLMAttackNodeItem(BaseModel):
    """LLM 输出的单个攻击节点（中间模型，由规则层进一步校验）。"""
    attack_node_id: str = Field(default="")
    target_issue_id: str = Field(default="")
    attack_description: str = Field(default="")
    success_conditions: str = Field(default="")
    supporting_evidence_ids: list[str] = Field(default_factory=list)
    counter_measure: str = Field(default="")
    adversary_pivot_strategy: str = Field(default="")


class LLMAttackChainOutput(BaseModel):
    """LLM 批量输出（中间模型）。"""
    top_attacks: list[LLMAttackNodeItem] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# 引擎 I/O wrapper / Engine I/O wrappers
# ---------------------------------------------------------------------------


class AttackChainOptimizerInput(BaseModel):
    """AttackChainOptimizer 输入 wrapper。

    Args:
        case_id:         案件 ID
        run_id:          运行快照 ID（写入产物元信息）
        owner_party_id:  生成方当事人 ID（原告或被告）
        issue_tree:      P0.1 产物（issues 已按 outcome_impact 排序并富化）
        evidence_index:  完整证据索引
    """
    case_id: str = Field(..., min_length=1)
    run_id: str = Field(..., min_length=1)
    owner_party_id: str = Field(..., min_length=1)
    issue_tree: IssueTree
    evidence_index: EvidenceIndex

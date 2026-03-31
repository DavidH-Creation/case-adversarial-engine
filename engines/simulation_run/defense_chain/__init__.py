"""
defense_chain — 原告方防御链优化模块（P2）。
Plaintiff Defense Chain optimization module (P2).

工作流阶段：simulation_run
职责：基于争点和证据，使用 LLM 生成最优防御策略链。
"""

from .models import DefensePoint, PlaintiffDefenseChain
from .optimizer import DefenseChainOptimizer
from .schemas import DefenseChainInput, DefenseChainResult

__all__ = [
    "DefenseChainOptimizer",
    "PlaintiffDefenseChain",
    "DefensePoint",
    "DefenseChainInput",
    "DefenseChainResult",
]

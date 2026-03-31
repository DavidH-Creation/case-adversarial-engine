"""
对抗性辩论引擎 — 原告/被告代理人 + 轮次编排器 + 语义总结层。
Adversarial engine — plaintiff/defendant party agents + round orchestrator + semantic summary.
"""

from .round_engine import RoundEngine
from .schemas import AdversarialResult, AdversarialSummary, RoundConfig, RoundState
from .summarizer import AdversarialSummarizer

__all__ = [
    "RoundEngine",
    "RoundConfig",
    "RoundState",
    "AdversarialResult",
    "AdversarialSummary",
    "AdversarialSummarizer",
]

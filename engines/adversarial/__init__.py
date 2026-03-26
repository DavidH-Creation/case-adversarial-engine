"""
对抗性辩论引擎 — 原告/被告代理人 + 轮次编排器。
Adversarial engine — plaintiff/defendant party agents + round orchestrator.
"""
from .round_engine import RoundEngine
from .schemas import AdversarialResult, RoundConfig, RoundState

__all__ = ["RoundEngine", "RoundConfig", "RoundState", "AdversarialResult"]

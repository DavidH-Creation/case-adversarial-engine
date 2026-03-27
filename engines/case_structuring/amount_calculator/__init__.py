"""
amount_calculator — 金额/诉请一致性硬校验模块。
Amount/claim consistency hard validation module.

公共 API / Public API:
    AmountCalculator:         主计算器类（纯规则层，不调用 LLM）
    AmountCalculatorInput:    输入 wrapper
    AmountClaimDescriptor:    诉请金额描述符
"""

from .calculator import AmountCalculator
from .schemas import AmountCalculatorInput, AmountClaimDescriptor

__all__ = [
    "AmountCalculator",
    "AmountCalculatorInput",
    "AmountClaimDescriptor",
]

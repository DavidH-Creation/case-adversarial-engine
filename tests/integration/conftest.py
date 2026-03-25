"""
集成测试共享 fixtures 和 Mock 工具。
Shared fixtures and mock utilities for integration tests.
"""

from __future__ import annotations

import pytest

from engines.case_structuring.evidence_indexer.schemas import RawMaterial


# ---------------------------------------------------------------------------
# Mock LLM Clients
# ---------------------------------------------------------------------------


class MockLLMClient:
    """返回固定响应的 mock LLM 客户端。
    Mock LLM client returning a fixed response string.

    fail_times: 前 N 次调用抛出 RuntimeError，之后恢复正常。
    """

    def __init__(self, response: str, fail_times: int = 0) -> None:
        self._response = response
        self._fail_times = fail_times
        self.call_count = 0
        self.last_system: str | None = None
        self.last_user: str | None = None

    async def create_message(self, system: str, user: str, **kwargs) -> str:
        self.call_count += 1
        self.last_system = system
        self.last_user = user
        if self._fail_times > 0:
            self._fail_times -= 1
            raise RuntimeError(
                f"Simulated LLM failure (call {self.call_count})"
            )
        return self._response


class SequentialMockLLMClient:
    """按顺序返回不同响应的 mock LLM 客户端（用于多轮追问测试）。
    Mock LLM client returning responses sequentially (for multi-turn tests).

    超过预设数量后重复最后一条响应。
    Returns the last response after the preset list is exhausted.
    """

    def __init__(self, responses: list[str]) -> None:
        self._responses = responses
        self._index = 0
        self.call_count = 0
        self.last_system: str | None = None
        self.last_user: str | None = None

    async def create_message(self, system: str, user: str, **kwargs) -> str:
        self.call_count += 1
        self.last_system = system
        self.last_user = user
        if self._index < len(self._responses):
            response = self._responses[self._index]
            self._index += 1
            return response
        return self._responses[-1]


# ---------------------------------------------------------------------------
# 共享常量 / Shared constants
# ---------------------------------------------------------------------------

CASE_ID = "case-integ-001"
CASE_SLUG = "integ-001"
WORKSPACE_ID = "workspace-integ-001"

# ---------------------------------------------------------------------------
# 共享 fixtures / Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_materials() -> list[RawMaterial]:
    """两份原始案件材料（借条 + 转账回单）。"""
    return [
        RawMaterial(
            source_id="mat-integ-001",
            text=(
                "借条。今借到张某人民币伍拾万元整，借款期限一年，"
                "利率按年利率6%计算。借款人：李某，2024年1月15日。"
            ),
            metadata={"document_type": "promissory_note", "date": "2024-01-15"},
        ),
        RawMaterial(
            source_id="mat-integ-002",
            text=(
                "中国工商银行电子回单，转账金额：500,000.00元，"
                "转入账户：李某，转账日期：2024年1月15日。"
            ),
            metadata={"document_type": "bank_transfer_receipt", "date": "2024-01-15"},
        ),
    ]


@pytest.fixture
def sample_claims() -> list[dict]:
    """两份诉请（归还本金 + 支付利息）。"""
    return [
        {
            "claim_id": "claim-integ-001-01",
            "case_id": CASE_ID,
            "title": "归还借款本金50万元",
            "description": "请求被告归还借款本金人民币500,000元",
            "related_evidence_ids": [],
        },
        {
            "claim_id": "claim-integ-001-02",
            "case_id": CASE_ID,
            "title": "支付逾期利息",
            "description": "请求被告支付自逾期之日起至实际还款日止的逾期利息",
            "related_evidence_ids": [],
        },
    ]


@pytest.fixture
def sample_defenses() -> list[dict]:
    """一份抗辩（已部分归还）。"""
    return [
        {
            "defense_id": "defense-integ-001-01",
            "case_id": CASE_ID,
            "title": "已归还20万元",
            "description": "被告主张已通过银行转账归还借款本金200,000元",
            "against_claim_id": "claim-integ-001-01",
            "related_evidence_ids": [],
        },
    ]

# engines/shared/tests/test_models_bugfix.py
"""v1.1 bugfix 新增模型的单元测试。"""
from __future__ import annotations

from decimal import Decimal

import pytest

from engines.shared.models import (
    ContractValidity,
    LitigationHistory,
    Party,
    AmountConsistencyCheck,
    AmountConflict,
    InterestRecalculation,
)


class TestContractValidity:
    def test_enum_values(self):
        assert ContractValidity.valid == "valid"
        assert ContractValidity.disputed == "disputed"
        assert ContractValidity.invalid == "invalid"


class TestLitigationHistory:
    def test_defaults(self):
        hist = LitigationHistory()
        assert hist.lending_case_count == 0
        assert hist.distinct_borrower_count == 0
        assert hist.total_lending_amount == Decimal("0")
        assert hist.time_span_months == 0
        assert hist.uniform_contract_detected is False

    def test_custom_values(self):
        hist = LitigationHistory(
            lending_case_count=8,
            distinct_borrower_count=8,
            total_lending_amount=Decimal("2850000"),
            time_span_months=24,
            uniform_contract_detected=True,
        )
        assert hist.lending_case_count == 8
        assert hist.uniform_contract_detected is True


class TestPartyLitigationHistory:
    def test_party_default_no_history(self):
        p = Party(
            party_id="p1", case_id="c1", name="A",
            party_type="natural_person", role_code="plaintiff_agent", side="plaintiff",
        )
        assert p.litigation_history is None

    def test_party_with_history(self):
        hist = LitigationHistory(lending_case_count=5, distinct_borrower_count=5)
        p = Party(
            party_id="p1", case_id="c1", name="A",
            party_type="natural_person", role_code="plaintiff_agent", side="plaintiff",
            litigation_history=hist,
        )
        assert p.litigation_history.lending_case_count == 5


class TestAmountConsistencyCheckExtensions:
    def _base_check(self, **overrides):
        defaults = dict(
            principal_base_unique=True,
            all_repayments_attributed=True,
            text_table_amount_consistent=True,
            duplicate_interest_penalty_claim=False,
            claim_total_reconstructable=True,
            verdict_block_active=False,
            claim_delivery_ratio_normal=True,
        )
        defaults.update(overrides)
        return AmountConsistencyCheck(**defaults)

    def test_new_field_default_true(self):
        check = self._base_check()
        assert check.claim_delivery_ratio_normal is True

    def test_new_field_false(self):
        check = self._base_check(claim_delivery_ratio_normal=False)
        assert check.claim_delivery_ratio_normal is False


class TestInterestRecalculation:
    def test_creation(self):
        ir = InterestRecalculation(
            original_rate=Decimal("0.24"),
            effective_rate=Decimal("0.0385"),
            rate_basis="LPR",
            contract_validity=ContractValidity.invalid,
            original_interest_amount=Decimal("120000"),
            recalculated_interest_amount=Decimal("19250"),
            delta=Decimal("100750"),
        )
        assert ir.effective_rate == Decimal("0.0385")
        assert ir.contract_validity == ContractValidity.invalid

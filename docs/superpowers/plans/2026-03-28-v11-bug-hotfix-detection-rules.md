# v1.1 Bug Hotfix: Detection Rules Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix 3 remaining v1.1 known bugs: professional lender detection (CRED-07), false litigation warning (amount rule #6), and interest recalculation on invalid contracts (amount rule #7).

**Architecture:** All 3 fixes are pure deterministic rules (zero LLM). Professional lender detection extends CredibilityScorer with CRED-07. False litigation warning and interest recalculation extend AmountCalculator with rules #6 and #7. A shared `RuleThresholds` config model centralizes all configurable thresholds.

**Tech Stack:** Python 3.11+, Pydantic v2, pytest

---

## File Structure

| File | Responsibility |
|------|---------------|
| `engines/shared/models.py` | Add `ContractValidity` enum, `LitigationHistory` model, extend `Party`, extend `AmountConsistencyCheck`, extend `AmountCalculationReport` |
| `engines/shared/rule_config.py` | **NEW** — `RuleThresholds` Pydantic model with all configurable thresholds |
| `engines/case_structuring/amount_calculator/schemas.py` | Extend `AmountCalculatorInput` with contract validity + interest rate fields |
| `engines/case_structuring/amount_calculator/calculator.py` | Add rule #6 (claim/delivery ratio) + rule #7 (interest recalculation) |
| `engines/simulation_run/credibility_scorer/schemas.py` | Extend `CredibilityScorerInput` with `party_list` field |
| `engines/simulation_run/credibility_scorer/scorer.py` | Add CRED-07 (professional lender detection) |
| `engines/shared/rule_config.py` | Test: `engines/shared/tests/test_rule_config.py` |
| `engines/case_structuring/amount_calculator/tests/test_calculator.py` | Extend with rule #6 and #7 tests |
| `engines/simulation_run/credibility_scorer/tests/test_scorer.py` | Extend with CRED-07 tests |

---

### Task 1: RuleThresholds Config Model

**Files:**
- Create: `engines/shared/rule_config.py`
- Create: `engines/shared/tests/test_rule_config.py`

- [ ] **Step 1: Write the failing test**

```python
# engines/shared/tests/test_rule_config.py
"""RuleThresholds 单元测试。"""
from decimal import Decimal
import pytest
from engines.shared.rule_config import RuleThresholds


class TestRuleThresholdsDefaults:
    def test_default_values(self):
        cfg = RuleThresholds()
        assert cfg.prof_lender_min_cases == 3
        assert cfg.prof_lender_min_borrowers == 3
        assert cfg.prof_lender_max_span_months == 24
        assert cfg.false_litigation_ratio == Decimal("2.0")
        assert cfg.lpr_multiplier_cap == Decimal("4.0")

    def test_custom_overrides(self):
        cfg = RuleThresholds(prof_lender_min_cases=5, false_litigation_ratio=Decimal("3.0"))
        assert cfg.prof_lender_min_cases == 5
        assert cfg.false_litigation_ratio == Decimal("3.0")
        # other defaults unchanged
        assert cfg.prof_lender_min_borrowers == 3

    def test_validation_min_cases_positive(self):
        with pytest.raises(ValueError):
            RuleThresholds(prof_lender_min_cases=0)

    def test_validation_ratio_positive(self):
        with pytest.raises(ValueError):
            RuleThresholds(false_litigation_ratio=Decimal("0"))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd C:\Users\david\dev\case-adversarial-engine && python -m pytest engines/shared/tests/test_rule_config.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'engines.shared.rule_config'`

- [ ] **Step 3: Write minimal implementation**

```python
# engines/shared/rule_config.py
"""
集中式规则阈值配置 — 所有确定性规则的可调参数。
Centralized rule thresholds — configurable parameters for all deterministic rules.
"""
from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, Field


class RuleThresholds(BaseModel):
    """规则引擎阈值配置。构造 Calculator/Scorer 时注入，测试时可覆盖。

    Args:
        prof_lender_min_cases:      职业放贷人：最低诉讼案件数
        prof_lender_min_borrowers:  职业放贷人：最低不同借款人数
        prof_lender_max_span_months: 职业放贷人：统计时间窗口（月）
        false_litigation_ratio:     虚假诉讼预警：起诉金额/可核实交付 比值上限
        lpr_multiplier_cap:         合同无效时 LPR 倍数上限
    """
    prof_lender_min_cases: int = Field(default=3, gt=0)
    prof_lender_min_borrowers: int = Field(default=3, gt=0)
    prof_lender_max_span_months: int = Field(default=24, gt=0)
    false_litigation_ratio: Decimal = Field(default=Decimal("2.0"), gt=0)
    lpr_multiplier_cap: Decimal = Field(default=Decimal("4.0"), gt=0)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd C:\Users\david\dev\case-adversarial-engine && python -m pytest engines/shared/tests/test_rule_config.py -v`
Expected: 4 PASSED

- [ ] **Step 5: Commit**

```bash
git add engines/shared/rule_config.py engines/shared/tests/test_rule_config.py
git commit -m "feat: add RuleThresholds centralized config model"
```

---

### Task 2: Models — ContractValidity, LitigationHistory, AmountConsistencyCheck extensions

**Files:**
- Modify: `engines/shared/models.py`
- Test: `engines/shared/tests/test_models_bugfix.py` (NEW)

- [ ] **Step 1: Write the failing tests**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd C:\Users\david\dev\case-adversarial-engine && python -m pytest engines/shared/tests/test_models_bugfix.py -v`
Expected: FAIL — `ImportError: cannot import name 'ContractValidity'`

- [ ] **Step 3: Add models to `engines/shared/models.py`**

Add after `LegalityRisk` enum (around line 294):

```python
class ContractValidity(str, Enum):
    """合同效力状态 — 影响利息计算标准。"""
    valid = "valid"
    disputed = "disputed"
    invalid = "invalid"
```

Add **before** the `Party` class (around line 445, so `Party` can reference it without forward-ref issues):

```python
class LitigationHistory(BaseModel):
    """当事人近期放贷诉讼统计 — 职业放贷人检测输入。"""
    lending_case_count: int = Field(default=0, ge=0, description="近期放贷诉讼数")
    distinct_borrower_count: int = Field(default=0, ge=0, description="不同借款人数")
    total_lending_amount: Decimal = Field(default=Decimal("0"), ge=0, description="累计放贷金额")
    time_span_months: int = Field(default=0, ge=0, description="统计时间跨度（月）")
    uniform_contract_detected: bool = Field(default=False, description="借条格式是否雷同")
```

Add `litigation_history` field to `Party`:

```python
    # v1.5 bugfix: 职业放贷人检测扩展字段
    litigation_history: Optional[LitigationHistory] = None
```

Add after `AmountCalculationReport` (around line 936):

```python
class InterestRecalculation(BaseModel):
    """利息重算记录 — 合同无效时的利率切换结果。"""
    original_rate: Decimal = Field(..., description="原合同约定利率")
    effective_rate: Decimal = Field(..., description="重算后适用利率")
    rate_basis: str = Field(..., min_length=1, description="利率依据（如 LPR、LPR*4）")
    contract_validity: ContractValidity
    original_interest_amount: Decimal = Field(..., description="原利息金额")
    recalculated_interest_amount: Decimal = Field(..., description="重算后利息金额")
    delta: Decimal = Field(..., description="利息差额 = original - recalculated")
```

Add `claim_delivery_ratio_normal` to `AmountConsistencyCheck`:

```python
    claim_delivery_ratio_normal: bool = Field(
        default=True,
        description="起诉金额与可核实交付金额比值是否正常（ratio <= 阈值）",
    )
```

Add `interest_recalculation` to `AmountCalculationReport`:

```python
    interest_recalculation: Optional[InterestRecalculation] = Field(
        default=None, description="合同无效/争议时的利息重算记录"
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd C:\Users\david\dev\case-adversarial-engine && python -m pytest engines/shared/tests/test_models_bugfix.py -v`
Expected: 7 PASSED

- [ ] **Step 5: Run existing tests to ensure no regressions**

Run: `cd C:\Users\david\dev\case-adversarial-engine && python -m pytest engines/shared/tests/ -v --tb=short`
Expected: All existing tests PASS (new fields have defaults, backward compatible)

- [ ] **Step 6: Commit**

```bash
git add engines/shared/models.py engines/shared/tests/test_models_bugfix.py
git commit -m "feat: add ContractValidity, LitigationHistory, InterestRecalculation models + extend Party/AmountConsistencyCheck"
```

---

### Task 3: CRED-07 — Professional Lender Detection

**Files:**
- Modify: `engines/simulation_run/credibility_scorer/schemas.py`
- Modify: `engines/simulation_run/credibility_scorer/scorer.py`
- Modify: `engines/simulation_run/credibility_scorer/tests/test_scorer.py`

- [ ] **Step 1: Write the failing tests**

Append to `engines/simulation_run/credibility_scorer/tests/test_scorer.py`:

```python
from engines.shared.models import LitigationHistory, Party
from engines.shared.rule_config import RuleThresholds

# ---------------------------------------------------------------------------
# CRED-07: 职业放贷人检测
# ---------------------------------------------------------------------------

class TestCRED07ProfessionalLender:
    """CRED-07: 原告放贷频次达标 → 扣分 -25。"""

    @staticmethod
    def _make_party(
        case_count: int = 0,
        borrowers: int = 0,
        months: int = 24,
        uniform: bool = False,
    ) -> Party:
        return Party(
            party_id="plaintiff-1",
            case_id="case1",
            name="郭某",
            party_type="natural_person",
            role_code="plaintiff_agent",
            side="plaintiff",
            litigation_history=LitigationHistory(
                lending_case_count=case_count,
                distinct_borrower_count=borrowers,
                time_span_months=months,
                uniform_contract_detected=uniform,
            ),
        )

    def test_triggers_when_all_thresholds_met(self):
        party = self._make_party(case_count=8, borrowers=8, months=24, uniform=True)
        inp = CredibilityScorerInput(
            case_id="case1",
            run_id="run1",
            amount_report=make_amount_report(),
            party_list=[party],
        )
        scorer = CredibilityScorer(thresholds=RuleThresholds())
        result = scorer.score(inp)
        cred07 = [d for d in result.deductions if d.rule_id == "CRED-07"]
        assert len(cred07) == 1
        assert cred07[0].deduction_points == -25

    def test_not_triggered_below_case_threshold(self):
        party = self._make_party(case_count=2, borrowers=5, months=24)
        inp = CredibilityScorerInput(
            case_id="case1",
            run_id="run1",
            amount_report=make_amount_report(),
            party_list=[party],
        )
        scorer = CredibilityScorer(thresholds=RuleThresholds())
        result = scorer.score(inp)
        cred07 = [d for d in result.deductions if d.rule_id == "CRED-07"]
        assert len(cred07) == 0

    def test_not_triggered_below_borrower_threshold(self):
        party = self._make_party(case_count=5, borrowers=2, months=24)
        inp = CredibilityScorerInput(
            case_id="case1",
            run_id="run1",
            amount_report=make_amount_report(),
            party_list=[party],
        )
        scorer = CredibilityScorer(thresholds=RuleThresholds())
        result = scorer.score(inp)
        cred07 = [d for d in result.deductions if d.rule_id == "CRED-07"]
        assert len(cred07) == 0

    def test_not_triggered_without_litigation_history(self):
        party = Party(
            party_id="p1", case_id="case1", name="A",
            party_type="natural_person", role_code="plaintiff_agent", side="plaintiff",
        )
        inp = CredibilityScorerInput(
            case_id="case1",
            run_id="run1",
            amount_report=make_amount_report(),
            party_list=[party],
        )
        scorer = CredibilityScorer(thresholds=RuleThresholds())
        result = scorer.score(inp)
        cred07 = [d for d in result.deductions if d.rule_id == "CRED-07"]
        assert len(cred07) == 0

    def test_custom_thresholds(self):
        party = self._make_party(case_count=5, borrowers=5, months=24)
        cfg = RuleThresholds(prof_lender_min_cases=5, prof_lender_min_borrowers=5)
        inp = CredibilityScorerInput(
            case_id="case1",
            run_id="run1",
            amount_report=make_amount_report(),
            party_list=[party],
        )
        scorer = CredibilityScorer(thresholds=cfg)
        result = scorer.score(inp)
        cred07 = [d for d in result.deductions if d.rule_id == "CRED-07"]
        assert len(cred07) == 1

    def test_empty_party_list(self):
        inp = CredibilityScorerInput(
            case_id="case1",
            run_id="run1",
            amount_report=make_amount_report(),
            party_list=[],
        )
        scorer = CredibilityScorer(thresholds=RuleThresholds())
        result = scorer.score(inp)
        cred07 = [d for d in result.deductions if d.rule_id == "CRED-07"]
        assert len(cred07) == 0

    def test_score_reduction_correct(self):
        party = self._make_party(case_count=8, borrowers=8, months=24, uniform=True)
        inp = CredibilityScorerInput(
            case_id="case1",
            run_id="run1",
            amount_report=make_amount_report(),
            party_list=[party],
        )
        scorer = CredibilityScorer(thresholds=RuleThresholds())
        result = scorer.score(inp)
        assert result.final_score == 100 - 25
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd C:\Users\david\dev\case-adversarial-engine && python -m pytest engines/simulation_run/credibility_scorer/tests/test_scorer.py::TestCRED07ProfessionalLender -v`
Expected: FAIL — CredibilityScorerInput doesn't accept `party_list`, CredibilityScorer doesn't accept `thresholds`

- [ ] **Step 3: Extend schemas.py — add `party_list`**

In `engines/simulation_run/credibility_scorer/schemas.py`, add `Party` import and field:

```python
from engines.shared.models import (  # noqa: F401
    AmountCalculationReport,
    CredibilityDeduction,
    CredibilityScorecard,
    Evidence,
    Issue,
    Party,
)

class CredibilityScorerInput(BaseModel):
    # ... existing fields ...
    party_list: list[Party] = Field(
        default_factory=list, description="当事人列表（用于 CRED-07 职业放贷人检测）"
    )
```

- [ ] **Step 4: Extend scorer.py — add CRED-07 + thresholds injection**

Add to `_RULES` dict:
```python
"CRED-07": ("原告构成职业放贷人（放贷频次、对象达标）", -25),
```

Modify `CredibilityScorer.__init__`:
```python
from engines.shared.rule_config import RuleThresholds

class CredibilityScorer:
    def __init__(self, thresholds: RuleThresholds | None = None):
        self._thresholds = thresholds or RuleThresholds()
```

Add CRED-07 call in `score()` method after CRED-06:
```python
        cred07 = self._check_cred07(inp.party_list)
        if cred07:
            deductions.append(cred07)
```

Add CRED-07 check method:
```python
    def _check_cred07(self, party_list: list[Party]) -> CredibilityDeduction | None:
        """CRED-07: 原告构成职业放贷人。

        触发条件：存在 Party 的 litigation_history 满足以下全部条件：
        - lending_case_count >= prof_lender_min_cases
        - distinct_borrower_count >= prof_lender_min_borrowers
        - time_span_months <= prof_lender_max_span_months
        """
        t = self._thresholds
        for party in party_list:
            hist = party.litigation_history
            if hist is None:
                continue
            if (
                hist.lending_case_count >= t.prof_lender_min_cases
                and hist.distinct_borrower_count >= t.prof_lender_min_borrowers
                and hist.time_span_months <= t.prof_lender_max_span_months
            ):
                desc, pts = _RULES["CRED-07"]
                return CredibilityDeduction(
                    deduction_id=str(uuid.uuid4()),
                    rule_id="CRED-07",
                    rule_description=desc,
                    deduction_points=pts,
                )
        return None
```

- [ ] **Step 5: Run CRED-07 tests to verify they pass**

Run: `cd C:\Users\david\dev\case-adversarial-engine && python -m pytest engines/simulation_run/credibility_scorer/tests/test_scorer.py::TestCRED07ProfessionalLender -v`
Expected: 7 PASSED

- [ ] **Step 6: Run ALL credibility scorer tests to ensure no regressions**

Run: `cd C:\Users\david\dev\case-adversarial-engine && python -m pytest engines/simulation_run/credibility_scorer/tests/test_scorer.py -v`
Expected: All existing CRED-01~06 tests + new CRED-07 tests PASS.

Note: existing tests construct `CredibilityScorer()` without arguments — this must still work (thresholds defaults to `RuleThresholds()`).

- [ ] **Step 7: Commit**

```bash
git add engines/simulation_run/credibility_scorer/schemas.py engines/simulation_run/credibility_scorer/scorer.py engines/simulation_run/credibility_scorer/tests/test_scorer.py
git commit -m "feat(CRED-07): add professional lender detection rule with configurable thresholds"
```

---

### Task 4: AmountCalculator Rule #6 — False Litigation Ratio Warning

**Files:**
- Modify: `engines/case_structuring/amount_calculator/calculator.py`
- Modify: `engines/case_structuring/amount_calculator/tests/test_calculator.py`

- [ ] **Step 1: Write the failing tests**

Append to `engines/case_structuring/amount_calculator/tests/test_calculator.py`:

```python
from engines.shared.rule_config import RuleThresholds

# ---------------------------------------------------------------------------
# Rule #6: 起诉金额/可核实交付比值 (claim_delivery_ratio_normal)
# ---------------------------------------------------------------------------

class TestRule6ClaimDeliveryRatio:
    """rule #6: total_claimed / total_principal_loans > threshold → 预警。"""

    def test_ratio_normal_within_threshold(self):
        """claimed 50000 / delivered 50000 = 1.0 → normal。"""
        inp = _base_input()
        calc = AmountCalculator(thresholds=RuleThresholds())
        report = calc.calculate(inp)
        assert report.consistency_check_result.claim_delivery_ratio_normal is True

    def test_ratio_exceeds_threshold(self):
        """claimed 150000 / delivered 50000 = 3.0 > 2.0 → abnormal。"""
        inp = _base_input(
            claim_entries=[_claim("claim-principal-001", ClaimType.principal, "150000")],
        )
        calc = AmountCalculator(thresholds=RuleThresholds())
        report = calc.calculate(inp)
        assert report.consistency_check_result.claim_delivery_ratio_normal is False

    def test_ratio_exactly_at_threshold(self):
        """claimed 100000 / delivered 50000 = 2.0 → still normal (<=)。"""
        inp = _base_input(
            claim_entries=[_claim("claim-principal-001", ClaimType.principal, "100000")],
        )
        calc = AmountCalculator(thresholds=RuleThresholds())
        report = calc.calculate(inp)
        assert report.consistency_check_result.claim_delivery_ratio_normal is True

    def test_custom_threshold(self):
        """custom threshold 1.5: claimed 80000 / delivered 50000 = 1.6 > 1.5 → abnormal。"""
        inp = _base_input(
            claim_entries=[_claim("claim-principal-001", ClaimType.principal, "80000")],
        )
        calc = AmountCalculator(thresholds=RuleThresholds(false_litigation_ratio=Decimal("1.5")))
        report = calc.calculate(inp)
        assert report.consistency_check_result.claim_delivery_ratio_normal is False

    def test_generates_risk_flag_conflict(self):
        """ratio > threshold → generates AmountConflict。"""
        inp = _base_input(
            claim_entries=[_claim("claim-principal-001", ClaimType.principal, "150000")],
        )
        calc = AmountCalculator(thresholds=RuleThresholds())
        report = calc.calculate(inp)
        ratio_conflicts = [
            c for c in report.consistency_check_result.unresolved_conflicts
            if "虚假诉讼" in c.conflict_description or "ratio" in c.conflict_description.lower()
        ]
        assert len(ratio_conflicts) >= 1

    def test_no_principal_loans_skips_check(self):
        """No principal_base_contribution=True loans → defaults to True (skip)。"""
        inp = _base_input(
            loan_transactions=[_loan("loan-001", "50000", is_principal=False)],
            claim_entries=[_claim("claim-interest-001", ClaimType.interest, "10000")],
        )
        calc = AmountCalculator(thresholds=RuleThresholds())
        report = calc.calculate(inp)
        assert report.consistency_check_result.claim_delivery_ratio_normal is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd C:\Users\david\dev\case-adversarial-engine && python -m pytest engines/case_structuring/amount_calculator/tests/test_calculator.py::TestRule6ClaimDeliveryRatio -v`
Expected: FAIL — `AmountCalculator` doesn't accept `thresholds`, `AmountConsistencyCheck` has no `claim_delivery_ratio_normal`

- [ ] **Step 3: Implement rule #6 in calculator.py**

Add thresholds injection to `AmountCalculator.__init__`:
```python
from engines.shared.rule_config import RuleThresholds

class AmountCalculator:
    def __init__(self, thresholds: RuleThresholds | None = None):
        self._thresholds = thresholds or RuleThresholds()
```

Add rule #6 check method:
```python
    def _check_claim_delivery_ratio(
        self,
        claim_entries,
        loan_transactions: list[LoanTransaction],
    ) -> bool:
        """规则 #6: 起诉总额 / 可核实交付总额 <= 阈值时返回 True。
        若无 principal_base_contribution 放款，跳过检查返回 True。
        """
        delivered = self._sum_principal_loans(loan_transactions)
        if delivered == Decimal("0"):
            return True
        total_claimed = sum(c.claimed_amount for c in claim_entries)
        ratio = total_claimed / delivered
        return ratio <= self._thresholds.false_litigation_ratio
```

Call it in `calculate()` after existing rules (after line 75), and generate the ratio conflict **outside** `_generate_conflicts` (appending to the conflicts list after line 82):

```python
        # --- 新增 rule #6 ---
        claim_delivery_ratio_normal = self._check_claim_delivery_ratio(
            inp.claim_entries, inp.loan_transactions
        )

        # 3. 生成冲突列表 (existing code at line 78-82)
        conflicts = list(self._generate_conflicts(
            claim_table=claim_table,
            disputed_attributions=inp.disputed_amount_attributions,
            loan_transactions=inp.loan_transactions,
        ))

        # 来源 3：起诉金额/可核实交付比值异常（rule #6 — 在 _generate_conflicts 之外追加）
        if not claim_delivery_ratio_normal:
            delivered = self._sum_principal_loans(inp.loan_transactions)
            total_claimed = sum(c.claimed_amount for c in inp.claim_entries)
            conflicts.append(AmountConflict(
                conflict_id=f"conflict-{len(conflicts) + 1:03d}",
                conflict_description=(
                    f"【虚假诉讼预警】起诉总额 {total_claimed} / 可核实交付 {delivered}"
                    f" = {total_claimed / delivered:.2f}，超出预警阈值 {self._thresholds.false_litigation_ratio}"
                ),
                amount_a=total_claimed,
                amount_b=delivered,
                source_a_evidence_id="",
                source_b_evidence_id="",
                resolution_note="",
            ))
```

Pass `claim_delivery_ratio_normal` into `AmountConsistencyCheck` constructor (line 87-95):

```python
        consistency = AmountConsistencyCheck(
            principal_base_unique=principal_base_unique,
            all_repayments_attributed=all_attributed,
            text_table_amount_consistent=text_table_consistent,
            duplicate_interest_penalty_claim=duplicate_claim,
            claim_total_reconstructable=total_reconstructable,
            unresolved_conflicts=conflicts,
            verdict_block_active=len(conflicts) > 0,
            claim_delivery_ratio_normal=claim_delivery_ratio_normal,
        )
```

- [ ] **Step 4: Run rule #6 tests**

Run: `cd C:\Users\david\dev\case-adversarial-engine && python -m pytest engines/case_structuring/amount_calculator/tests/test_calculator.py::TestRule6ClaimDeliveryRatio -v`
Expected: 6 PASSED

- [ ] **Step 5: Run all calculator tests for regressions**

Run: `cd C:\Users\david\dev\case-adversarial-engine && python -m pytest engines/case_structuring/amount_calculator/tests/test_calculator.py -v`
Expected: All existing + new tests PASS

- [ ] **Step 6: Commit**

```bash
git add engines/case_structuring/amount_calculator/calculator.py engines/case_structuring/amount_calculator/tests/test_calculator.py
git commit -m "feat(amount-rule-6): add false litigation ratio warning rule"
```

---

### Task 5: AmountCalculator Rule #7 — Interest Recalculation on Invalid Contract

**Files:**
- Modify: `engines/case_structuring/amount_calculator/schemas.py`
- Modify: `engines/case_structuring/amount_calculator/calculator.py`
- Modify: `engines/case_structuring/amount_calculator/tests/test_calculator.py`

- [ ] **Step 1: Write the failing tests**

Append to `engines/case_structuring/amount_calculator/tests/test_calculator.py`:

```python
from engines.shared.models import ContractValidity, InterestRecalculation

# ---------------------------------------------------------------------------
# Rule #7: 合同无效后利息重算 (interest recalculation)
# ---------------------------------------------------------------------------

class TestRule7InterestRecalculation:
    """rule #7: contract invalid → interest recalculated at LPR。"""

    def test_valid_contract_no_recalculation(self):
        inp = _base_input()
        calc = AmountCalculator(thresholds=RuleThresholds())
        report = calc.calculate(inp)
        assert report.interest_recalculation is None

    def test_invalid_contract_forces_lpr(self):
        inp = _base_input(
            contract_validity=ContractValidity.invalid,
            contractual_interest_rate=Decimal("0.24"),
            lpr_rate=Decimal("0.0385"),
        )
        calc = AmountCalculator(thresholds=RuleThresholds())
        report = calc.calculate(inp)
        assert report.interest_recalculation is not None
        ir = report.interest_recalculation
        assert ir.effective_rate == Decimal("0.0385")
        assert ir.rate_basis == "LPR"
        assert ir.contract_validity == ContractValidity.invalid

    def test_disputed_contract_caps_at_lpr_x4(self):
        inp = _base_input(
            contract_validity=ContractValidity.disputed,
            contractual_interest_rate=Decimal("0.24"),
            lpr_rate=Decimal("0.0385"),
        )
        calc = AmountCalculator(thresholds=RuleThresholds())
        report = calc.calculate(inp)
        assert report.interest_recalculation is not None
        ir = report.interest_recalculation
        expected_cap = Decimal("0.0385") * Decimal("4.0")
        assert ir.effective_rate == min(Decimal("0.24"), expected_cap)
        assert ir.rate_basis == "LPR*4"

    def test_disputed_rate_already_below_cap(self):
        inp = _base_input(
            contract_validity=ContractValidity.disputed,
            contractual_interest_rate=Decimal("0.10"),
            lpr_rate=Decimal("0.0385"),
        )
        calc = AmountCalculator(thresholds=RuleThresholds())
        report = calc.calculate(inp)
        ir = report.interest_recalculation
        assert ir.effective_rate == Decimal("0.10")  # below cap, no reduction

    def test_interest_delta_calculated(self):
        inp = _base_input(
            contract_validity=ContractValidity.invalid,
            contractual_interest_rate=Decimal("0.24"),
            lpr_rate=Decimal("0.0385"),
        )
        calc = AmountCalculator(thresholds=RuleThresholds())
        report = calc.calculate(inp)
        ir = report.interest_recalculation
        # principal_base = 50000, interest period = conceptual
        # original_interest = principal * original_rate
        # recalculated_interest = principal * effective_rate
        assert ir.delta == ir.original_interest_amount - ir.recalculated_interest_amount
        assert ir.delta > 0  # 24% > 3.85%, so delta must be positive

    def test_no_recalculation_without_interest_rate(self):
        """contract_validity=invalid but no contractual_interest_rate → skip。"""
        inp = _base_input(
            contract_validity=ContractValidity.invalid,
            lpr_rate=Decimal("0.0385"),
        )
        calc = AmountCalculator(thresholds=RuleThresholds())
        report = calc.calculate(inp)
        assert report.interest_recalculation is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd C:\Users\david\dev\case-adversarial-engine && python -m pytest engines/case_structuring/amount_calculator/tests/test_calculator.py::TestRule7InterestRecalculation -v`
Expected: FAIL — AmountCalculatorInput has no `contract_validity`, `lpr_rate`, `contractual_interest_rate`

- [ ] **Step 3: Extend schemas.py with contract fields**

Add `ContractValidity` to the existing import block in `schemas.py`:
```python
from engines.shared.models import (  # noqa: F401
    AmountCalculationReport,
    AmountConsistencyCheck,
    AmountConflict,
    ClaimCalculationEntry,
    ClaimType,
    ContractValidity,          # ← 新增
    DisputedAmountAttribution,
    DisputeResolutionStatus,
    LoanTransaction,
    RepaymentAttribution,
    RepaymentTransaction,
)
```

Append these fields to `AmountCalculatorInput` (use `X | None` syntax since `from __future__ import annotations` is active):
```python
class AmountCalculatorInput(BaseModel):
    # ... existing fields ...
    contract_validity: ContractValidity = Field(
        default=ContractValidity.valid,
        description="合同效力状态；非 valid 时触发利息重算",
    )
    contractual_interest_rate: Decimal | None = Field(
        default=None, ge=0,
        description="合同约定年利率；None 时跳过利息重算",
    )
    lpr_rate: Decimal | None = Field(
        default=None, gt=0,
        description="当期 LPR 利率（由调用方传入）；合同无效时必需",
    )
```

- [ ] **Step 4: Implement rule #7 in calculator.py**

Add to `AmountCalculator`:
```python
    def _recalculate_interest(
        self, inp: AmountCalculatorInput, principal_base: Decimal,
    ) -> InterestRecalculation | None:
        """规则 #7: 合同无效/争议时，利息按 LPR 重算。

        - invalid: 强制 LPR
        - disputed: min(contractual_rate, LPR * lpr_multiplier_cap)
        - valid 或缺少利率输入: 返回 None
        """
        if inp.contract_validity == ContractValidity.valid:
            return None
        if inp.contractual_interest_rate is None or inp.lpr_rate is None:
            return None

        original_rate = inp.contractual_interest_rate
        lpr = inp.lpr_rate

        if inp.contract_validity == ContractValidity.invalid:
            effective_rate = lpr
            basis = "LPR"
        else:  # disputed
            cap = lpr * self._thresholds.lpr_multiplier_cap
            effective_rate = min(original_rate, cap)
            basis = "LPR*4" if effective_rate == cap else f"合同约定（{original_rate}，未超上限）"

        original_interest = principal_base * original_rate
        recalculated_interest = principal_base * effective_rate
        delta = original_interest - recalculated_interest

        return InterestRecalculation(
            original_rate=original_rate,
            effective_rate=effective_rate,
            rate_basis=basis,
            contract_validity=inp.contract_validity,
            original_interest_amount=original_interest,
            recalculated_interest_amount=recalculated_interest,
            delta=delta,
        )
```

Add to `calculate()` after building claim table:
```python
        principal_base = self._sum_principal_loans(inp.loan_transactions)
        interest_recalc = self._recalculate_interest(inp, principal_base)
```

Pass `interest_recalculation=interest_recalc` to `AmountCalculationReport` constructor.

Add to the existing import block at the top of `calculator.py`:
```python
from engines.shared.models import (
    # ... existing imports ...
    ContractValidity,          # ← 新增
    InterestRecalculation,     # ← 新增
)
```

- [ ] **Step 5: Run rule #7 tests**

Run: `cd C:\Users\david\dev\case-adversarial-engine && python -m pytest engines/case_structuring/amount_calculator/tests/test_calculator.py::TestRule7InterestRecalculation -v`
Expected: 6 PASSED

- [ ] **Step 6: Run all calculator tests for regressions**

Run: `cd C:\Users\david\dev\case-adversarial-engine && python -m pytest engines/case_structuring/amount_calculator/tests/test_calculator.py -v`
Expected: All PASS (existing tests don't set contract_validity, defaults to `valid`, interest_recalculation = None)

- [ ] **Step 7: Commit**

```bash
git add engines/case_structuring/amount_calculator/schemas.py engines/case_structuring/amount_calculator/calculator.py engines/case_structuring/amount_calculator/tests/test_calculator.py
git commit -m "feat(amount-rule-7): add interest recalculation for invalid/disputed contracts"
```

---

### Task 6: Full Regression Test + pyproject.toml Update

**Files:**
- Modify: `pyproject.toml` (if needed — add test_rule_config path)

- [ ] **Step 1: Update pyproject.toml testpaths if needed**

Check if `engines/shared/tests` already in testpaths — it is (line 21). No change needed.

- [ ] **Step 2: Run full test suite**

Run: `cd C:\Users\david\dev\case-adversarial-engine && python -m pytest -v --tb=short 2>&1 | tail -40`
Expected: All tests PASS, no regressions

- [ ] **Step 3: Update module docstrings**

Update `calculator.py` top docstring: change "五条硬校验规则" / "five hard validation rules" to "七条" / "seven".
Update `_generate_conflicts` docstring: add "3. 起诉金额/可核实交付比值异常" to the source list.

- [ ] **Step 4: Final commit**

```bash
git add engines/case_structuring/amount_calculator/calculator.py engines/simulation_run/credibility_scorer/scorer.py
git commit -m "chore: v1.1 bug hotfix complete — CRED-07, amount rules #6 and #7"
```

"""
Unit tests for DeductionOptimizer and AMTCalculator.
"""

import pytest
from jit.accounting.deduction_optimizer import (
    DeductionOptimizer,
    DeductionType,
    STANDARD_DEDUCTIONS,
    SALT_CAP,
)
from jit.accounting.amt_calculator import AMTCalculator
from jit.accounting.tax_calculator import FilingStatus


@pytest.fixture
def optimizer():
    return DeductionOptimizer()


class TestDeductionOptimizer:
    def test_standard_deduction_used_when_itemized_lower(self, optimizer):
        """Standard deduction should be recommended when itemized is lower."""
        result = optimizer.optimize(agi=80_000, filing_status=FilingStatus.SINGLE)
        assert result.recommended_method == "standard"
        assert result.standard_deduction == STANDARD_DEDUCTIONS[FilingStatus.SINGLE]

    def test_itemized_recommended_when_higher(self, optimizer):
        """Itemized deduction recommended when it exceeds standard."""
        optimizer.add_deduction(DeductionType.MORTGAGE_INTEREST, 20_000)
        optimizer.add_deduction(DeductionType.CHARITABLE_CASH, 5_000)
        result = optimizer.optimize(agi=100_000, filing_status=FilingStatus.SINGLE)
        assert result.recommended_method == "itemized"
        assert result.itemized_deduction > result.standard_deduction

    def test_salt_cap_applied(self, optimizer):
        """SALT deductions should be capped at $10,000."""
        optimizer.add_deduction(DeductionType.STATE_LOCAL_TAX, 15_000)
        optimizer.add_deduction(DeductionType.PROPERTY_TAX, 5_000)
        result = optimizer.optimize(agi=200_000, filing_status=FilingStatus.SINGLE)
        salt_total = sum(
            i.applied_amount for i in result.itemized_items
            if i.deduction_type in (
                DeductionType.STATE_LOCAL_TAX, DeductionType.PROPERTY_TAX
            )
        )
        assert salt_total <= SALT_CAP

    def test_medical_expense_threshold(self, optimizer):
        """Medical expenses below 7.5% AGI threshold should be zero."""
        optimizer.add_deduction(DeductionType.MEDICAL_EXPENSES, 5_000)
        result = optimizer.optimize(agi=100_000, filing_status=FilingStatus.SINGLE)
        # 7.5% of 100,000 = 7,500; $5,000 expenses don't exceed threshold
        medical = next(
            (i for i in result.itemized_items if i.deduction_type == DeductionType.MEDICAL_EXPENSES),
            None,
        )
        assert medical is not None
        assert medical.applied_amount == 0.0

    def test_medical_expense_above_threshold(self, optimizer):
        """Medical expenses above threshold should be partially deductible."""
        optimizer.add_deduction(DeductionType.MEDICAL_EXPENSES, 15_000)
        result = optimizer.optimize(agi=100_000, filing_status=FilingStatus.SINGLE)
        medical = next(
            (i for i in result.itemized_items if i.deduction_type == DeductionType.MEDICAL_EXPENSES),
            None,
        )
        assert medical is not None
        # 15,000 - 7,500 threshold = 7,500 deductible
        assert medical.applied_amount == 7_500.0

    def test_qbi_deduction_calculated(self, optimizer):
        """QBI deduction should be 20% of qualified business income."""
        result = optimizer.optimize(
            agi=100_000, filing_status=FilingStatus.SINGLE, qbi_income=50_000
        )
        assert result.qbi_deduction == 50_000 * 0.20

    def test_qbi_phaseout_for_sstb(self, optimizer):
        """SSTB QBI deduction should phase out for high income."""
        result = optimizer.optimize(
            agi=600_000, filing_status=FilingStatus.SINGLE,
            qbi_income=100_000, is_sstb=True,
        )
        assert result.qbi_deduction == 0.0

    def test_opportunities_include_ira(self, optimizer):
        """Should suggest IRA contribution if not maxed."""
        result = optimizer.optimize(agi=50_000, filing_status=FilingStatus.SINGLE)
        ira_ops = [o for o in result.opportunities if "IRA" in o]
        assert len(ira_ops) > 0


class TestAMTCalculator:
    def test_no_amt_for_low_income(self):
        """Low income with no preferences should not trigger AMT."""
        calc = AMTCalculator()
        result = calc.calculate(
            regular_taxable_income=50_000,
            regular_tax=7_000,
            filing_status=FilingStatus.SINGLE,
        )
        assert not result.is_subject_to_amt
        assert result.amt_owed == 0.0

    def test_iso_triggers_amt(self):
        """Large ISO bargain element should trigger AMT."""
        calc = AMTCalculator()
        result = calc.calculate(
            regular_taxable_income=100_000,
            regular_tax=18_000,
            filing_status=FilingStatus.SINGLE,
            iso_bargain_element=500_000,
        )
        assert result.is_subject_to_amt
        assert result.amt_owed > 0

    def test_salt_addback(self):
        """SALT should be added back for AMT computation."""
        calc = AMTCalculator()
        result = calc.calculate(
            regular_taxable_income=80_000,
            regular_tax=12_000,
            filing_status=FilingStatus.SINGLE,
            salt_deduction_claimed=10_000,
        )
        # AMTI before exemption should include SALT addback
        assert result.amti_before_exemption >= 80_000 + 10_000

    def test_amt_exemption_applied(self):
        """AMT exemption should reduce AMTI."""
        calc = AMTCalculator()
        result = calc.calculate(
            regular_taxable_income=100_000,
            regular_tax=20_000,
            filing_status=FilingStatus.SINGLE,
        )
        # AMTI (after exemption) should be less than before
        assert result.amti < result.amti_before_exemption

    def test_total_tax_includes_amt(self):
        """Total tax should include AMT owed."""
        calc = AMTCalculator()
        result = calc.calculate(
            regular_taxable_income=100_000,
            regular_tax=18_000,
            filing_status=FilingStatus.SINGLE,
            iso_bargain_element=300_000,
        )
        assert result.total_tax == result.regular_tax + result.amt_owed

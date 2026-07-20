"""
Unit tests for RealTaxCalculator (jit/accounting/engine.py).
"""

from unittest.mock import patch

from jit.accounting.engine import RealTaxCalculator
from jit.core.models import AnalysisContext, IncomeRecord


def _context(income: float) -> AnalysisContext:
    return AnalysisContext(
        case_id="test-case",
        filing_status="single",
        state="CA",
        incomes=[IncomeRecord(kind="1099", amount=income, source="consulting")],
    )


class TestAMTWiring:
    """AMT is compared against regular *income* tax only -- not the total
    federal tax figure, which also folds in Social Security/Medicare tax,
    NIIT, and self-employment tax. Feeding that inflated total in as
    "regular_tax" would systematically understate AMT owed for anyone with
    payroll or SE income. AMT genuinely doesn't trigger through this
    engine's current interface without an ISO exercise (which isn't
    exposed here), so this checks the actual wiring directly rather than
    a dollar-amount difference in the output."""

    def test_amt_calculator_receives_income_tax_not_total_federal_tax(self):
        calculator = RealTaxCalculator()
        context = _context(500_000)  # substantial SE income -> substantial SE tax

        with patch("jit.accounting.engine.AMTCalculator") as mock_amt_cls:
            mock_amt_cls.return_value.calculate.return_value.amt_owed = 0.0
            mock_amt_cls.return_value.calculate.return_value.is_subject_to_amt = False
            calculator.calculate(context, {"tax_year": 2024})

            _, kwargs = mock_amt_cls.return_value.calculate.call_args
            regular_tax_passed = kwargs["regular_tax"]

        # Recompute the real tax result to know what the correct and
        # buggy values would each have been for this exact scenario.
        from jit.accounting.tax_calculator import FilingStatus, TaxCalculator

        real_result = TaxCalculator(tax_year=2024).calculate(
            gross_income=500_000,
            filing_status=FilingStatus.SINGLE,
            deductions=0.0,
            w2_wages=0.0,
            self_employment_income=500_000,
            state_code="CA",
        )
        correct_regular_tax = (
            real_result.federal_income_tax + real_result.long_term_capital_gains_tax
        )
        buggy_regular_tax = real_result.total_federal_tax

        # SE tax alone is tens of thousands of dollars at this income, so
        # the two candidate values are meaningfully different -- this
        # isn't a coincidental match.
        assert buggy_regular_tax - correct_regular_tax > 10_000
        assert regular_tax_passed == correct_regular_tax
        assert regular_tax_passed != buggy_regular_tax

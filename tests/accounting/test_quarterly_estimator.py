"""
Unit tests for QuarterlyEstimator.
"""

import pytest
from jit.accounting.quarterly_estimator import QuarterlyEstimator
from jit.accounting.tax_calculator import FilingStatus


@pytest.fixture
def estimator():
    return QuarterlyEstimator()


class TestQuarterlyEstimator:
    def test_four_quarters_returned(self, estimator):
        result = estimator.estimate(
            expected_total_tax=40_000,
            prior_year_tax=38_000,
            prior_year_agi=150_000,
            filing_status=FilingStatus.SINGLE,
        )
        assert len(result.quarterly_payments) == 4
        assert [p.quarter for p in result.quarterly_payments] == [1, 2, 3, 4]

    def test_no_withholding_shows_underpayment_each_quarter(self, estimator):
        """Regression: underpayment/overpayment used to always compute to 0.0
        because cumulative_paid was reassigned before the comparison, and
        is_safe_harbor_met was hardcoded True regardless of the shortfall."""
        result = estimator.estimate(
            expected_total_tax=40_000,
            prior_year_tax=38_000,
            prior_year_agi=150_000,
            filing_status=FilingStatus.SINGLE,
            w2_withholding=0.0,
        )
        for payment in result.quarterly_payments:
            assert payment.required_payment > 0
            assert payment.underpayment == payment.required_payment
            assert payment.overpayment == 0.0
            assert payment.is_safe_harbor_met is False

    def test_full_withholding_meets_safe_harbor(self, estimator):
        """Withholding that already covers the safe harbor amount should
        leave nothing required and safe harbor met for every quarter."""
        result = estimator.estimate(
            expected_total_tax=40_000,
            prior_year_tax=38_000,
            prior_year_agi=150_000,
            filing_status=FilingStatus.SINGLE,
            w2_withholding=100_000.0,
        )
        for payment in result.quarterly_payments:
            assert payment.required_payment == 0.0
            assert payment.underpayment == 0.0
            assert payment.is_safe_harbor_met is True

    def test_high_income_uses_110_percent_safe_harbor(self, estimator):
        """Prior-year AGI over $150k should use the 110% safe harbor rate,
        not the standard 100%."""
        result = estimator.estimate(
            expected_total_tax=100_000,
            prior_year_tax=50_000,
            prior_year_agi=200_000,
            filing_status=FilingStatus.SINGLE,
        )
        assert result.safe_harbor_amount == pytest.approx(50_000 * 1.10)

    def test_total_required_matches_sum_of_quarterly_payments(self, estimator):
        result = estimator.estimate(
            expected_total_tax=40_000,
            prior_year_tax=38_000,
            prior_year_agi=150_000,
            filing_status=FilingStatus.SINGLE,
            w2_withholding=10_000.0,
        )
        assert result.total_required == pytest.approx(
            sum(p.required_payment for p in result.quarterly_payments), abs=0.05
        )

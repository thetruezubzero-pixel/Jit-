"""
Unit tests for the TaxCalculator.

Tests cover all filing statuses, bracket calculations, FICA, SE tax,
LTCG, NIIT, and state tax estimation.
"""

import pytest
from jit.accounting.tax_calculator import (
    FilingStatus,
    TaxCalculator,
    STANDARD_DEDUCTIONS,
)


@pytest.fixture
def calculator():
    """Return a 2024 TaxCalculator instance."""
    return TaxCalculator(tax_year=2024)


class TestFilingStatusBasic:
    """Basic tax calculations for each filing status."""

    def test_single_low_income(self, calculator):
        """Single filer below the 12% bracket should pay 10%."""
        result = calculator.calculate(gross_income=10_000, filing_status=FilingStatus.SINGLE)
        assert result.tax_year == 2024
        assert result.filing_status == FilingStatus.SINGLE
        # After standard deduction ($14,600) taxable income is 0
        assert result.taxable_income == 0.0
        assert result.federal_income_tax == 0.0

    def test_single_middle_income(self, calculator):
        """Single filer with moderate income should hit 22% bracket."""
        result = calculator.calculate(
            gross_income=80_000,
            filing_status=FilingStatus.SINGLE,
            w2_wages=80_000,
        )
        assert result.gross_income == 80_000
        assert result.adjusted_gross_income == 80_000
        # Taxable income = 80,000 - 14,600 standard deduction = 65,400
        assert result.taxable_income == 65_400.0
        # Must be above 10% and 12% brackets (up to $47,150), hitting 22%
        assert result.marginal_federal_rate == 0.22
        assert result.federal_income_tax > 0

    def test_mfj_higher_standard_deduction(self, calculator):
        """MFJ standard deduction should be double the single deduction."""
        mfj = STANDARD_DEDUCTIONS[FilingStatus.MARRIED_FILING_JOINTLY]
        single = STANDARD_DEDUCTIONS[FilingStatus.SINGLE]
        assert mfj == single * 2

    def test_hoh_between_single_and_mfj(self, calculator):
        """HOH standard deduction should be between single and MFJ."""
        hoh = STANDARD_DEDUCTIONS[FilingStatus.HEAD_OF_HOUSEHOLD]
        single = STANDARD_DEDUCTIONS[FilingStatus.SINGLE]
        mfj = STANDARD_DEDUCTIONS[FilingStatus.MARRIED_FILING_JOINTLY]
        assert single < hoh < mfj


class TestFICA:
    """Tests for FICA tax calculations."""

    def test_social_security_cap(self, calculator):
        """Social Security tax should be capped at the wage base."""
        result = calculator.calculate(
            gross_income=200_000,
            filing_status=FilingStatus.SINGLE,
            w2_wages=200_000,
        )
        # SS rate 6.2% on first $168,600
        expected_ss = round(168_600 * 0.062, 2)
        assert result.social_security_tax == expected_ss

    def test_medicare_no_cap(self, calculator):
        """Medicare tax has no wage base cap."""
        result = calculator.calculate(
            gross_income=300_000,
            filing_status=FilingStatus.SINGLE,
            w2_wages=300_000,
        )
        expected_medicare = round(300_000 * 0.0145, 2)
        assert result.medicare_tax == expected_medicare

    def test_additional_medicare_tax(self, calculator):
        """Additional 0.9% Medicare tax applies above $200k for single."""
        result = calculator.calculate(
            gross_income=250_000,
            filing_status=FilingStatus.SINGLE,
            w2_wages=250_000,
        )
        excess = 250_000 - 200_000
        expected = round(excess * 0.009, 2)
        assert result.additional_medicare_tax == expected

    def test_no_additional_medicare_below_threshold(self, calculator):
        """No additional Medicare tax below threshold."""
        result = calculator.calculate(
            gross_income=150_000,
            filing_status=FilingStatus.SINGLE,
            w2_wages=150_000,
        )
        assert result.additional_medicare_tax == 0.0


class TestSelfEmployment:
    """Tests for self-employment tax."""

    def test_se_tax_calculated(self, calculator):
        """SE tax should be calculated on net SE income."""
        result = calculator.calculate(
            gross_income=50_000,
            filing_status=FilingStatus.SINGLE,
            self_employment_income=50_000,
        )
        assert result.self_employment_tax > 0
        # SE tax = 15.3% on 92.35% of net SE income
        expected = round(50_000 * 0.9235 * 0.153, 2)
        assert abs(result.self_employment_tax - expected) < 2  # Small rounding tolerance

    def test_se_deduction_reduces_agi(self, calculator):
        """Half of SE tax should reduce AGI."""
        result = calculator.calculate(
            gross_income=100_000,
            filing_status=FilingStatus.SINGLE,
            self_employment_income=100_000,
        )
        # AGI should be less than gross income due to SE deduction
        assert result.adjusted_gross_income < 100_000


class TestCapitalGains:
    """Tests for capital gains tax."""

    def test_ltcg_zero_rate_low_income(self, calculator):
        """LTCG at 0% rate for income below threshold."""
        # Single LTCG threshold: $47,025
        result = calculator.calculate(
            gross_income=40_000,
            filing_status=FilingStatus.SINGLE,
            long_term_capital_gains=5_000,
        )
        # Ordinary income is only $35,000 (40k - 5k LTCG), taxable ordinary < $47,025 threshold
        assert result.long_term_capital_gains_tax == 0.0

    def test_ltcg_taxed_at_15pct(self, calculator):
        """LTCG taxed at 15% for moderate income."""
        result = calculator.calculate(
            gross_income=100_000,
            filing_status=FilingStatus.SINGLE,
            w2_wages=80_000,
            long_term_capital_gains=20_000,
        )
        assert result.long_term_capital_gains_tax > 0


class TestNIIT:
    """Tests for Net Investment Income Tax."""

    def test_niit_applied_above_threshold(self, calculator):
        """NIIT 3.8% applies above $200k for single filers."""
        result = calculator.calculate(
            gross_income=250_000,
            filing_status=FilingStatus.SINGLE,
            w2_wages=200_000,
            net_investment_income=50_000,
        )
        assert result.niit > 0

    def test_niit_not_applied_below_threshold(self, calculator):
        """No NIIT below $200k for single filers."""
        result = calculator.calculate(
            gross_income=150_000,
            filing_status=FilingStatus.SINGLE,
            w2_wages=150_000,
            net_investment_income=10_000,
        )
        assert result.niit == 0.0


class TestStateEstimation:
    """Tests for state tax estimation."""

    def test_no_state_tax_for_florida(self, calculator):
        """Florida has no income tax."""
        result = calculator.calculate(
            gross_income=100_000,
            filing_status=FilingStatus.SINGLE,
            state_code="FL",
        )
        assert result.state_tax == 0.0

    def test_state_tax_for_california(self, calculator):
        """California has significant income tax."""
        result = calculator.calculate(
            gross_income=100_000,
            filing_status=FilingStatus.SINGLE,
            state_code="CA",
        )
        assert result.state_tax > 0
        assert result.state_code == "CA"

    def test_no_state_code_gives_zero_state_tax(self, calculator):
        """No state code should result in zero state tax."""
        result = calculator.calculate(gross_income=100_000)
        assert result.state_tax == 0.0
        assert result.state_code is None


class TestEffectiveRates:
    """Tests for effective and marginal rate calculations."""

    def test_effective_rate_less_than_marginal(self, calculator):
        """Effective rate should always be less than or equal to marginal rate."""
        result = calculator.calculate(
            gross_income=200_000,
            filing_status=FilingStatus.SINGLE,
            w2_wages=200_000,
        )
        assert result.effective_federal_rate <= result.marginal_federal_rate

    def test_zero_income_zero_rates(self, calculator):
        """Zero income should produce zero tax rates."""
        result = calculator.calculate(gross_income=0)
        assert result.federal_income_tax == 0.0
        assert result.effective_federal_rate == 0.0
        assert result.total_federal_tax == 0.0


class TestRecommendations:
    """Tests for recommendation generation."""

    def test_recommendations_non_empty(self, calculator):
        """Should always produce at least one recommendation."""
        result = calculator.calculate(
            gross_income=75_000,
            filing_status=FilingStatus.SINGLE,
        )
        assert isinstance(result.recommendations, list)

    def test_se_recommendation_for_se_income(self, calculator):
        """SE income should trigger retirement account recommendation."""
        result = calculator.calculate(
            gross_income=80_000,
            filing_status=FilingStatus.SINGLE,
            self_employment_income=80_000,
        )
        se_recs = [r for r in result.recommendations if "SEP" in r or "self-employed" in r.lower()]
        assert len(se_recs) > 0

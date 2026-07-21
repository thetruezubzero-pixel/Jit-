"""
Unit tests for jit.utils.formatters.

format_currency/format_percentage/format_tax_summary are used by
examples/full_analysis.py for human-readable CLI output but, being a
script rather than part of the pytest-collected suite, had never
actually been exercised by automated tests.
"""

from jit.utils.formatters import format_currency, format_percentage, format_tax_summary
from jit.accounting.tax_calculator import TaxCalculator, FilingStatus


class TestFormatCurrency:
    def test_positive_amount_with_cents(self):
        assert format_currency(1_234.5) == "$1,234.50"

    def test_negative_amount_wrapped_in_parens(self):
        assert format_currency(-1_234.5) == "($1,234.50)"

    def test_without_cents_rounds_to_whole_dollars(self):
        assert format_currency(1_234.5, include_cents=False) == "$1,234"

    def test_zero(self):
        assert format_currency(0) == "$0.00"


class TestFormatPercentage:
    def test_default_two_decimals(self):
        assert format_percentage(0.22) == "22.00%"

    def test_custom_decimal_places(self):
        assert format_percentage(0.0965, decimals=1) == "9.7%"

    def test_zero_decimals(self):
        assert format_percentage(0.37, decimals=0) == "37%"


class TestFormatTaxSummary:
    def test_includes_core_figures(self):
        calc = TaxCalculator(tax_year=2024)
        result = calc.calculate(
            gross_income=80_000,
            filing_status=FilingStatus.SINGLE,
            w2_wages=80_000,
        )
        summary = format_tax_summary(result)
        assert "TAX SUMMARY" in summary
        assert "2024 (SINGLE)" in summary
        assert format_currency(result.gross_income) in summary
        assert format_currency(result.federal_income_tax) in summary
        assert format_currency(result.total_tax) in summary

    def test_omits_zero_valued_optional_lines(self):
        """SE tax, LTCG tax, NIIT, and state tax lines should be hidden when zero."""
        calc = TaxCalculator(tax_year=2024)
        result = calc.calculate(
            gross_income=50_000,
            filing_status=FilingStatus.SINGLE,
            w2_wages=50_000,
        )
        summary = format_tax_summary(result)
        assert "Self-Employment Tax" not in summary
        assert "LTCG Tax" not in summary
        assert "Net Investment Income" not in summary
        assert "State Tax" not in summary

    def test_includes_optional_lines_when_present(self):
        calc = TaxCalculator(tax_year=2024)
        result = calc.calculate(
            gross_income=120_000,
            filing_status=FilingStatus.SINGLE,
            self_employment_income=120_000,
            long_term_capital_gains=10_000,
            net_investment_income=5_000,
            state_code="CA",
        )
        summary = format_tax_summary(result)
        assert "Self-Employment Tax" in summary
        assert "LTCG Tax" in summary
        assert "State Tax (CA)" in summary

    def test_includes_additional_medicare_and_niit_lines_when_present(self):
        calc = TaxCalculator(tax_year=2024)
        result = calc.calculate(
            gross_income=250_000,
            filing_status=FilingStatus.SINGLE,
            w2_wages=250_000,
            net_investment_income=20_000,
        )
        summary = format_tax_summary(result)
        assert "Add'l Medicare Tax" in summary
        assert "Net Investment Income" in summary

    def test_includes_recommendations_when_present(self):
        calc = TaxCalculator(tax_year=2024)
        result = calc.calculate(gross_income=75_000, filing_status=FilingStatus.SINGLE)
        summary = format_tax_summary(result)
        assert "RECOMMENDATIONS" in summary
        for rec in result.recommendations:
            assert rec in summary

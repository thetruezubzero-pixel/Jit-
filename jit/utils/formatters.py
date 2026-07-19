"""Formatting utilities for financial and legal output."""

from __future__ import annotations

from typing import Any


def format_currency(amount: float, include_cents: bool = True) -> str:
    """
    Format a dollar amount as currency string.

    Args:
        amount: Dollar amount (may be negative).
        include_cents: Whether to include cents in output.

    Returns:
        Formatted string like '$1,234.56' or '($1,234.56)' for negatives.
    """
    negative = amount < 0
    abs_amount = abs(amount)
    if include_cents:
        formatted = f"${abs_amount:,.2f}"
    else:
        formatted = f"${abs_amount:,.0f}"
    return f"({formatted})" if negative else formatted


def format_percentage(rate: float, decimals: int = 2) -> str:
    """
    Format a decimal rate as a percentage string.

    Args:
        rate: Decimal rate (e.g., 0.22 for 22%).
        decimals: Number of decimal places.

    Returns:
        Formatted string like '22.00%'.
    """
    return f"{rate * 100:.{decimals}f}%"


def format_tax_summary(tax_result: Any) -> str:
    """
    Format a TaxResult as a human-readable summary string.

    Args:
        tax_result: A TaxResult object from TaxCalculator.

    Returns:
        Multi-line formatted summary.
    """
    lines = [
        f"{'='*60}",
        f"  TAX SUMMARY — {tax_result.tax_year} ({tax_result.filing_status.value.upper()})",
        f"{'='*60}",
        f"  Gross Income:          {format_currency(tax_result.gross_income)}",
        f"  Adjusted Gross Income: {format_currency(tax_result.adjusted_gross_income)}",
        f"  Taxable Income:        {format_currency(tax_result.taxable_income)}",
        f"  {'─'*56}",
        f"  Federal Income Tax:    {format_currency(tax_result.federal_income_tax)}",
        f"  Social Security Tax:   {format_currency(tax_result.social_security_tax)}",
        f"  Medicare Tax:          {format_currency(tax_result.medicare_tax)}",
    ]
    if tax_result.additional_medicare_tax > 0:
        lines.append(
            f"  Add'l Medicare Tax:    {format_currency(tax_result.additional_medicare_tax)}"
        )
    if tax_result.self_employment_tax > 0:
        lines.append(
            f"  Self-Employment Tax:   {format_currency(tax_result.self_employment_tax)}"
        )
    if tax_result.long_term_capital_gains_tax > 0:
        lines.append(
            f"  LTCG Tax:              {format_currency(tax_result.long_term_capital_gains_tax)}"
        )
    if tax_result.niit > 0:
        lines.append(
            f"  Net Investment Income: {format_currency(tax_result.niit)}"
        )
    if tax_result.state_tax > 0:
        lines.append(
            f"  State Tax ({tax_result.state_code or 'N/A'}):       {format_currency(tax_result.state_tax)}"
        )
    lines += [
        f"  {'─'*56}",
        f"  TOTAL TAX:             {format_currency(tax_result.total_tax)}",
        f"  Effective Rate:        {format_percentage(tax_result.effective_total_rate)}",
        f"  Marginal Rate:         {format_percentage(tax_result.marginal_federal_rate)}",
        f"{'='*60}",
    ]
    if tax_result.recommendations:
        lines.append("  RECOMMENDATIONS:")
        for rec in tax_result.recommendations:
            lines.append(f"  • {rec}")
        lines.append(f"{'='*60}")

    return "\n".join(lines)

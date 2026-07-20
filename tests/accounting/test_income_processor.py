"""
Unit tests for IncomeProcessor.
"""

from datetime import date

import pytest

from jit.accounting.income_processor import (
    IncomeProcessor,
    IncomeRecord,
    IncomeType,
)


@pytest.fixture
def processor():
    return IncomeProcessor()


def test_add_w2_and_process(processor):
    """W-2 wages should appear in the summary."""
    processor.add_w2(
        amount=75_000,
        source="Employer Corp",
        tax_year=2024,
        withheld_federal=12_000,
        withheld_state=3_000,
    )
    summary = processor.process(2024)
    assert summary.total_w2_wages == 75_000
    assert summary.total_federal_withheld == 12_000
    assert summary.total_state_withheld == 3_000


def test_add_1099_nec(processor):
    """1099-NEC income should be counted as self-employment."""
    processor.add_1099_nec(amount=30_000, source="Client Inc", tax_year=2024)
    summary = processor.process(2024)
    assert summary.total_self_employment == 30_000
    assert summary.se_income == 30_000


def test_capital_gain_long_term(processor):
    """Long-term capital gain should be in net_long_term_capital_gains."""
    acq = date(2022, 1, 1)
    disp = date(2024, 3, 15)
    processor.add_capital_transaction(
        proceeds=20_000,
        cost_basis=10_000,
        source="Brokerage",
        tax_year=2024,
        acquisition_date=acq,
        disposition_date=disp,
    )
    summary = processor.process(2024)
    assert summary.net_long_term_capital_gains == 10_000


def test_capital_loss_short_term(processor):
    """Short-term capital loss reduces net short-term gains."""
    acq = date(2024, 1, 1)
    disp = date(2024, 6, 1)
    processor.add_capital_transaction(
        proceeds=5_000,
        cost_basis=8_000,
        source="Brokerage",
        tax_year=2024,
        acquisition_date=acq,
        disposition_date=disp,
    )
    summary = processor.process(2024)
    assert summary.short_term_losses == 3_000
    assert summary.net_short_term_capital_gains == -3_000


def test_social_security_taxability(processor):
    """Social security benefits should be partially taxable, matching the
    IRC §86 provisional-income worksheet exactly, not just some plausible
    range. A loose bound here (e.g. "somewhere between $0 and the max")
    would have silently passed even when a sign error zeroed out taxable
    SS entirely -- see test_provisional_income_adds_half_of_ss_not_subtracts
    for the regression this exact scenario caught."""
    processor.add_record(
        IncomeRecord(
            income_type=IncomeType.SOCIAL_SECURITY,
            amount=20_000,
            source="SSA",
            tax_year=2024,
        )
    )
    processor.add_record(
        IncomeRecord(
            income_type=IncomeType.W2_WAGES,
            amount=30_000,
            source="Employer",
            tax_year=2024,
        )
    )
    summary = processor.process(2024)
    # Provisional income = $30,000 + 50% * $20,000 = $40,000, which is
    # above the $34,000 upper threshold (single filer), so:
    # taxable = min(4,500 + 85% * (40,000 - 34,000), 85% * 20,000)
    #         = min(4,500 + 5,100, 17,000) = min(9,600, 17,000) = 9,600
    # This is the worked example from IRS Publication 915.
    assert summary.total_taxable_ss == 9_600.0


def test_provisional_income_adds_half_of_ss_not_subtracts(processor):
    # Regression: provisional income was computed as
    # `gross_income - total_social_security + 0.5*SS`, but gross_income
    # already excludes the SS benefit at the point this runs (it sums
    # total_taxable_ss, which is still 0.0 during this calculation, not
    # total_social_security) -- so the extra subtraction double-counted
    # the exclusion, understating provisional income by a full SS benefit.
    # For a large enough non-SS income relative to a small SS benefit, the
    # bug drove provisional income below the $25,000 floor and reported
    # $0 taxable SS when a real, non-zero amount was owed.
    processor.add_record(
        IncomeRecord(
            income_type=IncomeType.SOCIAL_SECURITY,
            amount=10_000,
            source="SSA",
            tax_year=2024,
        )
    )
    processor.add_record(
        IncomeRecord(
            income_type=IncomeType.W2_WAGES,
            amount=28_000,
            source="Employer",
            tax_year=2024,
        )
    )
    summary = processor.process(2024)
    # Correct provisional income = 28,000 + 0.5*10,000 = 33,000 (between
    # $25,000 and $34,000, so some SS is taxable).
    # Buggy provisional income = 28,000 - 10,000 + 0.5*10,000 = 23,000
    # (below $25,000, so the bug reports $0 -- silently wrong).
    assert summary.total_taxable_ss > 0


def test_gross_income_aggregation(processor):
    """Gross income should sum all positive income sources."""
    processor.add_w2(amount=50_000, source="Emp", tax_year=2024)
    processor.add_record(
        IncomeRecord(
            income_type=IncomeType.INTEREST,
            amount=1_000,
            source="Bank",
            tax_year=2024,
        )
    )
    summary = processor.process(2024)
    assert summary.gross_income >= 51_000


def test_year_filtering(processor):
    """Income from different years should not mix."""
    processor.add_w2(amount=60_000, source="EmpA", tax_year=2023)
    processor.add_w2(amount=70_000, source="EmpB", tax_year=2024)
    summary_2024 = processor.process(2024)
    assert summary_2024.total_w2_wages == 70_000


def test_clear_removes_records(processor):
    """clear() should remove all stored records."""
    processor.add_w2(amount=50_000, source="Emp", tax_year=2024)
    processor.clear()
    summary = processor.process(2024)
    assert summary.total_w2_wages == 0.0

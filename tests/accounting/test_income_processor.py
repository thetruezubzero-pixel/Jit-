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
    processor.add_w2(amount=75_000, source="Employer Corp", tax_year=2024,
                     withheld_federal=12_000, withheld_state=3_000)
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
        proceeds=20_000, cost_basis=10_000,
        source="Brokerage", tax_year=2024,
        acquisition_date=acq, disposition_date=disp,
    )
    summary = processor.process(2024)
    assert summary.net_long_term_capital_gains == 10_000


def test_capital_loss_short_term(processor):
    """Short-term capital loss reduces net short-term gains."""
    acq = date(2024, 1, 1)
    disp = date(2024, 6, 1)
    processor.add_capital_transaction(
        proceeds=5_000, cost_basis=8_000,
        source="Brokerage", tax_year=2024,
        acquisition_date=acq, disposition_date=disp,
    )
    summary = processor.process(2024)
    assert summary.short_term_losses == 3_000
    assert summary.net_short_term_capital_gains == -3_000


def test_social_security_taxability(processor):
    """Social security benefits should be partially taxable."""
    processor.add_record(IncomeRecord(
        income_type=IncomeType.SOCIAL_SECURITY,
        amount=20_000, source="SSA", tax_year=2024,
    ))
    processor.add_record(IncomeRecord(
        income_type=IncomeType.W2_WAGES,
        amount=30_000, source="Employer", tax_year=2024,
    ))
    summary = processor.process(2024)
    # Some portion of SS should be taxable
    assert 0 <= summary.total_taxable_ss <= 20_000 * 0.85


def test_gross_income_aggregation(processor):
    """Gross income should sum all positive income sources."""
    processor.add_w2(amount=50_000, source="Emp", tax_year=2024)
    processor.add_record(IncomeRecord(
        income_type=IncomeType.INTEREST, amount=1_000,
        source="Bank", tax_year=2024,
    ))
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

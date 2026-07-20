"""
Income processor for categorizing and tracking income from multiple sources.

Handles W-2, 1099-MISC, 1099-NEC, 1099-B, 1099-DIV, K-1, rental income,
and other income types per IRS reporting requirements.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Dict, List, Optional


class IncomeType(str, Enum):
    """IRS income classification types."""

    W2_WAGES = "w2_wages"  # Employer wages (Form W-2)
    SELF_EMPLOYMENT = "self_employment"  # Schedule C / 1099-NEC
    BUSINESS_INCOME = "business_income"  # Schedule C
    CAPITAL_GAINS_SHORT = "capital_gains_short"  # Short-term (held ≤1 year)
    CAPITAL_GAINS_LONG = "capital_gains_long"  # Long-term (held >1 year)
    DIVIDENDS_ORDINARY = "dividends_ordinary"  # 1099-DIV box 1a
    DIVIDENDS_QUALIFIED = "dividends_qualified"  # 1099-DIV box 1b
    INTEREST = "interest"  # 1099-INT
    RENTAL_INCOME = "rental_income"  # Schedule E
    PARTNERSHIP_K1 = "partnership_k1"  # Schedule K-1 (Form 1065)
    S_CORP_K1 = "s_corp_k1"  # Schedule K-1 (Form 1120-S)
    RETIREMENT_DISTRIBUTION = "retirement_dist"  # 1099-R
    SOCIAL_SECURITY = "social_security"  # SSA-1099
    UNEMPLOYMENT = "unemployment"  # 1099-G
    ALIMONY = "alimony"  # Pre-2019 agreements
    GAMBLING = "gambling"  # W-2G
    ROYALTIES = "royalties"  # 1099-MISC box 2
    FOREIGN_INCOME = "foreign_income"  # FBAR / Form 2555
    OTHER = "other"  # Miscellaneous


# Whether each income type is subject to self-employment tax
SE_TAX_APPLIES: Dict[IncomeType, bool] = {
    IncomeType.W2_WAGES: False,
    IncomeType.SELF_EMPLOYMENT: True,
    IncomeType.BUSINESS_INCOME: True,
    IncomeType.CAPITAL_GAINS_SHORT: False,
    IncomeType.CAPITAL_GAINS_LONG: False,
    IncomeType.DIVIDENDS_ORDINARY: False,
    IncomeType.DIVIDENDS_QUALIFIED: False,
    IncomeType.INTEREST: False,
    IncomeType.RENTAL_INCOME: False,
    IncomeType.PARTNERSHIP_K1: False,
    IncomeType.S_CORP_K1: False,
    IncomeType.RETIREMENT_DISTRIBUTION: False,
    IncomeType.SOCIAL_SECURITY: False,
    IncomeType.UNEMPLOYMENT: False,
    IncomeType.ALIMONY: False,
    IncomeType.GAMBLING: False,
    IncomeType.ROYALTIES: True,  # If trade/business
    IncomeType.FOREIGN_INCOME: False,
    IncomeType.OTHER: False,
}

# Taxability percentage of Social Security benefits (simplified)
SS_TAXABLE_RATES = [
    (25_000, 0.00),  # Below $25k (single) — not taxable
    (34_000, 0.50),  # $25k–$34k — 50% taxable
    (float("inf"), 0.85),  # Above $34k — 85% taxable
]


@dataclass
class IncomeRecord:
    """A single income record from one source."""

    income_type: IncomeType
    amount: float
    source: str
    tax_year: int
    payer_ein: Optional[str] = None
    withheld_federal: float = 0.0
    withheld_state: float = 0.0
    description: Optional[str] = None
    date_received: Optional[date] = None
    # For capital assets
    cost_basis: Optional[float] = None
    acquisition_date: Optional[date] = None
    disposition_date: Optional[date] = None

    @property
    def is_long_term(self) -> bool:
        """Return True if the asset was held more than one year."""
        if self.acquisition_date and self.disposition_date:
            return (self.disposition_date - self.acquisition_date).days > 365
        return self.income_type == IncomeType.CAPITAL_GAINS_LONG

    @property
    def capital_gain(self) -> Optional[float]:
        """Net capital gain/loss (amount minus cost basis)."""
        if self.cost_basis is not None:
            return self.amount - self.cost_basis
        return None


@dataclass
class IncomeSummary:
    """Aggregated income summary by category."""

    tax_year: int

    # Ordinary income
    total_w2_wages: float = 0.0
    total_self_employment: float = 0.0
    total_business_income: float = 0.0
    total_rental_income: float = 0.0
    total_interest: float = 0.0
    total_ordinary_dividends: float = 0.0
    total_qualified_dividends: float = 0.0
    total_retirement_distributions: float = 0.0
    total_social_security: float = 0.0
    total_taxable_ss: float = 0.0
    total_unemployment: float = 0.0
    total_gambling: float = 0.0
    total_alimony: float = 0.0
    total_royalties: float = 0.0
    total_partnership_k1: float = 0.0
    total_s_corp_k1: float = 0.0
    total_foreign_income: float = 0.0
    total_other: float = 0.0

    # Capital gains / losses
    short_term_gains: float = 0.0
    short_term_losses: float = 0.0
    long_term_gains: float = 0.0
    long_term_losses: float = 0.0

    # Withholdings
    total_federal_withheld: float = 0.0
    total_state_withheld: float = 0.0

    # Records
    records: List[IncomeRecord] = field(default_factory=list)

    @property
    def net_short_term_capital_gains(self) -> float:
        """Net short-term capital gains (can be negative)."""
        return self.short_term_gains - self.short_term_losses

    @property
    def net_long_term_capital_gains(self) -> float:
        """Net long-term capital gains (can be negative)."""
        return self.long_term_gains - self.long_term_losses

    @property
    def gross_income(self) -> float:
        """Total gross income before deductions."""
        return (
            self.total_w2_wages
            + self.total_self_employment
            + self.total_business_income
            + self.total_rental_income
            + self.total_interest
            + self.total_ordinary_dividends
            + self.total_retirement_distributions
            + self.total_taxable_ss
            + self.total_unemployment
            + self.total_gambling
            + self.total_alimony
            + self.total_royalties
            + self.total_partnership_k1
            + self.total_s_corp_k1
            + self.total_foreign_income
            + self.total_other
            + max(0.0, self.net_short_term_capital_gains)
            + max(0.0, self.net_long_term_capital_gains)
        )

    @property
    def se_income(self) -> float:
        """Total income subject to self-employment tax."""
        return self.total_self_employment + self.total_royalties

    @property
    def preferred_income(self) -> float:
        """Income taxed at preferred capital gains rates."""
        return max(0.0, self.net_long_term_capital_gains) + self.total_qualified_dividends


class IncomeProcessor:
    """
    Processes and categorizes income records from multiple sources.

    Aggregates income by type, applies SS taxability rules, and
    nets capital gains/losses per IRS Schedule D rules.
    """

    def __init__(self) -> None:
        """Initialize the income processor."""
        self._records: List[IncomeRecord] = []

    def add_record(self, record: IncomeRecord) -> None:
        """Add an income record to the processor."""
        self._records.append(record)

    def add_w2(
        self,
        amount: float,
        source: str,
        tax_year: int,
        withheld_federal: float = 0.0,
        withheld_state: float = 0.0,
        **kwargs,
    ) -> IncomeRecord:
        """Convenience method to add a W-2 wage record."""
        record = IncomeRecord(
            income_type=IncomeType.W2_WAGES,
            amount=amount,
            source=source,
            tax_year=tax_year,
            withheld_federal=withheld_federal,
            withheld_state=withheld_state,
            **kwargs,
        )
        self.add_record(record)
        return record

    def add_1099_nec(
        self,
        amount: float,
        source: str,
        tax_year: int,
        withheld_federal: float = 0.0,
        **kwargs,
    ) -> IncomeRecord:
        """Convenience method to add a 1099-NEC record."""
        record = IncomeRecord(
            income_type=IncomeType.SELF_EMPLOYMENT,
            amount=amount,
            source=source,
            tax_year=tax_year,
            withheld_federal=withheld_federal,
            **kwargs,
        )
        self.add_record(record)
        return record

    def add_capital_transaction(
        self,
        proceeds: float,
        cost_basis: float,
        source: str,
        tax_year: int,
        acquisition_date: date,
        disposition_date: date,
        **kwargs,
    ) -> IncomeRecord:
        """Convenience method to add a capital gain/loss transaction."""
        held_days = (disposition_date - acquisition_date).days
        income_type = (
            IncomeType.CAPITAL_GAINS_LONG if held_days > 365 else IncomeType.CAPITAL_GAINS_SHORT
        )
        record = IncomeRecord(
            income_type=income_type,
            amount=proceeds,
            source=source,
            tax_year=tax_year,
            cost_basis=cost_basis,
            acquisition_date=acquisition_date,
            disposition_date=disposition_date,
            **kwargs,
        )
        self.add_record(record)
        return record

    def process(self, tax_year: int) -> IncomeSummary:
        """
        Process all income records for the given tax year.

        Args:
            tax_year: The tax year to process.

        Returns:
            IncomeSummary with all income categorized and aggregated.
        """
        year_records = [r for r in self._records if r.tax_year == tax_year]
        summary = IncomeSummary(tax_year=tax_year, records=year_records)

        for record in year_records:
            self._categorize_record(record, summary)

        # Apply Social Security taxability rules
        summary.total_taxable_ss = self._calculate_taxable_ss(summary)

        return summary

    def clear(self) -> None:
        """Clear all income records."""
        self._records.clear()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _categorize_record(self, record: IncomeRecord, summary: IncomeSummary) -> None:
        """Assign a record's amount to the appropriate summary bucket."""
        summary.total_federal_withheld += record.withheld_federal
        summary.total_state_withheld += record.withheld_state

        if record.income_type == IncomeType.W2_WAGES:
            summary.total_w2_wages += record.amount

        elif record.income_type == IncomeType.SELF_EMPLOYMENT:
            summary.total_self_employment += record.amount

        elif record.income_type == IncomeType.BUSINESS_INCOME:
            summary.total_business_income += record.amount

        elif record.income_type == IncomeType.RENTAL_INCOME:
            summary.total_rental_income += record.amount

        elif record.income_type == IncomeType.INTEREST:
            summary.total_interest += record.amount

        elif record.income_type == IncomeType.DIVIDENDS_ORDINARY:
            summary.total_ordinary_dividends += record.amount

        elif record.income_type == IncomeType.DIVIDENDS_QUALIFIED:
            summary.total_ordinary_dividends += record.amount  # Also ordinary
            summary.total_qualified_dividends += record.amount

        elif record.income_type == IncomeType.CAPITAL_GAINS_SHORT:
            gain = record.capital_gain if record.capital_gain is not None else record.amount
            if gain >= 0:
                summary.short_term_gains += gain
            else:
                summary.short_term_losses += abs(gain)

        elif record.income_type == IncomeType.CAPITAL_GAINS_LONG:
            gain = record.capital_gain if record.capital_gain is not None else record.amount
            if gain >= 0:
                summary.long_term_gains += gain
            else:
                summary.long_term_losses += abs(gain)

        elif record.income_type == IncomeType.RETIREMENT_DISTRIBUTION:
            summary.total_retirement_distributions += record.amount

        elif record.income_type == IncomeType.SOCIAL_SECURITY:
            summary.total_social_security += record.amount

        elif record.income_type == IncomeType.UNEMPLOYMENT:
            summary.total_unemployment += record.amount

        elif record.income_type == IncomeType.ALIMONY:
            summary.total_alimony += record.amount

        elif record.income_type == IncomeType.GAMBLING:
            summary.total_gambling += record.amount

        elif record.income_type == IncomeType.ROYALTIES:
            summary.total_royalties += record.amount

        elif record.income_type == IncomeType.PARTNERSHIP_K1:
            summary.total_partnership_k1 += record.amount

        elif record.income_type == IncomeType.S_CORP_K1:
            summary.total_s_corp_k1 += record.amount

        elif record.income_type == IncomeType.FOREIGN_INCOME:
            summary.total_foreign_income += record.amount

        else:
            summary.total_other += record.amount

    def _calculate_taxable_ss(self, summary: IncomeSummary) -> float:
        """
        Calculate the taxable portion of Social Security benefits.

        Uses the provisional income method from IRC §86.
        """
        if summary.total_social_security == 0:
            return 0.0

        # Provisional income = AGI + tax-exempt interest + 50% SS
        provisional = (
            summary.gross_income
            - summary.total_social_security
            + (summary.total_social_security * 0.5)
        )

        if provisional < 25_000:
            return 0.0
        elif provisional < 34_000:
            taxable = min(
                (provisional - 25_000) * 0.5,
                summary.total_social_security * 0.5,
            )
        else:
            taxable = min(
                4_500 + (provisional - 34_000) * 0.85,
                summary.total_social_security * 0.85,
            )

        return round(taxable, 2)

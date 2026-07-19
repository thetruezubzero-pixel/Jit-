"""
Federal and state income tax calculator for American citizens.

Implements 2024 tax year brackets, standard deductions, and
filing status adjustments per IRS Publication 17.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple


class FilingStatus(str, Enum):
    """IRS filing status options."""

    SINGLE = "single"
    MARRIED_FILING_JOINTLY = "married_filing_jointly"
    MARRIED_FILING_SEPARATELY = "married_filing_separately"
    HEAD_OF_HOUSEHOLD = "head_of_household"
    QUALIFYING_SURVIVING_SPOUSE = "qualifying_surviving_spouse"


# 2024 Federal income tax brackets  (taxable income thresholds)
# Source: IRS Rev. Proc. 2023-34
FEDERAL_BRACKETS: Dict[FilingStatus, List[Tuple[float, float]]] = {
    FilingStatus.SINGLE: [
        (11_600, 0.10),
        (47_150, 0.12),
        (100_525, 0.22),
        (191_950, 0.24),
        (243_725, 0.32),
        (609_350, 0.35),
        (float("inf"), 0.37),
    ],
    FilingStatus.MARRIED_FILING_JOINTLY: [
        (23_200, 0.10),
        (94_300, 0.12),
        (201_050, 0.22),
        (383_900, 0.24),
        (487_450, 0.32),
        (731_200, 0.35),
        (float("inf"), 0.37),
    ],
    FilingStatus.MARRIED_FILING_SEPARATELY: [
        (11_600, 0.10),
        (47_150, 0.12),
        (100_525, 0.22),
        (191_950, 0.24),
        (243_725, 0.32),
        (365_600, 0.35),
        (float("inf"), 0.37),
    ],
    FilingStatus.HEAD_OF_HOUSEHOLD: [
        (16_550, 0.10),
        (63_100, 0.12),
        (100_500, 0.22),
        (191_950, 0.24),
        (243_700, 0.32),
        (609_350, 0.35),
        (float("inf"), 0.37),
    ],
    FilingStatus.QUALIFYING_SURVIVING_SPOUSE: [
        (23_200, 0.10),
        (94_300, 0.12),
        (201_050, 0.22),
        (383_900, 0.24),
        (487_450, 0.32),
        (731_200, 0.35),
        (float("inf"), 0.37),
    ],
}

# 2024 Standard deductions per filing status
STANDARD_DEDUCTIONS: Dict[FilingStatus, float] = {
    FilingStatus.SINGLE: 14_600,
    FilingStatus.MARRIED_FILING_JOINTLY: 29_200,
    FilingStatus.MARRIED_FILING_SEPARATELY: 14_600,
    FilingStatus.HEAD_OF_HOUSEHOLD: 21_900,
    FilingStatus.QUALIFYING_SURVIVING_SPOUSE: 29_200,
}

# FICA rates (2024)
SOCIAL_SECURITY_RATE = 0.062
MEDICARE_RATE = 0.0145
ADDITIONAL_MEDICARE_RATE = 0.009  # On wages > threshold
SOCIAL_SECURITY_WAGE_BASE = 168_600
ADDITIONAL_MEDICARE_THRESHOLD: Dict[FilingStatus, float] = {
    FilingStatus.SINGLE: 200_000,
    FilingStatus.MARRIED_FILING_JOINTLY: 250_000,
    FilingStatus.MARRIED_FILING_SEPARATELY: 125_000,
    FilingStatus.HEAD_OF_HOUSEHOLD: 200_000,
    FilingStatus.QUALIFYING_SURVIVING_SPOUSE: 200_000,
}

# Net Investment Income Tax (NIIT) 3.8% - IRC §1411
NIIT_RATE = 0.038
NIIT_THRESHOLD: Dict[FilingStatus, float] = {
    FilingStatus.SINGLE: 200_000,
    FilingStatus.MARRIED_FILING_JOINTLY: 250_000,
    FilingStatus.MARRIED_FILING_SEPARATELY: 125_000,
    FilingStatus.HEAD_OF_HOUSEHOLD: 200_000,
    FilingStatus.QUALIFYING_SURVIVING_SPOUSE: 250_000,
}

# Qualified dividends / long-term capital gains rates (2024)
LTCG_BRACKETS: Dict[FilingStatus, List[Tuple[float, float]]] = {
    FilingStatus.SINGLE: [
        (47_025, 0.00),
        (518_900, 0.15),
        (float("inf"), 0.20),
    ],
    FilingStatus.MARRIED_FILING_JOINTLY: [
        (94_050, 0.00),
        (583_750, 0.15),
        (float("inf"), 0.20),
    ],
    FilingStatus.MARRIED_FILING_SEPARATELY: [
        (47_025, 0.00),
        (291_850, 0.15),
        (float("inf"), 0.20),
    ],
    FilingStatus.HEAD_OF_HOUSEHOLD: [
        (63_000, 0.00),
        (551_350, 0.15),
        (float("inf"), 0.20),
    ],
    FilingStatus.QUALIFYING_SURVIVING_SPOUSE: [
        (94_050, 0.00),
        (583_750, 0.15),
        (float("inf"), 0.20),
    ],
}

# Self-employment tax
SE_TAX_RATE = 0.153  # 12.4% SS + 2.9% Medicare
SE_DEDUCTION_RATE = 0.5  # Deduct half of SE tax


@dataclass
class BracketDetail:
    """Tax bracket application detail."""

    rate: float
    bracket_income: float
    bracket_tax: float
    cumulative_tax: float


@dataclass
class TaxResult:
    """Comprehensive tax calculation result."""

    filing_status: FilingStatus
    tax_year: int

    # Income
    gross_income: float
    adjusted_gross_income: float
    taxable_income: float

    # Federal tax
    federal_income_tax: float
    effective_federal_rate: float
    marginal_federal_rate: float
    bracket_details: List[BracketDetail] = field(default_factory=list)

    # FICA
    social_security_tax: float = 0.0
    medicare_tax: float = 0.0
    additional_medicare_tax: float = 0.0

    # Capital gains
    long_term_capital_gains_tax: float = 0.0
    niit: float = 0.0

    # Self-employment
    self_employment_tax: float = 0.0

    # Total
    total_federal_tax: float = 0.0
    effective_total_rate: float = 0.0

    # State (placeholder — populated by state calculator)
    state_tax: float = 0.0
    state_code: Optional[str] = None

    # Recommendations
    recommendations: List[str] = field(default_factory=list)

    @property
    def total_tax(self) -> float:
        """Total tax burden including state."""
        return self.total_federal_tax + self.state_tax


class TaxCalculator:
    """
    Federal income tax calculator implementing 2024 IRS tax rules.

    Supports all filing statuses, ordinary income, capital gains,
    FICA taxes, self-employment tax, NIIT, and basic state tax.
    """

    def __init__(self, tax_year: int = 2024) -> None:
        """
        Initialize calculator.

        Args:
            tax_year: The tax year for calculations (default 2024).
        """
        self.tax_year = tax_year

    def calculate(
        self,
        gross_income: float,
        filing_status: FilingStatus = FilingStatus.SINGLE,
        adjustments: float = 0.0,
        deductions: float = 0.0,
        w2_wages: float = 0.0,
        self_employment_income: float = 0.0,
        long_term_capital_gains: float = 0.0,
        qualified_dividends: float = 0.0,
        net_investment_income: float = 0.0,
        state_code: Optional[str] = None,
    ) -> TaxResult:
        """
        Calculate comprehensive federal tax liability.

        Args:
            gross_income: Total gross income from all sources.
            filing_status: IRS filing status.
            adjustments: Above-the-line deductions (IRA, student loan interest, etc.).
            deductions: Itemized deductions (0 = use standard deduction).
            w2_wages: Wages subject to FICA.
            self_employment_income: Net self-employment income.
            long_term_capital_gains: Net long-term capital gains.
            qualified_dividends: Qualified dividends (taxed at LTCG rates).
            net_investment_income: Net investment income for NIIT.
            state_code: Two-letter state code for state tax estimate.

        Returns:
            TaxResult with full breakdown.
        """
        # --- Self-employment tax deduction ---
        se_tax = self._calculate_se_tax(self_employment_income)
        se_agi_deduction = se_tax * SE_DEDUCTION_RATE if se_tax > 0 else 0.0

        # --- AGI ---
        agi = max(0.0, gross_income - adjustments - se_agi_deduction)

        # --- Deductions ---
        standard = STANDARD_DEDUCTIONS[filing_status]
        applied_deduction = max(deductions, standard)

        # --- Taxable income (ordinary) ---
        preferred_income = long_term_capital_gains + qualified_dividends
        ordinary_taxable = max(0.0, agi - applied_deduction - preferred_income)
        total_taxable = max(0.0, agi - applied_deduction)

        # --- Federal ordinary income tax ---
        federal_tax, brackets = self._apply_brackets(
            ordinary_taxable, FEDERAL_BRACKETS[filing_status]
        )

        # --- Long-term capital gains tax ---
        ltcg_tax = self._calculate_ltcg_tax(
            ordinary_taxable, preferred_income, filing_status
        )

        # --- FICA ---
        ss_tax, medicare_tax, add_medicare = self._calculate_fica(
            w2_wages, agi, filing_status
        )

        # --- NIIT ---
        niit = self._calculate_niit(agi, net_investment_income, filing_status)

        # --- Marginal and effective rates ---
        marginal = self._marginal_rate(ordinary_taxable, FEDERAL_BRACKETS[filing_status])
        effective_federal = federal_tax / agi if agi > 0 else 0.0

        total_federal = (
            federal_tax + ltcg_tax + ss_tax + medicare_tax + add_medicare + niit + se_tax
        )
        effective_total = total_federal / gross_income if gross_income > 0 else 0.0

        # --- State tax ---
        state_tax = 0.0
        if state_code:
            state_tax = self._estimate_state_tax(agi, state_code, filing_status)

        # --- Build recommendations ---
        recs = self._generate_recommendations(
            agi, applied_deduction, standard, filing_status, se_tax
        )

        return TaxResult(
            filing_status=filing_status,
            tax_year=self.tax_year,
            gross_income=gross_income,
            adjusted_gross_income=agi,
            taxable_income=total_taxable,
            federal_income_tax=federal_tax,
            effective_federal_rate=round(effective_federal, 4),
            marginal_federal_rate=marginal,
            bracket_details=brackets,
            social_security_tax=ss_tax,
            medicare_tax=medicare_tax,
            additional_medicare_tax=add_medicare,
            long_term_capital_gains_tax=ltcg_tax,
            niit=niit,
            self_employment_tax=se_tax,
            total_federal_tax=total_federal,
            effective_total_rate=round(effective_total, 4),
            state_tax=state_tax,
            state_code=state_code,
            recommendations=recs,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _apply_brackets(
        self, taxable_income: float, brackets: List[Tuple[float, float]]
    ) -> Tuple[float, List[BracketDetail]]:
        """Apply progressive tax brackets and return total tax + breakdown."""
        tax = 0.0
        prev_limit = 0.0
        details: List[BracketDetail] = []

        for limit, rate in brackets:
            if taxable_income <= prev_limit:
                break
            bracket_income = min(taxable_income, limit) - prev_limit
            bracket_tax = bracket_income * rate
            tax += bracket_tax
            details.append(
                BracketDetail(
                    rate=rate,
                    bracket_income=bracket_income,
                    bracket_tax=round(bracket_tax, 2),
                    cumulative_tax=round(tax, 2),
                )
            )
            prev_limit = limit

        return round(tax, 2), details

    def _marginal_rate(
        self, taxable_income: float, brackets: List[Tuple[float, float]]
    ) -> float:
        """Return the marginal tax rate for the given taxable income."""
        prev_limit = 0.0
        for limit, rate in brackets:
            if taxable_income <= limit:
                return rate
            prev_limit = limit
        return brackets[-1][1]

    def _calculate_ltcg_tax(
        self,
        ordinary_income: float,
        preferred_income: float,
        filing_status: FilingStatus,
    ) -> float:
        """Calculate tax on qualified dividends and long-term capital gains."""
        if preferred_income <= 0:
            return 0.0
        brackets = LTCG_BRACKETS[filing_status]
        tax = 0.0
        prev_limit = 0.0
        # Stack preferred income on top of ordinary income
        base = ordinary_income
        remaining = preferred_income

        for limit, rate in brackets:
            if base >= limit:
                prev_limit = limit
                continue
            space = limit - max(base, prev_limit)
            taxable = min(remaining, space)
            tax += taxable * rate
            remaining -= taxable
            if remaining <= 0:
                break
            prev_limit = limit

        return round(tax, 2)

    def _calculate_fica(
        self,
        w2_wages: float,
        agi: float,
        filing_status: FilingStatus,
    ) -> Tuple[float, float, float]:
        """Calculate Social Security, Medicare, and Additional Medicare taxes."""
        ss_wages = min(w2_wages, SOCIAL_SECURITY_WAGE_BASE)
        ss_tax = round(ss_wages * SOCIAL_SECURITY_RATE, 2)
        medicare_tax = round(w2_wages * MEDICARE_RATE, 2)

        threshold = ADDITIONAL_MEDICARE_THRESHOLD[filing_status]
        additional_wages = max(0.0, w2_wages - threshold)
        add_medicare = round(additional_wages * ADDITIONAL_MEDICARE_RATE, 2)

        return ss_tax, medicare_tax, add_medicare

    def _calculate_se_tax(self, se_income: float) -> float:
        """Calculate self-employment tax (Schedule SE)."""
        if se_income <= 0:
            return 0.0
        # SE tax base = 92.35% of net SE income
        se_base = se_income * 0.9235
        # Social Security portion capped at wage base
        ss_portion = min(se_base, SOCIAL_SECURITY_WAGE_BASE) * 0.124
        medicare_portion = se_base * 0.029
        return round(ss_portion + medicare_portion, 2)

    def _calculate_niit(
        self,
        agi: float,
        net_investment_income: float,
        filing_status: FilingStatus,
    ) -> float:
        """Calculate Net Investment Income Tax (IRC §1411)."""
        threshold = NIIT_THRESHOLD[filing_status]
        if agi <= threshold or net_investment_income <= 0:
            return 0.0
        niit_base = min(net_investment_income, agi - threshold)
        return round(niit_base * NIIT_RATE, 2)

    def _estimate_state_tax(
        self, agi: float, state_code: str, filing_status: FilingStatus
    ) -> float:
        """
        Estimate state income tax using simplified flat-rate approximations.

        NOTE: This is a simplified approximation. Actual state tax calculations
        require state-specific brackets, credits, and deductions.
        """
        # Approximate effective state income tax rates by state
        STATE_RATES: Dict[str, float] = {
            "AL": 0.05, "AK": 0.00, "AZ": 0.025, "AR": 0.049,
            "CA": 0.093, "CO": 0.044, "CT": 0.065, "DE": 0.066,
            "FL": 0.00, "GA": 0.055, "HI": 0.11, "ID": 0.058,
            "IL": 0.0495, "IN": 0.0305, "IA": 0.06, "KS": 0.057,
            "KY": 0.045, "LA": 0.042, "ME": 0.075, "MD": 0.0575,
            "MA": 0.09, "MI": 0.0425, "MN": 0.0985, "MS": 0.05,
            "MO": 0.054, "MT": 0.069, "NE": 0.0664, "NV": 0.00,
            "NH": 0.00, "NJ": 0.0897, "NM": 0.059, "NY": 0.109,
            "NC": 0.0499, "ND": 0.029, "OH": 0.04, "OK": 0.0475,
            "OR": 0.099, "PA": 0.0307, "RI": 0.0599, "SC": 0.07,
            "SD": 0.00, "TN": 0.00, "TX": 0.00, "UT": 0.0485,
            "VT": 0.0875, "VA": 0.0575, "WA": 0.00, "WV": 0.065,
            "WI": 0.0765, "WY": 0.00, "DC": 0.0895,
        }
        rate = STATE_RATES.get(state_code.upper(), 0.05)
        return round(agi * rate, 2)

    def _generate_recommendations(
        self,
        agi: float,
        applied_deduction: float,
        standard_deduction: float,
        filing_status: FilingStatus,
        se_tax: float,
    ) -> List[str]:
        """Generate tax-saving recommendations based on the tax situation."""
        recs: List[str] = []

        if applied_deduction == standard_deduction:
            recs.append(
                "You are using the standard deduction. Consider tracking itemized "
                "deductions (mortgage interest, charitable contributions, state/local taxes) "
                "to see if itemizing would reduce your tax."
            )

        if agi > 150_000:
            recs.append(
                "Your AGI may affect eligibility for certain deductions and credits. "
                "Consider contributing to a traditional IRA or 401(k) to reduce AGI."
            )

        if se_tax > 0:
            recs.append(
                "As a self-employed individual, consider establishing a SEP-IRA or "
                "Solo 401(k) to reduce both income and self-employment taxes."
            )

        if agi > 200_000 and filing_status == FilingStatus.SINGLE:
            recs.append(
                "You may be subject to the Net Investment Income Tax (3.8%) and "
                "Additional Medicare Tax (0.9%). Review investment income strategies."
            )

        if agi < 66_000:
            recs.append(
                "You may qualify for the Earned Income Tax Credit (EITC). "
                "Review IRS eligibility requirements."
            )

        return recs

"""
Alternative Minimum Tax (AMT) calculator.

Implements AMT computation per IRS Form 6251 for tax year 2024,
including AMTI computation, exemption phase-outs, and AMT credit tracking.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

from jit.accounting.tax_calculator import FilingStatus

# 2024 AMT exemption amounts
AMT_EXEMPTIONS: Dict[FilingStatus, float] = {
    FilingStatus.SINGLE: 85_700,
    FilingStatus.MARRIED_FILING_JOINTLY: 133_300,
    FilingStatus.MARRIED_FILING_SEPARATELY: 66_650,
    FilingStatus.HEAD_OF_HOUSEHOLD: 85_700,
    FilingStatus.QUALIFYING_SURVIVING_SPOUSE: 133_300,
}

# 2024 AMT exemption phase-out thresholds
AMT_PHASEOUT_START: Dict[FilingStatus, float] = {
    FilingStatus.SINGLE: 609_350,
    FilingStatus.MARRIED_FILING_JOINTLY: 1_218_700,
    FilingStatus.MARRIED_FILING_SEPARATELY: 609_350,
    FilingStatus.HEAD_OF_HOUSEHOLD: 609_350,
    FilingStatus.QUALIFYING_SURVIVING_SPOUSE: 1_218_700,
}

# AMT tax rates
# $220,700 / $110,350 were the 2023 breakpoints (mislabeled "2024" here) --
# Rev. Proc. 2023-34 sets the actual 2024 figures at $232,600 / $116,300.
AMT_RATE_1 = 0.26  # On AMTI up to $232,600 (2024, all filing statuses except MFS)
AMT_RATE_2 = 0.28  # On AMTI above threshold
AMT_RATE_BREAKPOINT = 232_600  # All statuses (MFS: $116,300)
AMT_RATE_BREAKPOINT_MFS = 116_300


@dataclass
class AMTResult:
    """Result of AMT calculation."""

    filing_status: FilingStatus
    tax_year: int

    # Inputs
    regular_taxable_income: float
    regular_tax: float

    # AMT computation
    amti_before_exemption: float = 0.0
    amt_exemption: float = 0.0
    amti: float = 0.0  # AMTI after exemption
    tentative_minimum_tax: float = 0.0
    amt_owed: float = 0.0  # max(0, TMT - regular_tax)

    # AMT preference items
    preference_items: List[str] = field(default_factory=list)
    adjustment_items: List[str] = field(default_factory=list)

    # Credit carryforward
    amt_credit_generated: float = 0.0
    is_subject_to_amt: bool = False

    @property
    def total_tax(self) -> float:
        """Regular tax plus AMT owed."""
        return self.regular_tax + self.amt_owed


class AMTCalculator:
    """
    Calculates Alternative Minimum Tax per IRS Form 6251.

    The AMT is a parallel tax system designed to ensure that taxpayers
    with substantial economic income pay at least a minimum amount of tax,
    regardless of deductions and credits claimed under the regular tax.
    """

    def __init__(self, tax_year: int = 2024) -> None:
        """Initialize AMT calculator."""
        self.tax_year = tax_year

    def calculate(
        self,
        regular_taxable_income: float,
        regular_tax: float,
        filing_status: FilingStatus = FilingStatus.SINGLE,
        # Common AMT adjustments / preference items
        iso_bargain_element: float = 0.0,  # Incentive stock option spread
        accelerated_depreciation: float = 0.0,  # Excess depreciation (Form 4562)
        percentage_depletion_excess: float = 0.0,  # Oil & gas depletion
        tax_exempt_interest: float = 0.0,  # Private activity bond interest
        salt_deduction_claimed: float = 0.0,  # SALT (not deductible for AMT)
        misc_itemized_deductions: float = 0.0,  # Eliminated for AMT
        standard_deduction_claimed: float = 0.0,  # Not allowed for AMT
        long_term_capital_gains: float = 0.0,  # Excluded from AMT rate
        qualified_dividends: float = 0.0,
    ) -> AMTResult:
        """
        Calculate AMT liability.

        Args:
            regular_taxable_income: Taxable income for regular tax purposes.
            regular_tax: Regular income tax computed.
            filing_status: IRS filing status.
            iso_bargain_element: Spread on ISO exercise (major AMT trigger).
            accelerated_depreciation: Excess of regular over AMT depreciation.
            percentage_depletion_excess: Excess percentage over cost depletion.
            tax_exempt_interest: Interest from private activity bonds.
            salt_deduction_claimed: State/local taxes deducted on Schedule A.
            misc_itemized_deductions: Subject-to-2%-floor miscellaneous deductions.
            standard_deduction_claimed: Standard deduction (add back for AMT).
            long_term_capital_gains: LTCG excluded from high AMT rates.
            qualified_dividends: Qualified dividends excluded from high AMT rates.

        Returns:
            AMTResult with full AMT computation.
        """
        preference_items: List[str] = []
        adjustment_items: List[str] = []

        # --- Compute AMTI before exemption ---
        # Start with regular taxable income
        amti = regular_taxable_income

        # Add back standard deduction (not allowed for AMT)
        amti += standard_deduction_claimed
        if standard_deduction_claimed > 0:
            adjustment_items.append(
                f"Standard deduction add-back: +${standard_deduction_claimed:,.0f}"
            )

        # Add back SALT (not deductible for AMT)
        amti += salt_deduction_claimed
        if salt_deduction_claimed > 0:
            adjustment_items.append(f"SALT deduction add-back: +${salt_deduction_claimed:,.0f}")

        # Add back miscellaneous itemized deductions
        amti += misc_itemized_deductions
        if misc_itemized_deductions > 0:
            adjustment_items.append(
                f"Misc. itemized deduction add-back: +${misc_itemized_deductions:,.0f}"
            )

        # Preference items
        if iso_bargain_element > 0:
            amti += iso_bargain_element
            preference_items.append(
                f"ISO bargain element (exercise spread): +${iso_bargain_element:,.0f}"
            )

        if accelerated_depreciation > 0:
            amti += accelerated_depreciation
            preference_items.append(
                f"Accelerated depreciation adjustment: +${accelerated_depreciation:,.0f}"
            )

        if percentage_depletion_excess > 0:
            amti += percentage_depletion_excess
            preference_items.append(
                f"Excess percentage depletion: +${percentage_depletion_excess:,.0f}"
            )

        if tax_exempt_interest > 0:
            amti += tax_exempt_interest
            preference_items.append(f"Private activity bond interest: +${tax_exempt_interest:,.0f}")

        amti_before_exemption = max(0.0, amti)

        # --- Compute exemption with phase-out ---
        exemption = self._compute_exemption(amti_before_exemption, filing_status)

        # --- AMTI after exemption ---
        amti_net = max(0.0, amti_before_exemption - exemption)

        # --- Tentative minimum tax ---
        # Preferred items (LTCG / qualified dividends) taxed at preferential rates
        preferred = long_term_capital_gains + qualified_dividends
        ordinary_amti = max(0.0, amti_net - preferred)
        tmt = self._compute_tmt(ordinary_amti, preferred, filing_status)

        # --- AMT owed ---
        amt_owed = max(0.0, tmt - regular_tax)

        # --- AMT credit ---
        # AMT credit generated only from deferral items (ISO), not exclusion items
        amt_credit = min(amt_owed, iso_bargain_element * 0.26)

        return AMTResult(
            filing_status=filing_status,
            tax_year=self.tax_year,
            regular_taxable_income=regular_taxable_income,
            regular_tax=regular_tax,
            amti_before_exemption=round(amti_before_exemption, 2),
            amt_exemption=round(exemption, 2),
            amti=round(amti_net, 2),
            tentative_minimum_tax=round(tmt, 2),
            amt_owed=round(amt_owed, 2),
            preference_items=preference_items,
            adjustment_items=adjustment_items,
            amt_credit_generated=round(amt_credit, 2),
            is_subject_to_amt=amt_owed > 0,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _compute_exemption(self, amti: float, filing_status: FilingStatus) -> float:
        """Compute AMT exemption with phase-out."""
        base_exemption = AMT_EXEMPTIONS[filing_status]
        phaseout_start = AMT_PHASEOUT_START[filing_status]

        if amti <= phaseout_start:
            return base_exemption

        # Exemption reduced by $0.25 for every $1 of AMTI above threshold
        excess = amti - phaseout_start
        reduction = excess * 0.25
        return max(0.0, base_exemption - reduction)

    def _compute_tmt(
        self,
        ordinary_amti: float,
        preferred_income: float,
        filing_status: FilingStatus,
    ) -> float:
        """Compute tentative minimum tax."""
        breakpoint = (
            AMT_RATE_BREAKPOINT_MFS
            if filing_status == FilingStatus.MARRIED_FILING_SEPARATELY
            else AMT_RATE_BREAKPOINT
        )

        if ordinary_amti <= breakpoint:
            ordinary_tmt = ordinary_amti * AMT_RATE_1
        else:
            ordinary_tmt = breakpoint * AMT_RATE_1 + (ordinary_amti - breakpoint) * AMT_RATE_2

        # Preferred income taxed at regular capital gains rates (approx 15%)
        preferred_tmt = preferred_income * 0.15

        return round(ordinary_tmt + preferred_tmt, 2)

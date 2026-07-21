"""
Deduction optimizer for maximizing tax deductions.

Implements standard vs. itemized deduction comparison, phase-out rules,
Qualified Business Income (QBI) deduction, and retirement contribution
optimization per current IRS guidelines.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

from jit.accounting.tax_calculator import FilingStatus, STANDARD_DEDUCTIONS


class DeductionType(str, Enum):
    """Categories of deductions."""

    # Itemized deductions (Schedule A)
    MORTGAGE_INTEREST = "mortgage_interest"
    STATE_LOCAL_TAX = "state_local_tax"  # SALT (capped at $10k)
    PROPERTY_TAX = "property_tax"  # Part of SALT cap
    CHARITABLE_CASH = "charitable_cash"
    CHARITABLE_NONCASH = "charitable_noncash"
    MEDICAL_EXPENSES = "medical_expenses"  # >7.5% AGI threshold
    CASUALTY_LOSS = "casualty_loss"  # Federally declared disaster
    INVESTMENT_INTEREST = "investment_interest"
    GAMBLING_LOSSES = "gambling_losses"  # Up to gambling winnings

    # Above-the-line (Schedule 1 adjustments)
    TRADITIONAL_IRA = "traditional_ira"
    STUDENT_LOAN_INTEREST = "student_loan_interest"
    HSA_CONTRIBUTION = "hsa_contribution"
    EDUCATOR_EXPENSES = "educator_expenses"
    SELF_EMPLOYED_HEALTH = "self_employed_health_insurance"
    SELF_EMPLOYED_SEP = "self_employed_sep_ira"
    MOVING_EXPENSES = "moving_expenses"  # Military only after TCJA

    # QBI deduction (IRC §199A)
    QBI_DEDUCTION = "qbi_deduction"


# 2024 SALT deduction cap
SALT_CAP = 10_000

# 2024 Medical expense threshold
MEDICAL_THRESHOLD_RATE = 0.075  # 7.5% of AGI

# 2024 Charitable deduction limits (% of AGI)
CHARITABLE_CASH_LIMIT = 0.60
CHARITABLE_NONCASH_LIMIT = 0.30

# 2024 Traditional IRA contribution limits
IRA_LIMIT_UNDER_50 = 7_000
IRA_LIMIT_50_PLUS = 8_000

# IRA deductibility phase-outs (covered by workplace plan)
IRA_PHASEOUT: Dict[FilingStatus, tuple] = {
    FilingStatus.SINGLE: (77_000, 87_000),
    FilingStatus.MARRIED_FILING_JOINTLY: (123_000, 143_000),
    FilingStatus.MARRIED_FILING_SEPARATELY: (0, 10_000),
    FilingStatus.HEAD_OF_HOUSEHOLD: (77_000, 87_000),
    FilingStatus.QUALIFYING_SURVIVING_SPOUSE: (123_000, 143_000),
}

# 2024 HSA contribution limits
HSA_SELF_ONLY = 4_150
HSA_FAMILY = 8_300
HSA_CATCH_UP = 1_000  # Age 55+

# 2024 Student loan interest deduction limit
STUDENT_LOAN_LIMIT = 2_500
STUDENT_LOAN_PHASEOUT: Dict[FilingStatus, tuple] = {
    FilingStatus.SINGLE: (80_000, 95_000),
    FilingStatus.MARRIED_FILING_JOINTLY: (165_000, 195_000),
    FilingStatus.MARRIED_FILING_SEPARATELY: (0, 0),  # Not allowed
    FilingStatus.HEAD_OF_HOUSEHOLD: (80_000, 95_000),
    FilingStatus.QUALIFYING_SURVIVING_SPOUSE: (165_000, 195_000),
}

# QBI deduction phase-outs (specified service trades or businesses - SSTBs)
QBI_PHASEOUT: Dict[FilingStatus, tuple] = {
    FilingStatus.SINGLE: (191_950, 241_950),
    FilingStatus.MARRIED_FILING_JOINTLY: (383_900, 483_900),
    FilingStatus.MARRIED_FILING_SEPARATELY: (191_950, 241_950),
    FilingStatus.HEAD_OF_HOUSEHOLD: (191_950, 241_950),
    FilingStatus.QUALIFYING_SURVIVING_SPOUSE: (383_900, 483_900),
}


@dataclass
class DeductionItem:
    """A single deduction item."""

    deduction_type: DeductionType
    amount: float
    description: str = ""
    is_above_the_line: bool = False
    applied_amount: float = 0.0
    limitation_note: Optional[str] = None


@dataclass
class DeductionResult:
    """Result of deduction optimization analysis."""

    filing_status: FilingStatus
    agi: float

    # Standard vs itemized
    standard_deduction: float = 0.0
    itemized_deduction: float = 0.0
    recommended_method: str = "standard"
    tax_benefit_difference: float = 0.0

    # Above-the-line adjustments
    above_the_line_total: float = 0.0
    above_the_line_items: List[DeductionItem] = field(default_factory=list)

    # Itemized breakdown
    itemized_items: List[DeductionItem] = field(default_factory=list)

    # QBI
    qbi_deduction: float = 0.0

    # Total recommended deduction
    recommended_deduction: float = 0.0

    # Optimization opportunities
    opportunities: List[str] = field(default_factory=list)


class DeductionOptimizer:
    """
    Analyzes and optimizes tax deductions for American taxpayers.

    Compares standard vs. itemized deductions, applies phase-out rules,
    calculates QBI deduction, and identifies optimization opportunities.
    """

    def __init__(self) -> None:
        """Initialize the deduction optimizer."""
        self._deduction_items: List[DeductionItem] = []

    def add_deduction(
        self,
        deduction_type: DeductionType,
        amount: float,
        description: str = "",
    ) -> None:
        """Add a potential deduction item."""
        is_above_the_line = deduction_type in {
            DeductionType.TRADITIONAL_IRA,
            DeductionType.STUDENT_LOAN_INTEREST,
            DeductionType.HSA_CONTRIBUTION,
            DeductionType.EDUCATOR_EXPENSES,
            DeductionType.SELF_EMPLOYED_HEALTH,
            DeductionType.SELF_EMPLOYED_SEP,
            DeductionType.MOVING_EXPENSES,
        }
        self._deduction_items.append(
            DeductionItem(
                deduction_type=deduction_type,
                amount=amount,
                description=description,
                is_above_the_line=is_above_the_line,
            )
        )

    def optimize(
        self,
        agi: float,
        filing_status: FilingStatus = FilingStatus.SINGLE,
        age: int = 40,
        has_hsa_family_plan: bool = False,
        qbi_income: float = 0.0,
        is_sstb: bool = False,
        has_workplace_retirement_plan: bool = False,
        marginal_rate: float = 0.22,
    ) -> DeductionResult:
        """
        Run deduction optimization analysis.

        Args:
            agi: Adjusted gross income (before deductions).
            filing_status: IRS filing status.
            age: Taxpayer's age (affects IRA catch-up, etc.).
            has_hsa_family_plan: Whether HSA is family (vs self-only) coverage.
            qbi_income: Qualified business income for §199A deduction.
            is_sstb: Whether the business is a specified service trade/business.
            has_workplace_retirement_plan: Affects IRA deductibility.
            marginal_rate: Marginal tax rate for benefit calculations.

        Returns:
            DeductionResult with optimization recommendations.
        """
        result = DeductionResult(filing_status=filing_status, agi=agi)
        result.standard_deduction = STANDARD_DEDUCTIONS[filing_status]

        # --- Above-the-line deductions ---
        above_items = [i for i in self._deduction_items if i.is_above_the_line]
        result.above_the_line_items = self._process_above_the_line(
            above_items, agi, filing_status, age, has_workplace_retirement_plan, has_hsa_family_plan
        )
        result.above_the_line_total = sum(i.applied_amount for i in result.above_the_line_items)

        # Recalculate AGI after above-the-line
        adjusted_agi = max(0.0, agi - result.above_the_line_total)

        # --- Itemized deductions ---
        itemized_items = [i for i in self._deduction_items if not i.is_above_the_line]
        result.itemized_items = self._process_itemized(itemized_items, adjusted_agi)
        result.itemized_deduction = sum(i.applied_amount for i in result.itemized_items)

        # --- Compare standard vs itemized ---
        if result.itemized_deduction > result.standard_deduction:
            result.recommended_method = "itemized"
            result.recommended_deduction = result.itemized_deduction
            result.tax_benefit_difference = (
                result.itemized_deduction - result.standard_deduction
            ) * marginal_rate
        else:
            result.recommended_method = "standard"
            result.recommended_deduction = result.standard_deduction
            result.tax_benefit_difference = 0.0

        # --- QBI deduction (§199A) ---
        if qbi_income > 0:
            result.qbi_deduction = self._calculate_qbi(
                qbi_income, adjusted_agi, filing_status, is_sstb
            )

        # --- Opportunities ---
        result.opportunities = self._identify_opportunities(
            agi, filing_status, age, has_hsa_family_plan, has_workplace_retirement_plan, result
        )

        return result

    def clear(self) -> None:
        """Clear all deduction items."""
        self._deduction_items.clear()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _process_above_the_line(
        self,
        items: List[DeductionItem],
        agi: float,
        filing_status: FilingStatus,
        age: int,
        has_workplace_plan: bool,
        has_hsa_family_plan: bool,
    ) -> List[DeductionItem]:
        """Apply limits and phase-outs to above-the-line deductions."""
        processed: List[DeductionItem] = []

        for item in items:
            applied = item.amount
            note = None

            if item.deduction_type == DeductionType.TRADITIONAL_IRA:
                limit = IRA_LIMIT_50_PLUS if age >= 50 else IRA_LIMIT_UNDER_50
                applied = min(applied, limit)
                if has_workplace_plan:
                    applied = self._apply_phaseout(applied, agi, *IRA_PHASEOUT[filing_status])
                    if applied < item.amount:
                        note = f"IRA deduction phased out based on AGI (${agi:,.0f})"

            elif item.deduction_type == DeductionType.STUDENT_LOAN_INTEREST:
                applied = min(applied, STUDENT_LOAN_LIMIT)
                if filing_status == FilingStatus.MARRIED_FILING_SEPARATELY:
                    applied = 0.0
                    note = "Student loan interest not allowed for MFS"
                else:
                    applied = self._apply_phaseout(
                        applied, agi, *STUDENT_LOAN_PHASEOUT[filing_status]
                    )

            elif item.deduction_type == DeductionType.HSA_CONTRIBUTION:
                limit = (
                    (HSA_FAMILY + (HSA_CATCH_UP if age >= 55 else 0))
                    if has_hsa_family_plan
                    else (HSA_SELF_ONLY + (HSA_CATCH_UP if age >= 55 else 0))
                )
                applied = min(applied, limit)
                if applied < item.amount:
                    note = f"HSA limited to ${limit:,.0f}"

            elif item.deduction_type == DeductionType.EDUCATOR_EXPENSES:
                applied = min(applied, 300.0)

            processed_item = DeductionItem(
                deduction_type=item.deduction_type,
                amount=item.amount,
                description=item.description,
                is_above_the_line=True,
                applied_amount=round(applied, 2),
                limitation_note=note,
            )
            processed.append(processed_item)

        return processed

    def _process_itemized(self, items: List[DeductionItem], agi: float) -> List[DeductionItem]:
        """Apply limits to itemized deductions (Schedule A)."""
        processed: List[DeductionItem] = []
        salt_used = 0.0

        for item in items:
            applied = item.amount
            note = None

            if item.deduction_type in (
                DeductionType.STATE_LOCAL_TAX,
                DeductionType.PROPERTY_TAX,
            ):
                remaining_salt = max(0.0, SALT_CAP - salt_used)
                applied = min(applied, remaining_salt)
                salt_used += applied
                if applied < item.amount:
                    note = f"SALT capped at ${SALT_CAP:,.0f} combined"

            elif item.deduction_type == DeductionType.MEDICAL_EXPENSES:
                threshold = agi * MEDICAL_THRESHOLD_RATE
                applied = max(0.0, applied - threshold)
                if applied < item.amount:
                    note = f"Medical deduction reduced by 7.5% AGI floor (${threshold:,.0f})"

            elif item.deduction_type == DeductionType.CHARITABLE_CASH:
                limit = agi * CHARITABLE_CASH_LIMIT
                applied = min(applied, limit)
                if applied < item.amount:
                    note = f"Cash charitable deduction limited to 60% of AGI (${limit:,.0f})"

            elif item.deduction_type == DeductionType.CHARITABLE_NONCASH:
                limit = agi * CHARITABLE_NONCASH_LIMIT
                applied = min(applied, limit)
                if applied < item.amount:
                    note = f"Non-cash charitable deduction limited to 30% of AGI (${limit:,.0f})"

            processed.append(
                DeductionItem(
                    deduction_type=item.deduction_type,
                    amount=item.amount,
                    description=item.description,
                    is_above_the_line=False,
                    applied_amount=round(applied, 2),
                    limitation_note=note,
                )
            )

        return processed

    def _apply_phaseout(
        self,
        amount: float,
        agi: float,
        phaseout_start: float,
        phaseout_end: float,
    ) -> float:
        """Apply linear phase-out to a deduction amount."""
        if phaseout_start == 0 and phaseout_end == 0:
            return 0.0
        if agi <= phaseout_start:
            return amount
        if agi >= phaseout_end:
            return 0.0
        reduction_rate = (agi - phaseout_start) / (phaseout_end - phaseout_start)
        return round(amount * (1 - reduction_rate), 2)

    def _calculate_qbi(
        self,
        qbi_income: float,
        agi: float,
        filing_status: FilingStatus,
        is_sstb: bool,
    ) -> float:
        """
        Calculate the Qualified Business Income deduction (IRC §199A).

        The deduction is generally 20% of QBI, subject to taxable income
        limitations and phase-outs for SSTBs.
        """
        phaseout_start, phaseout_end = QBI_PHASEOUT[filing_status]
        base_deduction = qbi_income * 0.20

        if is_sstb:
            if agi >= phaseout_end:
                return 0.0
            elif agi > phaseout_start:
                reduction = (agi - phaseout_start) / (phaseout_end - phaseout_start)
                base_deduction *= 1 - reduction

        return round(base_deduction, 2)

    def _identify_opportunities(
        self,
        agi: float,
        filing_status: FilingStatus,
        age: int,
        has_hsa_family_plan: bool,
        has_workplace_plan: bool,
        result: DeductionResult,
    ) -> List[str]:
        """Identify deduction optimization opportunities."""
        ops: List[str] = []

        # IRA contribution
        ira_items = [
            i
            for i in result.above_the_line_items
            if i.deduction_type == DeductionType.TRADITIONAL_IRA
        ]
        limit = IRA_LIMIT_50_PLUS if age >= 50 else IRA_LIMIT_UNDER_50
        if not ira_items or sum(i.applied_amount for i in ira_items) < limit:
            remaining = limit - sum(i.applied_amount for i in ira_items)
            if remaining > 0:
                ops.append(
                    f"You could contribute up to ${remaining:,.0f} more to a Traditional IRA "
                    f"(2024 limit: ${limit:,.0f})."
                )

        # HSA
        hsa_items = [
            i
            for i in result.above_the_line_items
            if i.deduction_type == DeductionType.HSA_CONTRIBUTION
        ]
        hsa_limit = (
            (HSA_FAMILY + (HSA_CATCH_UP if age >= 55 else 0))
            if has_hsa_family_plan
            else (HSA_SELF_ONLY + (HSA_CATCH_UP if age >= 55 else 0))
        )
        if not hsa_items or sum(i.applied_amount for i in hsa_items) < hsa_limit:
            remaining = hsa_limit - sum(i.applied_amount for i in hsa_items)
            if remaining > 0:
                ops.append(f"Maximize HSA contributions: ${remaining:,.0f} remaining for 2024.")

        # Charitable bunching
        if result.recommended_method == "standard":
            ops.append(
                "Consider 'bunching' charitable contributions into one year to exceed "
                "the standard deduction and itemize, then take the standard deduction "
                "in alternate years."
            )

        # QBI optimization
        if result.qbi_deduction > 0:
            ops.append(
                f"Your QBI deduction is ${result.qbi_deduction:,.0f}. Consider "
                "consulting a tax professional about entity structure optimization."
            )

        return ops

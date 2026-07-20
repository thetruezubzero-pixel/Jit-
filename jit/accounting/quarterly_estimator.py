"""
Quarterly estimated tax payment calculator.

Implements IRS safe harbor rules and annualized income installment method
per Form 2210 for computing quarterly estimated tax payment requirements.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from jit.accounting.tax_calculator import FilingStatus

# 2024 Underpayment penalty rate (approximately; varies by quarter)
UNDERPAYMENT_PENALTY_RATE = 0.08  # 8% annualized (Fed funds + 3 pp)

# Safe harbor thresholds
PRIOR_YEAR_AGI_HIGH_INCOME_THRESHOLD = 150_000  # Prior year AGI
SAFE_HARBOR_HIGH_INCOME_RATE = 1.10  # 110% of prior year tax
SAFE_HARBOR_NORMAL_RATE = 1.00  # 100% of prior year tax
CURRENT_YEAR_SAFE_HARBOR = 0.90  # 90% of current year tax

# 2024 Quarterly due dates
QUARTERLY_DUE_DATES = {
    1: "April 15, 2024",  # Q1: Jan 1 – Mar 31
    2: "June 17, 2024",  # Q2: Apr 1 – May 31
    3: "September 16, 2024",  # Q3: Jun 1 – Aug 31
    4: "January 15, 2025",  # Q4: Sep 1 – Dec 31
}

# Withholding percentage applied per quarter (cumulative)
QUARTERLY_CUMULATIVE_PCTS = {1: 0.25, 2: 0.50, 3: 0.75, 4: 1.00}


@dataclass
class QuarterlyPayment:
    """Quarterly estimated tax payment details."""

    quarter: int
    due_date: str
    required_payment: float
    annualized_income: float
    cumulative_tax: float
    prior_period_payments: float
    underpayment: float = 0.0
    overpayment: float = 0.0
    is_safe_harbor_met: bool = True
    notes: List[str] = field(default_factory=list)


@dataclass
class QuarterlyEstimate:
    """Full quarterly estimated tax analysis for the year."""

    tax_year: int
    filing_status: FilingStatus
    expected_total_tax: float
    prior_year_tax: float
    prior_year_agi: float

    safe_harbor_amount: float = 0.0  # Minimum to avoid penalty
    current_year_safe_harbor: float = 0.0  # 90% of current year

    quarterly_payments: List[QuarterlyPayment] = field(default_factory=list)
    total_required: float = 0.0
    total_withholding: float = 0.0
    remaining_to_pay: float = 0.0

    potential_penalty: float = 0.0
    recommendations: List[str] = field(default_factory=list)


class QuarterlyEstimator:
    """
    Calculates quarterly estimated tax payments using IRS safe harbor rules.

    Applies both the prior-year safe harbor method (100%/110% of prior year
    tax) and the current-year method (90% of current year tax), and
    identifies which method requires lower payments.
    """

    def __init__(self, tax_year: int = 2024) -> None:
        """Initialize quarterly estimator."""
        self.tax_year = tax_year

    def estimate(
        self,
        expected_total_tax: float,
        prior_year_tax: float,
        prior_year_agi: float,
        filing_status: FilingStatus = FilingStatus.SINGLE,
        w2_withholding: float = 0.0,
        quarterly_income: Optional[Dict[int, float]] = None,
    ) -> QuarterlyEstimate:
        """
        Calculate quarterly estimated tax payment schedule.

        Args:
            expected_total_tax: Estimated current year total tax liability.
            prior_year_tax: Actual prior year federal income tax paid.
            prior_year_agi: Prior year adjusted gross income.
            filing_status: IRS filing status.
            w2_withholding: Expected W-2 withholding for the year.
            quarterly_income: Dict mapping quarter (1-4) to income earned that quarter.

        Returns:
            QuarterlyEstimate with payment schedule and safe harbor analysis.
        """
        # --- Safe harbor amounts ---
        safe_harbor_rate = (
            SAFE_HARBOR_HIGH_INCOME_RATE
            if prior_year_agi > PRIOR_YEAR_AGI_HIGH_INCOME_THRESHOLD
            else SAFE_HARBOR_NORMAL_RATE
        )
        safe_harbor_total = prior_year_tax * safe_harbor_rate
        current_year_safe_harbor = expected_total_tax * CURRENT_YEAR_SAFE_HARBOR

        # Use the lower of the two methods
        min_required = min(safe_harbor_total, current_year_safe_harbor)

        # Net of withholding
        net_required = max(0.0, min_required - w2_withholding)

        # --- Per-quarter payments ---
        payments: List[QuarterlyPayment] = []
        cumulative_paid = 0.0

        for q in range(1, 5):
            pct = QUARTERLY_CUMULATIVE_PCTS[q]
            cumulative_required = net_required * pct
            quarter_payment = cumulative_required - cumulative_paid

            # underpayment/overpayment/is_safe_harbor_met deliberately assume
            # no estimated payments have actually been made yet beyond
            # withholding — a conservative "if you do nothing further from
            # here, you're behind by this much" planning signal, not a
            # tracker of payments the filer has actually made (there's no
            # input for that). This must be computed before cumulative_paid
            # advances to this quarter's cumulative_required below, or both
            # sides of the comparison become equal and these are trivially
            # always zero regardless of any real shortfall.
            underpayment = max(0.0, cumulative_required - cumulative_paid)
            overpayment = max(0.0, cumulative_paid - cumulative_required) if q > 1 else 0.0

            cumulative_paid = cumulative_required

            # Annualized income for this quarter (if provided)
            annualized = 0.0
            if quarterly_income:
                q_income = quarterly_income.get(q, 0.0)
                annualized = q_income * (4 / q)  # Simple annualization

            notes: List[str] = []
            if q == 4:
                notes.append(
                    "Q4 payment due January 15 of the following year. "
                    "Filing tax return by January 31 eliminates this payment."
                )

            payments.append(
                QuarterlyPayment(
                    quarter=q,
                    due_date=QUARTERLY_DUE_DATES[q],
                    required_payment=round(max(0.0, quarter_payment), 2),
                    annualized_income=round(annualized, 2),
                    cumulative_tax=round(cumulative_required, 2),
                    prior_period_payments=round(cumulative_paid - quarter_payment, 2),
                    underpayment=round(underpayment, 2),
                    overpayment=round(overpayment, 2),
                    is_safe_harbor_met=underpayment <= 0.01,
                    notes=notes,
                )
            )

        # --- Penalty estimate if safe harbor not met ---
        shortfall = max(0.0, min_required - w2_withholding)
        penalty = 0.0
        if shortfall > 1_000:  # De minimis threshold
            penalty = shortfall * UNDERPAYMENT_PENALTY_RATE * 0.25  # Rough estimate

        recs = self._build_recommendations(
            expected_total_tax,
            safe_harbor_total,
            current_year_safe_harbor,
            w2_withholding,
            filing_status,
        )

        return QuarterlyEstimate(
            tax_year=self.tax_year,
            filing_status=filing_status,
            expected_total_tax=round(expected_total_tax, 2),
            prior_year_tax=round(prior_year_tax, 2),
            prior_year_agi=round(prior_year_agi, 2),
            safe_harbor_amount=round(safe_harbor_total, 2),
            current_year_safe_harbor=round(current_year_safe_harbor, 2),
            quarterly_payments=payments,
            total_required=round(net_required, 2),
            total_withholding=round(w2_withholding, 2),
            remaining_to_pay=round(net_required, 2),
            potential_penalty=round(penalty, 2),
            recommendations=recs,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_recommendations(
        self,
        expected_tax: float,
        safe_harbor: float,
        current_year_sh: float,
        withholding: float,
        filing_status: FilingStatus,
    ) -> List[str]:
        """Build recommendations for estimated tax payments."""
        recs: List[str] = []

        if withholding >= min(safe_harbor, current_year_sh):
            recs.append(
                "Your W-2 withholding is sufficient to meet safe harbor requirements. "
                "No estimated tax payments may be required."
            )
        else:
            shortfall = min(safe_harbor, current_year_sh) - withholding
            recs.append(
                f"You need to make estimated tax payments totaling approximately "
                f"${shortfall:,.0f} to avoid underpayment penalties."
            )

        if expected_tax > 1_000:
            recs.append(
                "Consider increasing W-2 withholding (Form W-4) to cover tax on "
                "self-employment or investment income and simplify estimated payments."
            )

        recs.append(
            f"Pay via IRS Direct Pay at irs.gov/payments or EFTPS.gov. "
            f"Payments are due: {', '.join(QUARTERLY_DUE_DATES.values())}."
        )

        return recs

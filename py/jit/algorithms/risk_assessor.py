"""
Risk assessment engine for tax and legal scenarios.

Evaluates audit probability, penalty exposure, legal risk, and
compliance risk scores for individual and business situations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class RiskCategory(str, Enum):
    """Category of risk being assessed."""

    AUDIT_RISK = "audit_risk"
    PENALTY_RISK = "penalty_risk"
    LEGAL_RISK = "legal_risk"
    COMPLIANCE_RISK = "compliance_risk"
    FINANCIAL_RISK = "financial_risk"


@dataclass
class RiskFactor:
    """A single risk factor contributing to overall risk."""

    category: RiskCategory
    factor_id: str
    description: str
    risk_contribution: float  # 0.0 to 1.0
    is_present: bool
    mitigation: Optional[str] = None
    regulatory_citation: Optional[str] = None


@dataclass
class RiskProfile:
    """Comprehensive risk profile for a taxpayer or legal scenario."""

    scenario: str
    factors: List[RiskFactor] = field(default_factory=list)

    # Overall scores
    audit_risk_score: float = 0.0  # 0.0 (minimal) to 1.0 (very high)
    penalty_risk_score: float = 0.0
    legal_risk_score: float = 0.0
    overall_risk_score: float = 0.0

    # Qualitative rating
    audit_risk_rating: str = "Low"
    overall_risk_rating: str = "Low"

    recommendations: List[str] = field(default_factory=list)
    estimated_audit_probability: float = 0.0  # Statistical probability 0-1

    @property
    def present_factors(self) -> List[RiskFactor]:
        """Return only the risk factors that are present."""
        return [f for f in self.factors if f.is_present]


# IRS audit rate statistics by income level (approximate 2022 data)
# Source: IRS Data Book 2022
AUDIT_BASE_RATES: Dict[str, float] = {
    "under_25k": 0.0025,
    "25k_to_75k": 0.0015,
    "75k_to_200k": 0.0020,
    "200k_to_500k": 0.0060,
    "500k_to_1m": 0.0110,
    "1m_to_5m": 0.0200,
    "over_5m": 0.0900,
}

# Schedule C audit rate premium
SCHEDULE_C_MULTIPLIER = 3.5
# EITC audit rate premium
EITC_MULTIPLIER = 2.0
# High deduction ratio premium
HIGH_DEDUCTION_MULTIPLIER = 2.0
# Foreign income premium
FOREIGN_INCOME_MULTIPLIER = 2.5


class RiskAssessor:
    """
    Assesses audit and compliance risk for tax and legal scenarios.

    Uses statistical audit rates, known IRS audit triggers, and
    compliance risk factors to generate a comprehensive risk profile.
    """

    def assess_individual_tax(
        self,
        agi: float,
        has_schedule_c: bool = False,
        schedule_c_income: float = 0.0,
        claimed_eitc: bool = False,
        deduction_to_income_ratio: float = 0.0,
        has_foreign_income: bool = False,
        has_crypto_transactions: bool = False,
        claimed_home_office: bool = False,
        claimed_large_charitable: bool = False,
        large_charitable_pct: float = 0.0,
        claimed_large_business_meals: bool = False,
        prior_audit_years: int = 0,
        has_mathematical_errors: bool = False,
        filed_late: bool = False,
        has_unreported_income: bool = False,
        has_substantial_understatement: bool = False,
    ) -> RiskProfile:
        """
        Assess individual income tax audit and compliance risk.

        Args:
            agi: Adjusted gross income.
            has_schedule_c: Whether a Schedule C was filed.
            schedule_c_income: Schedule C gross income.
            claimed_eitc: Whether EITC was claimed.
            deduction_to_income_ratio: Total deductions as fraction of income.
            has_foreign_income: Foreign income reported.
            has_crypto_transactions: Virtual currency transactions.
            claimed_home_office: Home office deduction claimed.
            claimed_large_charitable: Large charitable deductions claimed.
            large_charitable_pct: Charitable deductions as % of AGI.
            claimed_large_business_meals: Business meal deductions claimed.
            prior_audit_years: Number of prior years audited.
            has_mathematical_errors: Mathematical errors on return.
            filed_late: Return filed after deadline.
            has_unreported_income: Known unreported income.
            has_substantial_understatement: Tax understated by >10% or $5k.

        Returns:
            RiskProfile with audit probability and risk factors.
        """
        factors: List[RiskFactor] = []

        # --- Base audit rate ---
        base_rate = self._get_base_audit_rate(agi)

        # --- Build risk factors ---

        # Schedule C
        factors.append(
            RiskFactor(
                category=RiskCategory.AUDIT_RISK,
                factor_id="schedule_c",
                description="Schedule C (self-employment) filed — higher IRS scrutiny",
                risk_contribution=0.35 if has_schedule_c else 0.0,
                is_present=has_schedule_c,
                mitigation="Keep detailed receipts and records for all business expenses",
                regulatory_citation="IRS Publication 583; Treas. Reg. § 1.183-2",
            )
        )

        # EITC
        factors.append(
            RiskFactor(
                category=RiskCategory.AUDIT_RISK,
                factor_id="eitc",
                description="Earned Income Tax Credit (EITC) claimed — high error rate category",
                risk_contribution=0.25 if claimed_eitc else 0.0,
                is_present=claimed_eitc,
                mitigation="Verify eligibility per Form 8862 requirements; retain documentation",
                regulatory_citation="IRC § 32; Rev. Proc. 2012-48",
            )
        )

        # High deduction ratio
        high_deductions = deduction_to_income_ratio > 0.35
        factors.append(
            RiskFactor(
                category=RiskCategory.AUDIT_RISK,
                factor_id="high_deductions",
                description=f"Deduction-to-income ratio ({deduction_to_income_ratio:.0%}) is high",
                risk_contribution=0.30 if high_deductions else 0.0,
                is_present=high_deductions,
                mitigation="Ensure all deductions are properly documented and legitimate",
            )
        )

        # Foreign income/accounts
        factors.append(
            RiskFactor(
                category=RiskCategory.COMPLIANCE_RISK,
                factor_id="foreign_income",
                description="Foreign income or assets reported — additional scrutiny",
                risk_contribution=0.40 if has_foreign_income else 0.0,
                is_present=has_foreign_income,
                mitigation="Ensure FBAR, Form 8938, and Form 5471/8621 filed if applicable",
                regulatory_citation="IRC § 6038; 31 U.S.C. § 5314",
            )
        )

        # Crypto
        factors.append(
            RiskFactor(
                category=RiskCategory.COMPLIANCE_RISK,
                factor_id="crypto",
                description="Virtual currency transactions — IRS virtual currency question on 1040",
                risk_contribution=0.25 if has_crypto_transactions else 0.0,
                is_present=has_crypto_transactions,
                mitigation=(
                    "Report all crypto transactions on Form 8949; answer virtual currency question"
                ),
                regulatory_citation="IRS Notice 2014-21; Rev. Rul. 2019-24",
            )
        )

        # Home office
        factors.append(
            RiskFactor(
                category=RiskCategory.AUDIT_RISK,
                factor_id="home_office",
                description="Home office deduction claimed (regular exclusive use required)",
                risk_contribution=0.20 if claimed_home_office else 0.0,
                is_present=claimed_home_office,
                mitigation="Use simplified method or document exclusive business use area",
                regulatory_citation="IRC § 280A; Treas. Reg. § 1.280A-2",
            )
        )

        # Large charitable donations
        high_charitable = large_charitable_pct > 0.30
        factors.append(
            RiskFactor(
                category=RiskCategory.AUDIT_RISK,
                factor_id="large_charitable",
                description=f"Large charitable deductions ({large_charitable_pct:.0%} of AGI)",
                risk_contribution=0.25 if high_charitable else 0.0,
                is_present=high_charitable,
                mitigation=(
                    "Retain written acknowledgment for gifts $250+; "
                    "non-cash donations $500+ require Form 8283"
                ),
                regulatory_citation="IRC § 170(f)(8); Treas. Reg. § 1.170A-13",
            )
        )

        # Penalty risk factors

        # Unreported income
        factors.append(
            RiskFactor(
                category=RiskCategory.PENALTY_RISK,
                factor_id="unreported_income",
                description="Potential unreported income — civil and criminal penalty risk",
                risk_contribution=1.0 if has_unreported_income else 0.0,
                is_present=has_unreported_income,
                mitigation=(
                    "File amended return (Form 1040-X) and consider IRS Voluntary Disclosure "
                    "Program to limit criminal exposure"
                ),
                regulatory_citation="IRC § 7201; IRC § 6663",
            )
        )

        # Substantial understatement
        factors.append(
            RiskFactor(
                category=RiskCategory.PENALTY_RISK,
                factor_id="substantial_understatement",
                description="Substantial understatement of income tax (>10% or $5,000)",
                risk_contribution=0.60 if has_substantial_understatement else 0.0,
                is_present=has_substantial_understatement,
                mitigation="Ensure positions have 'substantial authority' (IRC § 6662(d)(2)(B))",
                regulatory_citation="IRC § 6662(b)(2); IRC § 6662(d)",
            )
        )

        # Mathematical errors
        factors.append(
            RiskFactor(
                category=RiskCategory.COMPLIANCE_RISK,
                factor_id="math_errors",
                description="Mathematical errors trigger automatic IRS review",
                risk_contribution=0.15 if has_mathematical_errors else 0.0,
                is_present=has_mathematical_errors,
                mitigation="Review return thoroughly; use tax software to check calculations",
            )
        )

        # Late filing
        factors.append(
            RiskFactor(
                category=RiskCategory.PENALTY_RISK,
                factor_id="late_filing",
                description="Return filed after deadline — failure-to-file penalty applies",
                risk_contribution=0.20 if filed_late else 0.0,
                is_present=filed_late,
                mitigation=(
                    "File immediately; consider requesting penalty abatement for first-time penalty"
                ),
                regulatory_citation="IRC § 6651(a)(1)",
            )
        )

        # --- Compute scores ---
        audit_score = self._compute_audit_score(factors, base_rate)
        penalty_score = self._compute_category_score(factors, RiskCategory.PENALTY_RISK)
        compliance_score = self._compute_category_score(factors, RiskCategory.COMPLIANCE_RISK)
        overall_score = audit_score * 0.4 + penalty_score * 0.35 + compliance_score * 0.25

        # Estimated audit probability
        audit_prob = base_rate
        for f in factors:
            if f.is_present and f.category == RiskCategory.AUDIT_RISK:
                audit_prob = min(audit_prob * (1 + f.risk_contribution * 2), 0.50)

        recs = self._build_recommendations(factors, overall_score)
        audit_rating = self._rating(audit_score)
        overall_rating = self._rating(overall_score)

        return RiskProfile(
            scenario=f"Individual tax risk assessment (AGI: ${agi:,.0f})",
            factors=factors,
            audit_risk_score=round(audit_score, 3),
            penalty_risk_score=round(penalty_score, 3),
            legal_risk_score=0.0,
            overall_risk_score=round(overall_score, 3),
            audit_risk_rating=audit_rating,
            overall_risk_rating=overall_rating,
            recommendations=recs,
            estimated_audit_probability=round(audit_prob, 4),
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _get_base_audit_rate(self, agi: float) -> float:
        """Return the statistical base audit rate for the given AGI."""
        if agi < 25_000:
            return AUDIT_BASE_RATES["under_25k"]
        elif agi < 75_000:
            return AUDIT_BASE_RATES["25k_to_75k"]
        elif agi < 200_000:
            return AUDIT_BASE_RATES["75k_to_200k"]
        elif agi < 500_000:
            return AUDIT_BASE_RATES["200k_to_500k"]
        elif agi < 1_000_000:
            return AUDIT_BASE_RATES["500k_to_1m"]
        elif agi < 5_000_000:
            return AUDIT_BASE_RATES["1m_to_5m"]
        else:
            return AUDIT_BASE_RATES["over_5m"]

    def _compute_audit_score(self, factors: List[RiskFactor], base_rate: float) -> float:
        """Compute normalized audit risk score."""
        audit_factors = [
            f for f in factors if f.category == RiskCategory.AUDIT_RISK and f.is_present
        ]
        if not audit_factors:
            return min(base_rate * 10, 0.15)  # Normalize base rate to 0-1 scale
        total = sum(f.risk_contribution for f in audit_factors)
        return min(total, 1.0)

    def _compute_category_score(self, factors: List[RiskFactor], category: RiskCategory) -> float:
        """Compute risk score for a specific category."""
        cat_factors = [f for f in factors if f.category == category and f.is_present]
        if not cat_factors:
            return 0.0
        return min(sum(f.risk_contribution for f in cat_factors), 1.0)

    def _rating(self, score: float) -> str:
        """Convert numerical score to qualitative rating."""
        if score < 0.15:
            return "Low"
        elif score < 0.35:
            return "Moderate"
        elif score < 0.60:
            return "High"
        else:
            return "Very High"

    def _build_recommendations(self, factors: List[RiskFactor], overall_score: float) -> List[str]:
        """Build risk mitigation recommendations."""
        recs: List[str] = []
        present = [f for f in factors if f.is_present]

        if overall_score > 0.5:
            recs.append(
                "IMPORTANT: Your risk profile indicates elevated audit/penalty risk. "
                "Consider consulting a CPA or enrolled agent before filing."
            )

        for factor in present:
            if factor.mitigation:
                recs.append(f"[{factor.factor_id}] {factor.mitigation}")

        if not present:
            recs.append(
                "Your risk profile appears clean. Continue maintaining good records "
                "and filing accurately and on time."
            )

        return recs

"""
Compliance verification engine.

Checks financial and legal scenarios against regulatory requirements,
generates compliance reports, and flags potential violations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


class ComplianceArea(str, Enum):
    """Area of compliance being checked."""

    FEDERAL_TAX = "federal_tax"
    STATE_TAX = "state_tax"
    FBAR = "fbar"  # FinCEN Form 114
    FATCA = "fatca"  # Foreign Account Tax Compliance Act
    EMPLOYMENT = "employment"
    SECURITIES = "securities"
    AML = "aml"  # Anti-money laundering
    PRIVACY = "privacy"
    CONSUMER_PROTECTION = "consumer"
    CORPORATE = "corporate"


class RiskLevel(str, Enum):
    """Compliance risk severity."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class ComplianceIssue:
    """A single compliance issue or finding."""

    issue_id: str
    area: ComplianceArea
    risk_level: RiskLevel
    title: str
    description: str
    regulatory_basis: str  # Citation to rule/regulation
    recommended_action: str
    deadline: Optional[str] = None
    penalty_range: Optional[str] = None
    is_correctable: bool = True


@dataclass
class ComplianceResult:
    """Result of a compliance check."""

    scenario: str
    areas_checked: List[ComplianceArea]

    issues: List[ComplianceIssue] = field(default_factory=list)
    passed_checks: List[str] = field(default_factory=list)

    overall_risk: RiskLevel = RiskLevel.LOW
    compliance_score: float = 1.0  # 1.0 = fully compliant, 0.0 = critical failures

    summary: str = ""
    recommendations: List[str] = field(default_factory=list)

    @property
    def critical_issues(self) -> List[ComplianceIssue]:
        """Return only critical-level issues."""
        return [i for i in self.issues if i.risk_level == RiskLevel.CRITICAL]

    @property
    def high_issues(self) -> List[ComplianceIssue]:
        """Return high-risk issues."""
        return [i for i in self.issues if i.risk_level == RiskLevel.HIGH]

    @property
    def is_compliant(self) -> bool:
        """Return True if no critical issues found."""
        return len(self.critical_issues) == 0


# FBAR thresholds
FBAR_THRESHOLD = 10_000  # Aggregate value of foreign accounts

# FATCA thresholds (unmarried, filing as single)
FATCA_THRESHOLD_DOMESTIC = 50_000  # Year-end balance or
FATCA_THRESHOLD_DOMESTIC_YEAR = 75_000  # At any point during year
FATCA_THRESHOLD_ABROAD = 200_000
FATCA_THRESHOLD_ABROAD_YEAR = 300_000

# AMT small business exemption (C-Corp)
AMT_SMALL_BUSINESS_EXEMPTION = 29_000_000  # Average gross receipts

# 1099 filing threshold
FORM_1099_THRESHOLD = 600  # For miscellaneous income
FORM_1099_NEC_THRESHOLD = 600

# Late filing penalties (2024)
LATE_FILING_PENALTY_RATE = 0.05  # 5% per month, up to 25%
LATE_PAYMENT_PENALTY_RATE = 0.005  # 0.5% per month, up to 25%

# FBAR penalties
FBAR_NON_WILLFUL_MAX = 10_000
FBAR_WILLFUL_MAX = 100_000  # Or 50% of account value, whichever is greater


class ComplianceEngine:
    """
    Verifies compliance with federal tax and financial regulations.

    Checks for common compliance issues including:
    - Federal and state tax filing obligations
    - FBAR/FATCA foreign account reporting
    - 1099 filing requirements
    - Employment tax compliance
    - Estimated tax payment obligations
    """

    def check_individual_tax_compliance(
        self,
        gross_income: float,
        tax_year: int,
        filing_status_str: str,
        taxes_withheld: Optional[float],
        taxes_paid: Optional[float],
        has_foreign_accounts: bool = False,
        max_foreign_account_balance: float = 0.0,
        aggregate_foreign_balance: float = 0.0,
        has_foreign_assets: float = 0.0,
        self_employment_income: float = 0.0,
        received_1099s: bool = False,
        issued_1099s_required: int = 0,
        issued_1099s_filed: int = 0,
    ) -> ComplianceResult:
        """
        Check individual taxpayer compliance.

        Args:
            gross_income: Total gross income.
            tax_year: Tax year being checked.
            filing_status_str: Filing status string.
            taxes_withheld: Federal taxes already withheld, or None if unknown
                (the underpayment check is skipped rather than treating
                unknown as $0, which would falsely flag every sufficiently
                high income as underpaid).
            taxes_paid: Estimated taxes already paid, or None if unknown
                (same handling as taxes_withheld).
            has_foreign_accounts: Whether taxpayer has foreign financial accounts.
            max_foreign_account_balance: Highest balance in any single foreign account.
            aggregate_foreign_balance: Sum of all foreign account balances.
            has_foreign_assets: Value of foreign assets for FATCA.
            self_employment_income: Net self-employment income.
            received_1099s: Whether taxpayer received 1099s that must be reported.
            issued_1099s_required: Number of 1099s taxpayer was required to issue.
            issued_1099s_filed: Number of 1099s taxpayer actually filed.

        Returns:
            ComplianceResult with all findings.
        """
        issues: List[ComplianceIssue] = []
        passed: List[str] = []
        areas = [ComplianceArea.FEDERAL_TAX]

        # --- Filing requirement check ---
        filing_threshold = self._get_filing_threshold(filing_status_str, tax_year)
        if gross_income >= filing_threshold:
            passed.append(f"Filing required: gross income ${gross_income:,.0f} exceeds threshold")
        else:
            passed.append(
                f"Filing may not be required: income below ${filing_threshold:,.0f} threshold"
            )

        # --- Estimated tax / underpayment check ---
        # Only run this when withholding/payments are actually known. Some
        # callers (the cross-module platform.py pipeline, which has no
        # source for this data) used to pass 0.0 as a stand-in for "unknown"
        # -- indistinguishable from a real $0, which meant every case with
        # gross income above ~$6,667 (min_required > $1,000) was
        # unconditionally flagged as underpaid, regardless of what was
        # actually withheld.
        if taxes_withheld is None or taxes_paid is None:
            passed.append(
                "Estimated tax payment status not checked (withholding/payments not provided)"
            )
        else:
            total_paid = taxes_withheld + taxes_paid
            min_required = gross_income * 0.15  # Very rough proxy
            if total_paid < min_required and gross_income > 1_000:
                issues.append(
                    ComplianceIssue(
                        issue_id="underpayment_001",
                        area=ComplianceArea.FEDERAL_TAX,
                        risk_level=RiskLevel.MEDIUM,
                        title="Potential Underpayment of Estimated Taxes",
                        description=(
                            f"Total taxes paid (${total_paid:,.0f}) may be insufficient. "
                            "IRS requires paying at least 90% of current year tax or "
                            "100%/110% of prior year tax."
                        ),
                        regulatory_basis="IRC § 6654; IRS Form 2210",
                        recommended_action=(
                            "Calculate estimated tax using Form 1040-ES and pay any shortfall. "
                            "Increase W-4 withholding if possible."
                        ),
                        penalty_range="0.5% per month on underpaid amount",
                    )
                )
            else:
                passed.append("Estimated tax payments appear adequate")

        # --- FBAR check ---
        if has_foreign_accounts:
            areas.append(ComplianceArea.FBAR)
            if aggregate_foreign_balance > FBAR_THRESHOLD:
                issues.append(
                    ComplianceIssue(
                        issue_id="fbar_001",
                        area=ComplianceArea.FBAR,
                        risk_level=RiskLevel.HIGH,
                        title="FBAR Filing Required",
                        description=(
                            f"Aggregate foreign account balance "
                            f"(${aggregate_foreign_balance:,.0f}) "
                            f"exceeds FBAR threshold (${FBAR_THRESHOLD:,.0f}). "
                            "FinCEN Form 114 must be filed by April 15."
                        ),
                        regulatory_basis="31 U.S.C. § 5314; 31 C.F.R. § 1010.350",
                        recommended_action=(
                            "File FinCEN Form 114 electronically at bsaefiling.fincen.treas.gov "
                            "by April 15 (automatic extension to October 15)."
                        ),
                        deadline="April 15 (auto-extended to October 15)",
                        penalty_range=(
                            f"Non-willful: up to ${FBAR_NON_WILLFUL_MAX:,}/year; "
                            f"Willful: up to ${FBAR_WILLFUL_MAX:,}/year or 50% of account value"
                        ),
                    )
                )
            else:
                passed.append("FBAR: Foreign account balance below reporting threshold")

        # --- FATCA check ---
        if has_foreign_assets > FATCA_THRESHOLD_DOMESTIC:
            areas.append(ComplianceArea.FATCA)
            issues.append(
                ComplianceIssue(
                    issue_id="fatca_001",
                    area=ComplianceArea.FATCA,
                    risk_level=RiskLevel.HIGH,
                    title="FATCA Reporting Required (Form 8938)",
                    description=(
                        f"Foreign financial assets (${has_foreign_assets:,.0f}) exceed "
                        f"FATCA threshold (${FATCA_THRESHOLD_DOMESTIC:,.0f}). "
                        "Form 8938 must be filed with your tax return."
                    ),
                    regulatory_basis="IRC § 6038D; 26 C.F.R. § 1.6038D-1",
                    recommended_action=(
                        "Attach Form 8938 (Statement of Specified Foreign Financial Assets) "
                        "to your Form 1040."
                    ),
                    penalty_range="$10,000 initial penalty; up to $50,000 for continued failure",
                )
            )

        # --- Self-employment tax ---
        if self_employment_income >= 400:
            areas.append(ComplianceArea.EMPLOYMENT)
            passed.append(
                f"Self-employment income (${self_employment_income:,.0f}) requires "
                "Schedule SE filing"
            )

        # --- 1099 issuance ---
        if issued_1099s_required > issued_1099s_filed:
            shortfall = issued_1099s_required - issued_1099s_filed
            issues.append(
                ComplianceIssue(
                    issue_id="1099_001",
                    area=ComplianceArea.FEDERAL_TAX,
                    risk_level=RiskLevel.MEDIUM,
                    title=f"Missing 1099 Filings ({shortfall} forms)",
                    description=(
                        f"{shortfall} required Form 1099(s) were not filed. "
                        "Businesses must issue 1099-NEC for payments to non-employees "
                        f"of ${FORM_1099_NEC_THRESHOLD}+ in the tax year."
                    ),
                    regulatory_basis="IRC § 6041; IRC § 6041A; Treas. Reg. § 1.6041-1",
                    recommended_action=(
                        "File missing 1099s immediately. Late filing penalties apply "
                        "per IRC § 6721."
                    ),
                    penalty_range="$60–$310 per form depending on lateness",
                )
            )

        # --- Compute overall risk ---
        overall_risk, score = self._compute_overall_risk(issues)

        summary = self._build_summary(issues, passed, overall_risk)
        recs = self._build_recommendations(issues, areas)

        return ComplianceResult(
            scenario=f"Individual tax compliance check for tax year {tax_year}",
            areas_checked=list(set(areas)),
            issues=issues,
            passed_checks=passed,
            overall_risk=overall_risk,
            compliance_score=round(score, 3),
            summary=summary,
            recommendations=recs,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _get_filing_threshold(self, filing_status: str, tax_year: int) -> float:
        """Return the gross income filing threshold for the given status."""
        thresholds = {
            "single": 13_850,
            "married_filing_jointly": 27_700,
            "married_filing_separately": 5,
            "head_of_household": 20_800,
            "qualifying_surviving_spouse": 27_700,
        }
        return thresholds.get(filing_status.lower(), 13_850)

    def _compute_overall_risk(self, issues: List[ComplianceIssue]) -> tuple:
        """Compute overall risk level and compliance score."""
        if not issues:
            return RiskLevel.LOW, 1.0

        risk_weights = {
            RiskLevel.LOW: 0.1,
            RiskLevel.MEDIUM: 0.3,
            RiskLevel.HIGH: 0.6,
            RiskLevel.CRITICAL: 1.0,
        }

        max_risk = max((i.risk_level for i in issues), key=lambda r: risk_weights[r])
        total_weight = sum(risk_weights[i.risk_level] for i in issues)
        score = max(0.0, 1.0 - min(total_weight / len(risk_weights), 1.0))

        return max_risk, score

    def _build_summary(
        self,
        issues: List[ComplianceIssue],
        passed: List[str],
        overall_risk: RiskLevel,
    ) -> str:
        """Generate a compliance summary."""
        if not issues:
            return (
                f"Compliance check passed. {len(passed)} checks passed with no issues identified."
            )
        return (
            f"Compliance check complete. Found {len(issues)} issue(s) "
            f"({sum(1 for i in issues if i.risk_level == RiskLevel.CRITICAL)} critical, "
            f"{sum(1 for i in issues if i.risk_level == RiskLevel.HIGH)} high). "
            f"Overall risk: {overall_risk.value.upper()}."
        )

    def _build_recommendations(
        self, issues: List[ComplianceIssue], areas: List[ComplianceArea]
    ) -> List[str]:
        """Build top-level recommendations from issues."""
        recs: List[str] = []
        if any(i.risk_level in (RiskLevel.CRITICAL, RiskLevel.HIGH) for i in issues):
            recs.append(
                "URGENT: Address all critical and high-risk compliance issues immediately. "
                "Consider consulting a tax attorney or CPA."
            )
        for issue in issues:
            recs.append(f"[{issue.risk_level.upper()}] {issue.title}: {issue.recommended_action}")
        return recs

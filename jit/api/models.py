"""
Pydantic request and response models for all API endpoints.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# -----------------------------------------------------------------------
# Accounting request/response models
# -----------------------------------------------------------------------

class TaxCalculationRequest(BaseModel):
    """Request body for tax calculation endpoint."""

    gross_income: float = Field(..., ge=0, description="Total gross income from all sources")
    filing_status: str = Field(
        "single",
        description="IRS filing status: single | married_filing_jointly | "
                    "married_filing_separately | head_of_household | qualifying_surviving_spouse",
    )
    tax_year: int = Field(2024, ge=2020, le=2030)
    adjustments: float = Field(0.0, ge=0, description="Above-the-line deductions")
    deductions: float = Field(0.0, ge=0, description="Itemized deductions (0 = use standard)")
    w2_wages: float = Field(0.0, ge=0, description="W-2 wages subject to FICA")
    self_employment_income: float = Field(0.0, ge=0, description="Net self-employment income")
    long_term_capital_gains: float = Field(0.0, ge=0, description="Net long-term capital gains")
    qualified_dividends: float = Field(0.0, ge=0, description="Qualified dividends")
    net_investment_income: float = Field(0.0, ge=0, description="Net investment income for NIIT")
    state_code: Optional[str] = Field(None, max_length=2, description="Two-letter state code")


class BracketDetailResponse(BaseModel):
    """Tax bracket detail in response."""

    rate: float
    bracket_income: float
    bracket_tax: float
    cumulative_tax: float


class TaxCalculationResponse(BaseModel):
    """Response from tax calculation endpoint."""

    filing_status: str
    tax_year: int
    gross_income: float
    adjusted_gross_income: float
    taxable_income: float
    federal_income_tax: float
    effective_federal_rate: float
    marginal_federal_rate: float
    bracket_details: List[BracketDetailResponse]
    social_security_tax: float
    medicare_tax: float
    additional_medicare_tax: float
    long_term_capital_gains_tax: float
    niit: float
    self_employment_tax: float
    total_federal_tax: float
    effective_total_rate: float
    state_tax: float
    state_code: Optional[str]
    total_tax: float
    recommendations: List[str]


class DeductionOptimizationRequest(BaseModel):
    """Request for deduction optimization."""

    agi: float = Field(..., ge=0, description="Adjusted gross income")
    filing_status: str = Field("single")
    age: int = Field(40, ge=0, le=130)
    has_hsa_family_plan: bool = False
    qbi_income: float = Field(0.0, ge=0)
    is_sstb: bool = False
    has_workplace_retirement_plan: bool = False
    marginal_rate: float = Field(0.22, ge=0, le=1.0)
    deductions: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="List of {deduction_type, amount, description} dicts",
    )


class QuarterlyEstimateRequest(BaseModel):
    """Request for quarterly estimated tax calculation."""

    expected_total_tax: float = Field(..., ge=0)
    prior_year_tax: float = Field(..., ge=0)
    prior_year_agi: float = Field(..., ge=0)
    filing_status: str = Field("single")
    w2_withholding: float = Field(0.0, ge=0)
    tax_year: int = Field(2024, ge=2020, le=2030)


# -----------------------------------------------------------------------
# Legal request/response models
# -----------------------------------------------------------------------

class DocumentAnalysisRequest(BaseModel):
    """Request for legal document analysis."""

    text: str = Field(..., min_length=10, description="Raw text of the legal document")
    document_type: str = Field("other", description="Type of legal document")
    title: str = Field("Untitled Document")
    jurisdiction_level: str = Field("federal")
    jurisdiction: Optional[str] = None


class DocumentAnalysisResponse(BaseModel):
    """Response from legal document analysis."""

    document_id: str
    document_type: str
    title: str
    summary: Optional[str]
    risk_score: float
    risk_flags: List[str]
    citation_count: int
    provision_count: int
    keyword_count: int
    keywords: List[str]


class ComplianceCheckRequest(BaseModel):
    """Request for compliance check."""

    gross_income: float = Field(..., ge=0)
    tax_year: int = Field(2024, ge=2020, le=2030)
    filing_status: str = Field("single")
    taxes_withheld: float = Field(0.0, ge=0)
    taxes_paid: float = Field(0.0, ge=0)
    has_foreign_accounts: bool = False
    aggregate_foreign_balance: float = Field(0.0, ge=0)
    has_foreign_assets: float = Field(0.0, ge=0)
    self_employment_income: float = Field(0.0, ge=0)
    issued_1099s_required: int = Field(0, ge=0)
    issued_1099s_filed: int = Field(0, ge=0)


class ComplianceCheckResponse(BaseModel):
    """Response from compliance check."""

    scenario: str
    overall_risk: str
    compliance_score: float
    is_compliant: bool
    issue_count: int
    critical_count: int
    high_count: int
    summary: str
    recommendations: List[str]
    issues: List[Dict[str, Any]]
    passed_checks: List[str]


# -----------------------------------------------------------------------
# Algorithm request/response models
# -----------------------------------------------------------------------

class FilingStatusRequest(BaseModel):
    """Request for filing status recommendation."""

    is_married: bool = False
    prefer_filing_separately: bool = False
    is_qualifying_surviving_spouse: bool = False
    has_qualifying_dependent: bool = False


class FilingStatusResponse(BaseModel):
    """Response from filing status decision tree."""

    recommendation: str
    confidence: float
    path_taken: List[str]
    supporting_reasons: List[str]


class OptimizationRequest(BaseModel):
    """Request for tax optimization analysis."""

    gross_income: float = Field(..., ge=0)
    current_tax: float = Field(..., ge=0)
    marginal_rate: float = Field(0.22, ge=0, le=1.0)
    filing_status: str = Field("single")
    age: int = Field(40, ge=0, le=130)
    has_401k_access: bool = False
    current_401k_contribution: float = Field(0.0, ge=0)
    self_employment_income: float = Field(0.0, ge=0)
    current_sep_contribution: float = Field(0.0, ge=0)
    has_hsa_eligible_plan: bool = False
    current_hsa_contribution: float = Field(0.0, ge=0)
    has_hsa_family_coverage: bool = False
    has_capital_losses: float = Field(0.0, ge=0)
    unrealized_capital_gains: float = Field(0.0, ge=0)
    charitable_intent: float = Field(0.0, ge=0)
    qualified_business_income: float = Field(0.0, ge=0)
    is_business_owner: bool = False


class OptimizationResponse(BaseModel):
    """Response from tax optimization analysis."""

    gross_income: float
    current_estimated_tax: float
    optimized_estimated_tax: float
    total_savings: float
    savings_percentage: float
    strategy_count: int
    strategies: List[Dict[str, Any]]
    warnings: List[str]


class RiskAssessmentRequest(BaseModel):
    """Request for tax risk assessment."""

    agi: float = Field(..., ge=0)
    has_schedule_c: bool = False
    claimed_eitc: bool = False
    deduction_to_income_ratio: float = Field(0.0, ge=0, le=1.0)
    has_foreign_income: bool = False
    has_crypto_transactions: bool = False
    claimed_home_office: bool = False
    large_charitable_pct: float = Field(0.0, ge=0, le=1.0)
    filed_late: bool = False
    has_unreported_income: bool = False
    has_substantial_understatement: bool = False


class RiskAssessmentResponse(BaseModel):
    """Response from risk assessment."""

    scenario: str
    audit_risk_score: float
    penalty_risk_score: float
    overall_risk_score: float
    audit_risk_rating: str
    overall_risk_rating: str
    estimated_audit_probability: float
    factor_count: int
    present_factor_count: int
    recommendations: List[str]

"""
Accounting API router.

Provides endpoints for tax calculation, deduction optimization,
AMT calculation, and quarterly estimated tax payments.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from jit.accounting.tax_calculator import FilingStatus, TaxCalculator
from jit.accounting.deduction_optimizer import DeductionOptimizer, DeductionType
from jit.accounting.amt_calculator import AMTCalculator
from jit.accounting.quarterly_estimator import QuarterlyEstimator
from jit.api.models import (
    TaxCalculationRequest,
    TaxCalculationResponse,
    BracketDetailResponse,
    DeductionOptimizationRequest,
    QuarterlyEstimateRequest,
)

router = APIRouter()


@router.post(
    "/tax/calculate",
    response_model=TaxCalculationResponse,
    summary="Calculate federal and state income tax",
)
async def calculate_tax(request: TaxCalculationRequest) -> TaxCalculationResponse:
    """
    Calculate comprehensive federal and state income tax liability.

    Computes ordinary income tax, FICA, self-employment tax, capital gains
    tax, NIIT, and estimated state tax for the given income profile.
    """
    try:
        status = FilingStatus(request.filing_status)
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid filing_status: {request.filing_status!r}. "
                   "Must be one of: single, married_filing_jointly, "
                   "married_filing_separately, head_of_household, "
                   "qualifying_surviving_spouse",
        )

    calculator = TaxCalculator(tax_year=request.tax_year)
    result = calculator.calculate(
        gross_income=request.gross_income,
        filing_status=status,
        adjustments=request.adjustments,
        deductions=request.deductions,
        w2_wages=request.w2_wages,
        self_employment_income=request.self_employment_income,
        long_term_capital_gains=request.long_term_capital_gains,
        qualified_dividends=request.qualified_dividends,
        net_investment_income=request.net_investment_income,
        state_code=request.state_code,
    )

    return TaxCalculationResponse(
        filing_status=result.filing_status.value,
        tax_year=result.tax_year,
        gross_income=result.gross_income,
        adjusted_gross_income=result.adjusted_gross_income,
        taxable_income=result.taxable_income,
        federal_income_tax=result.federal_income_tax,
        effective_federal_rate=result.effective_federal_rate,
        marginal_federal_rate=result.marginal_federal_rate,
        bracket_details=[
            BracketDetailResponse(
                rate=b.rate,
                bracket_income=b.bracket_income,
                bracket_tax=b.bracket_tax,
                cumulative_tax=b.cumulative_tax,
            )
            for b in result.bracket_details
        ],
        social_security_tax=result.social_security_tax,
        medicare_tax=result.medicare_tax,
        additional_medicare_tax=result.additional_medicare_tax,
        long_term_capital_gains_tax=result.long_term_capital_gains_tax,
        niit=result.niit,
        self_employment_tax=result.self_employment_tax,
        total_federal_tax=result.total_federal_tax,
        effective_total_rate=result.effective_total_rate,
        state_tax=result.state_tax,
        state_code=result.state_code,
        total_tax=result.total_tax,
        recommendations=result.recommendations,
    )


@router.post(
    "/deductions/optimize",
    summary="Optimize tax deductions",
)
async def optimize_deductions(request: DeductionOptimizationRequest) -> dict:
    """
    Analyze and optimize deductions, comparing standard vs. itemized.

    Returns deduction recommendations including QBI deduction and
    optimization opportunities.
    """
    try:
        status = FilingStatus(request.filing_status)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"Invalid filing_status: {request.filing_status!r}")

    optimizer = DeductionOptimizer()

    for item in request.deductions:
        try:
            dtype = DeductionType(item["deduction_type"])
            optimizer.add_deduction(
                dtype,
                float(item.get("amount", 0)),
                item.get("description", ""),
            )
        except (KeyError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=f"Invalid deduction item: {exc}")

    result = optimizer.optimize(
        agi=request.agi,
        filing_status=status,
        age=request.age,
        has_hsa_family_plan=request.has_hsa_family_plan,
        qbi_income=request.qbi_income,
        is_sstb=request.is_sstb,
        has_workplace_retirement_plan=request.has_workplace_retirement_plan,
        marginal_rate=request.marginal_rate,
    )

    return {
        "filing_status": result.filing_status.value,
        "agi": result.agi,
        "standard_deduction": result.standard_deduction,
        "itemized_deduction": result.itemized_deduction,
        "recommended_method": result.recommended_method,
        "recommended_deduction": result.recommended_deduction,
        "tax_benefit_difference": result.tax_benefit_difference,
        "above_the_line_total": result.above_the_line_total,
        "qbi_deduction": result.qbi_deduction,
        "opportunities": result.opportunities,
        "itemized_items": [
            {
                "type": i.deduction_type.value,
                "amount": i.amount,
                "applied_amount": i.applied_amount,
                "limitation_note": i.limitation_note,
            }
            for i in result.itemized_items
        ],
    }


@router.post("/amt/calculate", summary="Calculate Alternative Minimum Tax (AMT)")
async def calculate_amt(
    regular_taxable_income: float,
    regular_tax: float,
    filing_status: str = "single",
    iso_bargain_element: float = 0.0,
    salt_deduction_claimed: float = 0.0,
    standard_deduction_claimed: float = 0.0,
) -> dict:
    """Calculate Alternative Minimum Tax (Form 6251)."""
    try:
        status = FilingStatus(filing_status)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"Invalid filing_status: {filing_status!r}")

    calc = AMTCalculator()
    result = calc.calculate(
        regular_taxable_income=regular_taxable_income,
        regular_tax=regular_tax,
        filing_status=status,
        iso_bargain_element=iso_bargain_element,
        salt_deduction_claimed=salt_deduction_claimed,
        standard_deduction_claimed=standard_deduction_claimed,
    )

    return {
        "is_subject_to_amt": result.is_subject_to_amt,
        "amt_owed": result.amt_owed,
        "tentative_minimum_tax": result.tentative_minimum_tax,
        "amti": result.amti,
        "amt_exemption": result.amt_exemption,
        "total_tax": result.total_tax,
        "amt_credit_generated": result.amt_credit_generated,
        "preference_items": result.preference_items,
        "adjustment_items": result.adjustment_items,
    }


@router.post("/quarterly/estimate", summary="Calculate quarterly estimated tax payments")
async def estimate_quarterly(request: QuarterlyEstimateRequest) -> dict:
    """
    Calculate quarterly estimated tax payment schedule.

    Uses safe harbor rules and current year estimates to determine
    required quarterly payments to avoid underpayment penalties.
    """
    try:
        status = FilingStatus(request.filing_status)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"Invalid filing_status: {request.filing_status!r}")

    estimator = QuarterlyEstimator(tax_year=request.tax_year)
    result = estimator.estimate(
        expected_total_tax=request.expected_total_tax,
        prior_year_tax=request.prior_year_tax,
        prior_year_agi=request.prior_year_agi,
        filing_status=status,
        w2_withholding=request.w2_withholding,
    )

    return {
        "tax_year": result.tax_year,
        "safe_harbor_amount": result.safe_harbor_amount,
        "current_year_safe_harbor": result.current_year_safe_harbor,
        "total_required": result.total_required,
        "total_withholding": result.total_withholding,
        "remaining_to_pay": result.remaining_to_pay,
        "potential_penalty": result.potential_penalty,
        "quarterly_payments": [
            {
                "quarter": p.quarter,
                "due_date": p.due_date,
                "required_payment": p.required_payment,
                "cumulative_tax": p.cumulative_tax,
            }
            for p in result.quarterly_payments
        ],
        "recommendations": result.recommendations,
    }

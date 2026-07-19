"""
Algorithmic analysis API router.

Provides endpoints for filing status recommendations, tax optimization,
and risk assessment using recursive decision trees and optimization engines.
"""

from __future__ import annotations

from fastapi import APIRouter

from jit.algorithms.decision_tree import DecisionTree
from jit.algorithms.optimizer import TaxOptimizer
from jit.algorithms.risk_assessor import RiskAssessor
from jit.api.models import (
    FilingStatusRequest,
    FilingStatusResponse,
    OptimizationRequest,
    OptimizationResponse,
    RiskAssessmentRequest,
    RiskAssessmentResponse,
)

router = APIRouter()


@router.post(
    "/filing-status",
    response_model=FilingStatusResponse,
    summary="Recommend optimal IRS filing status",
)
async def recommend_filing_status(request: FilingStatusRequest) -> FilingStatusResponse:
    """
    Use a recursive decision tree to recommend the optimal IRS filing status.

    Evaluates marital status, qualifying dependents, and surviving spouse
    eligibility to determine the most advantageous filing status.
    """
    tree = DecisionTree.build_filing_status_tree()
    result = tree.evaluate({
        "is_married": request.is_married,
        "prefer_filing_separately": request.prefer_filing_separately,
        "is_qualifying_surviving_spouse": request.is_qualifying_surviving_spouse,
        "has_qualifying_dependent": request.has_qualifying_dependent,
    })

    return FilingStatusResponse(
        recommendation=result.recommendation,
        confidence=result.confidence,
        path_taken=result.path_taken,
        supporting_reasons=result.supporting_reasons,
    )


@router.post(
    "/optimize",
    response_model=OptimizationResponse,
    summary="Generate tax optimization strategies",
)
async def optimize_tax(request: OptimizationRequest) -> OptimizationResponse:
    """
    Generate personalized tax optimization strategies.

    Recursively analyzes retirement contributions, HSA, capital gains,
    charitable giving, QBI, and business structure to maximize tax savings.
    """
    optimizer = TaxOptimizer()
    result = optimizer.optimize(
        gross_income=request.gross_income,
        current_tax=request.current_tax,
        marginal_rate=request.marginal_rate,
        filing_status=request.filing_status,
        age=request.age,
        has_401k_access=request.has_401k_access,
        current_401k_contribution=request.current_401k_contribution,
        self_employment_income=request.self_employment_income,
        current_sep_contribution=request.current_sep_contribution,
        has_hsa_eligible_plan=request.has_hsa_eligible_plan,
        current_hsa_contribution=request.current_hsa_contribution,
        has_hsa_family_coverage=request.has_hsa_family_coverage,
        has_capital_losses=request.has_capital_losses,
        unrealized_capital_gains=request.unrealized_capital_gains,
        charitable_intent=request.charitable_intent,
        qualified_business_income=request.qualified_business_income,
        is_business_owner=request.is_business_owner,
    )

    strategies_data = [
        {
            "strategy_id": s.strategy_id,
            "title": s.title,
            "description": s.description,
            "estimated_savings": s.estimated_savings,
            "implementation_complexity": s.implementation_complexity,
            "prerequisites": s.prerequisites,
            "risks": s.risks,
            "citations": s.citations,
        }
        for s in result.strategies
    ]

    return OptimizationResponse(
        gross_income=result.gross_income,
        current_estimated_tax=result.current_estimated_tax,
        optimized_estimated_tax=result.optimized_estimated_tax,
        total_savings=result.total_savings,
        savings_percentage=result.savings_percentage,
        strategy_count=len(result.strategies),
        strategies=strategies_data,
        warnings=result.warnings,
    )


@router.post(
    "/risk/assess",
    response_model=RiskAssessmentResponse,
    summary="Assess tax audit and compliance risk",
)
async def assess_risk(request: RiskAssessmentRequest) -> RiskAssessmentResponse:
    """
    Assess individual tax audit and compliance risk.

    Evaluates known IRS audit triggers, penalty risk factors, and
    compliance issues to generate a comprehensive risk profile.
    """
    assessor = RiskAssessor()
    result = assessor.assess_individual_tax(
        agi=request.agi,
        has_schedule_c=request.has_schedule_c,
        claimed_eitc=request.claimed_eitc,
        deduction_to_income_ratio=request.deduction_to_income_ratio,
        has_foreign_income=request.has_foreign_income,
        has_crypto_transactions=request.has_crypto_transactions,
        claimed_home_office=request.claimed_home_office,
        large_charitable_pct=request.large_charitable_pct,
        filed_late=request.filed_late,
        has_unreported_income=request.has_unreported_income,
        has_substantial_understatement=request.has_substantial_understatement,
    )

    return RiskAssessmentResponse(
        scenario=result.scenario,
        audit_risk_score=result.audit_risk_score,
        penalty_risk_score=result.penalty_risk_score,
        overall_risk_score=result.overall_risk_score,
        audit_risk_rating=result.audit_risk_rating,
        overall_risk_rating=result.overall_risk_rating,
        estimated_audit_probability=result.estimated_audit_probability,
        factor_count=len(result.factors),
        present_factor_count=len(result.present_factors),
        recommendations=result.recommendations,
    )

"""
Legal analysis API router.

Provides endpoints for document processing, statute parsing,
case law research, and compliance checking.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from jit.legal.document_processor import DocumentProcessor, DocumentType, JurisdictionLevel
from jit.legal.compliance_engine import ComplianceEngine
from jit.api.models import (
    DocumentAnalysisRequest,
    DocumentAnalysisResponse,
    ComplianceCheckRequest,
    ComplianceCheckResponse,
)

router = APIRouter()


@router.post(
    "/document/analyze",
    response_model=DocumentAnalysisResponse,
    summary="Analyze a legal document",
)
async def analyze_document(request: DocumentAnalysisRequest) -> DocumentAnalysisResponse:
    """
    Process and analyze a legal document.

    Extracts provisions, citations, keywords, and computes a risk score
    for the provided legal document text.
    """
    try:
        doc_type = DocumentType(request.document_type)
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid document_type: {request.document_type!r}",
        )

    try:
        jurisdiction_level = JurisdictionLevel(request.jurisdiction_level)
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid jurisdiction_level: {request.jurisdiction_level!r}",
        )

    processor = DocumentProcessor()
    doc = processor.process(
        text=request.text,
        document_type=doc_type,
        title=request.title,
        jurisdiction_level=jurisdiction_level,
        jurisdiction=request.jurisdiction,
    )

    return DocumentAnalysisResponse(
        document_id=doc.document_id,
        document_type=doc.document_type.value,
        title=doc.title,
        summary=doc.summary,
        risk_score=doc.risk_score,
        risk_flags=doc.risk_flags,
        citation_count=len(doc.citations),
        provision_count=len(doc.provisions),
        keyword_count=len(doc.keywords),
        keywords=doc.keywords,
    )


@router.post(
    "/compliance/check",
    response_model=ComplianceCheckResponse,
    summary="Check tax and legal compliance",
)
async def check_compliance(request: ComplianceCheckRequest) -> ComplianceCheckResponse:
    """
    Perform a comprehensive compliance check.

    Verifies compliance with federal tax filing obligations, FBAR/FATCA
    foreign account reporting, 1099 requirements, and more.
    """
    engine = ComplianceEngine()
    result = engine.check_individual_tax_compliance(
        gross_income=request.gross_income,
        tax_year=request.tax_year,
        filing_status_str=request.filing_status,
        taxes_withheld=request.taxes_withheld,
        taxes_paid=request.taxes_paid,
        has_foreign_accounts=request.has_foreign_accounts,
        aggregate_foreign_balance=request.aggregate_foreign_balance,
        has_foreign_assets=request.has_foreign_assets,
        self_employment_income=request.self_employment_income,
        issued_1099s_required=request.issued_1099s_required,
        issued_1099s_filed=request.issued_1099s_filed,
    )

    issues_data = [
        {
            "issue_id": i.issue_id,
            "area": i.area.value,
            "risk_level": i.risk_level.value,
            "title": i.title,
            "description": i.description,
            "regulatory_basis": i.regulatory_basis,
            "recommended_action": i.recommended_action,
            "deadline": i.deadline,
            "penalty_range": i.penalty_range,
        }
        for i in result.issues
    ]

    return ComplianceCheckResponse(
        scenario=result.scenario,
        overall_risk=result.overall_risk.value,
        compliance_score=result.compliance_score,
        is_compliant=result.is_compliant,
        issue_count=len(result.issues),
        critical_count=len(result.critical_issues),
        high_count=len(result.high_issues),
        summary=result.summary,
        recommendations=result.recommendations,
        issues=issues_data,
        passed_checks=result.passed_checks,
    )

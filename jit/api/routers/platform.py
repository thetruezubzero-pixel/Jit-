"""
Platform orchestration API router.

Exposes the upgradeable ``JitPlatform`` orchestrator — which runs a case
through the accounting, legal, and algorithms engines in sequence and
records an audit trail — as a single REST endpoint, distinct from the
module-specific endpoints in ``accounting``, ``legal``, and ``algorithms``.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from jit.core.models import AnalysisContext, DeductionRecord, IncomeRecord, LegalDocument
from jit.platform import JitPlatform

router = APIRouter()
_platform = JitPlatform()


class IncomeItem(BaseModel):
    kind: str
    amount: float
    source: str = "unknown"


class DeductionItem(BaseModel):
    name: str
    amount: float
    itemized: bool = True


class LegalDocumentItem(BaseModel):
    title: str
    text: str
    citations: list[str] = Field(default_factory=list)


class CaseAnalysisRequest(BaseModel):
    case_id: str
    filing_status: str = "single"
    state: str = "CA"
    incomes: list[IncomeItem] = Field(default_factory=list)
    deductions: list[DeductionItem] = Field(default_factory=list)
    legal_documents: list[LegalDocumentItem] = Field(default_factory=list)


@router.post("/analyze", summary="Run a case through the full accounting/legal/algorithms pipeline")
async def analyze_case(request: CaseAnalysisRequest) -> dict[str, Any]:
    """
    Feed a case through the platform orchestrator.

    Runs the accounting engine, then the legal engine (informed by the
    accounting result), then the algorithms engine (informed by both),
    publishing an audit event after each stage.
    """
    context = AnalysisContext(
        case_id=request.case_id,
        filing_status=request.filing_status,
        state=request.state,
        incomes=[IncomeRecord(**item.model_dump()) for item in request.incomes],
        deductions=[DeductionRecord(**item.model_dump()) for item in request.deductions],
        legal_documents=[LegalDocument(**item.model_dump()) for item in request.legal_documents],
    )
    response = _platform.analyze_case(context)
    return {
        "success": response.success,
        "data": response.data,
        "audit_trail": [
            {"topic": record.topic, "payload": record.payload} for record in response.audit_trail
        ],
    }

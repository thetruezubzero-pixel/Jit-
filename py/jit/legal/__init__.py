"""Legal analysis module for document processing and case law research."""

from jit.legal.document_processor import DocumentProcessor, LegalDocument
from jit.legal.statute_parser import StatuteParser, StatuteSection
from jit.legal.case_analyzer import CaseAnalyzer, CaseRecord, Precedent
from jit.legal.compliance_engine import ComplianceEngine, ComplianceResult

__all__ = [
    "DocumentProcessor",
    "LegalDocument",
    "StatuteParser",
    "StatuteSection",
    "CaseAnalyzer",
    "CaseRecord",
    "Precedent",
    "ComplianceEngine",
    "ComplianceResult",
]

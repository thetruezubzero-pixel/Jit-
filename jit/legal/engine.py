"""Legal analysis engine with pluggable analyzers, backed by the real document
processor and compliance engine."""

from __future__ import annotations

from jit.core.events import EventBus
from jit.core.models import AnalysisContext, ModuleResult
from jit.core.plugins import PluginRegistry
from jit.legal.base import LegalAnalyzerPlugin
from jit.legal.compliance_engine import ComplianceEngine
from jit.legal.document_processor import DocumentProcessor

_COMPLIANT_STATUSES = {
    "low": "clear",
    "medium": "review",
    "high": "review",
    "critical": "non_compliant",
}


class RealLegalAnalyzer(LegalAnalyzerPlugin):
    """Runs each attached legal document through the citation/risk-scoring
    processor and cross-checks tax compliance using the accounting module's
    output (gross income, self-employment income) as inputs.
    """

    def analyze(self, context: AnalysisContext, accounting: ModuleResult) -> dict[str, object]:
        processor = DocumentProcessor()
        citations: set[str] = set()
        risk_scores: list[float] = [0.0]
        risk_flags: list[str] = []

        for document in context.legal_documents:
            processed = processor.process(text=document.text, title=document.title)
            citations.update(document.citations)
            citations.update(c.normalized or c.raw_text for c in processed.citations)
            risk_scores.append(processed.risk_score)
            risk_flags.extend(processed.risk_flags)

        compliance = ComplianceEngine().check_individual_tax_compliance(
            gross_income=accounting.data["gross_income"],
            tax_year=2024,
            filing_status_str=context.filing_status,
            # AnalysisContext has no field for withholding/estimated payments
            # already made, so this is genuinely unknown here -- passing None
            # (not 0.0) makes the compliance engine skip the underpayment
            # check instead of treating "unknown" as "definitely $0," which
            # used to flag every sufficiently high income as underpaid.
            taxes_withheld=None,
            taxes_paid=None,
            self_employment_income=accounting.data.get("self_employment_income", 0.0),
        )

        document_risk = max(risk_scores)
        compliance_risk = 1.0 - compliance.compliance_score
        risk_score = max(document_risk, compliance_risk)

        return {
            "document_count": len(context.legal_documents),
            "precedent_hits": len(risk_flags),
            "citations": sorted(citations),
            "risk_flags": sorted(set(risk_flags)),
            "compliance_status": _COMPLIANT_STATUSES.get(compliance.overall_risk.value, "review"),
            "compliance_issues": [issue.title for issue in compliance.issues],
            "compliance_recommendations": compliance.recommendations,
            "risk_score": risk_score,
            "accounting_total_tax": accounting.data["total_tax"],
        }


class LegalAnalysisEngine:
    def __init__(self, event_bus: EventBus, rule_version: str) -> None:
        self.event_bus = event_bus
        self.rule_version = rule_version
        self.analyzers = PluginRegistry()
        self.analyzers.register("real", RealLegalAnalyzer)
        self._active_analyzers = [("real", "default")]

    def register_analyzer(
        self, name: str, analyzer: type[LegalAnalyzerPlugin], version: str = "default"
    ) -> None:
        self.analyzers.register(name, analyzer, version)

    def add_analyzer(self, name: str, version: str = "default") -> None:
        self._active_analyzers.append((name, version))

    def analyze(self, context: AnalysisContext, accounting: ModuleResult) -> ModuleResult:
        results = [
            self.analyzers.create(name, version).analyze(context, accounting)
            for name, version in self._active_analyzers
        ]
        citations = sorted({citation for result in results for citation in result["citations"]})
        risk_score = max(result["risk_score"] for result in results) if results else 0.0
        payload = {
            "results": results,
            "citations": citations,
            "risk_score": risk_score,
            "compliance_status": "review" if risk_score >= 0.4 else "clear",
        }
        self.event_bus.publish(
            "legal.completed",
            {"case_id": context.case_id, "risk_score": payload["risk_score"]},
        )
        return ModuleResult(
            module="legal",
            version=self.rule_version,
            data=payload,
            messages=["Legal analysis completed"],
        )

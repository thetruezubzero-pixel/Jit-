"""Legal analysis engine with pluggable analyzers."""

from __future__ import annotations

from jit.core.events import EventBus
from jit.core.models import AnalysisContext, ModuleResult
from jit.core.plugins import PluginRegistry
from jit.legal.base import LegalAnalyzerPlugin


class KeywordRiskAnalyzer(LegalAnalyzerPlugin):
    KEYWORDS = ("irs", "indemnify", "penalty", "audit", "reporting")

    def analyze(self, context: AnalysisContext, accounting: ModuleResult) -> dict[str, object]:
        citations: list[str] = []
        hits = 0
        for document in context.legal_documents:
            normalized = document.text.lower()
            hits += sum(1 for keyword in self.KEYWORDS if keyword in normalized)
            citations.extend(document.citations)
        return {
            "document_count": len(context.legal_documents),
            "precedent_hits": hits,
            "citations": sorted(set(citations)),
            "compliance_status": "review" if hits else "clear",
            "risk_score": min(1.0, hits / 5 or 0.1),
            "accounting_total_tax": accounting.data["total_tax"],
        }


class LegalAnalysisEngine:
    def __init__(self, event_bus: EventBus, rule_version: str) -> None:
        self.event_bus = event_bus
        self.rule_version = rule_version
        self.analyzers = PluginRegistry()
        self.analyzers.register("keyword_risk", KeywordRiskAnalyzer)
        self._active_analyzers = [("keyword_risk", "default")]

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

"""Recursive recommendation engine with runtime strategy selection."""

from __future__ import annotations

from jit.algorithms.base import RecommendationStrategy
from jit.core.events import EventBus
from jit.core.models import AnalysisContext, ModuleResult
from jit.core.plugins import PluginRegistry


class ConnectedRecommendationStrategy(RecommendationStrategy):
    def recommend(
        self, context: AnalysisContext, accounting: ModuleResult, legal: ModuleResult
    ) -> dict[str, object]:
        audit_risk = legal.data["risk_score"]
        deduction_basis = accounting.data["deduction_recommendation"]
        recommendation = "defer complex filing for review" if audit_risk >= 0.6 else deduction_basis
        return {
            "primary_recommendation": recommendation,
            "confidence": max(0.2, 1 - audit_risk / 2),
            "decision_tree": {
                "case_id": context.case_id,
                "income_nodes": len(context.incomes),
                "document_nodes": len(context.legal_documents),
                "selected_path": recommendation,
            },
            "risk_summary": {
                "audit_probability": audit_risk,
                "penalty_exposure": "medium" if audit_risk >= 0.4 else "low",
            },
        }


class AlgorithmEngine:
    def __init__(self, event_bus: EventBus, rule_version: str) -> None:
        self.event_bus = event_bus
        self.rule_version = rule_version
        self.strategies = PluginRegistry()
        self.strategies.register("connected", ConnectedRecommendationStrategy)
        self._active_strategy = ("connected", "default")

    def register_strategy(
        self, name: str, strategy: type[RecommendationStrategy], version: str = "default"
    ) -> None:
        self.strategies.register(name, strategy, version)

    def use_strategy(self, name: str, version: str = "default") -> None:
        self._active_strategy = (name, version)

    def analyze(
        self, context: AnalysisContext, accounting: ModuleResult, legal: ModuleResult
    ) -> ModuleResult:
        strategy = self.strategies.create(*self._active_strategy)
        payload = strategy.recommend(context, accounting, legal)
        self.event_bus.publish(
            "algorithms.completed",
            {"case_id": context.case_id, "recommendation": payload["primary_recommendation"]},
        )
        return ModuleResult(
            module="algorithms",
            version=self.rule_version,
            data=payload,
            messages=["Algorithmic recommendation completed"],
        )

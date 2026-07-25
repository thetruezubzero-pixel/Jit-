"""Recursive recommendation engine with runtime strategy selection, backed by
the real audit-risk assessor, tax optimizer, and filing-status decision tree.
"""

from __future__ import annotations

from jit.algorithms.base import RecommendationStrategy
from jit.algorithms.decision_tree import DecisionTree
from jit.algorithms.optimizer import TaxOptimizer
from jit.algorithms.risk_assessor import RiskAssessor
from jit.core.events import EventBus
from jit.core.models import AnalysisContext, ModuleResult
from jit.core.plugins import PluginRegistry


class ConnectedRecommendationStrategy(RecommendationStrategy):
    """Combines audit-risk assessment, the ranked optimization strategies, and
    the filing-status decision tree into a single recommendation, using the
    legal module's risk score to decide whether to defer to a human advisor.
    """

    def recommend(
        self, context: AnalysisContext, accounting: ModuleResult, legal: ModuleResult
    ) -> dict[str, object]:
        gross_income = accounting.data["gross_income"]
        se_income = accounting.data.get("self_employment_income", 0.0)
        itemized = accounting.data["itemized_deductions"]

        risk = RiskAssessor().assess_individual_tax(
            agi=gross_income,
            has_schedule_c=se_income > 0,
            schedule_c_income=se_income,
            deduction_to_income_ratio=(itemized / gross_income) if gross_income else 0.0,
        )

        optimization = TaxOptimizer().optimize(
            gross_income=gross_income,
            current_tax=accounting.data["total_tax"],
            marginal_rate=accounting.data["marginal_rate"],
            filing_status=context.filing_status,
            self_employment_income=se_income,
            qualified_business_income=se_income,
        )

        filing_tree = DecisionTree.build_filing_status_tree()
        filing_decision = filing_tree.evaluate(
            {
                "is_married": context.filing_status
                in ("married_filing_jointly", "married_filing_separately"),
                "prefer_filing_separately": context.filing_status == "married_filing_separately",
                "has_qualifying_dependent": context.filing_status == "head_of_household",
                "is_qualifying_surviving_spouse": context.filing_status
                == "qualifying_surviving_spouse",
            }
        )

        audit_risk = max(risk.audit_risk_score, legal.data["risk_score"])
        deduction_basis = accounting.data["deduction_recommendation"]
        top_strategy = optimization.strategies[0].title if optimization.strategies else None
        recommendation = (
            "defer complex filing for review"
            if audit_risk >= 0.6
            else (top_strategy or deduction_basis)
        )

        return {
            "primary_recommendation": recommendation,
            "confidence": max(0.2, 1 - audit_risk / 2),
            "filing_status_guidance": filing_decision.recommendation,
            "decision_tree": {
                "case_id": context.case_id,
                "income_nodes": len(context.incomes),
                "document_nodes": len(context.legal_documents),
                "selected_path": recommendation,
                "filing_status_path": filing_decision.path_taken,
            },
            "optimization_strategies": [
                {"id": s.strategy_id, "title": s.title, "estimated_savings": s.estimated_savings}
                for s in optimization.strategies
            ],
            "total_potential_savings": optimization.total_savings,
            "risk_summary": {
                "audit_probability": risk.estimated_audit_probability,
                "audit_risk_rating": risk.audit_risk_rating,
                "penalty_exposure": risk.overall_risk_rating,
                "recommendations": risk.recommendations,
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

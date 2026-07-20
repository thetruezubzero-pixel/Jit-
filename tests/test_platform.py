"""Integration tests for the combined Jit platform: verifies that the
upgradeable architecture (core contracts, plugin registry, event bus,
JitPlatform orchestrator) is wired to the real accounting, legal, and
algorithms engines rather than placeholder logic.
"""

from __future__ import annotations

import unittest

from jit.accounting.base import TaxCalculatorPlugin
from jit.algorithms.base import RecommendationStrategy
from jit.core.models import AnalysisContext, DeductionRecord, IncomeRecord, LegalDocument
from jit.legal.base import LegalAnalyzerPlugin
from jit.platform import JitPlatform


def build_context() -> AnalysisContext:
    return AnalysisContext(
        case_id="case-001",
        filing_status="single",
        state="CA",
        incomes=[
            IncomeRecord(kind="w2", amount=120000, source="Employer"),
            IncomeRecord(kind="1099", amount=20000, source="Side Gig"),
        ],
        deductions=[
            DeductionRecord(name="mortgage_interest", amount=12000),
            DeductionRecord(name="charity", amount=4000),
        ],
        legal_documents=[
            LegalDocument(
                title="Services Contract",
                text="The contract includes indemnification language and IRS reporting duties.",
                citations=["26 U.S.C. § 61"],
            )
        ],
    )


class FlatCreditCalculator(TaxCalculatorPlugin):
    def calculate(self, context: AnalysisContext, rules: dict[str, float]) -> dict[str, float]:
        gross_income = sum(income.amount for income in context.incomes)
        return {
            "gross_income": gross_income,
            "self_employment_income": 0.0,
            "itemized_deductions": 0.0,
            "taxable_income": gross_income,
            "federal_tax": gross_income * 0.2 - 500,
            "state_tax": 0.0,
            "self_employment_tax": 0.0,
            "niit": 0.0,
            "marginal_rate": 0.2,
            "effective_rate": 0.2,
            "quarterly_estimate": 0.0,
            "amt_exposure": False,
            "amt_owed": 0.0,
            "total_tax": gross_income * 0.2 - 500,
            "recommendations": [],
        }


class CitationEchoAnalyzer(LegalAnalyzerPlugin):
    def analyze(self, context: AnalysisContext, accounting) -> dict[str, object]:
        return {
            "document_count": len(context.legal_documents),
            "precedent_hits": 1,
            "citations": ["Echo Citation"],
            "compliance_status": "review",
            "risk_score": 0.25,
            "accounting_total_tax": accounting.data["total_tax"],
        }


class ConservativeStrategy(RecommendationStrategy):
    def recommend(self, context: AnalysisContext, accounting, legal) -> dict[str, object]:
        return {
            "primary_recommendation": "review with advisor",
            "confidence": 0.7,
            "decision_tree": {"case_id": context.case_id, "selected_path": "review with advisor"},
            "risk_summary": {
                "audit_probability": legal.data["risk_score"],
                "penalty_exposure": "low",
            },
        }


class PlatformTests(unittest.TestCase):
    def test_cross_module_analysis_flow_uses_real_engines(self) -> None:
        platform = JitPlatform()
        response = platform.analyze_case(build_context())

        self.assertTrue(response.success)
        self.assertIn("accounting", response.data)
        self.assertIn("legal", response.data)
        self.assertIn("algorithms", response.data)
        self.assertEqual(
            [r.topic for r in response.audit_trail],
            [
                "accounting.completed",
                "legal.completed",
                "algorithms.completed",
            ],
        )
        self.assertIn("gateway", response.data["services"])

        accounting = response.data["accounting"]
        # $140k gross, $16k itemized > $14.6k standard deduction for single filers.
        self.assertEqual(accounting["gross_income"], 140000)
        self.assertEqual(accounting["deduction_recommendation"], "itemized")
        self.assertGreater(accounting["total_tax"], 0)
        self.assertGreater(accounting["self_employment_tax"], 0)

        legal = response.data["legal"]
        self.assertIn("26 U.S.C. § 61", legal["citations"])
        self.assertGreater(legal["risk_score"], 0)

        algorithms = response.data["algorithms"]
        self.assertIn("primary_recommendation", algorithms)
        self.assertIn("filing_status_guidance", algorithms)
        self.assertIsInstance(algorithms["optimization_strategies"], list)

    def test_plugins_can_be_upgraded_at_runtime(self) -> None:
        platform = JitPlatform()
        platform.accounting.register_calculator("credit", FlatCreditCalculator)
        platform.accounting.use_calculator("credit")
        platform.legal.register_analyzer("echo", CitationEchoAnalyzer)
        platform.legal.add_analyzer("echo")
        platform.algorithms.register_strategy("conservative", ConservativeStrategy)
        platform.algorithms.use_strategy("conservative")

        response = platform.analyze_case(build_context())

        self.assertEqual(
            response.data["algorithms"]["primary_recommendation"], "review with advisor"
        )
        self.assertIn("Echo Citation", response.data["legal"]["citations"])
        # FlatCreditCalculator: 140,000 * 0.2 - 500 = 27,500, far below the real engine's total.
        self.assertEqual(response.data["accounting"]["total_tax"], 27500.0)

    def test_versioned_api_and_middleware(self) -> None:
        platform = JitPlatform()
        response = platform.handle_request(
            "v1",
            "/analyze",
            {"context": build_context()},
        )

        self.assertEqual(response["status"], "ok")
        self.assertEqual(response["version"], "v1")
        self.assertTrue(response["data"]["success"])
        self.assertTrue(response["data"]["metadata"]["audit_enabled"])


if __name__ == "__main__":
    unittest.main()

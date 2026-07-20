"""
Browser-side dispatch bridge for the Jit engines, run inside Pyodide.

Exposes every real module in the jit package (accounting, legal, algorithms,
and the cross-module platform orchestrator) through one JSON-in/JSON-out
entry point, ``dispatch(module_name, payload_json)``, so the frontend never
talks to a server — it calls straight into the same Python source that
backs the FastAPI routers, running client-side.
"""

from __future__ import annotations

import json
from dataclasses import fields, is_dataclass
from enum import Enum


def to_jsonable(obj):
    """Recursively convert dataclasses/enums/etc. into plain JSON-safe values.

    Includes ``@property`` values (e.g. ``TaxResult.total_tax``,
    ``ComplianceResult.is_compliant``) alongside declared dataclass fields,
    since several result types compute their headline numbers that way.
    """
    if is_dataclass(obj) and not isinstance(obj, type):
        result = {f.name: to_jsonable(getattr(obj, f.name)) for f in fields(obj)}
        for name, member in vars(type(obj)).items():
            if isinstance(member, property) and name not in result:
                try:
                    result[name] = to_jsonable(getattr(obj, name))
                except Exception:
                    pass
        return result
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, dict):
        return {k: to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [to_jsonable(v) for v in obj]
    return obj


def tax_calculate(payload: dict) -> dict:
    from jit.accounting.tax_calculator import FilingStatus, TaxCalculator

    calc = TaxCalculator(tax_year=int(payload.get("tax_year", 2024)))
    result = calc.calculate(
        gross_income=payload["gross_income"],
        filing_status=FilingStatus(payload.get("filing_status", "single")),
        adjustments=payload.get("adjustments", 0.0),
        deductions=payload.get("deductions", 0.0),
        w2_wages=payload.get("w2_wages", 0.0),
        self_employment_income=payload.get("self_employment_income", 0.0),
        long_term_capital_gains=payload.get("long_term_capital_gains", 0.0),
        qualified_dividends=payload.get("qualified_dividends", 0.0),
        net_investment_income=payload.get("net_investment_income", 0.0),
        state_code=payload.get("state_code") or None,
    )
    return to_jsonable(result)


def deduction_optimize(payload: dict) -> dict:
    from jit.accounting.deduction_optimizer import DeductionOptimizer, DeductionType
    from jit.accounting.tax_calculator import FilingStatus

    optimizer = DeductionOptimizer()
    for item in payload.get("deductions", []):
        optimizer.add_deduction(
            DeductionType(item["deduction_type"]),
            float(item.get("amount", 0)),
            item.get("description", ""),
        )
    result = optimizer.optimize(
        agi=payload["agi"],
        filing_status=FilingStatus(payload.get("filing_status", "single")),
        age=payload.get("age", 40),
        has_hsa_family_plan=payload.get("has_hsa_family_plan", False),
        qbi_income=payload.get("qbi_income", 0.0),
        is_sstb=payload.get("is_sstb", False),
        has_workplace_retirement_plan=payload.get("has_workplace_retirement_plan", False),
        marginal_rate=payload.get("marginal_rate", 0.22),
    )
    return to_jsonable(result)


def amt_calculate(payload: dict) -> dict:
    from jit.accounting.amt_calculator import AMTCalculator
    from jit.accounting.tax_calculator import FilingStatus

    calc = AMTCalculator(tax_year=int(payload.get("tax_year", 2024)))
    result = calc.calculate(
        regular_taxable_income=payload["regular_taxable_income"],
        regular_tax=payload["regular_tax"],
        filing_status=FilingStatus(payload.get("filing_status", "single")),
        iso_bargain_element=payload.get("iso_bargain_element", 0.0),
        salt_deduction_claimed=payload.get("salt_deduction_claimed", 0.0),
        standard_deduction_claimed=payload.get("standard_deduction_claimed", 0.0),
    )
    return to_jsonable(result)


def quarterly_estimate(payload: dict) -> dict:
    from jit.accounting.quarterly_estimator import QuarterlyEstimator
    from jit.accounting.tax_calculator import FilingStatus

    estimator = QuarterlyEstimator(tax_year=int(payload.get("tax_year", 2024)))
    result = estimator.estimate(
        expected_total_tax=payload["expected_total_tax"],
        prior_year_tax=payload["prior_year_tax"],
        prior_year_agi=payload["prior_year_agi"],
        filing_status=FilingStatus(payload.get("filing_status", "single")),
        w2_withholding=payload.get("w2_withholding", 0.0),
    )
    return to_jsonable(result)


def document_analyze(payload: dict) -> dict:
    from jit.legal.document_processor import DocumentProcessor, DocumentType, JurisdictionLevel

    processor = DocumentProcessor()
    result = processor.process(
        text=payload["text"],
        document_type=DocumentType(payload.get("document_type", "other")),
        title=payload.get("title", "Untitled Document"),
        jurisdiction_level=JurisdictionLevel(payload.get("jurisdiction_level", "federal")),
        jurisdiction=payload.get("jurisdiction") or None,
    )
    return to_jsonable(result)


def compliance_check(payload: dict) -> dict:
    from jit.legal.compliance_engine import ComplianceEngine

    result = ComplianceEngine().check_individual_tax_compliance(
        gross_income=payload["gross_income"],
        tax_year=int(payload.get("tax_year", 2024)),
        filing_status_str=payload.get("filing_status", "single"),
        taxes_withheld=payload.get("taxes_withheld", 0.0),
        taxes_paid=payload.get("taxes_paid", 0.0),
        has_foreign_accounts=payload.get("has_foreign_accounts", False),
        max_foreign_account_balance=payload.get("max_foreign_account_balance", 0.0),
        aggregate_foreign_balance=payload.get("aggregate_foreign_balance", 0.0),
        has_foreign_assets=payload.get("has_foreign_assets", 0.0),
        self_employment_income=payload.get("self_employment_income", 0.0),
        received_1099s=payload.get("received_1099s", False),
        issued_1099s_required=payload.get("issued_1099s_required", 0),
        issued_1099s_filed=payload.get("issued_1099s_filed", 0),
    )
    return to_jsonable(result)


def filing_status_tree(payload: dict) -> dict:
    from jit.algorithms.decision_tree import DecisionTree

    tree = DecisionTree.build_filing_status_tree()
    result = tree.evaluate(
        {
            "is_married": payload.get("is_married", False),
            "prefer_filing_separately": payload.get("prefer_filing_separately", False),
            "is_qualifying_surviving_spouse": payload.get("is_qualifying_surviving_spouse", False),
            "has_qualifying_dependent": payload.get("has_qualifying_dependent", False),
        }
    )
    return to_jsonable(result)


def deduction_method_tree(payload: dict) -> dict:
    from jit.algorithms.decision_tree import DecisionTree

    tree = DecisionTree.build_deduction_method_tree()
    result = tree.evaluate(
        {
            "itemized_deductions": payload.get("itemized_deductions", 0.0),
            "standard_deduction": payload.get("standard_deduction", 14_600.0),
        }
    )
    return to_jsonable(result)


def algorithm_optimize(payload: dict) -> dict:
    from jit.algorithms.optimizer import TaxOptimizer

    result = TaxOptimizer().optimize(
        gross_income=payload["gross_income"],
        current_tax=payload["current_tax"],
        marginal_rate=payload["marginal_rate"],
        filing_status=payload.get("filing_status", "single"),
        age=payload.get("age", 40),
        has_401k_access=payload.get("has_401k_access", False),
        current_401k_contribution=payload.get("current_401k_contribution", 0.0),
        self_employment_income=payload.get("self_employment_income", 0.0),
        current_sep_contribution=payload.get("current_sep_contribution", 0.0),
        has_hsa_eligible_plan=payload.get("has_hsa_eligible_plan", False),
        current_hsa_contribution=payload.get("current_hsa_contribution", 0.0),
        has_hsa_family_coverage=payload.get("has_hsa_family_coverage", False),
        has_capital_losses=payload.get("has_capital_losses", 0.0),
        unrealized_capital_gains=payload.get("unrealized_capital_gains", 0.0),
        charitable_intent=payload.get("charitable_intent", 0.0),
        qualified_business_income=payload.get("qualified_business_income", 0.0),
        is_business_owner=payload.get("is_business_owner", False),
        has_real_estate=payload.get("has_real_estate", False),
        net_rental_income=payload.get("net_rental_income", 0.0),
        expected_state_tax=payload.get("expected_state_tax", 0.0),
    )
    return to_jsonable(result)


def risk_assess(payload: dict) -> dict:
    from jit.algorithms.risk_assessor import RiskAssessor

    result = RiskAssessor().assess_individual_tax(
        agi=payload["agi"],
        has_schedule_c=payload.get("has_schedule_c", False),
        schedule_c_income=payload.get("schedule_c_income", 0.0),
        claimed_eitc=payload.get("claimed_eitc", False),
        deduction_to_income_ratio=payload.get("deduction_to_income_ratio", 0.0),
        has_foreign_income=payload.get("has_foreign_income", False),
        has_crypto_transactions=payload.get("has_crypto_transactions", False),
        claimed_home_office=payload.get("claimed_home_office", False),
        claimed_large_charitable=payload.get("claimed_large_charitable", False),
        large_charitable_pct=payload.get("large_charitable_pct", 0.0),
        claimed_large_business_meals=payload.get("claimed_large_business_meals", False),
        prior_audit_years=payload.get("prior_audit_years", 0),
        has_mathematical_errors=payload.get("has_mathematical_errors", False),
        filed_late=payload.get("filed_late", False),
        has_unreported_income=payload.get("has_unreported_income", False),
        has_substantial_understatement=payload.get("has_substantial_understatement", False),
    )
    return to_jsonable(result)


def platform_analyze(payload: dict) -> dict:
    from jit.core.models import AnalysisContext, DeductionRecord, IncomeRecord, LegalDocument
    from jit.platform import JitPlatform

    context = AnalysisContext(
        case_id=payload.get("case_id", "case-1"),
        filing_status=payload.get("filing_status", "single"),
        state=payload.get("state", "CA"),
        incomes=[IncomeRecord(**i) for i in payload.get("incomes", [])],
        deductions=[DeductionRecord(**d) for d in payload.get("deductions", [])],
        legal_documents=[LegalDocument(**d) for d in payload.get("legal_documents", [])],
    )
    response = JitPlatform().analyze_case(context)
    return {
        **response.data,
        "audit_trail": [to_jsonable(record) for record in response.audit_trail],
    }


_HANDLERS = {
    "tax_calculate": tax_calculate,
    "deduction_optimize": deduction_optimize,
    "amt_calculate": amt_calculate,
    "quarterly_estimate": quarterly_estimate,
    "document_analyze": document_analyze,
    "compliance_check": compliance_check,
    "filing_status_tree": filing_status_tree,
    "deduction_method_tree": deduction_method_tree,
    "algorithm_optimize": algorithm_optimize,
    "risk_assess": risk_assess,
    "platform_analyze": platform_analyze,
}


def dispatch(module_name: str, payload_json: str) -> str:
    try:
        handler = _HANDLERS[module_name]
    except KeyError:
        return json.dumps({"success": False, "error": f"Unknown module: {module_name!r}"})

    try:
        payload = json.loads(payload_json)
        result = handler(payload)
        return json.dumps({"success": True, "data": result})
    except Exception as exc:  # noqa: BLE001 - surface any engine error to the UI
        return json.dumps({"success": False, "error": f"{type(exc).__name__}: {exc}"})

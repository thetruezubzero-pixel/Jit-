"""Accounting engine with upgradeable calculators, backed by the real IRS-rules tax engine."""

from __future__ import annotations

from dataclasses import dataclass, field

from jit.accounting.amt_calculator import AMTCalculator
from jit.accounting.base import TaxCalculatorPlugin
from jit.accounting.quarterly_estimator import QuarterlyEstimator
from jit.accounting.tax_calculator import FilingStatus, TaxCalculator
from jit.core.events import EventBus
from jit.core.models import AnalysisContext, ModuleResult
from jit.core.plugins import PluginRegistry

# SALT deduction is capped at $10,000 regardless of how much is claimed.
_SALT_CAP = 10_000.0

# Income kinds treated as self-employment / 1099 income for FICA and SE-tax purposes.
_SELF_EMPLOYMENT_KINDS = {"1099", "1099_nec", "se", "self_employment", "schedule_c"}
_LTCG_KINDS = {"ltcg", "long_term_capital_gains", "capital_gains"}
_QUALIFIED_DIVIDEND_KINDS = {"qualified_dividends"}


@dataclass
class VersionedRulesEngine:
    """Maps a rule version string to the tax year it should compute against.

    Lets the accounting module upgrade rule sets independently: adding a new
    year's brackets only requires teaching ``TaxCalculator``/``AMTCalculator``
    about it and registering the version here.
    """

    versions: dict[str, int] = field(default_factory=lambda: {"2024": 2024, "2026.1": 2024})

    def register_version(self, version: str, tax_year: int) -> None:
        self.versions[version] = tax_year

    def resolve(self, version: str) -> int:
        return self.versions.get(version, 2024)


def _filing_status(value: str) -> FilingStatus:
    try:
        return FilingStatus(value)
    except ValueError:
        return FilingStatus.SINGLE


class RealTaxCalculator(TaxCalculatorPlugin):
    """Default calculator: wraps the full federal tax engine (brackets, FICA,
    SE tax, NIIT, AMT, and quarterly safe-harbor estimates) behind the
    pluggable ``TaxCalculatorPlugin`` interface.
    """

    def calculate(self, context: AnalysisContext, rules: dict[str, float]) -> dict[str, float]:
        tax_year = int(rules.get("tax_year", 2024))
        filing_status = _filing_status(context.filing_status)

        w2_wages = sum(i.amount for i in context.incomes if i.kind == "w2")
        se_income = sum(i.amount for i in context.incomes if i.kind in _SELF_EMPLOYMENT_KINDS)
        ltcg = sum(i.amount for i in context.incomes if i.kind in _LTCG_KINDS)
        qualified_dividends = sum(
            i.amount for i in context.incomes if i.kind in _QUALIFIED_DIVIDEND_KINDS
        )
        other_income = sum(
            i.amount
            for i in context.incomes
            if i.kind
            not in (_SELF_EMPLOYMENT_KINDS | _LTCG_KINDS | _QUALIFIED_DIVIDEND_KINDS | {"w2"})
        )
        gross_income = w2_wages + se_income + ltcg + qualified_dividends + other_income
        itemized_deductions = sum(d.amount for d in context.deductions if d.itemized)

        calculator = TaxCalculator(tax_year=tax_year)
        result = calculator.calculate(
            gross_income=gross_income,
            filing_status=filing_status,
            deductions=itemized_deductions,
            w2_wages=w2_wages,
            self_employment_income=se_income,
            long_term_capital_gains=ltcg,
            qualified_dividends=qualified_dividends,
            state_code=context.state,
        )

        amt = AMTCalculator(tax_year=tax_year).calculate(
            regular_taxable_income=result.taxable_income,
            regular_tax=result.total_federal_tax,
            filing_status=filing_status,
            salt_deduction_claimed=min(itemized_deductions, _SALT_CAP),
            standard_deduction_claimed=0.0,
        )

        expected_total_tax = result.total_tax + amt.amt_owed
        quarterly = QuarterlyEstimator(tax_year=tax_year).estimate(
            expected_total_tax=expected_total_tax,
            prior_year_tax=expected_total_tax,
            prior_year_agi=result.adjusted_gross_income,
            filing_status=filing_status,
        )

        return {
            "gross_income": gross_income,
            "self_employment_income": se_income,
            "itemized_deductions": itemized_deductions,
            "taxable_income": result.taxable_income,
            "federal_tax": result.federal_income_tax,
            "state_tax": result.state_tax,
            "self_employment_tax": result.self_employment_tax,
            "niit": result.niit,
            "marginal_rate": result.marginal_federal_rate,
            "effective_rate": result.effective_total_rate,
            "quarterly_estimate": quarterly.total_required / 4 if quarterly.total_required else 0.0,
            "amt_exposure": amt.is_subject_to_amt,
            "amt_owed": amt.amt_owed,
            "total_tax": expected_total_tax,
            "recommendations": result.recommendations,
        }


class AccountingEngine:
    def __init__(self, event_bus: EventBus, rule_version: str) -> None:
        self.event_bus = event_bus
        self.rule_version = rule_version
        self.rules = VersionedRulesEngine()
        self.calculators = PluginRegistry()
        self.calculators.register("real", RealTaxCalculator)
        self._active_calculator = ("real", "default")

    def register_calculator(
        self, name: str, calculator: type[TaxCalculatorPlugin], version: str = "default"
    ) -> None:
        self.calculators.register(name, calculator, version)

    def use_calculator(self, name: str, version: str = "default") -> None:
        self._active_calculator = (name, version)

    def analyze(self, context: AnalysisContext, standard_deduction: float) -> ModuleResult:
        calculator = self.calculators.create(*self._active_calculator)
        rules = {"tax_year": float(self.rules.resolve(self.rule_version))}
        tax_summary = calculator.calculate(context, rules)
        itemized = tax_summary["itemized_deductions"]
        recommendation = "itemized" if itemized > standard_deduction else "standard"
        tax_summary["deduction_recommendation"] = recommendation
        tax_summary["filing_status_recommendation"] = context.filing_status
        self.event_bus.publish(
            "accounting.completed",
            {"case_id": context.case_id, "taxable_income": tax_summary["taxable_income"]},
        )
        return ModuleResult(
            module="accounting",
            version=self.rule_version,
            data=tax_summary,
            messages=["Accounting analysis completed"],
        )

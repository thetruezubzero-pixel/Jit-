"""Accounting engine with upgradeable calculators and rules."""

from __future__ import annotations

from dataclasses import dataclass, field

from jit.accounting.base import TaxCalculatorPlugin
from jit.core.events import EventBus
from jit.core.models import AnalysisContext, ModuleResult
from jit.core.plugins import PluginRegistry


@dataclass(slots=True)
class VersionedRulesEngine:
    versions: dict[str, dict[str, float]] = field(
        default_factory=lambda: {
            "2026.1": {"federal": 0.22, "state": 0.05, "local": 0.01}
        }
    )

    def register_version(self, version: str, rules: dict[str, float]) -> None:
        self.versions[version] = rules

    def resolve(self, version: str) -> dict[str, float]:
        return self.versions[version]


class ProgressiveTaxCalculator(TaxCalculatorPlugin):
    def calculate(self, context: AnalysisContext, rules: dict[str, float]) -> dict[str, float]:
        gross_income = sum(income.amount for income in context.incomes)
        itemized_deductions = sum(deduction.amount for deduction in context.deductions if deduction.itemized)
        taxable_income = max(gross_income - itemized_deductions, 0.0)
        taxes = {
            "federal_tax": taxable_income * rules["federal"],
            "state_tax": taxable_income * rules["state"],
            "local_tax": taxable_income * rules["local"],
        }
        total_tax = sum(taxes.values())
        return {
            "gross_income": gross_income,
            "itemized_deductions": itemized_deductions,
            "taxable_income": taxable_income,
            "quarterly_estimate": total_tax / 4 if total_tax else 0.0,
            "amt_exposure": taxable_income > 200000,
            **taxes,
            "total_tax": total_tax,
        }


class AccountingEngine:
    def __init__(self, event_bus: EventBus, rule_version: str) -> None:
        self.event_bus = event_bus
        self.rule_version = rule_version
        self.rules = VersionedRulesEngine()
        self.calculators = PluginRegistry()
        self.calculators.register("progressive", ProgressiveTaxCalculator)
        self._active_calculator = ("progressive", "default")

    def register_calculator(
        self, name: str, calculator: type[TaxCalculatorPlugin], version: str = "default"
    ) -> None:
        self.calculators.register(name, calculator, version)

    def use_calculator(self, name: str, version: str = "default") -> None:
        self._active_calculator = (name, version)

    def analyze(self, context: AnalysisContext, standard_deduction: float) -> ModuleResult:
        calculator = self.calculators.create(*self._active_calculator)
        tax_summary = calculator.calculate(context, self.rules.resolve(self.rule_version))
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

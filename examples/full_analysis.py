"""
Example: Comprehensive tax analysis for a typical American taxpayer.

Demonstrates the full Jit workflow:
1. Income processing
2. Tax calculation
3. Deduction optimization
4. AMT check
5. Quarterly estimate
6. Compliance check
7. Risk assessment
8. Tax optimization strategies
9. Decision tree — filing status
"""

from datetime import date

from jit.accounting.tax_calculator import TaxCalculator, FilingStatus
from jit.accounting.income_processor import IncomeProcessor, IncomeType, IncomeRecord
from jit.accounting.deduction_optimizer import DeductionOptimizer, DeductionType
from jit.accounting.amt_calculator import AMTCalculator
from jit.accounting.quarterly_estimator import QuarterlyEstimator
from jit.legal.compliance_engine import ComplianceEngine
from jit.algorithms.decision_tree import DecisionTree
from jit.algorithms.optimizer import TaxOptimizer
from jit.algorithms.risk_assessor import RiskAssessor
from jit.utils.formatters import format_tax_summary, format_currency


def main():
    print("\n" + "=" * 70)
    print("  JIT — Automatic Recursive Algorithmic Accounting & Legal Analysis")
    print("  Example: Jane Doe, Software Engineer, 2024 Tax Year")
    print("=" * 70)

    # -----------------------------------------------------------------------
    # 1. Income Processing
    # -----------------------------------------------------------------------
    print("\n[1] INCOME PROCESSING")
    processor = IncomeProcessor()
    processor.add_w2(
        amount=120_000,
        source="TechCorp Inc",
        tax_year=2024,
        withheld_federal=22_000,
        withheld_state=7_000,
    )
    processor.add_1099_nec(
        amount=15_000,
        source="Freelance Client LLC",
        tax_year=2024,
    )
    processor.add_record(
        IncomeRecord(
            income_type=IncomeType.DIVIDENDS_QUALIFIED,
            amount=3_000,
            source="Brokerage",
            tax_year=2024,
        )
    )
    processor.add_capital_transaction(
        proceeds=25_000,
        cost_basis=18_000,
        source="Brokerage",
        tax_year=2024,
        acquisition_date=date(2022, 6, 1),
        disposition_date=date(2024, 3, 15),
    )

    summary = processor.process(2024)
    print(f"  W-2 Wages:               {format_currency(summary.total_w2_wages)}")
    print(f"  Self-Employment:         {format_currency(summary.total_self_employment)}")
    print(f"  Qualified Dividends:     {format_currency(summary.total_qualified_dividends)}")
    print(f"  LT Capital Gains:        {format_currency(summary.net_long_term_capital_gains)}")
    print(f"  Gross Income:            {format_currency(summary.gross_income)}")
    print(f"  Federal Withheld:        {format_currency(summary.total_federal_withheld)}")

    # -----------------------------------------------------------------------
    # 2. Filing Status Recommendation
    # -----------------------------------------------------------------------
    print("\n[2] FILING STATUS RECOMMENDATION")
    fs_tree = DecisionTree.build_filing_status_tree()
    fs_result = fs_tree.evaluate(
        {
            "is_married": False,
            "is_qualifying_surviving_spouse": False,
            "has_qualifying_dependent": False,
        }
    )
    print(f"  {fs_result.recommendation}")
    print(f"  Confidence: {fs_result.confidence:.0%}")

    # -----------------------------------------------------------------------
    # 3. Deduction Optimization
    # -----------------------------------------------------------------------
    print("\n[3] DEDUCTION OPTIMIZATION")
    optimizer = DeductionOptimizer()
    optimizer.add_deduction(DeductionType.MORTGAGE_INTEREST, 14_000)
    optimizer.add_deduction(DeductionType.STATE_LOCAL_TAX, 10_000)
    optimizer.add_deduction(DeductionType.CHARITABLE_CASH, 3_000)
    optimizer.add_deduction(DeductionType.TRADITIONAL_IRA, 7_000, "Traditional IRA")

    deduction_result = optimizer.optimize(
        agi=summary.gross_income,
        filing_status=FilingStatus.SINGLE,
        age=35,
        qbi_income=summary.total_self_employment,
    )
    print(f"  Standard Deduction:       {format_currency(deduction_result.standard_deduction)}")
    print(f"  Itemized Deduction:       {format_currency(deduction_result.itemized_deduction)}")
    print(f"  Recommended Method:       {deduction_result.recommended_method.upper()}")
    print(f"  QBI Deduction:            {format_currency(deduction_result.qbi_deduction)}")
    if deduction_result.opportunities:
        print("  Opportunities:")
        for opp in deduction_result.opportunities[:3]:
            print(f"    • {opp}")

    # -----------------------------------------------------------------------
    # 4. Tax Calculation
    # -----------------------------------------------------------------------
    print("\n[4] TAX CALCULATION")
    calculator = TaxCalculator(tax_year=2024)
    tax_result = calculator.calculate(
        gross_income=summary.gross_income,
        filing_status=FilingStatus.SINGLE,
        adjustments=deduction_result.above_the_line_total,
        deductions=deduction_result.recommended_deduction,
        w2_wages=summary.total_w2_wages,
        self_employment_income=summary.total_self_employment,
        long_term_capital_gains=summary.net_long_term_capital_gains,
        qualified_dividends=summary.total_qualified_dividends,
        state_code="CA",
    )
    print(format_tax_summary(tax_result))

    # -----------------------------------------------------------------------
    # 5. AMT Check
    # -----------------------------------------------------------------------
    print("\n[5] AMT CHECK")
    amt_calc = AMTCalculator()
    amt_result = amt_calc.calculate(
        regular_taxable_income=tax_result.taxable_income,
        regular_tax=tax_result.federal_income_tax,
        filing_status=FilingStatus.SINGLE,
    )
    if amt_result.is_subject_to_amt:
        print(f"  ⚠  AMT Owed: {format_currency(amt_result.amt_owed)}")
    else:
        print(
            f"  ✓  Not subject to AMT (TMT: {format_currency(amt_result.tentative_minimum_tax)}, "
            f"Regular Tax: {format_currency(tax_result.federal_income_tax)})"
        )

    # -----------------------------------------------------------------------
    # 6. Quarterly Estimated Payments
    # -----------------------------------------------------------------------
    print("\n[6] QUARTERLY ESTIMATED PAYMENTS")
    estimator = QuarterlyEstimator(tax_year=2024)
    quarterly = estimator.estimate(
        expected_total_tax=tax_result.total_federal_tax,
        prior_year_tax=18_000,
        prior_year_agi=125_000,
        filing_status=FilingStatus.SINGLE,
        w2_withholding=summary.total_federal_withheld,
    )
    for qp in quarterly.quarterly_payments:
        print(f"  Q{qp.quarter} ({qp.due_date}): {format_currency(qp.required_payment)}")
    print(f"  Total Required:         {format_currency(quarterly.total_required)}")
    if quarterly.potential_penalty > 0:
        print(f"  Potential Penalty:      {format_currency(quarterly.potential_penalty)}")

    # -----------------------------------------------------------------------
    # 7. Compliance Check
    # -----------------------------------------------------------------------
    print("\n[7] COMPLIANCE CHECK")
    compliance_engine = ComplianceEngine()
    compliance = compliance_engine.check_individual_tax_compliance(
        gross_income=summary.gross_income,
        tax_year=2024,
        filing_status_str="single",
        taxes_withheld=summary.total_federal_withheld,
        taxes_paid=quarterly.total_required,
        self_employment_income=summary.total_self_employment,
    )
    print(f"  Overall Risk:           {compliance.overall_risk.value.upper()}")
    print(f"  Compliance Score:       {compliance.compliance_score:.2%}")
    if compliance.issues:
        print("  Issues:")
        for issue in compliance.issues:
            print(f"    [{issue.risk_level.value.upper()}] {issue.title}")
    else:
        print("  ✓  No compliance issues detected.")

    # -----------------------------------------------------------------------
    # 8. Risk Assessment
    # -----------------------------------------------------------------------
    print("\n[8] AUDIT RISK ASSESSMENT")
    risk_assessor = RiskAssessor()
    risk_profile = risk_assessor.assess_individual_tax(
        agi=tax_result.adjusted_gross_income,
        has_schedule_c=True,  # Freelance income
        deduction_to_income_ratio=deduction_result.recommended_deduction / summary.gross_income,
    )
    print(f"  Audit Risk:             {risk_profile.audit_risk_rating}")
    print(f"  Overall Risk:           {risk_profile.overall_risk_rating}")
    print(f"  Est. Audit Probability: {risk_profile.estimated_audit_probability:.2%}")
    print("  Risk Factors Present:")
    for factor in risk_profile.present_factors:
        print(f"    • {factor.description}")

    # -----------------------------------------------------------------------
    # 9. Tax Optimization Strategies
    # -----------------------------------------------------------------------
    print("\n[9] TAX OPTIMIZATION STRATEGIES")
    tax_optimizer = TaxOptimizer()
    optimization = tax_optimizer.optimize(
        gross_income=summary.gross_income,
        current_tax=tax_result.total_federal_tax,
        marginal_rate=tax_result.marginal_federal_rate,
        filing_status="single",
        age=35,
        has_401k_access=True,
        current_401k_contribution=6_000,
        self_employment_income=summary.total_self_employment,
        has_hsa_eligible_plan=False,
        has_capital_losses=0,
        unrealized_capital_gains=10_000,
        qualified_business_income=summary.total_self_employment,
        is_business_owner=True,
    )
    print(f"  Current Tax:            {format_currency(optimization.current_estimated_tax)}")
    print(f"  Optimized Tax:          {format_currency(optimization.optimized_estimated_tax)}")
    print(
        f"  Potential Savings:      {format_currency(optimization.total_savings)} "
        f"({optimization.savings_percentage:.1f}%)"
    )
    print("  Top Strategies:")
    for strategy in optimization.strategies[:5]:
        print(
            f"    [{strategy.implementation_complexity.upper()}] {strategy.title}: "
            f"{format_currency(strategy.estimated_savings)}"
        )

    print("\n" + "=" * 70)
    print("  Analysis Complete. Consult a qualified CPA or tax attorney for")
    print("  personalized advice before filing.")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()

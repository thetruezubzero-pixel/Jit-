"""
Example: Running a case through the JitPlatform orchestrator.

Demonstrates the upgradeable platform architecture — core contracts, the
plugin registry, the event bus, and versioned rules — driving the same
accounting, legal, and algorithms engines used by ``examples/full_analysis.py``
and the REST API, but through a single ``analyze_case`` call with an
audit trail of every module that ran.
"""

import json
from pathlib import Path

from jit.core.models import AnalysisContext, DeductionRecord, IncomeRecord, LegalDocument
from jit.platform import JitPlatform


def load_context(path: Path) -> AnalysisContext:
    payload = json.loads(path.read_text())
    return AnalysisContext(
        case_id=payload["case_id"],
        filing_status=payload["filing_status"],
        state=payload["state"],
        incomes=[IncomeRecord(**income) for income in payload["incomes"]],
        deductions=[DeductionRecord(**deduction) for deduction in payload["deductions"]],
        legal_documents=[LegalDocument(**doc) for doc in payload["legal_documents"]],
    )


def main() -> None:
    print("\n" + "=" * 70)
    print("  JIT PLATFORM — Cross-Module Orchestration Demo")
    print("=" * 70)

    context = load_context(Path(__file__).parent / "sample_case.json")
    platform = JitPlatform()
    response = platform.analyze_case(context)

    accounting = response.data["accounting"]
    legal = response.data["legal"]
    algorithms = response.data["algorithms"]

    print(f"\nCase: {context.case_id} ({context.filing_status}, {context.state})")

    print("\n[ACCOUNTING]")
    print(f"  Gross income:            ${accounting['gross_income']:,.2f}")
    print(f"  Itemized deductions:     ${accounting['itemized_deductions']:,.2f}")
    print(f"  Deduction recommendation: {accounting['deduction_recommendation']}")
    print(f"  Total tax:               ${accounting['total_tax']:,.2f}")
    print(f"  Quarterly estimate:      ${accounting['quarterly_estimate']:,.2f}")

    print("\n[LEGAL]")
    print(f"  Documents reviewed: {legal['results'][0]['document_count']}")
    print(f"  Citations found:    {legal['citations']}")
    print(f"  Risk score:         {legal['risk_score']:.2f}")
    print(f"  Compliance status:  {legal['compliance_status']}")

    print("\n[ALGORITHMS]")
    print(f"  Primary recommendation: {algorithms['primary_recommendation']}")
    print(f"  Filing status guidance: {algorithms['filing_status_guidance']}")
    print(f"  Total potential savings: ${algorithms['total_potential_savings']:,.2f}")

    print("\n[AUDIT TRAIL]")
    for record in response.audit_trail:
        print(f"  - {record.topic}: {record.payload}")

    print(f"\nServices registered: {response.data['services']}")
    print("\n" + "=" * 70 + "\n")


if __name__ == "__main__":
    main()

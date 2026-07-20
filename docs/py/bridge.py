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


def _extract_amount(text: str) -> float | None:
    """Pull the dollar figure out of free text, handling '150k'/'1.2m'/'$1,234,567'.

    Text like "1099 income of 200k" contains multiple bare numbers where only
    one is actually a dollar amount, so this scores every candidate — a '$'
    prefix, comma grouping, or k/m suffix are strong signals of an intended
    amount — rather than just taking the first number in the string (which
    would grab '1099' as if it were a dollar figure, not a form number).
    """
    import re

    best_value = None
    best_score = -1
    for match in re.finditer(r"\$?\s*(\d[\d,]*(?:\.\d+)?)\s*([kKmM])?", text):
        raw, suffix = match.group(1), (match.group(2) or "").lower()
        number = float(raw.replace(",", ""))
        if suffix == "k":
            number *= 1_000
        elif suffix == "m":
            number *= 1_000_000

        score = 0
        if text[match.start()] == "$" or (match.start() > 0 and text[match.start() - 1] == "$"):
            score += 2
        if "," in raw:
            score += 1
        if suffix:
            score += 2

        if score > best_score or (
            score == best_score and (best_value is None or number > best_value)
        ):
            best_score = score
            best_value = number

    return best_value


def _extract_filing_status(text: str) -> str:
    lowered = text.lower()
    if "surviving spouse" in lowered or "widow" in lowered:
        return "qualifying_surviving_spouse"
    if "married" in lowered and ("separat" in lowered):
        return "married_filing_separately"
    if "married" in lowered or "joint" in lowered:
        return "married_filing_jointly"
    if "head of household" in lowered or " hoh" in lowered:
        return "head_of_household"
    return "single"


_STATE_NAMES = {
    "california": "CA",
    "new york": "NY",
    "texas": "TX",
    "florida": "FL",
    "washington": "WA",
    "massachusetts": "MA",
    "illinois": "IL",
}


def _extract_state(text: str) -> str:
    lowered = text.lower()
    for name, code in _STATE_NAMES.items():
        if name in lowered:
            return code
    import re

    match = re.search(r"\bin ([A-Z]{2})\b", text)
    return match.group(1) if match else "CA"


def _has_any(text: str, *keywords: str) -> bool:
    lowered = text.lower()
    return any(kw in lowered for kw in keywords)


def _mentions_filing_status(text: str) -> bool:
    return _has_any(
        text,
        "married",
        "single",
        "separat",
        "joint",
        "widow",
        "surviving spouse",
        "head of household",
        " hoh",
    )


def _mentions_state(text: str) -> bool:
    if _has_any(text, *_STATE_NAMES):
        return True
    import re

    return bool(re.search(r"\bin ([A-Z]{2})\b", text))


# Remembered across messages within one browser session (this module stays
# loaded in Pyodide for as long as the page is open), so a follow-up like
# "what if I'm married instead?" doesn't need to restate the income again.
# Reset with the "chat_reset" handler (a fresh page load also clears it).
_conversation_context: dict = {
    "amount": None,
    "filing_status": None,
    "state": None,
    "pending_intent": None,
}

# Intents where a dollar amount is essential to computing anything real —
# rather than silently guessing $120k when none is given or remembered,
# chat() asks for it instead.
_NEEDS_AMOUNT = {
    "tax_calculate",
    "deduction_optimize",
    "amt_calculate",
    "quarterly_estimate",
    "compliance_check",
    "algorithm_optimize",
    "risk_assess",
    "platform_analyze",
}


# A small built-in library of tax-law facts (2024 tax year) the chat can
# recite directly, for questions that want a definitive number or a plain
# explanation rather than a calculation run against the user's own figures.
# Keyed by the topic keywords that should trigger each entry; checked before
# intent routing so "what's the SALT cap" doesn't get misrouted into running
# a calculator against a guessed income.
_FACTS = [
    {
        "keywords": ("standard deduction",),
        "answer": (
            "2024 standard deduction: $14,600 (single or married filing separately), "
            "$29,200 (married filing jointly or qualifying surviving spouse), "
            "$21,900 (head of household). Add $1,550 per filer 65+ or blind "
            "($1,950 if single/HOH)."
        ),
    },
    {
        "keywords": ("salt cap", "salt deduction"),
        "answer": (
            "The SALT (state and local tax) itemized deduction is capped at $10,000 "
            "per return ($5,000 if married filing separately) through 2025 under the "
            "TCJA. Owners of pass-through businesses in many states can work around "
            "it via a Pass-Through Entity Tax (PTET) election, which lets the entity "
            "pay and deduct state tax at the business level instead."
        ),
    },
    {
        "keywords": ("backdoor roth",),
        "answer": (
            "A backdoor Roth IRA: contribute to a nondeductible traditional IRA "
            "(2024 limit $7,000, or $8,000 if 50+), then convert it to a Roth IRA. "
            "There's no income limit on conversions, even though direct Roth "
            "contributions phase out above ~$146,000 single / $230,000 married "
            "filing jointly (2024). Watch the pro-rata rule if you hold other "
            "pre-tax IRA balances — the conversion is taxed proportionally across "
            "all your traditional IRA funds, not just the new nondeductible one."
        ),
    },
    {
        "keywords": ("ptet", "pass-through entity tax", "pass through entity tax"),
        "answer": (
            "A Pass-Through Entity Tax (PTET) election lets an S-corp or "
            "partnership pay state income tax at the entity level and deduct it "
            "as a business expense (unlimited, unlike the owner's personal SALT "
            "deduction, which is capped at $10,000). The owner then gets an "
            "offsetting state tax credit on their personal return. Most states "
            "with an income tax now offer some version of this."
        ),
    },
    {
        "keywords": ("401k limit", "401(k) limit", "401k contribution", "elective deferral"),
        "answer": (
            "2024 401(k)/403(b) elective deferral limit: $23,000, plus a $7,500 "
            "catch-up if you're 50+ ($30,500 total). Combined employee+employer "
            "limit is $69,000 ($76,500 with catch-up)."
        ),
    },
    {
        "keywords": ("ira limit", "ira contribution"),
        "answer": (
            "2024 IRA contribution limit (traditional + Roth combined): $7,000, "
            "or $8,000 if you're 50+. Roth eligibility phases out at "
            "$146,000-$161,000 MAGI (single) or $230,000-$240,000 (married filing "
            "jointly)."
        ),
    },
    {
        "keywords": ("hsa limit", "hsa contribution"),
        "answer": (
            "2024 HSA contribution limit: $4,150 (self-only coverage) or $8,300 "
            "(family coverage), plus a $1,000 catch-up if you're 55+. Requires an "
            "HSA-eligible high-deductible health plan."
        ),
    },
    {
        "keywords": ("capital gains rate", "long term capital gains", "ltcg rate"),
        "answer": (
            "2024 long-term capital gains rates: 0% up to $47,025 taxable income "
            "(single) / $94,050 (married filing jointly); 15% above that up to "
            "$518,900 / $583,750; 20% above those thresholds. A 3.8% Net "
            "Investment Income Tax (NIIT) can also apply above $200,000 / "
            "$250,000 MAGI."
        ),
    },
    {
        "keywords": ("amt exemption",),
        "answer": (
            "2024 AMT exemption: $85,700 (single/HOH), $133,300 (married filing "
            "jointly), phasing out at 25 cents per dollar above $609,350 / "
            "$1,218,700 AMTI. AMT rate is 26% up to $232,600 of AMT income above "
            "the exemption, 28% above that."
        ),
    },
    {
        "keywords": ("fbar threshold", "fbar limit"),
        "answer": (
            "FBAR (FinCEN Form 114) is required if the aggregate value of your "
            "foreign financial accounts exceeded $10,000 at any point during the "
            "year. FATCA Form 8938 has higher, filing-status- and "
            "residency-dependent thresholds (e.g. $50,000 year-end / $75,000 "
            "any-time for a single filer living in the US)."
        ),
    },
    {
        "keywords": ("qbi", "qualified business income", "section 199a", "199a deduction"),
        "answer": (
            "The Section 199A QBI deduction lets eligible pass-through business "
            "owners deduct up to 20% of qualified business income. Full "
            "deduction below $191,950 taxable income (single) / $383,900 "
            "(married filing jointly) in 2024; above that, wage/property limits "
            "phase in, and specified service businesses (SSTBs — law, "
            "accounting, consulting, etc.) lose the deduction entirely once "
            "fully phased out."
        ),
    },
    {
        "keywords": ("child tax credit",),
        "answer": (
            "2024 Child Tax Credit: $2,000 per qualifying child under 17, up to "
            "$1,700 of which is refundable (Additional CTC). Phases out $50 per "
            "$1,000 of MAGI above $200,000 (single/HOH) or $400,000 (married "
            "filing jointly)."
        ),
    },
    {
        "keywords": ("eitc", "earned income tax credit", "earned income credit"),
        "answer": (
            "2024 Earned Income Tax Credit maximum: $632 (no children), $4,213 "
            "(1 child), $6,960 (2 children), $7,830 (3+ children). Fully phases "
            "out around $18,600-$59,900 (single/HOH) or $25,500-$66,800 (married "
            "filing jointly) depending on number of qualifying children."
        ),
    },
    {
        "keywords": (
            "dependent care credit",
            "child and dependent care credit",
            "child care credit",
        ),
        "answer": (
            "The Child and Dependent Care Credit applies to up to $3,000 of "
            "care expenses for one qualifying person, or $6,000 for two or "
            "more. The credit rate is 20%-35% of those expenses depending on "
            "AGI (35% at AGI $15,000 or below, phasing down to 20% above "
            "$43,000)."
        ),
    },
    {
        "keywords": ("american opportunity credit", "aotc"),
        "answer": (
            "The American Opportunity Tax Credit: up to $2,500 per student "
            "(100% of the first $2,000 of qualified expenses plus 25% of the "
            "next $2,000), 40% refundable (up to $1,000). Phases out at MAGI "
            "$80,000-$90,000 (single) or $160,000-$180,000 (married filing "
            "jointly). Limited to a student's first 4 years of postsecondary "
            "education."
        ),
    },
    {
        "keywords": ("lifetime learning credit",),
        "answer": (
            "The Lifetime Learning Credit: 20% of up to $10,000 of qualified "
            "education expenses per return (max $2,000), nonrefundable. Same "
            "MAGI phase-out as the American Opportunity Credit ($80,000-$90,000 "
            "single, $160,000-$180,000 married filing jointly), but with no "
            "limit on the number of years you can claim it."
        ),
    },
    {
        "keywords": ("estate tax exemption", "estate tax exclusion"),
        "answer": (
            "2024 federal estate tax basic exclusion amount: $13.61 million per "
            "person ($27.22 million for a married couple with portability). "
            "Amounts above the exclusion are taxed up to 40%. This exclusion is "
            "scheduled to roughly halve at the end of 2025 absent new "
            "legislation."
        ),
    },
    {
        "keywords": ("gift tax exclusion", "annual gift exclusion"),
        "answer": (
            "2024 annual gift tax exclusion: $18,000 per recipient ($36,000 for "
            "a married couple splitting gifts), with no limit on the number of "
            "recipients. Gifts above that use up part of your lifetime estate "
            "tax exclusion rather than triggering gift tax immediately."
        ),
    },
    {
        "keywords": ("529 plan", "529 contribution"),
        "answer": (
            "529 plan contributions aren't federally deductible, but growth and "
            "withdrawals for qualified education expenses are tax-free. "
            "Contributions count as gifts (2024 annual exclusion $18,000 per "
            "beneficiary), but a special election lets you front-load 5 years "
            "of exclusions at once ($90,000, or $180,000 for a couple) without "
            "using more exclusion in years 2-5."
        ),
    },
    {
        "keywords": ("self employment tax rate", "self-employment tax rate", "se tax rate"),
        "answer": (
            "Self-employment tax is 15.3% total: 12.4% Social Security (on "
            "earnings up to the annual wage base, $168,600 in 2024) plus 2.9% "
            "Medicare (uncapped), computed on 92.35% of net self-employment "
            "earnings. Half of the SE tax you pay is deductible above the "
            "line."
        ),
    },
    {
        "keywords": ("capital loss deduction", "capital loss limit"),
        "answer": (
            "Net capital losses offset capital gains dollar-for-dollar, and up "
            "to $3,000 of any remaining loss ($1,500 if married filing "
            "separately) can offset ordinary income per year. Unused losses "
            "carry forward indefinitely to future tax years."
        ),
    },
    {
        "keywords": ("charitable deduction limit", "charitable contribution limit"),
        "answer": (
            "Charitable cash gifts to public charities are deductible up to "
            "60% of AGI; gifts of appreciated long-term property are limited to "
            "30% of AGI. Contributions above those limits carry forward for up "
            "to 5 years."
        ),
    },
    {
        "keywords": ("kiddie tax",),
        "answer": (
            'The "kiddie tax" taxes a child\'s unearned income (interest, '
            "dividends, capital gains) above $2,600 (2024) at the parents' "
            "marginal rate. The first $1,300 is tax-free and the next $1,300 "
            "is taxed at the child's own rate."
        ),
    },
    {
        "keywords": ("social security wage base", "ss wage base"),
        "answer": (
            "2024 Social Security wage base: $168,600 — the 6.2% employee "
            "(12.4% self-employed) Social Security payroll tax only applies up "
            "to this amount of earnings. The 1.45%/2.9% Medicare portion has no "
            "wage cap."
        ),
    },
    {
        "keywords": ("niit", "net investment income tax"),
        "answer": (
            "The Net Investment Income Tax (NIIT) is a 3.8% surtax on the "
            "lesser of your net investment income or the amount your MAGI "
            "exceeds $200,000 (single/HOH), $250,000 (married filing jointly), "
            "or $125,000 (married filing separately)."
        ),
    },
    {
        "keywords": ("additional medicare tax",),
        "answer": (
            "The Additional Medicare Tax adds 0.9% on wages or self-employment "
            "income above $200,000 (single), $250,000 (married filing "
            "jointly), or $125,000 (married filing separately). It isn't "
            "employer-matched and the thresholds aren't indexed for inflation."
        ),
    },
]


def _match_fact(text: str) -> str | None:
    lowered = text.lower()
    for fact in _FACTS:
        if any(kw in lowered for kw in fact["keywords"]):
            return fact["answer"]
    return None


_INTENT_KEYWORDS = {
    "amt_calculate": ("amt", "alternative minimum tax"),
    "quarterly_estimate": ("quarterly", "estimated payment", "estimated tax payment"),
    "compliance_check": ("compliance", "fbar", "fatca", "foreign account", "1099 filing"),
    "document_analyze": ("contract", "clause", "document", "agreement", "indemnif"),
    "filing_status_tree": ("filing status", "should i file", "file as single", "file jointly"),
    "deduction_optimize": ("deduction", "itemize", "itemized", "standard deduction"),
    "risk_assess": ("audit risk", "audit probability", "get audited", "irs audit"),
    "algorithm_optimize": (
        "save on tax",
        "tax strategy",
        "tax strategies",
        "reduce my tax",
        "optimize",
    ),
    "tax_calculate": ("tax", "calculate", "how much tax", "owe"),
    "platform_analyze": ("full analysis", "everything", "complete case", "full case", "overall"),
}


def _classify_intent(text: str) -> tuple[str, bool]:
    """Return (intent, matched) — matched is False when nothing in the text
    hit any topic keyword, so the caller can tell "genuinely a full-case
    question" apart from "no topic here, e.g. just an income figure."
    """
    lowered = text.lower()
    scores = {
        intent: sum(1 for kw in keywords if kw in lowered)
        for intent, keywords in _INTENT_KEYWORDS.items()
    }
    best_intent = max(scores, key=scores.get)
    if scores[best_intent] == 0:
        return "platform_analyze", False
    return best_intent, True


def chat(payload: dict) -> dict:
    """Route a free-text message to the right engine(s) and reply in one place.

    This is plain keyword/regex matching, not a language model — it stays
    within "no paid API, GitHub Pages only." It reuses the exact same
    handlers as every other tab, just chosen from the message text instead
    of a form.
    """
    message = payload.get("message", "")

    fact_answer = _match_fact(message)
    if fact_answer is not None:
        # A factual lookup ("what's the SALT cap") doesn't depend on the
        # user's own numbers and shouldn't disturb whatever topic/amount is
        # already remembered, so it's answered immediately, standalone.
        return {
            "intent": "fact",
            "extracted": {"amount": None, "filing_status": None, "state": None},
            "reply": fact_answer,
            "result": {},
        }

    extracted_amount = _extract_amount(message)
    amount = extracted_amount if extracted_amount is not None else _conversation_context["amount"]

    filing_status = (
        _extract_filing_status(message)
        if _mentions_filing_status(message)
        else (_conversation_context["filing_status"] or "single")
    )
    state = (
        _extract_state(message)
        if _mentions_state(message)
        else (_conversation_context["state"] or "CA")
    )
    self_employed = _has_any(
        message, "self employ", "self-employ", "1099", "schedule c", "freelance"
    )
    business_owner = _has_any(
        message, "business owner", "own a business", "my business", "llc", "s-corp"
    )

    intent, intent_matched = _classify_intent(message)
    if not intent_matched and _conversation_context["pending_intent"]:
        # This message is just an answer ("150k, self-employed") to the
        # question chat() asked last turn, not a fresh, unrelated topic —
        # resume what was actually being asked about instead of falling
        # back to the generic full-case default.
        intent = _conversation_context["pending_intent"]

    if intent in _NEEDS_AMOUNT and amount is None:
        _conversation_context["pending_intent"] = intent
        return {
            "intent": "clarify",
            "extracted": {
                "amount": None,
                "filing_status": filing_status,
                "state": state,
                "self_employed": self_employed,
                "business_owner": business_owner,
            },
            "reply": (
                "I don't have an income figure for this yet — what's your approximate "
                'income (e.g. "150k" or "$85,000")?'
            ),
            "result": {},
        }

    # Remember what this turn established, so a follow-up question can omit it.
    _conversation_context["amount"] = amount
    _conversation_context["filing_status"] = filing_status
    _conversation_context["state"] = state
    _conversation_context["pending_intent"] = None

    if intent == "tax_calculate":
        result = tax_calculate(
            {
                "gross_income": amount,
                "filing_status": filing_status,
                "state_code": state,
                "w2_wages": 0.0 if self_employed else amount,
                "self_employment_income": amount if self_employed else 0.0,
            }
        )
        reply = (
            f"On ${amount:,.0f} of income filing {filing_status.replace('_', ' ')} in {state}, "
            f"your estimated total tax is ${result['total_tax']:,.2f} "
            f"(effective rate {result['effective_total_rate']:.1%})."
        )
    elif intent == "amt_calculate":
        result = amt_calculate(
            {
                "regular_taxable_income": amount,
                "regular_tax": amount * 0.22,
                "filing_status": filing_status,
            }
        )
        reply = (
            f"On ${amount:,.0f} of taxable income, you are "
            f"{'likely' if result['is_subject_to_amt'] else 'not likely'} subject to AMT "
            f"(AMT owed: ${result['amt_owed']:,.2f})."
        )
    elif intent == "quarterly_estimate":
        result = quarterly_estimate(
            {
                "expected_total_tax": amount * 0.24,
                "prior_year_tax": amount * 0.24,
                "prior_year_agi": amount,
                "filing_status": filing_status,
            }
        )
        reply = (
            f"Based on an estimated ${amount * 0.24:,.0f} annual tax, your quarterly "
            f"payment should be about ${result['total_required'] / 4:,.2f}."
        )
    elif intent == "compliance_check":
        result = compliance_check(
            {
                "gross_income": amount,
                "filing_status": filing_status,
                "taxes_withheld": amount * 0.15,
                "taxes_paid": 0.0,
                "has_foreign_accounts": _has_any(message, "foreign account", "fbar", "fatca"),
                "aggregate_foreign_balance": 15_000.0 if _has_any(message, "foreign") else 0.0,
                "self_employment_income": amount if self_employed else 0.0,
            }
        )
        reply = (
            f"Compliance check: overall risk is {result['overall_risk']}, "
            f"compliance score {result['compliance_score']:.2f}. {result['summary']}"
        )
    elif intent == "document_analyze":
        result = document_analyze({"text": message, "title": "Chat-submitted text"})
        reply = (
            f"Risk score {result['risk_score']:.2f}, found {len(result['citations'])} citation(s) "
            f"and {len(result['risk_flags'])} risk flag(s)."
        )
    elif intent == "filing_status_tree":
        result = filing_status_tree(
            {
                "is_married": _has_any(message, "married"),
                "has_qualifying_dependent": _has_any(message, "dependent", "child", "kids"),
                "is_qualifying_surviving_spouse": _has_any(message, "widow", "surviving spouse"),
                "prefer_filing_separately": _has_any(message, "separately"),
            }
        )
        reply = result["recommendation"]
    elif intent == "deduction_optimize":
        result = deduction_optimize(
            {
                "agi": amount,
                "filing_status": filing_status,
                "deductions": [
                    {"deduction_type": "mortgage_interest", "amount": amount * 0.08},
                    {"deduction_type": "charitable_cash", "amount": amount * 0.03},
                ],
            }
        )
        reply = (
            f"On ${amount:,.0f} AGI, {result['recommended_method']} deduction is better "
            f"(${result['recommended_deduction']:,.0f})."
        )
    elif intent == "risk_assess":
        result = risk_assess(
            {
                "agi": amount,
                "has_schedule_c": self_employed,
                "schedule_c_income": amount if self_employed else 0.0,
                "has_crypto_transactions": _has_any(message, "crypto", "bitcoin"),
                "claimed_home_office": _has_any(message, "home office"),
            }
        )
        reply = (
            f"Your audit risk rating is {result['audit_risk_rating']} "
            f"(estimated probability {result['estimated_audit_probability']:.2%})."
        )
    elif intent == "algorithm_optimize":
        result = algorithm_optimize(
            {
                "gross_income": amount,
                "current_tax": amount * 0.24,
                "marginal_rate": 0.24,
                "filing_status": filing_status,
                "has_401k_access": not self_employed,
                "self_employment_income": amount if self_employed else 0.0,
                "is_business_owner": business_owner,
                "expected_state_tax": amount * 0.05 if business_owner else 0.0,
            }
        )
        top = result["strategies"][0]["title"] if result["strategies"] else None
        reply = (
            f"Top strategy: {top}. Total potential savings: ${result['total_savings']:,.2f}."
            if top
            else "No specific optimization strategies applied for this scenario."
        )
    else:
        result = platform_analyze(
            {
                "case_id": "chat-case",
                "filing_status": filing_status,
                "state": state,
                "incomes": [
                    {
                        "kind": "1099" if self_employed else "w2",
                        "amount": amount,
                        "source": "chat",
                    }
                ],
            }
        )
        reply = (
            f"Full case: total tax ${result['accounting']['total_tax']:,.2f}, "
            f"legal risk score {result['legal']['risk_score']:.2f}, "
            f"recommendation: {result['algorithms']['primary_recommendation']}."
        )

    _record_session_entry(intent, amount, self_employed, result)

    return {
        "intent": intent,
        "matched": intent_matched,
        "extracted": {
            "amount": amount,
            "filing_status": filing_status,
            "state": state,
            "self_employed": self_employed,
            "business_owner": business_owner,
        },
        "reply": reply,
        "result": result,
    }


def chat_reset(payload: dict) -> dict:
    """Forget everything chat() has remembered so far this session."""
    for key in _conversation_context:
        _conversation_context[key] = None
    _session_history.clear()
    return {"reset": True}


def chat_export_state(payload: dict) -> dict:
    """Serialize remembered context + session history for the frontend to
    persist (e.g. to localStorage). Pyodide's Python interpreter is
    recreated from scratch on every page load, so nothing here survives a
    refresh on its own — this is what makes that possible, across every
    intent/domain uniformly, since both structures are shared by all of
    them."""
    return {"context": dict(_conversation_context), "history": list(_session_history)}


def chat_import_state(payload: dict) -> dict:
    """Restore state previously produced by chat_export_state — called once
    right after boot with whatever was saved from the last visit."""
    context = payload.get("context") or {}
    for key in _conversation_context:
        if key in context:
            _conversation_context[key] = context[key]
    history = payload.get("history")
    if isinstance(history, list):
        _session_history.clear()
        _session_history.extend(history)
    return {"restored": True}


# History of computed (non-clarify, non-fact) chat turns this session, used
# by session_insights() below to spot patterns across the conversation —
# plain statistics over data the user already gave us, not a model.
_session_history: list = []


def _record_session_entry(intent: str, amount: float | None, self_employed: bool, result: dict):
    entry = {"intent": intent, "amount": amount, "self_employed": self_employed}
    if intent == "deduction_optimize" and isinstance(result, dict):
        entry["recommended_deduction"] = result.get("recommended_deduction")
    _session_history.append(entry)


def session_insights(payload: dict) -> dict:
    """Rule-based pattern detection over this session's chat history.

    Flags things like an income figure that changed a lot between messages,
    a deduction total that's high relative to income (a real audit-selection
    correlate, matching the same ratio risk_assess already scores), or
    self-employment income mentioned without ever checking deductions or
    audit risk. Pure statistics/heuristics over this session's own data —
    not a model, and computed entirely client-side.
    """
    insights = []

    amounts = [e["amount"] for e in _session_history if e["amount"] is not None]
    if len(amounts) >= 2 and min(amounts) > 0:
        spread = (max(amounts) - min(amounts)) / min(amounts)
        if spread > 0.5:
            insights.append(
                f"Your stated income varied a lot this session (${min(amounts):,.0f} to "
                f"${max(amounts):,.0f}) — results reflect whichever figure was most recent."
            )

    for entry in _session_history:
        deduction = entry.get("recommended_deduction")
        if entry["intent"] == "deduction_optimize" and deduction and entry["amount"]:
            ratio = deduction / entry["amount"]
            if ratio > 0.35:
                insights.append(
                    f"Deductions came out to {ratio:.0%} of AGI in one calculation — "
                    "that's a ratio the IRS's own audit-selection models flag more often; "
                    "make sure everything claimed is well documented."
                )
                break

    mentioned_self_employed = any(e["self_employed"] for e in _session_history)
    checked_deductions_or_risk = any(
        e["intent"] in ("risk_assess", "deduction_optimize") for e in _session_history
    )
    if mentioned_self_employed and not checked_deductions_or_risk:
        insights.append(
            "You mentioned self-employment income but haven't asked about deductions or "
            "audit risk yet — self-employed filers often have the most to gain from both."
        )

    return {"insights": insights, "entries_analyzed": len(_session_history)}


_HANDLERS = {
    "chat": chat,
    "chat_reset": chat_reset,
    "chat_export_state": chat_export_state,
    "chat_import_state": chat_import_state,
    "session_insights": session_insights,
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

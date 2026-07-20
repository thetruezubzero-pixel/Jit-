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
    # The suffix must be glued directly to the digits with no letter right
    # after it — otherwise "18000 mortgage interest" reads its leading "m"
    # as a million-suffix on 18000, turning $18,000 into $18,000,000,000.
    for match in re.finditer(r"\$?\s*(\d[\d,]*(?:\.\d+)?)([kKmM])?(?![a-zA-Z])", text):
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

# All 50 states + DC, so "in IT" (as in "investing in IT stocks") doesn't
# get misread as the state code "IT" -- the old check accepted *any* two
# capital letters after "in ", real state or not.
_VALID_STATE_CODES = {
    "AL",
    "AK",
    "AZ",
    "AR",
    "CA",
    "CO",
    "CT",
    "DE",
    "FL",
    "GA",
    "HI",
    "ID",
    "IL",
    "IN",
    "IA",
    "KS",
    "KY",
    "LA",
    "ME",
    "MD",
    "MA",
    "MI",
    "MN",
    "MS",
    "MO",
    "MT",
    "NE",
    "NV",
    "NH",
    "NJ",
    "NM",
    "NY",
    "NC",
    "ND",
    "OH",
    "OK",
    "OR",
    "PA",
    "RI",
    "SC",
    "SD",
    "TN",
    "TX",
    "UT",
    "VT",
    "VA",
    "WA",
    "WV",
    "WI",
    "WY",
    "DC",
}


def _extract_state(text: str) -> str | None:
    """Return a state code if one was actually stated, else None -- the
    caller decides what "no state given" should fall back to, rather than
    this function silently picking CA itself."""
    lowered = text.lower()
    for name, code in _STATE_NAMES.items():
        if name in lowered:
            return code
    import re

    match = re.search(r"\bin ([A-Za-z]{2})\b", text)
    if match:
        code = match.group(1).upper()
        if code in _VALID_STATE_CODES:
            return code
    return None


def _mentions_state(text: str) -> bool:
    return _extract_state(text) is not None


def _contains_keyword(lowered_text: str, keyword: str) -> bool:
    """Word-*start*-boundary-aware substring match, so a short keyword like
    "amt" or "owe" doesn't fire mid-word ("dreamt", "lower") -- unlike a
    plain `keyword in text` check, which has no notion of word edges at
    all. Only the leading edge is required, not a trailing one, so this
    still deliberately catches inflected forms a strict whole-word match
    would miss: "tax" inside "taxes", "deduction" inside "deductions"."""
    import re

    return re.search(r"\b" + re.escape(keyword.strip()), lowered_text) is not None


def _has_any(text: str, *keywords: str) -> bool:
    lowered = text.lower()
    return any(_contains_keyword(lowered, kw) for kw in keywords)


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


# Remembered across messages within one browser session (this module stays
# loaded in Pyodide for as long as the page is open), so a follow-up like
# "what if I'm married instead?" doesn't need to restate the income again.
# Reset with the "chat_reset" handler (a fresh page load also clears it).
_conversation_context: dict = {
    "amount": None,
    "filing_status": None,
    "state": None,
    "state_explicit": False,
    "pending_intent": None,
    "suggested_intent": None,
}

# After answering one topic, a natural next question often follows the same
# income/filing-status/state — offer it instead of waiting to be asked, and
# let a short affirmative reply run it automatically (see _is_affirmative).
# platform_analyze is excluded: it already covers everything, and every
# NEEDS_AMOUNT intent maps somewhere so the chain has real content each hop.
_NEXT_SUGGESTION = {
    "tax_calculate": "risk_assess",
    "amt_calculate": "tax_calculate",
    "quarterly_estimate": "tax_calculate",
    "compliance_check": "risk_assess",
    "filing_status_tree": "tax_calculate",
    "deduction_optimize": "algorithm_optimize",
    "risk_assess": "deduction_optimize",
    "algorithm_optimize": "deduction_optimize",
    "document_analyze": "compliance_check",
}

_SUGGESTION_TEXT = {
    "tax_calculate": "Want me to run your full tax number too?",
    "risk_assess": "Curious about your audit risk while we're at it?",
    "deduction_optimize": "Want me to take a look at your deductions too?",
    "algorithm_optimize": "Want a few tax-saving moves to consider too?",
    "compliance_check": "Should I check your compliance status too?",
}

_AFFIRMATIVE_PHRASES = {
    "yes",
    "yeah",
    "yep",
    "yup",
    "sure",
    "ok",
    "okay",
    "please",
    "please do",
    "do it",
    "go ahead",
    "sounds good",
    "yes please",
    "sure thing",
}


def _is_affirmative(text: str) -> bool:
    """True only for a short, standalone "yes"-shaped reply — not merely a
    message that happens to contain "yes" as one word among others, which
    could just as easily be a real new question ("yes but what about AMT
    instead")."""
    return text.strip().lower().rstrip(".!?") in _AFFIRMATIVE_PHRASES


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
        "citation": "IRC §63(c)",
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
        "citation": "IRC §164(b)(6)",
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
        "citation": "IRC §408A(c)(3) (conversion limit repealed); §408(d)(3) (conversion)",
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
        "citation": "IRS Notice 2020-75 (state PTET workaround to the IRC §164(b)(6) SALT cap)",
    },
    {
        "keywords": ("401k limit", "401(k) limit", "401k contribution", "elective deferral"),
        "answer": (
            "2024 401(k)/403(b) elective deferral limit: $23,000, plus a $7,500 "
            "catch-up if you're 50+ ($30,500 total). Combined employee+employer "
            "limit is $69,000 ($76,500 with catch-up)."
        ),
        "citation": "IRC §402(g)",
    },
    {
        "keywords": ("ira limit", "ira contribution"),
        "answer": (
            "2024 IRA contribution limit (traditional + Roth combined): $7,000, "
            "or $8,000 if you're 50+. Roth eligibility phases out at "
            "$146,000-$161,000 MAGI (single) or $230,000-$240,000 (married filing "
            "jointly)."
        ),
        "citation": "IRC §219(b)(5)(A)",
    },
    {
        "keywords": ("hsa limit", "hsa contribution"),
        "answer": (
            "2024 HSA contribution limit: $4,150 (self-only coverage) or $8,300 "
            "(family coverage), plus a $1,000 catch-up if you're 55+. Requires an "
            "HSA-eligible high-deductible health plan."
        ),
        "citation": "IRC §223(b)",
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
        "citation": "IRC §1(h)",
    },
    {
        "keywords": ("amt exemption",),
        "answer": (
            "2024 AMT exemption: $85,700 (single/HOH), $133,300 (married filing "
            "jointly), phasing out at 25 cents per dollar above $609,350 / "
            "$1,218,700 AMTI. AMT rate is 26% up to $232,600 of AMT income above "
            "the exemption, 28% above that."
        ),
        "citation": "IRC §55(d)",
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
        "citation": "31 U.S.C. §5314 (FBAR, not the IRC); IRC §6038D (FATCA Form 8938)",
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
        "citation": "IRC §199A",
    },
    {
        "keywords": ("child tax credit",),
        "answer": (
            "2024 Child Tax Credit: $2,000 per qualifying child under 17, up to "
            "$1,700 of which is refundable (Additional CTC). Phases out $50 per "
            "$1,000 of MAGI above $200,000 (single/HOH) or $400,000 (married "
            "filing jointly)."
        ),
        "citation": "IRC §24",
    },
    {
        "keywords": ("eitc", "earned income tax credit", "earned income credit"),
        "answer": (
            "2024 Earned Income Tax Credit maximum: $632 (no children), $4,213 "
            "(1 child), $6,960 (2 children), $7,830 (3+ children). Fully phases "
            "out around $18,600-$59,900 (single/HOH) or $25,500-$66,800 (married "
            "filing jointly) depending on number of qualifying children."
        ),
        "citation": "IRC §32",
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
        "citation": "IRC §21",
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
        "citation": "IRC §25A(b)",
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
        "citation": "IRC §25A(c)",
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
        "citation": "IRC §2010(c)",
    },
    {
        "keywords": ("gift tax exclusion", "annual gift exclusion"),
        "answer": (
            "2024 annual gift tax exclusion: $18,000 per recipient ($36,000 for "
            "a married couple splitting gifts), with no limit on the number of "
            "recipients. Gifts above that use up part of your lifetime estate "
            "tax exclusion rather than triggering gift tax immediately."
        ),
        "citation": "IRC §2503(b)",
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
        "citation": "IRC §529",
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
        "citation": "IRC §1401",
    },
    {
        "keywords": ("capital loss deduction", "capital loss limit"),
        "answer": (
            "Net capital losses offset capital gains dollar-for-dollar, and up "
            "to $3,000 of any remaining loss ($1,500 if married filing "
            "separately) can offset ordinary income per year. Unused losses "
            "carry forward indefinitely to future tax years."
        ),
        "citation": "IRC §1211(b); §1212",
    },
    {
        "keywords": ("charitable deduction limit", "charitable contribution limit"),
        "answer": (
            "Charitable cash gifts to public charities are deductible up to "
            "60% of AGI; gifts of appreciated long-term property are limited to "
            "30% of AGI. Contributions above those limits carry forward for up "
            "to 5 years."
        ),
        "citation": "IRC §170(b)",
    },
    {
        "keywords": ("kiddie tax",),
        "answer": (
            'The "kiddie tax" taxes a child\'s unearned income (interest, '
            "dividends, capital gains) above $2,600 (2024) at the parents' "
            "marginal rate. The first $1,300 is tax-free and the next $1,300 "
            "is taxed at the child's own rate."
        ),
        "citation": "IRC §1(g)",
    },
    {
        "keywords": ("social security wage base", "ss wage base"),
        "answer": (
            "2024 Social Security wage base: $168,600 — the 6.2% employee "
            "(12.4% self-employed) Social Security payroll tax only applies up "
            "to this amount of earnings. The 1.45%/2.9% Medicare portion has no "
            "wage cap."
        ),
        "citation": "IRC §3121(a)(1) (FICA wage base)",
    },
    {
        "keywords": ("niit", "net investment income tax"),
        "answer": (
            "The Net Investment Income Tax (NIIT) is a 3.8% surtax on the "
            "lesser of your net investment income or the amount your MAGI "
            "exceeds $200,000 (single/HOH), $250,000 (married filing jointly), "
            "or $125,000 (married filing separately)."
        ),
        "citation": "IRC §1411",
    },
    {
        "keywords": ("additional medicare tax",),
        "answer": (
            "The Additional Medicare Tax adds 0.9% on wages or self-employment "
            "income above $200,000 (single), $250,000 (married filing "
            "jointly), or $125,000 (married filing separately). It isn't "
            "employer-matched and the thresholds aren't indexed for inflation."
        ),
        "citation": "IRC §3101(b)(2)",
    },
    {
        "keywords": ("mortgage interest deduction", "mortgage interest limit"),
        "answer": (
            "Mortgage interest is deductible (itemized) on up to $750,000 of "
            "acquisition debt ($375,000 if married filing separately) for "
            "loans originated after December 15, 2017. Loans from before then "
            "are grandfathered at the older $1 million cap."
        ),
        "citation": "IRC §163(h)(3)",
    },
    {
        "keywords": ("student loan interest deduction",),
        "answer": (
            "The student loan interest deduction: up to $2,500/year, taken "
            "above the line (no itemizing needed). Phases out at MAGI "
            "$80,000-$95,000 (single) or $165,000-$195,000 (married filing "
            "jointly) in 2024; unavailable if married filing separately."
        ),
        "citation": "IRC §221",
    },
    {
        "keywords": (
            "home sale exclusion",
            "section 121",
            "sale of primary residence",
            "home sale gain exclusion",
        ),
        "answer": (
            "Section 121 lets you exclude up to $250,000 ($500,000 married "
            "filing jointly) of gain on the sale of your primary residence, "
            "as long as you owned and used it as your main home for at least "
            "2 of the last 5 years before the sale."
        ),
        "citation": "IRC §121",
    },
    {
        "keywords": ("wash sale rule", "wash sale"),
        "answer": (
            "The wash sale rule disallows a capital loss deduction if you buy "
            "the same or a substantially identical security within 30 days "
            "before or after the sale that created the loss. The disallowed "
            "loss isn't gone — it's added to the cost basis of the "
            "replacement shares."
        ),
        "citation": "IRC §1091",
    },
    {
        "keywords": ("1031 exchange", "like kind exchange", "like-kind exchange"),
        "answer": (
            "A 1031 (like-kind) exchange lets you defer capital gains tax on "
            "the sale of investment or business real property by rolling the "
            "proceeds into similar replacement property. You must identify "
            "the replacement within 45 days of the sale and close within 180 "
            "days. Only real property qualifies since the 2017 tax law."
        ),
        "citation": "IRC §1031",
    },
    {
        "keywords": (
            "foreign earned income exclusion",
            "feie",
        ),
        "answer": (
            "The Foreign Earned Income Exclusion lets a qualifying U.S. "
            "citizen or resident exclude up to $126,500 (2024) of foreign "
            "earned income from U.S. tax, if you meet either the bona fide "
            "residence test or the physical presence test (330 full days "
            "abroad in a 12-month period)."
        ),
        "citation": "IRC §911",
    },
    {
        "keywords": ("section 179", "bonus depreciation"),
        "answer": (
            "Section 179 lets a business immediately expense up to "
            "$1,160,000 (2024) of qualifying equipment/property purchases, "
            "phasing out above $2,890,000 in purchases for the year. Bonus "
            "depreciation is 60% for 2024 (down from 100% in 2022), and is "
            "scheduled to keep phasing down 20 points a year absent new "
            "legislation."
        ),
        "citation": "IRC §179 (bonus depreciation is a separate provision, IRC §168(k))",
    },
    {
        "keywords": ("net operating loss", "nol carryforward", "nol carryback"),
        "answer": (
            "Post-2017 net operating losses carry forward indefinitely but "
            "can only offset up to 80% of taxable income in the year "
            "they're used — they can no longer be carried back (except "
            "certain farming and insurance-company losses)."
        ),
        "citation": "IRC §172",
    },
    {
        "keywords": ("mega backdoor roth",),
        "answer": (
            "A mega backdoor Roth: if your 401(k) plan allows after-tax "
            "contributions and in-service withdrawals/conversions, you can "
            "contribute after-tax dollars beyond the $23,000 elective-"
            "deferral limit, up to the overall $69,000 limit (2024), then "
            "convert those after-tax dollars to Roth — much larger than a "
            "regular backdoor Roth's $7,000 IRA cap."
        ),
        "citation": "IRC §401(k); §402A(c)(4) (in-plan Roth rollover)",
    },
    {
        "keywords": ("educator expense deduction",),
        "answer": (
            "K-12 educators can deduct up to $300 (2024) of unreimbursed "
            "classroom supplies above the line, no itemizing required. Two "
            "educators married filing jointly can each claim their own $300."
        ),
        "citation": "IRC §62(a)(2)(D)",
    },
    {
        "keywords": ("self employed health insurance", "self-employed health insurance"),
        "answer": (
            "Self-employed people can deduct 100% of health insurance "
            "premiums (for themselves, a spouse, and dependents) above the "
            "line, limited to net self-employment income, and only for "
            "months they weren't eligible for an employer-subsidized plan."
        ),
        "citation": "IRC §162(l)",
    },
    {
        "keywords": ("mileage rate", "standard mileage"),
        "answer": (
            "2024 standard mileage rates: 67 cents/mile for business use, "
            "21 cents/mile for medical or moving (active-duty military "
            "only), and 14 cents/mile for charitable use (set by statute, "
            "not indexed for inflation)."
        ),
        "citation": "Annual IRS notice under IRC §162; §170(i) sets the charitable rate",
    },
    {
        "keywords": ("home office deduction",),
        "answer": (
            "The simplified home-office method deducts $5 per square foot "
            "of dedicated business-use space, up to 300 sq ft ($1,500 "
            "max/year). The regular method instead deducts that same "
            "business-use percentage of actual home expenses (rent, "
            "utilities, insurance, depreciation) — whichever is larger is "
            "worth comparing. Only available for space used regularly and "
            "exclusively for business."
        ),
        "citation": "IRC §280A(c)",
    },
    {
        "keywords": ("roth ira income limit", "roth ira phase out", "roth ira phase-out"),
        "answer": (
            "2024 Roth IRA contribution phases out at MAGI $146,000– "
            "$161,000 (single/head of household), $230,000–$240,000 "
            "(married filing jointly), and $0–$10,000 (married filing "
            "separately, if you lived with your spouse at all during the "
            "year)."
        ),
        "citation": "IRC §408A(c)(3)",
    },
    {
        "keywords": (
            "traditional ira deduction limit",
            "traditional ira phase out",
            "traditional ira phase-out",
        ),
        "answer": (
            "If you're covered by a workplace retirement plan, your 2024 "
            "traditional IRA deduction phases out at MAGI $77,000–$87,000 "
            "(single), $123,000–$143,000 (married filing jointly, you're "
            "covered). If only your spouse is covered, the phase-out is "
            "$230,000–$240,000. Not covered by a plan at all (and neither "
            "is your spouse)? The deduction isn't limited by income."
        ),
        "citation": "IRC §219(g)",
    },
    {
        "keywords": ("rmd", "rmd age", "required minimum distribution"),
        "answer": (
            "Required minimum distributions from traditional IRAs/401(k)s "
            "must start at age 73 (for those turning 72 after 2022), under "
            "SECURE 2.0 — rising to 75 starting in 2033. Missing an RMD "
            "carries a 25% excise tax on the shortfall (10% if corrected "
            "promptly)."
        ),
        "citation": "IRC §401(a)(9)",
    },
    {
        "keywords": ("fsa limit", "fsa contribution"),
        "answer": (
            "2024 health FSA contribution limit: $3,200 per employee "
            "(via salary reduction). Employers may allow up to $640 to "
            "carry over into the next year, or a grace period instead — "
            "not both — and unused balances above that are forfeited "
            "('use it or lose it')."
        ),
        "citation": "IRC §125(i)",
    },
    {
        "keywords": ("medical expense deduction", "medical expense threshold"),
        "answer": (
            "Unreimbursed medical/dental expenses are itemizable only "
            "above 7.5% of AGI — e.g. $100,000 AGI means the first $7,500 "
            "of medical costs isn't deductible, only the amount above it. "
            "Covers costs for yourself, a spouse, and dependents; insurance "
            "premiums paid pre-tax (most employer plans) don't count again "
            "here."
        ),
        "citation": "IRC §213",
    },
    {
        "keywords": (
            "cancellation of debt",
            "cancelled debt",
            "canceled debt",
            "1099-c",
            "1099c",
            "debt forgiveness",
        ),
        "answer": (
            "Forgiven/cancelled debt (reported on Form 1099-C) is taxable "
            "income by default — a creditor writing off what you owed is "
            "treated as if they paid it to you. The main exceptions: debt "
            "discharged in bankruptcy, or discharged while you were "
            "insolvent (liabilities exceeded assets, excludable up to the "
            "amount you were insolvent by), and qualified principal "
            "residence debt under separate rules."
        ),
        "citation": "IRC §61(a)(12) (income); exclusions under §108",
    },
    {
        "keywords": ("bankruptcy discharge", "debt discharged in bankruptcy"),
        "answer": (
            "Debt discharged through a bankruptcy case (Title 11) is fully "
            "excluded from taxable income — no 1099-C income results, "
            "unlike ordinary debt forgiveness outside bankruptcy. You "
            "generally must reduce certain tax attributes (like loss "
            "carryforwards or basis in property) by the excluded amount "
            "instead."
        ),
        "citation": "IRC §108(a)(1)(A)",
    },
    {
        "keywords": ("life insurance proceeds", "life insurance payout", "life insurance taxable"),
        "answer": (
            "Life insurance death-benefit proceeds paid in a lump sum are "
            "generally not taxable income to the beneficiary. Interest "
            "earned if payment is delayed/installment-based is taxable, "
            "and proceeds can still be pulled into the deceased's taxable "
            "estate for estate-tax purposes if they owned the policy."
        ),
        "citation": "IRC §101(a)",
    },
    {
        "keywords": (
            "disability insurance taxable",
            "disability benefits taxable",
            "short term disability taxable",
            "long term disability taxable",
        ),
        "answer": (
            "Whether disability benefits are taxable depends on who paid "
            "the premiums: benefits are tax-free if you paid the premiums "
            "yourself with after-tax dollars, but taxable if your employer "
            "paid the premiums (or you paid with pre-tax dollars). "
            "Employer-paid premiums themselves aren't taxable income to "
            "you up front — the benefit is what's taxed later."
        ),
        "citation": "IRC §104(a)(3) (self-paid, tax-free); §105(a) (employer-paid, taxable)",
    },
    {
        "keywords": ("foreign tax credit", "ftc limitation"),
        "answer": (
            "The Foreign Tax Credit lets you offset US tax dollar-for-"
            "dollar with income tax already paid to a foreign country on "
            "the same income, avoiding double taxation — the main "
            "alternative to (and usually better than) the Foreign Earned "
            "Income Exclusion for higher earners, since it's not capped at "
            "a fixed exclusion amount. The credit is limited to the US tax "
            "attributable to that foreign income (computed per income "
            "category/'basket'); unused credit carries back 1 year or "
            "forward 10."
        ),
        "citation": "IRC §901 (credit); §904 (limitation)",
    },
]


def _match_fact(text: str) -> tuple[str, str] | None:
    """Return the (answer, citation) for the most specific keyword match,
    not just the first one found in list order — e.g. "mega backdoor roth"
    must win over the plain "backdoor roth" entry even though the latter's
    keyword is a substring of the former's, and happens to be declared
    earlier. The citation is a real statute/IRC section reference, not a
    generated summary — every fact traces back to an actual legal source."""
    lowered = text.lower()
    best_match = None
    best_len = -1
    for fact in _FACTS:
        for kw in fact["keywords"]:
            if kw in lowered and len(kw) > best_len:
                best_match = (fact["answer"], fact["citation"])
                best_len = len(kw)
    return best_match


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
        "optimization",
        "tax-saving",
        "tax saving",
    ),
    "tax_calculate": ("tax", "calculate", "how much tax", "owe"),
    "platform_analyze": ("full analysis", "everything", "complete case", "full case", "overall"),
}

# Single, very generic words that legitimately drive *primary* intent
# selection (below) but are too promiscuous to justify pulling in a
# *second* intent for a compound question — nearly every tax-related
# message contains "tax" somewhere, so it can't be trusted as a genuine
# signal that a message is really asking about two separate things.
_WEAK_KEYWORDS = {
    "tax_calculate": {"tax"},
    "deduction_optimize": {"deduction"},
    "algorithm_optimize": {"optimize", "optimization", "tax-saving", "tax saving"},
}

_COMPOUND_CUES = (" and ", " also ", " as well", " plus ", "&")


def _classify_intent(text: str) -> tuple[str, bool]:
    """Return (intent, matched) — matched is False when nothing in the text
    hit any topic keyword, so the caller can tell "genuinely a full-case
    question" apart from "no topic here, e.g. just an income figure."
    """
    lowered = text.lower()
    scores = {
        intent: sum(1 for kw in keywords if _contains_keyword(lowered, kw))
        for intent, keywords in _INTENT_KEYWORDS.items()
    }
    best_intent = max(scores, key=scores.get)
    if scores[best_intent] == 0:
        return "platform_analyze", False
    return best_intent, True


def _classify_intents(text: str) -> list[str]:
    """Like _classify_intent, but also detects a genuine second topic in a
    compound question ("should I itemize and am I at audit risk") instead of
    only ever answering the single best-scoring one.

    A second intent only gets included when the message has an explicit
    conjunction cue *and* that intent has a "strong" (non-generic) keyword
    hit — otherwise incidental overlap (nearly everything mentions "tax")
    would turn ordinary single-topic questions into noisy compound answers.
    Capped at 2 intents so a reply never sprawls across the whole engine
    suite.
    """
    intent, matched = _classify_intent(text)
    if not matched:
        return []

    lowered = text.lower()
    if not any(cue in lowered for cue in _COMPOUND_CUES):
        return [intent]

    for other, keywords in _INTENT_KEYWORDS.items():
        if other in (intent, "platform_analyze"):
            continue
        weak = _WEAK_KEYWORDS.get(other, set())
        if any(_contains_keyword(lowered, kw) for kw in keywords if kw not in weak):
            return [intent, other]

    return [intent]


def _matched_keywords_for(intent: str, text: str) -> list[str]:
    """Which of an intent's keywords actually appear in this message —
    real routing transparency (what triggered this label), not a model
    confidence score."""
    lowered = text.lower()
    return [kw for kw in _INTENT_KEYWORDS.get(intent, ()) if _contains_keyword(lowered, kw)]


def _compute_intent(
    intent: str,
    message: str,
    amount: float,
    filing_status: str,
    state: str,
    self_employed: bool,
    business_owner: bool,
    state_explicit: bool = True,
) -> tuple[dict, str]:
    """Run one known intent's engine and build its reply. Factored out of
    chat() so a compound question ("should I itemize and am I at audit
    risk") can call this twice and combine the results, instead of the
    router only ever being able to answer one topic per message.

    state_explicit tells the state-sensitive replies (tax_calculate,
    platform_analyze) whether the state was actually said by the user at
    some point, or is a silent CA default — worth disclosing rather than
    quietly presenting a guess as if it were given information."""
    state_note = "" if state_explicit else f" (assuming {state} since no state was mentioned)"
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
            f"Alright — ${amount:,.0f} in income, filing {filing_status.replace('_', ' ')} in "
            f"{state}{state_note}: you're looking at about ${result['total_tax']:,.2f} total "
            f"tax, roughly {result['effective_total_rate']:.1%} of it overall."
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
            f"On ${amount:,.0f} of taxable income, you're "
            f"{'likely' if result['is_subject_to_amt'] else 'probably not'} on the hook for "
            f"AMT — that parallel tax system — with about ${result['amt_owed']:,.2f} owed there."
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
            f"Ballpark ${amount * 0.24:,.0f} in annual tax means each quarterly payment "
            f"should run about ${result['total_required'] / 4:,.2f}."
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
            f"Here's where you stand: overall compliance risk comes out "
            f"{result['overall_risk']}, with a compliance score of "
            f"{result['compliance_score']:.2f}. {result['summary']}"
        )
    elif intent == "document_analyze":
        result = document_analyze({"text": message, "title": "Chat-submitted text"})
        reply = (
            f"Went through it — risk score {result['risk_score']:.2f}, with "
            f"{len(result['citations'])} citation(s) and {len(result['risk_flags'])} "
            f"flag(s) worth a look."
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
            f"On ${amount:,.0f} AGI, going {result['recommended_method']} comes out ahead — "
            f"about ${result['recommended_deduction']:,.0f} in deductions."
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
            f"Your audit risk rating comes out {result['audit_risk_rating']} — about a "
            f"{result['estimated_audit_probability']:.2%} estimated probability."
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
            f"Best move here: {top}, worth about ${result['total_savings']:,.2f} in "
            "potential savings."
            if top
            else "Nothing specific jumps out as an optimization for this scenario."
        )
    else:
        # A genuine "give me everything" request (matched the platform_analyze
        # keywords, e.g. "full analysis") — this is the one case worth
        # actually running all three engines for.
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
            f"Full case: total tax comes to ${result['accounting']['total_tax']:,.2f}, "
            f"legal risk score {result['legal']['risk_score']:.2f}, and the top move is "
            f"{result['algorithms']['primary_recommendation']}."
        )
        if not state_explicit:
            reply += f" (Assuming {state} since no state was mentioned.)"
    return result, reply


def chat(payload: dict) -> dict:
    """Route a free-text message to the right engine(s) and reply in one place.

    This is plain keyword/regex matching, not a language model — it stays
    within "no paid API, GitHub Pages only." It reuses the exact same
    handlers as every other tab, just chosen from the message text instead
    of a form. A compound question naming two distinct topics gets both
    answered in one reply (see _classify_intents); otherwise it's one topic
    per message just like before.
    """
    message = payload.get("message", "")

    fact_match = _match_fact(message)
    if fact_match is not None:
        # A factual lookup ("what's the SALT cap") doesn't depend on the
        # user's own numbers and shouldn't disturb whatever topic/amount is
        # already remembered, so it's answered immediately, standalone. It
        # does clear any pending suggestion, though — otherwise a later
        # "yes" would resume a suggestion from before this topic-switch, as
        # if it were still what "yes" was replying to.
        _conversation_context["suggested_intent"] = None
        fact_answer, fact_citation = fact_match
        return {
            "intent": "fact",
            "routing_reason": "fact_lookup",
            "citation": fact_citation,
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
    extracted_state = _extract_state(message)
    state = (
        extracted_state if extracted_state is not None else (_conversation_context["state"] or "CA")
    )
    # Tracked separately from `state` itself, since once a default gets
    # remembered in _conversation_context there'd be no way to tell a real
    # "CA" the user typed apart from a silent guess — this is what makes it
    # possible to say so honestly in the reply instead of quietly assuming.
    state_explicit = extracted_state is not None or bool(_conversation_context["state_explicit"])
    self_employed = _has_any(
        message, "self employ", "self-employ", "1099", "schedule c", "freelance"
    )
    business_owner = _has_any(
        message, "business owner", "own a business", "my business", "llc", "s-corp"
    )

    # A transparent, rule-based label for *why* this message routed the way
    # it did — real routing metadata, not a fabricated confidence score.
    # Surfaced in every response so the routing decision is inspectable
    # (used by the frontend and by tests) instead of being a black box.
    suggested_intent = _conversation_context["suggested_intent"]
    if suggested_intent and _is_affirmative(message):
        # A short "yes"/"sure" reply to the question chat() just asked
        # ("Want me to also check your audit risk?") — run the suggestion
        # directly rather than trying to classify "yes" as a topic.
        intents = [suggested_intent]
        intent_matched = True
        routing_reason = "resumed_suggestion"
    else:
        intents = _classify_intents(message)
        intent_matched = bool(intents)
        if intent_matched:
            routing_reason = "keyword_match"
        elif _conversation_context["pending_intent"]:
            # This message is just an answer ("150k, self-employed") to the
            # question chat() asked last turn, not a fresh, unrelated topic —
            # resume what was actually being asked about instead of falling
            # back to the generic full-case default.
            intents = [_conversation_context["pending_intent"]]
            routing_reason = "resumed_pending_clarify"
        else:
            routing_reason = "unmatched"

    # An unmatched message still defaults to platform_analyze for the
    # purposes of the amount-needed check below, exactly like a single
    # unmatched intent always has — that's what makes "hello there" (no
    # topic, no amount) prompt for income instead of skipping straight to
    # "I'm not sure what you're asking."
    gate_intents = intents or ["platform_analyze"]

    if any(i in _NEEDS_AMOUNT for i in gate_intents) and amount is None:
        # A state or filing status mentioned in this same message ("what's
        # my tax in Texas") must survive to the next turn just like it
        # would for a matched intent — otherwise "in Texas" gets silently
        # dropped the moment income wasn't also given yet, and the eventual
        # answer defaults to CA without ever having forgotten on purpose.
        _conversation_context["filing_status"] = filing_status
        _conversation_context["state"] = state
        _conversation_context["state_explicit"] = state_explicit
        _conversation_context["pending_intent"] = gate_intents[0]
        _conversation_context["suggested_intent"] = None
        return {
            "intent": "clarify",
            "routing_reason": routing_reason,
            "extracted": {
                "amount": None,
                "filing_status": filing_status,
                "state": state,
                "self_employed": self_employed,
                "business_owner": business_owner,
            },
            "reply": (
                "I don't have an income figure yet — what's your rough income? "
                'Something like "150k" or "$85,000" works.'
            ),
            "result": {},
        }

    # Remember what this turn established, so a follow-up question can omit
    # it — even when nothing matched, as long as an amount was mentioned.
    _conversation_context["amount"] = amount
    _conversation_context["filing_status"] = filing_status
    _conversation_context["state"] = state
    _conversation_context["state_explicit"] = state_explicit
    _conversation_context["pending_intent"] = None

    if not intents:
        # Nothing in the message matched any topic keyword, and an amount
        # was mentioned (else the clarify branch above would have caught
        # it) — say so plainly instead of quietly running a full-case
        # computation the user never asked for.
        intent = "platform_analyze"
        result: dict = {}
        reply = (
            "I'm not sure what you're asking — try me on tax, deductions, AMT, "
            "quarterly estimates, a contract or document, compliance (FBAR/FATCA), "
            "filing status, audit risk, tax-saving strategies, or a specific "
            "tax-law fact."
        )
        _conversation_context["suggested_intent"] = None
        _record_session_entry(intent, amount, self_employed, business_owner, state, result)
        return {
            "intent": intent,
            "matched": intent_matched,
            "routing_reason": routing_reason,
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

    computed = [
        (
            i,
            *_compute_intent(
                i,
                message,
                amount,
                filing_status,
                state,
                self_employed,
                business_owner,
                state_explicit,
            ),
        )
        for i in intents
    ]
    for i, result, _ in computed:
        _record_session_entry(i, amount, self_employed, business_owner, state, result)

    matched_keywords = (
        {i: _matched_keywords_for(i, message) for i, _, _ in computed}
        if routing_reason == "keyword_match"
        else {}
    )

    if len(computed) == 1:
        intent, result, reply = computed[0]
        next_intent = _NEXT_SUGGESTION.get(intent)
        _conversation_context["suggested_intent"] = next_intent
        if next_intent:
            reply = f"{reply} {_SUGGESTION_TEXT[next_intent]}"
    else:
        intent = "+".join(i for i, _, _ in computed)
        result = {i: r for i, r, _ in computed}
        reply = " ".join(r for _, _, r in computed)
        # A compound answer already covered two topics — don't also tack on
        # a suggestion for a third.
        _conversation_context["suggested_intent"] = None

    return {
        "intent": intent,
        "matched": intent_matched,
        "routing_reason": routing_reason,
        "matched_keywords": matched_keywords,
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


def _record_session_entry(
    intent: str,
    amount: float | None,
    self_employed: bool,
    business_owner: bool,
    state: str | None,
    result: dict,
):
    entry = {
        "intent": intent,
        "amount": amount,
        "self_employed": self_employed,
        "business_owner": business_owner,
        "state": state,
    }
    if intent == "deduction_optimize" and isinstance(result, dict):
        entry["recommended_deduction"] = result.get("recommended_deduction")
        entry["recommended_method"] = result.get("recommended_method")
    if intent == "quarterly_estimate" and isinstance(result, dict):
        entry["remaining_to_pay"] = result.get("remaining_to_pay")
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
        # Only itemized deductions carry any audit-selection signal — the
        # standard deduction is a fixed, automatic amount everyone qualifies
        # for regardless of income, so a modest earner whose standard
        # deduction is a large fraction of their AGI isn't a risk signal at
        # all. Checking recommended_method here is the actual fix: this
        # used to fire on the standard deduction too, falsely warning
        # ordinary filers who'd never itemized anything.
        if (
            entry["intent"] == "deduction_optimize"
            and entry.get("recommended_method") == "itemized"
            and deduction
            and entry["amount"]
        ):
            ratio = deduction / entry["amount"]
            if ratio > 0.35:
                insights.append(
                    f"Itemized deductions came out to {ratio:.0%} of AGI in one calculation — "
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

    for entry in _session_history:
        remaining = entry.get("remaining_to_pay")
        if entry["intent"] == "quarterly_estimate" and remaining and remaining > 0:
            insights.append(
                f"Your quarterly estimate showed ${remaining:,.0f} still owed against the "
                "safe harbor — paying that down before the next due date avoids an "
                "underpayment penalty."
            )
            break

    states = {e["state"] for e in _session_history if e.get("state")}
    if len(states) >= 2:
        insights.append(
            f"You mentioned more than one state this session ({', '.join(sorted(states))}) — "
            "results reflect whichever was most recent; multi-state income has its own filing "
            "rules this doesn't account for."
        )

    mentioned_business_owner = any(e["business_owner"] for e in _session_history)
    checked_compliance = any(e["intent"] == "compliance_check" for e in _session_history)
    if mentioned_business_owner and not checked_compliance:
        insights.append(
            "You mentioned owning a business but haven't run a compliance check yet — "
            "worth checking 1099 filing requirements and estimated-payment adequacy."
        )

    # Cross-referencing the individual signals above into one summary level
    # — real aggregation over already-computed heuristics (how many
    # independent flags co-occur), not a new model or a fabricated score.
    if len(insights) >= 2:
        attention_level = "elevated"
    elif len(insights) == 1:
        attention_level = "mild"
    else:
        attention_level = "clear"

    return {
        "insights": insights,
        "entries_analyzed": len(_session_history),
        "attention_level": attention_level,
    }


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

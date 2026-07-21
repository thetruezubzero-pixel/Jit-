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
    "alabama": "AL",
    "alaska": "AK",
    "arizona": "AZ",
    "arkansas": "AR",
    "california": "CA",
    "colorado": "CO",
    "connecticut": "CT",
    "delaware": "DE",
    "district of columbia": "DC",
    "florida": "FL",
    "georgia": "GA",
    "hawaii": "HI",
    "idaho": "ID",
    "illinois": "IL",
    "indiana": "IN",
    "iowa": "IA",
    "kansas": "KS",
    "kentucky": "KY",
    "louisiana": "LA",
    "maine": "ME",
    "maryland": "MD",
    "massachusetts": "MA",
    "michigan": "MI",
    "minnesota": "MN",
    "mississippi": "MS",
    "missouri": "MO",
    "montana": "MT",
    "nebraska": "NE",
    "nevada": "NV",
    "new hampshire": "NH",
    "new jersey": "NJ",
    "new mexico": "NM",
    "new york": "NY",
    "north carolina": "NC",
    "north dakota": "ND",
    "ohio": "OH",
    "oklahoma": "OK",
    "oregon": "OR",
    "pennsylvania": "PA",
    "rhode island": "RI",
    "south carolina": "SC",
    "south dakota": "SD",
    "tennessee": "TN",
    "texas": "TX",
    "utah": "UT",
    "vermont": "VT",
    "west virginia": "WV",
    "virginia": "VA",
    "washington": "WA",
    "wisconsin": "WI",
    "wyoming": "WY",
}


def _extract_state(text: str) -> str:
    """Return a two-letter state code for the first/longest state name found in text.

    Uses longest-match so "west virginia" wins over the "virginia" substring,
    and the two-letter abbreviation pattern ("in TX") serves as a fallback.
    """
    lowered = text.lower()
    best_code = None
    best_len = 0
    for name, code in _STATE_NAMES.items():
        if name in lowered and len(name) > best_len:
            best_code = code
            best_len = len(name)
    if best_code:
        return best_code
    import re

    match = re.search(r"\bin ([A-Z]{2})\b", text)
    return match.group(1) if match else "CA"


def _has_any(text: str, *keywords: str) -> bool:
    lowered = text.lower()
    return any(kw in lowered for kw in keywords)


# ---------------------------------------------------------------------------
# Text normalisation for intent classification
# ---------------------------------------------------------------------------

# Contractions commonly typed without apostrophes (mobile, hurried typing).
_CONTRACTIONS = {
    "cant": "cannot",
    "wont": "will not",
    "dont": "do not",
    "doesnt": "does not",
    "didnt": "did not",
    "isnt": "is not",
    "arent": "are not",
    "wasnt": "was not",
    "werent": "were not",
    "wouldnt": "would not",
    "couldnt": "could not",
    "shouldnt": "should not",
    "havent": "have not",
    "hasnt": "has not",
    "hadnt": "had not",
    "whats": "what is",
    "hows": "how is",
    "whos": "who is",
    "thats": "that is",
    "theres": "there is",
    "im": "i am",
    "ive": "i have",
    "ill": "i will",
    "theyll": "they will",
    "youre": "you are",
    "youve": "you have",
    "youll": "you will",
}

# Common misspellings of tax terms that appear in user messages.
_SPELLING_FIXES = {
    "decution": "deduction",
    "dedution": "deduction",
    "deducton": "deduction",
    "defuction": "deduction",
    "quaterly": "quarterly",
    "quartely": "quarterly",
    "quarterley": "quarterly",
    "quaterley": "quarterly",
    "witholding": "withholding",
    "withholdng": "withholding",
    "withdrawl": "withdrawal",
    "dividents": "dividends",
    "dividens": "dividends",
    "benifits": "benefits",
    "busness": "business",
    "expences": "expenses",
    "exspenses": "expenses",
    "recieve": "receive",
    "receit": "receipt",
    "anuual": "annual",
    "anual": "annual",
    "penaly": "penalty",
    "penalthy": "penalty",
    "fedral": "federal",
    "goverment": "government",
    "complience": "compliance",
    "compliense": "compliance",
    "algrythm": "algorithm",
    "algorthm": "algorithm",
    "defered": "deferred",
    "deffered": "deferred",
    "roth ira": "roth ira",  # already correct — listed to prevent other fixes clobbering it
}

# Regex-based normalisation for hyphenated / dotted tax acronyms and
# common split representations (e.g. "am-t", "401 k", "i.r.s.").
_TERM_REGEXES = [
    (r"\bam[\s\-]+t\b", "amt"),
    (r"\b401[\s\-]+k\b", "401k"),
    (r"\b403[\s\-]+b\b", "403b"),
    (r"\b457[\s\-]+b\b", "457b"),
    (r"\bi\.r\.s\.?\b", "irs"),
    (r"\bw[\s\-]+2\b", "w2"),
    (r"\bsep[\s\-]+ira\b", "sep ira"),
    (r"\bsolo[\s\-]+401\b", "solo 401"),
    (r"\b409[\s\-]+a\b", "409a"),
    (r"\b1099[\s\-]+(nec|misc|k)\b", r"1099 \1"),
    (r"\bwrite[\s\-]+off(s?)\b", r"write off\1"),
    (r"\btax[\s\-]+break(s?)\b", r"tax break\1"),
    (r"\bhome[\s\-]+office\b", "home office"),
    (r"\bself[\s\-]+employ", "self employ"),
    (r"\bwash[\s\-]+sale\b", "wash sale"),
    (r"\b1031[\s\-]+exchange\b", "1031 exchange"),
    (r"\blike[\s\-]+kind\b", "like kind"),
    (r"\bnet[\s\-]+operating[\s\-]+loss\b", "net operating loss"),
]


def _normalize_text(text: str) -> str:
    """Normalise free-form chat text before intent classification.

    Handles contractions without apostrophes (common on mobile), hyphen/dot
    separated tax acronyms (``am-t`` → ``amt``, ``i.r.s.`` → ``irs``),
    and frequent tax-term misspellings (``quaterly`` → ``quarterly``).
    Returns lowercase text; does **not** alter numbers or proper-noun state
    codes so amount/state extraction on the original ``message`` is unaffected.
    """
    import re

    normalized = text.lower()

    # Apply term-level regex substitutions first (most specific).
    for pattern, replacement in _TERM_REGEXES:
        normalized = re.sub(pattern, replacement, normalized)

    # Fix common misspellings via whole-word substitution.
    for wrong, right in _SPELLING_FIXES.items():
        normalized = re.sub(r"\b" + re.escape(wrong) + r"\b", right, normalized)

    # Expand apostrophe-free contractions.
    for contracted, expanded in _CONTRACTIONS.items():
        normalized = re.sub(r"\b" + re.escape(contracted) + r"\b", expanded, normalized)

    # Collapse stray punctuation used as separators (e.g. "---", "...").
    normalized = re.sub(r"[.]{2,}", " ", normalized)
    normalized = re.sub(r"\s{2,}", " ", normalized).strip()

    return normalized


def _extract_age(text: str) -> int | None:
    """Pull the speaker's age from free text using common phrasings.

    Recognises "I'm 55", "I am 62", "age 45", "55 years old", "turning 60".
    Only accepts values in [_AGE_MIN, _AGE_MAX] to avoid false-positives on
    unrelated two-digit numbers (form numbers, percentages, year fragments).
    """
    import re

    # Bounds that filter out stray two-digit numbers while covering all
    # realistic tax-filer ages.
    _AGE_MIN = 18  # Minimum working/filing age for tax purposes
    _AGE_MAX = 85  # Avoids false positives from form numbers, rates, etc.

    patterns = [
        r"\bi(?:'m| am)\s+(\d{2})\b",  # "I'm 55" / "I am 55"
        r"\bage\s+(\d{2})\b",  # "age 55"
        r"\b(\d{2})\s+years?\s+old\b",  # "55 years old"
        r"\bturning\s+(\d{2})\b",  # "turning 60"
    ]
    for pat in patterns:
        m = re.search(pat, text.lower())
        if m:
            age = int(m.group(1))
            if _AGE_MIN <= age <= _AGE_MAX:
                return age
    return None


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
    "suggested_intent": None,
    "age": None,  # Extracted from free text; enables age-aware advice (e.g. catch-up limits)
    "mentioned_crypto": False,  # Set to True when any message mentions crypto/bitcoin
    # Adaptive learning — accumulated within a single browser session.
    "topics_seen": [],  # Intents that have already been computed; avoids re-suggesting them.
    "intent_sequence": [],  # Ring buffer (last 5) of intent names for pattern detection.
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
    "tax_calculate": "Want your full tax calculated too?",
    "risk_assess": "Want me to also check your audit risk?",
    "deduction_optimize": "Want me to check your deductions too?",
    "algorithm_optimize": "Want other tax-saving strategies too?",
    "compliance_check": "Want a compliance check too?",
}


def _get_adaptive_suggestion(intent: str) -> str | None:
    """Return the next suggestion intent, skipping any already seen this session.

    Walks the ``_NEXT_SUGGESTION`` chain starting from *intent*, skipping
    topics that are already in ``_conversation_context["topics_seen"]``.
    Returns ``None`` once there is nothing new left to suggest — avoids
    suggesting topics the user has already explored this session, which is the
    "learns what you have done" behaviour.
    """
    topics_seen: set[str] = set(_conversation_context.get("topics_seen") or [])
    candidate = _NEXT_SUGGESTION.get(intent)
    visited: set[str] = {intent}
    while candidate and candidate in topics_seen:
        if candidate in visited:
            # Circular chain — nothing new to offer.
            return None
        visited.add(candidate)
        candidate = _NEXT_SUGGESTION.get(candidate)
    return candidate if candidate and candidate in _SUGGESTION_TEXT else None

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
    {
        "keywords": ("mortgage interest deduction", "mortgage interest limit"),
        "answer": (
            "Mortgage interest is deductible (itemized) on up to $750,000 of "
            "acquisition debt ($375,000 if married filing separately) for "
            "loans originated after December 15, 2017. Loans from before then "
            "are grandfathered at the older $1 million cap."
        ),
    },
    {
        "keywords": ("student loan interest deduction",),
        "answer": (
            "The student loan interest deduction: up to $2,500/year, taken "
            "above the line (no itemizing needed). Phases out at MAGI "
            "$80,000-$95,000 (single) or $165,000-$195,000 (married filing "
            "jointly) in 2024; unavailable if married filing separately."
        ),
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
    },
    {
        "keywords": ("net operating loss", "nol carryforward", "nol carryback"),
        "answer": (
            "Post-2017 net operating losses carry forward indefinitely but "
            "can only offset up to 80% of taxable income in the year "
            "they're used — they can no longer be carried back (except "
            "certain farming and insurance-company losses)."
        ),
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
    },
    {
        "keywords": ("educator expense deduction",),
        "answer": (
            "K-12 educators can deduct up to $300 (2024) of unreimbursed "
            "classroom supplies above the line, no itemizing required. Two "
            "educators married filing jointly can each claim their own $300."
        ),
    },
    {
        "keywords": ("self employed health insurance", "self-employed health insurance"),
        "answer": (
            "Self-employed people can deduct 100% of health insurance "
            "premiums (for themselves, a spouse, and dependents) above the "
            "line, limited to net self-employment income, and only for "
            "months they weren't eligible for an employer-subsidized plan."
        ),
    },
    {
        "keywords": ("roth conversion", "convert to roth", "roth ira conversion"),
        "answer": (
            "A Roth IRA conversion moves money from a traditional (pre-tax) IRA to a "
            "Roth IRA. The converted amount is included in ordinary income the year "
            "you convert — there's no income limit on conversions even though direct "
            "Roth contributions have income limits. The 5-year rule means converted "
            "funds must stay in the Roth at least 5 years before being withdrawn "
            "penalty-free if you're under 59½. Converting in a low-income year "
            "minimizes the tax hit."
        ),
    },
    {
        "keywords": ("s-corp tax", "s corporation tax", "s corp election", "s-corp election"),
        "answer": (
            "An S-corp election lets owner-employees split income into a "
            "'reasonable salary' (subject to payroll/SE tax) and distributions "
            "(not subject to self-employment tax). For a sole proprietor netting "
            "$80k+/year the payroll-tax savings can reach $5k–$15k/year — but "
            "requires running payroll, filing Form 1120-S, and paying state fees. "
            "The IRS requires the salary to be 'reasonable' for the work performed; "
            "too low a salary is an audit red flag."
        ),
    },
    {
        "keywords": ("sep ira vs solo 401k", "sep-ira vs solo 401", "sep vs solo"),
        "answer": (
            "SEP-IRA (2024 limit: 25% of net SE income, max $69,000): very easy to "
            "open, no annual filing, no catch-up. Solo 401(k): same $69,000 total "
            "cap but also allows a $23,000 employee elective deferral (plus $7,500 "
            "catch-up at 50+) on top of the employer contribution, making it better "
            "for lower-income self-employed people who want to shelter more. Solo "
            "401(k) also allows Roth contributions and participant loans; more "
            "administrative overhead and requires Form 5500-EZ above $250k in assets."
        ),
    },
    {
        "keywords": ("sep ira limit", "sep-ira limit", "sep ira contribution"),
        "answer": (
            "2024 SEP-IRA contribution limit: the lesser of 25% of net "
            "self-employment income (after the SE tax deduction) or $69,000. "
            "Contributions are made entirely by the employer/self-employed owner "
            "and are immediately 100% vested. There are no catch-up contributions "
            "for a SEP-IRA."
        ),
    },
    {
        "keywords": ("real estate professional", "real estate professional status"),
        "answer": (
            "To qualify as a 'real estate professional' and deduct rental losses "
            "against ordinary income without limit: you must spend more than 750 "
            "hours/year in real property trades or businesses AND real estate must "
            "be more than half of your total personal services for the year. "
            "Without this status, rental losses are passive and can only offset "
            "passive income — except a $25,000 allowance for active participants "
            "with AGI ≤$100,000 (phasing out at $150,000)."
        ),
    },
    {
        "keywords": ("passive activity", "passive loss", "passive income rules"),
        "answer": (
            "Passive activity losses (from rental properties and businesses you don't "
            "materially participate in) can only offset passive income — not wages, "
            "salary, or portfolio income. Suspended losses accumulate and are fully "
            "released (deductible against any income) when you dispose of the "
            "passive activity in a taxable transaction. Material participation "
            "requires meeting one of seven tests, the most common being 500+ "
            "hours/year in the activity."
        ),
    },
    {
        "keywords": ("depreciation recapture", "section 1250", "unrecaptured 1250 gain"),
        "answer": (
            "When you sell depreciated real property, the portion of gain equal to "
            "prior depreciation deductions (§1250 gain) is taxed at a maximum "
            "25% rate ('unrecaptured §1250 gain') — not the standard 0%/15%/20% "
            "long-term capital gains rate. Personal property (equipment, vehicles) "
            "depreciation is recaptured at ordinary income rates under §1245."
        ),
    },
    {
        "keywords": ("qualified opportunity zone", "opportunity zone investment", "qoz fund"),
        "answer": (
            "Investing capital gains in a Qualified Opportunity Zone (QOZ) fund "
            "within 180 days defers those original gains until December 31, 2026 "
            "(or earlier sale of the QOZ investment). More importantly, any "
            "appreciation in the QOZ fund itself is completely excluded from tax "
            "if you hold the investment at least 10 years. Useful for large "
            "capital gains looking for deferral and potential elimination."
        ),
    },
    {
        "keywords": (
            "solar tax credit",
            "solar credit",
            "residential clean energy credit",
            "clean energy credit",
        ),
        "answer": (
            "The Residential Clean Energy Credit (Inflation Reduction Act): 30% of "
            "the cost of solar panels, battery storage (stand-alone after 2022), "
            "geothermal heat pumps, small wind turbines, and fuel cells installed "
            "at your home — through 2032 (steps to 26% in 2033, 22% in 2034). "
            "No dollar cap. The credit can carry forward if it exceeds your tax "
            "liability. A separate Energy Efficient Home Improvement Credit covers "
            "insulation, windows, heat pumps, etc. (up to $3,200/year)."
        ),
    },
    {
        "keywords": (
            "ev tax credit",
            "electric vehicle credit",
            "clean vehicle credit",
            "electric car credit",
        ),
        "answer": (
            "New EVs (2024): up to $7,500 federal credit — must meet battery "
            "mineral/assembly requirements. Income limits: $150,000 AGI (single), "
            "$225,000 (HOH), $300,000 (joint). The credit is nonrefundable for "
            "purchases; a 'transfer election' lets buyers apply it at point of "
            "sale like a discount. Used EVs: up to $4,000 (30% of sale price, "
            "max $25,000 vehicle price). Income limits: $75,000/$112,500/$150,000."
        ),
    },
    {
        "keywords": (
            "premium tax credit",
            "marketplace health insurance",
            "aca subsidy",
            "health insurance marketplace",
        ),
        "answer": (
            "The ACA Premium Tax Credit subsidizes marketplace health insurance. "
            "Post-American Rescue Plan (extended through 2025): available to "
            "households above 400% of the Federal Poverty Level too — no more "
            "income 'cliff.' The credit is reconciled on Form 8962; if advance "
            "payments exceeded your actual credit, you repay the difference "
            "(with a cap for lower incomes)."
        ),
    },
    {
        "keywords": ("qsbs", "qualified small business stock", "section 1202 exclusion"),
        "answer": (
            "IRC §1202 lets you exclude up to 100% of the gain on Qualified Small "
            "Business Stock (QSBS) held more than 5 years — up to the greater of "
            "$10 million or 10× your adjusted cost basis per company, per taxpayer. "
            "Requirements: original-issue stock in a domestic C-corp; aggregate "
            "gross assets ≤$50 million at issuance; active business in an eligible "
            "trade (excludes finance, law, consulting, etc.). State exclusions vary."
        ),
    },
    {
        "keywords": (
            "inherited ira",
            "stretch ira",
            "10 year rule ira",
            "inherited retirement account",
        ),
        "answer": (
            "The SECURE Act (2019) eliminated the 'stretch IRA' for most non-spouse "
            "beneficiaries who inherit after 2019: the entire inherited IRA must be "
            "distributed within 10 years. Exceptions (can still stretch): surviving "
            "spouses, minor children (until majority), disabled/chronically ill "
            "beneficiaries, and beneficiaries within 10 years of the decedent's age. "
            "IRS proposed regulations (2024) added nuance for accounts where the "
            "owner had already started RMDs."
        ),
    },
    {
        "keywords": ("required minimum distribution", "rmd rules", "when do rmds start"),
        "answer": (
            "Required Minimum Distributions (RMDs) from traditional IRAs and most "
            "employer plans begin at age 73 (SECURE Act 2.0, effective 2023; rising "
            "to 75 in 2033). Roth IRAs have no RMDs during the owner's lifetime. "
            "Missing an RMD triggers a 25% excise tax, reduced to 10% if corrected "
            "within a 2-year correction window. A Qualified Charitable Distribution "
            "(QCD) counts toward RMD requirements and is excluded from income."
        ),
    },
    {
        "keywords": (
            "iso stock option",
            "incentive stock option",
            "nqso",
            "nonqualified stock option",
        ),
        "answer": (
            "ISOs (incentive stock options): no ordinary income at exercise, but "
            "the spread (FMV minus strike) is an AMT preference item. Hold ≥1 year "
            "from exercise AND ≥2 years from grant → LTCG rates on the full gain. "
            "NQSOs (nonqualified): ordinary income at exercise equal to the spread "
            "(reported on W-2 or 1099-NEC), then LTCG or short-term on later "
            "appreciation. Company gets a deduction for NQSOs; not for ISOs."
        ),
    },
    {
        "keywords": ("crypto tax", "bitcoin tax", "cryptocurrency tax", "nft tax"),
        "answer": (
            "The IRS treats crypto as property. Every sale, trade, or spend is a "
            "taxable event: gains held ≤12 months are short-term (ordinary income "
            "rates); held >12 months qualify for LTCG rates. Mining and staking "
            "income is ordinary income at FMV when received. The wash sale rule "
            "does NOT currently apply to crypto (unlike stocks) — though proposed "
            "legislation may change this. All transactions must be reported on "
            "Form 8949; the 1040 asks a virtual-currency question regardless."
        ),
    },
    {
        "keywords": ("alimony tax", "divorce alimony", "spousal support tax", "alimony deduction"),
        "answer": (
            "For divorce/separation agreements executed after December 31, 2018: "
            "alimony payments are NOT deductible by the payer and NOT includible "
            "in the recipient's income (TCJA change). Pre-2019 agreements are "
            "grandfathered under the old rules (deductible/includible) unless "
            "the parties specifically modify the agreement to adopt the new rules."
        ),
    },
    {
        "keywords": (
            "net unrealized appreciation",
            "nua stock",
            "employer stock 401k distribution",
        ),
        "answer": (
            "Net Unrealized Appreciation (NUA): if you have highly appreciated "
            "employer stock in your 401(k) and take a qualifying lump-sum "
            "distribution, you pay ordinary income tax only on your cost basis "
            "(what the employer paid in), not the full value. The built-in gain "
            "(NUA) is taxed at LTCG rates when you eventually sell the shares — "
            "potentially much lower than the ordinary rates you'd pay on a normal "
            "401(k) distribution or rollover."
        ),
    },
    {
        "keywords": ("foreign tax credit", "form 1116", "double taxation foreign"),
        "answer": (
            "If you pay income tax to a foreign country on income also taxed by "
            "the U.S., you can claim a foreign tax credit (Form 1116) to offset "
            "U.S. tax dollar-for-dollar, subject to a limitation based on your "
            "foreign-source income ratio. Alternatively you can deduct foreign "
            "taxes as an itemized deduction — generally less valuable than the "
            "credit. The foreign tax credit and the Foreign Earned Income "
            "Exclusion (FEIE) can't apply to the same income."
        ),
    },
    {
        "keywords": ("qualified charitable distribution", "qcd ira", "ira to charity"),
        "answer": (
            "A Qualified Charitable Distribution (QCD) lets IRA owners age 70½+ "
            "donate up to $105,000 (2024, indexed) directly from their IRA to a "
            "qualified charity. The distribution is excluded from income entirely "
            "(unlike a normal withdrawal + deduction, which still inflates AGI). "
            "QCDs count dollar-for-dollar toward your RMD for the year — making "
            "them the most tax-efficient way to give for anyone with an IRA who "
            "doesn't need all of their RMD."
        ),
    },
    {
        "keywords": ("fsa", "flexible spending account", "health fsa", "dependent care fsa"),
        "answer": (
            "Health FSA (2024): contribute up to $3,200 pre-tax through payroll; "
            "use-it-or-lose-it with up to a $640 rollover option if the plan allows. "
            "Dependent Care FSA: up to $5,000 ($2,500 if married filing separately) "
            "pre-tax for qualifying childcare or adult dependent care while you "
            "work. Unlike an HSA, FSAs don't accumulate or invest long-term. A "
            "health FSA requires enrollment in a qualifying health plan (no HDHP "
            "requirement); a dependent care FSA is separate."
        ),
    },
    {
        "keywords": (
            "rental property depreciation",
            "27.5 year depreciation",
            "depreciate rental property",
        ),
        "answer": (
            "Residential rental property is depreciated over 27.5 years using "
            "straight-line MACRS; commercial real property over 39 years. Land is "
            "never depreciated. A cost segregation study can reclassify interior "
            "components, land improvements, and personal property into 5-, 7-, or "
            "15-year property eligible for much faster depreciation (and bonus "
            "depreciation). This is often the single largest tax deferral "
            "opportunity for real estate investors."
        ),
    },
    {
        "keywords": (
            "deferred compensation 409a",
            "nonqualified deferred compensation",
            "409a rules",
        ),
        "answer": (
            "Nonqualified deferred compensation (NQDC) governed by IRC §409A must "
            "be elected before the year the compensation is earned (or within 30 "
            "days for new participants). Distributions must follow six permissible "
            "triggers: separation from service, disability, death, change in control, "
            "unforeseeable emergency, or a fixed date. Violations cause immediate "
            "taxation of the entire deferred amount plus a 20% additional tax and "
            "interest — one of the harshest penalty structures in the tax code."
        ),
    },
    {
        "keywords": (
            "above the line deduction",
            "above-the-line deduction",
            "adjustments to income",
        ),
        "answer": (
            "Above-the-line deductions reduce AGI without itemizing (taken on "
            "Schedule 1). Key 2024 above-the-line deductions: traditional IRA "
            "contributions (if deductible), student loan interest ($2,500 cap), "
            "HSA contributions ($4,150/$8,300), self-employed health insurance "
            "premiums, half of self-employment tax, SEP/SIMPLE/Solo 401(k) "
            "contributions, educator expenses ($300), and alimony paid under "
            "pre-2019 agreements. Lowering AGI also expands eligibility for "
            "credits and deductions that phase out with income."
        ),
    },
]


def _match_fact(text: str) -> str | None:
    """Return the answer for the most specific keyword match, not just the
    first one found in list order — e.g. "mega backdoor roth" must win over
    the plain "backdoor roth" entry even though the latter's keyword is a
    substring of the former's, and happens to be declared earlier."""
    lowered = text.lower()
    best_answer = None
    best_len = -1
    for fact in _FACTS:
        for kw in fact["keywords"]:
            if kw in lowered and len(kw) > best_len:
                best_answer = fact["answer"]
                best_len = len(kw)
    return best_answer


_INTENT_KEYWORDS = {
    "amt_calculate": (
        "amt",
        "alternative minimum tax",
        "iso exercise",
        "incentive stock option",
        "form 6251",
    ),
    "quarterly_estimate": (
        "quarterly",
        "estimated payment",
        "estimated tax payment",
        "safe harbor",
        "underpayment",
        "quarterly estimated",
        # colloquial
        "quarterly taxes",
        "quarterly due",
        "quarterly payment",
        "pay quarterly",
        "pay by quarter",
        "estimated payments",
    ),
    "compliance_check": (
        "compliance",
        "fbar",
        "fatca",
        "foreign account",
        "1099 filing",
        "crypto wallet",
        "virtual currency report",
        # colloquial
        "am i compliant",
        "do i need to report",
        "1099 requirements",
    ),
    "document_analyze": ("contract", "clause", "document", "agreement", "indemnif"),
    "filing_status_tree": (
        "filing status",
        "should i file",
        "file as single",
        "file jointly",
        # colloquial
        "how should i file",
        "what status should i",
        "married filing",
        "head of household",
    ),
    "deduction_optimize": (
        "deduction",
        "itemize",
        "itemized",
        "standard deduction",
        "write off",
        "write-off",
        "deductible expense",
        "mortgage interest deduction",
        # colloquial / metaphor
        "tax break",
        "tax breaks",
        "deductible",
        "can i deduct",
        "is this deductible",
        "write offs",
        "writing off",
        "throwing money at taxes",
        "tax write",
    ),
    "risk_assess": (
        "audit risk",
        "audit probability",
        "get audited",
        "irs audit",
        "audit trigger",
        "red flag irs",
        "irs red flag",
        "noticed by irs",
        # colloquial / metaphor
        "audit chance",
        "chance of audit",
        "am i at risk",
        "worried about audit",
        "worried about irs",
        "irs scrutiny",
        "irs watching",
        "irs coming",
        "flag my return",
        "will i get audited",
        "audit me",
    ),
    "algorithm_optimize": (
        "save on tax",
        "tax strategy",
        "tax strategies",
        "reduce my tax",
        "lower my tax",
        "minimize my tax",
        "tax planning",
        "tax savings",
        "tax shelter",
        "optimize",
        # colloquial / metaphor — user expressing frustration or desire to reduce burden
        "pay less tax",
        "pay less in tax",
        "paying too much tax",
        "cut my tax",
        "cut taxes",
        "save money on tax",
        "lower tax burden",
        "lower my taxes",
        "lower my bill",
        "reduce tax burden",
        "bleeding in tax",
        "killing me in tax",
        "help me save",
        "how to save",
        "what can i do to lower",
        "ways to reduce",
        "tax efficient",
        "tax optimization",
    ),
    "tax_calculate": (
        "tax",
        "calculate",
        "how much tax",
        "owe",
        "income tax",
        "federal tax",
        "effective tax rate",
        "tax owed",
        # colloquial
        "tax bill",
        "how much will i pay",
        "how much am i paying",
        "taxes due",
        "what is my tax",
        "what will i owe",
        "how much do i owe",
        "what do i owe",
        "tax return this year",
    ),
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
    "algorithm_optimize": {"optimize"},
}

_COMPOUND_CUES = (" and ", " also ", " as well", " plus ", "&")


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
        if any(kw in lowered for kw in keywords if kw not in weak):
            return [intent, other]

    return [intent]


def _matched_keywords_for(intent: str, text: str) -> list[str]:
    """Which of an intent's keywords actually appear in this message —
    real routing transparency (what triggered this label), not a model
    confidence score."""
    lowered = text.lower()
    return [kw for kw in _INTENT_KEYWORDS.get(intent, ()) if kw in lowered]


def _compute_intent(
    intent: str,
    message: str,
    amount: float,
    filing_status: str,
    state: str,
    self_employed: bool,
    business_owner: bool,
    age: int | None = None,
) -> tuple[dict, str]:
    """Run one known intent's engine and build its reply. Factored out of
    chat() so a compound question ("should I itemize and am I at audit
    risk") can call this twice and combine the results, instead of the
    router only ever being able to answer one topic per message."""
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
        # Compute actual estimated federal + SE tax rather than assuming 24%.
        tax_result = tax_calculate(
            {
                "gross_income": amount,
                "filing_status": filing_status,
                "state_code": state,
                "w2_wages": 0.0 if self_employed else amount,
                "self_employment_income": amount if self_employed else 0.0,
            }
        )
        expected_annual_tax = tax_result["total_tax"]
        result = quarterly_estimate(
            {
                "expected_total_tax": expected_annual_tax,
                "prior_year_tax": expected_annual_tax,
                "prior_year_agi": amount,
                "filing_status": filing_status,
            }
        )
        reply = (
            f"Based on an estimated ${expected_annual_tax:,.0f} annual tax "
            f"({tax_result['effective_total_rate']:.1%} effective rate), "
            f"each quarterly payment should be about ${result['total_required'] / 4:,.2f}. "
            f"Safe-harbor amount: ${result['safe_harbor_amount']:,.2f}/year "
            f"(${result['safe_harbor_amount'] / 4:,.2f}/quarter)."
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
        if result.get("tax_savings"):
            reply += (
                f" That saves you roughly ${result['tax_savings']:,.0f} "
                "compared to the other method."
            )
    elif intent == "risk_assess":
        result = risk_assess(
            {
                "agi": amount,
                "has_schedule_c": self_employed,
                "schedule_c_income": amount if self_employed else 0.0,
                "has_crypto_transactions": _has_any(
                    message, "crypto", "bitcoin", "ethereum", "nft"
                ),
                "claimed_home_office": _has_any(message, "home office"),
            }
        )
        factor_count = len(result.get("risk_factors", []))
        factor_note = (
            f" {factor_count} risk factor{'s' if factor_count != 1 else ''} detected."
            if factor_count
            else ""
        )
        reply = (
            f"Your audit risk rating is {result['audit_risk_rating']} "
            f"(estimated probability {result['estimated_audit_probability']:.2%}).{factor_note}"
        )
    elif intent == "algorithm_optimize":
        effective_age = age if age is not None else 40
        result = algorithm_optimize(
            {
                "gross_income": amount,
                "current_tax": amount * 0.24,
                "marginal_rate": 0.24,
                "filing_status": filing_status,
                "age": effective_age,
                "has_401k_access": not self_employed,
                "self_employment_income": amount if self_employed else 0.0,
                "is_business_owner": business_owner,
                "expected_state_tax": amount * 0.05 if business_owner else 0.0,
            }
        )
        strategies = result.get("strategies", [])
        top_titles = [s["title"] for s in strategies[:3]] if strategies else []
        if top_titles:
            age_note = " (catch-up limits applied)" if effective_age >= 50 else ""
            reply = (
                f"Total potential savings: ${result['total_savings']:,.2f}{age_note}. "
                f"Top strategies: {', '.join(top_titles)}."
            )
        else:
            reply = "No specific optimization strategies applied for this scenario."
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
            f"Full case: total tax ${result['accounting']['total_tax']:,.2f}, "
            f"legal risk score {result['legal']['risk_score']:.2f}, "
            f"recommendation: {result['algorithms']['primary_recommendation']}."
        )
    return result, reply


def chat(payload: dict) -> dict:
    """Route a free-text message to the right engine(s) and reply in one place.

    This is keyword/regex matching augmented with text normalisation — it
    stays within "no paid API, GitHub Pages only." Text is normalised before
    intent classification so that common typos, missing apostrophes, and
    hyphenated tax acronyms (e.g. ``am-t``, ``i.r.s.``) are handled
    naturally.  A compound question naming two distinct topics gets both
    answered in one reply (see _classify_intents); otherwise it's one topic
    per message.  The session learns which topics have been covered and
    avoids suggesting ones already explored (see _get_adaptive_suggestion).
    """
    message = payload.get("message", "")
    # Normalised copy used for intent classification only; the original
    # ``message`` string is preserved for amount/state extraction (which
    # needs the original casing for uppercase state abbreviations) and for
    # document analysis (which processes the raw text directly).
    normalized = _normalize_text(message)

    fact_answer = _match_fact(normalized)
    if fact_answer is None:
        # Also check original in case fact keywords don't survive normalisation
        fact_answer = _match_fact(message)
    if fact_answer is not None:
        # A factual lookup ("what's the SALT cap") doesn't depend on the
        # user's own numbers and shouldn't disturb whatever topic/amount is
        # already remembered, so it's answered immediately, standalone.
        return {
            "intent": "fact",
            "routing_reason": "fact_lookup",
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
    extracted_age = _extract_age(message)
    age = extracted_age if extracted_age is not None else _conversation_context["age"]

    self_employed = _has_any(
        normalized, "self employ", "self-employ", "1099", "schedule c", "freelance"
    )
    business_owner = _has_any(
        normalized, "business owner", "own a business", "my business", "llc", "s-corp"
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
        intents = _classify_intents(normalized)
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
        _conversation_context["pending_intent"] = gate_intents[0]
        _conversation_context["suggested_intent"] = None
        return {
            "intent": "clarify",
            "routing_reason": routing_reason,
            "extracted": {
                "amount": None,
                "filing_status": filing_status,
                "state": state,
                "age": age,
                "self_employed": self_employed,
                "business_owner": business_owner,
            },
            "reply": (
                "I don't have an income figure for this yet — what's your approximate "
                'income (e.g. "150k" or "$85,000")?'
            ),
            "result": {},
        }

    # Remember what this turn established, so a follow-up question can omit
    # it — even when nothing matched, as long as an amount was mentioned.
    _conversation_context["amount"] = amount
    _conversation_context["filing_status"] = filing_status
    _conversation_context["state"] = state
    _conversation_context["age"] = age
    # Cumulative flag — once crypto/bitcoin is mentioned in any message it stays set
    # for the rest of the session so session_insights can check without re-scanning history.
    if _has_any(normalized, "crypto", "bitcoin", "ethereum", "nft", "virtual currency"):
        _conversation_context["mentioned_crypto"] = True
    _conversation_context["pending_intent"] = None

    if not intents:
        # Nothing in the message matched any topic keyword, and an amount
        # was mentioned (else the clarify branch above would have caught
        # it) — say so plainly instead of quietly running a full-case
        # computation the user never asked for.
        intent = "platform_analyze"
        result: dict = {}
        reply = (
            "I'm not sure what you're asking. Try a question about tax, "
            "deductions, AMT, quarterly estimates, a contract or document, "
            "compliance (FBAR/FATCA), filing status, audit risk, tax-saving "
            "strategies, or a specific tax-law fact."
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
                "age": age,
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
                i, message, amount, filing_status, state, self_employed, business_owner, age
            ),
        )
        for i in intents
    ]
    for i, result, _ in computed:
        _record_session_entry(i, amount, self_employed, business_owner, state, result)

    # Use normalized text for matched-keyword reporting so that typo-corrected
    # routing shows the canonical keyword that triggered it.
    matched_keywords = (
        {i: _matched_keywords_for(i, normalized) for i, _, _ in computed}
        if routing_reason == "keyword_match"
        else {}
    )

    if len(computed) == 1:
        intent, result, reply = computed[0]
        # Adaptive suggestion: skip topics the user has already explored.
        next_intent = _get_adaptive_suggestion(intent)
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

    # Record which intents have been run so adaptive suggestions can skip them.
    topics_seen: list = _conversation_context.get("topics_seen") or []
    intent_sequence: list = _conversation_context.get("intent_sequence") or []
    for i, _, _ in computed:
        if i not in topics_seen:
            topics_seen.append(i)
        intent_sequence.append(i)
    _conversation_context["topics_seen"] = topics_seen
    # Keep the sequence bounded to the last 10 entries.
    _conversation_context["intent_sequence"] = intent_sequence[-10:]

    return {
        "intent": intent,
        "matched": intent_matched,
        "routing_reason": routing_reason,
        "matched_keywords": matched_keywords,
        "extracted": {
            "amount": amount,
            "filing_status": filing_status,
            "state": state,
            "age": age,
            "self_employed": self_employed,
            "business_owner": business_owner,
        },
        "reply": reply,
        "result": result,
    }


def chat_reset(payload: dict) -> dict:
    """Forget everything chat() has remembered so far this session."""
    for key in list(_conversation_context):
        if isinstance(_conversation_context[key], list):
            _conversation_context[key] = []
        else:
            _conversation_context[key] = None
    _conversation_context["mentioned_crypto"] = False
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

    # Crypto mentioned without ever running a compliance check.
    # The mentioned_crypto flag is set cumulatively in _conversation_context whenever
    # any message contains crypto keywords — no need to scan history entries.
    has_crypto_in_session = bool(_conversation_context.get("mentioned_crypto"))
    if has_crypto_in_session and not any(
        e["intent"] == "compliance_check" for e in _session_history
    ):
        insights.append(
            "Crypto transactions were mentioned but you haven't run a compliance check — "
            "every crypto sale is a taxable event the IRS expects to see reported on Form 8949."
        )

    # Age ≥ 50 was captured but no retirement strategy check was done.
    saved_age = _conversation_context.get("age")
    if saved_age is not None and saved_age >= 50:
        checked_optimize = any(e["intent"] == "algorithm_optimize" for e in _session_history)
        if not checked_optimize:
            insights.append(
                f"You mentioned being {saved_age} years old — at 50+ you're eligible for "
                "catch-up contributions ($7,500 extra in a 401k, $1,000 extra in an IRA). "
                "Run a tax-saving strategies check to see what that means for your situation."
            )

    # High income (>$200k) without any NIIT awareness check (i.e. no tax calculation
    # or optimization run that would surface this).
    high_income_entries = [e for e in _session_history if e["amount"] and e["amount"] > 200_000]
    if high_income_entries and not any(
        e["intent"] in ("tax_calculate", "algorithm_optimize", "platform_analyze")
        for e in _session_history
    ):
        insights.append(
            "Your income is above $200,000 — the 3.8% Net Investment Income Tax (NIIT) "
            "can apply to interest, dividends, and capital gains at that level. "
            "Run a tax calculation to see your full picture including NIIT."
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

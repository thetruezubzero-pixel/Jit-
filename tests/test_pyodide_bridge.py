"""Tests for docs/py/bridge.py — the dispatch layer the client-side,
Pyodide-powered GitHub Pages frontend calls into. Runs the same handlers
under plain CPython so regressions are caught without a browser.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

DOCS_PY = Path(__file__).resolve().parent.parent / "docs" / "py"
if str(DOCS_PY) not in sys.path:
    sys.path.insert(0, str(DOCS_PY))

import bridge  # noqa: E402


def _run(module_name: str, payload: dict) -> dict:
    return json.loads(bridge.dispatch(module_name, json.dumps(payload)))


class TestDispatch:
    def test_unknown_module_reports_failure(self):
        response = _run("not_a_real_module", {})
        assert response["success"] is False
        assert "Unknown module" in response["error"]

    def test_tax_calculate_includes_property_backed_total_tax(self):
        response = _run(
            "tax_calculate",
            {
                "gross_income": 145000,
                "filing_status": "single",
                "w2_wages": 120000,
                "self_employment_income": 15000,
                "long_term_capital_gains": 7000,
                "state_code": "CA",
            },
        )
        assert response["success"] is True
        data = response["data"]
        # total_tax is a @property on TaxResult, not a dataclass field —
        # this is the exact bug the property-walk in to_jsonable fixes.
        assert data["total_tax"] == pytest.approx(data["total_federal_tax"] + data["state_tax"])
        assert data["total_tax"] > 0

    def test_deduction_optimize(self):
        response = _run(
            "deduction_optimize",
            {
                "agi": 120000,
                "filing_status": "single",
                "deductions": [
                    {"deduction_type": "mortgage_interest", "amount": 12000},
                    {"deduction_type": "charitable_cash", "amount": 4000},
                ],
            },
        )
        assert response["success"] is True
        assert response["data"]["recommended_method"] == "itemized"

    def test_amt_calculate(self):
        response = _run(
            "amt_calculate",
            {
                "regular_taxable_income": 300000,
                "regular_tax": 60000,
                "filing_status": "single",
                "iso_bargain_element": 50000,
            },
        )
        assert response["success"] is True
        assert "is_subject_to_amt" in response["data"]

    def test_quarterly_estimate(self):
        response = _run(
            "quarterly_estimate",
            {
                "expected_total_tax": 40000,
                "prior_year_tax": 38000,
                "prior_year_agi": 150000,
                "filing_status": "single",
            },
        )
        assert response["success"] is True
        assert len(response["data"]["quarterly_payments"]) == 4

    def test_document_analyze(self):
        response = _run(
            "document_analyze",
            {
                "text": "This agreement includes indemnification language under 26 U.S.C. 61.",
                "title": "Contract",
            },
        )
        assert response["success"] is True
        assert response["data"]["risk_score"] > 0

    def test_compliance_check_includes_property_backed_is_compliant(self):
        response = _run(
            "compliance_check",
            {
                "gross_income": 200000,
                "filing_status": "single",
                "taxes_withheld": 35000,
                "taxes_paid": 0,
                "has_foreign_accounts": True,
                "aggregate_foreign_balance": 25000,
            },
        )
        assert response["success"] is True
        # is_compliant is a @property on ComplianceResult, not a dataclass field.
        assert "is_compliant" in response["data"]

    def test_filing_status_tree(self):
        response = _run(
            "filing_status_tree", {"is_married": False, "has_qualifying_dependent": True}
        )
        assert response["success"] is True
        assert "Head of Household" in response["data"]["recommendation"]

    def test_deduction_method_tree(self):
        response = _run(
            "deduction_method_tree", {"itemized_deductions": 16000, "standard_deduction": 14600}
        )
        assert response["success"] is True
        assert "itemize" in response["data"]["recommendation"].lower()

    def test_algorithm_optimize_includes_property_backed_savings_percentage(self):
        response = _run(
            "algorithm_optimize",
            {
                "gross_income": 145000,
                "current_tax": 30000,
                "marginal_rate": 0.22,
                "has_401k_access": True,
                "self_employment_income": 15000,
            },
        )
        assert response["success"] is True
        assert "savings_percentage" in response["data"]

    def test_risk_assess(self):
        response = _run(
            "risk_assess",
            {"agi": 250000, "has_schedule_c": True, "schedule_c_income": 50000},
        )
        assert response["success"] is True
        assert response["data"]["estimated_audit_probability"] > 0

    def test_platform_analyze_runs_all_three_modules(self):
        response = _run(
            "platform_analyze",
            {
                "case_id": "demo",
                "filing_status": "single",
                "state": "CA",
                "incomes": [{"kind": "w2", "amount": 120000}],
                "deductions": [{"name": "charity", "amount": 4000}],
                "legal_documents": [{"title": "Doc", "text": "Contains indemnification."}],
            },
        )
        assert response["success"] is True
        assert set(response["data"].keys()) >= {"accounting", "legal", "algorithms"}
        assert [e["topic"] for e in response["data"]["audit_trail"]] == [
            "accounting.completed",
            "legal.completed",
            "algorithms.completed",
        ]

    def test_engine_error_is_reported_not_raised(self):
        response = _run("tax_calculate", {"filing_status": "not_a_real_status"})
        assert response["success"] is False
        assert "error" in response


class TestAmountExtraction:
    def test_plain_number(self):
        assert bridge._extract_amount("I earn 85000 dollars a year") == 85_000.0

    def test_k_suffix(self):
        assert bridge._extract_amount("what if I make 150k") == 150_000.0

    def test_m_suffix(self):
        assert bridge._extract_amount("a 1.2m exit") == 1_200_000.0

    def test_dollar_sign_and_commas(self):
        assert bridge._extract_amount("$1,234,567 in gross income") == 1_234_567.0

    def test_no_number_returns_none(self):
        assert bridge._extract_amount("just saying hello") is None

    def test_lone_comma_does_not_crash(self):
        # Regression: "separately, I am married" — a bare comma must not be
        # mistaken for a numeric match (it previously raised ValueError
        # trying to float('') after stripping the comma).
        assert bridge._extract_amount("separately, I am married with kids") is None

    def test_prefers_dollar_amount_over_form_number(self):
        # "1099" here is a tax form reference, not a dollar figure — the
        # actual amount ("200k") must win.
        assert bridge._extract_amount("1099 income of 200k") == 200_000.0

    def test_suffix_does_not_bleed_into_next_word(self):
        # Regression: the k/m suffix match used to allow arbitrary
        # whitespace before it, so "18000 mortgage interest" read the
        # leading "m" of "mortgage" as a million-suffix on 18000 — turning
        # $18,000 into $18,000,000,000. The suffix must be glued directly
        # to the digits, not separated by a space into the next word.
        assert bridge._extract_amount("itemized 18000 mortgage interest") == 18_000.0
        assert bridge._extract_amount("40000 medical expenses") == 40_000.0
        assert bridge._extract_amount("5000 miles driven for work") == 5_000.0


class TestKeywordAndStateMatchingEdgeCases:
    """Regressions found during an independent code review: plain substring
    keyword checks had no notion of word edges, so a short keyword could
    fire inside an unrelated word, and the state regex accepted any two
    capital letters after "in " as if it were a real state code."""

    @pytest.fixture(autouse=True)
    def reset_conversation(self):
        bridge.dispatch("chat_reset", "{}")
        yield
        bridge.dispatch("chat_reset", "{}")

    def test_owe_does_not_match_inside_lower(self):
        response = _run("chat", {"message": "the price is much lower than expected, 150k income"})
        assert response["data"]["matched"] is False

    def test_amt_keyword_does_not_match_inside_dreamt(self):
        response = _run("chat", {"message": "I dreamt about my finances, 150k income"})
        assert response["data"]["matched"] is False

    def test_amt_keyword_still_matches_as_a_real_word(self):
        response = _run("chat", {"message": "what is my AMT liability on 300k"})
        assert response["data"]["intent"] == "amt_calculate"

    def test_owe_keyword_still_matches_as_a_real_word(self):
        response = _run("chat", {"message": "how much do I owe on 150k"})
        assert response["data"]["intent"] == "tax_calculate"

    def test_invalid_two_letter_code_is_not_read_as_a_state(self):
        # "investing in IT stocks" used to be misread as the state "IT" --
        # not a real US state code.
        response = _run("chat", {"message": "what's my tax on 150k investing in IT stocks"})
        assert response["data"]["extracted"]["state"] == "CA"
        assert "assuming CA" in response["data"]["reply"]

    def test_valid_two_letter_code_is_still_read_as_a_state(self):
        response = _run("chat", {"message": "what's my tax on 150k in NY"})
        assert response["data"]["extracted"]["state"] == "NY"

    def test_fact_lookup_clears_a_stale_pending_suggestion(self):
        # Regression: chat()'s follow-up suggestion ("want your audit risk
        # checked too?") used to survive a fact lookup in between, so a
        # later "yes" -- unrelated to the original suggestion -- would
        # incorrectly resume it.
        first = _run("chat", {"message": "what's my tax on 150k"})
        assert "audit risk" in first["data"]["reply"].lower()

        _run("chat", {"message": "what's the salt cap"})

        third = _run("chat", {"message": "yes"})
        assert third["data"]["intent"] != "risk_assess"


class TestFabricatedInputDisclosure:
    """Several calculators (amt_calculate, quarterly_estimate,
    compliance_check, deduction_optimize, algorithm_optimize) only ever
    get one real figure from chat() -- the stated income -- and invent
    placeholder numbers (a flat 22%/24% tax rate, 15% withholding, 8%
    mortgage interest, 3% charitable giving) for everything else a real
    calculation needs. Presenting the result as the user's real answer
    with no indication those inputs were invented would be actively
    misleading, so each of these replies must say so honestly."""

    @pytest.fixture(autouse=True)
    def reset_conversation(self):
        bridge.dispatch("chat_reset", "{}")
        yield
        bridge.dispatch("chat_reset", "{}")

    def test_amt_reply_discloses_the_placeholder_tax_rate(self):
        response = _run("chat", {"message": "am I subject to AMT on 300k income"})
        assert "placeholder" in response["data"]["reply"].lower()

    def test_quarterly_reply_discloses_the_placeholder_rate(self):
        response = _run("chat", {"message": "what's my quarterly estimate on 150k"})
        assert "placeholder" in response["data"]["reply"].lower()

    def test_compliance_reply_discloses_the_placeholder_withholding(self):
        response = _run("chat", {"message": "check my compliance on 200k income"})
        assert "placeholder" in response["data"]["reply"].lower()

    def test_deduction_reply_discloses_the_placeholder_itemized_amounts(self):
        response = _run("chat", {"message": "what deductions should I take on 90k"})
        assert "placeholder" in response["data"]["reply"].lower()

    def test_optimizer_reply_discloses_the_placeholder_tax_rate(self):
        response = _run(
            "chat", {"message": "what optimization strategies can save me money on 220k income"}
        )
        assert "placeholder" in response["data"]["reply"].lower()


class TestChat:
    @pytest.fixture(autouse=True)
    def reset_conversation(self):
        # bridge stays imported for the whole test session, so its
        # module-level _conversation_context would otherwise leak between
        # tests — reset it before and after each one.
        bridge.dispatch("chat_reset", "{}")
        yield
        bridge.dispatch("chat_reset", "{}")

    def test_tax_question_routes_to_tax_calculate(self):
        response = _run("chat", {"message": "What is my tax if I make 150k filing single in CA"})
        assert response["success"] is True
        data = response["data"]
        assert data["intent"] == "tax_calculate"
        assert data["extracted"]["amount"] == 150_000.0
        assert data["extracted"]["state"] == "CA"
        assert "total tax" in data["reply"]

    def test_audit_risk_question_routes_correctly_with_correct_amount(self):
        response = _run(
            "chat", {"message": "I am self employed with 1099 income of 200k, am I at audit risk?"}
        )
        data = response["data"]
        assert data["intent"] == "risk_assess"
        assert data["extracted"]["amount"] == 200_000.0
        assert data["extracted"]["self_employed"] is True

    def test_document_question_routes_to_document_analyze(self):
        message = "Is this contract risky: includes indemnification and a class action waiver"
        response = _run("chat", {"message": message})
        assert response["data"]["intent"] == "document_analyze"

    def test_no_keyword_or_number_asks_for_income_instead_of_guessing(self):
        # No topic keyword, no greeting, and no income mentioned (or
        # remembered, thanks to the reset_conversation fixture) — chat()
        # should ask rather than silently defaulting to a made-up income
        # figure.
        response = _run("chat", {"message": "what should I do about this situation"})
        data = response["data"]
        assert data["intent"] == "clarify"
        assert data["extracted"]["amount"] is None

    def test_message_with_lone_comma_does_not_crash(self):
        # Regression test for the exact failing message found during manual testing.
        response = _run(
            "chat", {"message": "Should I file jointly or separately, I am married with kids"}
        )
        assert response["success"] is True
        assert response["data"]["intent"] == "filing_status_tree"

    def test_optimization_wording_routes_to_optimizer(self):
        # Regression: "optimize" was a recognized keyword but "optimization"
        # (the more natural noun form, and literally this feature's label
        # in the UI) was not, so a very ordinary phrasing of the same
        # request fell through to the "not sure what you're asking" reply.
        response = _run(
            "chat",
            {"message": "what optimization strategies can save me money on 220k income"},
        )
        assert response["data"]["intent"] == "algorithm_optimize"

    def test_business_owner_routes_to_optimizer_with_state_tax(self):
        response = _run(
            "chat", {"message": "I own a business making 300k, how can I save on taxes?"}
        )
        data = response["data"]
        assert data["intent"] == "algorithm_optimize"
        assert data["extracted"]["business_owner"] is True
        assert data["result"]["total_savings"] >= 0

    def test_unknown_intent_never_raises(self):
        # Broad smoke test: no matter what free text comes in, dispatch always
        # returns success (routing to platform_analyze/clarify as the safe
        # default) rather than propagating an exception to the caller.
        for message in ["", "asdkjfh aslkdjf", "12345", "!!!???", "married married married"]:
            response = _run("chat", {"message": message})
            assert response["success"] is True, f"message {message!r} raised: {response}"

    def test_genuinely_unmatched_question_says_so_instead_of_guessing(self):
        # Regression: this used to silently run a full multi-engine
        # platform_analyze computation and present it as if it answered an
        # off-topic question — now it should say plainly that nothing matched,
        # without computing (or claiming) anything.
        response = _run("chat", {"message": "150k, tell me something interesting"})
        data = response["data"]
        assert data["intent"] == "platform_analyze"
        assert data["matched"] is False
        assert data["result"] == {}
        assert "not sure what you're asking" in data["reply"].lower()

    def test_explicit_full_case_request_still_runs_all_engines(self):
        response = _run("chat", {"message": "give me the full analysis on 150k"})
        data = response["data"]
        assert data["intent"] == "platform_analyze"
        assert data["matched"] is True
        assert "total_tax" in data["result"]["accounting"]
        assert "Full case:" in data["reply"]


class TestSmallTalk:
    # Regression coverage: a bare greeting/thanks/goodbye used to be forced
    # through the "I need an income figure" clarify prompt (or, once an
    # amount was already remembered from earlier in the conversation, the
    # "I'm not sure what you're asking" fallback) instead of getting a
    # normal conversational reply.
    @pytest.fixture(autouse=True)
    def reset_conversation(self):
        bridge.dispatch("chat_reset", "{}")
        yield
        bridge.dispatch("chat_reset", "{}")

    def test_greeting_gets_a_friendly_reply_not_a_clarify_prompt(self):
        response = _run("chat", {"message": "hi"})
        data = response["data"]
        assert data["intent"] == "small_talk"
        assert "income figure" not in data["reply"]

    def test_how_are_you_gets_a_friendly_reply(self):
        response = _run("chat", {"message": "hey, how are you?"})
        data = response["data"]
        assert data["intent"] == "small_talk"

    def test_thanks_gets_acknowledged(self):
        response = _run("chat", {"message": "thanks!"})
        data = response["data"]
        assert data["intent"] == "small_talk"
        assert "anytime" in data["reply"].lower()

    def test_farewell_gets_acknowledged(self):
        response = _run("chat", {"message": "ok bye"})
        data = response["data"]
        assert data["intent"] == "small_talk"

    def test_greeting_word_does_not_false_positive_inside_a_real_word(self):
        # "hi" is a substring of "history" -- must not fire as a greeting
        # via prefix matching the way _contains_keyword would for tax terms.
        response = _run("chat", {"message": "what is the history of the income tax"})
        data = response["data"]
        assert data["intent"] != "small_talk"

    def test_greeting_combined_with_a_real_question_is_not_hijacked(self):
        # A greeting that ALSO asks a real, keyword-matched question should
        # be answered as that question, not swallowed by small talk.
        response = _run("chat", {"message": "hi, what's the SALT cap"})
        data = response["data"]
        assert data["intent"] == "fact"

    def test_small_talk_does_not_set_a_pending_intent(self):
        # A greeting shouldn't leave the conversation thinking it's waiting
        # for an answer to a question it never actually asked.
        _run("chat", {"message": "hi"})
        response = _run("chat", {"message": "how does this work"})
        data = response["data"]
        assert data["routing_reason"] != "resumed_pending_clarify"


class TestCompoundIntents:
    """A message naming two distinct topics with an explicit conjunction
    cue ("and", "also", "plus") gets both answered in one reply, instead of
    the router only ever picking a single best-scoring intent."""

    @pytest.fixture(autouse=True)
    def reset_conversation(self):
        bridge.dispatch("chat_reset", "{}")
        yield
        bridge.dispatch("chat_reset", "{}")

    def test_two_distinct_topics_both_get_answered(self):
        response = _run(
            "chat", {"message": "should I itemize my deductions and am I at audit risk on 150k"}
        )
        data = response["data"]
        assert data["intent"] == "deduction_optimize+risk_assess"
        assert data["matched"] is True
        assert set(data["result"].keys()) == {"deduction_optimize", "risk_assess"}
        assert "recommended_method" in data["result"]["deduction_optimize"]
        assert "audit_risk_rating" in data["result"]["risk_assess"]
        assert "deduction" in data["reply"].lower() or "AGI" in data["reply"]
        assert "audit risk" in data["reply"].lower()

    def test_incidental_generic_overlap_does_not_trigger_a_compound_answer(self):
        # "how can I save on taxes" scores algorithm_optimize AND, via the
        # bare word "tax", also tax_calculate — but there's no conjunction
        # cue, so this must stay a single-intent answer.
        response = _run(
            "chat", {"message": "I own a business making 300k, how can I save on taxes?"}
        )
        assert response["data"]["intent"] == "algorithm_optimize"

    def test_generic_tax_overlap_with_a_conjunction_still_does_not_compound(self):
        # Even with a conjunction cue present, the generic "tax" keyword
        # alone shouldn't be enough to pull in tax_calculate as a bogus
        # second topic when the message is really just about one thing.
        response = _run(
            "chat", {"message": "how can I save on taxes and reduce my tax bill on 150k"}
        )
        assert response["data"]["intent"] == "algorithm_optimize"

    def test_compound_needs_amount_just_like_a_single_intent(self):
        response = _run("chat", {"message": "should I itemize and am I at audit risk"})
        assert response["data"]["intent"] == "clarify"

    def test_compound_records_both_intents_in_session_history(self):
        _run("chat", {"message": "should I itemize and am I at audit risk on 150k"})
        response = _run("session_insights", {})
        assert response["data"]["entries_analyzed"] == 2


class TestConversationalSuggestions:
    """After answering one topic, chat() offers a natural next step, and a
    short affirmative reply ("yes", "sure") runs it automatically using the
    same remembered income/filing-status/state — real conversation-to-
    automation chaining, not just Q&A."""

    @pytest.fixture(autouse=True)
    def reset_conversation(self):
        bridge.dispatch("chat_reset", "{}")
        yield
        bridge.dispatch("chat_reset", "{}")

    def test_reply_offers_a_next_step_suggestion(self):
        response = _run("chat", {"message": "what's my tax on 150k"})
        assert "audit risk" in response["data"]["reply"].lower()

    def test_affirmative_reply_runs_the_suggested_intent(self):
        _run("chat", {"message": "what's my tax on 150k"})
        response = _run("chat", {"message": "yes"})
        data = response["data"]
        assert data["intent"] == "risk_assess"
        assert data["extracted"]["amount"] == 150_000.0

    def test_various_affirmative_phrasings_all_work(self):
        for phrase in ["yeah", "sure", "ok", "please do", "go ahead", "sounds good"]:
            bridge.dispatch("chat_reset", "{}")
            _run("chat", {"message": "what's my tax on 150k"})
            response = _run("chat", {"message": phrase})
            assert response["data"]["intent"] == "risk_assess", f"{phrase!r} did not chain"

    def test_suggestions_chain_across_multiple_turns(self):
        _run("chat", {"message": "what's my tax on 150k"})  # suggests risk_assess
        second = _run("chat", {"message": "yes"})  # runs risk_assess, suggests deduction_optimize
        assert second["data"]["intent"] == "risk_assess"
        third = _run("chat", {"message": "yes"})  # runs deduction_optimize
        assert third["data"]["intent"] == "deduction_optimize"

    def test_a_new_real_topic_supersedes_a_pending_suggestion(self):
        _run("chat", {"message": "what's my tax on 150k"})  # suggests risk_assess
        # A genuine new question, not an affirmative — should win outright,
        # not get swallowed by the pending suggestion.
        response = _run("chat", {"message": "what's the SALT cap?"})
        assert response["data"]["intent"] == "fact"

    def test_a_flat_no_does_not_trigger_the_suggestion(self):
        _run("chat", {"message": "what's my tax on 150k"})  # suggests risk_assess
        response = _run("chat", {"message": "no"})
        assert response["data"]["intent"] != "risk_assess"

    def test_declining_clears_the_suggestion_so_a_later_yes_does_nothing_odd(self):
        _run("chat", {"message": "what's my tax on 150k"})
        _run("chat", {"message": "no"})
        response = _run("chat", {"message": "yes"})
        # With no pending suggestion left, a bare "yes" has no topic and no
        # pending_intent either — falls through to the honest fallback.
        assert response["data"]["intent"] == "platform_analyze"
        assert response["data"]["matched"] is False

    def test_compound_answers_do_not_add_a_suggestion(self):
        _run("chat", {"message": "should I itemize my deductions and am I at audit risk on 150k"})
        response = _run("chat", {"message": "yes"})
        assert response["data"]["intent"] == "platform_analyze"
        assert response["data"]["matched"] is False

    def test_reset_clears_the_pending_suggestion(self):
        _run("chat", {"message": "what's my tax on 150k"})
        bridge.dispatch("chat_reset", "{}")
        _run("chat", {"message": "I make 150k"})
        response = _run("chat", {"message": "yes"})
        assert response["data"]["intent"] != "risk_assess"


class TestRoutingTransparency:
    """chat() labels *why* it routed a message the way it did
    (routing_reason) and, for a genuine keyword match, exactly which
    keyword(s) triggered it (matched_keywords) — real, inspectable routing
    metadata, not a fabricated confidence score."""

    @pytest.fixture(autouse=True)
    def reset_conversation(self):
        bridge.dispatch("chat_reset", "{}")
        yield
        bridge.dispatch("chat_reset", "{}")

    def test_keyword_match_reports_the_matched_keyword(self):
        response = _run("chat", {"message": "what's my tax on 150k"})
        data = response["data"]
        assert data["routing_reason"] == "keyword_match"
        assert "tax" in data["matched_keywords"]["tax_calculate"]

    def test_compound_reports_matched_keywords_for_both_intents(self):
        response = _run(
            "chat", {"message": "should I itemize my deductions and am I at audit risk on 150k"}
        )
        data = response["data"]
        assert data["routing_reason"] == "keyword_match"
        assert set(data["matched_keywords"].keys()) == {"deduction_optimize", "risk_assess"}

    def test_resumed_suggestion_is_labeled_distinctly(self):
        _run("chat", {"message": "what's my tax on 150k"})
        response = _run("chat", {"message": "yes"})
        assert response["data"]["routing_reason"] == "resumed_suggestion"
        assert response["data"]["matched_keywords"] == {}

    def test_resumed_pending_clarify_is_labeled_distinctly(self):
        _run("chat", {"message": "am I at audit risk?"})  # clarify, no amount yet
        response = _run("chat", {"message": "150k"})
        assert response["data"]["routing_reason"] == "resumed_pending_clarify"

    def test_unmatched_fallback_is_labeled_distinctly(self):
        response = _run("chat", {"message": "150k, tell me something interesting"})
        assert response["data"]["routing_reason"] == "unmatched"

    def test_fact_lookup_is_labeled_distinctly(self):
        response = _run("chat", {"message": "what's the SALT cap?"})
        assert response["data"]["routing_reason"] == "fact_lookup"


class TestChatMemoryAndClarify:
    @pytest.fixture(autouse=True)
    def reset_conversation(self):
        bridge.dispatch("chat_reset", "{}")
        yield
        bridge.dispatch("chat_reset", "{}")

    def test_no_amount_asks_instead_of_guessing(self):
        """Regression: chat() used to silently default to $120k when no
        income was mentioned or remembered. It should ask instead."""
        response = _run("chat", {"message": "am I at audit risk?"})
        data = response["data"]
        assert data["intent"] == "clarify"
        assert data["extracted"]["amount"] is None
        assert "income" in data["reply"].lower()
        assert data["result"] == {}

    def test_follow_up_resumes_the_pending_topic(self):
        """After being asked to clarify, a reply that's just an income
        figure (no new topic keywords) should resume what was actually
        being asked about, not fall back to the generic full-case default."""
        first = _run("chat", {"message": "am I at audit risk?"})
        assert first["data"]["intent"] == "clarify"

        second = _run("chat", {"message": "150k, self employed"})
        assert second["data"]["intent"] == "risk_assess"
        assert second["data"]["extracted"]["amount"] == 150_000.0
        assert second["data"]["extracted"]["self_employed"] is True

    def test_amount_is_remembered_across_messages(self):
        first = _run("chat", {"message": "I make 150k, self employed"})
        assert first["data"]["extracted"]["amount"] == 150_000.0

        # No amount mentioned this time — should reuse the remembered one.
        second = _run("chat", {"message": "what deductions should I take?"})
        assert second["data"]["intent"] == "deduction_optimize"
        assert second["data"]["extracted"]["amount"] == 150_000.0

    def test_new_amount_overrides_remembered_one(self):
        _run("chat", {"message": "I make 150k"})
        second = _run("chat", {"message": "what if I made 300k instead"})
        assert second["data"]["extracted"]["amount"] == 300_000.0

    def test_filing_status_and_state_are_also_remembered(self):
        _run("chat", {"message": "I make 150k, married, in NY"})
        second = _run("chat", {"message": "what's my tax"})
        assert second["data"]["extracted"]["filing_status"] == "married_filing_jointly"
        assert second["data"]["extracted"]["state"] == "NY"

    def test_state_mentioned_before_income_is_not_lost_at_the_clarify_gate(self):
        # Regression: "what's my tax in Texas" has no amount, so it hits the
        # clarify branch and asks for income -- but "Texas" was still real
        # information the user gave, and used to be silently dropped there
        # since only pending_intent/suggested_intent were persisted before
        # the clarify return, not state. The next message ("150k") should
        # still land on TX, not the CA default.
        clarify = _run("chat", {"message": "what's my tax in Texas"})
        assert clarify["data"]["intent"] == "clarify"
        second = _run("chat", {"message": "150k"})
        assert second["data"]["extracted"]["state"] == "TX"
        assert " TX" in second["data"]["reply"]

    def test_unstated_state_is_disclosed_not_silently_assumed(self):
        # Regression: chat() used to default to CA with no indication this
        # was a guess rather than something the user said.
        response = _run("chat", {"message": "what's my tax on 150k"})
        assert "assuming CA" in response["data"]["reply"]

    def test_explicitly_stated_state_is_not_flagged_as_an_assumption(self):
        response = _run("chat", {"message": "what's my tax on 150k in NY"})
        assert "assuming" not in response["data"]["reply"].lower()

    def test_reset_clears_remembered_context(self):
        _run("chat", {"message": "I make 150k"})
        response = json.loads(bridge.dispatch("chat_reset", "{}"))
        assert response == {"success": True, "data": {"reset": True}}

        after_reset = _run("chat", {"message": "am I at audit risk?"})
        assert after_reset["data"]["intent"] == "clarify"

    def test_document_question_needs_no_amount(self):
        """Intents that don't depend on a dollar figure should never be
        blocked waiting for one."""
        response = _run("chat", {"message": "is this contract risky: includes indemnification"})
        assert response["data"]["intent"] == "document_analyze"

    def test_matched_is_true_for_a_recognized_topic(self):
        response = _run("chat", {"message": "what's my tax on 150k filing single in CA"})
        assert response["data"]["matched"] is True

    def test_matched_is_false_for_a_genuinely_unmatched_question(self):
        response = _run("chat", {"message": "150k, tell me something interesting"})
        assert response["data"]["intent"] == "platform_analyze"
        assert response["data"]["matched"] is False


class TestFactLookup:
    @pytest.fixture(autouse=True)
    def reset_conversation(self):
        bridge.dispatch("chat_reset", "{}")
        yield
        bridge.dispatch("chat_reset", "{}")

    @pytest.mark.parametrize(
        "message,expected_snippet",
        [
            ("what's the standard deduction?", "$14,600"),
            ("what is the salt cap", "$10,000"),
            ("how does a backdoor roth work", "nondeductible traditional IRA"),
            ("explain ptet to me", "entity level"),
            ("what's the 401k limit this year", "$23,000"),
            ("ira contribution limit", "$7,000"),
            ("hsa contribution limit for family", "$8,300"),
            ("long term capital gains rate", "0%"),
            ("amt exemption amount", "$85,700"),
            ("fbar threshold", "$10,000"),
            ("what is qbi", "20%"),
            ("what's the child tax credit", "$2,000"),
            ("earned income tax credit amounts", "$7,830"),
            ("child and dependent care credit", "$3,000"),
            ("american opportunity credit amount", "$2,500"),
            ("lifetime learning credit amount", "$2,000"),
            ("estate tax exemption this year", "$13.61 million"),
            ("annual gift exclusion amount", "$18,000"),
            ("529 plan contribution rules", "tax-free"),
            ("self employment tax rate", "15.3%"),
            ("capital loss deduction limit", "$3,000"),
            ("charitable contribution limit", "60%"),
            ("kiddie tax threshold", "$2,600"),
            ("social security wage base this year", "$168,600"),
            ("net investment income tax rate", "3.8%"),
            ("additional medicare tax rate", "0.9%"),
            ("mortgage interest deduction limit", "$750,000"),
            ("student loan interest deduction amount", "$2,500"),
            ("home sale exclusion amount", "$250,000"),
            ("what's the wash sale rule", "30 days"),
            ("how does a 1031 exchange work", "45 days"),
            ("foreign earned income exclusion amount", "$126,500"),
            ("section 179 limit", "$1,160,000"),
            ("net operating loss carryforward rules", "80%"),
            ("what is a mega backdoor roth", "$69,000"),
            ("educator expense deduction amount", "$300"),
            ("self employed health insurance deduction", "100%"),
            ("what's the standard mileage rate", "67 cents"),
            ("can I take a home office deduction", "$5 per square foot"),
            ("what's the roth ira income limit", "$146,000"),
            ("what's the traditional ira deduction limit", "$77,000"),
            ("what age do I need to take my rmd", "age 73"),
            ("what's the fsa contribution limit", "$3,200"),
            ("what's the medical expense deduction threshold", "7.5%"),
            ("is cancellation of debt taxable", "1099-C"),
            ("is debt discharged in bankruptcy taxable", "Title 11"),
            ("are life insurance proceeds taxable", "not taxable"),
            ("is short term disability taxable", "who paid the premiums"),
            ("what is the foreign tax credit", "double taxation"),
        ],
    )
    def test_fact_answers_directly_without_a_calculation(self, message, expected_snippet):
        response = _run("chat", {"message": message})
        data = response["data"]
        assert data["intent"] == "fact"
        assert data["result"] == {}
        assert expected_snippet in data["reply"]

    def test_every_fact_has_a_real_citation(self):
        # Every hardcoded fact traces back to an actual statute/IRC section
        # (or, where the fact isn't an IRC provision at all — FBAR is Bank
        # Secrecy Act, not the tax code — the correct non-IRC citation)
        # rather than being an unsourced assertion.
        for fact in bridge._FACTS:
            assert fact.get("citation"), f"missing citation: {fact['keywords']}"
            assert "§" in fact["citation"] or "U.S.C." in fact["citation"]

    def test_fact_response_includes_its_citation(self):
        response = _run("chat", {"message": "what's the salt cap"})
        data = response["data"]
        assert data["intent"] == "fact"
        assert data["citation"] == "IRC §164(b)(6)"

    def test_fact_lookup_does_not_disturb_remembered_context(self):
        _run("chat", {"message": "I make 150k, married, in NY"})
        fact_response = _run("chat", {"message": "what's the salt cap"})
        assert fact_response["data"]["intent"] == "fact"

        # The remembered amount/filing status/state should be untouched.
        follow_up = _run("chat", {"message": "what's my tax"})
        assert follow_up["data"]["extracted"]["amount"] == 150_000.0
        assert follow_up["data"]["extracted"]["filing_status"] == "married_filing_jointly"
        assert follow_up["data"]["extracted"]["state"] == "NY"

    def test_itemize_vs_standard_comparison_runs_the_calculator_not_the_fact(self):
        # Regression: "standard deduction" is both a fact keyword and one
        # of deduction_optimize's routing keywords, so a real comparison
        # question with a real income figure used to always get the
        # static fact and never actually run the optimizer.
        response = _run(
            "chat", {"message": "should I itemize or take the standard deduction on 90k income"}
        )
        assert response["data"]["intent"] == "deduction_optimize"
        assert "recommended_method" in response["data"]["result"]

    def test_plain_standard_deduction_question_still_answers_as_a_fact(self):
        # The fix above must not break the ordinary case -- no "itemize"
        # comparison cue, no amount, just the raw fact.
        response = _run("chat", {"message": "what's the standard deduction"})
        assert response["data"]["intent"] == "fact"

    def test_fact_lookup_needs_no_amount_even_with_no_context(self):
        response = _run("chat", {"message": "what's the standard deduction?"})
        assert response["data"]["intent"] == "fact"

    def test_more_specific_keyword_wins_over_a_substring_match(self):
        # Regression: "mega backdoor roth" contains "backdoor roth" as a
        # literal substring, and the plain backdoor-Roth fact is declared
        # earlier in the list — _match_fact must prefer the longer, more
        # specific keyword rather than whichever fact comes first.
        response = _run("chat", {"message": "what is a mega backdoor roth"})
        assert "$69,000" in response["data"]["reply"]


class TestSessionInsights:
    """session_insights() is plain statistics over this session's own chat
    history (income variance, deduction ratio, self-employment without a
    deduction/risk check) — no model involved, just arithmetic over data the
    user already gave the chat."""

    @pytest.fixture(autouse=True)
    def reset_conversation(self):
        bridge.dispatch("chat_reset", "{}")
        yield
        bridge.dispatch("chat_reset", "{}")

    def test_no_history_means_no_insights(self):
        response = _run("session_insights", {})
        assert response["data"]["insights"] == []
        assert response["data"]["entries_analyzed"] == 0

    def test_fact_and_clarify_turns_are_not_recorded(self):
        _run("chat", {"message": "what's the standard deduction?"})  # fact
        _run("chat", {"message": "am I at audit risk?"})  # clarify, no amount yet
        response = _run("session_insights", {})
        assert response["data"]["entries_analyzed"] == 0

    def test_income_variance_is_flagged(self):
        _run("chat", {"message": "what's my tax on 100k"})
        _run("chat", {"message": "what if I made 500k instead"})
        response = _run("session_insights", {})
        insights = " ".join(response["data"]["insights"])
        assert "varied a lot" in insights
        assert "$100,000" in insights and "$500,000" in insights

    def test_standard_deduction_never_triggers_the_audit_ratio_warning(self):
        # Regression: this insight used to compare recommended_deduction to
        # AGI regardless of which method was recommended — so a low-income
        # filer whose flat, automatic standard deduction ($14,600 in 2024)
        # is a large fraction of a small AGI got a false "this looks
        # audit-risky" warning for taking the deduction everyone qualifies
        # for. The standard deduction carries no audit-selection signal at
        # all; only a real itemized total would.
        _run("chat", {"message": "what deductions should I take on 30k income"})
        response = _run("session_insights", {})
        insights = " ".join(response["data"]["insights"])
        assert "audit-selection models" not in insights

    def test_itemized_deduction_within_normal_range_does_not_falsely_warn(self):
        # chat()'s deduction_optimize path itemizes a fixed 11% of AGI
        # (mortgage interest + charitable giving placeholders) — well under
        # the 35% threshold — so even when itemizing is recommended, this
        # shouldn't fire from chat() alone without a real, larger itemized
        # total.
        _run("chat", {"message": "what deductions should I take on 200k income"})
        response = _run("session_insights", {})
        insights = " ".join(response["data"]["insights"])
        assert "audit-selection models" not in insights

    def test_self_employed_without_deduction_or_risk_check_is_flagged(self):
        _run("chat", {"message": "what's my tax if I'm self employed making 150k"})
        response = _run("session_insights", {})
        insights = " ".join(response["data"]["insights"])
        assert "self-employment" in insights.lower()

    def test_self_employed_flag_clears_once_deductions_are_checked(self):
        _run("chat", {"message": "what's my tax if I'm self employed making 150k"})
        _run("chat", {"message": "what deductions should I take?"})
        response = _run("session_insights", {})
        insights = " ".join(response["data"]["insights"])
        assert "haven't asked about deductions" not in insights

    def test_reset_clears_session_history(self):
        _run("chat", {"message": "what's my tax on 150k"})
        bridge.dispatch("chat_reset", "{}")
        response = _run("session_insights", {})
        assert response["data"]["entries_analyzed"] == 0

    def test_quarterly_underpayment_is_flagged(self):
        # chat()'s quarterly_estimate path doesn't assume any withholding,
        # so remaining_to_pay is always positive here.
        _run("chat", {"message": "what's my quarterly estimate on 200k"})
        response = _run("session_insights", {})
        insights = " ".join(response["data"]["insights"])
        assert "still owed against the safe harbor" in insights

    def test_state_mismatch_is_flagged(self):
        _run("chat", {"message": "what's my tax on 150k in NY"})
        _run("chat", {"message": "what if I lived in CA instead"})
        response = _run("session_insights", {})
        insights = " ".join(response["data"]["insights"])
        assert "more than one state" in insights
        assert "CA" in insights and "NY" in insights

    def test_business_owner_without_compliance_check_is_flagged(self):
        _run("chat", {"message": "I own a business making 300k, how can I save on taxes?"})
        response = _run("session_insights", {})
        insights = " ".join(response["data"]["insights"])
        assert "haven't run a compliance check" in insights

    def test_business_owner_flag_clears_once_compliance_is_checked(self):
        _run("chat", {"message": "I own a business making 300k, how can I save on taxes?"})
        _run("chat", {"message": "compliance check please"})
        response = _run("session_insights", {})
        insights = " ".join(response["data"]["insights"])
        assert "haven't run a compliance check" not in insights

    def test_no_insights_means_clear_attention_level(self):
        response = _run("session_insights", {})
        assert response["data"]["attention_level"] == "clear"

    def test_one_insight_means_mild_attention_level(self):
        _run("chat", {"message": "I own a business making 300k, how can I save on taxes?"})
        response = _run("session_insights", {})
        assert response["data"]["attention_level"] == "mild"

    def test_two_or_more_insights_means_elevated_attention_level(self):
        # Cross-references two independent signals firing at once
        # (self-employed with no risk/deduction check, business owner with
        # no compliance check) into one summary level.
        message = "I am self employed and own a business making 300k, how can I save on taxes?"
        _run("chat", {"message": message})
        response = _run("session_insights", {})
        data = response["data"]
        assert len(data["insights"]) >= 2
        assert data["attention_level"] == "elevated"


class TestChatStatePersistence:
    """chat_export_state/chat_import_state are what let the frontend persist
    memory across a page reload (Pyodide's interpreter is recreated from
    scratch on every visit, so nothing survives on its own)."""

    @pytest.fixture(autouse=True)
    def reset_conversation(self):
        bridge.dispatch("chat_reset", "{}")
        yield
        bridge.dispatch("chat_reset", "{}")

    def test_export_reflects_current_context_and_history(self):
        _run("chat", {"message": "I make 150k, married, in NY"})
        response = _run("chat_export_state", {})
        data = response["data"]
        assert data["context"]["amount"] == 150_000.0
        assert data["context"]["filing_status"] == "married_filing_jointly"
        assert data["context"]["state"] == "NY"
        assert len(data["history"]) == 1

    def test_import_restores_context_and_history_after_a_reset(self):
        _run("chat", {"message": "I make 150k, married, in NY"})
        exported = _run("chat_export_state", {})["data"]

        bridge.dispatch("chat_reset", "{}")
        assert _run("session_insights", {})["data"]["entries_analyzed"] == 0

        restore_response = _run("chat_import_state", exported)
        assert restore_response["data"] == {"restored": True}

        # A follow-up with no amount should reuse the restored one, exactly
        # as if the browser tab had never been closed.
        follow_up = _run("chat", {"message": "what's my tax"})
        assert follow_up["data"]["extracted"]["amount"] == 150_000.0
        assert follow_up["data"]["extracted"]["filing_status"] == "married_filing_jointly"
        assert follow_up["data"]["extracted"]["state"] == "NY"
        # The restored entry plus this new one.
        assert _run("session_insights", {})["data"]["entries_analyzed"] == 2

    def test_import_ignores_malformed_payload_without_raising(self):
        response = _run("chat_import_state", {"context": "not a dict", "history": "not a list"})
        assert response["success"] is True
        assert response["data"] == {"restored": True}


class TestAnomalousInputRobustness:
    """chat() has to stay well-behaved on real-world garbled, contradictory,
    or extreme input, not just clean questions — a router that only works
    on tidy test-suite phrasing isn't actually reliable. Every case here
    must come back success=True with a well-formed reply, never an
    exception, never garbage leaking into the reply, and never a silent
    computation on nonsense."""

    @pytest.fixture(autouse=True)
    def reset_conversation(self):
        bridge.dispatch("chat_reset", "{}")
        yield
        bridge.dispatch("chat_reset", "{}")

    @pytest.mark.parametrize(
        "message",
        [
            "\x00\x01\x02 what's my tax on 150k \x03",  # control characters
            "🤑💰🏠" * 20,  # emoji-only, no parseable text
            "150k " * 500,  # pathologically repeated input
            "税金は150kでいくらですか",  # non-English (Japanese) text
            "'; DROP TABLE users; --",  # injection-shaped garbage (no DB here, but must not crash)
            "\n\n\n\t\t\t   \n",  # whitespace-only
            "a" * 10_000,  # extremely long single token, no spaces
            "150k" + "0" * 300 + "k",  # pathological number-like token
            "I am married and single and filing jointly and separately",  # self-contradictory
            "married" * 50,  # regression case from the existing smoke test, scaled up
        ],
    )
    def test_never_raises_and_returns_well_formed_reply(self, message):
        response = _run("chat", {"message": message})
        assert response["success"] is True, f"message {message!r} raised: {response}"
        data = response["data"]
        assert isinstance(data["reply"], str) and data["reply"], "reply must be non-empty text"
        assert "intent" in data
        assert "routing_reason" in data

    def test_contradictory_filing_status_does_not_crash_and_picks_one(self):
        # "married ... separately" — the extractor must deterministically
        # pick a single filing status rather than raising or returning
        # something that isn't one of the five valid IRS statuses.
        response = _run(
            "chat",
            {"message": "I am married and single, what's my tax on 150k filing jointly separately"},
        )
        assert response["success"] is True
        valid_statuses = {
            "single",
            "married_filing_jointly",
            "married_filing_separately",
            "head_of_household",
            "qualifying_surviving_spouse",
        }
        assert response["data"]["extracted"]["filing_status"] in valid_statuses

    def test_huge_pasted_document_does_not_crash_document_analyze(self):
        # A user pasting a full (long, messy) contract shouldn't blow up the
        # document analyzer even though it's much bigger than any test
        # fixture text used elsewhere.
        huge_contract = (
            "This agreement, by and between the parties, contains a clause "
            "regarding indemnification and liability. "
        ) * 2000
        response = _run("chat", {"message": huge_contract})
        assert response["success"] is True
        assert response["data"]["intent"] == "document_analyze"

    def test_mixed_garbage_with_a_real_amount_still_extracts_it(self):
        # Noise surrounding a real signal shouldn't defeat extraction --
        # the amount is still the one thing in the message that means
        # something.
        response = _run(
            "chat", {"message": "asdkjfh 😵‍💫🌀 alkjsdf $$$ what's my tax on 150k ??? asdf"}
        )
        assert response["success"] is True
        assert response["data"]["extracted"]["amount"] == 150_000.0

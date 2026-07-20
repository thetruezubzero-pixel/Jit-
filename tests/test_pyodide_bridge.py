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
        # No topic keyword and no income mentioned (or remembered, thanks to
        # the reset_conversation fixture) — chat() should ask rather than
        # silently defaulting to a made-up income figure.
        response = _run("chat", {"message": "hello there"})
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
        ],
    )
    def test_fact_answers_directly_without_a_calculation(self, message, expected_snippet):
        response = _run("chat", {"message": message})
        data = response["data"]
        assert data["intent"] == "fact"
        assert data["result"] == {}
        assert expected_snippet in data["reply"]

    def test_fact_lookup_does_not_disturb_remembered_context(self):
        _run("chat", {"message": "I make 150k, married, in NY"})
        fact_response = _run("chat", {"message": "what's the salt cap"})
        assert fact_response["data"]["intent"] == "fact"

        # The remembered amount/filing status/state should be untouched.
        follow_up = _run("chat", {"message": "what's my tax"})
        assert follow_up["data"]["extracted"]["amount"] == 150_000.0
        assert follow_up["data"]["extracted"]["filing_status"] == "married_filing_jointly"
        assert follow_up["data"]["extracted"]["state"] == "NY"

    def test_fact_lookup_needs_no_amount_even_with_no_context(self):
        response = _run("chat", {"message": "what's the standard deduction?"})
        assert response["data"]["intent"] == "fact"


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

    def test_high_deduction_ratio_is_flagged(self):
        # chat()'s deduction_optimize path itemizes 11% of AGI by default, so
        # at a low enough income the flat $14,600 standard deduction (2024,
        # single) ends up recommended instead — and dominates a small AGI.
        _run("chat", {"message": "what deductions should I take on 30k income"})
        response = _run("session_insights", {})
        insights = " ".join(response["data"]["insights"])
        assert "audit-selection models" in insights

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

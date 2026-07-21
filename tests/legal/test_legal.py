"""
Unit tests for legal analysis modules.
"""

from jit.legal.document_processor import (
    DocumentProcessor,
    DocumentType,
)
from jit.legal.statute_parser import StatuteParser, CodeType, StatuteSection
from jit.legal.case_analyzer import CaseAnalyzer, CourtLevel
from jit.legal.compliance_engine import ComplianceEngine, RiskLevel
from jit.legal.engine import RealLegalAnalyzer
from jit.core.models import AnalysisContext, IncomeRecord, ModuleResult

# -----------------------------------------------------------------------
# DocumentProcessor tests
# -----------------------------------------------------------------------

SAMPLE_CONTRACT = """
SECTION 1. DEFINITIONS

"Confidential Information" means any non-public information disclosed.

SECTION 2. OBLIGATIONS

The receiving party agrees to hold all Confidential Information in strict
confidence and shall not disclose it to any third party.
The receiving party waives any rights to challenge the governing law.
Arbitration shall be the sole remedy for disputes. Limitation of liability
applies to all consequential damages.

SECTION 3. GOVERNING LAW

This agreement shall be governed by the laws of the State of California.
"""

SAMPLE_CONTRACT_WITH_CITATIONS = """
This agreement is governed by 26 U.S.C. § 61 and 26 U.S.C. § 162.
See also 26 C.F.R. § 1.61-1 for regulations.
The court in 348 U.S. 426 (1955) held that gross income includes all
accessions to wealth.
"""


class TestDocumentProcessor:
    def test_basic_processing(self):
        """Basic processing should return a LegalDocument."""
        proc = DocumentProcessor()
        doc = proc.process(SAMPLE_CONTRACT, document_type=DocumentType.CONTRACT)
        assert doc.document_id is not None
        assert doc.risk_score >= 0

    def test_risk_score_positive_for_risky_contract(self):
        """Contract with risk clauses should have positive risk score."""
        proc = DocumentProcessor()
        doc = proc.process(SAMPLE_CONTRACT, document_type=DocumentType.CONTRACT)
        assert doc.risk_score > 0

    def test_risk_flags_populated(self):
        """Risk flags should include detected risky clauses."""
        proc = DocumentProcessor()
        doc = proc.process(SAMPLE_CONTRACT, document_type=DocumentType.CONTRACT)
        assert len(doc.risk_flags) > 0

    def test_usc_citation_extraction(self):
        """USC citations should be extracted from document text."""
        proc = DocumentProcessor()
        doc = proc.process(SAMPLE_CONTRACT_WITH_CITATIONS)
        usc_cites = [c for c in doc.citations if c.citation_type == "statute"]
        assert len(usc_cites) >= 2

    def test_cfr_citation_extraction(self):
        """CFR citations should be extracted."""
        proc = DocumentProcessor()
        doc = proc.process(SAMPLE_CONTRACT_WITH_CITATIONS)
        cfr_cites = [c for c in doc.citations if c.citation_type == "regulation"]
        assert len(cfr_cites) >= 1

    def test_case_citation_extraction(self):
        """Case citations should be extracted."""
        proc = DocumentProcessor()
        doc = proc.process(SAMPLE_CONTRACT_WITH_CITATIONS)
        case_cites = [c for c in doc.citations if c.citation_type == "case"]
        assert len(case_cites) >= 1

    def test_provisions_extracted_from_sections(self):
        """Numbered sections should be extracted as provisions."""
        proc = DocumentProcessor()
        doc = proc.process(SAMPLE_CONTRACT, document_type=DocumentType.CONTRACT)
        assert len(doc.provisions) > 0

    def test_document_summary_generated(self):
        """Summary should be generated from document text."""
        proc = DocumentProcessor()
        doc = proc.process(SAMPLE_CONTRACT)
        assert doc.summary is not None
        assert len(doc.summary) > 0


# -----------------------------------------------------------------------
# StatuteParser tests
# -----------------------------------------------------------------------

SAMPLE_STATUTE_TEXT = """
§ 61. Gross income defined

(a) General definition.

Except as otherwise provided in this subtitle, gross income means all
income from whatever source derived, including (but not limited to) the
following items:

(1) Compensation for services, including fees, commissions, fringe
benefits, and similar items;

(2) Gross income derived from business;

(3) Gains derived from dealings in property.

"Gross income" means all income from whatever source derived.

NOTE: See also section 62 of this title for above-the-line deductions.
"""


class TestStatuteParser:
    def test_parse_usc_section(self):
        """Should parse a USC section with definitions and keywords."""
        parser = StatuteParser()
        section = parser.parse_usc_section(
            title="26",
            section="61",
            text=SAMPLE_STATUTE_TEXT,
            heading="Gross income defined",
        )
        assert section.code_type == CodeType.USC
        assert section.title == "26"
        assert section.section == "61"
        assert section.citation == "26 U.S.C. § 61"

    def test_definitions_extracted(self):
        """Defined terms should be extracted from statute text."""
        parser = StatuteParser()
        section = parser.parse_usc_section("26", "61", SAMPLE_STATUTE_TEXT)
        assert "Gross income" in section.definitions

    def test_keyword_extraction(self):
        """Tax-relevant keywords should be identified."""
        parser = StatuteParser()
        section = parser.parse_usc_section("26", "61", SAMPLE_STATUTE_TEXT)
        assert "gross income" in section.keywords

    def test_cfr_citation(self):
        """CFR section should have correct citation format."""
        parser = StatuteParser()
        section = parser.parse_cfr_section("26", "1.61-1", "Income from services...")
        assert "C.F.R." in section.citation

    def test_state_code_citation_uses_generic_fallback(self):
        """Non-USC/CFR code types should fall back to the generic citation format."""
        section = StatuteSection(code_type=CodeType.STATE_CODE, title="CA", section="17041")
        assert section.citation == "state Title CA, § 17041"

    def test_cfr_xref_extraction_matches_standard_space_format(self):
        """Regression: _CFR_XREF_PATTERN required the section number to
        immediately follow '§' with no whitespace, so the standard
        citation format ('§ 1.61-1', with a space) never matched -- only
        the rarer no-space form did. document_processor.py's equivalent
        pattern already allows optional whitespace after '§'; statute_parser
        did not, so real-world CFR cross-references were silently dropped."""
        parser = StatuteParser()
        section = parser.parse_cfr_section(
            "26",
            "1.62-1",
            "See 26 C.F.R. § 1.61 for further guidance on this matter.",
        )
        assert "26 C.F.R. § 1.61" in section.cross_references

    def test_parse_document_splits_multiple_sections(self):
        """parse_document should split a multi-section statute into an indexed set."""
        parser = StatuteParser()
        doc_text = (
            "\n§ 61. Gross income defined\n\n"
            "(a) General definition.\n"
            "Gross income means all income from whatever source derived.\n\n"
            "§ 62. Adjusted gross income defined\n\n"
            "(a) Definition.\n"
            "The term adjusted gross income means gross income minus certain "
            "deductions.\n"
        )
        index = parser.parse_document(doc_text, code_type=CodeType.USC, title="26")
        assert [s.section for s in index.sections] == ["61", "62"]
        assert index.sections[0].heading == "Gross income defined"
        assert index.sections[1].citation == "26 U.S.C. § 62"

    def test_statute_index_get_section(self):
        """get_section should retrieve a previously indexed section by number."""
        parser = StatuteParser()
        doc_text = "\n§ 61. Gross income defined\n\nGross income means all income.\n"
        index = parser.parse_document(doc_text, code_type=CodeType.USC, title="26")
        assert index.get_section("61") is not None
        assert index.get_section("61").heading == "Gross income defined"
        assert index.get_section("999") is None

    def test_parse_document_cfr_code_type(self):
        """parse_document should dispatch to parse_cfr_section for CFR documents.

        Note: the section-marker regex used by parse_document (designed for
        plain USC-style numbers like "61" or "162a") only captures the
        leading digits of a dotted CFR-style number like "1.61-1", so this
        uses an undotted number purely to exercise the CFR dispatch branch.
        """
        parser = StatuteParser()
        doc_text = "\n§ 1. Gross income defined\n\nIncome from services is included.\n"
        index = parser.parse_document(doc_text, code_type=CodeType.CFR, title="26")
        assert len(index.sections) == 1
        assert index.sections[0].code_type == CodeType.CFR
        assert index.sections[0].citation == "26 C.F.R. § 1"

    def test_statute_index_search_matches_heading_and_text(self):
        """search should find sections by heading, body text, or keyword."""
        parser = StatuteParser()
        doc_text = (
            "\n§ 61. Gross income defined\n\n"
            "Gross income means all income from whatever source derived.\n\n"
            "§ 62. Adjusted gross income defined\n\n"
            "The term adjusted gross income means gross income minus certain "
            "deductions.\n"
        )
        index = parser.parse_document(doc_text, code_type=CodeType.USC, title="26")
        results = index.search("adjusted gross income")
        assert [s.section for s in results] == ["62"]
        assert index.search("no such phrase anywhere") == []


# -----------------------------------------------------------------------
# CaseAnalyzer tests
# -----------------------------------------------------------------------

SAMPLE_OPINION = """
Commissioner v. Glenshaw Glass Co., 348 U.S. 426 (1955)

The issue before the court is whether punitive damages constitute gross
income under 26 U.S.C. § 61.

We hold that punitive damages received by a taxpayer constitute gross
income under section 61 of the Internal Revenue Code. The court finds
that gross income encompasses all "undeniable accessions to wealth,
clearly realized, and over which the taxpayers have complete dominion."

The Commissioner's position is affirmed.
"""


class TestCaseAnalyzer:
    def test_add_case_from_text(self):
        """Should parse and index a case from raw text."""
        analyzer = CaseAnalyzer()
        from datetime import date

        case = analyzer.add_case_from_text(
            case_name="Commissioner v. Glenshaw Glass",
            citation="348 U.S. 426 (1955)",
            court_level=CourtLevel.US_SUPREME_COURT,
            full_text=SAMPLE_OPINION,
            decision_date=date(1955, 3, 7),
        )
        assert case.case_name == "Commissioner v. Glenshaw Glass"
        assert case.authority_weight == 1.0  # SCOTUS

    def test_find_precedents(self):
        """Should find relevant precedents for a keyword query."""
        analyzer = CaseAnalyzer()
        analyzer.add_case_from_text(
            case_name="Commissioner v. Glenshaw Glass",
            citation="348 U.S. 426 (1955)",
            court_level=CourtLevel.US_SUPREME_COURT,
            full_text=SAMPLE_OPINION,
        )
        results = analyzer.find_precedents("gross income punitive damages")
        assert len(results) > 0
        assert results[0].relevance_score > 0

    def test_holdings_extracted(self):
        """Holdings should be extracted from opinion text."""
        analyzer = CaseAnalyzer()
        case = analyzer.add_case_from_text(
            case_name="Test Case",
            citation="100 U.S. 100",
            court_level=CourtLevel.US_SUPREME_COURT,
            full_text=SAMPLE_OPINION,
        )
        assert len(case.holdings) > 0

    def test_get_case_by_citation(self):
        """Should retrieve case by citation."""
        analyzer = CaseAnalyzer()
        analyzer.add_case_from_text(
            "Test Case",
            "100 U.S. 1 (2000)",
            CourtLevel.US_SUPREME_COURT,
            SAMPLE_OPINION,
        )
        retrieved = analyzer.get_case_by_citation("100 U.S. 1 (2000)")
        assert retrieved is not None
        assert retrieved.case_name == "Test Case"


# -----------------------------------------------------------------------
# ComplianceEngine tests
# -----------------------------------------------------------------------


class TestComplianceEngine:
    def test_no_issues_basic_compliant(self):
        """Basic compliant scenario should have no critical issues."""
        engine = ComplianceEngine()
        result = engine.check_individual_tax_compliance(
            gross_income=75_000,
            tax_year=2024,
            filing_status_str="single",
            taxes_withheld=15_000,
            taxes_paid=0,
        )
        assert result.is_compliant

    def test_unknown_withholding_skips_underpayment_check_instead_of_assuming_zero(self):
        # Regression: taxes_withheld/taxes_paid used to be required floats,
        # so a caller with no way to know them (platform.py's cross-module
        # pipeline) passed 0.0 as a stand-in for "unknown" -- indistinguishable
        # from a real $0, which meant every sufficiently high income got
        # flagged as underpaid regardless of actual withholding. None must
        # skip the check rather than assume the worst case.
        engine = ComplianceEngine()
        result = engine.check_individual_tax_compliance(
            gross_income=200_000,
            tax_year=2024,
            filing_status_str="single",
            taxes_withheld=None,
            taxes_paid=None,
        )
        underpayment_issues = [i for i in result.issues if i.issue_id == "underpayment_001"]
        assert underpayment_issues == []
        assert any("not checked" in p for p in result.passed_checks)

    def test_genuinely_zero_withholding_still_flags_underpayment(self):
        # The fix above must not silently suppress a real, known $0.
        engine = ComplianceEngine()
        result = engine.check_individual_tax_compliance(
            gross_income=200_000,
            tax_year=2024,
            filing_status_str="single",
            taxes_withheld=0.0,
            taxes_paid=0.0,
        )
        underpayment_issues = [i for i in result.issues if i.issue_id == "underpayment_001"]
        assert len(underpayment_issues) == 1

    def test_fbar_triggered(self):
        """FBAR issue should be triggered when foreign balance exceeds $10k."""
        engine = ComplianceEngine()
        result = engine.check_individual_tax_compliance(
            gross_income=100_000,
            tax_year=2024,
            filing_status_str="single",
            taxes_withheld=20_000,
            taxes_paid=0,
            has_foreign_accounts=True,
            aggregate_foreign_balance=50_000,
        )
        fbar_issues = [i for i in result.issues if i.issue_id == "fbar_001"]
        assert len(fbar_issues) == 1
        assert fbar_issues[0].risk_level == RiskLevel.HIGH

    def test_fatca_triggered(self):
        """FATCA issue triggered when foreign assets exceed $50k."""
        engine = ComplianceEngine()
        result = engine.check_individual_tax_compliance(
            gross_income=200_000,
            tax_year=2024,
            filing_status_str="single",
            taxes_withheld=40_000,
            taxes_paid=0,
            has_foreign_assets=75_000,
        )
        fatca_issues = [i for i in result.issues if i.issue_id == "fatca_001"]
        assert len(fatca_issues) == 1

    def test_1099_issue_for_missing_forms(self):
        """Missing 1099s should generate compliance issue."""
        engine = ComplianceEngine()
        result = engine.check_individual_tax_compliance(
            gross_income=100_000,
            tax_year=2024,
            filing_status_str="single",
            taxes_withheld=20_000,
            taxes_paid=0,
            issued_1099s_required=5,
            issued_1099s_filed=3,
        )
        issues_1099 = [i for i in result.issues if "1099" in i.issue_id]
        assert len(issues_1099) == 1

    def test_compliance_score_decreases_with_issues(self):
        """More issues should result in lower compliance score."""
        engine = ComplianceEngine()
        clean = engine.check_individual_tax_compliance(
            gross_income=75_000,
            tax_year=2024,
            filing_status_str="single",
            taxes_withheld=15_000,
            taxes_paid=0,
        )
        risky = engine.check_individual_tax_compliance(
            gross_income=75_000,
            tax_year=2024,
            filing_status_str="single",
            taxes_withheld=0,
            taxes_paid=0,
            has_foreign_accounts=True,
            aggregate_foreign_balance=100_000,
            has_foreign_assets=80_000,
            issued_1099s_required=10,
            issued_1099s_filed=0,
        )
        assert risky.compliance_score < clean.compliance_score


# -----------------------------------------------------------------------
# RealLegalAnalyzer tests (the platform.py cross-module orchestration path)
# -----------------------------------------------------------------------


class TestRealLegalAnalyzer:
    def test_high_income_with_no_withholding_data_is_not_flagged_as_underpaid(self):
        # Regression: AnalysisContext has no field for withholding or
        # estimated payments already made, so RealLegalAnalyzer used to pass
        # 0.0 for both to check_individual_tax_compliance -- indistinguishable
        # from a real $0, which meant every case routed through platform.py
        # with meaningful income got an unconditional false "Potential
        # Underpayment of Estimated Taxes" finding.
        analyzer = RealLegalAnalyzer()
        context = AnalysisContext(
            case_id="test",
            filing_status="single",
            state="CA",
            incomes=[IncomeRecord(kind="w2", amount=200_000, source="employer")],
        )
        accounting = ModuleResult(
            module="accounting",
            version="v1",
            data={"gross_income": 200_000, "total_tax": 45_000},
        )
        result = analyzer.analyze(context, accounting)
        assert result["compliance_issues"] == []
        assert result["compliance_status"] == "clear"

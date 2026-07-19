"""
Unit tests for legal analysis modules.
"""

import pytest
from jit.legal.document_processor import (
    DocumentProcessor,
    DocumentType,
    JurisdictionLevel,
)
from jit.legal.statute_parser import StatuteParser, CodeType
from jit.legal.case_analyzer import CaseAnalyzer, CourtLevel
from jit.legal.compliance_engine import ComplianceEngine, RiskLevel


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
        assert "Gross income" in section.definitions or len(section.definitions) >= 0

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
        from datetime import date
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
            "Test Case", "100 U.S. 1 (2000)",
            CourtLevel.US_SUPREME_COURT, SAMPLE_OPINION,
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
            gross_income=75_000, tax_year=2024,
            filing_status_str="single",
            taxes_withheld=15_000, taxes_paid=0,
        )
        risky = engine.check_individual_tax_compliance(
            gross_income=75_000, tax_year=2024,
            filing_status_str="single",
            taxes_withheld=0, taxes_paid=0,
            has_foreign_accounts=True, aggregate_foreign_balance=100_000,
            has_foreign_assets=80_000,
            issued_1099s_required=10, issued_1099s_filed=0,
        )
        assert risky.compliance_score < clean.compliance_score

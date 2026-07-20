"""
Case law analyzer for legal precedent tracking and relevance scoring.

Indexes court opinions, extracts holdings and key principles, and
scores case relevance to user queries using keyword-based matching.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Dict, List, Optional, Tuple


class CourtLevel(str, Enum):
    """U.S. federal court hierarchy level."""

    US_SUPREME_COURT = "us_supreme_court"
    US_CIRCUIT_COURT = "us_circuit_court"  # Federal Courts of Appeal
    US_DISTRICT_COURT = "us_district_court"  # Federal District Courts
    US_TAX_COURT = "us_tax_court"
    US_BANKRUPTCY_COURT = "us_bankruptcy_court"
    STATE_SUPREME_COURT = "state_supreme_court"
    STATE_APPEALS_COURT = "state_appeals_court"
    STATE_TRIAL_COURT = "state_trial_court"
    ADMINISTRATIVE = "administrative"  # ALJ, NLRB, IRS Appeals, etc.


# Court authority weights for precedent scoring
COURT_WEIGHTS: Dict[CourtLevel, float] = {
    CourtLevel.US_SUPREME_COURT: 1.0,
    CourtLevel.US_CIRCUIT_COURT: 0.85,
    CourtLevel.US_TAX_COURT: 0.80,
    CourtLevel.US_DISTRICT_COURT: 0.65,
    CourtLevel.STATE_SUPREME_COURT: 0.60,
    CourtLevel.STATE_APPEALS_COURT: 0.50,
    CourtLevel.US_BANKRUPTCY_COURT: 0.45,
    CourtLevel.STATE_TRIAL_COURT: 0.35,
    CourtLevel.ADMINISTRATIVE: 0.30,
}


@dataclass
class CaseParty:
    """A party to a legal case."""

    name: str
    role: str  # "plaintiff", "defendant", "appellant", "appellee", "petitioner", etc.


@dataclass
class Holding:
    """The legal holding of a case."""

    text: str
    area_of_law: str
    is_majority: bool = True
    supporting_sections: List[str] = field(default_factory=list)  # USC/CFR sections


@dataclass
class CaseRecord:
    """A court opinion / case record."""

    case_id: str
    case_name: str
    citation: str
    court_level: CourtLevel
    decision_date: Optional[date] = None
    court_name: Optional[str] = None
    jurisdiction: Optional[str] = None  # Circuit, state, etc.

    parties: List[CaseParty] = field(default_factory=list)
    holdings: List[Holding] = field(default_factory=list)
    legal_issues: List[str] = field(default_factory=list)
    statutes_cited: List[str] = field(default_factory=list)
    cases_cited: List[str] = field(default_factory=list)
    full_text: Optional[str] = None
    summary: Optional[str] = None
    keywords: List[str] = field(default_factory=list)

    # Computed fields
    authority_weight: float = 0.0  # Based on court level

    def __post_init__(self) -> None:
        """Set authority weight based on court level."""
        self.authority_weight = COURT_WEIGHTS.get(self.court_level, 0.3)


@dataclass
class Precedent:
    """A relevant precedent found for a query."""

    case: CaseRecord
    relevance_score: float  # 0.0 to 1.0
    matched_keywords: List[str] = field(default_factory=list)
    relevance_explanation: str = ""


class CaseAnalyzer:
    """
    Analyzes and indexes case law for legal precedent research.

    Maintains an in-memory index of case records and provides
    relevance-scored search against legal queries.
    """

    def __init__(self) -> None:
        """Initialize the case analyzer with an empty index."""
        self._cases: List[CaseRecord] = []
        self._citation_index: Dict[str, CaseRecord] = {}

    def add_case(self, case: CaseRecord) -> None:
        """Add a case record to the index."""
        self._cases.append(case)
        self._citation_index[case.citation] = case

    def add_case_from_text(
        self,
        case_name: str,
        citation: str,
        court_level: CourtLevel,
        full_text: str,
        decision_date: Optional[date] = None,
        court_name: Optional[str] = None,
    ) -> CaseRecord:
        """
        Parse and add a case from raw text.

        Args:
            case_name: Name of the case (e.g., "Commissioner v. Glenshaw Glass").
            citation: Legal citation (e.g., "348 U.S. 426 (1955)").
            court_level: Level of the deciding court.
            full_text: Full opinion text.
            decision_date: Date of decision.
            court_name: Name of the specific court.

        Returns:
            The created CaseRecord.
        """
        case_id = re.sub(r"[^a-zA-Z0-9]", "_", case_name.lower())[:40]
        holdings = self._extract_holdings(full_text)
        legal_issues = self._extract_legal_issues(full_text)
        statutes = self._extract_statute_citations(full_text)
        cases = self._extract_case_citations(full_text)
        keywords = self._extract_keywords(full_text)
        summary = self._summarize(full_text)

        record = CaseRecord(
            case_id=case_id,
            case_name=case_name,
            citation=citation,
            court_level=court_level,
            decision_date=decision_date,
            court_name=court_name,
            holdings=holdings,
            legal_issues=legal_issues,
            statutes_cited=statutes,
            cases_cited=cases,
            full_text=full_text,
            summary=summary,
            keywords=keywords,
        )
        self.add_case(record)
        return record

    def find_precedents(
        self,
        query: str,
        area_of_law: Optional[str] = None,
        min_court_level: Optional[CourtLevel] = None,
        max_results: int = 10,
    ) -> List[Precedent]:
        """
        Find relevant precedents for a legal query.

        Args:
            query: Natural language or keyword query.
            area_of_law: Optional filter by area of law.
            min_court_level: Minimum court level to include.
            max_results: Maximum number of results to return.

        Returns:
            List of Precedent objects sorted by relevance score.
        """
        query_keywords = self._tokenize(query)
        min_weight = COURT_WEIGHTS.get(min_court_level, 0.0) if min_court_level else 0.0

        precedents: List[Precedent] = []

        for case in self._cases:
            if case.authority_weight < min_weight:
                continue

            if area_of_law:
                area_match = any(
                    area_of_law.lower() in h.area_of_law.lower() for h in case.holdings
                )
                if not area_match:
                    continue

            score, matched_kws, explanation = self._score_relevance(case, query_keywords)
            if score > 0:
                precedents.append(
                    Precedent(
                        case=case,
                        relevance_score=round(score, 4),
                        matched_keywords=matched_kws,
                        relevance_explanation=explanation,
                    )
                )

        # Sort by relevance score, then authority weight
        precedents.sort(key=lambda p: (p.relevance_score, p.case.authority_weight), reverse=True)
        return precedents[:max_results]

    def get_case_by_citation(self, citation: str) -> Optional[CaseRecord]:
        """Retrieve a case by its legal citation."""
        return self._citation_index.get(citation)

    def get_citing_cases(self, citation: str) -> List[CaseRecord]:
        """Find all cases that cite the given citation."""
        return [c for c in self._cases if citation in (c.cases_cited or [])]

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _score_relevance(
        self, case: CaseRecord, query_keywords: List[str]
    ) -> Tuple[float, List[str], str]:
        """Score case relevance against query keywords."""
        matched: List[str] = []
        full_text_lower = (case.full_text or "").lower()
        summary_lower = (case.summary or "").lower()
        case_keywords_lower = [k.lower() for k in case.keywords]

        for kw in query_keywords:
            kw_lower = kw.lower()
            if (
                kw_lower in case_keywords_lower
                or kw_lower in summary_lower
                or kw_lower in full_text_lower
            ):
                matched.append(kw)

        if not matched:
            return 0.0, [], ""

        keyword_score = len(matched) / max(len(query_keywords), 1)
        # Boost by authority weight
        combined_score = keyword_score * 0.7 + case.authority_weight * 0.3

        explanation = (
            f"Matched {len(matched)}/{len(query_keywords)} keywords. "
            f"Court authority weight: {case.authority_weight:.2f}."
        )
        return combined_score, matched, explanation

    def _tokenize(self, text: str) -> List[str]:
        """Tokenize a query into meaningful keywords."""
        stop_words = {
            "the",
            "a",
            "an",
            "of",
            "in",
            "to",
            "for",
            "is",
            "are",
            "was",
            "and",
            "or",
            "but",
            "with",
            "that",
            "this",
            "it",
        }
        tokens = re.findall(r"[a-zA-Z]{3,}", text.lower())
        return [t for t in tokens if t not in stop_words]

    def _extract_holdings(self, text: str) -> List[Holding]:
        """Extract case holdings from opinion text."""
        holdings: List[Holding] = []
        # Look for "held that", "we hold", "the court holds" patterns
        patterns = [
            r"(?:we\s+hold|held\s+that|the\s+court\s+holds?|it\s+is\s+held)\s+([^.]+\.)",
        ]
        for pattern in patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                holdings.append(
                    Holding(
                        text=match.group(1).strip(),
                        area_of_law="general",
                        is_majority=True,
                    )
                )
        return holdings[:5]

    def _extract_legal_issues(self, text: str) -> List[str]:
        """Extract legal issues from the text."""
        issues: List[str] = []
        issue_patterns = [
            r"[Tt]he\s+(?:sole\s+)?(?:issue|question)\s+"
            r"(?:before\s+(?:the\s+)?(?:court|us)\s+)?is\s+([^.]+)\.",
            r"[Ww]e\s+(?:must\s+)?(?:decide|determine|consider)\s+(?:whether\s+)?([^.]+)\.",
        ]
        for pattern in issue_patterns:
            for match in re.finditer(pattern, text):
                issues.append(match.group(1).strip())
        return issues[:5]

    def _extract_statute_citations(self, text: str) -> List[str]:
        """Extract USC and CFR statute citations."""
        citations: List[str] = []
        patterns = [
            re.compile(
                r"\b(\d+)\s+U\.?S\.?C\.?\s+(?:§+|sec\.?)\s*(\d+[a-z]?)",
                re.IGNORECASE,
            ),
            re.compile(
                r"\b(\d+)\s+C\.?F\.?R\.?\s+(?:§+|pt\.?\s*)(\d+(?:\.\d+)?)",
                re.IGNORECASE,
            ),
        ]
        for pattern in patterns:
            for match in pattern.finditer(text):
                citations.append(match.group(0))
        return list(set(citations))[:20]

    def _extract_case_citations(self, text: str) -> List[str]:
        """Extract cited case references."""
        pattern = re.compile(r"\b\d+\s+[A-Z][A-Za-z\.]+\s+\d+(?:\s*\(\d{4}\))?")
        return list(set(m.group(0) for m in pattern.finditer(text)))[:20]

    def _extract_keywords(self, text: str) -> List[str]:
        """Extract domain keywords from case text."""
        domain_terms = [
            "income",
            "deduction",
            "gross income",
            "taxable income",
            "basis",
            "realization",
            "recognition",
            "exclusion",
            "exemption",
            "credit",
            "capital gain",
            "ordinary income",
            "property",
            "transaction",
            "sham",
            "substance over form",
            "business purpose",
            "step transaction",
            "assignment of income",
            "constructive receipt",
            "accrual",
            "cash method",
            "at-risk",
            "passive activity",
            "negligence",
            "fraud",
            "willful",
            "penalty",
            "statute of limitations",
            "contract",
            "damages",
            "breach",
            "consideration",
        ]
        text_lower = text.lower()
        return [t for t in domain_terms if t in text_lower]

    def _summarize(self, text: str) -> str:
        """Generate a brief case summary from the opinion text."""
        paragraphs = [p.strip() for p in text.split("\n\n") if len(p.strip()) > 80]
        if paragraphs:
            return paragraphs[0][:600] + ("..." if len(paragraphs[0]) > 600 else "")
        return text[:300]

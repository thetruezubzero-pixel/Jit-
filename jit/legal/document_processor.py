"""
Legal document processor for parsing and analyzing legal documents.

Handles contracts, statutes, regulations, court opinions, and other
legal documents, extracting key provisions and metadata.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Dict, List, Optional, Tuple


class DocumentType(str, Enum):
    """Types of legal documents."""

    CONTRACT = "contract"
    STATUTE = "statute"
    REGULATION = "regulation"
    COURT_OPINION = "court_opinion"
    BRIEF = "brief"
    COMPLAINT = "complaint"
    MOTION = "motion"
    ORDER = "order"
    LEASE = "lease"
    WILL = "will"
    TRUST = "trust"
    POWER_OF_ATTORNEY = "power_of_attorney"
    CORPORATE_BYLAWS = "corporate_bylaws"
    PARTNERSHIP_AGREEMENT = "partnership_agreement"
    EMPLOYMENT_AGREEMENT = "employment_agreement"
    OTHER = "other"


class JurisdictionLevel(str, Enum):
    """Level of jurisdiction."""

    FEDERAL = "federal"
    STATE = "state"
    LOCAL = "local"
    TRIBAL = "tribal"
    INTERNATIONAL = "international"


@dataclass
class LegalProvision:
    """A single provision or clause extracted from a legal document."""

    provision_id: str
    title: Optional[str]
    text: str
    section_number: Optional[str] = None
    page_number: Optional[int] = None
    keywords: List[str] = field(default_factory=list)
    cross_references: List[str] = field(default_factory=list)
    risk_flags: List[str] = field(default_factory=list)


@dataclass
class Citation:
    """A legal citation found in a document."""

    raw_text: str
    citation_type: str  # "case", "statute", "regulation", "secondary"
    reporter: Optional[str] = None
    volume: Optional[str] = None
    page: Optional[str] = None
    year: Optional[int] = None
    court: Optional[str] = None
    normalized: Optional[str] = None


@dataclass
class LegalDocument:
    """A parsed legal document with extracted metadata."""

    document_id: str
    document_type: DocumentType
    title: str
    text: str

    jurisdiction_level: JurisdictionLevel = JurisdictionLevel.FEDERAL
    jurisdiction: Optional[str] = None  # State code or circuit for federal
    date_filed: Optional[date] = None
    date_effective: Optional[date] = None

    parties: List[str] = field(default_factory=list)
    provisions: List[LegalProvision] = field(default_factory=list)
    citations: List[Citation] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    summary: Optional[str] = None
    risk_score: float = 0.0  # 0.0 (low risk) to 1.0 (high risk)
    risk_flags: List[str] = field(default_factory=list)
    metadata: Dict = field(default_factory=dict)


# Common legal citation patterns
_CASE_CITATION_PATTERN = re.compile(
    r"\b(\d+)\s+([A-Z][A-Za-z\.]+(?:[ \t]+[A-Za-z\.]+)*)\s+(\d+)(?:\s*\((\d{4})\))?"
)
_STATUTE_CITATION_PATTERN = re.compile(
    r"\b(\d+)\s+U\.?S\.?C\.?\s+(?:§+|sec\.?)\s*(\d+[a-z]?(?:-\d+[a-z]?)?)" r"(?:\(([a-z0-9]+)\))?",
    re.IGNORECASE,
)
_CFR_CITATION_PATTERN = re.compile(
    r"\b(\d+)\s+C\.?F\.?R\.?\s+(?:§+\s*|Part\s+|pt\.?\s*)(\d+(?:\.\d+(?:-\d+[a-z]*)?)?)",
    re.IGNORECASE,
)
_STATE_CODE_PATTERN = re.compile(
    r"(?:[A-Z][a-z]+\.?\s+Code\s+(?:Ann\.?\s+)?(?:§+|sec\.?)\s*\d+[\w\.\-]*)",
    re.IGNORECASE,
)

# High-risk legal phrases
HIGH_RISK_PHRASES = [
    "indemnif",
    "limitation of liability",
    "waiver of rights",
    "arbitration",
    "class action waiver",
    "liquidated damages",
    "penalty",
    "forfeiture",
    "termination for convenience",
    "non-compete",
    "non-solicitation",
    "assignment of invention",
    "governing law",
    "severability",
    "force majeure",
    "confession of judgment",
    "cognovit",
    "personal guarantee",
]


class DocumentProcessor:
    """
    Processes legal documents to extract provisions, citations, and risk flags.

    Performs pattern matching on legal citation formats, extracts
    key provisions, and scores documents for legal risk.
    """

    def process(
        self,
        text: str,
        document_type: DocumentType = DocumentType.OTHER,
        document_id: Optional[str] = None,
        title: str = "Untitled Document",
        jurisdiction_level: JurisdictionLevel = JurisdictionLevel.FEDERAL,
        jurisdiction: Optional[str] = None,
    ) -> LegalDocument:
        """
        Process a legal document and extract structured data.

        Args:
            text: Raw text of the document.
            document_type: Type of legal document.
            document_id: Unique identifier for the document.
            title: Document title.
            jurisdiction_level: Federal, state, or local.
            jurisdiction: State code or circuit identifier.

        Returns:
            LegalDocument with extracted provisions, citations, and analysis.
        """
        if document_id is None:
            import hashlib

            document_id = hashlib.md5(text[:200].encode()).hexdigest()[:12]

        citations = self._extract_citations(text)
        provisions = self._extract_provisions(text, document_type)
        keywords = self._extract_keywords(text)
        risk_flags, risk_score = self._assess_risk(text, document_type)
        summary = self._generate_summary(text, document_type)

        return LegalDocument(
            document_id=document_id,
            document_type=document_type,
            title=title,
            text=text,
            jurisdiction_level=jurisdiction_level,
            jurisdiction=jurisdiction,
            provisions=provisions,
            citations=citations,
            keywords=keywords,
            summary=summary,
            risk_score=risk_score,
            risk_flags=risk_flags,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _extract_citations(self, text: str) -> List[Citation]:
        """Extract all legal citations from document text."""
        citations: List[Citation] = []
        seen: set = set()

        # Case citations
        for match in _CASE_CITATION_PATTERN.finditer(text):
            raw = match.group(0)
            if raw not in seen:
                seen.add(raw)
                citations.append(
                    Citation(
                        raw_text=raw,
                        citation_type="case",
                        volume=match.group(1),
                        reporter=match.group(2).strip(),
                        page=match.group(3),
                        year=int(match.group(4)) if match.group(4) else None,
                        normalized=f"{match.group(1)} {match.group(2).strip()} {match.group(3)}",
                    )
                )

        # USC statute citations
        for match in _STATUTE_CITATION_PATTERN.finditer(text):
            raw = match.group(0)
            if raw not in seen:
                seen.add(raw)
                citations.append(
                    Citation(
                        raw_text=raw,
                        citation_type="statute",
                        volume=match.group(1),
                        page=match.group(2),
                        normalized=f"{match.group(1)} U.S.C. § {match.group(2)}",
                    )
                )

        # CFR citations
        for match in _CFR_CITATION_PATTERN.finditer(text):
            raw = match.group(0)
            if raw not in seen:
                seen.add(raw)
                citations.append(
                    Citation(
                        raw_text=raw,
                        citation_type="regulation",
                        volume=match.group(1),
                        page=match.group(2),
                        normalized=f"{match.group(1)} C.F.R. § {match.group(2)}",
                    )
                )

        return citations

    def _extract_provisions(self, text: str, doc_type: DocumentType) -> List[LegalProvision]:
        """Extract sections and provisions from document text."""
        provisions: List[LegalProvision] = []

        # Split on numbered sections or headings
        section_pattern = re.compile(
            r"(?:^|\n)(?:SECTION|Section|SEC\.|§)\s*(\d+(?:\.\d+)*)[ \t]*(.*?)"
            r"(?=\n(?:SECTION|Section|SEC\.|§)\s*\d|\Z)",
            re.DOTALL | re.IGNORECASE,
        )

        for i, match in enumerate(section_pattern.finditer(text)):
            section_num = match.group(1)
            rest = match.group(2).strip()
            lines = rest.split("\n", 1)
            title = lines[0].strip() if lines else ""
            body = lines[1].strip() if len(lines) > 1 else rest

            # Identify keywords in this section
            kws = self._extract_keywords(body)
            risk_flags = [phrase for phrase in HIGH_RISK_PHRASES if phrase.lower() in body.lower()]

            provisions.append(
                LegalProvision(
                    provision_id=f"sec-{section_num}",
                    title=title or None,
                    text=body[:2000],  # Truncate very long sections
                    section_number=section_num,
                    keywords=kws[:10],
                    risk_flags=risk_flags,
                )
            )

        # If no section headers found, treat as single provision
        if not provisions and text.strip():
            provisions.append(
                LegalProvision(
                    provision_id="body",
                    title=None,
                    text=text[:5000],
                    keywords=self._extract_keywords(text)[:10],
                    risk_flags=[p for p in HIGH_RISK_PHRASES if p.lower() in text.lower()],
                )
            )

        return provisions

    def _extract_keywords(self, text: str) -> List[str]:
        """Extract significant legal keywords from text."""
        legal_keywords = [
            "liability",
            "warranty",
            "indemnity",
            "jurisdiction",
            "venue",
            "arbitration",
            "breach",
            "damages",
            "termination",
            "confidential",
            "intellectual property",
            "copyright",
            "trademark",
            "patent",
            "assignment",
            "sublicense",
            "force majeure",
            "governing law",
            "dispute resolution",
            "non-compete",
            "non-disclosure",
            "NDA",
            "consideration",
            "representations",
            "warranties",
            "covenants",
            "conditions",
            "obligations",
            "rights",
            "remedies",
            "waiver",
            "amendment",
            "entire agreement",
            "severability",
            "notices",
            "counterparts",
            "electronic signatures",
        ]
        text_lower = text.lower()
        return [kw for kw in legal_keywords if kw.lower() in text_lower]

    def _assess_risk(self, text: str, doc_type: DocumentType) -> Tuple[List[str], float]:
        """Assess legal risk level of the document."""
        text_lower = text.lower()
        flags: List[str] = []

        for phrase in HIGH_RISK_PHRASES:
            if phrase.lower() in text_lower:
                flags.append(f"Contains '{phrase}' clause — review carefully")

        # Risk score based on flag count and document type
        base_score = len(flags) / max(len(HIGH_RISK_PHRASES), 1)

        # Increase base score for certain document types
        type_multipliers = {
            DocumentType.CONTRACT: 1.2,
            DocumentType.EMPLOYMENT_AGREEMENT: 1.3,
            DocumentType.LEASE: 1.1,
            DocumentType.PARTNERSHIP_AGREEMENT: 1.2,
        }
        multiplier = type_multipliers.get(doc_type, 1.0)
        score = min(1.0, base_score * multiplier)

        return flags, round(score, 3)

    def _generate_summary(self, text: str, doc_type: DocumentType) -> str:
        """Generate a brief summary of the legal document."""
        # Extract first meaningful paragraph as summary
        paragraphs = [p.strip() for p in text.split("\n\n") if len(p.strip()) > 50]
        if paragraphs:
            summary = paragraphs[0][:500]
            if len(paragraphs[0]) > 500:
                summary += "..."
            return summary
        return text[:300] + ("..." if len(text) > 300 else "")

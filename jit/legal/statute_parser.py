"""
Statute and regulation parser.

Parses United States Code (USC) sections, Code of Federal Regulations (CFR),
and state statutes into structured, searchable sections with cross-reference
linking.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class CodeType(str, Enum):
    """Type of legal code."""

    USC = "usc"          # United States Code
    CFR = "cfr"          # Code of Federal Regulations
    FR = "fr"            # Federal Register
    STATE_CODE = "state" # State statute/code
    LOCAL_ORD = "local"  # Local ordinance


@dataclass
class StatuteSection:
    """A parsed section of a statute or regulation."""

    code_type: CodeType
    title: str            # Title number (USC) or CFR title
    section: str          # Section number
    heading: Optional[str] = None
    text: str = ""
    subsections: List["StatuteSection"] = field(default_factory=list)
    definitions: Dict[str, str] = field(default_factory=dict)
    cross_references: List[str] = field(default_factory=list)
    effective_date: Optional[str] = None
    notes: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)

    @property
    def citation(self) -> str:
        """Return the canonical citation for this section."""
        if self.code_type == CodeType.USC:
            return f"{self.title} U.S.C. § {self.section}"
        elif self.code_type == CodeType.CFR:
            return f"{self.title} C.F.R. § {self.section}"
        return f"{self.code_type.value} Title {self.title}, § {self.section}"


@dataclass
class StatuteIndex:
    """An index of parsed statute sections for search and cross-reference."""

    code_type: CodeType
    title: str
    sections: List[StatuteSection] = field(default_factory=list)
    _section_map: Dict[str, StatuteSection] = field(default_factory=dict, repr=False)

    def add_section(self, section: StatuteSection) -> None:
        """Add a section to the index."""
        self.sections.append(section)
        self._section_map[section.section] = section

    def get_section(self, section_number: str) -> Optional[StatuteSection]:
        """Retrieve a section by number."""
        return self._section_map.get(section_number)

    def search(self, query: str) -> List[StatuteSection]:
        """Full-text search across sections."""
        query_lower = query.lower()
        results: List[StatuteSection] = []
        for section in self.sections:
            if (
                query_lower in section.text.lower()
                or (section.heading and query_lower in section.heading.lower())
                or any(query_lower in kw.lower() for kw in section.keywords)
            ):
                results.append(section)
        return results


# Pattern to match definition clauses
_DEFINITION_PATTERN = re.compile(
    r'"([^"]+)"\s+means?\s+([^;.]+)[;.]',
    re.IGNORECASE,
)

# Pattern to match cross-references within USC
_USC_XREF_PATTERN = re.compile(
    r"(?:section|§)\s*(\d+[a-z]?(?:-\d+[a-z]?)?)\s+of\s+(?:this\s+title|title\s+(\d+))",
    re.IGNORECASE,
)

# Pattern to match CFR cross-references
_CFR_XREF_PATTERN = re.compile(
    r"(\d+)\s+C\.?F\.?R\.?\s+(?:§+|part\s+|pt\.?\s*)(\d+(?:\.\d+)?)",
    re.IGNORECASE,
)


class StatuteParser:
    """
    Parses statute and regulation texts into structured sections.

    Handles USC, CFR, and generic state code formats. Extracts
    definitions, cross-references, and keyword indices for each section.
    """

    def parse_usc_section(
        self,
        title: str,
        section: str,
        text: str,
        heading: Optional[str] = None,
    ) -> StatuteSection:
        """
        Parse a United States Code section.

        Args:
            title: USC title number (e.g., "26" for Internal Revenue Code).
            section: Section number (e.g., "61").
            text: Full text of the section.
            heading: Optional section heading.

        Returns:
            Parsed StatuteSection.
        """
        definitions = self._extract_definitions(text)
        cross_refs = self._extract_usc_xrefs(text, title)
        subsections = self._extract_subsections(text, CodeType.USC, title)
        keywords = self._extract_keywords(text)
        notes = self._extract_notes(text)

        return StatuteSection(
            code_type=CodeType.USC,
            title=title,
            section=section,
            heading=heading,
            text=text,
            subsections=subsections,
            definitions=definitions,
            cross_references=cross_refs,
            keywords=keywords,
            notes=notes,
        )

    def parse_cfr_section(
        self,
        title: str,
        section: str,
        text: str,
        heading: Optional[str] = None,
    ) -> StatuteSection:
        """
        Parse a Code of Federal Regulations section.

        Args:
            title: CFR title number (e.g., "26" for IRS regulations).
            section: Section number (e.g., "1.61-1").
            text: Full text of the section.
            heading: Optional section heading.

        Returns:
            Parsed StatuteSection.
        """
        definitions = self._extract_definitions(text)
        cross_refs = self._extract_cfr_xrefs(text)
        subsections = self._extract_subsections(text, CodeType.CFR, title)
        keywords = self._extract_keywords(text)

        return StatuteSection(
            code_type=CodeType.CFR,
            title=title,
            section=section,
            heading=heading,
            text=text,
            subsections=subsections,
            definitions=definitions,
            cross_references=cross_refs,
            keywords=keywords,
        )

    def parse_document(
        self,
        text: str,
        code_type: CodeType = CodeType.USC,
        title: str = "Unknown",
    ) -> StatuteIndex:
        """
        Parse a multi-section statute document.

        Args:
            text: Full text of the statute or regulation.
            code_type: Type of legal code.
            title: Title/chapter number.

        Returns:
            StatuteIndex with all parsed sections.
        """
        index = StatuteIndex(code_type=code_type, title=title)

        # Split on section markers
        section_pattern = re.compile(
            r"(?:^|\n)§\s*(\d+[a-z]?(?:-\d+[a-z]?)?)\s*\.?\s*(.*?)(?=\n§\s*\d|\Z)",
            re.DOTALL,
        )

        for match in section_pattern.finditer(text):
            section_num = match.group(1)
            rest = match.group(2).strip()

            lines = rest.split("\n", 1)
            heading = lines[0].strip()
            body = lines[1].strip() if len(lines) > 1 else rest

            if code_type == CodeType.USC:
                section = self.parse_usc_section(title, section_num, body, heading)
            else:
                section = self.parse_cfr_section(title, section_num, body, heading)

            index.add_section(section)

        return index

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _extract_definitions(self, text: str) -> Dict[str, str]:
        """Extract defined terms and their definitions."""
        defs: Dict[str, str] = {}
        for match in _DEFINITION_PATTERN.finditer(text):
            term = match.group(1).strip()
            definition = match.group(2).strip()
            defs[term] = definition
        return defs

    def _extract_usc_xrefs(self, text: str, current_title: str) -> List[str]:
        """Extract cross-references to other USC sections."""
        refs: List[str] = []
        for match in _USC_XREF_PATTERN.finditer(text):
            ref_section = match.group(1)
            ref_title = match.group(2) if match.group(2) else current_title
            refs.append(f"{ref_title} U.S.C. § {ref_section}")
        return list(set(refs))

    def _extract_cfr_xrefs(self, text: str) -> List[str]:
        """Extract cross-references to CFR sections."""
        refs: List[str] = []
        for match in _CFR_XREF_PATTERN.finditer(text):
            refs.append(f"{match.group(1)} C.F.R. § {match.group(2)}")
        return list(set(refs))

    def _extract_subsections(
        self, text: str, code_type: CodeType, title: str
    ) -> List["StatuteSection"]:
        """Extract lettered/numbered subsections."""
        subsections: List[StatuteSection] = []
        pattern = re.compile(
            r"\(([a-z])\)\s+(.*?)(?=\([a-z]\)|\Z)", re.DOTALL
        )
        for match in pattern.finditer(text):
            label = match.group(1)
            body = match.group(2).strip()
            if len(body) > 20:
                subsections.append(
                    StatuteSection(
                        code_type=code_type,
                        title=title,
                        section=label,
                        text=body[:1000],
                        keywords=self._extract_keywords(body),
                    )
                )
        return subsections

    def _extract_keywords(self, text: str) -> List[str]:
        """Extract legal and tax-relevant keywords."""
        domain_keywords = [
            "taxpayer", "gross income", "taxable income", "deduction", "credit",
            "penalty", "interest", "assessment", "collection", "refund",
            "liability", "obligation", "right", "duty", "compliance",
            "regulations", "statute of limitations", "substantial authority",
            "reasonable cause", "willful", "fraud", "civil penalty",
            "criminal", "jurisdiction", "standing", "due process",
        ]
        text_lower = text.lower()
        return [kw for kw in domain_keywords if kw in text_lower]

    def _extract_notes(self, text: str) -> List[str]:
        """Extract statutory notes and annotations."""
        notes: List[str] = []
        note_patterns = [
            r"NOTE:\s*(.+?)(?=\n\n|\Z)",
            r"EDITORIAL NOTE:\s*(.+?)(?=\n\n|\Z)",
            r"EFFECTIVE DATE:\s*(.+?)(?=\n\n|\Z)",
        ]
        for pattern in note_patterns:
            for match in re.finditer(pattern, text, re.DOTALL | re.IGNORECASE):
                notes.append(match.group(1).strip()[:500])
        return notes

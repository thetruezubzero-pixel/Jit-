"""Shared data models used across Jit modules."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class IncomeRecord:
    kind: str
    amount: float
    source: str = "unknown"


@dataclass
class DeductionRecord:
    name: str
    amount: float
    itemized: bool = True


@dataclass
class LegalDocument:
    title: str
    text: str
    citations: list[str] = field(default_factory=list)


@dataclass
class AnalysisContext:
    case_id: str
    filing_status: str
    state: str
    incomes: list[IncomeRecord] = field(default_factory=list)
    deductions: list[DeductionRecord] = field(default_factory=list)
    legal_documents: list[LegalDocument] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ModuleResult:
    module: str
    version: str
    data: dict[str, Any]
    messages: list[str] = field(default_factory=list)


@dataclass
class AuditRecord:
    topic: str
    payload: dict[str, Any]


@dataclass
class SystemResponse:
    success: bool
    data: dict[str, Any]
    errors: list[str] = field(default_factory=list)
    audit_trail: list[AuditRecord] = field(default_factory=list)

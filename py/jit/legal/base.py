"""Abstract legal interfaces."""

from __future__ import annotations

from abc import ABC, abstractmethod

from jit.core.models import AnalysisContext, ModuleResult


class LegalAnalyzerPlugin(ABC):
    @abstractmethod
    def analyze(self, context: AnalysisContext, accounting: ModuleResult) -> dict[str, object]:
        """Return a legal analysis payload."""

"""Abstract accounting interfaces."""

from __future__ import annotations

from abc import ABC, abstractmethod

from jit.core.models import AnalysisContext


class TaxCalculatorPlugin(ABC):
    @abstractmethod
    def calculate(self, context: AnalysisContext, rules: dict[str, float]) -> dict[str, float]:
        """Return a tax analysis payload."""

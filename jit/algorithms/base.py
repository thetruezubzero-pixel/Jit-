"""Abstract recursive strategy interfaces."""

from __future__ import annotations

from abc import ABC, abstractmethod

from jit.core.models import AnalysisContext, ModuleResult


class RecommendationStrategy(ABC):
    @abstractmethod
    def recommend(
        self, context: AnalysisContext, accounting: ModuleResult, legal: ModuleResult
    ) -> dict[str, object]:
        """Return a recommendation payload."""

"""Persistence metadata and migration structures."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class StoredCase:
    case_id: str
    schema_version: str
    modules: dict[str, dict[str, object]]


@dataclass(slots=True)
class MigrationPlan:
    current_version: str
    target_version: str
    steps: list[str] = field(default_factory=list)

    def add_step(self, description: str) -> None:
        self.steps.append(description)

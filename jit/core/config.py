"""Configuration and feature management for Jit."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class AppConfig:
    api_versions: tuple[str, ...] = ("v1",)
    module_rule_versions: dict[str, str] = field(
        default_factory=lambda: {
            "accounting": "2026.1",
            "legal": "2026.1",
            "algorithms": "2026.1",
        }
    )
    feature_flags: dict[str, bool] = field(
        default_factory=lambda: {
            "live_updates": True,
            "audit_logging": True,
            "compatibility_layer": True,
        }
    )
    standard_deduction: dict[str, float] = field(
        default_factory=lambda: {
            "single": 14600.0,
            "married_filing_jointly": 29200.0,
            "head_of_household": 21900.0,
        }
    )

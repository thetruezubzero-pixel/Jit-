"""Runtime service discovery utilities."""

from __future__ import annotations

from typing import Any


class ServiceRegistry:
    def __init__(self) -> None:
        self._services: dict[str, Any] = {}

    def register(self, name: str, service: Any) -> None:
        self._services[name] = service

    def resolve(self, name: str) -> Any:
        return self._services[name]

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._services))

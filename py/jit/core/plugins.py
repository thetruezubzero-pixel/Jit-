"""Generic plugin registration helpers."""

from __future__ import annotations

from collections import defaultdict
from typing import Any


class PluginRegistry:
    def __init__(self) -> None:
        self._plugins: dict[str, dict[str, type[Any]]] = defaultdict(dict)

    def register(self, name: str, plugin: type[Any], version: str = "default") -> None:
        self._plugins[name][version] = plugin

    def get(self, name: str, version: str = "default") -> type[Any]:
        return self._plugins[name][version]

    def create(self, name: str, version: str = "default", **kwargs: Any) -> Any:
        return self.get(name, version)(**kwargs)

    def list_plugins(self) -> dict[str, list[str]]:
        return {name: sorted(versions) for name, versions in self._plugins.items()}

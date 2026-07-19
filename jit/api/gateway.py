"""Versioned API gateway with middleware support."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class Request:
    version: str
    path: str
    payload: dict[str, Any]
    metadata: dict[str, Any] = field(default_factory=dict)


Handler = Callable[[Request], dict[str, Any]]
Middleware = Callable[[Request, Handler], dict[str, Any]]


class ApiGateway:
    def __init__(self) -> None:
        self._routes: dict[tuple[str, str], Handler] = {}
        self._middleware: list[Middleware] = []

    def add_route(self, version: str, path: str, handler: Handler) -> None:
        self._routes[(version, path)] = handler

    def add_middleware(self, middleware: Middleware) -> None:
        self._middleware.append(middleware)

    def handle(self, request: Request) -> dict[str, Any]:
        handler = self._routes[(request.version, request.path)]
        pipeline = handler
        for middleware in reversed(self._middleware):
            pipeline = self._wrap_middleware(middleware, pipeline)
        payload = pipeline(request)
        return {
            "status": "ok",
            "version": request.version,
            "path": request.path,
            "data": payload,
            "errors": [],
        }

    @staticmethod
    def _wrap_middleware(middleware: Middleware, next_handler: Handler) -> Handler:
        def wrapped(request: Request) -> dict[str, Any]:
            return middleware(request, next_handler)

        return wrapped

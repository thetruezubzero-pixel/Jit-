"""Top-level orchestration for the Jit platform.

Wires the accounting, legal, and algorithms engines together behind a shared
event bus and audit trail, and exposes both a direct ``analyze_case`` call
and a versioned request/middleware pipeline via ``ApiGateway``.
"""

from __future__ import annotations

from typing import Any

from jit.accounting.engine import AccountingEngine
from jit.algorithms.engine import AlgorithmEngine
from jit.api.gateway import ApiGateway, Request
from jit.core.config import AppConfig
from jit.core.events import Event, EventBus
from jit.core.models import AnalysisContext, AuditRecord, SystemResponse
from jit.core.services import ServiceRegistry
from jit.legal.engine import LegalAnalysisEngine


class JitPlatform:
    def __init__(self, config: AppConfig | None = None) -> None:
        self.config = config or AppConfig()
        self.event_bus = EventBus()
        self.audit_trail: list[AuditRecord] = []
        self.services = ServiceRegistry()
        self.gateway = ApiGateway()
        self.event_bus.subscribe("*", self._capture_event)

        self.accounting = AccountingEngine(
            self.event_bus, self.config.module_rule_versions["accounting"]
        )
        self.legal = LegalAnalysisEngine(self.event_bus, self.config.module_rule_versions["legal"])
        self.algorithms = AlgorithmEngine(
            self.event_bus, self.config.module_rule_versions["algorithms"]
        )

        self.services.register("accounting", self.accounting)
        self.services.register("legal", self.legal)
        self.services.register("algorithms", self.algorithms)
        self.services.register("gateway", self.gateway)

        for version in self.config.api_versions:
            self.gateway.add_route(version, "/analyze", self._handle_analysis_request)
        self.gateway.add_middleware(self._audit_middleware)

    def _capture_event(self, event: Event) -> None:
        self.audit_trail.append(AuditRecord(topic=event.topic, payload=event.payload))

    def _audit_middleware(self, request: Request, handler: Any) -> dict[str, Any]:
        request.metadata["audit_enabled"] = self.config.feature_flags["audit_logging"]
        return handler(request)

    def analyze_case(self, context: AnalysisContext) -> SystemResponse:
        self.audit_trail.clear()
        standard_deduction = self.config.standard_deduction.get(context.filing_status, 14_600.0)
        accounting = self.accounting.analyze(context, standard_deduction)
        legal = self.legal.analyze(context, accounting)
        algorithms = self.algorithms.analyze(context, accounting, legal)
        return SystemResponse(
            success=True,
            data={
                "accounting": accounting.data,
                "legal": legal.data,
                "algorithms": algorithms.data,
                "services": list(self.services.names()),
            },
            audit_trail=list(self.audit_trail),
        )

    def handle_request(self, version: str, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        request = Request(version=version, path=path, payload=payload)
        return self.gateway.handle(request)

    def _handle_analysis_request(self, request: Request) -> dict[str, Any]:
        context = request.payload["context"]
        response = self.analyze_case(context)
        return {
            "success": response.success,
            "audit_events": [record.topic for record in response.audit_trail],
            "result": response.data,
            "metadata": request.metadata,
        }

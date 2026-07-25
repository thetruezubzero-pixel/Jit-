"""
adapter.py — the Jit service side of the federation protocol.

Exposes an ``APIRouter`` mounted by ``jit.api.main`` at ``/federation`` and a
module-level :class:`~jit.federation.protocol.AuditLedger` that other Jit code
can append to. The audit ledger is the tamper-evident record the forensic
matrix in the jfjf hub verifies.

Kept deliberately small: a federated service self-describes and keeps an
audit trail; all the learning/routing/forensics live in the hub.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Query

from jit.federation import hub_client, protocol
from jit.federation.protocol import (
    AuditLedger,
    Capability,
    ServiceManifest,
)

SERVICE_ID = "jit"

# Ledger file at the repo root (gitignored). One ledger per process.
_LEDGER_PATH = Path(__file__).resolve().parents[2] / ".federation_ledger.json"
ledger = AuditLedger(service_id=SERVICE_ID, path=_LEDGER_PATH)

router = APIRouter(prefix="/federation", tags=["Federation"])


def build_manifest(base_url: str = "http://localhost:8000") -> ServiceManifest:
    """Describe the Jit API's real capabilities to the federation hub."""
    return ServiceManifest(
        service_id=SERVICE_ID,
        display_name="Jit — Accounting & Legal Engine",
        kind="service",
        language="python",
        base_url=base_url,
        capabilities=[
            Capability(
                name="tax.calculate",
                method="POST",
                path="/api/v1/accounting/tax/calculate",
                description="Federal income tax calculation.",
                equivalence="compute",
            ),
            Capability(
                name="tax.optimize-deductions",
                method="POST",
                path="/api/v1/accounting/deductions/optimize",
                description="Deduction optimization.",
                equivalence="compute",
            ),
            Capability(
                name="platform.analyze-case",
                method="POST",
                path="/api/v1/platform/analyze",
                description="Full accounting -> legal -> algorithms pipeline.",
                equivalence="compute",
            ),
        ],
    )


def record(action: str, payload: dict[str, Any], actor: str = "") -> None:
    """Append a federation audit event, and forward it to the hub if one is
    configured. Safe to call from request handlers.

    The hub push is fire-and-forget: it only fires when FEDERATION_HUB_URL is
    set and an event loop is running, and it never blocks or raises here.
    """
    ledger.append(action, payload, actor=actor)
    if hub_client.enabled():
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        loop.create_task(hub_client.emit(f"service.{SERVICE_ID}", action, payload, SERVICE_ID))


async def announce() -> dict[str, Any]:
    """Register with the hub and emit a 'service.online' event, if configured.

    Called on startup. A no-op returning ``{"enabled": False}`` unless
    ``FEDERATION_HUB_URL`` is set, so default deployments are unaffected.
    """
    if not hub_client.enabled():
        return {"enabled": False}
    registered = await hub_client.register(build_manifest().to_dict())
    emitted = await hub_client.emit(
        f"service.{SERVICE_ID}", "service.online", {"service_id": SERVICE_ID}, SERVICE_ID
    )
    return {"enabled": True, "registered": registered, "emitted": emitted}


@router.get("/health")
async def federation_health() -> dict[str, Any]:
    """Federation liveness for this service + audit chain length."""
    return {
        "status": "ok",
        "service_id": SERVICE_ID,
        "federation_version": protocol.FEDERATION_VERSION,
        "audit_records": len(ledger),
        "secret_secure": not protocol.secret_is_insecure(),
    }


@router.get("/manifest")
async def federation_manifest() -> dict[str, Any]:
    """This service's federation manifest."""
    return build_manifest().to_dict()


@router.get("/audit")
async def federation_audit(limit: int = Query(200, ge=1, le=5000)) -> dict[str, Any]:
    """Export this service's tamper-evident audit chain for the hub."""
    return {
        "service": SERVICE_ID,
        "head": ledger.head(),
        "records": ledger.records(limit),
    }

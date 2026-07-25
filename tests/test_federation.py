"""
Tests for the Jit federation adapter.

Covers the tamper-evident audit ledger (pure, deterministic) and the
``/federation/*`` HTTP surface the Neural Swarm hub consumes.
"""

import httpx
import pytest
from httpx import ASGITransport, AsyncClient

from jit.api.main import app
from jit.federation import adapter, hub_client, protocol
from jit.federation.protocol import AuditLedger, verify_chain


@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


# -----------------------------------------------------------------------
# Ledger (tamper-evident chain)
# -----------------------------------------------------------------------
class TestAuditLedger:
    def test_appends_link_by_hash(self, tmp_path):
        led = AuditLedger(service_id="jit", path=tmp_path / "l.json")
        r0 = led.append("boot", {"n": 0})
        r1 = led.append("calc", {"n": 1})
        assert r0.prev_hash == protocol.GENESIS_PREV_HASH
        assert r1.prev_hash == r0.hash
        assert verify_chain(led.records())["intact"]

    def test_detects_tampering(self, tmp_path):
        led = AuditLedger(service_id="jit", path=tmp_path / "l.json")
        led.append("charge", {"amount": 10})
        led.append("charge", {"amount": 20})
        recs = led.records()
        recs[0]["payload"]["amount"] = 999
        report = verify_chain(recs)
        assert not report["intact"]
        assert report["first_break"]["seq"] == 0

    def test_persists_across_instances(self, tmp_path):
        path = tmp_path / "l.json"
        AuditLedger(service_id="jit", path=path).append("a", {})
        reopened = AuditLedger(service_id="jit", path=path)
        assert len(reopened) == 1


# -----------------------------------------------------------------------
# Federation HTTP surface
# -----------------------------------------------------------------------
class TestFederationEndpoints:
    async def test_health(self, client):
        response = await client.get("/federation/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["service_id"] == "jit"

    async def test_manifest_lists_capabilities(self, client):
        response = await client.get("/federation/manifest")
        assert response.status_code == 200
        data = response.json()
        assert data["service_id"] == "jit"
        names = {c["name"] for c in data["capabilities"]}
        assert "tax.calculate" in names

    async def test_audit_export_is_verifiable(self, client):
        response = await client.get("/federation/audit")
        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "jit"
        # Whatever the ledger currently holds must form an intact chain.
        assert verify_chain(data["records"])["intact"]


# -----------------------------------------------------------------------
# Outbound hub client (active participation)
# -----------------------------------------------------------------------
class TestHubClient:
    def test_disabled_by_default(self, monkeypatch):
        monkeypatch.delenv("FEDERATION_HUB_URL", raising=False)
        assert hub_client.enabled() is False
        # Disabled calls are safe no-ops, no network touched.

    async def test_disabled_calls_return_false(self, monkeypatch):
        monkeypatch.delenv("FEDERATION_HUB_URL", raising=False)
        assert await hub_client.register({"service_id": "jit"}) is False

    async def test_register_and_emit_hit_expected_endpoints(self, monkeypatch):
        monkeypatch.setenv("FEDERATION_HUB_URL", "http://hub.local")
        seen = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen.append((request.url.path, dict(request.url.params)))
            return httpx.Response(200, json={"ok": True})

        transport = httpx.MockTransport(handler)
        assert await hub_client.register({"service_id": "jit"}, transport=transport)
        assert await hub_client.emit("service.jit", "t", {"n": 1}, "jit", transport=transport)
        paths = [p for p, _ in seen]
        assert "/federation/register" in paths
        assert "/federation/bus/publish" in paths
        assert dict(seen[1][1])["source"] == "jit"

    async def test_announce_noop_when_disabled(self, monkeypatch):
        monkeypatch.delenv("FEDERATION_HUB_URL", raising=False)
        assert await adapter.announce() == {"enabled": False}

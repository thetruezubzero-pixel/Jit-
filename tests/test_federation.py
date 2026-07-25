"""
Tests for the Jit federation adapter.

Covers the tamper-evident audit ledger (pure, deterministic) and the
``/federation/*`` HTTP surface the Neural Swarm hub consumes.
"""

import pytest
from httpx import ASGITransport, AsyncClient

from jit.api.main import app
from jit.federation import protocol
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

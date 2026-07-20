"""Integration tests for the /api/v1/platform endpoint."""

import pytest
from httpx import ASGITransport, AsyncClient
from jit.api.main import app


@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


class TestPlatformAnalyzeEndpoint:
    async def test_analyze_case_runs_full_pipeline(self, client):
        response = await client.post(
            "/api/v1/platform/analyze",
            json={
                "case_id": "api-case-1",
                "filing_status": "single",
                "state": "CA",
                "incomes": [{"kind": "w2", "amount": 120000, "source": "Employer"}],
                "deductions": [{"name": "charity", "amount": 2000, "itemized": True}],
                "legal_documents": [
                    {
                        "title": "Contract",
                        "text": "Standard services agreement.",
                        "citations": [],
                    }
                ],
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert "accounting" in body["data"]
        assert "legal" in body["data"]
        assert "algorithms" in body["data"]
        assert body["data"]["accounting"]["gross_income"] == 120000
        assert [event["topic"] for event in body["audit_trail"]] == [
            "accounting.completed",
            "legal.completed",
            "algorithms.completed",
        ]

    async def test_analyze_case_defaults(self, client):
        response = await client.post("/api/v1/platform/analyze", json={"case_id": "api-case-2"})
        assert response.status_code == 200
        assert response.json()["success"] is True

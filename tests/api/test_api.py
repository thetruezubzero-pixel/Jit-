"""
Integration tests for the FastAPI endpoints.
"""

import pytest
from httpx import ASGITransport, AsyncClient
from jit.api.main import app


@pytest.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac


# -----------------------------------------------------------------------
# Health endpoint
# -----------------------------------------------------------------------

class TestHealthEndpoint:
    async def test_health_ok(self, client):
        """Health endpoint should return 200 OK."""
        response = await client.get("/health/")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"


# -----------------------------------------------------------------------
# Accounting endpoints
# -----------------------------------------------------------------------

class TestTaxCalculationEndpoint:
    async def test_basic_single_filer(self, client):
        """Single filer tax calculation should return valid response."""
        response = await client.post(
            "/api/v1/accounting/tax/calculate",
            json={
                "gross_income": 100_000,
                "filing_status": "single",
                "tax_year": 2024,
                "w2_wages": 100_000,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["gross_income"] == 100_000
        assert data["federal_income_tax"] > 0
        assert data["total_tax"] > 0

    async def test_mfj_filer(self, client):
        """MFJ filer should have higher standard deduction."""
        response = await client.post(
            "/api/v1/accounting/tax/calculate",
            json={
                "gross_income": 150_000,
                "filing_status": "married_filing_jointly",
                "tax_year": 2024,
                "w2_wages": 150_000,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "bracket_details" in data
        assert len(data["bracket_details"]) > 0

    async def test_invalid_filing_status_returns_422(self, client):
        """Invalid filing status should return 422."""
        response = await client.post(
            "/api/v1/accounting/tax/calculate",
            json={
                "gross_income": 50_000,
                "filing_status": "invalid_status",
            },
        )
        assert response.status_code == 422

    async def test_with_state_code(self, client):
        """CA state code should add state tax to result."""
        response = await client.post(
            "/api/v1/accounting/tax/calculate",
            json={
                "gross_income": 100_000,
                "filing_status": "single",
                "state_code": "CA",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["state_tax"] > 0

    async def test_recommendations_present(self, client):
        """Tax calculation should include recommendations."""
        response = await client.post(
            "/api/v1/accounting/tax/calculate",
            json={"gross_income": 75_000, "filing_status": "single"},
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data["recommendations"], list)


# -----------------------------------------------------------------------
# Legal endpoints
# -----------------------------------------------------------------------

class TestDocumentAnalysisEndpoint:
    async def test_basic_document_analysis(self, client):
        """Document analysis should return structured response."""
        response = await client.post(
            "/api/v1/legal/document/analyze",
            json={
                "text": (
                    "SECTION 1. This agreement includes an arbitration clause "
                    "and limitation of liability. See 26 U.S.C. § 61."
                ),
                "document_type": "contract",
                "title": "Test Contract",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "risk_score" in data
        assert "citation_count" in data
        assert data["citation_count"] >= 1

    async def test_invalid_document_type_returns_422(self, client):
        """Invalid document type should return 422."""
        response = await client.post(
            "/api/v1/legal/document/analyze",
            json={"text": "Some legal text here.", "document_type": "invalid_type"},
        )
        assert response.status_code == 422


class TestComplianceCheckEndpoint:
    async def test_basic_compliance_check(self, client):
        """Basic compliance check should return structured response."""
        response = await client.post(
            "/api/v1/legal/compliance/check",
            json={
                "gross_income": 100_000,
                "tax_year": 2024,
                "filing_status": "single",
                "taxes_withheld": 20_000,
                "taxes_paid": 0,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "compliance_score" in data
        assert "overall_risk" in data
        assert "is_compliant" in data

    async def test_fbar_issue_in_response(self, client):
        """FBAR issue should appear in response when threshold exceeded."""
        response = await client.post(
            "/api/v1/legal/compliance/check",
            json={
                "gross_income": 100_000,
                "tax_year": 2024,
                "filing_status": "single",
                "taxes_withheld": 20_000,
                "taxes_paid": 0,
                "has_foreign_accounts": True,
                "aggregate_foreign_balance": 100_000,
            },
        )
        assert response.status_code == 200
        data = response.json()
        # FBAR is a HIGH risk issue (not CRITICAL), so there should be issues present
        assert data["issue_count"] > 0
        assert data["high_count"] > 0
        fbar_issues = [i for i in data["issues"] if "fbar" in i["issue_id"]]
        assert len(fbar_issues) > 0


# -----------------------------------------------------------------------
# Algorithms endpoints
# -----------------------------------------------------------------------

class TestFilingStatusEndpoint:
    async def test_single_recommendation(self, client):
        """Single status recommendation."""
        response = await client.post(
            "/api/v1/algorithms/filing-status",
            json={"is_married": False, "has_qualifying_dependent": False,
                  "is_qualifying_surviving_spouse": False},
        )
        assert response.status_code == 200
        data = response.json()
        assert "SINGLE" in data["recommendation"].upper()

    async def test_hoh_recommendation(self, client):
        """HOH recommendation for unmarried with dependent."""
        response = await client.post(
            "/api/v1/algorithms/filing-status",
            json={"is_married": False, "has_qualifying_dependent": True,
                  "is_qualifying_surviving_spouse": False},
        )
        assert response.status_code == 200
        data = response.json()
        assert "HEAD" in data["recommendation"].upper()


class TestOptimizationEndpoint:
    async def test_optimization_returns_strategies(self, client):
        """Optimization endpoint should return at least one strategy."""
        response = await client.post(
            "/api/v1/algorithms/optimize",
            json={
                "gross_income": 120_000,
                "current_tax": 28_000,
                "marginal_rate": 0.24,
                "filing_status": "single",
                "has_401k_access": True,
                "current_401k_contribution": 5_000,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["strategy_count"] > 0
        assert data["total_savings"] >= 0


class TestRiskAssessmentEndpoint:
    async def test_risk_assessment_returns_profile(self, client):
        """Risk assessment should return a complete risk profile."""
        response = await client.post(
            "/api/v1/algorithms/risk/assess",
            json={
                "agi": 100_000,
                "has_schedule_c": True,
                "has_crypto_transactions": True,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "audit_risk_score" in data
        assert "overall_risk_rating" in data
        assert 0.0 <= data["estimated_audit_probability"] <= 1.0

"""Tests for the bundled frontend and request-logging middleware."""

import pytest
from httpx import ASGITransport, AsyncClient
from jit.api.main import app


@pytest.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test", follow_redirects=False
    ) as ac:
        yield ac


class TestFrontend:
    async def test_root_redirects_to_ui(self, client):
        response = await client.get("/")
        assert response.status_code == 307
        assert response.headers["location"] == "/ui/"

    async def test_ui_serves_index_html(self, client):
        response = await client.get("/ui/")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert "Jit" in response.text

    async def test_favicon_no_content(self, client):
        response = await client.get("/favicon.ico")
        assert response.status_code == 204


class TestRequestLoggingMiddleware:
    async def test_adds_request_id_and_timing_headers(self, client):
        response = await client.get("/health/")
        assert response.status_code == 200
        assert "x-request-id" in response.headers
        assert "x-process-time" in response.headers
        assert response.headers["x-process-time"].endswith("ms")

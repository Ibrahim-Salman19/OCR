"""
tests.test_playwright_api_client

Playwright Headless REST API testing using Playwright's APIRequestContext,
implementing best practices from testing-patterns/api-testing.md.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import APIRequestContext

pytestmark = pytest.mark.playwright


def test_api_health_endpoint(api_request_context: APIRequestContext) -> None:
    """Verifies GET /v1/health using Playwright APIRequestContext."""
    response = api_request_context.get("/v1/health")
    assert response.ok, f"Expected status 200, got {response.status}"
    assert response.status == 200

    data = response.json()
    assert data.get("status") == "healthy"
    assert "database" in data
    assert "storage_backend" in data
    assert "queue_backend" in data


def test_api_openapi_specification(api_request_context: APIRequestContext) -> None:
    """Verifies GET /openapi.json OpenAPI 3.x schema validity."""
    response = api_request_context.get("/openapi.json")
    assert response.ok
    assert response.status == 200

    schema = response.json()
    assert schema.get("openapi", "").startswith("3.")
    assert "info" in schema
    assert "paths" in schema
    assert "/v1/health" in schema["paths"]
    assert "/v1/ocr/jobs" in schema["paths"]


def test_api_job_status_not_found(api_request_context: APIRequestContext) -> None:
    """Verifies GET /v1/ocr/jobs/{job_id} returns 404 for non-existent job."""
    response = api_request_context.get("/v1/ocr/jobs/999999")
    assert response.status == 404
    detail = response.json().get("detail", "")
    assert "999999" in detail or "not found" in detail.lower()


def test_api_job_toc_not_found(api_request_context: APIRequestContext) -> None:
    """Verifies GET /v1/ocr/jobs/{job_id}/toc returns 404 for non-existent job."""
    response = api_request_context.get("/v1/ocr/jobs/999999/toc")
    assert response.status == 404


def test_api_job_chunks_not_found(api_request_context: APIRequestContext) -> None:
    """Verifies GET /v1/ocr/jobs/{job_id}/chunks returns 404 for non-existent job."""
    response = api_request_context.get("/v1/ocr/jobs/999999/chunks")
    assert response.status == 404


def test_api_invalid_payload_validation(api_request_context: APIRequestContext) -> None:
    """Verifies POST /v1/ocr/jobs without required file returns 400 or 422 error."""
    response = api_request_context.post("/v1/ocr/jobs", data={})
    assert response.status in (400, 422)

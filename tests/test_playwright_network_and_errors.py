"""
tests.test_playwright_network_and_errors

Advanced network interception, failure simulation, and error boundary testing
for B.L.A.S.T. OCR, implementing best practices from:
- advanced/network-advanced.md
- debugging/error-testing.md
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

pytestmark = pytest.mark.playwright


def test_swagger_ui_network_abort_handling(page: Page, fastapi_app_url: str) -> None:
    """Verifies that Swagger UI catches network dropouts and aborts gracefully without crashing."""
    # Intercept /v1/health and simulate network loss
    page.route("**/v1/health", lambda route: route.abort("failed"))

    page.goto(f"{fastapi_app_url}/docs", wait_until="networkidle")

    # Find and expand /v1/health
    health_op = page.locator(".opblock").filter(has_text="/v1/health").first
    health_op.wait_for(state="visible", timeout=8000)
    health_op.click()

    # Click Try it out
    try_btn = health_op.locator("button.try-out__btn")
    try_btn.wait_for(state="visible", timeout=5000)
    try_btn.click()

    # Click Execute
    exec_btn = health_op.locator("button.execute")
    exec_btn.wait_for(state="visible", timeout=5000)
    exec_btn.click()

    # Verify that Swagger UI handles the network abort cleanly
    error_indicator = health_op.locator(".response, .responses-inner, .highlight-code").first
    expect(error_indicator).to_be_visible(timeout=8000)
    error_text = error_indicator.inner_text().lower()
    assert "failed to fetch" in error_text or "error" in error_text or "undetermined" in error_text


def test_swagger_ui_injected_server_error(page: Page, fastapi_app_url: str) -> None:
    """Verifies that Swagger UI captures and renders simulated HTTP 500 server errors."""
    page.route(
        "**/v1/health",
        lambda route: route.fulfill(
            status=500,
            content_type="application/json",
            body='{"error": "Simulated Chaos Internal Server Error", "code": 500}',
        ),
    )

    page.goto(f"{fastapi_app_url}/docs", wait_until="networkidle")

    health_op = page.locator(".opblock").filter(has_text="/v1/health").first
    health_op.wait_for(state="visible", timeout=8000)
    health_op.click()

    try_btn = health_op.locator("button.try-out__btn")
    try_btn.wait_for(state="visible", timeout=5000)
    try_btn.click()

    exec_btn = health_op.locator("button.execute")
    exec_btn.wait_for(state="visible", timeout=5000)
    exec_btn.click()

    # Verify 500 response column appears
    status_col = health_op.locator(".response-col_status").filter(has_text="500").first
    expect(status_col).to_be_visible(timeout=8000)

    # Verify injected error body is displayed
    resp_body = health_op.locator(".response .highlight-code").first.inner_text()
    assert "Simulated Chaos Internal Server Error" in resp_body


def test_network_request_header_interception(page: Page, fastapi_app_url: str) -> None:
    """Verifies modifying request handling via Playwright route fulfillment."""
    intercept_events: list[bool] = []

    def intercept_route(route):
        intercept_events.append(True)
        route.fulfill(
            status=200,
            content_type="application/json",
            body='{"status": "healthy", "intercepted": true}',
            headers={"X-Intercepted-By": "Playwright-Route"},
        )

    page.route("**/v1/health", intercept_route)

    page.goto(f"{fastapi_app_url}/docs", wait_until="networkidle")
    health_op = page.locator(".opblock").filter(has_text="/v1/health").first
    health_op.click()
    health_op.locator("button.try-out__btn").click()
    health_op.locator("button.execute").click()

    # Wait for response
    status_col = health_op.locator(".response-col_status").filter(has_text="200").first
    expect(status_col).to_be_visible(timeout=8000)
    assert len(intercept_events) > 0
    resp_body = health_op.locator(".response .highlight-code").first.inner_text()
    assert "intercepted" in resp_body

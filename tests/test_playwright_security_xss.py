"""
tests.test_playwright_security_xss

Security testing and XSS injection prevention for B.L.A.S.T. OCR Sovereign Edition,
implementing best practices from testing-patterns/security-testing.md.

Verifies:
- Reflected XSS injection into UI search boxes is safely sanitized
- Filename-based stored XSS payloads do not execute script context in browser
- API responses enforce proper content-type encoding without dangerous MIME sniffing
"""

from __future__ import annotations

import pytest
from playwright.sync_api import APIRequestContext, Page, expect

from tests.playwright_fixtures import enter_mission_control, switch_tab

pytestmark = pytest.mark.playwright


def _setup_xss_detector(page: Page) -> None:
    """Installs XSS trap script on window object before navigation."""
    page.add_init_script(
        """
        window.__xssTriggered = false;
        window.alert = () => { window.__xssTriggered = true; };
        window.confirm = () => { window.__xssTriggered = true; return false; };
        window.prompt = () => { window.__xssTriggered = true; return null; };
        """
    )


def test_xss_prevention_in_audit_search(page: Page, streamlit_app_url: str) -> None:
    """Verifies that malicious script tags in audit trail search are neutralized without execution."""
    _setup_xss_detector(page)
    page.goto(streamlit_app_url, wait_until="networkidle")
    enter_mission_control(page)
    switch_tab(page, "SYSTEM AUDIT LOGS")

    search_input = page.get_by_placeholder("filename or timestamp")
    expect(search_input).to_be_visible()

    # Inject diverse XSS vectors
    xss_vectors = [
        '<script>window.__xssTriggered=true;</script>',
        '"><img src="invalid_path.jpg" onerror="window.__xssTriggered=true;">',
        "javascript:alert(1)",
    ]

    for vector in xss_vectors:
        search_input.fill(vector)
        search_input.press("Enter")
        page.wait_for_timeout(400)

        # Assert no script executed
        xss_fired = page.evaluate("() => window.__xssTriggered === true")
        assert not xss_fired, f"XSS payload executed via audit search: {vector}"

        # Assert safe zero-state rendered
        expect(page.get_by_text("No matching audit records.")).to_be_visible()


def test_xss_prevention_in_file_names(page: Page, streamlit_app_url: str) -> None:
    """Verifies that malicious script tags embedded in uploaded file names do not execute."""
    _setup_xss_detector(page)
    page.goto(streamlit_app_url, wait_until="networkidle")
    enter_mission_control(page)

    # Upload virtual in-memory file with XSS payload in filename
    page.locator('input[type="file"]').set_input_files(
        [
            {
                "name": "safe_document_<script>window.__xssTriggered=true</script>.txt",
                "mimeType": "text/plain",
                "buffer": b"Safe text content for OCR processing.",
            }
        ]
    )
    page.wait_for_timeout(1000)

    # Assert no script was triggered by DOM rendering
    xss_fired = page.evaluate("() => window.__xssTriggered === true")
    assert not xss_fired, "XSS executed from uploaded document file name"

    # Content of the DOM must not contain an unescaped executable script tag
    script_elements = page.evaluate(
        """() => {
            const scripts = Array.from(document.querySelectorAll('script'));
            return scripts.filter(s => s.textContent.includes('__xssTriggered')).length;
        }"""
    )
    assert script_elements == 0, "Found unescaped script tag injected into DOM"


def test_api_content_type_security(api_request_context: APIRequestContext) -> None:
    """Verifies that REST API endpoints return strict application/json content-type."""
    response = api_request_context.get("/v1/health")
    assert response.ok
    content_type = response.headers.get("content-type", "")
    assert "application/json" in content_type

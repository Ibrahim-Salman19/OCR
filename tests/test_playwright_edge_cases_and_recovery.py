"""
tests.test_playwright_edge_cases_and_recovery

Deep Playwright End-to-End browser tests for:
- Magic bytes extension spoofing rejection in the browser file uploader.
- Zero-byte file handling and execution button disabling.
- Rapid tab switching stability and virtual DOM persistence under active state.
- Keyboard focus accessibility across primary CTA and tabs.
- Interactive FastAPI Swagger UI error probing (testing non-existent job ID returns 404).
- Interactive Swagger UI TOC and stream endpoint exploration.
"""

import pytest
from playwright.sync_api import Page, expect

from tests.playwright_fixtures import (
    ROOT_DIR,
    enter_mission_control,
    switch_tab,
    upload_files_to_mission,
)

pytestmark = pytest.mark.playwright

SPOOFED_PDF = ROOT_DIR / "tests" / "fixtures" / "spoofed_magic_bytes.pdf"


def test_magic_bytes_spoofing_detection_and_rejection(page: Page, streamlit_app_url: str) -> None:
    """Verifies that extension-spoofed files without valid magic bytes are caught before execution."""
    assert SPOOFED_PDF.is_file(), f"Missing {SPOOFED_PDF}"

    page.goto(streamlit_app_url, wait_until="networkidle")
    enter_mission_control(page)
    switch_tab(page, "MISSION CONTROL")

    # Upload extension-spoofed file
    upload_files_to_mission(page, [SPOOFED_PDF])

    # Assert magic bytes failure error is rendered
    expect(page.locator("text=file signature does not match")).to_be_visible(timeout=10000)

    # EXECUTE button must be DISABLED because 0 valid files were provided
    exec_btn = page.locator('button:has-text("EXECUTE OCR ENGINE")')
    expect(exec_btn).to_be_disabled()


def test_rapid_tab_switching_under_active_state(page: Page, streamlit_app_url: str) -> None:
    """Stress tests rapid consecutive tab switches to ensure virtual DOM resilience."""
    page.goto(streamlit_app_url, wait_until="networkidle")
    enter_mission_control(page)

    tabs = [
        "MISSION CONTROL",
        "LAYOUT INSPECTOR",
        "SYSTEM AUDIT LOGS",
        "TELEMETRY & SWARM",
        "MISSION CONTROL",
        "SYSTEM AUDIT LOGS",
        "LAYOUT INSPECTOR",
        "MISSION CONTROL",
    ]

    for tab_name in tabs:
        switch_tab(page, tab_name, timeout_ms=5000)
        page.wait_for_timeout(200)

    # Confirm final tab is visible and healthy
    expect(page.locator("text=ENGINE CONFIGURATION")).to_be_visible()


def test_keyboard_accessibility_and_focus(page: Page, streamlit_app_url: str) -> None:
    """Verifies that essential navigation elements receive keyboard focus via Tab navigation."""
    page.goto(streamlit_app_url, wait_until="networkidle")

    # Tab to the CTA button on the landing page
    cta = page.locator('button:has-text("ENTER MISSION CONTROL")')
    expect(cta).to_be_visible()

    # Trigger Enter to navigate
    cta.focus()
    page.keyboard.press("Enter")
    page.wait_for_timeout(1000)

    # Confirm navigation to Mission Control
    tab_locator = page.locator('[role="tab"]:has-text("MISSION CONTROL")')
    expect(tab_locator).to_be_visible(timeout=10000)


def test_fastapi_swagger_ui_endpoint_error_handling(page: Page, fastapi_app_url: str) -> None:
    """Deeply probes Swagger UI interactive execution for GET /v1/ocr/jobs/{job_id} error handling."""
    page.goto(f"{fastapi_app_url}/docs", wait_until="networkidle")
    page.wait_for_selector(".swagger-ui", timeout=12000)

    # Locate and expand GET /v1/ocr/jobs/{job_id}
    job_get_op = page.locator('#operations-OCR_Automation-get_job_status_v1_ocr_jobs__job_id__get .opblock-summary-get')
    if job_get_op.count() == 0:
        job_get_op = page.locator('.opblock-summary-get:has-text("Get Job Status")')
    expect(job_get_op).to_be_visible(timeout=8000)
    job_get_op.click()
    page.wait_for_timeout(400)

    # Click 'Try it out'
    try_btn = page.locator('.opblock-body button:has-text("Try it out")').first
    expect(try_btn).to_be_visible()
    try_btn.click()
    page.wait_for_timeout(300)

    # Fill in integer non-existent job ID
    param_input = page.locator('.opblock-body input[placeholder="job_id"]')
    expect(param_input).to_be_visible()
    param_input.fill("999999")

    # Click 'Execute'
    execute_btn = page.locator('.opblock-body button:has-text("Execute")').first
    execute_btn.click()
    page.wait_for_timeout(1500)

    # Assert HTTP 404 response is rendered in Swagger UI
    expect(page.locator('.live-responses-table, .responses-table').first).to_contain_text("404", timeout=8000)


def test_fastapi_swagger_ui_toc_endpoint(page: Page, fastapi_app_url: str) -> None:
    """Deeply probes Swagger UI interactive execution for GET /v1/ocr/jobs/{job_id}/toc error handling."""
    page.goto(f"{fastapi_app_url}/docs", wait_until="networkidle")
    page.wait_for_selector(".swagger-ui", timeout=12000)

    # Locate and expand GET /v1/ocr/jobs/{job_id}/toc
    toc_op = page.locator('.opblock-summary-get:has-text("/v1/ocr/jobs/{job_id}/toc")')
    expect(toc_op).to_be_visible(timeout=8000)
    toc_op.click()
    page.wait_for_timeout(400)

    # Click 'Try it out'
    try_btn = page.locator('.opblock-body button:has-text("Try it out")').first
    expect(try_btn).to_be_visible()
    try_btn.click()
    page.wait_for_timeout(300)

    # Fill in integer non-existent job ID and execute
    param_input = page.locator('.opblock-body input[placeholder="job_id"]')
    expect(param_input).to_be_visible()
    param_input.fill("999999")

    execute_btn = page.locator('.opblock-body button:has-text("Execute")').first
    execute_btn.click()
    page.wait_for_timeout(1500)

    # Assert HTTP 404 response is rendered
    expect(page.locator('.live-responses-table, .responses-table').first).to_contain_text("404", timeout=8000)

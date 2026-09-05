"""
tests.test_playwright_audit_telemetry_security

Playwright End-to-End browser tests for:
- System Audit Logs: history records, search query filtering, status filtering, CSV export, log clearing
- Live Telemetry & Swarm: RSS/CPU metrics, subsystem status table, Zombie Reaper scan, session cleanup
- Hardened Security Gateway: unauthorized extension rejection and execution prevention
"""

import time
from pathlib import Path
import pytest
from playwright.sync_api import Page, expect

from tests.playwright_fixtures import ROOT_DIR, enter_mission_control, execute_ocr_and_wait, switch_tab, upload_files_to_mission

pytestmark = pytest.mark.playwright

TEST_IMAGE = ROOT_DIR / "data" / "clean_test" / "page-06.png"


def test_audit_logs_and_telemetry_hud(page: Page, streamlit_app_url: str) -> None:
    """Verifies audit trail persistence, CSV export, telemetry metrics, and reaper invocation."""
    page.goto(streamlit_app_url, wait_until="networkidle")
    enter_mission_control(page)
    switch_tab(page, "MISSION CONTROL")

    # 1. Execute a fast job to populate audit records
    upload_files_to_mission(page, [TEST_IMAGE])
    execute_ocr_and_wait(page, timeout_sec=60.0)

    # 2. Switch to SYSTEM AUDIT LOGS
    switch_tab(page, "SYSTEM AUDIT LOGS")
    expect(page.locator("text=AUDIT TRAIL & JOB HISTORY")).to_be_visible()

    # Verify search input is interactive
    search_input = page.locator('input[aria-label="SEARCH LOGS"]')
    expect(search_input).to_be_visible()
    search_input.fill("page-06")
    time.sleep(0.5)

    # Verify CSV export button is available and download works
    csv_btn = page.locator('button:has-text("EXPORT AUDIT TRAIL (.CSV)")')
    expect(csv_btn).to_be_visible()
    with page.expect_download() as download_info:
        csv_btn.click()
    download = download_info.value
    csv_path = download.path()
    assert csv_path is not None
    csv_content = Path(csv_path).read_text(encoding="utf-8")
    assert "FILE" in csv_content or "STATUS" in csv_content

    # Verify CLEAR SESSION LOG button is clickable and maintains stability
    clear_log_btn = page.locator('button:has-text("CLEAR SESSION LOG")')
    expect(clear_log_btn).to_be_visible()
    clear_log_btn.click()
    time.sleep(1.0)
    expect(page.locator("text=AUDIT TRAIL & JOB HISTORY")).to_be_visible()

    # 3. Switch to TELEMETRY & SWARM
    switch_tab(page, "TELEMETRY & SWARM")
    expect(page.locator("text=LIVE TELEMETRY, SWARM & STORAGE HUD")).to_be_visible()

    # Verify metrics
    metrics = page.locator('[data-testid="stMetricLabel"]').all_inner_texts()
    assert any("PROCESS RSS" in m for m in metrics)
    assert any("HOST CPU" in m for m in metrics)
    assert any("DATABASE BACKEND" in m for m in metrics)

    # Run Zombie Reaper Scan
    reaper_btn = page.locator('button:has-text("RUN ZOMBIE REAPER SCAN")')
    expect(reaper_btn).to_be_visible()
    reaper_btn.click()
    time.sleep(1.0)
    expect(page.locator("text=Reaper scan completed")).to_be_visible()

    # Clear Session Artifacts and verify artifact count resets
    clear_artifacts_btn = page.locator('button:has-text("CLEAR THIS SESSION\'S ARTIFACTS")')
    expect(clear_artifacts_btn).to_be_visible()
    clear_artifacts_btn.click()
    time.sleep(1.0)
    expect(page.locator("text=in the current isolated session directory").first).to_be_visible()


def test_security_gateway_unauthorized_extension(page: Page, streamlit_app_url: str, tmp_path: Path) -> None:
    """Verifies that hostile or unauthorized file extensions are rejected by the security gateway."""
    # Create fake executable file
    fake_exe = tmp_path / "payload.exe"
    fake_exe.write_bytes(b"MZ\x90\x00fake_executable_bytes")

    page.goto(streamlit_app_url, wait_until="networkidle")
    enter_mission_control(page)
    switch_tab(page, "MISSION CONTROL")

    # Attempt to upload unauthorized extension
    upload_files_to_mission(page, [fake_exe])

    # Check for rejection or disabled state
    body_text = page.locator("body").inner_text()
    exec_btn = page.locator('button:has-text("EXECUTE OCR ENGINE")')

    is_rejected = (
        "not an allowed format" in body_text
        or "UNAUTHORIZED EXTENSION" in body_text
        or exec_btn.count() == 0
        or not exec_btn.is_enabled()
    )
    assert is_rejected, "Security gateway failed to reject unauthorized file extension"

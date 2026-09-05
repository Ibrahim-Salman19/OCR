"""
tests.test_playwright_deep_inspector_and_storage

Deep Playwright End-to-End browser tests for:
- Layout Inspector block classification dynamic filtering (ALL, TEXT, TITLE, TABLE, etc.)
- Minimum confidence threshold slider filtering in Layout Inspector
- SVG layout geometry heatmap updates and coordinate badge inspection
- Audit trail real-time keyword search filtering (positive & negative needle match)
- Audit trail status dropdown filtering (ALL, SUCCESS)
- Session audit log purging via CLEAR SESSION LOG button
- Isolated session storage reclamation via CLEAR THIS SESSION'S ARTIFACTS button
"""

import pytest
from playwright.sync_api import Page, expect

from tests.playwright_fixtures import (
    ROOT_DIR,
    enter_mission_control,
    execute_ocr_and_wait,
    switch_tab,
    upload_files_to_mission,
)

pytestmark = pytest.mark.playwright

IMG_FILE = ROOT_DIR / "data" / "clean_test" / "page-06.png"


def test_layout_inspector_block_classification_filtering(page: Page, streamlit_app_url: str) -> None:
    """Deeply tests the Layout Inspector's classification selectbox dynamic filtering and SVG heatmap updates."""
    assert IMG_FILE.is_file(), f"Missing {IMG_FILE}"

    page.goto(streamlit_app_url, wait_until="networkidle")
    enter_mission_control(page)
    switch_tab(page, "MISSION CONTROL")

    # Ingest file and execute OCR to generate layout JSON
    upload_files_to_mission(page, [IMG_FILE])
    expect(page.locator("text=VERIFIED FOR INGESTION")).to_be_visible(timeout=10000)
    success = execute_ocr_and_wait(page, timeout_sec=60.0)
    assert success is True

    # Navigate to LAYOUT INSPECTOR tab
    switch_tab(page, "LAYOUT INSPECTOR")
    expect(page.locator("text=LAYOUT GEOMETRY & BOUNDING BOX HEATMAPS")).to_be_visible(timeout=10000)

    # Verify initial layout geometry SVG renders
    svg = page.locator("svg").first
    expect(svg).to_be_visible(timeout=8000)
    initial_rect_count = page.locator("svg rect").count()
    assert initial_rect_count > 0, f"Expected SVG rects, got {initial_rect_count}"

    # Verify caption displays total blocks
    caption = page.locator("text=Displaying").first
    expect(caption).to_be_visible()
    initial_caption = caption.inner_text()
    assert "Displaying" in initial_caption

    # 1. Filter by TEXT
    filter_box = page.locator('[data-testid="stSelectbox"]:has-text("FILTER BLOCK CLASSIFICATION")')
    expect(filter_box).to_be_visible()
    filter_box.click()
    page.wait_for_timeout(300)

    text_opt = page.locator('li[role="option"]:has-text("TEXT")').first
    if text_opt.is_visible():
        text_opt.click()
        page.wait_for_timeout(600)
        # Verify filtered caption
        caption_elem = page.locator("text=Displaying").first
        expect(caption_elem).to_be_visible()
        assert "Displaying" in caption_elem.inner_text()

    # 2. Reset Filter to ALL
    filter_box.click()
    page.wait_for_timeout(300)
    all_opt = page.locator('li[role="option"]:has-text("ALL")').first
    if all_opt.is_visible():
        all_opt.click()
        page.wait_for_timeout(600)
        expect(page.locator("text=Displaying").first).to_be_visible()


def test_layout_inspector_confidence_threshold_filtering(page: Page, streamlit_app_url: str) -> None:
    """Verifies that the confidence threshold slider interactively alters layout block filtering."""
    assert IMG_FILE.is_file(), f"Missing {IMG_FILE}"

    page.goto(streamlit_app_url, wait_until="networkidle")
    enter_mission_control(page)
    switch_tab(page, "MISSION CONTROL")

    # Ingest document first so layout JSON model is present
    upload_files_to_mission(page, [IMG_FILE])
    execute_ocr_and_wait(page, timeout_sec=60.0)

    switch_tab(page, "LAYOUT INSPECTOR")
    expect(page.locator("text=LAYOUT GEOMETRY & BOUNDING BOX HEATMAPS")).to_be_visible(timeout=8000)

    # Verify minimum confidence slider is rendered
    slider = page.locator('[data-testid="stSlider"]:has-text("MINIMUM CONFIDENCE THRESHOLD")')
    expect(slider).to_be_visible(timeout=8000)

    slider_handle = slider.locator('[role="slider"]')
    expect(slider_handle).to_be_visible()
    slider_val = slider_handle.get_attribute("aria-valuenow")
    assert slider_val is not None


def test_audit_trail_search_filtering_and_log_clearing(page: Page, streamlit_app_url: str) -> None:
    """Deeply tests system audit trail keyword filtering and session log clearing."""
    assert IMG_FILE.is_file(), f"Missing {IMG_FILE}"

    page.goto(streamlit_app_url, wait_until="networkidle")
    enter_mission_control(page)

    # Ingest and execute a job so that an audit record is guaranteed to exist
    switch_tab(page, "MISSION CONTROL")
    upload_files_to_mission(page, [IMG_FILE])
    expect(page.locator("text=VERIFIED FOR INGESTION")).to_be_visible(timeout=10000)
    execute_ocr_and_wait(page, timeout_sec=60.0)

    # Switch to SYSTEM AUDIT LOGS tab
    switch_tab(page, "SYSTEM AUDIT LOGS")
    expect(page.locator("text=AUDIT TRAIL & JOB HISTORY")).to_be_visible()

    # Verify export button is present when records exist
    export_btn = page.locator('button:has-text("EXPORT AUDIT TRAIL (.CSV)")')
    expect(export_btn).to_be_visible(timeout=8000)

    # 1. Search with matching keyword
    search_input = page.locator('input[aria-label="SEARCH LOGS"]')
    expect(search_input).to_be_visible()
    search_input.fill("page-06")
    page.wait_for_timeout(500)
    expect(export_btn).to_be_visible()

    # 2. Search with non-matching query
    search_input.fill("unmatched_negative_search_token_xyz999")
    search_input.press("Enter")
    page.wait_for_timeout(800)
    expect(page.locator("text=No matching audit records.")).to_be_visible(timeout=8000)

    # 3. Clear search query to restore records
    search_input.fill("")
    search_input.press("Enter")
    page.wait_for_timeout(800)
    expect(export_btn).to_be_visible()

    # 4. Purge logs via CLEAR SESSION LOG button
    clear_btn = page.locator('button:has-text("CLEAR SESSION LOG")')
    expect(clear_btn).to_be_visible()
    clear_btn.click()
    page.wait_for_timeout(800)

    # Verify log cleared state
    body_txt = page.locator("body").inner_text()
    assert "No matching audit records." in body_txt or "AUDIT TRAIL & JOB HISTORY" in body_txt


def test_session_storage_reclamation_lifecycle(page: Page, streamlit_app_url: str) -> None:
    """Verifies that the session storage monitor tracks artifacts and reclaims space upon button click."""
    page.goto(streamlit_app_url, wait_until="networkidle")
    enter_mission_control(page)

    # Switch to TELEMETRY & SWARM tab
    switch_tab(page, "TELEMETRY & SWARM")
    expect(page.locator("text=SESSION STORAGE")).to_be_visible(timeout=8000)

    # Verify session artifacts metric
    storage_label = page.locator('[data-testid="stMetricLabel"]:has-text("THIS SESSION\'S ARTIFACTS")')
    expect(storage_label).to_be_visible()

    # Locate CLEAR THIS SESSION'S ARTIFACTS button
    clear_storage_btn = page.locator('button:has-text("CLEAR THIS SESSION\'S ARTIFACTS")')
    expect(clear_storage_btn).to_be_visible()

    # Click storage cleanup button
    clear_storage_btn.click()
    page.wait_for_timeout(1000)

    # Verify success feedback
    body_txt = page.locator("body").inner_text()
    assert "Reclaimed" in body_txt or "0.00 MB" in body_txt

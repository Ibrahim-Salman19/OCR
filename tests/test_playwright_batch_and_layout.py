"""
tests.test_playwright_batch_and_layout

Playwright End-to-End browser tests for:
- Multi-document batch ingestion and parallel execution
- Batch ZIP bundle download and zip content integrity validation
- Per-document output tab cards
- Layout Inspector SVG heatmap and bounding box rendering
"""

import zipfile
import pytest
from playwright.sync_api import Page, expect

from tests.playwright_fixtures import ROOT_DIR, enter_mission_control, execute_ocr_and_wait, switch_tab, upload_files_to_mission

pytestmark = pytest.mark.playwright

IMG_1 = ROOT_DIR / "data" / "clean_test" / "page-06.png"
IMG_2 = ROOT_DIR / "data" / "clean_test" / "page-10.png"


def test_multi_document_batch_and_layout_inspector(page: Page, streamlit_app_url: str) -> None:
    """Verifies batch execution, ZIP archive integrity, and Layout Inspector SVG heatmaps."""
    assert IMG_1.is_file(), f"Test vector missing: {IMG_1}"
    assert IMG_2.is_file(), f"Test vector missing: {IMG_2}"

    page.goto(streamlit_app_url, wait_until="networkidle")
    enter_mission_control(page)
    switch_tab(page, "MISSION CONTROL")

    # 1. Multi-document upload
    upload_files_to_mission(page, [IMG_1, IMG_2])

    # 2. Batch verification confirmation
    expect(page.locator("text=VERIFIED FOR INGESTION: 2 file(s)")).to_be_visible(timeout=10000)

    # 3. Execute OCR Engine across batch
    success = execute_ocr_and_wait(page, timeout_sec=80.0)
    assert success is True, "Batch OCR execution failed to complete successfully"

    # 4. Verify batch summary and metrics
    expect(page.locator("text=PROCESSED ARTIFACTS")).to_be_visible()
    metrics = page.locator('[data-testid="stMetricLabel"]').all_inner_texts()
    assert any("DOCUMENTS" in m for m in metrics)
    assert any("PAGES DECODED" in m for m in metrics)

    # 5. Master batch archive download button
    batch_zip_btn = page.locator('button:has-text("DOWNLOAD COMPLETE BATCH ARCHIVE")')
    expect(batch_zip_btn).to_be_visible()

    # 6. Intercept ZIP download and verify internal files
    with page.expect_download() as download_info:
        batch_zip_btn.click()
    download = download_info.value
    download_path = download.path()
    assert download_path is not None

    with zipfile.ZipFile(download_path, "r") as archive:
        namelist = archive.namelist()
        assert len(namelist) >= 2, f"Expected at least 2 files in zip, got {namelist}"
        # Confirm artifacts from both files exist in the bundle
        assert any("page-06" in name for name in namelist)
        assert any("page-10" in name for name in namelist)

    # 7. Verify per-document tab cards exist
    expect(page.locator('[role="tab"]:has-text("page-06.png")')).to_be_visible()
    expect(page.locator('[role="tab"]:has-text("page-10.png")')).to_be_visible()

    # 8. Navigate to LAYOUT INSPECTOR tab
    switch_tab(page, "LAYOUT INSPECTOR")
    expect(page.locator("text=LAYOUT GEOMETRY & BOUNDING BOX HEATMAPS")).to_be_visible()

    # Verify selectbox for Document Model
    expect(page.locator("text=DOCUMENT MODEL")).to_be_visible()

    # Verify selectbox for Filter Block Classification
    expect(page.locator("text=FILTER BLOCK CLASSIFICATION")).to_be_visible()

    # Verify selectbox for Page
    expect(page.locator("text=SELECT PAGE TO INSPECT")).to_be_visible()

    # Verify SVG geometry element exists and has bounding box rects
    svg_locator = page.locator("svg")
    expect(svg_locator.first).to_be_visible(timeout=8000)
    rect_count = page.locator("svg rect").count()
    assert rect_count > 0, f"Expected SVG bounding box rectangles, found {rect_count}"

    # Verify block count caption is rendered
    expect(page.locator("text=Displaying")).to_be_visible()

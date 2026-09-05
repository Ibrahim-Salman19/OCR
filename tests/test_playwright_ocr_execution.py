"""
tests.test_playwright_ocr_execution

Playwright End-to-End browser tests for:
- Document upload and ingestion validation
- Live OCR execution with real-time progress monitoring
- Processed artifacts table and throughput metrics
- Exported format downloads (Markdown, DOCX, TXT, EPUB, PDF, JSON, Manifest)
- Interactive document preview tabs (Markdown, Raw Text, JSON)
"""

from pathlib import Path
import pytest
from playwright.sync_api import Page, expect

from tests.playwright_fixtures import ROOT_DIR, enter_mission_control, execute_ocr_and_wait, switch_tab, upload_files_to_mission

pytestmark = pytest.mark.playwright

TEST_IMAGE = ROOT_DIR / "data" / "clean_test" / "page-06.png"


def test_single_document_ocr_pipeline(page: Page, streamlit_app_url: str) -> None:
    """Verifies complete upload, OCR inference, metric updates, downloads, and preview tabs."""
    assert TEST_IMAGE.is_file(), f"Test image vector not found at {TEST_IMAGE}"

    page.goto(streamlit_app_url, wait_until="networkidle")
    enter_mission_control(page)
    switch_tab(page, "MISSION CONTROL")

    # 1. Ingestion upload
    upload_files_to_mission(page, [TEST_IMAGE])

    # 2. Verify ingestion confirmation
    expect(page.locator("text=VERIFIED FOR INGESTION")).to_be_visible(timeout=10000)
    exec_btn = page.locator('button:has-text("EXECUTE OCR ENGINE")')
    expect(exec_btn).to_be_visible()
    expect(exec_btn).to_be_enabled()

    # 3. Execute OCR and wait for completion
    success = execute_ocr_and_wait(page, timeout_sec=60.0)
    assert success is True, "OCR execution failed to complete successfully"

    # 4. Verify batch summary and throughput metrics
    expect(page.locator("text=PROCESSED ARTIFACTS")).to_be_visible()
    metrics = page.locator('[data-testid="stMetricLabel"]').all_inner_texts()
    assert any("DOCUMENTS" in m for m in metrics)
    assert any("PAGES DECODED" in m for m in metrics)

    # 5. Verify format download buttons
    download_buttons = [
        "DOWNLOAD MD",
        "DOWNLOAD DOCX",
        "DOWNLOAD TXT",
        "DOWNLOAD EPUB",
        "DOWNLOAD PDF",
        "DOWNLOAD MANIFEST",
        "DOWNLOAD JSON",
    ]
    for btn_label in download_buttons:
        expect(page.locator(f'button:has-text("{btn_label}")')).to_be_visible()

    # 6. Verify clicking download button and capturing real file payload via Playwright
    with page.expect_download() as download_info:
        page.locator('button:has-text("DOWNLOAD MD")').click()
    download = download_info.value
    download_path = download.path()
    assert download_path is not None
    content = Path(download_path).read_text(encoding="utf-8", errors="ignore")
    assert len(content) > 0, "Downloaded Markdown file is empty"

    # 7. Verify document preview tabs exist (RENDERED MARKDOWN, RAW TEXT, JSON STRUCTURE)
    preview_tabs = [
        "RENDERED MARKDOWN",
        "RAW TEXT",
        "JSON STRUCTURE",
    ]
    for p_tab in preview_tabs:
        expect(page.locator(f'[role="tab"]:has-text("{p_tab}")')).to_be_visible()

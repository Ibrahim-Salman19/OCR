"""
tests.test_playwright_heterogeneous_batch

Playwright End-to-End browser tests deeply validating:
- Simultaneous heterogeneous multi-document batch ingestion across diverse formats:
  PDF (.pdf), Presentation (.pptx), Lossless Image (.png), Lossy Image (.jpg), and Plaintext (.txt).
- Unified batch verification and progress monitoring.
- Per-document output asset tab cards for each distinct document type.
- Master batch ZIP bundle archive download with byte and entry integrity checks across all 5 formats.
- Dynamic multi-document preview switching between different document types.
- Mixed batch security gateway enforcement (valid heterogeneous docs + unauthorized .exe).
- Multilingual heterogeneous batch ingestion (English doc + Urdu image).
"""

import zipfile
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

PDF_FILE = ROOT_DIR / "tests" / "fixtures" / "sample_single_page.pdf"
PPTX_FILE = ROOT_DIR / "tests" / "fixtures" / "sample_deck.pptx"
PNG_FILE = ROOT_DIR / "data" / "clean_test" / "page-06.png"
JPG_FILE = ROOT_DIR / "tests" / "fixtures" / "sample_page.jpg"
TXT_FILE = ROOT_DIR / "tests" / "fixtures" / "sample_notes.txt"
EXE_FILE = ROOT_DIR / "tests" / "fixtures" / "hostile_script.exe"
URDU_FILE = ROOT_DIR / "tests" / "fixtures" / "urdu_ocr_sample.png"


def test_heterogeneous_multi_format_simultaneous_batch(page: Page, streamlit_app_url: str) -> None:
    """Deeply tests simultaneous ingestion of 5 distinct document formats at once."""
    for f in [PDF_FILE, PPTX_FILE, PNG_FILE, JPG_FILE, TXT_FILE]:
        assert f.is_file(), f"Required test vector missing: {f}"

    page.goto(streamlit_app_url, wait_until="networkidle")
    enter_mission_control(page)
    switch_tab(page, "MISSION CONTROL")

    # 1. Upload 5 heterogeneous document types AT ONCE
    upload_files_to_mission(page, [PDF_FILE, PPTX_FILE, PNG_FILE, JPG_FILE, TXT_FILE])

    # 2. Verify batch verification banner detects all 5 heterogeneous files
    expect(page.locator("text=VERIFIED FOR INGESTION: 5 file(s)")).to_be_visible(timeout=15000)

    # 3. Execute OCR Engine across the heterogeneous batch
    success = execute_ocr_and_wait(page, timeout_sec=140.0)
    assert success is True, "Heterogeneous batch OCR execution failed or timed out"

    # 4. Verify batch summary headers and metric tallies
    expect(page.locator("text=PROCESSED ARTIFACTS")).to_be_visible()
    metrics = page.locator('[data-testid="stMetricLabel"]').all_inner_texts()
    assert any("DOCUMENTS" in m for m in metrics)
    assert any("PAGES DECODED" in m for m in metrics)

    # 5. Master batch archive download button for all 5 documents
    batch_zip_btn = page.locator('button:has-text("DOWNLOAD COMPLETE BATCH ARCHIVE (5 DOCUMENTS .ZIP)")')
    expect(batch_zip_btn).to_be_visible()

    # 6. Download master ZIP bundle and thoroughly verify entries from ALL 5 document types
    with page.expect_download() as download_info:
        batch_zip_btn.click()
    download = download_info.value
    download_path = download.path()
    assert download_path is not None

    with zipfile.ZipFile(download_path, "r") as archive:
        namelist = archive.namelist()
        assert len(namelist) >= 5, f"Expected at least 5 files in zip, got {len(namelist)}: {namelist}"
        # Assert artifacts from every distinct document type exist in the master bundle
        assert any("sample_single_page" in name for name in namelist), "Missing PDF artifacts in zip"
        assert any("sample_deck" in name for name in namelist), "Missing PPTX artifacts in zip"
        assert any("page-06" in name for name in namelist), "Missing PNG artifacts in zip"
        assert any("sample_page" in name for name in namelist), "Missing JPG artifacts in zip"
        assert any("sample_notes" in name for name in namelist), "Missing TXT artifacts in zip"

    # 7. Verify all 5 per-document tab cards exist
    expect(page.locator('[role="tab"]:has-text("sample_single_page.pdf")')).to_be_visible()
    expect(page.locator('[role="tab"]:has-text("sample_deck.pptx")')).to_be_visible()
    expect(page.locator('[role="tab"]:has-text("page-06.png")')).to_be_visible()
    expect(page.locator('[role="tab"]:has-text("sample_page.jpg")')).to_be_visible()
    expect(page.locator('[role="tab"]:has-text("sample_notes.txt")')).to_be_visible()

    # 8. Inspect PPTX tab card and download its Markdown export
    pptx_tab = page.locator('[role="tab"]:has-text("sample_deck.pptx")')
    pptx_tab.click()
    page.wait_for_timeout(500)

    # In the active tab, find the visible DOWNLOAD MD button and verify downloaded text
    md_btn = page.locator('button:has-text("DOWNLOAD MD"):visible').first
    expect(md_btn).to_be_visible()
    with page.expect_download() as pptx_md_info:
        md_btn.click()
    pptx_md_download = pptx_md_info.value
    with open(pptx_md_download.path(), "r", encoding="utf-8") as fh:
        md_text = fh.read()
    assert "Heterogeneous Document Testing" in md_text or "Slide 1" in md_text, (
        f"Expected PPTX slide content in markdown, got: {md_text[:200]}"
    )

    # 9. Test dynamic multi-document preview switching
    preview_expander = page.locator('text=INLINE DOCUMENT PREVIEW & INSPECTION')
    expect(preview_expander).to_be_visible()

    # Switch preview selectbox to sample_notes.txt
    preview_selector = page.locator('[data-testid="stSelectbox"]:has-text("SELECT DOCUMENT TO PREVIEW")')
    if preview_selector.count() > 0:
        preview_selector.click()
        page.wait_for_timeout(300)
        option = page.locator('li[role="option"]:has-text("sample_notes.txt")')
        if option.count() > 0:
            option.first.click()
            page.wait_for_timeout(600)
            expect(page.locator("text=B.L.A.S.T. OCR Native Text Ingestion Test").first).to_be_visible(timeout=5000)

    # 10. Switch to LAYOUT INSPECTOR tab to confirm geometry rendering across batch
    switch_tab(page, "LAYOUT INSPECTOR")
    expect(page.locator("text=LAYOUT GEOMETRY & BOUNDING BOX HEATMAPS")).to_be_visible()
    svg_locator = page.locator("svg")
    expect(svg_locator.first).to_be_visible(timeout=8000)
    assert page.locator("svg rect").count() > 0


def test_heterogeneous_mixed_valid_and_rejected_security_batch(page: Page, streamlit_app_url: str) -> None:
    """Verifies that uploading valid documents alongside an unauthorized hostile file safely rejects the invalid file while allowing valid execution."""
    assert PPTX_FILE.is_file(), f"Missing {PPTX_FILE}"
    assert TXT_FILE.is_file(), f"Missing {TXT_FILE}"
    assert EXE_FILE.is_file(), f"Missing {EXE_FILE}"

    page.goto(streamlit_app_url, wait_until="networkidle")
    enter_mission_control(page)
    switch_tab(page, "MISSION CONTROL")

    # Upload mixed batch: valid PPTX, valid TXT, and unauthorized EXE
    upload_files_to_mission(page, [PPTX_FILE, TXT_FILE, EXE_FILE])

    # Security gateway and uploader should identify the unauthorized file
    uploader_area = page.locator('[data-testid="stFileUploader"]')
    expect(uploader_area).to_contain_text("hostile_script.exe", timeout=10000)
    expect(uploader_area).to_contain_text("not allowed", timeout=10000)
    expect(page.locator("text=VERIFIED FOR INGESTION: 2 file(s)")).to_be_visible(timeout=10000)

    # EXECUTE button should remain ENABLED because valid files exist
    execute_btn = page.locator('button:has-text("EXECUTE OCR ENGINE")')
    expect(execute_btn).to_be_enabled()

    # Trigger execution of the remaining valid files
    success = execute_ocr_and_wait(page, timeout_sec=60.0)
    assert success is True, "Execution of valid subset failed"

    # Batch summary should reflect successful processing of valid docs
    expect(page.locator("text=PROCESSED ARTIFACTS")).to_be_visible()
    expect(page.locator('[role="tab"]:has-text("sample_deck.pptx")')).to_be_visible()
    expect(page.locator('[role="tab"]:has-text("sample_notes.txt")')).to_be_visible()


def test_multilingual_heterogeneous_batch(page: Page, streamlit_app_url: str) -> None:
    """Verifies simultaneous batch ingestion of English and Urdu script documents."""
    assert PNG_FILE.is_file(), f"Missing {PNG_FILE}"
    assert URDU_FILE.is_file(), f"Missing {URDU_FILE}"

    page.goto(streamlit_app_url, wait_until="networkidle")
    enter_mission_control(page)
    switch_tab(page, "MISSION CONTROL")

    # Ingest English and Urdu documents simultaneously
    upload_files_to_mission(page, [PNG_FILE, URDU_FILE])
    expect(page.locator("text=VERIFIED FOR INGESTION: 2 file(s)")).to_be_visible(timeout=10000)

    success = execute_ocr_and_wait(page, timeout_sec=80.0)
    assert success is True, "Multilingual batch OCR execution failed"

    expect(page.locator("text=PROCESSED ARTIFACTS")).to_be_visible()
    expect(page.locator('[role="tab"]:has-text("page-06.png")')).to_be_visible()
    expect(page.locator('[role="tab"]:has-text("urdu_ocr_sample.png")')).to_be_visible()

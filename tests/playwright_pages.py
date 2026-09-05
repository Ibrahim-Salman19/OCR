"""
tests.playwright_pages

Page Object Model (POM) architecture for B.L.A.S.T. OCR Sovereign Edition
following Playwright Best Practices (currents.dev/playwright-best-practices).

Encapsulates UI interactions into cohesive, reusable page objects:
- MissionControlPage: landing hero, preset configuration, multi-file uploads, OCR execution, artifact downloads.
- LayoutInspectorPage: geometry heatmap, block classification selectbox filtering, confidence slider.
- AuditTrailPage: log querying, negative zero-state assertion, CSV export, session log purging.
- FastApiDocsPage: interactive Swagger UI and ReDoc navigation, execution, and HTTP response assertion.
- SovereignApp: unified entrypoint aggregating all page objects.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Sequence

from playwright.sync_api import Locator, Page, expect


class BasePage:
    """Base Page Object with common assertions and auto-waiting utilities."""

    def __init__(self, page: Page) -> None:
        self.page = page

    def wait_for_dom_stable(self, timeout_ms: int = 5000) -> None:
        """Waits for Streamlit script runner to settle into an idle state."""
        try:
            self.page.wait_for_selector(".stStatusWidget", state="hidden", timeout=timeout_ms)
        except Exception:
            pass


class MissionControlPage(BasePage):
    """Page Object for the Mission Control / OCR Studio tab."""

    def __init__(self, page: Page) -> None:
        super().__init__(page)
        # Semantic Locators
        self.hero_cta = page.get_by_role("button", name="ENTER MISSION CONTROL")
        self.mission_tab = page.get_by_role("tab", name="MISSION CONTROL")
        self.layout_tab = page.get_by_role("tab", name="LAYOUT INSPECTOR")
        self.audit_tab = page.get_by_role("tab", name="SYSTEM AUDIT LOGS")
        self.telemetry_tab = page.get_by_role("tab", name="TELEMETRY & SWARM")
        self.file_uploader_input = page.locator('input[type="file"]')
        self.execute_button = page.locator('button:has-text("EXECUTE OCR ENGINE")')
        self.radio_group = page.locator('[data-testid="stRadio"]')
        self.advanced_expander = page.locator('div[data-testid="stExpander"]:has-text("ADVANCED ENGINE PROTOCOLS")')

    def enter_console(self, timeout_ms: int = 15000) -> None:
        """Navigates past the landing hero into the active operations console."""
        if self.mission_tab.count() > 0 and self.mission_tab.first.is_visible():
            return

        self.hero_cta.wait_for(state="visible", timeout=timeout_ms)
        for _ in range(4):
            if self.hero_cta.count() > 0 and self.hero_cta.first.is_visible():
                self.hero_cta.first.click()
                try:
                    self.mission_tab.wait_for(state="visible", timeout=3000)
                    break
                except Exception:
                    pass
            else:
                break
        self.mission_tab.wait_for(state="visible", timeout=timeout_ms)
        self.wait_for_dom_stable()

    def select_preset(self, preset_label: str) -> None:
        """Selects an engine preset from the profile radio group."""
        self.enter_console()
        radio_item = self.radio_group.locator(f'label:has-text("{preset_label}")')
        radio_item.wait_for(state="visible", timeout=6000)
        radio_item.click()
        self.wait_for_dom_stable()

    def upload_files(self, file_paths: Sequence[str | Path]) -> None:
        """Uploads one or more documents through the file chooser."""
        self.enter_console()
        paths_str = [str(Path(p).resolve()) for p in file_paths]
        self.file_uploader_input.set_input_files(paths_str)
        try:
            self.page.wait_for_selector(
                '[data-testid="stFileUploadDropzone"], button:has-text("EXECUTE OCR ENGINE")',
                timeout=5000,
            )
        except Exception:
            pass
        self.wait_for_dom_stable()

    def execute_ocr(self, timeout_sec: float = 60.0) -> bool:
        """Clicks EXECUTE OCR ENGINE and auto-waits until completion or failure marker appears."""
        self.execute_button.wait_for(state="visible", timeout=10000)
        self.execute_button.click()

        start = time.monotonic()
        while (time.monotonic() - start) < timeout_sec:
            body = self.page.locator("body").inner_text()
            if any(marker in body for marker in ("PROCESSED ARTIFACTS", "BATCH COMPLETED", "PARTIAL BATCH COMPLETE", "DOWNLOAD MD")):
                return True
            if "MISSION FAILED" in body:
                return False
            time.sleep(0.5)

        raise TimeoutError(f"OCR execution did not complete within {timeout_sec}s")

    def get_download_button(self, format_name: str) -> Locator:
        """Returns the locator for a specific artifact download button."""
        return self.page.locator(f'button:has-text("DOWNLOAD {format_name.upper()}")')


class LayoutInspectorPage(BasePage):
    """Page Object for the Layout Geometry Inspector tab."""

    def __init__(self, page: Page) -> None:
        super().__init__(page)
        self.layout_tab = page.get_by_role("tab", name="LAYOUT INSPECTOR")
        self.svg_canvas = page.locator("svg")
        self.block_filter_select = page.get_by_label("Block Classification Filter")
        self.confidence_slider = page.locator('div[data-testid="stSlider"]:has-text("Min Confidence") input')

    def open(self) -> None:
        """Switches to the Layout Inspector tab."""
        self.layout_tab.wait_for(state="visible", timeout=8000)
        self.layout_tab.click()
        self.wait_for_dom_stable()

    def filter_blocks(self, classification: str) -> None:
        """Filters rendered bounding boxes by classification (e.g. ALL, TEXT, TITLE)."""
        self.block_filter_select.wait_for(state="visible", timeout=8000)
        self.block_filter_select.select_option(label=classification)
        self.wait_for_dom_stable()

    def get_svg_rectangles_count(self) -> int:
        """Returns the number of bounding box polygons rendered in the SVG inspector."""
        self.svg_canvas.wait_for(state="visible", timeout=10000)
        return self.page.locator("svg rect, svg polygon").count()


class AuditTrailPage(BasePage):
    """Page Object for the System Audit Logs tab."""

    def __init__(self, page: Page) -> None:
        super().__init__(page)
        self.audit_tab = page.get_by_role("tab", name="SYSTEM AUDIT LOGS")
        self.search_input = page.get_by_placeholder("filename or timestamp")
        self.clear_button = page.get_by_role("button", name="CLEAR SESSION LOG")
        self.download_csv_button = page.locator('button:has-text("DOWNLOAD AUDIT LOG (CSV)")')

    def open(self) -> None:
        """Switches to the System Audit Logs tab."""
        self.audit_tab.wait_for(state="visible", timeout=8000)
        self.audit_tab.click()
        self.wait_for_dom_stable()

    def filter_audit_log(self, query: str) -> None:
        """Applies a search query filter to the audit log."""
        self.search_input.wait_for(state="visible", timeout=6000)
        self.search_input.fill(query)
        self.search_input.press("Enter")
        self.wait_for_dom_stable()

    def clear_log(self) -> None:
        """Purges the current session audit records."""
        self.clear_button.wait_for(state="visible", timeout=6000)
        self.clear_button.click()
        self.wait_for_dom_stable()


class FastApiDocsPage(BasePage):
    """Page Object for FastAPI Interactive Swagger UI (/docs) and ReDoc (/redoc)."""

    def __init__(self, page: Page) -> None:
        super().__init__(page)

    def navigate_swagger(self, base_url: str) -> None:
        """Navigates to Swagger UI and awaits initialization."""
        self.page.goto(f"{base_url}/docs", wait_until="networkidle")
        self.page.locator(".swagger-ui").wait_for(state="visible", timeout=15000)

    def execute_operation(self, endpoint_text: str, expected_status: int = 200) -> Locator:
        """Expands an operation by endpoint pattern, clicks Try it out, Executes, and waits for response."""
        op_block = self.page.locator(".opblock").filter(has_text=endpoint_text).first
        op_block.wait_for(state="visible", timeout=10000)
        op_block.click()

        try_btn = op_block.locator("button.try-out__btn")
        try_btn.wait_for(state="visible", timeout=5000)
        try_btn.click()

        exec_btn = op_block.locator("button.execute")
        exec_btn.wait_for(state="visible", timeout=5000)
        exec_btn.click()

        response_status = op_block.locator(".response-col_status").filter(has_text=str(expected_status)).first
        response_status.wait_for(state="visible", timeout=12000)
        return response_status


class SovereignApp:
    """Unified application root encapsulating all Sovereign UI pages."""

    def __init__(self, page: Page, base_url: str) -> None:
        self.page = page
        self.base_url = base_url
        self.mission = MissionControlPage(page)
        self.layout = LayoutInspectorPage(page)
        self.audit = AuditTrailPage(page)
        self.docs = FastApiDocsPage(page)

    def goto(self) -> None:
        """Navigates to the root Streamlit application."""
        self.page.goto(self.base_url, wait_until="networkidle")
        self.page.wait_for_selector(".blast-landing-title", timeout=15000)
        expect(self.page.locator(".blast-landing-title")).to_be_visible()

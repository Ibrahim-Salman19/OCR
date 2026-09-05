"""
tests.test_playwright_pom

Page Object Model (POM) verified execution tests for B.L.A.S.T. OCR Sovereign Edition,
implementing best practices from core/page-object-model.md and architecture/pom-vs-fixtures.md.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

from tests.playwright_pages import FastApiDocsPage, SovereignApp

pytestmark = pytest.mark.playwright


def test_pom_landing_and_console_navigation(page: Page, streamlit_app_url: str) -> None:
    """Verifies landing and entering mission control using Page Object Model."""
    app = SovereignApp(page, streamlit_app_url)
    app.goto()

    # Verify hero CTA
    expect(app.mission.hero_cta).to_be_visible()

    # Enter operations console
    app.mission.enter_console()
    expect(app.mission.mission_tab).to_be_visible()
    expect(page.get_by_text("UPLOAD MISSION PAYLOAD")).to_be_visible()
    expect(app.mission.file_uploader_input).to_be_attached()


def test_pom_preset_selection(page: Page, streamlit_app_url: str) -> None:
    """Verifies profile preset selection using MissionControlPage object."""
    app = SovereignApp(page, streamlit_app_url)
    app.goto()
    app.mission.enter_console()

    app.mission.select_preset("RECEIPT / INVOICE")
    expect(app.mission.radio_group.locator('label:has-text("RECEIPT / INVOICE")')).to_be_visible()


def test_pom_audit_trail_search_and_clear(page: Page, streamlit_app_url: str) -> None:
    """Verifies audit trail navigation and interaction using AuditTrailPage object."""
    app = SovereignApp(page, streamlit_app_url)
    app.goto()
    app.mission.enter_console()

    # Open Audit Trail via POM
    app.audit.open()
    expect(app.audit.search_input).to_be_visible()

    # Filter by non-existent query to verify zero-state
    app.audit.filter_audit_log("QUERY_DEFINITELY_ABSENT_XYZ_987")
    expect(page.get_by_text("No matching audit records.")).to_be_visible()

    # Clear log via POM
    app.audit.clear_log()
    expect(page.get_by_text("No matching audit records.")).to_be_visible()


def test_pom_swagger_docs_execution(page: Page, fastapi_app_url: str) -> None:
    """Verifies interactive Swagger UI execution using FastApiDocsPage object."""
    docs = FastApiDocsPage(page)
    docs.navigate_swagger(fastapi_app_url)

    # Execute /v1/health via POM
    status_locator = docs.execute_operation(
        endpoint_text="/v1/health",
        expected_status=200,
    )
    expect(status_locator).to_be_visible()

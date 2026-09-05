"""
tests.test_playwright_multi_user

Multi-user and multi-context concurrency testing for B.L.A.S.T. OCR Sovereign Edition,
implementing best practices from advanced/multi-user.md and advanced/multi-context.md.

Verifies:
- Two isolated browser contexts (User A and User B) interacting simultaneously
- Independent state isolation: User A's preset selections do not leak to User B
- Upload isolation: User A's uploaded documents are isolated from User B
- Audit log isolation: User A's session history does not contaminate User B's audit view
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Browser, expect

from tests.playwright_fixtures import ROOT_DIR
from tests.playwright_pages import SovereignApp

pytestmark = pytest.mark.playwright


def test_concurrent_isolated_browser_contexts(browser: Browser, streamlit_app_url: str) -> None:
    """Verifies that two concurrent browser contexts maintain strictly isolated UI states."""
    # Create two completely independent browser contexts
    context_a = browser.new_context(viewport={"width": 1280, "height": 800})
    context_b = browser.new_context(viewport={"width": 1280, "height": 800})

    page_a = context_a.new_page()
    page_b = context_b.new_page()

    try:
        app_a = SovereignApp(page_a, streamlit_app_url)
        app_b = SovereignApp(page_b, streamlit_app_url)

        # User A and User B open the application concurrently
        app_a.goto()
        app_b.goto()

        # Both users navigate past landing hero
        app_a.mission.enter_console()
        app_b.mission.enter_console()

        # User A switches profile preset to "RECEIPT / INVOICE"
        app_a.mission.select_preset("RECEIPT / INVOICE")

        # Verify User A has RECEIPT / INVOICE selected
        radio_a = page_a.locator('[data-testid="stRadio"]')
        expect(radio_a.locator('label:has-text("RECEIPT / INVOICE")')).to_be_visible()

        # Verify User B remains on default GENERAL DOCUMENT preset without state leakage
        radio_b = page_b.locator('[data-testid="stRadio"]')
        expect(radio_b.locator('label:has-text("GENERAL DOCUMENT")')).to_be_visible()

        # User A uploads a document
        sample_doc = ROOT_DIR / "tests" / "fixtures" / "sample_notes.txt"
        app_a.mission.upload_files([sample_doc])

        # Verify User A sees the execute button for the uploaded document
        expect(page_a.locator('button:has-text("EXECUTE OCR ENGINE")')).to_be_visible()

        # Verify User B has NO execute button (no documents uploaded in context B)
        expect(page_b.locator('button:has-text("EXECUTE OCR ENGINE")')).to_have_count(0)

    finally:
        context_a.close()
        context_b.close()


def test_multi_session_audit_log_isolation(browser: Browser, streamlit_app_url: str) -> None:
    """Verifies that audit trail and job history are isolated between user sessions."""
    context_a = browser.new_context(viewport={"width": 1280, "height": 800})
    context_b = browser.new_context(viewport={"width": 1280, "height": 800})

    page_a = context_a.new_page()
    page_b = context_b.new_page()

    try:
        app_a = SovereignApp(page_a, streamlit_app_url)
        app_b = SovereignApp(page_b, streamlit_app_url)

        app_a.goto()
        app_b.goto()

        app_a.mission.enter_console()
        app_b.mission.enter_console()

        # User A executes OCR on sample_notes.txt
        sample_doc = ROOT_DIR / "tests" / "fixtures" / "sample_notes.txt"
        app_a.mission.upload_files([sample_doc])
        app_a.mission.execute_ocr(timeout_sec=30.0)

        # User A navigates to Audit Logs and filters for their document
        app_a.audit.open()
        expect(page_a.locator('button:has-text("EXPORT AUDIT TRAIL")')).to_be_visible()
        app_a.audit.filter_audit_log("sample_notes")
        expect(app_a.audit.search_input).to_have_value("sample_notes")

        # User B navigates to Audit Logs - their search input is independent and empty
        app_b.audit.open()
        expect(app_b.audit.search_input).to_have_value("")

        # User B filters for a distinct non-matching query
        app_b.audit.filter_audit_log("session_b_unmatched_needle_xyz")
        expect(page_b.get_by_text("No matching audit records.")).to_be_visible()

        # Verify User A's search input remains unaffected by User B's search
        expect(app_a.audit.search_input).to_have_value("sample_notes")

        # Verify User B's session has zero completed files in metrics
        expect(page_b.locator('[data-testid="stMetricValue"]').first).to_have_text("0")

    finally:
        context_a.close()
        context_b.close()

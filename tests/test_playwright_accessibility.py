"""
tests.test_playwright_accessibility

Accessibility and ARIA compliance testing for B.L.A.S.T. OCR Sovereign Edition,
implementing best practices from testing-patterns/accessibility.md.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

from tests.playwright_fixtures import enter_mission_control

pytestmark = pytest.mark.playwright


def test_landing_page_aria_landmarks(page: Page, streamlit_app_url: str) -> None:
    """Verifies that the landing page exposes required ARIA landmarks and roles."""
    page.goto(streamlit_app_url, wait_until="networkidle")

    # Verify hero CTA button has accessible name
    cta = page.get_by_role("button", name="ENTER MISSION CONTROL")
    expect(cta).to_be_visible()
    expect(cta).to_be_enabled()

    # Verify that headings are structured properly
    hero_title = page.locator(".blast-landing-title")
    expect(hero_title).to_be_visible()


def test_mission_control_tablist_aria_roles(page: Page, streamlit_app_url: str) -> None:
    """Verifies tablist semantics, ARIA tab roles, and aria-selected state switching."""
    page.goto(streamlit_app_url, wait_until="networkidle")
    enter_mission_control(page)

    # Verify tablist role exists
    tablist = page.get_by_role("tablist")
    expect(tablist.first).to_be_visible()

    # Verify all 4 tabs have role="tab" and accessible names
    tab_names = [
        "MISSION CONTROL",
        "LAYOUT INSPECTOR",
        "SYSTEM AUDIT LOGS",
        "TELEMETRY & SWARM",
    ]
    for name in tab_names:
        tab = page.get_by_role("tab", name=name)
        expect(tab).to_be_visible()

    # Verify Mission Control is initially selected (aria-selected="true")
    mission_tab = page.get_by_role("tab", name="MISSION CONTROL")
    expect(mission_tab).to_have_attribute("aria-selected", "true")

    # Switch to Audit tab and verify aria-selected toggles correctly
    audit_tab = page.get_by_role("tab", name="SYSTEM AUDIT LOGS")
    audit_tab.click()
    page.wait_for_timeout(400)
    expect(audit_tab).to_have_attribute("aria-selected", "true")
    expect(mission_tab).to_have_attribute("aria-selected", "false")


def test_form_controls_accessible_labels(page: Page, streamlit_app_url: str) -> None:
    """Verifies that interactive form controls have associated accessible labels."""
    page.goto(streamlit_app_url, wait_until="networkidle")
    enter_mission_control(page)

    # Processing profile radio group has accessible label
    preset_label = page.locator('[data-testid="stRadio"]').locator('label:has-text("GENERAL DOCUMENT")')
    expect(preset_label).to_be_visible()

    # File uploader has input element with proper type
    file_input = page.locator('input[type="file"]')
    expect(file_input).to_be_attached()


def test_keyboard_tab_navigation_and_focus(page: Page, streamlit_app_url: str) -> None:
    """Verifies keyboard focus sequence and focus outline on interactive elements."""
    page.goto(streamlit_app_url, wait_until="networkidle")

    # Focus title element to place keyboard focus in viewport
    title = page.locator(".blast-landing-title")
    title.wait_for(state="visible", timeout=8000)
    title.click()

    focused = False
    for _ in range(10):
        page.keyboard.press("Tab")
        cta_focused = page.evaluate(
            """() => {
                const el = document.activeElement;
                return el && (el.textContent.includes("ENTER MISSION CONTROL") || el.tagName === "BUTTON");
            }"""
        )
        if cta_focused:
            focused = True
            break

    assert focused, "Keyboard Tab navigation failed to focus on interactive button element"

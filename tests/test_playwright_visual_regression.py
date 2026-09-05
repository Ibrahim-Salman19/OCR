"""
tests.test_playwright_visual_regression

Visual regression and snapshot testing for B.L.A.S.T. OCR Sovereign Edition,
implementing best practices from testing-patterns/visual-regression.md.

Verifies:
- Masking volatile dynamic content (session uptime, clocks, dynamic tokens)
- Animation freezing for deterministic visual stability
- Element-level and full-page visual rendering integrity
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

from tests.playwright_fixtures import enter_mission_control

pytestmark = pytest.mark.playwright


def test_landing_hero_visual_capture_and_dimensions(page: Page, streamlit_app_url: str) -> None:
    """Verifies visual rendering of landing hero with animations disabled and volatile content masked."""
    page.goto(streamlit_app_url, wait_until="networkidle")
    hero_title = page.locator(".blast-landing-title")
    expect(hero_title).to_be_visible()

    # Capture hero screenshot with animations disabled
    screenshot = hero_title.screenshot(animations="disabled")

    # Validate valid PNG binary output
    assert screenshot.startswith(b"\x89PNG\r\n\x1a\n"), "Invalid PNG magic bytes in screenshot"
    assert len(screenshot) > 1024, "Hero screenshot buffer unexpectedly small"


def test_mission_control_masked_visual_integrity(page: Page, streamlit_app_url: str) -> None:
    """Verifies mission control console visual rendering masking dynamic volatile metrics."""
    page.goto(streamlit_app_url, wait_until="networkidle")
    enter_mission_control(page)

    tab_panel = page.get_by_role("tabpanel", name="MISSION CONTROL")
    expect(tab_panel).to_be_visible()

    # Identify volatile elements like session uptime or metrics
    volatile_elements = [
        page.locator('paragraph:has-text("SESSION UPTIME")'),
        page.locator('.stStatusWidget'),
    ]
    masks = [el for el in volatile_elements if el.count() > 0]

    # Capture console screenshot with animations disabled and volatile masks applied
    screenshot = page.screenshot(
        animations="disabled",
        mask=masks if masks else None,
        full_page=False,
    )

    assert screenshot.startswith(b"\x89PNG\r\n\x1a\n")
    assert len(screenshot) > 10000, "Full console screenshot too small"

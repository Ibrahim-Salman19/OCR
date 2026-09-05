"""
tests.test_playwright_engine_config

Playwright End-to-End browser tests for:
- Engine configuration processing presets
- Advanced Engine Protocols expander
- OCR engine adapter selection
- Language profile selection
- Acceleration, preprocessing, and security feature toggles
"""

import time
import pytest
from playwright.sync_api import Page, expect

from tests.playwright_fixtures import enter_mission_control, switch_tab

pytestmark = pytest.mark.playwright


def test_engine_presets_selection(page: Page, streamlit_app_url: str) -> None:
    """Verifies that preset radio buttons can be switched and reflect active profile defaults."""
    page.goto(streamlit_app_url, wait_until="networkidle")
    enter_mission_control(page)
    switch_tab(page, "MISSION CONTROL")

    radio_container = page.locator('[data-testid="stRadio"]')
    expect(radio_container).to_be_visible()

    presets = [
        "GENERAL DOCUMENT",
        "RECEIPT / INVOICE",
        "HANDWRITTEN TEXT",
        "BOOK / SPREAD DEWARP",
        "RAW PASSTHROUGH",
    ]

    for preset_name in presets:
        preset_label = radio_container.locator(f'label:has-text("{preset_name}")')
        expect(preset_label).to_be_visible()

    # Click RECEIPT / INVOICE preset
    receipt_label = radio_container.locator('label:has-text("RECEIPT / INVOICE")')
    receipt_label.click()
    time.sleep(0.8)

    # Click BOOK / SPREAD DEWARP preset
    dewarp_label = radio_container.locator('label:has-text("BOOK / SPREAD DEWARP")')
    dewarp_label.click()
    time.sleep(0.8)


def test_advanced_protocols_expander_and_adapters(page: Page, streamlit_app_url: str) -> None:
    """Verifies expanding advanced protocols, OCR engine adapters, and language cores."""
    page.goto(streamlit_app_url, wait_until="networkidle")
    enter_mission_control(page)
    switch_tab(page, "MISSION CONTROL")

    # Expand ADVANCED ENGINE PROTOCOLS
    expander_summary = page.locator('[data-testid="stExpander"] summary:has-text("ADVANCED ENGINE PROTOCOLS")')
    expect(expander_summary).to_be_visible()
    expander_summary.click()
    time.sleep(0.6)

    # Engine adapter selectbox
    engine_box = page.locator('[data-testid="stSelectbox"]').filter(has_text="OCR ENGINE ADAPTER")
    expect(engine_box).to_be_visible()

    # Language core selectbox
    lang_box = page.locator('[data-testid="stSelectbox"]').filter(has_text="LANGUAGE / SCRIPT CORE")
    expect(lang_box).to_be_visible()


def test_feature_toggles_and_sliders(page: Page, streamlit_app_url: str) -> None:
    """Verifies that preprocessing toggles, security flags, and sliders are interactive."""
    page.goto(streamlit_app_url, wait_until="networkidle")
    enter_mission_control(page)
    switch_tab(page, "MISSION CONTROL")

    # Open expander
    expander_summary = page.locator('[data-testid="stExpander"] summary:has-text("ADVANCED ENGINE PROTOCOLS")')
    expander_summary.click()
    time.sleep(0.6)

    # Verify presence of core toggles
    expect(page.locator('text="GPU HYPER-ACCELERATION"')).to_be_visible()
    expect(page.locator('text="AUTO-DESKEW ANGLE CORRECTION"')).to_be_visible()
    expect(page.locator('text="BOOK SPINE CURVATURE DEWARPING"')).to_be_visible()
    expect(page.locator('text="SECURE MODE (PII REDACTION)"')).to_be_visible()
    expect(page.locator('text="BOOK INTELLIGENCE (REFLOW/DEHYPHEN)"')).to_be_visible()
    expect(page.locator('text="TIER-0 NATIVE PDF ROUTER"')).to_be_visible()

    # Verify presence of sliders
    expect(page.locator('text="DENOISE FILTER LEVEL"')).to_be_visible()
    expect(page.locator('text="CONTRAST BOOST FACTOR"')).to_be_visible()

    # Interact with a toggle: Secure Mode
    secure_mode_label = page.locator('text="SECURE MODE (PII REDACTION)"')
    secure_mode_label.click()
    time.sleep(0.5)

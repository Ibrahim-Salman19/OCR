"""
tests.test_playwright_landing_and_nav

Playwright End-to-End browser tests for:
- Sovereign landing page hero, feature cards, and SEO/GEO meta tags
- Call-to-action transition into the console
- Sovereign header badges, real-time metrics, and tab navigation
"""

import pytest
from playwright.sync_api import Page, expect

from tests.playwright_fixtures import enter_mission_control, switch_tab

pytestmark = pytest.mark.playwright


def test_landing_page_hero_and_seo(page: Page, streamlit_app_url: str) -> None:
    """Verifies that the landing page renders hero elements, 4 feature cards, and SEO metadata."""
    page.goto(streamlit_app_url, wait_until="networkidle")
    page.wait_for_selector(".blast-landing-title", timeout=15000)

    # 1. Hero text and badge
    title = page.locator(".blast-landing-title")
    expect(title).to_be_visible()
    assert "B.L.A.S.T." in title.inner_text()
    assert "OCR" in title.inner_text()

    badge = page.locator(".blast-landing-badge")
    expect(badge).to_be_visible()
    assert "SOVEREIGN EDITION" in badge.inner_text()

    tagline = page.locator(".blast-landing-tagline")
    expect(tagline).to_be_visible()
    assert "Batched. Latency-Aware. Streaming. Text-extraction." in tagline.inner_text()

    # 2. Four core architectural feature cards
    cards = page.locator(".blast-feature-card")
    expect(cards).to_have_count(4)

    card_titles = [cards.nth(i).locator("h3").inner_text() for i in range(4)]
    assert "ONNX Multi-Provider Inference" in card_titles
    assert "Distributed Swarm Queue" in card_titles
    assert "Bounded Memory Streaming" in card_titles
    assert "Hardened Security Gateway" in card_titles

    # 3. Canonical SEO / GEO meta tags and Schema.org JSON-LD
    page_html = page.content()
    assert "Self-hosted ONNX OCR" in page_html
    assert "Python OCR" in page_html
    assert "B.L.A.S.T. OCR Engine" in page_html

    # 4. Primary CTA button
    cta = page.locator('button:has-text("ENTER MISSION CONTROL")')
    expect(cta).to_be_visible()
    expect(cta).to_be_enabled()


def test_landing_page_cta_transition(page: Page, streamlit_app_url: str) -> None:
    """Verifies that clicking ENTER MISSION CONTROL transitions to the operations console."""
    page.goto(streamlit_app_url, wait_until="networkidle")
    enter_mission_control(page)

    # Hero should no longer be rendered
    expect(page.locator(".blast-landing-title")).to_have_count(0)

    # Header title should now be visible
    header_title = page.locator(".blast-title")
    expect(header_title).to_be_visible()
    assert "B.L.A.S.T. OCR" in header_title.inner_text()

    # Subtitle
    subtitle = page.locator(".blast-subtitle")
    expect(subtitle).to_be_visible()
    assert "operations console" in subtitle.inner_text()


def test_header_status_badges_and_metrics(page: Page, streamlit_app_url: str) -> None:
    """Verifies that the app header displays live operational pills and resource counters."""
    page.goto(streamlit_app_url, wait_until="networkidle")
    enter_mission_control(page)

    # Badge row
    badge_row = page.locator(".blast-badge-row")
    expect(badge_row).to_be_visible()
    badge_text = badge_row.inner_text()

    assert "UI ONLINE" in badge_text
    assert "PIPELINE" in badge_text
    assert "DB" in badge_text

    # Top metrics (Files Completed, Pages Decoded, Wall Time, Session Uptime)
    metric_labels = page.locator('[data-testid="stMetricLabel"]').all_inner_texts()
    assert any("FILES COMPLETED" in m for m in metric_labels)
    assert any("PAGES DECODED" in m for m in metric_labels)
    assert any("LAST JOB WALL TIME" in m for m in metric_labels)
    assert any("SESSION UPTIME" in m for m in metric_labels)


def test_tab_navigation_and_panels(page: Page, streamlit_app_url: str) -> None:
    """Verifies that all four Sovereign tabs can be selected and display their respective panels."""
    page.goto(streamlit_app_url, wait_until="networkidle")
    enter_mission_control(page)

    # 1. MISSION CONTROL
    switch_tab(page, "MISSION CONTROL")
    expect(page.locator('text="ENGINE CONFIGURATION"')).to_be_visible()
    expect(page.locator('text="UPLOAD MISSION PAYLOAD"')).to_be_visible()

    # 2. LAYOUT INSPECTOR
    switch_tab(page, "LAYOUT INSPECTOR")
    expect(page.locator('text="LAYOUT GEOMETRY & BOUNDING BOX HEATMAPS"')).to_be_visible()

    # 3. SYSTEM AUDIT LOGS
    switch_tab(page, "SYSTEM AUDIT LOGS")
    expect(page.locator('text="AUDIT TRAIL & JOB HISTORY"')).to_be_visible()
    expect(page.locator('button:has-text("CLEAR SESSION LOG")')).to_be_visible()

    # 4. TELEMETRY & SWARM
    switch_tab(page, "TELEMETRY & SWARM")
    expect(page.locator('text="LIVE TELEMETRY, SWARM & STORAGE HUD"')).to_be_visible()
    expect(page.locator('text="PROCESS RSS"')).to_be_visible()
    expect(page.locator('text="DATABASE BACKEND"')).to_be_visible()
    expect(page.locator('button:has-text("RUN ZOMBIE REAPER SCAN")')).to_be_visible()
    expect(page.locator('button:has-text("CLEAR THIS SESSION\'S ARTIFACTS")')).to_be_visible()

    # Return to MISSION CONTROL
    switch_tab(page, "MISSION CONTROL")
    expect(page.locator('text="UPLOAD MISSION PAYLOAD"')).to_be_visible()

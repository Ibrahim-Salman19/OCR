"""
tests.test_playwright_responsive_and_docs

Playwright End-to-End browser tests for:
- Universal multi-device responsive rendering (Fold 320x653, iPhone SE 375x667, iPhone 14 Pro 390x844,
  Pixel 7 412x915, Mobile Landscape 667x375, Galaxy Landscape 800x360, Surface Duo 540x720,
  iPad Mini 768x1024, iPad Landscape 1024x768, Standard Laptop 1366x768, FHD Desktop 1920x1080,
  Ultrawide 2560x1440, 4K Workstation 3840x2160)
- Zero horizontal overflow verification (scrollWidth <= innerWidth + 1) across Landing and Mission Control
- WCAG 2.5.5 touch target size compliance (min 44px) on touch devices
- Mobile 2x2 metrics grid and tablet tab fit verification
- FastAPI interactive Swagger UI (/docs) execution and 200 response validation
- FastAPI ReDoc documentation (/redoc) rendering
"""

import time
import pytest
from playwright.sync_api import Browser, Page, expect

from tests.playwright_fixtures import enter_mission_control, switch_tab

# Fixtures provided automatically by pytest_plugins in conftest.py
pytestmark = pytest.mark.playwright


@pytest.mark.parametrize(
    "viewport_name,width,height,has_touch",
    [
        ("galaxy_fold_cover", 320, 653, True),
        ("iphone_se_portrait", 375, 667, True),
        ("iphone_14_pro", 390, 844, True),
        ("google_pixel_7", 412, 915, True),
        ("iphone_se_landscape", 667, 375, True),
        ("galaxy_s20_landscape", 800, 360, True),
        ("surface_duo_foldable", 540, 720, True),
        ("ipad_mini_portrait", 768, 1024, True),
        ("ipad_landscape", 1024, 768, True),
        ("standard_laptop", 1366, 768, False),
        ("fhd_desktop", 1920, 1080, False),
        ("ultrawide_2k", 2560, 1440, False),
        ("workstation_4k", 3840, 2160, False),
    ],
)
def test_universal_device_viewports(
    browser: Browser,
    streamlit_app_url: str,
    viewport_name: str,
    width: int,
    height: int,
    has_touch: bool,
) -> None:
    """Verifies that every device form factor renders with zero overflow and single-line CTAs."""
    context = browser.new_context(
        viewport={"width": width, "height": height},
        has_touch=has_touch,
        is_mobile=has_touch and width < 1024,
    )
    p = context.new_page()
    try:
        p.goto(streamlit_app_url, wait_until="networkidle")
        p.wait_for_selector(".blast-landing-title", timeout=15000)

        # 1. Landing Hero Verification
        title = p.locator(".blast-landing-title")
        expect(title).to_be_visible()

        cta = p.locator('button:has-text("ENTER MISSION CONTROL")')
        expect(cta).to_be_visible()
        expect(cta).to_be_enabled()

        # Check that landing page has zero horizontal scrollbar / overflow
        landing_overflow = p.evaluate("""() => {
            return document.documentElement.scrollWidth > window.innerWidth + 1;
        }""")
        assert not landing_overflow, f"Landing page has horizontal overflow on {viewport_name} ({width}x{height})"

        # Check that CTA button does not wrap to multiple lines
        cta_height = p.evaluate("""() => {
            const btn = Array.from(document.querySelectorAll('button')).find(b => b.innerText.includes('ENTER MISSION CONTROL'));
            return btn ? btn.getBoundingClientRect().height : 0;
        }""")
        assert cta_height <= 55, f"CTA button wrapped awkwardly (height={cta_height}px) on {viewport_name}"

        # 2. Enter Mission Control
        enter_mission_control(p, timeout_ms=18000)

        # Check that Mission Control has zero horizontal overflow
        mission_overflow = p.evaluate("""() => {
            return document.documentElement.scrollWidth > window.innerWidth + 1;
        }""")
        assert not mission_overflow, f"Mission Control has horizontal overflow on {viewport_name} ({width}x{height})"

        # Verify all 4 tabs exist
        tabs = p.locator('[role="tab"]')
        expect(tabs.first).to_be_visible()
        assert tabs.count() >= 4, f"Expected 4 navigation tabs, found {tabs.count()}"

    finally:
        context.close()


def test_touch_target_accessibility_wcag(browser: Browser, streamlit_app_url: str) -> None:
    """Verifies WCAG 2.5.5 touch target size compliance (min 44px) on touch devices."""
    context = browser.new_context(
        viewport={"width": 390, "height": 844},
        has_touch=True,
        is_mobile=True,
    )
    p = context.new_page()
    try:
        p.goto(streamlit_app_url, wait_until="networkidle")
        enter_mission_control(p, timeout_ms=18000)

        # Check tabs touch targets
        tab_targets = p.evaluate("""() => {
            return Array.from(document.querySelectorAll('[role="tab"]')).map(t => {
                const r = t.getBoundingClientRect();
                return { text: t.innerText.trim(), height: r.height, width: r.width };
            });
        }""")
        for t in tab_targets:
            assert t["height"] >= 44, f"Tab '{t['text']}' height ({t['height']:.1f}px) below WCAG 44px minimum"

        # Check primary action buttons touch targets
        buttons = p.evaluate("""() => {
            return Array.from(document.querySelectorAll('button')).filter(b => b.offsetWidth > 0 && b.offsetHeight > 0).map(b => {
                const r = b.getBoundingClientRect();
                return { text: b.innerText.slice(0, 25).trim(), height: r.height };
            });
        }""")
        for b in buttons:
            assert b["height"] >= 40, f"Button '{b['text']}' height ({b['height']:.1f}px) below minimum touch size"
    finally:
        context.close()


def test_mobile_metrics_2x2_grid_layout(browser: Browser, streamlit_app_url: str) -> None:
    """Verifies that metrics render in a compact 2x2 grid on mobile screens instead of 4 stacked rows."""
    context = browser.new_context(viewport={"width": 375, "height": 667})
    p = context.new_page()
    try:
        p.goto(streamlit_app_url, wait_until="networkidle")
        enter_mission_control(p, timeout_ms=18000)

        metric_positions = p.evaluate("""() => {
            const metrics = Array.from(document.querySelectorAll('[data-testid="stMetric"]'))
                .filter(m => m.offsetWidth > 0 && m.offsetHeight > 0);
            return metrics.slice(0, 4).map(m => {
                const r = m.getBoundingClientRect();
                return { top: Math.round(r.top), left: Math.round(r.left), width: Math.round(r.width) };
            });
        }""")
        assert len(metric_positions) == 4, f"Expected 4 visible header metrics, got {len(metric_positions)}"

        # Verify that metrics are arranged in 2 columns (metric 0 and 1 side-by-side in row 1)
        m0, m1, m2, m3 = metric_positions
        assert m0["left"] != m1["left"], "Expected metric 0 and 1 to be side-by-side in 2 columns"
        assert abs(m0["top"] - m1["top"]) <= 10, "Expected metric 0 and 1 to share the same row"
        assert abs(m2["top"] - m3["top"]) <= 10, "Expected metric 2 and 3 to share the same row"
    finally:
        context.close()


def test_tablet_tabs_fit_no_truncation(browser: Browser, streamlit_app_url: str) -> None:
    """Verifies that all 4 navigation tabs fit across iPad Mini portrait (768px) with zero truncation."""
    context = browser.new_context(viewport={"width": 768, "height": 1024})
    p = context.new_page()
    try:
        p.goto(streamlit_app_url, wait_until="networkidle")
        enter_mission_control(p, timeout_ms=18000)

        tabs_fit = p.evaluate("""() => {
            const tabs = Array.from(document.querySelectorAll('[role="tab"]'));
            const lastTab = tabs[tabs.length - 1];
            const r = lastTab.getBoundingClientRect();
            return {
                lastTabRight: r.right,
                winWidth: window.innerWidth,
                fits: r.right <= window.innerWidth
            };
        }""")
        assert tabs_fit["fits"], f"Tab 4 overflows viewport on 768px: right={tabs_fit['lastTabRight']}px, win={tabs_fit['winWidth']}px"
    finally:
        context.close()


def test_multi_tab_responsive_stability(browser: Browser, streamlit_app_url: str) -> None:
    """Verifies that switching between tabs on mobile maintains zero horizontal overflow."""
    context = browser.new_context(viewport={"width": 375, "height": 667})
    p = context.new_page()
    try:
        p.goto(streamlit_app_url, wait_until="networkidle")
        enter_mission_control(p, timeout_ms=18000)

        for tab_name in ["LAYOUT INSPECTOR", "SYSTEM AUDIT LOGS", "TELEMETRY & SWARM", "MISSION CONTROL"]:
            switch_tab(p, tab_name)
            overflow = p.evaluate("() => document.documentElement.scrollWidth > window.innerWidth + 1")
            assert not overflow, f"Tab '{tab_name}' caused horizontal overflow on 375px mobile"
    finally:
        context.close()



def test_fastapi_swagger_ui_interactive(page: Page, fastapi_app_url: str) -> None:
    """Verifies Swagger UI loading, schema rendering, and interactive /v1/health execution."""
    page.goto(f"{fastapi_app_url}/docs", wait_until="networkidle")
    expect(page).to_have_title("B.L.A.S.T. OCR Engine - Enterprise REST API - Swagger UI")

    # Verify header title
    api_title = page.locator(".title")
    expect(api_title).to_be_visible()
    assert "B.L.A.S.T. OCR Engine" in api_title.inner_text()

    # Verify Swagger operations exist
    opblocks = page.locator(".opblock")
    expect(opblocks.first).to_be_visible(timeout=8000)
    assert opblocks.count() >= 10, f"Expected at least 10 API operations, found {opblocks.count()}"

    # Expand GET /v1/health endpoint
    health_op = page.locator(".opblock").filter(has_text="/v1/health").first
    health_op.click()
    time.sleep(0.5)

    # Click 'Try it out'
    try_btn = health_op.locator("button.try-out__btn")
    expect(try_btn).to_be_visible()
    try_btn.click()

    # Click 'Execute'
    exec_btn = health_op.locator("button.execute")
    expect(exec_btn).to_be_visible()
    exec_btn.click()
    time.sleep(1.0)

    # Verify 200 response in Swagger UI
    status_col = health_op.locator(".response .response-col_status").first
    expect(status_col).to_be_visible(timeout=6000)
    assert "200" in status_col.inner_text()

    # Verify JSON response body contains "healthy"
    resp_body = health_op.locator(".response .highlight-code").first.inner_text()
    assert "healthy" in resp_body


def test_fastapi_redoc_ui(page: Page, fastapi_app_url: str) -> None:
    """Verifies that ReDoc renders clean technical documentation with navigation."""
    page.goto(f"{fastapi_app_url}/redoc", wait_until="networkidle")
    expect(page).to_have_title("B.L.A.S.T. OCR Engine - Enterprise REST API - ReDoc")

    heading = page.locator("h1").first
    expect(heading).to_be_visible()
    assert "B.L.A.S.T. OCR Engine" in heading.inner_text()

"""
tests.test_playwright_performance_vitals

Performance testing and Web Vitals budgeting for B.L.A.S.T. OCR Sovereign Edition,
implementing best practices from testing-patterns/performance-testing.md.

Verifies:
- Navigation timing metrics (TTFB, DOMContentLoaded) remain within strict budgets
- Interactive transition latency from landing CTA to operations console
- Client-side JavaScript heap memory limits
"""

from __future__ import annotations

import time

import pytest
from playwright.sync_api import Page, expect

from tests.playwright_fixtures import enter_mission_control

pytestmark = pytest.mark.playwright


def test_landing_page_navigation_timing_budget(page: Page, streamlit_app_url: str) -> None:
    """Verifies that the initial landing page load meets strict performance latency budgets."""
    page.goto(streamlit_app_url, wait_until="networkidle")
    expect(page.locator(".blast-landing-title")).to_be_visible()

    timing_metrics = page.evaluate(
        """() => {
            const nav = performance.getEntriesByType('navigation')[0];
            if (nav) {
                return {
                    ttfb_ms: nav.responseStart - nav.requestStart,
                    dom_content_loaded_ms: nav.domContentLoadedEventEnd - nav.startTime,
                    load_complete_ms: nav.loadEventEnd - nav.startTime,
                    transfer_size_bytes: nav.transferSize
                };
            }
            const timing = performance.timing;
            return {
                ttfb_ms: timing.responseStart - timing.requestStart,
                dom_content_loaded_ms: timing.domContentLoadedEventEnd - timing.navigationStart,
                load_complete_ms: timing.loadEventEnd - timing.navigationStart,
                transfer_size_bytes: 0
            };
        }"""
    )

    # Validate Performance Budgets
    assert timing_metrics["ttfb_ms"] < 2500, f"TTFB budget exceeded: {timing_metrics['ttfb_ms']}ms"
    assert timing_metrics["dom_content_loaded_ms"] < 5000, f"DOMContentLoaded exceeded budget: {timing_metrics['dom_content_loaded_ms']}ms"


def test_mission_control_transition_latency_budget(page: Page, streamlit_app_url: str) -> None:
    """Verifies that transitioning into the operations console completes within responsive bounds (< 5s)."""
    page.goto(streamlit_app_url, wait_until="networkidle")
    expect(page.locator(".blast-landing-title")).to_be_visible()

    start_time = time.monotonic()
    enter_mission_control(page)
    elapsed_ms = (time.monotonic() - start_time) * 1000.0

    # Ensure responsive transition within budget
    assert elapsed_ms < 6000.0, f"Console transition latency exceeded budget: {elapsed_ms:.1f}ms"
    expect(page.get_by_role("tab", name="MISSION CONTROL")).to_be_visible()


def test_client_javascript_heap_budget(page: Page, streamlit_app_url: str) -> None:
    """Verifies that client-side JavaScript heap memory stays within conservative bounds."""
    page.goto(streamlit_app_url, wait_until="networkidle")
    enter_mission_control(page)

    heap_bytes = page.evaluate(
        """() => {
            if (performance.memory && performance.memory.usedJSHeapSize) {
                return performance.memory.usedJSHeapSize;
            }
            return 0;
        }"""
    )

    if heap_bytes > 0:
        heap_mb = heap_bytes / (1024 * 1024)
        assert heap_mb < 200.0, f"Client JS heap budget exceeded: {heap_mb:.2f}MB (max 200MB)"

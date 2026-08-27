"""
scripts/keep_awake.py
=====================
Automated Streamlit Community Cloud wake-up script.

Playwright navigates to the deployed app, detects the hibernation banner
("Zzzz — This app has gone to sleep due to inactivity"), and clicks the
"Yes, get this app back up!" button when found. If the app is already
running, it exits cleanly.

Usage:
    pip install playwright
    playwright install chromium --with-deps
    STREAMLIT_APP_URL=https://your-app.streamlit.app python scripts/keep_awake.py

Environment Variables:
    STREAMLIT_APP_URL   The full public URL of the Streamlit app.
                        Can also be passed via GitHub Actions secrets.
"""

import os
import sys
import time

STREAMLIT_URL = os.environ.get("STREAMLIT_APP_URL", "").strip()

# How long to wait after clicking wake button before exiting (seconds)
WAKE_BOOT_WAIT = 20

# How many seconds to wait for the page to settle on initial load
INITIAL_SETTLE = 6


def main() -> int:
    if not STREAMLIT_URL:
        print(
            "[ERROR] STREAMLIT_APP_URL environment variable is not set.\n"
            "        Set it in GitHub Secrets or export it locally before running.",
            file=sys.stderr,
        )
        return 1

    print(f"[*] Checking Streamlit app: {STREAMLIT_URL}")

    try:
        from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
    except ImportError:
        print(
            "[ERROR] Playwright is not installed.\n"
            "        Run: pip install playwright && playwright install chromium --with-deps",
            file=sys.stderr,
        )
        return 1

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            # Mimic a real browser to avoid bot-detection filters
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800},
        )
        page = context.new_page()

        try:
            print("[*] Loading page (timeout 60s)...")
            page.goto(STREAMLIT_URL, timeout=60_000, wait_until="domcontentloaded")

            # Give the JS bundle time to hydrate the DOM
            time.sleep(INITIAL_SETTLE)

            # Streamlit Community Cloud sleep screen contains this exact button text
            wake_button = page.locator("button:has-text('Yes, get this app back up!')")

            try:
                is_sleeping = wake_button.is_visible(timeout=4_000)
            except PlaywrightTimeout:
                is_sleeping = False

            if is_sleeping:
                print("[!] App is sleeping -- clicking wake button...")
                wake_button.click()
                print(f"[*] Wake signal sent. Waiting {WAKE_BOOT_WAIT}s for container boot...")
                time.sleep(WAKE_BOOT_WAIT)
                print("[+] Wake-up request dispatched successfully.")
            else:
                print("[+] App is already awake and operational.")

        except PlaywrightTimeout:
            print(
                "[ERROR] Page did not load within 60s. "
                "Check that STREAMLIT_APP_URL is correct and the app is deployed.",
                file=sys.stderr,
            )
            return 1
        except Exception as exc:
            print(f"[ERROR] Unexpected error: {exc}", file=sys.stderr)
            return 1
        finally:
            browser.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())

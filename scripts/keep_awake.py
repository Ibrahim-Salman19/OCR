"""
scripts/keep_awake.py
=====================
Automated Streamlit Community Cloud wake-up script.

Playwright navigates to the deployed app, detects the hibernation banner
("Zzzz -- This app has gone to sleep due to inactivity"), and clicks the
"Yes, get this app back up!" button when found. If the app is already
running, it exits cleanly.

Usage:
    pip install playwright
    playwright install chromium --with-deps
    STREAMLIT_APP_URL=https://your-app.streamlit.app python scripts/keep_awake.py

Environment Variables:
    STREAMLIT_APP_URL   The full public HTTPS URL of the Streamlit app.
                        Set as a GitHub Actions secret or export locally.
"""

import os
import sys
import time

STREAMLIT_URL: str = os.environ.get("STREAMLIT_APP_URL", "").strip()

# Seconds to wait for the DOM to settle after initial page load
INITIAL_SETTLE: int = 8

# Seconds to wait after sending the wake signal before re-checking / exiting
WAKE_BOOT_WAIT: int = 20

# Maximum attempts to click the wake button (guards against slow hibernation exit)
MAX_WAKE_ATTEMPTS: int = 2


def _validate_url(url: str) -> None:
    """Raise ValueError for obviously wrong URLs before launching a browser."""
    if not url.startswith(("https://", "http://")):
        raise ValueError(
            f"STREAMLIT_APP_URL must start with https:// or http://, got: {url!r}"
        )
    if " " in url:
        raise ValueError(f"STREAMLIT_APP_URL contains spaces: {url!r}")


def main() -> int:
    # ------------------------------------------------------------------ #
    # 1. Validate inputs                                                   #
    # ------------------------------------------------------------------ #
    if not STREAMLIT_URL:
        print(
            "[ERROR] STREAMLIT_APP_URL environment variable is not set.\n"
            "        Add it as a GitHub Actions secret or export it locally.",
            file=sys.stderr,
        )
        return 1

    try:
        _validate_url(STREAMLIT_URL)
    except ValueError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1

    print(f"[*] Checking Streamlit app: {STREAMLIT_URL}")

    # ------------------------------------------------------------------ #
    # 2. Import Playwright (graceful failure if not installed)             #
    # ------------------------------------------------------------------ #
    try:
        from playwright.sync_api import (
            sync_playwright,
            TimeoutError as PlaywrightTimeout,
        )
    except ImportError:
        print(
            "[ERROR] Playwright is not installed.\n"
            "        Run: pip install playwright && playwright install chromium --with-deps",
            file=sys.stderr,
        )
        return 1

    # ------------------------------------------------------------------ #
    # 3. Launch browser and interact with the page                         #
    # ------------------------------------------------------------------ #
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            # Realistic user-agent prevents bot-detection on some CDN layers
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800},
        )
        page = context.new_page()

        try:
            print("[*] Loading page (timeout 60 s)...")
            page.goto(STREAMLIT_URL, timeout=60_000, wait_until="domcontentloaded")

            # Give the React / Streamlit JS bundle time to hydrate the DOM
            print(f"[*] Waiting {INITIAL_SETTLE} s for DOM to settle...")
            time.sleep(INITIAL_SETTLE)

            # The sleep screen exposes exactly this button text
            wake_button = page.locator(
                "button:has-text('Yes, get this app back up!')"
            )

            # Attempt to wake up to MAX_WAKE_ATTEMPTS times (Streamlit
            # occasionally needs a second click if the container is slow to start)
            woke = False
            for attempt in range(1, MAX_WAKE_ATTEMPTS + 1):
                try:
                    is_sleeping = wake_button.is_visible(timeout=4_000)
                except PlaywrightTimeout:
                    is_sleeping = False

                if not is_sleeping:
                    break

                print(
                    f"[!] App is sleeping (attempt {attempt}/{MAX_WAKE_ATTEMPTS}) "
                    "-- clicking wake button..."
                )
                wake_button.click()
                woke = True
                time.sleep(WAKE_BOOT_WAIT)

            if woke:
                print("[+] Wake-up request dispatched successfully.")
            else:
                print("[+] App is already awake and operational.")

        except PlaywrightTimeout:
            print(
                "[ERROR] Page did not load within 60 s.\n"
                "        Verify that STREAMLIT_APP_URL is correct and the app is deployed.",
                file=sys.stderr,
            )
            return 1
        except Exception as exc:
            print(f"[ERROR] Unexpected error: {exc}", file=sys.stderr)
            return 1
        finally:
            # Always close the browser to free resources even on error
            browser.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())

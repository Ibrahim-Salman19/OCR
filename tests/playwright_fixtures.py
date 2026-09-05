"""
tests.playwright_fixtures

Reusable Playwright fixtures, server lifecycle managers, and UI interaction helpers
for high-reliability browser testing of B.L.A.S.T. OCR Sovereign Edition.
"""

from __future__ import annotations

import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path
from typing import Generator, Sequence

import pytest
from playwright.sync_api import APIRequestContext, Browser, Page, Playwright, sync_playwright

ROOT_DIR = Path(__file__).resolve().parent.parent


def find_free_port() -> int:
    """Find an unbound high-range TCP port on localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


class StreamlitServer:
    """Manages an isolated subprocess running the Streamlit Sovereign Web App."""

    def __init__(self, port: int | None = None, extra_env: dict[str, str] | None = None) -> None:
        self.port = port or find_free_port()
        self.base_url = f"http://127.0.0.1:{self.port}"
        self.proc: subprocess.Popen | None = None
        self.temp_dir = tempfile.mkdtemp(prefix="blast_st_")
        self.extra_env = extra_env or {}

    def start(self, timeout_sec: float = 25.0) -> str:
        env = dict(os.environ)
        env.update(
            {
                "STREAMLIT_SERVER_HEADLESS": "true",
                "STREAMLIT_SERVER_PORT": str(self.port),
                "STREAMLIT_SERVER_ADDRESS": "127.0.0.1",
                "STREAMLIT_BROWSER_SERVER_ADDRESS": "127.0.0.1",
                "STREAMLIT_BROWSER_GATHER_USAGE_STATS": "false",
                "STREAMLIT_SERVER_ENABLE_CORS": "false",
                "STREAMLIT_SERVER_ENABLE_XSRF_PROTECTION": "false",
                "STREAMLIT_SERVER_FILE_WATCHER_TYPE": "none",
                "PYTHONUNBUFFERED": "1",
                "BLAST_OCR_DATABASE_URL": f"sqlite:///{Path(self.temp_dir) / 'test_ui.db'}",
                "BLAST_OCR_OCR_GPU": "false",
            }
        )
        env.update(self.extra_env)

        entrypoint = str(ROOT_DIR / "streamlit_app.py")
        cmd = [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            entrypoint,
            f"--server.port={self.port}",
            "--server.address=127.0.0.1",
            "--server.headless=true",
            "--browser.gatherUsageStats=false",
        ]

        self.proc = subprocess.Popen(
            cmd,
            cwd=str(ROOT_DIR),
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        start_time = time.monotonic()
        health_url = f"{self.base_url}/_stcore/health"
        fallback_url = f"{self.base_url}/"
        ready = False

        while (time.monotonic() - start_time) < timeout_sec:
            if self.proc.poll() is not None:
                raise RuntimeError(
                    f"Streamlit server process exited prematurely with code {self.proc.returncode}"
                )
            for probe_url in (health_url, fallback_url):
                try:
                    with urllib.request.urlopen(probe_url, timeout=0.8) as resp:
                        if resp.status == 200:
                            ready = True
                            break
                except Exception:
                    pass
            if ready:
                break
            time.sleep(0.4)

        if not ready:
            self.stop()
            raise TimeoutError(
                f"Streamlit server on port {self.port} failed to respond within {timeout_sec}s"
            )

        return self.base_url

    def stop(self) -> None:
        if self.proc is not None:
            try:
                self.proc.terminate()
                self.proc.wait(timeout=3.0)
            except Exception:
                try:
                    self.proc.kill()
                    self.proc.wait(timeout=2.0)
                except Exception:
                    pass
            self.proc = None
        shutil.rmtree(self.temp_dir, ignore_errors=True)


class FastAPIServer:
    """Manages an isolated subprocess running the FastAPI Enterprise REST API."""

    def __init__(self, port: int | None = None) -> None:
        self.port = port or find_free_port()
        self.base_url = f"http://127.0.0.1:{self.port}"
        self.proc: subprocess.Popen | None = None
        self.temp_dir = tempfile.mkdtemp(prefix="blast_api_")

    def start(self, timeout_sec: float = 20.0) -> str:
        env = dict(os.environ)
        env.update(
            {
                "PYTHONUNBUFFERED": "1",
                "BLAST_OCR_DATABASE_URL": f"sqlite:///{Path(self.temp_dir) / 'test_api.db'}",
                "BLAST_OCR_OCR_GPU": "false",
            }
        )

        cmd = [
            sys.executable,
            "-m",
            "uvicorn",
            "blast_ocr.api.app:app",
            "--host",
            "127.0.0.1",
            f"--port={self.port}",
            "--log-level",
            "warning",
        ]

        self.proc = subprocess.Popen(
            cmd,
            cwd=str(ROOT_DIR),
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        start_time = time.monotonic()
        health_url = f"{self.base_url}/v1/health"
        ready = False

        while (time.monotonic() - start_time) < timeout_sec:
            if self.proc.poll() is not None:
                raise RuntimeError(
                    f"FastAPI server process exited prematurely with code {self.proc.returncode}"
                )
            try:
                with urllib.request.urlopen(health_url, timeout=0.8) as resp:
                    if resp.status == 200:
                        ready = True
                        break
            except Exception:
                pass
            time.sleep(0.4)

        if not ready:
            self.stop()
            raise TimeoutError(
                f"FastAPI server on port {self.port} failed to respond within {timeout_sec}s"
            )

        return self.base_url

    def stop(self) -> None:
        if self.proc is not None:
            try:
                self.proc.terminate()
                self.proc.wait(timeout=3.0)
            except Exception:
                try:
                    self.proc.kill()
                    self.proc.wait(timeout=2.0)
                except Exception:
                    pass
            self.proc = None
        shutil.rmtree(self.temp_dir, ignore_errors=True)


# -----------------------------------------------------------------------------
# Pytest Fixtures
# -----------------------------------------------------------------------------


@pytest.fixture(scope="session")
def playwright_instance() -> Generator[Playwright, None, None]:
    with sync_playwright() as pw:
        yield pw


@pytest.fixture(scope="session")
def browser(playwright_instance: Playwright) -> Generator[Browser, None, None]:
    b = playwright_instance.chromium.launch(
        headless=True,
        args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"],
    )
    yield b
    b.close()


@pytest.fixture
def page(browser: Browser) -> Generator[Page, None, None]:
    context = browser.new_context(
        viewport={"width": 1280, "height": 800},
        accept_downloads=True,
    )
    p = context.new_page()

    # Playwright Best Practice: monitor uncaught JS exceptions
    page_errors: list[str] = []
    p.on("pageerror", lambda err: page_errors.append(str(err)))

    yield p

    context.close()
    if page_errors:
        raise AssertionError(
            f"Uncaught JavaScript error(s) detected in browser:\n" + "\n".join(page_errors)
        )


@pytest.fixture(scope="session")
def streamlit_app_url() -> Generator[str, None, None]:
    server = StreamlitServer()
    url = server.start()
    yield url
    server.stop()


@pytest.fixture(scope="session")
def fastapi_app_url() -> Generator[str, None, None]:
    server = FastAPIServer()
    url = server.start()
    yield url
    server.stop()


@pytest.fixture(scope="session")
def api_request_context(
    playwright_instance: Playwright,
    fastapi_app_url: str,
) -> Generator[APIRequestContext, None, None]:
    """Provides a Playwright APIRequestContext for fast, headless REST API testing."""
    ctx = playwright_instance.request.new_context(base_url=fastapi_app_url)
    yield ctx
    ctx.dispose()


# -----------------------------------------------------------------------------
# Playwright Streamlit Navigation & Interaction Helpers
# -----------------------------------------------------------------------------


def enter_mission_control(page: Page, timeout_ms: int = 20000) -> None:
    """Clicks 'ENTER MISSION CONTROL' on the landing hero and waits for dashboard tabs."""
    tab_locator = page.locator('[role="tab"]:has-text("MISSION CONTROL")')
    if tab_locator.count() > 0 and tab_locator.first.is_visible():
        return

    # Auto-wait for hero title to ensure initial hydration
    try:
        page.locator(".blast-landing-title").wait_for(state="visible", timeout=8000)
    except Exception:
        pass

    start_time = time.monotonic()
    while (time.monotonic() - start_time) < (timeout_ms / 1000.0):
        tab_locator = page.locator('[role="tab"]:has-text("MISSION CONTROL")')
        if tab_locator.count() > 0 and tab_locator.first.is_visible():
            break

        cta = page.locator('button:has-text("ENTER MISSION CONTROL")').first
        if cta.count() > 0 and cta.is_visible():
            try:
                cta.click(timeout=2500)
                try:
                    tab_locator.wait_for(state="visible", timeout=2500)
                    break
                except Exception:
                    pass
            except Exception:
                pass
        time.sleep(0.4)

    tab_locator.wait_for(state="visible", timeout=timeout_ms)
    try:
        page.locator(".blast-landing-title").wait_for(state="detached", timeout=timeout_ms)
    except Exception:
        pass
    time.sleep(0.5)


def switch_tab(page: Page, tab_name: str, timeout_ms: int = 8000) -> None:
    """Switches to one of the 4 Sovereign tabs."""
    tab = page.locator(f'[role="tab"]:has-text("{tab_name}")')
    tab.wait_for(state="visible", timeout=timeout_ms)
    tab.click()
    time.sleep(0.6)


def upload_files_to_mission(page: Page, file_paths: Sequence[str | Path]) -> None:
    """Uploads one or more files into Streamlit's file uploader."""
    paths_str = [str(Path(p).resolve()) for p in file_paths]
    page.locator('input[type="file"]').set_input_files(paths_str)
    # Allow Streamlit round-trip upload event
    time.sleep(1.5)


def execute_ocr_and_wait(
    page: Page,
    timeout_sec: float = 60.0,
    check_interval_sec: float = 0.8,
) -> bool:
    """Clicks 'EXECUTE OCR ENGINE' and polls until completion or failure marker appears."""
    exec_btn = page.locator('button:has-text("EXECUTE OCR ENGINE")')
    exec_btn.click()

    start = time.monotonic()
    while (time.monotonic() - start) < timeout_sec:
        time.sleep(check_interval_sec)
        body = page.locator("body").inner_text()
        if (
            "PROCESSED ARTIFACTS" in body
            or "BATCH COMPLETED" in body
            or "PARTIAL BATCH COMPLETE" in body
            or "DOWNLOAD MD" in body
            or "DOWNLOAD MARKDOWN" in body
        ):
            return True
        if "MISSION FAILED" in body:
            return False

    raise TimeoutError(f"OCR execution did not conclude within {timeout_sec}s")

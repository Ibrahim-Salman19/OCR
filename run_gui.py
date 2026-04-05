"""Root GUI entry point for local and cloud-safe execution."""

import os
import subprocess
import sys
from pathlib import Path

# Get the absolute path to this script's directory.
SCRIPT_DIR = Path(__file__).parent.resolve()

# Add root to path so blast_ocr can be imported.
sys.path.insert(0, str(SCRIPT_DIR))


def _running_in_streamlit() -> bool:
    """Return True when called inside an active Streamlit script run."""
    try:
        from streamlit.runtime.scriptrunner import get_script_run_ctx

        return get_script_run_ctx() is not None
    except Exception:
        return bool(os.getenv("STREAMLIT_SERVER_PORT"))


def _run_embedded_streamlit_app() -> None:
    """Execute the app inline when this file is run via `streamlit run`."""
    from blast_ocr.ui.web_app import main as web_app_main

    web_app_main()


def _streamlit_entry_path() -> Path:
    """Return canonical root Streamlit app entry path."""
    return SCRIPT_DIR / "streamlit_app.py"


def main() -> int:
    """Launch Streamlit dashboard and return process exit code."""
    if _running_in_streamlit():
        _run_embedded_streamlit_app()
        return 0

    streamlit_entry = _streamlit_entry_path()
    if not streamlit_entry.exists():
        print(f"[ERROR] Could not find Streamlit entrypoint: {streamlit_entry}")
        return 1

    print("Launching B.L.A.S.T. OCR Dashboard...")
    print(f"Entry: {streamlit_entry}")

    completed = subprocess.run(
        [sys.executable, "-m", "streamlit", "run", str(streamlit_entry)],
        cwd=str(SCRIPT_DIR),
        check=False,
    )
    return int(completed.returncode)


if __name__ == "__main__":
    if _running_in_streamlit():
        main()
    else:
        sys.exit(main())

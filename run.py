"""
Root Entry Point
"""

import sys
import os
import argparse

# Add root to path so blast_ocr can be imported
sys.path.append(os.path.dirname(__file__))

from blast_ocr.main import main


def _running_in_streamlit() -> bool:
    """Return True when this script is executed by Streamlit."""
    try:
        from streamlit.runtime.scriptrunner import get_script_run_ctx

        return get_script_run_ctx() is not None
    except Exception:
        return bool(os.getenv("STREAMLIT_SERVER_PORT"))


def _run_streamlit_ui() -> None:
    """Run dashboard UI when misconfigured as Streamlit app entrypoint."""
    from blast_ocr.ui.web_app import main as ui_main

    ui_main()


if __name__ == "__main__":
    if _running_in_streamlit():
        _run_streamlit_ui()
    else:
        from blast_ocr.cli import run_cli
        sys.exit(run_cli())

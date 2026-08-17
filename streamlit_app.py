"""Streamlit Community Cloud entrypoint."""

import sys
from pathlib import Path

# Add project root to sys.path
_ROOT = Path(__file__).parent.resolve()
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from blast_ocr.ui.web_app import main

main()

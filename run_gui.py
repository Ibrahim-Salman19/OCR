"""
Root GUI Entry Point
Launches the B.L.A.S.T. OCR Dashboard from anywhere.
"""

import sys
import subprocess
from pathlib import Path

# Get the absolute path to this script's directory
SCRIPT_DIR = Path(__file__).parent.resolve()

# Add root to path so blast_ocr can be imported
sys.path.insert(0, str(SCRIPT_DIR))


def main():
    """Launch Streamlit Dashboard using absolute paths."""
    web_app_path = SCRIPT_DIR / "blast_ocr" / "ui" / "web_app.py"

    if not web_app_path.exists():
        print(f"[ERROR] Could not find web app at: {web_app_path}")
        sys.exit(1)

    print("🚀 Launching B.L.A.S.T. OCR Dashboard...")
    print(f"   Path: {web_app_path}")

    # Use subprocess for better cross-platform compatibility
    # Change working directory to project root so relative imports work
    subprocess.run(
        [sys.executable, "-m", "streamlit", "run", str(web_app_path)],
        cwd=str(SCRIPT_DIR),
    )


if __name__ == "__main__":
    main()

import sys
import os
import logging
from pathlib import Path
import tempfile
import cv2
import numpy as np

# Add project root
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.append(str(PROJECT_ROOT))

# Setup Logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("VERIFY")


def check_step(name):
    print(f"\n[TEST] {name}...")


def assert_true(condition, message):
    if not condition:
        print(f"[FAIL] {message}")
        sys.exit(1)
    else:
        print(f"[PASS] {message}")


def verify_dependencies():
    check_step("Dependencies")

    # 1. Config & Poppler
    try:
        from blast_ocr.config import config

        poppler = config.poppler_path
        assert_true(
            poppler and os.path.exists(poppler), f"Poppler path valid: {poppler}"
        )

        # Check pdftoppm executable specifically
        exe = os.path.join(poppler, "pdftoppm.exe")
        assert_true(os.path.exists(exe), f"pdftoppm.exe found at {exe}")

    except ImportError:
        assert_true(False, "Could not import blast_ocr.config")

    # 2. EasyOCR
    try:
        import easyocr  # noqa: F401

        print("[PASS] EasyOCR importable")
    except ImportError:
        assert_true(False, "EasyOCR not installed")

    # 3. UI Libs
    try:
        import streamlit  # noqa: F401
        import pandas  # noqa: F401

        print("[PASS] Streamlit & Pandas importable")
    except ImportError:
        assert_true(False, "UI dependencies missing")


def verify_database():
    check_step("Database")
    from blast_ocr.storage.database import OCRDatabase

    db_path = PROJECT_ROOT / "blast_ocr.db"

    try:
        db = OCRDatabase(f"sqlite:///{db_path}")
        # Write test
        job_id = db.create_job("VERIFY_TEST_FILE", 999)
        assert_true(job_id is not None, "Database write (create_job)")

        # Read test
        job = db.get_job(job_id)
        assert_true(job.filename == "VERIFY_TEST_FILE", "Database read (get_job)")

        # Cleanup (optional, but good for cleanliness)
        session = db.session
        session.delete(job)
        session.commit()
        print("[PASS] Database Read/Write/Delete")

    except Exception as e:
        assert_true(False, f"Database Integrity Error: {e}")


def verify_core_logic():
    check_step("Core Logic (Simulated Run)")
    from blast_ocr.core.text_extractor import extract_from_image, sanitize_for_xml

    # 1. XML Sanitization
    bad_str = "Clean\x00Me"
    clean = sanitize_for_xml(bad_str)
    assert_true(clean == "CleanMe", "XML Sanitizer logic")

    # 2. Image Extraction (Synthetic Image)
    # Create a simple white image with black text is hard to synth without fonts.
    # We will just verify the function doesn't crash on a blank image.
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        img_path = tmp.name

    try:
        # Create blank white image
        img = np.full((100, 100, 3), 255, dtype=np.uint8)
        cv2.imwrite(img_path, img)

        # Run Extractor
        res = extract_from_image(img_path)
        # Should return empty string or initialized error if model fails, but not crash
        assert_true(isinstance(res, str), "Extractor returned string")
        print(f"    Extractor Output (Blank Img): '{res}'")

    except Exception as e:
        assert_true(False, f"Core Extraction Crash: {e}")
    finally:
        if os.path.exists(img_path):
            os.remove(img_path)


def verify_ui_integrity():
    check_step("UI Integrity")
    ui_path = PROJECT_ROOT / "blast_ocr" / "ui" / "web_app.py"
    assert_true(ui_path.exists(), "web_app.py exists")

    # Check for syntax errors by compiling
    try:
        with open(ui_path, "r") as f:
            compile(f.read(), ui_path, "exec")
        print("[PASS] web_app.py Syntax Check")
    except Exception as e:
        assert_true(False, f"UI Syntax Error: {e}")


if __name__ == "__main__":
    print("[*] STARTING FINAL SYSTEM AUDIT [*]")
    verify_dependencies()
    verify_database()
    verify_core_logic()
    verify_ui_integrity()
    print("\n[SUCCESS] SYSTEM VERIFIED: NO ISSUES DETECTED")
    sys.exit(0)

import sys
import os
from pathlib import Path

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from blast_ocr.config import config
    from blast_ocr.logging_config import setup_logging
    from blast_ocr.storage.database import OCRDatabase
    from blast_ocr.core.extractor import RobustOCRExtractor

    print("[OK] Imports successful")
except Exception as e:
    print(f"[FAIL] Imports failed: {e}")
    sys.exit(1)


def main():
    # 1. Test Config
    print(f"[-] Config loaded. Langs: {config.ocr_languages}, GPU: {config.ocr_gpu}")

    # 2. Test Logging
    logger = setup_logging()
    logger.info("Test log message")
    if Path("logs/blast_ocr.log").exists():
        print("[OK] Log file created")
    else:
        print("[FAIL] Log file not found")

    # 3. Test Database
    try:
        db = OCRDatabase()
        job_id = db.create_job("test_file.png", 5)
        print(f"[OK] Database initialized. Created Job ID: {job_id}")
    except Exception as e:
        print(f"[FAIL] Database error: {e}")

    # 4. Test Extractor Init
    try:
        extractor = RobustOCRExtractor()
        print("[OK] Extractor initialized (EasyOCR loaded)")
    except Exception as e:
        print(f"[FAIL] Extractor init failed: {e}")


if __name__ == "__main__":
    main()

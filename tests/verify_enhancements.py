import sys
from pathlib import Path
import os
import logging

# Add project root
sys.path.append(str(Path(__file__).parent.parent))

from blast_ocr.config import config
from blast_ocr.storage.database import OCRDatabase
from blast_ocr.main import process_pdf, get_components

def test_config():
    print("[-] Testing Config...")
    assert hasattr(config, 'poppler_path'), "Config missing poppler_path"
    print(f"    Poppler Path: {config.poppler_path}")
    print("[+] Config OK")

def test_database():
    print("[-] Testing Database...")
    try:
        db = OCRDatabase()
        # Check if we can query
        jobs = db.session.query(db.get_job(1).__class__).all()
        print(f"    Existing Jobs: {len(jobs)}")
        print("[+] Database OK")
    except Exception as e:
        print(f"[!] Database Failed: {e}")
        raise

def test_process_logic():
    print("[-] Testing Process Logic (Dry Run)...")
    logger, _, _, _ = get_components()
    logger.setLevel(logging.CRITICAL) # Silence logs for test
    
    # Test with non-existent PDF to trigger error handling
    res = process_pdf("non_existent_file.pdf", "output")
    assert res == [], "Should return empty list on failure"
    print("[+] Error Handling OK")

if __name__ == "__main__":
    try:
        test_config()
        test_database()
        test_process_logic()
        print("\n[SUCCESS] All verification checks passed.")
    except Exception as e:
        print(f"\n[FAILURE] Verification failed: {e}")
        sys.exit(1)

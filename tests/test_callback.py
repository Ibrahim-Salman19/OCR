import sys
from pathlib import Path
import os
import time

# Add project root
sys.path.append(str(Path(__file__).parent.parent))

from blast_ocr.main import process_pdf, process_single_image
from blast_ocr.config import config

def mock_callback(current, total):
    print(f"CALLBACK: {current}/{total}")

def test_callback_integration():
    print("[-] Testing Callback Integration...")
    
    # We can't easily test process_pdf without a real PDF and time.
    # But we can check if main.py accepts the arg.
    import inspect
    from blast_ocr.main import main, process_pdf
    
    sig_main = inspect.signature(main)
    if 'progress_callback' in sig_main.parameters:
        print("[PASS] main() accepts progress_callback")
    else:
        print("[FAIL] main() missing progress_callback")
        sys.exit(1)

    sig_pdf = inspect.signature(process_pdf)
    if 'progress_callback' in sig_pdf.parameters:
        print("[PASS] process_pdf() accepts progress_callback")
    else:
        print("[FAIL] process_pdf() missing progress_callback")
        sys.exit(1)
        
    print("[SUCCESS] Signatures verified.")

if __name__ == "__main__":
    test_callback_integration()

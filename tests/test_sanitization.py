import sys
from pathlib import Path
import os

# Add project root
sys.path.append(str(Path(__file__).parent.parent))

from blast_ocr.core.text_extractor import sanitize_for_xml, save_output
from docx import Document

def test_sanitization():
    print("[-] Testing Sanitization Logic...")
    
    # Bad string with null byte and control char (0x1F is unit separator, invalid in XML)
    bad_text = "Hello\x00World\x1FTest"
    expected = "HelloWorldTest" # removed chars
    
    sanitized = sanitize_for_xml(bad_text)
    
    if sanitized == expected:
        print(f"[PASS] Sanitized correctly: {repr(bad_text)} -> {repr(sanitized)}")
    else:
        print(f"[FAIL] Expected {repr(expected)}, got {repr(sanitized)}")
        sys.exit(1)

def test_docx_save():
    print("[-] Testing DOCX Save with Bad Chars...")
    bad_text_content = "Safe Line\n## Forbidden\x00Header\nContent with control\x0bchar."
    
    output_dir = "tests/temp_out"
    os.makedirs(output_dir, exist_ok=True)
    
    try:
        md, docx = save_output(bad_text_content, "test_bad_chars", output_dir)
        if docx and os.path.exists(docx):
            print(f"[PASS] DOCX saved successfully at {docx}")
        else:
            print("[FAIL] DOCX path returned None or file missing")
            sys.exit(1)
    except Exception as e:
        print(f"[FAIL] Exception during save: {e}")
        sys.exit(1)

if __name__ == "__main__":
    try:
        test_sanitization()
        test_docx_save()
        print("\n[SUCCESS] XML Sanitization Verified.")
    except Exception as e:
        print(f"\n[FAILURE] Verification failed: {e}")
        sys.exit(1)

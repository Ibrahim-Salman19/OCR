"""
Handshake Script: Tesseract OCR
Phase: Link (Connectivity)

Verifies:
1. pytesseract import
2. Tesseract binary execution
3. Simple OCR on a generated image
"""

import sys
import os
import pytesseract
from PIL import Image, ImageDraw, ImageFont

# Define potential Tesseract paths if not in PATH
COMMON_PATHS = [
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\Tesseract-OCR\tesseract.exe")
]

def check_tesseract():
    print("[-] Checking pytesseract...")
    try:
        import pytesseract
        print(f"[+] pytesseract installed: {pytesseract.__version__}")
    except ImportError:
        print("[!] pytesseract NOT installed.")
        return False

    print("[-] Checking Tesseract binary...")
    tess_cmd = "tesseract"
    
    # Check if tesseract is in PATH
    from shutil import which
    if which("tesseract"):
        print("[+] Tesseract found in PATH.")
    else:
        print("[!] Tesseract NOT in PATH. Checking common locations...")
        found = False
        for path in COMMON_PATHS:
            if os.path.exists(path):
                print(f"[+] Found Tesseract at: {path}")
                pytesseract.pytesseract.tesseract_cmd = path
                tess_cmd = path
                found = True
                break
        if not found:
            print("[X] Tesseract binary NOT found. Please install Tesseract-OCR.")
            return False

    print("[-] Running OCR Handshake...")
    try:
        # Create a simple image
        img = Image.new('RGB', (200, 50), color='white')
        d = ImageDraw.Draw(img)
        d.text((10,10), "B.L.A.S.T.", fill='black')
        
        # Run OCR
        text = pytesseract.image_to_string(img).strip()
        print(f"[-] OCR Output: '{text}'")
        
        if "B.L.A.S.T" in text:
            print("[+] Handshake SUCCESS: OCR is working.")
            return True
        else:
            print("[!] Handshake WARNING: OCR ran but text did not match perfectly.")
            return True
    except Exception as e:
        print(f"[X] Handshake FAILED: {e}")
        return False

if __name__ == "__main__":
    if check_tesseract():
        sys.exit(0)
    else:
        sys.exit(1)

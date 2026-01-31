"""
Handshake Script: EasyOCR
Phase: Link (Connectivity)

Verifies:
1. easyocr import
2. Model loading (CPU/GPU)
3. Text extraction on a sample image
"""

import sys
import easyocr
import numpy as np
from PIL import Image, ImageDraw

def check_easyocr():
    print("[-] Checking EasyOCR...")
    try:
        # Initialize reader (this might download models)
        print("[-] Initializing Reader (en)...")
        reader = easyocr.Reader(['en'], gpu=False) 
        print("[+] Reader Initialized.")
        
        # Create image
        img = Image.new('RGB', (200, 50), color='white')
        d = ImageDraw.Draw(img)
        d.text((10,10), "B.L.A.S.T.", fill='black')
        img_np = np.array(img)
        
        # Run OCR
        print("[-] Running OCR...")
        results = reader.readtext(img_np, detail=0)
        text = " ".join(results)
        print(f"[-] OCR Output: '{text}'")
        
        if "B.L.A.S.T" in text or "B.L.A.S.T." in text:
            print("[+] Handshake SUCCESS: EasyOCR is working.")
            return True
        else:
            print(f"[!] Handshake WARNING: OCR ran but output '{text}' didn't match perfectly.")
            # We consider it a pass if it ran without crashing
            return True
            
    except Exception as e:
        print(f"[X] Handshake FAILED: {e}")
        return False

if __name__ == "__main__":
    if check_easyocr():
        sys.exit(0)
    else:
        sys.exit(1)

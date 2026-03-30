import os
import sys
import logging

# Add current dir to path
sys.path.append(os.getcwd())

from blast_ocr.core.extractor import RobustOCRExtractor
from blast_ocr.config import config

logging.basicConfig(level=logging.INFO)

def test():
    print("Testing clean page (no deskew)...")
    config.auto_deskew = False
    extractor = RobustOCRExtractor()
    
    path = "data/pages/page-06.png"
    if not os.path.exists(path):
        print(f"Error: {path} not found")
        return

    img = extractor.load_image(path)
    processed = extractor.preprocess_image(img)
    
    print("Running EasyOCR...")
    results = extractor.reader.readtext(processed, detail=0)
    
    print("\n--- RESULTS (First 10 lines) ---")
    for line in results[:10]:
        print(line)

if __name__ == "__main__":
    test()

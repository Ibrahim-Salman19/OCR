import cv2
import numpy as np
from blast_ocr.core.extractor import RobustOCRExtractor
from blast_ocr.config import config
import logging

logging.basicConfig(level=logging.INFO)

def debug_page(path, out_processed):
    extractor = RobustOCRExtractor()
    
    # Load and Preprocess like the real pipeline
    img = extractor.load_image(path)
    
    # Simulate the downscale in process_page
    height, width = img.shape[:2]
    max_dim = 1800 
    if height > max_dim or width > max_dim:
        scale = max_dim / max(height, width)
        img = cv2.resize(img, (int(width * scale), int(height * scale)), interpolation=cv2.INTER_LINEAR)
    
    processed = extractor.preprocess_image(img)
    
    # Save the processed image to see what the OCR engine sees
    cv2.imwrite(out_processed, processed)
    print(f"Saved processed image to {out_processed}")
    
    # Run OCR
    results = extractor.reader.readtext(processed, detail=1)
    print("\n--- OCR RESULTS ---")
    for res in results:
        print(f"Conf: {res[2]:.2f} | Text: {res[1]}")

if __name__ == "__main__":
    debug_page("data/pages/page-06.png", "debug_processed_06.png")

from typing import List, Dict, Optional, Union
from pathlib import Path
import logging
import cv2
import numpy as np
import easyocr
import torch
from blast_ocr.config import config
from blast_ocr.core.exceptions import *
from blast_ocr.core.healing import healer
# Optional: if we want to log to DB directly, import here. 
# But usually better to keep extractor pure. 
# The user example showed db usage, I'll allow passing a db instance or ignore it for now to keep it clean, 
# relying on the caller to handle DB based on the returned result/exception.

logger = logging.getLogger(__name__)

class RobustOCRExtractor:
    """
    Robust OCR text extraction engine with self-healing capabilities.
    """
    
    def __init__(self):
        """Initialize OCR engine with config settings"""
        self.reader = None
        self._init_engine()

    @healer.retry_with_backoff
    def _init_engine(self):
        """Initialize EasyOCR with retry logic"""
        try:
            logger.info(f"Initializing EasyOCR (GPU={config.ocr_gpu}, Langs={config.ocr_languages})")
            self.reader = easyocr.Reader(
                config.ocr_languages, 
                gpu=config.ocr_gpu,
                verbose=False
            )
        except Exception as e:
            logger.error(f"Failed to initialize EasyOCR: {e}")
            raise OCREngineError(f"Engine init failed: {e}")

    def load_image(self, image_path: str) -> np.ndarray:
        """Load and validate image file"""
        if not Path(image_path).exists():
            raise ImageLoadError(f"File not found: {image_path}")
            
        try:
            # Load using CV2
            img = cv2.imdecode(np.fromfile(image_path, dtype=np.uint8), cv2.IMREAD_COLOR)
            if img is None:
                raise ImageLoadError("cv2.imdecode returned None")
            return img
        except Exception as e:
            raise ImageLoadError(f"Failed to load image: {e}")

    def preprocess_image(self, img: np.ndarray, target_width=2000) -> np.ndarray:
        """Standard B.L.A.S.T. Preprocessing"""
        try:
            # 1. Gray
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            
            # 2. Denoise (Fast)
            gray = cv2.fastNlMeansDenoising(gray, None, h=10, templateWindowSize=7, searchWindowSize=21)

            # 3. Deskew
            coords = np.column_stack(np.where(gray > 0))
            angle = cv2.minAreaRect(coords)[-1]
            if angle < -45: angle = -(90 + angle)
            else: angle = -angle
            if abs(angle) > 0.2:
                (h, w) = gray.shape
                center = (w // 2, h // 2)
                M = cv2.getRotationMatrix2D(center, angle, 1.0)
                gray = cv2.warpAffine(gray, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)

            # 4. Resize
            h, w = gray.shape
            if w < target_width:
                scale = target_width / float(w)
                gray = cv2.resize(gray, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_CUBIC)

            # 5. Adaptive Threshold
            bin_img = cv2.adaptiveThreshold(
                gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY, 21, 10
            )
            return bin_img
        except Exception as e:
            logger.warning(f"Preprocessing failed: {e}. Using original image.")
            return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    @healer.retry_with_backoff
    def process_page(self, page_path: str, page_number: int) -> Dict:
        """Process single page with comprehensive error handling"""
        try:
            logger.debug(f"Processing page {page_number}: {page_path}")
            
            # 1. Load
            try:
                image = self.load_image(page_path)
            except Exception as e:
                raise ImageLoadError(f"Cannot load {page_path}: {e}")
            
            # 2. Preprocess
            processed_img = self.preprocess_image(image)
            
            # 3. OCR
            try:
                # detail=1 returns [bbox, text, conf]
                raw_results = self.reader.readtext(processed_img, detail=1)
            except Exception as e:
                raise OCREngineError(f"OCR processing failed: {e}")
            
            # 4. Extract & Validate
            if not raw_results:
                logger.warning(f"Page {page_number}: No text detected")
                return {
                    "page": page_number,
                    "text": "",
                    "confidence": 0.0,
                    "bbox_count": 0,
                    "warning": "no_text_detected"
                }

            text_parts = [item[1] for item in raw_results]
            confidences = [item[2] for item in raw_results]
            
            extracted_text = " ".join(text_parts)
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
            
            result = {
                "page": page_number,
                "text": extracted_text,
                "confidence": avg_confidence,
                "bbox_count": len(raw_results)
            }

            # Quality check
            if avg_confidence < config.min_confidence:
                logger.warning(f"Page {page_number} low confidence: {avg_confidence:.2f}")
                # We raise error to trigger retry if desired, OR just flag it. 
                # User requirement said "raise LowConfidenceError" in the sample, 
                # but also "Store with warning flag" in the catch block. 
                # I will raise it so the catch block below handles it as a warning.
                raise LowConfidenceError(avg_confidence, config.min_confidence)
            
            return result

        except LowConfidenceError as e:
            # We caught our own quality check. Return result with warning.
            # We need to reconstruction the result since we raised inside logic.
            # For simplicity, I'll recalculate or restructure this method to avoid double work.
            # But adhering to the requested structure:
            return {
                "page": page_number,
                "text": extracted_text,
                "confidence": e.confidence,
                "bbox_count": len(raw_results),
                "warning": "low_confidence"
            }
        
        except (ImageLoadError, OCREngineError) as e:
            logger.error(f"Page {page_number}: Fatal error - {e}")
            raise PageExtractionError(page_number, e)

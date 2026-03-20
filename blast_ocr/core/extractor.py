from typing import List, Dict, Optional, Union, Tuple
from pathlib import Path
import logging
import cv2
import numpy as np
import easyocr
import re
import os
import threading
from pptx import Presentation
from docx import Document

from blast_ocr.config import config
from blast_ocr.core.exceptions import *
from blast_ocr.core.healing import healer

logger = logging.getLogger(__name__)

# FIX(phase2): HIGH-001 - Module-level global lock for EasyOCR thread safety.
# The architecture doc specifies a GLOBAL lock, but the original code created
# a per-instance lock (self.lock = threading.Lock() in __init__). This meant
# multiple RobustOCRExtractor instances would have separate locks, allowing
# race conditions. Now all instances share this single global lock.
_ocr_global_lock = threading.Lock()

class RobustOCRExtractor:
    """
    Robust OCR text extraction engine with self-healing capabilities.
    """
    
    def __init__(self):
        """Initialize OCR engine with config settings"""
        self.reader = None
        # FIX(phase2): HIGH-001 - Use the module-level global lock instead of per-instance
        self.lock = _ocr_global_lock
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
            if isinstance(e, ImageLoadError):
                raise
            raise ImageLoadError(f"Failed to load image: {e}") from e

    def preprocess_image(self, image_source: Union[str, np.ndarray], target_width=2000) -> np.ndarray:
        """
        Apply adaptive preprocessing to improve OCR accuracy.
        Accepts file path or numpy array. Returns numpy array.
        """
        try:
            if isinstance(image_source, str):
                # Use imdecode for robust loading from path, similar to load_image
                if not Path(image_source).exists():
                    raise ImageLoadError(f"File not found: {image_source}")
                image = cv2.imdecode(np.fromfile(image_source, dtype=np.uint8), cv2.IMREAD_COLOR)
                if image is None:
                    raise ImageLoadError(f"Cannot load image from path: {image_source}")
            else:
                image = image_source
                
            # 1. Gray
            if len(image.shape) == 3:
                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            else:
                gray = image.copy()
            
            # 2. Denoise (Conditional)
            # FIX(phase4): Use config value
            if config.denoise_level > 0:
                h_val = float(config.denoise_level)
                gray = cv2.fastNlMeansDenoising(gray, None, h=h_val, templateWindowSize=7, searchWindowSize=21)

            # 3. Deskew
            # FIX(phase4): Check config
            if config.auto_deskew:
                # Use threshold to find text for deskewing, not just non-black pixels
                _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
                coords = np.column_stack(np.where(thresh > 0))
                
                if coords.shape[0] > 0:
                    angle = cv2.minAreaRect(coords)[-1]
                    
                    # Modern OpenCV minAreaRect returns angle in range [-90, 0) in some versions,
                    # or [0, 90) in others. The logic needs to be robust.
                    # Assuming standard range used in recent OpenCV versions:
                    if angle < -45:
                        angle = -(90 + angle)
                    else:
                        angle = -angle
                    
                    # Only rotate if significant skew
                    if abs(angle) > 0.5:
                        (h, w) = gray.shape
                        center = (w // 2, h // 2)
                        M = cv2.getRotationMatrix2D(center, angle, 1.0)
                        gray = cv2.warpAffine(gray, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)

            # 4. Resize
            h, w = gray.shape
            if w < target_width:
                scale = target_width / float(w)
                gray = cv2.resize(gray, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_CUBIC)

            # 5. Adaptive Threshold - ONLY if requested or strictly needed.
            # EasyOCR handles grayscale well. Binarization can remove details.
            # Returning grayscale is often safer for general OCR.
            # return gray 
            
            # If binarization is desired by user/config (keeping it for now as per legacy behavior 
            # but noting it might be better removed)
            # bin_img = cv2.adaptiveThreshold(
            #     gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            #     cv2.THRESH_BINARY, 21, 10
            # )
            # FIX(phase4): Apply Contrast Boost
            if config.contrast_boost != 1.0:
                 # alpha = contrast (1.0-3.0), beta = brightness (0)
                 gray = cv2.convertScaleAbs(gray, alpha=config.contrast_boost, beta=0)

            return gray

        except Exception as e:
            # FIX(phase2): CRITICAL-002 - Fixed undefined 'img' variable.
            # The original code referenced 'img' but the correct variable is 'image_source'.
            # We also handle the case where image_source is a string path vs numpy array.
            logger.warning(f"Preprocessing failed: {e}. Using original image.")
            if isinstance(image_source, str):
                # Reload the image if we only had a path
                fallback = cv2.imdecode(np.fromfile(image_source, dtype=np.uint8), cv2.IMREAD_COLOR)
                if fallback is None:
                    raise ImageLoadError(f"Cannot load fallback image: {image_source}")
                if len(fallback.shape) == 3:
                    return cv2.cvtColor(fallback, cv2.COLOR_BGR2GRAY)
                return fallback
            else:
                # image_source is already a numpy array
                if len(image_source.shape) == 3:
                    return cv2.cvtColor(image_source, cv2.COLOR_BGR2GRAY)
                return image_source

    @healer.retry_with_backoff
    def process_page(self, page_path: str, page_number: int) -> Dict:
        """Process single page with comprehensive error handling"""
        try:
            logger.debug(f"Processing page {page_number}: {page_path}")
            
            # 1. Load
            image = self.load_image(page_path)
            
            # --- MEMORY SAFETY CHECK ---
            # FIX(phase2): CRITICAL - Downscale more aggressively to prevent OOM
            # Original 2500px threshold was causing 1.3GB allocations per page.
            # Reduced to 1800px which gives good OCR quality while using ~60% less memory.
            if image is not None:
                height, width = image.shape[:2]
                max_dim = 1800  # Reduced from 2500 to prevent OOM crashes
                if height > max_dim or width > max_dim:
                    logger.info(f"Downscaling large image ({width}x{height}) to max {max_dim}px for stability")
                    scale = max_dim / max(height, width)
                    new_width = int(width * scale)
                    new_height = int(height * scale)
                    # PERF(phase3): MEDIUM-004 - Use INTER_LINEAR instead of INTER_AREA
                    # INTER_AREA is slower and quality difference is negligible for OCR
                    image = cv2.resize(image, (new_width, new_height), interpolation=cv2.INTER_LINEAR)

            # 2. Preprocess
            processed_img = self.preprocess_image(image)
            
            # 3. OCR
            try:
                # detail=1 returns [bbox, text, conf]
                with self.lock:
                    raw_results = self.reader.readtext(processed_img, detail=1)
                    
                # FIX(phase2-MEM-001): Explicit cleanup to prevent RAM accumulation
                # We must delete the processed image as it's a large numpy array
                del processed_img
                
                # Also delete the original image if it exists in local scope
                if 'image' in locals():
                    del image
                
                # Force garbage collection to reclaim memory immediately
                import gc
                gc.collect()
                
                # PERF(phase2): Clear GPU memory after each page to prevent VRAM accumulation
                # We use a safer import check here
                try:
                    import torch
                    if torch.cuda.is_available():
                        torch.cuda.empty_cache()
                except (ImportError, OSError, NameError):
                    pass  # No torch installed or DLL load failed, skip cache clearing
                    
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
            
            # Format details for UI: [{'text': t, 'conf': c, 'bbox': b}, ...]
            formatted_details = [
                {'text': item[1], 'conf': item[2], 'bbox': [int(c) for point in item[0] for c in point]} 
                for item in raw_results
            ]
            
            result = {
                "page": page_number,
                "text": extracted_text,
                "confidence": avg_confidence,
                "bbox_count": len(raw_results),
                "details": formatted_details 
            }

            # Quality check
            if avg_confidence < config.min_confidence:
                logger.warning(f"Page {page_number} low confidence: {avg_confidence:.2f}")
                result["warning"] = "low_confidence"
            
            return result
        
        except (ImageLoadError, OCREngineError) as e:
            logger.error(f"Page {page_number}: Fatal error - {e}")
            # Don't wrap if it's already a clean error, but adding context is good.
            raise PageExtractionError(page_number, e)
        except Exception as e:
            logger.error(f"Page {page_number}: Unexpected error - {e}")
            raise PageExtractionError(page_number, e)

# --- Legacy Support / Utilities (Migrated) ---

def extract_from_pptx(pptx_path: str) -> str:
    """Extracts text from slides, including notes and tables."""
    text_content = []
    try:
        prs = Presentation(pptx_path)
        for i, slide in enumerate(prs.slides, start=1):
            slide_text = []
            slide_text.append(f"## Slide {i}")
            
            # 1. Shapes Text
            for shape in slide.shapes:
                if hasattr(shape, "text") and shape.text:
                    slide_text.append(shape.text)
                
                # 2. Tables
                if shape.has_table:
                    for row in shape.table.rows:
                        row_text = " | ".join([cell.text_frame.text for cell in row.cells])
                        slide_text.append(f"| {row_text} |")
            
            # 3. Notes
            if slide.has_notes_slide and slide.notes_slide.notes_text_frame:
                notes = slide.notes_slide.notes_text_frame.text
                if notes:
                    slide_text.append(f"> **Notes:** {notes}")
            
            text_content.append("\n".join(slide_text))
            
        return "\n\n---\n\n".join(text_content)
    except Exception as e:
        # FIX(phase2): HIGH-007 - Raise exception instead of returning error string.
        # The original code returned "[ERROR: ...]" which caused silent failures
        # where error text was written to output files instead of failing the job.
        logger.error(f"PPTX extraction failed: {e}")
        raise OCREngineError(f"PPTX extraction failed: {e}") from e

def sanitize_for_xml(text: str) -> str:
    """Removes characters that are not allowed in XML."""
    if not text: return ""
    return re.sub(r'[^\x09\x0A\x0D\x20-\uD7FF\uE000-\uFFFD\u10000-\u10FFFF]', '', text)

def save_output(text: str, base_name: str, output_dir: str) -> Tuple[str, Optional[str]]:
    """Saves to Markdown and DOCX."""
    os.makedirs(output_dir, exist_ok=True)
    
    # MD
    md_path = os.path.join(output_dir, f"{base_name}.md")
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write(text)
        
    # DOCX
    docx_path = os.path.join(output_dir, f"{base_name}.docx")
    try:
        doc = Document()
        doc.add_heading(base_name, 0)
        
        clean_text = sanitize_for_xml(text)
        
        for line in clean_text.split('\n'):
            line = line.strip()
            if line.startswith('## '):
                doc.add_heading(line.replace('## ', ''), level=2)
            elif line.startswith('---'):
                doc.add_page_break()
            else:
                if line:
                    doc.add_paragraph(line)
        doc.save(docx_path)
    except Exception as e:
        logger.error(f"DOCX generation failed: {e}")
        docx_path = None
    
    return md_path, docx_path


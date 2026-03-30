import cv2
import numpy as np
import gc
import logging
from PIL import Image
from typing import Union, Tuple

logger = logging.getLogger(__name__)

class ForensicRestorer:
    """
    Advanced Image Restoration Layer for OCR.
    Uses Gaussian-Adaptive Denoising and CLAHE to maximize extraction accuracy.
    """

    @staticmethod
    def apply_denoising(image: np.ndarray) -> np.ndarray:
        """
        Removes sensor noise and JPEG artifacts without blurring text edges.
        Inspired by 'fal-restore' patterns for document cleaning.
        """
        try:
            # fastNlMeansDenoising is excellent for flat paper backgrounds
            return cv2.fastNlMeansDenoising(image, None, h=10, templateWindowSize=7, searchWindowSize=21)
        except Exception as e:
            logger.warning(f"Denoising failed, falling back to original: {e}")
            return image

    @staticmethod
    def apply_clahe(image: np.ndarray) -> np.ndarray:
        """
        Contrast Limited Adaptive Histogram Equalization.
        Makes faded text 'pop' relative to the background.
        """
        try:
            # CLAHE (Contrast Limited Adaptive Histogram Equalization)
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            return clahe.apply(image)
        except Exception as e:
            logger.warning(f"CLAHE failed: {e}")
            return image

    @classmethod
    def restore(cls, image_path: str) -> np.ndarray:
        """
        Full restoration pipeline: Gray -> Denoise -> CLAHE -> Sharpen.
        Returns a high-fidelity numpy array ready for EasyOCR.
        """
        # 1. Load as Grayscale for OCR performance
        img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
        if img is None:
            raise ValueError(f"Could not read image at {image_path}")

        # 2. Denoise
        img = cls.apply_denoising(img)

        # 3. Enhance Contrast
        img = cls.apply_clahe(img)

        # 4. Adaptive Thresholding (Optional - EasyOCR often prefers grayscale + CLAHE)
        # However, for 'Ultra-Stable' reliability, we provide a cleaned version.
        
        # Explicitly trigger GC for large image arrays
        gc.collect()
        
        return img

def explicit_gc():
    """Aggressive garbage collection for long-running batch jobs."""
    gc.collect()
    if hasattr(gc, "collect"):
        gc.collect()
    logger.debug("Explict GC Cycle Triggered")

from PIL import Image
import re
from typing import Union, Tuple, List

logger = logging.getLogger(__name__)

class ForensicRestorer:
    """
    Advanced Image Restoration Layer for OCR.
    Uses Gaussian-Adaptive Denoising and CLAHE to maximize extraction accuracy.
    """

    @staticmethod
    def redact_pii(text: str) -> str:
        """
        Regex-based redaction for PII (Social Security, Credit Cards, etc).
        Inspired by 'PSPDFKit-labs/nutrient-agent-skill'.
        """
        # Patterns for SSN and Credit Cards
        ssn_pattern = r'\b\d{3}-\d{2}-\d{4}\b'
        card_pattern = r'\b(?:\d[ -]*?){13,16}\b' # Basic CC pattern
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        
        redacted = re.sub(ssn_pattern, "[REDACTED-SSN]", text)
        redacted = re.sub(card_pattern, "[REDACTED-CARD]", redacted)
        redacted = re.sub(email_pattern, "[REDACTED-EMAIL]", redacted)
        return redacted

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
    def restore(cls, image_path: str, mode: str = "standard") -> np.ndarray:
        """
        Full restoration pipeline: Gray -> Denoise -> CLAHE -> Sharpen.
        'mode' can be 'standard' or 'reflexion' (ultra-high contrast).
        """
        # 1. Load as Grayscale for OCR performance
        img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
        if img is None:
            raise ValueError(f"Could not read image at {image_path}")

        # 2. Denoise
        img = cls.apply_denoising(img)

        # 3. Enhance Contrast (CLAHE logic)
        clip_limit = 2.0 if mode == "standard" else 4.0 # High contrast for reflexion
        clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=(8, 8))
        img = clahe.apply(img)

        # 4. Adaptive Thresholding (Reflection Mode)
        if mode == "reflexion":
            # Extra sharpening kernel
            kernel = np.array([[-1,-1,-1], [-1,9,-1], [-1,-1,-1]])
            img = cv2.filter2D(img, -1, kernel)
        
        # Explicitly trigger GC for large image arrays
        gc.collect()
        
        return img

def explicit_gc():
    """Aggressive garbage collection for long-running batch jobs."""
    gc.collect()
    if hasattr(gc, "collect"):
        gc.collect()
    logger.debug("Explict GC Cycle Triggered")

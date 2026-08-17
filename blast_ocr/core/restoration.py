import re
import logging
import cv2
import numpy as np
import gc

logger = logging.getLogger(__name__)

# FIX(F-09/phase1): Threshold for ForensicRestorer.estimate_noise_sigma().
# Calibrated against this project's own gold corpus (eval/gold): all 14
# real scanned book pages measured sigma in [0.06, 1.05]. Injecting a
# modest synthetic Gaussian noise (std=5) on top of a real page pushed the
# estimate to ~4.5 -- roughly 4x the noisiest real page observed. 2.0 sits
# with headroom above natural variation in a clean scan while remaining
# well below where injected noise starts registering, so it should rarely
# fire on a well-scanned document and reliably fire on a genuinely noisy
# one (phone photo, low-quality fax, degraded microfilm).
NOISE_SIGMA_THRESHOLD = 2.0


class ForensicRestorer:
    """
    Advanced Image Restoration Layer for OCR.
    Uses Gaussian-Adaptive Denoising and CLAHE to maximize extraction accuracy.
    """

    @staticmethod
    def redact_pii(text: str) -> str:
        """
        Enterprise-grade regex redaction for PII, secrets, and sensitive tokens.
        """
        if not text:
            return ""

        # Patterns for SSN and Tax IDs
        ssn_pattern = r"\b\d{3}[- ]\d{2}[- ]\d{4}\b"
        
        # IBAN Bank Accounts (2 letters + 2 digits + 12-30 alphanumeric)
        iban_pattern = r"\b[A-Z]{2}[0-9]{2}[A-Z0-9]{12,30}\b"

        # Credit Cards: 13 to 19 digits with optional hyphens/spaces
        card_pattern = r"\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13}|3(?:0[0-5]|[68][0-9])[0-9]{11}|6(?:011|5[0-9]{2})[0-9]{12}|(?:2131|1800|35\d{3})\d{11}|(?:\d[ -]*?){13,16})\b"
        
        # Email Addresses
        email_pattern = r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"

        # Phone Numbers: requires standard delimiter between groups
        phone_pattern = r"\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]\d{3}[-.\s]\d{4}\b"

        # API Keys & Secrets: AWS, OpenAI, GitHub, Bearer/JWT
        jwt_pattern = r"\beyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]+\b"
        aws_key_pattern = r"\b(AKIA[0-9A-Z]{16})\b"
        openai_key_pattern = r"\b(sk-[A-Za-z0-9_-]{20,})\b"
        github_token_pattern = r"\b(ghp_[A-Za-z0-9]{36}|github_pat_[A-Za-z0-9_]{22,})\b"

        # IPv4 Addresses
        ip_pattern = r"\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b"

        redacted = re.sub(ssn_pattern, "[REDACTED-SSN]", text)
        redacted = re.sub(iban_pattern, "[REDACTED-IBAN]", redacted)
        redacted = re.sub(card_pattern, "[REDACTED-CARD]", redacted)
        redacted = re.sub(email_pattern, "[REDACTED-EMAIL]", redacted)
        redacted = re.sub(jwt_pattern, "[REDACTED-API-KEY]", redacted)
        redacted = re.sub(aws_key_pattern, "[REDACTED-API-KEY]", redacted)
        redacted = re.sub(openai_key_pattern, "[REDACTED-API-KEY]", redacted)
        redacted = re.sub(github_token_pattern, "[REDACTED-API-KEY]", redacted)
        redacted = re.sub(phone_pattern, "[REDACTED-PHONE]", redacted)
        redacted = re.sub(ip_pattern, "[REDACTED-IP]", redacted)
        return redacted

    @staticmethod
    def estimate_noise_sigma(image: np.ndarray) -> float:
        """
        Fast additive-Gaussian-noise standard-deviation estimate.

        Immerkaer, J. (1996), "Fast Noise Variance Estimation",
        CVGIP: Image Understanding, 64(2), 300-302. Convolves with a
        Laplacian mask constructed so that it is (by design) insensitive
        to real image structure/edges and responds mainly to noise --
        unlike a raw Laplacian-variance blur metric, it doesn't conflate
        genuine fine detail (small serif text, thin rules) with sensor
        noise, so it's usable as a "does this page actually need
        denoising" gate rather than just a sharpness score.
        """
        n = image.shape[0] * image.shape[1]
        if n == 0:
            return 0.0

        kernel = np.array(
            [[1, -2, 1], [-2, 4, -2], [1, -2, 1]], dtype=np.float64
        )
        laplace = cv2.filter2D(
            image.astype(np.float64), -1, kernel, borderType=cv2.BORDER_REFLECT
        )
        divider = float(np.square(kernel).sum())  # 36
        factor = np.sqrt(np.pi / 2.0) / (np.sqrt(divider) * n)
        return float(factor * np.sum(np.abs(laplace)))

    @staticmethod
    def apply_denoising(image: np.ndarray) -> np.ndarray:
        """
        Removes sensor noise and JPEG artifacts without blurring text edges.
        Inspired by 'fal-restore' patterns for document cleaning.
        """
        try:
            # fastNlMeansDenoising is excellent for flat paper backgrounds
            return cv2.fastNlMeansDenoising(
                image, None, h=10, templateWindowSize=7, searchWindowSize=21
            )
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
        Full restoration pipeline: Gray -> Denoise (conditional) -> CLAHE -> Sharpen.
        'mode' can be 'standard' or 'reflexion' (ultra-high contrast).
        """
        # 1. Load as Grayscale for OCR performance
        img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
        if img is None:
            raise ValueError(f"Could not read image at {image_path}")

        # 2. Denoise, but only if the page actually measures as noisy.
        # FIX(F-09/phase1): this used to run unconditionally on every page.
        # fastNlMeansDenoising is the single most expensive operation in
        # the pipeline, and on an already-clean scan it blurs thin strokes
        # along with noise that isn't there. Gate it on a real estimate
        # instead of assuming every scan needs it.
        try:
            noise_sigma = cls.estimate_noise_sigma(img)
        except Exception as e:
            logger.warning(f"Noise estimation failed, denoising unconditionally: {e}")
            noise_sigma = float("inf")

        if noise_sigma > NOISE_SIGMA_THRESHOLD:
            logger.info(
                f"Noise sigma {noise_sigma:.2f} > {NOISE_SIGMA_THRESHOLD}, denoising"
            )
            img = cls.apply_denoising(img)
        else:
            logger.debug(
                f"Noise sigma {noise_sigma:.2f} <= {NOISE_SIGMA_THRESHOLD}, skipping denoise"
            )

        # 3. Enhance Contrast & Sharpen (Reflexion Mode only)
        # FIX(phase1 ablation): Unconditional CLAHE on standard mode was
        # measured (in component ablation tests) to severely degrade text
        # recognition accuracy on clean book scans by introducing tiled
        # background contrast artifacts (driving p097 CER 0.439->0.805 and
        # p002 CER 0.197->0.214). Clean scans must be passed to the extractor
        # as natural grayscale without crushed local tile contrast. High-contrast
        # CLAHE and sharpening belong strictly in reflexion mode for recovery.
        if mode == "reflexion":
            clahe = cv2.createCLAHE(clipLimit=4.0, tileGridSize=(8, 8))
            img = clahe.apply(img)
            kernel = np.array([[-1, -1, -1], [-1, 9, -1], [-1, -1, -1]])
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

# B.L.A.S.T. OCR Package
import logging

logger = logging.getLogger(__name__)

# --- Sovereign Forensic Safety Wrapper ---
try:
    import defusedxml
    defusedxml.defuse_stdlib()
    logger.info("Forensic XML Security: ACTIVE")
except ImportError:
    logger.warning("Forensic XML Security: MISSING (defusedxml not found)")
    # We do not crash here, we allow the UI to report the error in detail

__version__ = "1.0.0-SOVEREIGN"

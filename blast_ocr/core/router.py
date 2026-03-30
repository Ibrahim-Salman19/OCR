import langdetect
import logging
from typing import List

logger = logging.getLogger(__name__)


class ScriptRouter:
    """
    Intelligent Script & Language Router for OCR.
    Inspired by 'WordPress/wordpress-router' and 'anthropics/pdf' patterns.
    """

    SUPPORTED_SCRIPTS = {
        "en": "english",
        "fr": "french",
        "de": "german",
        "es": "spanish",
        "pt": "portuguese",
        "zh": "chinese_sim",
        "ar": "arabic",
    }

    @staticmethod
    def detect_script(text_sample: str) -> str:
        """
        Detects the probable script/language of a text snippet.
        """
        try:
            # Fast detection using langdetect
            lang = langdetect.detect(text_sample)
            logger.info(f"Detected script: {lang}")
            return lang
        except Exception as e:
            logger.warning(f"Script detection failed: {e}")
            return "en"  # Fallback to core logic

    @classmethod
    def get_ocr_engine_params(cls, lang: str) -> List[str]:
        """
        Returns the optimized language list for EasyOCR based on detection.
        """
        # Common Script Groups
        script_groups = {
            "en": ["en"],
            "fr": ["en", "fr"],
            "de": ["en", "de"],
            "ar": ["en", "ar"],
        }
        return script_groups.get(lang, ["en"])


def apply_auto_routing(pipeline_instance, sample_text: str):
    """
    Dynamically adjusts pipeline settings based on script discovery.
    """
    lang = ScriptRouter.detect_script(sample_text)
    engine_langs = ScriptRouter.get_ocr_engine_params(lang)

    # We update the internal config if needed - however, EasyOCR initialization is expensive.
    # We typically signal the pipeline to use these for the next job or re-initialize.
    logger.info(f"Routing to engine profile: {engine_langs}")
    return engine_langs

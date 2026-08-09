import langdetect
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


class ScriptRouter:
    """
    Intelligent Script & Language Router for OCR.
    Dynamically routes multi-lingual content to optimal engine language combinations.
    """

    SUPPORTED_SCRIPTS: Dict[str, str] = {
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
        Detects the probable script/language of a text snippet using langdetect.
        Falls back to 'en' gracefully if text is invalid or language is unknown.
        """
        if not text_sample or not text_sample.strip():
            return "en"
        try:
            lang = langdetect.detect(text_sample)
            logger.info(f"Detected script: {lang}")
            return lang
        except Exception as e:
            logger.warning(f"Script detection failed: {e}")
            return "en"

    @classmethod
    def get_ocr_engine_params(cls, lang: str) -> List[str]:
        """
        Returns the optimized language combination list for EasyOCR based on detected language code.
        """
        script_groups: Dict[str, List[str]] = {
            "en": ["en"],
            "fr": ["en", "fr"],
            "de": ["en", "de"],
            "es": ["en", "es"],
            "pt": ["en", "pt"],
            "ar": ["en", "ar"],
            "zh": ["en", "ch_sim"],
            "zh-cn": ["en", "ch_sim"],
            "zh-tw": ["en", "ch_tra"],
        }
        return script_groups.get(lang.lower(), ["en"])


def apply_auto_routing(pipeline_instance: Any, sample_text: str) -> List[str]:
    """
    Dynamically adjusts pipeline language settings based on script discovery.
    """
    lang = ScriptRouter.detect_script(sample_text)
    engine_langs = ScriptRouter.get_ocr_engine_params(lang)

    if pipeline_instance and hasattr(pipeline_instance, "_config"):
        pipeline_instance._config.ocr_languages = engine_langs

    logger.info(f"Routing pipeline to engine profile: {engine_langs}")
    return engine_langs

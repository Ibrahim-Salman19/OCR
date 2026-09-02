import langdetect
import logging
from typing import List, Dict, Any

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
        "ur": "urdu",
        "fa": "persian",
        "ug": "uyghur",
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
            "ur": ["en", "ur"],
            "fa": ["en", "fa"],
            "ug": ["en", "ug"],
            "zh": ["en", "ch_sim"],
            "zh-cn": ["en", "ch_sim"],
            "zh-tw": ["en", "ch_tra"],
        }
        return script_groups.get(lang.lower(), ["en"])


def apply_auto_routing(pipeline_instance: Any, sample_text: str) -> List[str]:
    """
    Determines the OCR engine language profile for a sample of text.

    Returns the language list for the caller to fold into its own immutable
    per-job JobConfig. Does NOT mutate shared pipeline/global state -- a
    pipeline instance may be processing multiple concurrent jobs with
    different language requirements, and writing the result onto
    `pipeline_instance._config` would leak one job's language routing into
    another's (the same class of cross-job state bug that JobConfig was
    introduced to eliminate for OCR engine selection).
    """
    lang = ScriptRouter.detect_script(sample_text)
    engine_langs = ScriptRouter.get_ocr_engine_params(lang)
    logger.info(f"Detected engine profile for sample text: {engine_langs}")
    return engine_langs

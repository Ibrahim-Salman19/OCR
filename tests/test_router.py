from unittest.mock import MagicMock
from blast_ocr.core.router import ScriptRouter, apply_auto_routing


def test_script_router_supported_scripts():
    assert "en" in ScriptRouter.SUPPORTED_SCRIPTS
    assert "fr" in ScriptRouter.SUPPORTED_SCRIPTS
    assert "de" in ScriptRouter.SUPPORTED_SCRIPTS
    assert "es" in ScriptRouter.SUPPORTED_SCRIPTS
    assert "zh" in ScriptRouter.SUPPORTED_SCRIPTS


def test_detect_script_valid_text():
    lang = ScriptRouter.detect_script("This is a simple English text for detection.")
    assert lang == "en"


def test_detect_script_empty_fallback():
    assert ScriptRouter.detect_script("") == "en"
    assert ScriptRouter.detect_script(None) == "en"


def test_get_ocr_engine_params():
    assert ScriptRouter.get_ocr_engine_params("en") == ["en"]
    assert ScriptRouter.get_ocr_engine_params("fr") == ["en", "fr"]
    assert ScriptRouter.get_ocr_engine_params("de") == ["en", "de"]
    assert ScriptRouter.get_ocr_engine_params("es") == ["en", "es"]
    assert ScriptRouter.get_ocr_engine_params("zh") == ["en", "ch_sim"]
    assert ScriptRouter.get_ocr_engine_params("unknown_script") == ["en"]


def test_apply_auto_routing():
    mock_pipeline = MagicMock()
    mock_pipeline._config.ocr_languages = ["en"]

    langs = apply_auto_routing(
        mock_pipeline, "Bonjour tout le monde, ceci est un texte en français."
    )
    assert isinstance(langs, list)
    assert len(langs) > 0

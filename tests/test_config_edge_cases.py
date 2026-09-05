"""
PHASE 9: OCRConfig validation, environment variable parsing, and edge cases.
"""

import pytest
import os
from unittest.mock import patch


# ── Test 1: Negative max_workers ─────────────────────────────────────────
def test_config_negative_max_workers():
    from blast_ocr.config import OCRConfig

    try:
        cfg = OCRConfig(max_workers=-1)
        # If Pydantic doesn't validate, this is a bug
        if cfg.max_workers < 0:
            pytest.fail(
                "BUG: OCRConfig accepts negative max_workers. "
                "ThreadPoolExecutor(max_workers=-1) will raise ValueError at runtime."
            )
    except Exception:
        pass  # Validation correctly rejected it


# ── Test 2: min_confidence > 1.0 ─────────────────────────────────────────
def test_config_min_confidence_above_1():
    from blast_ocr.config import OCRConfig

    try:
        cfg = OCRConfig(min_confidence=1.5)
        if cfg.min_confidence == 1.5:
            pytest.fail(
                "BUG: OCRConfig accepts min_confidence=1.5. "
                "EasyOCR confidence is always 0.0-1.0, so no page would ever pass the check."
            )
    except Exception:
        pass


# ── Test 3: Empty ocr_languages list ─────────────────────────────────────
def test_config_empty_languages():
    from blast_ocr.config import OCRConfig

    try:
        cfg = OCRConfig(ocr_languages=[])
        if cfg.ocr_languages == []:
            pytest.fail(
                "BUG: OCRConfig accepts empty ocr_languages=[]. "
                "easyocr.Reader([]) will raise ValueError at runtime."
            )
    except Exception:
        pass


# ── Test 4: timeout_per_page=0 ───────────────────────────────────────────
def test_config_zero_timeout():
    from blast_ocr.config import OCRConfig

    try:
        cfg = OCRConfig(timeout_per_page=0)
        if cfg.timeout_per_page == 0:
            pytest.fail(
                "BUG: OCRConfig accepts timeout_per_page=0. "
                "ThreadPoolExecutor.result(timeout=0) will immediately raise TimeoutError "
                "for every page, making the pipeline completely non-functional."
            )
    except Exception:
        pass


# ── Test 5: _detect_poppler_path on Linux returns None ───────────────────
def test_poppler_path_is_none_on_linux():
    """On Linux, poppler should be on system PATH — None is correct."""
    import sys

    if sys.platform != "win32":
        from blast_ocr.config import config

        # None means "use system PATH" — this is correct for Linux/cloud
        # But verify it doesn't crash pdf2image if set to None
        assert config.poppler_path is None or isinstance(config.poppler_path, str)


# ── Test 6: Environment variables override defaults ───────────────────────
def test_env_vars_override_defaults():
    """Verify BLAST_OCR_ prefix env vars are picked up."""
    with patch.dict(
        os.environ,
        {
            "BLAST_OCR_MIN_CONFIDENCE": "0.42",
            "BLAST_OCR_MAX_WORKERS": "1",
            "BLAST_OCR_OCR_GPU": "false",
        },
    ):
        from importlib import reload
        import blast_ocr.config as cfg_module

        orig_config = cfg_module.config
        try:
            reload(cfg_module)

            assert cfg_module.config.min_confidence == 0.42, (
                f"Env var BLAST_OCR_MIN_CONFIDENCE not picked up: {cfg_module.config.min_confidence}"
            )
            assert cfg_module.config.max_workers == 1
        finally:
            cfg_module.config = orig_config


# ── Test 7: contrast_boost=0.0 (would black out the image) ───────────────
def test_config_zero_contrast_boost():
    from blast_ocr.config import OCRConfig

    try:
        cfg = OCRConfig(contrast_boost=0.0)
        if cfg.contrast_boost == 0.0:
            pytest.fail(
                "BUG: contrast_boost=0.0 will call cv2.convertScaleAbs(alpha=0.0) "
                "which produces a completely black image, destroying all OCR accuracy. "
                "Valid range should be 1.0-3.0, or 0.0 should mean 'disabled'."
            )
    except Exception:
        pass


# ── Additional Test 11.1 — except Exception swallows KeyboardInterrupt ─────
def test_no_bare_except_swallowing_keyboard_interrupt():
    """
    REASONING: 'except Exception:' does NOT catch KeyboardInterrupt (BaseException).
    BUT 'except:' (bare) DOES — trapping Ctrl+C inside OCR loops.
    Also check for SystemExit being swallowed by overly broad except blocks.
    """
    from pathlib import Path
    import ast

    for src in Path("blast_ocr/").rglob("*.py"):
        try:
            tree = ast.parse(src.read_text(encoding="utf-8"))
        except SyntaxError:
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler):
                if node.type is None:  # bare except:
                    pytest.fail(
                        f"BUG-EXCEPT-BARE-01 | MEDIUM | logic\n"
                        f"Bare 'except:' found in {src}:{node.lineno}\n"
                        f"Catches KeyboardInterrupt and SystemExit — "
                        f"prevents graceful shutdown of OCR pipeline.\n"
                        f"Fix: Use 'except Exception:' instead of bare 'except:'"
                    )

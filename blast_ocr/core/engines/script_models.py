"""
blast_ocr.core.engines.script_models

Perso-Arabic script model registry for RapidOCREngine.

RapidOCR's bundled default models (ch_PP-OCRv4_det/rec) are trained on
Chinese+English text only -- they have no Arabic-script characters in their
recognition dictionary at all, so requesting Arabic/Urdu/Persian/Uyghur
through the default `rapidocr` engine silently returns empty or garbage text
for every non-Latin, non-CJK glyph while still correctly reading any
Latin-script fragments (e.g. page numbers) on the same page. This is the
root cause of a real user report: an Urdu book PDF returned only page
numbers, with all Urdu words dropped.

This module downloads and caches PaddleOCR's dedicated PP-OCRv5 Arabic-script
recognition model (which covers Arabic, Persian, Urdu, and Uyghur -- they
share the same base script and this model's ~750-entry dictionary includes
the Urdu/Persian-specific letters, e.g. ٹ ڈ ڑ ں ے ھ ژ ک گ چ), so
RapidOCREngine can swap it in for `config.ocr_languages` containing any of
those four codes while keeping the existing bundled detection model (text
*detection* is script-agnostic; only recognition needs a language-specific
model).

Source: PaddleOCR's own PP-OCRv5 multilingual release, mirrored by the
RapidOCR project (github.com/RapidAI/RapidOCR) at the URLs below -- verified
against RapidOCR v3.9.2's own `default_models.yaml` model manifest, which is
also where the pinned SHA256 for the recognition model comes from.
"""

from __future__ import annotations

import hashlib
import logging
import os
import tempfile
import threading
import urllib.request
from pathlib import Path
from typing import Tuple

from blast_ocr.core.script_detection import (  # noqa: F401 (re-exported)
    RTL_SCRIPT_LANGUAGES,
    contains_rtl_script,
)

logger = logging.getLogger(__name__)

# Guards the whole check-download-verify-replace sequence in _ensure_file.
# RapidOCREngine instances are created per worker thread (blast_ocr.core.
# parallel's ThreadPoolExecutor), so several threads can call
# ensure_arabic_model() concurrently on a cold cache -- without this lock,
# two threads in the same process race on the same tmp_dest path (its name
# is only unique per-process, via os.getpid(), not per-thread) and can
# interleave writes into it before either side's os.replace() runs. Same
# class of bug as image_sanitizer.py's _pil_ceiling_lock.
_download_lock = threading.Lock()

_REC_URL = (
    "https://www.modelscope.cn/models/RapidAI/RapidOCR/resolve/v3.9.2/"
    "onnx/PP-OCRv5/rec/arabic_PP-OCRv5_rec_mobile.onnx"
)
_REC_SHA256 = "c1192e632d0baa9146ae5b756a0e635e3dc63c1733737ebfd1629e87144e9295"

_DICT_URL = (
    "https://www.modelscope.cn/models/RapidAI/RapidOCR/resolve/v3.9.2/"
    "paddle/PP-OCRv5/rec/arabic_PP-OCRv5_rec_mobile/ppocrv5_arabic_dict.txt"
)
_DICT_SHA256 = "7f92f7dbb9b75a4787a83bfb4f6d14a8ab515525130c9d40a9036f61cf6999e9"

_REC_FILENAME = "arabic_PP-OCRv5_rec_mobile.onnx"
_DICT_FILENAME = "ppocrv5_arabic_dict.txt"


class ArabicModelUnavailableError(RuntimeError):
    """Raised when the Arabic-script model isn't cached and download is
    disabled or fails."""


def _default_cache_dir() -> str:
    configured = os.getenv("BLAST_OCR_RAPIDOCR_ARABIC_MODEL_DIR")
    if configured:
        return configured
    return os.path.join(tempfile.gettempdir(), "blast_ocr_models", "arabic_ppocrv5")


def _download_enabled() -> bool:
    flag = os.getenv("BLAST_OCR_RAPIDOCR_MODEL_DOWNLOAD_ENABLED", "1")
    return flag.strip().lower() not in {"0", "false", "no", "off"}


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _ensure_file(dest: Path, url: str, expected_sha256: str) -> None:
    with _download_lock:
        if dest.exists() and _sha256_file(dest) == expected_sha256:
            return
        if not _download_enabled():
            raise ArabicModelUnavailableError(
                f"{dest.name} not found in cache ({dest.parent}) and "
                "BLAST_OCR_RAPIDOCR_MODEL_DOWNLOAD_ENABLED disables fetching it. "
                f"Pre-populate the cache or download manually from {url}"
            )
        if not url.startswith("https://"):
            raise ArabicModelUnavailableError(f"Refusing non-HTTPS model URL: {url}")

        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp_dest = dest.with_suffix(dest.suffix + f".tmp{os.getpid()}")
        logger.info("Downloading Arabic-script OCR model asset: %s", url)
        try:
            # url is one of this module's own hardcoded HTTPS constants
            # (never user input), and the scheme is checked above.
            urllib.request.urlretrieve(url, tmp_dest)  # nosec B310
            actual = _sha256_file(tmp_dest)
            if actual != expected_sha256:
                raise ArabicModelUnavailableError(
                    f"Downloaded {dest.name} failed checksum verification "
                    f"(expected {expected_sha256}, got {actual}) -- refusing to "
                    "use a possibly corrupted or tampered OCR model file."
                )
            os.replace(tmp_dest, dest)
        finally:
            tmp_dest.unlink(missing_ok=True)


def ensure_arabic_model() -> Tuple[str, str]:
    """Returns (rec_model_path, dict_path) for PaddleOCR's PP-OCRv5
    Arabic-script recognition model, downloading and checksum-verifying into
    a local cache on first use if not already present.

    Raises ArabicModelUnavailableError if the files aren't cached and
    downloading is disabled or fails.
    """
    cache_dir = Path(_default_cache_dir())
    rec_path = cache_dir / _REC_FILENAME
    dict_path = cache_dir / _DICT_FILENAME
    _ensure_file(rec_path, _REC_URL, _REC_SHA256)
    _ensure_file(dict_path, _DICT_URL, _DICT_SHA256)
    return str(rec_path), str(dict_path)

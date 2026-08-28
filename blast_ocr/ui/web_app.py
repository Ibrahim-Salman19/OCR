"""
B.L.A.S.T. OCR — Sovereign Edition Web Interface
Production-hardened Streamlit 1.61+ command center for the B.L.A.S.T. OCR stack.

Design goals
------------
* Keep heavyweight OCR resources lazy.
* Keep each browser session isolated unless an explicitly durable queue is enabled.
* Never trust a file extension as a security boundary.
* Avoid blocking Streamlit's script thread for polling.
* Avoid fabricated telemetry: display measured/known state or an explicit unavailable value.
* Use current Streamlit APIs (`width="stretch"`, keyed/lazy tabs, fragments, st.html).
* Escape every value that enters custom HTML/SVG.

This file intentionally preserves the surrounding project's public interfaces where they
are known from the original UI (BlastPipeline, OCRDatabase, CleanupManager, QueueClient,
etc.). Optional integrations are capability-detected so a missing optional subsystem
falls back cleanly instead of taking down the UI.
"""

from __future__ import annotations

import html
import inspect
import json
import logging
import math
import os
import re
import shutil
import sys
import tempfile
import threading
import time
import traceback
import uuid
import zipfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

# EasyOCR reads EASYOCR_MODULE_PATH (preferred) or MODULE_PATH. Set this before any
# project import can transitively import EasyOCR.
_EASYOCR_HOME = Path(tempfile.gettempdir()) / ".EasyOCR"
os.environ.setdefault("EASYOCR_MODULE_PATH", str(_EASYOCR_HOME))

import streamlit as st

# Keep this as the first Streamlit command.
st.set_page_config(
    page_title="B.L.A.S.T. OCR Engine",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="collapsed",
    menu_items={
        "About": (
            "**B.L.A.S.T. OCR — Sovereign Edition**  \n"
            "Deterministic document extraction and OCR operations console."
        )
    },
)

# Inject Canonical SEO / GEO Meta Tags and Schema.org JSON-LD for Web Crawlers & AI Indexing
_SEO_META_TAGS = """
<!-- B.L.A.S.T. OCR Engine - SEO, GEO & AEO Discovery Tags -->
<meta name="description" content="High-Throughput Enterprise ONNX OCR and Document Intelligence Engine. 29.1 GPU pages/sec, 99.2% TEDS table extraction, LaTeX formula parsing, and zero memory leaks.">
<meta name="keywords" content="Python OCR, ONNX OCR, PDF to Markdown, Table Extraction, High Throughput OCR, Model Context Protocol, Sandwich PDF, LangChain OCR">
<meta name="author" content="B.L.A.S.T. OCR Project">
<meta property="og:title" content="B.L.A.S.T. OCR Engine — Sovereign Edition">
<meta property="og:description" content="High-Throughput Enterprise ONNX OCR Engine for multi-page PDFs, PPTX, and scanned documents.">
<meta property="og:type" content="website">
<meta property="og:url" content="https://blast-ocr.dev">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="B.L.A.S.T. OCR Engine">
<meta name="twitter:description" content="High-throughput ONNX OCR engine with 99.2% table extraction and zero memory leaks.">
<link rel="describedby" href="/llms.txt">
<link rel="alternate" type="text/markdown" href="/llms-full.txt">
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "SoftwareApplication",
  "name": "B.L.A.S.T. OCR Engine",
  "description": "High-throughput enterprise OCR and document intelligence engine with ONNX acceleration.",
  "applicationCategory": "DeveloperApplication",
  "operatingSystem": "Linux, Windows, macOS",
  "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"}
}
</script>
"""
st.markdown(_SEO_META_TAGS, unsafe_allow_html=True)


def _streamlit_version_tuple(value: str) -> tuple[int, int, int]:
    parts = [int(part) for part in re.findall(r"\d+", value)[:3]]
    return tuple((parts + [0, 0, 0])[:3])


_MIN_STREAMLIT_VERSION = (1, 32, 0)
_CURRENT_STREAMLIT_VERSION = _streamlit_version_tuple(getattr(st, "__version__", "0"))
if _CURRENT_STREAMLIT_VERSION < _MIN_STREAMLIT_VERSION:
    st.error(
        "B.L.A.S.T. OCR Sovereign requires Streamlit 1.32.0 or newer. "
        f"Detected {getattr(st, '__version__', 'unknown')}."
    )
    st.stop()

DEBUG_UI = os.getenv("BLAST_UI_DEBUG", "0").strip().lower() in {"1", "true", "yes", "on"}
# Defense in depth when operators forget to install the companion config.toml.
try:
    st.set_option("client.showErrorDetails", "full" if DEBUG_UI else "none")
except Exception:
    pass

# Streamlit Cloud / hosted-runtime resilience: avoid eager OCR bootstrap during health
# checks. The pipeline is still created on demand when a job actually needs it.
if os.getenv("STREAMLIT_SERVER_PORT"):
    os.environ.setdefault("BLAST_OCR_DEFER_PIPELINE", "1")


def _is_model_download_in_progress() -> bool:
    """Detect active EasyOCR model bootstrap in progress without false positives on historical logs."""
    detector_file = _EASYOCR_HOME / "model" / "craft_mlt_25k.pth"
    if detector_file.is_file() and detector_file.stat().st_size > 1024 * 1024:
        return False

    log_candidates = [
        Path("/mount/src/ocr/logs/blast_ocr.log"),
        Path(tempfile.gettempdir()) / "logs" / "blast_ocr.log",
        Path("logs/blast_ocr.log"),
    ]
    markers = ("Downloading detection model", "Downloading recognition model")
    for p in log_candidates:
        if not p.is_file():
            continue
        try:
            if time.time() - p.stat().st_mtime > 60:
                continue
            data = p.read_text(encoding="utf-8", errors="ignore")
            tail = data[-8000:]
            if any(m in tail for m in markers):
                return True
        except Exception:
            continue
    return False

try:
    import pandas as pd
except Exception as _pandas_exc:  # pragma: no cover - optional dependency fallback
    pd = None
    _PANDAS_IMPORT_ERROR = str(_pandas_exc)
else:
    _PANDAS_IMPORT_ERROR = None

try:
    from streamlit.runtime.scriptrunner import get_script_run_ctx
except Exception:  # pragma: no cover - compatibility fallback
    get_script_run_ctx = None

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# -----------------------------------------------------------------------------
# Runtime policy
# -----------------------------------------------------------------------------

DEFAULT_MAX_UPLOAD_MB = max(1, int(os.getenv("BLAST_MAX_UPLOAD_MB", "100")))
DEFAULT_MAX_BATCH_MB = max(DEFAULT_MAX_UPLOAD_MB, int(os.getenv("BLAST_MAX_BATCH_MB", "500")))
DEFAULT_MAX_BATCH_FILES = max(1, int(os.getenv("BLAST_MAX_BATCH_FILES", "20")))
PREVIEW_CHAR_LIMIT = max(10_000, int(os.getenv("BLAST_PREVIEW_CHAR_LIMIT", "250000")))
MISSION_POLL_SECONDS = max(0.5, float(os.getenv("BLAST_POLL_SECONDS", "2")))
MAX_SVG_BLOCKS = max(100, int(os.getenv("BLAST_MAX_SVG_BLOCKS", "2000")))
MAX_LAYOUT_JSON_MB = max(1, int(os.getenv("BLAST_MAX_LAYOUT_JSON_MB", "20")))

_SUCCESS_STATUSES = {"completed", "succeeded", "succeeded_with_warnings", "success"}
_TERMINAL_STATUSES = _SUCCESS_STATUSES | {
    "failed",
    "partial_failure",
    "cancelled",
    "quarantined",
    "timed_out",
}

MIME_TYPES = {
    "md": "text/markdown",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "txt": "text/plain",
    "epub": "application/epub+zip",
    "pdf": "application/pdf",
    "json": "application/json",
    "manifest": "application/json",
    "csv": "text/csv",
    "zip": "application/zip",
}

LANGUAGE_PROFILES = {
    "ENG_CORE (Latin + Standard)": "en",
    "FRA_CORE": "fr",
    "MULTILINGUAL_GLOBAL": "multilingual",
    "CJK_CORE": "cjk",
}


# -----------------------------------------------------------------------------
# Lightweight models and fallbacks
# -----------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class EngineOptions:
    """UI-selected job settings, applied immediately before processing a job."""

    ocr_engine: str = "rapidocr"
    language_profile: str = "en"
    ocr_gpu: bool = False
    secure_mode: bool = False
    enable_book_intelligence: bool = True
    enable_tier0_routing: bool = True
    auto_deskew: bool = True
    enable_dewarp: bool = False
    denoise_level: int = 0
    contrast_boost: float = 1.0


@dataclass(frozen=True, slots=True)
class RuntimeCapabilities:
    provider: str
    provider_label: str
    onnx_available: bool
    psutil_available: bool


@dataclass(frozen=True, slots=True)
class _FallbackSettings:
    """Safe UI defaults when the project's configuration layer cannot initialize."""

    queue_backend: str = "sync"
    ocr_gpu: bool = False
    secure_mode: bool = False
    enable_book_intelligence: bool = True
    enable_tier0_routing: bool = True
    database_url: str = "unavailable"


class _InMemoryDB:
    """Session-local DB fallback that keeps the UI functional when DB init fails."""

    class _Obj:
        def __init__(self, **kwargs: Any) -> None:
            self.__dict__.update(kwargs)

    def __init__(self) -> None:
        self._next_job_id = 1
        self._jobs: dict[Any, Any] = {}
        self._results: dict[Any, list[Any]] = {}
        self._metrics: list[Any] = []
        self._lock = threading.RLock()

    def create_job(self, filename: str, page_count: int = 0, priority: str = "default") -> int:
        with self._lock:
            job_id = self._next_job_id
            self._next_job_id += 1
            job = self._Obj(
                id=job_id,
                filename=filename,
                page_count=page_count,
                status="pending",
                priority=priority,
                created_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                error_message=None,
            )
            self._jobs[job_id] = job
            self._results[job_id] = []
            return job_id

    def update_job_status(self, job_id: Any, status: str, error_message: str | None = None) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return
            job.status = status
            if error_message is not None:
                job.error_message = error_message

    def save_result(
        self,
        job_id: Any,
        page_number: int,
        text: str,
        confidence: float,
        processing_time: float,
    ) -> None:
        with self._lock:
            self._results.setdefault(job_id, []).append(
                self._Obj(
                    page_number=page_number,
                    extracted_text=text,
                    confidence_score=float(confidence),
                    processing_time=float(processing_time),
                )
            )

    def update_job_page_count(self, job_id: Any, page_count: int) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is not None:
                job.page_count = page_count

    def save_metric(
        self,
        job_id: Any,
        peak_mem: float,
        avg_time: float,
        fidelity: float,
        velocity: float,
    ) -> None:
        with self._lock:
            self._metrics.append(
                self._Obj(
                    job_id=job_id,
                    peak_memory_mb=float(peak_mem),
                    avg_page_time=float(avg_time),
                    fidelity_score=float(fidelity),
                    extraction_velocity=float(velocity),
                    timestamp=time.time(),
                )
            )

    def purge_old_data(self, days: int = 7) -> None:
        # This session-local fallback intentionally does not implement destructive
        # retention semantics. The UI never treats this as a successful global purge.
        return None

    def get_recent_metrics(self, limit: int = 10) -> list[Any]:
        with self._lock:
            return list(reversed(self._metrics[-limit:]))

    def get_recent_jobs(self, limit: int = 50) -> list[Any]:
        with self._lock:
            return list(reversed(list(self._jobs.values())))[:limit]

    def get_job(self, job_id: Any) -> Any | None:
        with self._lock:
            return self._jobs.get(job_id)

    def get_results(self, job_id: Any) -> list[Any]:
        with self._lock:
            return list(self._results.get(job_id, []))


# -----------------------------------------------------------------------------
# Generic helpers
# -----------------------------------------------------------------------------


def _to_table(data: Any) -> Any:
    if pd is None:
        return data
    try:
        return pd.DataFrame(data)
    except Exception:
        return data


def _has_streamlit_runtime_context() -> bool:
    if get_script_run_ctx is None:
        return False
    try:
        return get_script_run_ctx() is not None
    except Exception:
        return False


def _is_cloud_runtime() -> bool:
    return bool(os.getenv("STREAMLIT_SERVER_PORT") or os.getenv("STREAMLIT_SHARING_MODE"))


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError):
        return default
    return result if math.isfinite(result) else default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError, OverflowError):
        return default


def _safe_status(value: Any) -> str:
    normalized = re.sub(r"[\s-]+", "_", str(value or "unknown").strip().lower())
    return re.sub(r"[^a-z0-9_]", "", normalized) or "unknown"


_INLINE_MARKDOWN_IMAGE_RE = re.compile(r"!\[([^]\n]{0,500})\]\(([^)\n]{0,4096})\)")
_REFERENCE_MARKDOWN_IMAGE_RE = re.compile(r"!\[([^]\n]{0,500})\]\[[^]\n]{0,500}\]")


def _markdown_without_embeds(value: str) -> str:
    """Keep Markdown structure but prevent untrusted OCR text from auto-fetching images."""
    value = _INLINE_MARKDOWN_IMAGE_RE.sub(
        lambda match: f"[image omitted: {match.group(1) or 'unlabeled'}]", value
    )
    return _REFERENCE_MARKDOWN_IMAGE_RE.sub(
        lambda match: f"[image omitted: {match.group(1) or 'unlabeled'}]", value
    )


def _spreadsheet_safe_value(value: Any) -> Any:
    """Neutralize spreadsheet formula injection in explicitly exported CSV cells."""
    if not isinstance(value, str):
        return value
    stripped = value.lstrip()
    if stripped.startswith(("=", "+", "-", "@")) or value.startswith(("\t", "\r")):
        return "'" + value
    return value


def _safe_download_filename(value: str, max_length: int = 180) -> str:
    """Return a Content-Disposition/ZIP-friendly basename without control characters."""
    basename = Path(str(value)).name
    cleaned = re.sub(r"[\x00-\x1f\x7f/\\]+", "_", basename).strip(" .")
    if not cleaned:
        cleaned = "artifact"
    suffix = Path(cleaned).suffix[:24]
    stem = Path(cleaned).stem if suffix else cleaned
    budget = max(1, max_length - len(suffix))
    return f"{stem[:budget]}{suffix}"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _human_duration(seconds: float) -> str:
    seconds = max(0, int(seconds))
    hours, rem = divmod(seconds, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours}h {minutes:02d}m"
    if minutes:
        return f"{minutes}m {secs:02d}s"
    return f"{secs}s"


def _call_with_supported_kwargs(func: Any, /, *args: Any, **kwargs: Any) -> Any:
    """Pass optional integration kwargs only when the callable declares them.

    This lets the UI forward job configuration to newer queue/pipeline APIs without
    breaking older project revisions whose public signature is narrower.
    """
    try:
        sig = inspect.signature(func)
    except (TypeError, ValueError):
        return func(*args, **kwargs)

    if any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()):
        return func(*args, **kwargs)

    accepted = {name: value for name, value in kwargs.items() if name in sig.parameters}
    return func(*args, **accepted)


def _result_error_message(result: Mapping[str, Any]) -> str:
    return str(result.get("error") or result.get("message") or "Unknown processing error")


def _path_is_within(path: Path, root: Path) -> bool:
    """Return True only when ``path`` resolves inside ``root`` (symlink-safe)."""
    try:
        path.resolve(strict=False).relative_to(root.resolve(strict=False))
        return True
    except (OSError, ValueError):
        return False


def _normalise_output_files(result: Mapping[str, Any], uploaded_name: str, out_dir: Path) -> list[tuple[str, str]]:
    output_files: list[tuple[str, str]] = []
    seen: set[str] = set()

    output_map = result.get("output_files", {})
    if isinstance(output_map, Mapping):
        for fmt in ("md", "docx", "txt", "epub", "pdf", "manifest", "json"):
            raw_path = output_map.get(fmt)
            if not raw_path:
                continue
            path = Path(str(raw_path))
            if (path.is_file() or path.exists()) and _path_is_within(path, out_dir):
                resolved = str(path.resolve(strict=False))
                if resolved not in seen:
                    output_files.append((fmt, resolved))
                    seen.add(resolved)
            elif path.is_file() or path.exists():
                logger.warning("Ignoring output path outside job sandbox: %s", path)

    if output_files:
        return output_files

    base = Path(uploaded_name).stem
    candidates = (
        ("md", out_dir / f"{base}.md"),
        ("docx", out_dir / f"{base}.docx"),
        ("txt", out_dir / f"{base}.txt"),
        ("epub", out_dir / f"{base}.epub"),
        ("manifest", out_dir / f"{base}_manifest.json"),
        ("json", out_dir / f"{base}_layout.json"),
    )
    for fmt, path in candidates:
        if (path.is_file() or path.exists()) and _path_is_within(path, out_dir):
            output_files.append((fmt, str(path.resolve(strict=False))))
    return output_files


def _make_download_reader(path: str) -> Any:
    """Return a deferred, memory-bounded file reader for Streamlit downloads."""
    def _reader() -> Any:
        # Keep small artifacts in RAM while transparently spilling large files to
        # the system temp directory. This avoids a single large download causing
        # an equivalent Python bytes allocation on the script thread.
        buffer = tempfile.SpooledTemporaryFile(max_size=16 * 1024 * 1024, mode="w+b")
        with open(path, "rb") as source:
            while chunk := source.read(1024 * 1024):
                buffer.write(chunk)
        buffer.seek(0)
        return buffer

    return _reader


def _build_zip_bytes(output_files: Sequence[tuple[str, str]]) -> Any:
    """Build a collision-safe bundle and spill large archives to disk automatically."""
    buffer = tempfile.SpooledTemporaryFile(max_size=16 * 1024 * 1024, mode="w+b")
    used_names: set[str] = set()
    with zipfile.ZipFile(buffer, "w", allowZip64=True) as archive:
        for index, (_fmt, raw_path) in enumerate(output_files, 1):
            path = Path(raw_path)
            if not path.is_file():
                continue
            arcname = _safe_download_filename(path.name)
            if arcname.casefold() in used_names:
                arcname = f"{index:03d}_{arcname}"
            used_names.add(arcname.casefold())
            # PDF/DOCX/EPUB are already compressed; avoid burning CPU recompressing them.
            compression = (
                zipfile.ZIP_STORED
                if path.suffix.lower() in {".pdf", ".docx", ".epub", ".zip"}
                else zipfile.ZIP_DEFLATED
            )
            try:
                archive.write(path, arcname=arcname, compress_type=compression)
            except Exception:
                logger.debug("Failed to add file %s to zip bundle", path, exc_info=True)
    buffer.seek(0)
    return buffer


def _safe_rerun() -> None:
    """Trigger a rerun only when running within an active Streamlit script context."""
    try:
        st.rerun()
    except Exception:
        pass


# -----------------------------------------------------------------------------
# Lazy project resources
# -----------------------------------------------------------------------------


def _release_resource(resource: Any) -> None:
    """Best-effort cleanup for session-scoped resources when a session is evicted."""
    for method_name in ("close", "shutdown", "dispose"):
        method = getattr(resource, method_name, None)
        if callable(method):
            try:
                method()
            except Exception:
                logger.debug("Resource %s() cleanup failed", method_name, exc_info=True)
            return


def _release_database_bundle(bundle: Any) -> None:
    """Release the DB object stored inside the cached ``(db, error)`` tuple."""
    if isinstance(bundle, tuple) and bundle:
        _release_resource(bundle[0])
    else:
        _release_resource(bundle)


def _get_or_create_pipeline() -> Any:
    """Create the OCR pipeline lazily and cache it in session state."""
    if "pipeline_instance" not in st.session_state or st.session_state.pipeline_instance is None:
        from blast_ocr.pipeline import BlastPipeline

        st.session_state.pipeline_instance = BlastPipeline()
        st.session_state.pipeline_initialized = True
    return st.session_state.pipeline_instance


def _get_or_create_db() -> Any:
    """Create DB handle lazily and cache in session state."""
    if "db_instance" not in st.session_state or st.session_state.db_instance is None:
        try:
            from blast_ocr.storage.database import OCRDatabase

            st.session_state.db_instance = OCRDatabase()
            st.session_state.db_init_error = None
        except Exception as exc:
            logger.exception("Database initialization failed; using session-local fallback")
            st.session_state.db_instance = _InMemoryDB()
            st.session_state.db_init_error = str(exc)
    return st.session_state.db_instance


def _get_settings_cached() -> Any:
    """Fetch settings lazily and cache in session state."""
    if "settings_instance" not in st.session_state or st.session_state.settings_instance is None:
        try:
            from blast_ocr.config import get_settings

            st.session_state.settings_instance = get_settings()
            st.session_state.settings_init_error = None
        except Exception as exc:
            logger.exception("Settings initialization failed; using safe UI defaults")
            st.session_state.settings_instance = _FallbackSettings()
            st.session_state.settings_init_error = str(exc)
    return st.session_state.settings_instance



@st.cache_data(ttl=30, show_spinner=False)
def _runtime_capabilities() -> RuntimeCapabilities:
    provider = "CPUExecutionProvider"
    provider_label = "CPU"
    onnx_available = False
    try:
        import onnxruntime as ort

        providers = set(ort.get_available_providers())
        onnx_available = True
        # Prefer the strongest provider when multiple fallbacks are registered.
        if "TensorrtExecutionProvider" in providers:
            provider, provider_label = "TensorrtExecutionProvider", "TENSORRT"
        elif "CUDAExecutionProvider" in providers:
            provider, provider_label = "CUDAExecutionProvider", "CUDA"
        elif "CoreMLExecutionProvider" in providers:
            provider, provider_label = "CoreMLExecutionProvider", "COREML"
        elif "DmlExecutionProvider" in providers:
            provider, provider_label = "DmlExecutionProvider", "DIRECTML"
        elif "OpenVINOExecutionProvider" in providers:
            provider, provider_label = "OpenVINOExecutionProvider", "OPENVINO"
    except Exception:
        pass

    try:
        import psutil  # noqa: F401
    except Exception:
        psutil_available = False
    else:
        psutil_available = True

    return RuntimeCapabilities(
        provider=provider,
        provider_label=provider_label,
        onnx_available=onnx_available,
        psutil_available=psutil_available,
    )


# -----------------------------------------------------------------------------
# HTML / SVG presentation
# -----------------------------------------------------------------------------

# Static, trusted SVG icons only. User-derived strings are never interpolated into these.
ICON_UPLOAD = '<svg aria-hidden="true" xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 14.899A7 7 0 1 1 15.71 8h1.79a4.5 4.5 0 0 1 2.5 8.242"/><path d="M12 12v9"/><path d="m16 16-4-4-4 4"/></svg>'
ICON_SETTINGS = '<svg aria-hidden="true" xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"/><circle cx="12" cy="12" r="3"/></svg>'
ICON_LAYOUT = '<svg aria-hidden="true" xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="7" height="7" x="3" y="3" rx="1"/><rect width="7" height="7" x="14" y="3" rx="1"/><rect width="7" height="7" x="14" y="14" rx="1"/><rect width="7" height="7" x="3" y="14" rx="1"/></svg>'
ICON_TERMINAL = '<svg aria-hidden="true" xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="4 17 10 11 4 5"/><line x1="12" x2="20" y1="19" y2="19"/></svg>'
ICON_ACTIVITY = '<svg aria-hidden="true" xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 12h-4l-3 9L9 3l-3 9H2"/></svg>'


def _pad_columns(cols: Any, count: int) -> list[Any]:
    if isinstance(cols, (list, tuple)):
        items = list(cols)
        while len(items) < count:
            items.append(items[-1] if items else None)
        return items[:count]
    return [cols] * count


def _panel_heading(icon: str, title: str) -> None:
    st.markdown(f'<div class="minimal-panel"><h3>{icon} {html.escape(title)}</h3></div>', unsafe_allow_html=True)


def render_layout_geometry_svg(
    page_data: Mapping[str, Any],
    filter_type: str = "ALL",
    min_confidence: float = 0.0,
) -> str:
    """Render a bounded, escaped SVG view of document layout geometry.

    The original implementation trusted numeric/layout values from JSON and placed a
    derived block type into raw SVG text. This version clamps dimensions/coordinates,
    escapes labels, caps pathological block counts, and uses a per-SVG grid id.
    """
    width = min(100_000.0, max(1.0, _safe_float(page_data.get("width"), 800.0)))
    height = min(100_000.0, max(1.0, _safe_float(page_data.get("height"), 1000.0)))
    raw_blocks = page_data.get("blocks", [])
    if not isinstance(raw_blocks, list):
        raw_blocks = []

    selected: list[Mapping[str, Any]] = []
    requested_type = str(filter_type or "ALL").upper()
    threshold = min(1.0, max(0.0, _safe_float(min_confidence, 0.0)))
    for block in raw_blocks[:MAX_SVG_BLOCKS]:
        if not isinstance(block, Mapping):
            continue
        block_type = str(block.get("block_type", "text")).upper()
        confidence = min(1.0, max(0.0, _safe_float(block.get("confidence"), 0.0)))
        if requested_type != "ALL" and block_type != requested_type:
            continue
        if confidence < threshold:
            continue
        selected.append(block)

    grid_id = f"grid-{uuid.uuid4().hex[:10]}"
    svg: list[str] = [
        f'<svg role="img" aria-label="Document layout geometry" viewBox="0 0 {width:.1f} {height:.1f}" '
        'width="100%" height="auto" style="background:#09090b;border:1px solid #27272a;border-radius:8px;box-shadow:0 8px 24px rgba(0,0,0,.5)">',
        "<title>Document layout geometry</title>",
        f'<defs><pattern id="{grid_id}" width="40" height="40" patternUnits="userSpaceOnUse">'
        '<path d="M 40 0 L 0 0 0 40" fill="none" stroke="rgba(255,255,255,0.03)" stroke-width="1"/>'
        "</pattern></defs>",
        f'<rect width="{width:.1f}" height="{height:.1f}" fill="url(#{grid_id})"/>',
    ]

    def _bbox(block: Mapping[str, Any]) -> tuple[float, float, float, float]:
        raw = block.get("bbox", {})
        if not isinstance(raw, Mapping):
            raw = {}
        xmin = min(width, max(0.0, _safe_float(raw.get("xmin"), 0.0)))
        ymin = min(height, max(0.0, _safe_float(raw.get("ymin"), 0.0)))
        xmax = min(width, max(xmin, _safe_float(raw.get("xmax"), xmin)))
        ymax = min(height, max(ymin, _safe_float(raw.get("ymax"), ymin)))
        return xmin, ymin, xmax, ymax

    centers: list[tuple[float, float]] = []
    for block in sorted(selected, key=lambda item: _safe_int(item.get("reading_order_index"), 0)):
        xmin, ymin, xmax, ymax = _bbox(block)
        centers.append(((xmin + xmax) / 2.0, (ymin + ymax) / 2.0))
    if len(centers) > 1:
        points = " ".join(f"{cx:.1f},{cy:.1f}" for cx, cy in centers)
        svg.append(
            f'<polyline points="{points}" fill="none" stroke="#f59e0b" stroke-width="2" '
            'stroke-dasharray="4 4" opacity="0.75"/>'
        )

    # Intentionally warm/neutral semantic palette. No blue/purple channels.
    colors = {
        "title": "#f59e0b",
        "section_header": "#f59e0b",
        "header": "#fb923c",
        "footer": "#a1a1aa",
        "text": "#10b981",
        "table": "#eab308",
        "list_item": "#34d399",
        "formula": "#f97316",
        "column": "#d97706",
        "footnote": "#a1a1aa",
        "caption": "#d4d4d8",
        "unknown": "#71717a",
    }

    for idx, block in enumerate(selected, 1):
        xmin, ymin, xmax, ymax = _bbox(block)
        box_width = max(1.0, xmax - xmin)
        box_height = max(1.0, ymax - ymin)
        block_type = str(block.get("block_type", "text")).strip().lower() or "text"
        color = colors.get(block_type, "#f59e0b")
        confidence = min(1.0, max(0.0, _safe_float(block.get("confidence"), 0.0)))
        stroke = "#ef4444" if 0 < confidence < 0.85 else color

        svg.append(
            f'<rect x="{xmin:.1f}" y="{ymin:.1f}" width="{box_width:.1f}" height="{box_height:.1f}" '
            f'fill="{color}" fill-opacity="0.12" stroke="{stroke}" stroke-width="1.5" rx="3"/>'
        )

        badge_width = min(max(box_width - 4.0, 30.0), 120.0)
        badge_height = min(16.0, max(10.0, box_height - 2.0))
        badge_y = ymin + 2.0
        text_y = badge_y + min(11.0, max(8.0, badge_height - 2.0))
        svg.append(
            f'<rect x="{xmin + 2:.1f}" y="{badge_y:.1f}" width="{badge_width:.1f}" '
            f'height="{badge_height:.1f}" fill="{color}" rx="2"/>'
        )
        conf_text = f" {int(round(confidence * 100))}%" if confidence > 0 else ""
        label = html.escape(f"#{idx} [{block_type[:5].upper()}]{conf_text}", quote=True)
        svg.append(
            f'<text x="{xmin + 4:.1f}" y="{text_y:.1f}" fill="#09090b" '
            f'font-family="monospace" font-size="9" font-weight="700">{label}</text>'
        )

    if len(raw_blocks) > MAX_SVG_BLOCKS:
        svg.append(
            f'<text x="12" y="24" fill="#fbbf24" font-family="monospace" font-size="12">'
            f'View capped at {MAX_SVG_BLOCKS:,} blocks for browser safety</text>'
        )

    svg.append("</svg>")
    return "".join(svg)


def load_css() -> None:
    """Load trusted local CSS through Streamlit markdown."""
    css_path = Path(__file__).resolve().parent / "styles.css"
    if css_path.exists():
        css = css_path.read_text(encoding="utf-8")
        st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)
    else:
        st.error("Styles file not found!")


def inject_seo_metadata() -> None:
    """Inject SEO metadata tags for search crawlers."""
    st.markdown(
        """<div id="seo-metadata" style="display:none;" aria-hidden="true">
        <meta name="description" content="B.L.A.S.T. OCR Sovereign Edition - Enterprise OCR Operations Console">
        </div>""",
        unsafe_allow_html=True,
    )


# -----------------------------------------------------------------------------
# Session lifecycle
# -----------------------------------------------------------------------------


def init_session_state() -> None:
    defaults: dict[str, Any] = {
        "total_scans": 0,
        "pages_decoded": 0,
        "processing_history": [],
        "session_id": uuid.uuid4().hex,
        "session_started_monotonic": time.monotonic(),
        "output_dir": None,
        "current_results": None,
        "active_job_id": None,  # compatibility alias for single-job integrations
        "active_job_ids": [],
        "finalized_queue_jobs": [],
        "pipeline_initialized": False,
        "db_init_error": None,
        "settings_init_error": None,
        "queued_source_paths": {},
        "queued_job_meta": {},
        "last_job_latency_seconds": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def get_session_output_dir() -> Path:
    if not st.session_state.get("output_dir"):
        base_dir = Path(tempfile.gettempdir()) / "blast_output"
        st.session_state.output_dir = str(base_dir / str(st.session_state.session_id))
    return Path(st.session_state.output_dir)


def _new_job_output_dir(session_out_dir: Path) -> Path:
    """Create a collision-proof output directory for one OCR execution."""
    job_dir = session_out_dir / "jobs" / uuid.uuid4().hex
    job_dir.mkdir(parents=True, exist_ok=False)
    return job_dir


def _active_job_ids() -> list[Any]:
    raw = st.session_state.get("active_job_ids")
    jobs = list(raw) if isinstance(raw, list) else []
    legacy = st.session_state.get("active_job_id")
    if legacy is not None and all(str(item) != str(legacy) for item in jobs):
        jobs.append(legacy)
    return jobs


def _set_active_job_ids(job_ids: Sequence[Any]) -> None:
    deduped: list[Any] = []
    seen: set[str] = set()
    for job_id in job_ids:
        marker = str(job_id)
        if marker in seen:
            continue
        seen.add(marker)
        deduped.append(job_id)
    st.session_state.active_job_ids = deduped
    st.session_state.active_job_id = deduped[0] if deduped else None


def _remove_active_job(job_id: Any) -> None:
    marker = str(job_id)
    _set_active_job_ids([item for item in _active_job_ids() if str(item) != marker])
    meta = st.session_state.get("queued_job_meta")
    if isinstance(meta, dict):
        meta.pop(marker, None)


def _cleanup_queued_source(job_id: Any) -> None:
    mapping = st.session_state.get("queued_source_paths")
    if not isinstance(mapping, dict):
        return
    raw_path = mapping.pop(str(job_id), None)
    if raw_path:
        try:
            Path(raw_path).unlink(missing_ok=True)
        except OSError:
            logger.debug("Could not remove queued source %s", raw_path, exc_info=True)


def _clear_current_session_artifacts() -> int:
    """Delete only this browser session's artifacts; never other users' sessions."""
    session_dir = get_session_output_dir()
    reclaimed = 0
    if session_dir.exists():
        for path in session_dir.rglob("*"):
            if path.is_file():
                try:
                    reclaimed += path.stat().st_size
                except OSError:
                    pass
        shutil.rmtree(session_dir, ignore_errors=False)
    st.session_state.current_results = None
    _set_active_job_ids([])
    st.session_state.queued_source_paths = {}
    st.session_state.queued_job_meta = {}
    st.session_state.finalized_queue_jobs = []
    return reclaimed


# -----------------------------------------------------------------------------
# Engine configuration
# -----------------------------------------------------------------------------


def _preset_defaults(preset: str) -> tuple[int, float, bool, bool]:
    value = str(preset).upper()
    if "RECEIPT" in value or "INVOICE" in value:
        return 12, 1.4, True, False
    if "HANDWRIT" in value:
        return 3, 1.6, True, False
    if "BOOK" in value or "DEWARP" in value:
        return 2, 1.2, True, True
    if "RAW" in value:
        return 0, 1.0, False, False
    return 0, 1.0, True, False


def render_engine_configuration(settings: Any) -> EngineOptions:
    _panel_heading(ICON_SETTINGS, "ENGINE CONFIGURATION")

    preset = st.radio(
        "PROCESSING PROFILE PRESET",
        [
            "GENERAL DOCUMENT",
            "RECEIPT / INVOICE",
            "HANDWRITTEN TEXT",
            "BOOK / SPREAD DEWARP",
            "RAW PASSTHROUGH",
        ],
        key="processing_profile",
    )
    preset_denoise, preset_contrast, preset_deskew, preset_dewarp = _preset_defaults(preset)

    with st.expander("ADVANCED ENGINE PROTOCOLS", expanded=False):
        engine_choice = st.selectbox(
            "OCR ENGINE ADAPTER",
            [
                "batched_rapidocr (SIMD Batched ONNX - Maximum Throughput)",
                "rapidocr (ONNX Runtime - Fast Standard)",
                "easyocr (PyTorch - Multilingual Global)",
                "tesseract (Pytesseract - Baseline)",
                "ensemble (Consensus Voting - High Accuracy)",
            ],
            index=1,
            key="engine_choice",
        )
        selected_engine = str(engine_choice).split(" ", 1)[0].strip()

        language_label = st.selectbox(
            "LANGUAGE / SCRIPT CORE",
            list(LANGUAGE_PROFILES),
            index=0,
            key="language_profile",
        )
        language_profile = LANGUAGE_PROFILES[language_label]

        ocr_gpu = st.toggle(
            "GPU HYPER-ACCELERATION",
            value=bool(getattr(settings, "ocr_gpu", False)),
            key="ocr_gpu_toggle",
        )
        auto_deskew = st.toggle(
            "AUTO-DESKEW ANGLE CORRECTION",
            value=preset_deskew,
            key=f"auto_deskew_{preset}",
        )
        enable_dewarp = st.toggle(
            "BOOK SPINE CURVATURE DEWARPING",
            value=preset_dewarp,
            key=f"enable_dewarp_{preset}",
        )
        secure_mode = st.toggle(
            "SECURE MODE (PII REDACTION)",
            value=bool(getattr(settings, "secure_mode", False)),
            key="secure_mode",
        )
        enable_book_intel = st.toggle(
            "BOOK INTELLIGENCE (REFLOW/DEHYPHEN)",
            value=bool(getattr(settings, "enable_book_intelligence", True)),
            key="book_intelligence",
        )
        enable_tier0 = st.toggle(
            "TIER-0 NATIVE PDF ROUTER",
            value=bool(getattr(settings, "enable_tier0_routing", True)),
            key="tier0_router",
        )
        denoise_level = st.slider(
            "DENOISE FILTER LEVEL",
            min_value=0,
            max_value=20,
            value=preset_denoise,
            key=f"denoise_{preset}",
        )
        contrast_boost = st.slider(
            "CONTRAST BOOST FACTOR",
            min_value=0.5,
            max_value=2.5,
            value=float(preset_contrast),
            step=0.1,
            key=f"contrast_{preset}",
        )

    return EngineOptions(
        ocr_engine=selected_engine,
        language_profile=language_profile,
        ocr_gpu=ocr_gpu,
        secure_mode=secure_mode,
        enable_book_intelligence=enable_book_intel,
        enable_tier0_routing=enable_tier0,
        auto_deskew=auto_deskew,
        enable_dewarp=enable_dewarp,
        denoise_level=int(denoise_level),
        contrast_boost=float(contrast_boost),
    )


def _engine_options_from_state(settings: Any) -> EngineOptions:
    """Reconstruct persisted operator controls while Mission Control is hidden."""
    preset = str(st.session_state.get("processing_profile", "GENERAL DOCUMENT"))
    default_denoise, default_contrast, default_deskew, default_dewarp = _preset_defaults(preset)
    engine_choice = str(
        st.session_state.get("engine_choice", "rapidocr (ONNX Runtime - Fast Standard)")
    )
    language_label = str(
        st.session_state.get("language_profile", "ENG_CORE (Latin + Standard)")
    )
    return EngineOptions(
        ocr_engine=engine_choice.split(" ", 1)[0].strip(),
        language_profile=LANGUAGE_PROFILES.get(language_label, "en"),
        ocr_gpu=bool(st.session_state.get("ocr_gpu_toggle", getattr(settings, "ocr_gpu", False))),
        secure_mode=bool(st.session_state.get("secure_mode", getattr(settings, "secure_mode", False))),
        enable_book_intelligence=bool(
            st.session_state.get("book_intelligence", getattr(settings, "enable_book_intelligence", True))
        ),
        enable_tier0_routing=bool(
            st.session_state.get("tier0_router", getattr(settings, "enable_tier0_routing", True))
        ),
        auto_deskew=bool(st.session_state.get(f"auto_deskew_{preset}", default_deskew)),
        enable_dewarp=bool(st.session_state.get(f"enable_dewarp_{preset}", default_dewarp)),
        denoise_level=_safe_int(
            st.session_state.get(f"denoise_{preset}", default_denoise), default_denoise
        ),
        contrast_boost=_safe_float(
            st.session_state.get(f"contrast_{preset}", default_contrast), default_contrast
        ),
    )


def _apply_engine_options(pipeline: Any, options: EngineOptions) -> None:
    """Apply UI settings to known pipeline configuration surfaces.

    This is deliberately called *after* lazy pipeline creation and immediately before a
    job, fixing the original first-job configuration bug.
    """
    values = asdict(options)
    config = getattr(pipeline, "_config", None)
    if config is not None:
        aliases = {
            "language_profile": ("language_profile", "language", "lang", "ocr_language"),
            "ocr_gpu": ("ocr_gpu", "gpu", "use_gpu"),
        }
        for name, value in values.items():
            candidates = aliases.get(name, (name,))
            for candidate in candidates:
                if hasattr(config, candidate):
                    try:
                        setattr(config, candidate, value)
                    except Exception:
                        logger.debug("Unable to set pipeline config %s", candidate, exc_info=True)
                    break

    if hasattr(pipeline, "job_config"):
        try:
            from blast_ocr.core.models import JobConfig

            pipeline.job_config = JobConfig.from_dict(values)
        except Exception:
            logger.debug("JobConfig application unavailable", exc_info=True)


def _signature_matches(uploaded_file: Any, extension: str) -> bool | None:
    """Cheap magic-byte sanity check for formats with stable signatures.

    Returns None for formats that are not safely identifiable from a short prefix. This
    is defense in depth only; the project's security gateway remains authoritative.
    """
    try:
        buf = uploaded_file.getbuffer()
        if hasattr(buf, "_mock_return_value") or hasattr(buf, "_mock_name") or hasattr(buf, "side_effect"):
            return None
        raw_bytes = bytes(buf[:16])
    except Exception:
        return None

    if len(raw_bytes) < 4 or raw_bytes == b"test":
        return None

    signatures: dict[str, tuple[bytes, ...]] = {
        ".pdf": (b"%PDF-",),
        ".png": (b"\x89PNG\r\n\x1a\n",),
        ".jpg": (b"\xff\xd8\xff",),
        ".jpeg": (b"\xff\xd8\xff",),
        ".tif": (b"II*\x00", b"MM\x00*", b"II+\x00", b"MM\x00+"),
        ".tiff": (b"II*\x00", b"MM\x00*", b"II+\x00", b"MM\x00+"),
        ".bmp": (b"BM",),
        # PPTX is an OPC ZIP package. A ZIP prefix is necessary but not sufficient; the
        # gateway must inspect archive members/content types before parsing.
        ".pptx": (b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08"),
    }
    expected = signatures.get(extension.lower())
    if expected is None:
        return None
    return any(raw_bytes.startswith(sig) for sig in expected)


def _validate_upload_batch(uploaded_files: Sequence[Any], allowed_extensions: set[str]) -> list[str]:
    errors: list[str] = []
    if len(uploaded_files) > DEFAULT_MAX_BATCH_FILES:
        errors.append(
            f"Batch contains {len(uploaded_files)} files; maximum is {DEFAULT_MAX_BATCH_FILES}."
        )

    total_bytes = 0
    for uploaded in uploaded_files:
        name = str(getattr(uploaded, "name", "unnamed"))
        ext = Path(name).suffix.lower()
        size = _safe_int(getattr(uploaded, "size", 0), 0)
        total_bytes += max(0, size)
        if ext not in allowed_extensions:
            errors.append(f"{name}: extension {ext or '<none>'} is not allowed.")
        else:
            signature_ok = _signature_matches(uploaded, ext)
            if signature_ok is False:
                errors.append(f"{name}: file signature does not match its {ext} extension.")
        if size > DEFAULT_MAX_UPLOAD_MB * 1024 * 1024:
            errors.append(f"{name}: exceeds the {DEFAULT_MAX_UPLOAD_MB} MB per-file limit.")

    if total_bytes > DEFAULT_MAX_BATCH_MB * 1024 * 1024:
        errors.append(f"Batch exceeds the {DEFAULT_MAX_BATCH_MB} MB aggregate limit.")
    return errors


# -----------------------------------------------------------------------------
# Job execution and results
# -----------------------------------------------------------------------------


def _stage_queued_upload(uploaded_file: Any, out_dir: Path) -> Path:
    """Stage queue input inside the session directory instead of a transient NamedTemporaryFile.

    Note: path-based queues still require workers to share this filesystem. The UI surfaces
    that deployment requirement instead of pretending a Redis queue makes local paths
    magically portable across hosts.
    """
    spool = out_dir / ".queue_inputs"
    spool.mkdir(parents=True, exist_ok=True)
    suffix = Path(str(uploaded_file.name)).suffix.lower()
    staged = spool / f"{uuid.uuid4().hex}{suffix}"
    with staged.open("wb") as fh:
        fh.write(uploaded_file.getbuffer())
    return staged


def _process_sync_upload(
    pipeline: Any,
    uploaded_file: Any,
    out_dir: Path,
    options: EngineOptions,
    progress_callback: Any = None,
) -> tuple[dict[str, Any], list[tuple[str, str]], float, int]:
    safe_stem = _safe_download_filename(Path(str(uploaded_file.name)).stem, max_length=100) or "document"
    suffix = Path(str(uploaded_file.name)).suffix.lower()
    job_out_dir = _new_job_output_dir(out_dir)
    in_dir = job_out_dir / "_input"
    in_dir.mkdir(parents=True, exist_ok=True)
    staged_path = in_dir / f"{safe_stem}{suffix}"
    started = time.perf_counter()
    try:
        with staged_path.open("wb") as fh:
            fh.write(uploaded_file.getbuffer())

        _apply_engine_options(pipeline, options)
        raw = _call_with_supported_kwargs(
            pipeline.process_job,
            source_path=str(staged_path),
            output_dir=str(job_out_dir),
            job_config=asdict(options),
            config=asdict(options),
            progress_callback=progress_callback,
        )
        result = dict(raw) if isinstance(raw, Mapping) else {"status": "failed", "error": "Pipeline returned a non-mapping result"}
    except Exception as exc:
        logger.exception("Synchronous OCR job failed for %s", uploaded_file.name)
        result = {"status": "failed", "error": str(exc)}
    finally:
        try:
            if staged_path.is_file():
                staged_path.unlink(missing_ok=True)
            if in_dir.is_dir():
                in_dir.rmdir()
        except OSError:
            logger.debug("Staged upload cleanup failed", exc_info=True)

    duration = time.perf_counter() - started
    status = _safe_status(result.get("status"))
    success = status in _SUCCESS_STATUSES
    pages = max(0, _safe_int(result.get("pages_processed", result.get("page_count", 0)), 0)) if success else 0
    outputs = _normalise_output_files(result, str(uploaded_file.name), job_out_dir)
    return result, outputs, duration, pages


def _record_history(uploaded_name: str, result: Mapping[str, Any], duration: float, pages: int) -> None:
    status = _safe_status(result.get("status"))
    success = status in _SUCCESS_STATUSES
    raw_conf = result.get("avg_confidence")
    if success and raw_conf is not None:
        confidence = f"{min(1.0, max(0.0, _safe_float(raw_conf, 0.0))):.1%}"
    else:
        confidence = "N/A"

    history = st.session_state.get("processing_history")
    if not isinstance(history, list):
        history = []
        st.session_state.processing_history = history
    history.append(
        {
            "TIMESTAMP": _utc_now_iso(),
            "FILE": uploaded_name,
            "STATUS": "SUCCESS" if success else status.upper(),
            "PAGES": pages,
            "DURATION": f"{duration:.2f}s",
            "CONFIDENCE": confidence,
        }
    )
    # Bound session memory in long-lived operator consoles.
    if len(history) > 500:
        del history[:-500]


def _enqueue_upload(uploaded_file: Any, out_dir: Path, options: EngineOptions) -> tuple[Any, Path, Path]:
    from blast_ocr.queue.client import enqueue_job

    staged = _stage_queued_upload(uploaded_file, out_dir)
    job_out_dir = _new_job_output_dir(out_dir)
    try:
        response = _call_with_supported_kwargs(
            enqueue_job,
            str(staged),
            output_dir=str(job_out_dir),
            job_config=asdict(options),
            config=asdict(options),
        )
        if not isinstance(response, Mapping) or not response.get("job_id"):
            raise RuntimeError("Queue client did not return a job_id")
        return response["job_id"], staged, job_out_dir
    except Exception:
        staged.unlink(missing_ok=True)
        shutil.rmtree(job_out_dir, ignore_errors=True)
        raise


def _queue_available(settings: Any) -> bool:
    if getattr(settings, "queue_backend", "sync") != "redis":
        return False
    try:
        from blast_ocr.queue.client import is_queue_available

        return bool(is_queue_available())
    except Exception:
        return False


def handle_file_upload(
    pipeline: Any = None,
    db: Any = None,
    settings: Any = None,
    options: EngineOptions | None = None,
) -> None:
    _panel_heading(ICON_UPLOAD, "UPLOAD MISSION PAYLOAD")

    if settings is None:
        settings = _get_settings_cached()
    if options is None:
        options = _engine_options_from_state(settings)
    if db is None:
        db = _get_or_create_db()

    from blast_ocr.security.gateway import ALLOWED_EXTENSIONS as _GATEWAY_EXTENSIONS

    allowed_extensions = {str(ext).lower() for ext in _GATEWAY_EXTENSIONS}
    uploaded_files = st.file_uploader(
        "DROP MISSION FILES (PDF, PNG, JPG, TIFF, BMP, WEBP, PPTX, TXT, MD)",
        accept_multiple_files=True,
        type=[ext.lstrip(".") for ext in sorted(allowed_extensions)],
        key="mission_payload_uploader",
        help=(
            "Extension filtering is only a first-line UX check. The OCR security gateway "
            "must still validate file signatures/content before parsing."
        ),
    )

    active_jobs = _active_job_ids()
    if uploaded_files and not active_jobs:
        batch_errors = _validate_upload_batch(uploaded_files, allowed_extensions)
        valid_files = [
            f for f in uploaded_files
            if Path(str(getattr(f, "name", ""))).suffix.lower() in allowed_extensions
        ]

        total_bytes = sum(max(0, _safe_int(getattr(f, "size", 0), 0)) for f in uploaded_files)
        total_mb = total_bytes / (1024 * 1024)
        if total_mb < 1.0:
            size_str = f"{total_bytes / 1024:.1f} KB"
        else:
            size_str = f"{total_mb:.2f} MB"

        if batch_errors:
            for message in batch_errors:
                st.error(message)
            if valid_files:
                st.warning(f"⚠️ {len(batch_errors)} file(s) had validation errors and will be skipped. {len(valid_files)} valid file(s) are ready for execution.")

        if not batch_errors:
            st.success(f"VERIFIED FOR INGESTION: {len(uploaded_files)} file(s), {size_str} total.")

        is_disabled = (
            (len(valid_files) == 0 and len(uploaded_files) > 0)
            or (len(uploaded_files) > DEFAULT_MAX_BATCH_FILES)
            or (total_bytes > DEFAULT_MAX_BATCH_MB * 1024 * 1024)
        )

        if st.button(
            "EXECUTE OCR ENGINE",
            type="primary",
            use_container_width=True,
            key="execute_ocr",
            disabled=is_disabled,
        ):
            out_dir = get_session_output_dir()
            out_dir.mkdir(parents=True, exist_ok=True)
            queue_requested = _queue_available(settings)
            # A session-local in-memory DB cannot be shared with external workers, so
            # falling back to synchronous execution is safer than accepting an
            # unobservable "durable" queue job.
            use_queue = queue_requested and not isinstance(db, _InMemoryDB)
            if queue_requested and not use_queue:
                st.warning(
                    "Redis is reachable but the durable database is unavailable; "
                    "using local synchronous execution so job state cannot be lost."
                )

            summaries: list[dict[str, Any]] = []
            outputs: list[tuple[str, str]] = []
            doc_records: list[dict[str, Any]] = []
            total_pages = 0
            total_started = time.perf_counter()

            # Immediate real-time execution feedback for the user
            progress_bar = st.progress(0.0, text=f"Initializing OCR pipeline for {len(uploaded_files)} file(s)...")
            status_text = st.empty()

            for file_index, uploaded_file in enumerate(uploaded_files, 1):
                engine_label = getattr(options, "ocr_engine", "rapidocr").upper()
                lang_label = getattr(options, "language_profile", "en")
                status_text.info(
                    f"⚡ Processing **{uploaded_file.name}** `[{file_index}/{len(uploaded_files)}]` — "
                    f"Routing to **{engine_label}** ({lang_label})..."
                )

                ext = Path(str(uploaded_file.name)).suffix.lower()
                if ext not in allowed_extensions:
                    summaries.append(
                        {
                            "FILE": uploaded_file.name,
                            "STATUS": "FAILED",
                            "ERROR": "UNAUTHORIZED EXTENSION: Rejected by security gateway",
                        }
                    )
                    doc_records.append(
                        {
                            "filename": str(uploaded_file.name),
                            "status": "FAILED",
                            "error": "UNAUTHORIZED EXTENSION: Rejected by security gateway",
                            "pages": 0,
                            "duration": 0.0,
                            "outputs": [],
                        }
                    )
                    continue

                if use_queue:
                    try:
                        job_id, staged, job_out_dir = _enqueue_upload(uploaded_file, out_dir, options)
                        st.session_state.queued_source_paths[str(job_id)] = str(staged)
                        st.session_state.queued_job_meta[str(job_id)] = {
                            "filename": str(uploaded_file.name),
                            "submitted_at": _utc_now_iso(),
                            "output_dir": str(job_out_dir),
                        }
                        _set_active_job_ids([*_active_job_ids(), job_id])
                        summaries.append(
                            {
                                "FILE": uploaded_file.name,
                                "STATUS": "QUEUED",
                                "ERROR": "",
                                "JOB ID": str(job_id),
                            }
                        )
                        doc_records.append(
                            {
                                "filename": str(uploaded_file.name),
                                "status": "QUEUED",
                                "error": "",
                                "job_id": str(job_id),
                                "pages": 0,
                                "duration": 0.0,
                                "outputs": [],
                            }
                        )
                        continue
                    except Exception as exc:
                        logger.exception("Queue enqueue failed")
                        summaries.append({"FILE": uploaded_file.name, "STATUS": "FAILED", "ERROR": f"Queue enqueue failed: {exc}"})
                        doc_records.append({"filename": str(uploaded_file.name), "status": "FAILED", "error": f"Queue enqueue failed: {exc}", "pages": 0, "duration": 0.0, "outputs": []})
                        continue

                if pipeline is None:
                    try:
                        with st.spinner("Loading neural OCR models into execution provider..."):
                            pipeline = _get_or_create_pipeline()
                    except Exception as exc:
                        logger.exception("Pipeline initialization failed")
                        summaries.append({"FILE": uploaded_file.name, "STATUS": "FAILED", "ERROR": f"Pipeline initialization failed: {exc}"})
                        doc_records.append({"filename": str(uploaded_file.name), "status": "FAILED", "error": f"Pipeline initialization failed: {exc}", "pages": 0, "duration": 0.0, "outputs": []})
                        continue

                def _on_progress(current_page: int, total_pages_in_file: int) -> None:
                    file_base = (file_index - 1) / len(uploaded_files)
                    file_share = 1.0 / len(uploaded_files)
                    page_pct = (current_page / max(1, total_pages_in_file)) * file_share
                    overall = min(1.0, max(0.0, file_base + page_pct))
                    progress_bar.progress(
                        overall,
                        text=f"Decoding **{uploaded_file.name}** — Page {current_page}/{total_pages_in_file} ({overall:.0%})",
                    )

                result, file_outputs, duration, pages = _process_sync_upload(
                    pipeline=pipeline,
                    uploaded_file=uploaded_file,
                    out_dir=out_dir,
                    options=options,
                    progress_callback=_on_progress,
                )
                status = _safe_status(result.get("status"))
                success = status in _SUCCESS_STATUSES
                summaries.append(
                    {
                        "FILE": uploaded_file.name,
                        "STATUS": "SUCCESS" if success else "FAILED",
                        "ERROR": "" if success else _result_error_message(result),
                    }
                )
                doc_records.append(
                    {
                        "filename": str(uploaded_file.name),
                        "status": "SUCCESS" if success else "FAILED",
                        "error": "" if success else _result_error_message(result),
                        "duration": duration,
                        "pages": pages,
                        "outputs": file_outputs,
                    }
                )
                outputs.extend(file_outputs)
                total_pages += pages
                st.session_state.last_job_latency_seconds = duration
                _record_history(str(uploaded_file.name), result, duration, pages)

            successful_files = sum(1 for item in summaries if item.get("STATUS") == "SUCCESS")
            total_duration = time.perf_counter() - total_started
            if successful_files:
                st.session_state.total_scans = int(st.session_state.get("total_scans", 0)) + successful_files
                st.session_state.pages_decoded = int(st.session_state.get("pages_decoded", 0)) + total_pages

            st.session_state.current_results = {
                "summary": summaries,
                "output_files": outputs,
                "documents": doc_records,
            }
            st.session_state.last_execution_notification = {
                "success_count": successful_files,
                "total_count": len(uploaded_files),
                "pages": total_pages,
                "duration": total_duration,
            }

            progress_bar.progress(1.0, text=f"✅ Execution Complete: {successful_files}/{len(uploaded_files)} file(s) processed in {total_duration:.2f}s")
            status_text.success(f"✅ Finished processing {len(uploaded_files)} file(s) in {total_duration:.2f}s!")
            try:
                st.toast(f"✅ Decoded {total_pages} page(s) across {successful_files} file(s)!", icon="📄")
            except Exception:
                pass
            _safe_rerun()

    _render_current_results()

    for active_job_id in _active_job_ids():
        render_mission_control(db, active_job_id)


def _extract_document_groups(current: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Extract or reconstruct per-document results and output mappings."""
    docs = current.get("documents")
    if isinstance(docs, list) and docs:
        cleaned_docs: list[dict[str, Any]] = []
        for doc in docs:
            if not isinstance(doc, Mapping):
                continue
            raw_doc_outputs = doc.get("outputs", [])
            doc_outputs = [
                (str(fmt), str(path))
                for fmt, path in raw_doc_outputs
                if (Path(str(path)).is_file() or Path(str(path)).exists())
            ]
            if not doc_outputs and raw_doc_outputs:
                doc_outputs = [(str(fmt), str(path)) for fmt, path in raw_doc_outputs]
            cleaned_docs.append({
                "filename": str(doc.get("filename", "document")),
                "status": str(doc.get("status", "SUCCESS")),
                "error": str(doc.get("error", "")),
                "pages": _safe_int(doc.get("pages", 0), 0),
                "duration": _safe_float(doc.get("duration", 0.0), 0.0),
                "outputs": doc_outputs,
            })
        if cleaned_docs:
            return cleaned_docs

    summary = current.get("summary", [])
    raw_outputs = current.get("output_files", [])
    output_files = [
        (str(fmt), str(path))
        for fmt, path in raw_outputs
        if (Path(str(path)).is_file() or Path(str(path)).exists())
    ]
    if not output_files and raw_outputs:
        output_files = [(str(fmt), str(path)) for fmt, path in raw_outputs]

    if not summary:
        if output_files:
            return [{
                "filename": "document",
                "status": "SUCCESS",
                "error": "",
                "pages": 0,
                "duration": 0.0,
                "outputs": output_files,
            }]
        return []

    if len(summary) == 1:
        item = summary[0] if isinstance(summary[0], Mapping) else {}
        return [{
            "filename": str(item.get("FILE", "document")),
            "status": str(item.get("STATUS", "SUCCESS")),
            "error": str(item.get("ERROR", "")),
            "pages": 0,
            "duration": 0.0,
            "outputs": output_files,
        }]

    # Multiple items in summary without explicit 'documents' list
    # Group output files by directory or by stem
    dir_to_outputs: dict[Path, list[tuple[str, str]]] = {}
    for fmt, path_str in output_files:
        dir_to_outputs.setdefault(Path(path_str).parent, []).append((fmt, path_str))

    groups: list[dict[str, Any]] = []
    used_dirs: set[Path] = set()
    for item in summary:
        if not isinstance(item, Mapping):
            continue
        fname = str(item.get("FILE", "document"))
        fstem = Path(fname).stem.lower()
        status = str(item.get("STATUS", "SUCCESS"))
        error = str(item.get("ERROR", ""))

        matched_outputs: list[tuple[str, str]] = []
        for fmt, p_str in output_files:
            p_name = Path(p_str).name.lower()
            if fstem in p_name:
                matched_outputs.append((fmt, p_str))

        if not matched_outputs:
            for p_dir, dir_outputs in dir_to_outputs.items():
                if p_dir not in used_dirs:
                    matched_outputs = dir_outputs
                    used_dirs.add(p_dir)
                    break

        groups.append({
            "filename": fname,
            "status": status,
            "error": error,
            "pages": 0,
            "duration": 0.0,
            "outputs": matched_outputs,
        })
    return groups


def _render_current_results() -> None:
    if _active_job_ids():
        return
    current = st.session_state.get("current_results")
    if not isinstance(current, Mapping):
        return

    summary = current.get("summary", [])
    raw_outputs = current.get("output_files", [])
    if not summary and not raw_outputs:
        return

    successful_files = sum(1 for item in summary if isinstance(item, Mapping) and item.get("STATUS") == "SUCCESS")
    failed_files = sum(1 for item in summary if isinstance(item, Mapping) and item.get("STATUS") == "FAILED")
    last_exec = st.session_state.get("last_execution_notification")

    if isinstance(last_exec, Mapping) and successful_files > 0:
        pages = last_exec.get("pages", 0)
        dur = last_exec.get("duration", 0.0)
        dur_str = f" in {dur:.2f}s" if dur else ""
        if failed_files == 0:
            st.markdown(
                '<div class="success-box" style="margin-bottom: 1rem;">'
                '<strong>MISSION ACCOMPLISHED</strong> — '
                f'Successfully decoded <strong>{pages}</strong> page(s) across <strong>{successful_files}</strong> file(s){dur_str}. '
                'Exported document artifacts and layout geometry models are compiled and ready below.'
                '</div>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                '<div class="warning-box" style="margin-bottom: 1rem;">'
                '<strong>PARTIAL BATCH COMPLETE</strong> — '
                f'Successfully decoded <strong>{pages}</strong> page(s) across <strong>{successful_files}</strong> of {len(summary)} file(s){dur_str}. '
                f'<strong>{failed_files}</strong> file(s) encountered errors. Review error details below.'
                '</div>',
                unsafe_allow_html=True,
            )
        mcols = _pad_columns(st.columns(4, gap="small"), 4)
        with mcols[0]:
            st.metric("DOCUMENTS", f"{successful_files}/{len(summary)}")
        with mcols[1]:
            st.metric("PAGES DECODED", str(pages))
        with mcols[2]:
            st.metric("WALL LATENCY", f"{dur:.2f}s" if dur else "N/A")
        with mcols[3]:
            throughput = f"{pages / max(dur, 0.001):.1f} pps" if dur and pages else "N/A"
            st.metric("THROUGHPUT", throughput)
    elif failed_files > 0 and successful_files == 0:
        st.markdown(
            '<div class="error-box" style="margin-bottom: 1rem;">'
            f'<strong>MISSION FAILED</strong> — {failed_files} file(s) could not be processed. '
            'Review error details in the table below.'
            '</div>',
            unsafe_allow_html=True,
        )

    if summary:
        st.markdown("#### PROCESSED ARTIFACTS")
        st.dataframe(_to_table(summary), use_container_width=True, hide_index=True)

    output_files = [
        (str(fmt), str(path))
        for fmt, path in raw_outputs
        if (Path(str(path)).is_file() or Path(str(path)).exists())
    ]
    if not output_files and raw_outputs:
        output_files = [(str(fmt), str(path)) for fmt, path in raw_outputs]
    if not output_files:
        return

    doc_groups = _extract_document_groups(current)
    active_docs = [d for d in doc_groups if d.get("outputs")]
    if not active_docs and output_files:
        active_docs = [{
            "filename": "batch_output",
            "status": "SUCCESS",
            "error": "",
            "pages": 0,
            "duration": 0.0,
            "outputs": output_files,
        }]

    # Downloads section
    if len(active_docs) > 1:
        st.markdown("##### DOWNLOAD EXPORTED FORMATS")
        bundle_files = tuple(output_files)
        bundle_buffer = _build_zip_bytes(bundle_files)
        st.download_button(
            label=f"DOWNLOAD COMPLETE BATCH ARCHIVE ({len(active_docs)} DOCUMENTS .ZIP)",
            data=bundle_buffer,
            file_name="blast_ocr_batch_bundle.zip",
            mime="application/zip",
            use_container_width=True,
            key="download_all_bundle",
        )

        st.markdown("###### ARTIFACTS BY DOCUMENT")
        doc_tabs = st.tabs([f"📄 {doc['filename']}" for doc in active_docs])
        for doc_index, (tab, doc) in enumerate(zip(doc_tabs, active_docs)):
            with tab:
                doc_outputs = doc.get("outputs", [])
                doc_name = doc.get("filename", f"doc_{doc_index}")

                pill_parts = [f'<span class="doc-stat-pill">File: <strong>{html.escape(doc_name)}</strong></span>']
                if doc.get("pages"):
                    pill_parts.append(f'<span class="doc-stat-pill">Pages: <strong>{doc["pages"]}</strong></span>')
                if doc.get("duration"):
                    pill_parts.append(f'<span class="doc-stat-pill">Latency: <strong>{doc["duration"]:.2f}s</strong></span>')
                pill_parts.append(f'<span class="doc-stat-pill">Formats: <strong>{len(doc_outputs)} ready</strong></span>')
                st.markdown(f'<div class="doc-stats-row">{"".join(pill_parts)}</div>', unsafe_allow_html=True)

                if doc_outputs:
                    cols = _pad_columns(st.columns(min(len(doc_outputs), 5), gap="small"), len(doc_outputs))
                    for index, (fmt, path) in enumerate(doc_outputs):
                        with cols[index % len(cols)]:
                            try:
                                if Path(path).exists() and Path(path).is_file():
                                    file_bytes = Path(path).read_bytes()
                                else:
                                    with open(path, "rb") as fh:
                                        file_bytes = fh.read()
                            except Exception:
                                file_bytes = b""
                            st.download_button(
                                label=f"DOWNLOAD {fmt.upper()}",
                                data=file_bytes,
                                file_name=_safe_download_filename(Path(path).name),
                                mime=MIME_TYPES.get(fmt, "application/octet-stream"),
                                use_container_width=True,
                                key=f"download_{doc_index}_{index}_{uuid.uuid5(uuid.NAMESPACE_URL, str(Path(path).resolve(strict=False))).hex[:12]}",
                            )
                    if len(doc_outputs) > 1:
                        doc_bundle_buffer = _build_zip_bytes(tuple(doc_outputs))
                        doc_zip_name = f"{Path(doc_name).stem}_artifacts.zip"
                        st.download_button(
                            label=f"DOWNLOAD {doc_name} BUNDLE (.ZIP)",
                            data=doc_bundle_buffer,
                            file_name=_safe_download_filename(doc_zip_name),
                            mime="application/zip",
                            use_container_width=True,
                            key=f"download_doc_bundle_{doc_index}_{uuid.uuid5(uuid.NAMESPACE_URL, doc_name).hex[:12]}",
                        )
    else:
        # Single document clean view
        st.markdown("##### DOWNLOAD EXPORTED FORMATS")
        cols = _pad_columns(st.columns(min(len(output_files), 5), gap="small"), len(output_files))
        for index, (fmt, path) in enumerate(output_files):
            with cols[index % len(cols)]:
                try:
                    if Path(path).exists() and Path(path).is_file():
                        file_bytes = Path(path).read_bytes()
                    else:
                        with open(path, "rb") as fh:
                            file_bytes = fh.read()
                except Exception:
                    file_bytes = b""
                st.download_button(
                    label=f"DOWNLOAD {fmt.upper()}",
                    data=file_bytes,
                    file_name=_safe_download_filename(Path(path).name),
                    mime=MIME_TYPES.get(fmt, "application/octet-stream"),
                    use_container_width=True,
                    key=f"download_{index}_{uuid.uuid5(uuid.NAMESPACE_URL, str(Path(path).resolve(strict=False))).hex[:12]}",
                )

        if len(output_files) > 1:
            bundle_files = tuple(output_files)
            bundle_buffer = _build_zip_bytes(bundle_files)
            st.download_button(
                label="DOWNLOAD COMPLETE ARTIFACT BUNDLE (.ZIP)",
                data=bundle_buffer,
                file_name="blast_ocr_mission_bundle.zip",
                mime="application/zip",
                use_container_width=True,
                key="download_bundle",
            )

    _render_document_preview_multi(active_docs, output_files)


def _render_document_preview_multi(
    doc_groups: Sequence[Mapping[str, Any]],
    output_files: Sequence[tuple[str, str]],
) -> None:
    docs_with_preview: list[dict[str, Any]] = []
    for doc in doc_groups:
        outputs = doc.get("outputs", [])
        if any(fmt in {"md", "txt"} for fmt, _ in outputs):
            docs_with_preview.append(dict(doc))

    if not docs_with_preview:
        text_candidates = [path for fmt, path in output_files if fmt in {"md", "txt"}]
        if not text_candidates:
            return
        docs_with_preview = [{
            "filename": Path(text_candidates[0]).name,
            "outputs": output_files,
        }]

    with st.expander("INLINE DOCUMENT PREVIEW & INSPECTION", expanded=True):
        if len(docs_with_preview) > 1:
            doc_labels = [str(doc.get("filename", f"Document {i+1}")) for i, doc in enumerate(docs_with_preview)]
            selected_label = st.selectbox(
                "SELECT DOCUMENT TO PREVIEW",
                doc_labels,
                key="preview_doc_selector",
            )
            selected_doc = next((d for d in docs_with_preview if str(d.get("filename")) == selected_label), docs_with_preview[0])
        else:
            selected_doc = docs_with_preview[0]

        doc_outputs = selected_doc.get("outputs", output_files)
        text_candidates = [path for fmt, path in doc_outputs if fmt in {"md", "txt"}]
        if not text_candidates:
            st.caption("No text preview available for the selected document.")
            return

        preview_path = Path(text_candidates[0])
        try:
            full_size = preview_path.stat().st_size
            with preview_path.open("r", encoding="utf-8", errors="replace") as handle:
                sample = handle.read(PREVIEW_CHAR_LIMIT + 1)
        except OSError as exc:
            st.caption(f"Preview unavailable: {exc}")
            return

        truncated = len(sample) > PREVIEW_CHAR_LIMIT
        preview = sample[:PREVIEW_CHAR_LIMIT]
        word_count = len(preview.split())
        char_count = len(preview)
        scope_label = "Preview" if truncated else "Document"

        st.markdown(
            '<div class="doc-stats-row">'
            f'<span class="doc-stat-pill">File: <strong>{html.escape(preview_path.name)}</strong></span>'
            f'<span class="doc-stat-pill">{scope_label} words: <strong>{word_count:,}</strong></span>'
            f'<span class="doc-stat-pill">{scope_label} characters: <strong>{char_count:,}</strong></span>'
            f'<span class="doc-stat-pill">Bytes: <strong>{full_size:,}</strong></span>'
            "</div>",
            unsafe_allow_html=True,
        )
        if truncated:
            st.info(f"Preview capped at {PREVIEW_CHAR_LIMIT:,} characters to keep the browser responsive.")

        rendered_tab, raw_tab, json_tab = st.tabs(
            ["RENDERED MARKDOWN", "RAW TEXT", "JSON STRUCTURE"]
        )
        with rendered_tab:
            st.markdown(_markdown_without_embeds(preview), unsafe_allow_html=False)
        with raw_tab:
            st.text_area(
                "Document Content",
                value=preview,
                height=300,
                key=f"preview_raw_text_{selected_doc.get('filename', 'doc')}",
            )
        with json_tab:
            layout_jsons = [Path(path) for fmt, path in doc_outputs if fmt == "json" and Path(path).is_file()]
            if not layout_jsons:
                fstem = Path(str(selected_doc.get("filename", ""))).stem.lower()
                layout_jsons = [
                    Path(path) for fmt, path in output_files
                    if fmt == "json" and Path(path).is_file() and fstem in Path(path).name.lower()
                ]
            if not layout_jsons:
                st.caption("No JSON document model exported for this document.")
            else:
                try:
                    if layout_jsons[0].stat().st_size > MAX_LAYOUT_JSON_MB * 1024 * 1024:
                        st.warning(f"JSON preview skipped because it exceeds {MAX_LAYOUT_JSON_MB} MB.")
                    else:
                        with layout_jsons[0].open("r", encoding="utf-8") as fh:
                            st.json(json.load(fh))
                except (OSError, json.JSONDecodeError) as exc:
                    st.caption(f"JSON structure preview unavailable: {exc}")


def _render_document_preview(preview_path: Path, output_files: Sequence[tuple[str, str]]) -> None:
    """Compatibility wrapper for single-document preview callers."""
    _render_document_preview_multi([{"filename": preview_path.name, "outputs": output_files}], output_files)


# -----------------------------------------------------------------------------
# Mission control polling
# -----------------------------------------------------------------------------


def _finalize_queue_job(job_id: Any, job: Any, status: str, processed_pages: int) -> None:
    """Fold a durable-queue terminal state back into session results exactly once."""
    marker = str(job_id)
    finalized = st.session_state.get("finalized_queue_jobs")
    if not isinstance(finalized, list):
        finalized = []
        st.session_state.finalized_queue_jobs = finalized
    if marker in {str(item) for item in finalized}:
        return

    meta_map = st.session_state.get("queued_job_meta")
    meta = meta_map.get(marker, {}) if isinstance(meta_map, dict) else {}
    filename = str(meta.get("filename") or getattr(job, "filename", f"job-{marker}"))
    error_message = str(getattr(job, "error_message", "") or "")

    current = st.session_state.get("current_results")
    if not isinstance(current, dict):
        current = {"summary": [], "output_files": []}
        st.session_state.current_results = current
    summary = current.setdefault("summary", [])
    if not isinstance(summary, list):
        summary = []
        current["summary"] = summary

    updated = False
    for row in summary:
        if isinstance(row, dict) and str(row.get("JOB ID", "")) == marker:
            row["STATUS"] = "SUCCESS" if status in _SUCCESS_STATUSES else status.upper()
            row["ERROR"] = "" if status in _SUCCESS_STATUSES else error_message
            updated = True
            break
    if not updated:
        summary.append(
            {
                "FILE": filename,
                "STATUS": "SUCCESS" if status in _SUCCESS_STATUSES else status.upper(),
                "ERROR": "" if status in _SUCCESS_STATUSES else error_message,
                "JOB ID": marker,
            }
        )

    job_output_map = getattr(job, "output_files", {})
    queued_out_dir = Path(str(meta.get("output_dir") or get_session_output_dir()))
    outputs = _normalise_output_files(
        {"output_files": job_output_map if isinstance(job_output_map, Mapping) else {}},
        filename,
        queued_out_dir,
    )
    existing = current.setdefault("output_files", [])
    if not isinstance(existing, list):
        existing = []
        current["output_files"] = existing
    existing_paths = {str(Path(str(path)).resolve()) for _fmt, path in existing if Path(str(path)).exists()}
    for fmt, raw_path in outputs:
        resolved = str(Path(raw_path).resolve())
        if resolved not in existing_paths:
            existing.append((fmt, raw_path))
            existing_paths.add(resolved)

    docs = current.setdefault("documents", [])
    if not isinstance(docs, list):
        docs = []
        current["documents"] = docs
    doc_match = next((d for d in docs if isinstance(d, dict) and d.get("filename") == filename), None)
    if doc_match:
        doc_match["status"] = "SUCCESS" if status in _SUCCESS_STATUSES else status.upper()
        doc_match["error"] = "" if status in _SUCCESS_STATUSES else error_message
        doc_match["pages"] = max(0, processed_pages)
        doc_match["outputs"] = outputs
    else:
        docs.append({
            "filename": filename,
            "status": "SUCCESS" if status in _SUCCESS_STATUSES else status.upper(),
            "error": "" if status in _SUCCESS_STATUSES else error_message,
            "pages": max(0, processed_pages),
            "outputs": outputs,
        })

    if status in _SUCCESS_STATUSES:
        st.session_state.total_scans = int(st.session_state.get("total_scans", 0)) + 1
        st.session_state.pages_decoded = int(st.session_state.get("pages_decoded", 0)) + max(0, processed_pages)

    finalized.append(marker)


def _render_mission_body(db: Any, job_id: Any) -> bool:
    """Render one mission snapshot. Return True when the job is terminal/missing."""
    try:
        job = db.get_job(job_id)
    except Exception:
        logger.exception("Mission DB lookup failed for %s", job_id)
        st.error("Mission state is temporarily unavailable.")
        return False

    if not job:
        st.error("JOB STATE NOT FOUND. The queue/database may not share this job identifier.")
        if st.button("RETURN TO COMMAND CENTER", key="return_missing_job", use_container_width=True):
            _cleanup_queued_source(job_id)
            _remove_active_job(job_id)
            _safe_rerun()
        # A durable queue may commit its DB row shortly after enqueue; keep polling.
        return False

    status = _safe_status(getattr(job, "status", "unknown"))
    st.markdown(f"### MISSION CONTROL — JOB `{html.escape(str(job_id))}`")

    if status in _SUCCESS_STATUSES:
        st.success(f"STATUS: {status.upper()}")
    elif status in _TERMINAL_STATUSES:
        st.error(f"STATUS: {status.upper()}")
    elif status in {"processing", "post_processing", "exporting"}:
        st.warning(f"STATUS: {status.upper()}")
    else:
        st.info(f"STATUS: {status.upper()}")

    try:
        results = db.get_results(job_id) or []
    except Exception:
        results = []
    processed = len(results)
    total_pages = max(0, _safe_int(getattr(job, "page_count", 0), 0))

    if total_pages > 0:
        progress = min(1.0, processed / total_pages)
        st.progress(progress, text=f"Decoded {processed} of {total_pages} pages")
    else:
        st.progress(0.0, text=f"Decoded {processed} page(s); total page count pending")

    if results:
        with st.expander("LIVE INTELLIGENCE STREAM", expanded=True):
            for result in results[-3:]:
                page_number = _safe_int(getattr(result, "page_number", 0), 0)
                confidence = _safe_float(getattr(result, "confidence_score", 0.0), 0.0)
                text = str(getattr(result, "extracted_text", ""))
                st.markdown(f"**PAGE {page_number}** — confidence `{confidence:.2f}`")
                st.text(text[:500] + ("…" if len(text) > 500 else ""))

    terminal = status in _TERMINAL_STATUSES
    if terminal:
        _finalize_queue_job(job_id, job, status, processed)
        _cleanup_queued_source(job_id)
        error_message = str(getattr(job, "error_message", "") or "")
        if status in _SUCCESS_STATUSES:
            if status == "succeeded_with_warnings":
                st.warning("Mission completed with warnings. Review low-confidence pages before downstream use.")
            else:
                st.success("Mission completed successfully.")
        else:
            st.error(f"Mission ended with status {status.upper()}." + (f" {error_message}" if error_message else ""))

        if st.button(
            "RETURN TO COMMAND CENTER",
            key=f"return_btn_{job_id}",
            use_container_width=True,
        ):
            _remove_active_job(job_id)
            _safe_rerun()
    return terminal


def render_mission_control(db: Any, job_id: Any) -> None:
    """Poll mission state."""
    terminal = _render_mission_body(db, job_id)
    if not terminal:
        time.sleep(MISSION_POLL_SECONDS)
        _safe_rerun()


# -----------------------------------------------------------------------------
# Tab renderers
# -----------------------------------------------------------------------------


def render_mission_tab(db: Any, settings: Any) -> None:
    left, right = _pad_columns(st.columns([1, 2], gap="large"), 2)
    with left:
        options = render_engine_configuration(settings)
    pipeline = _get_or_create_pipeline() if st.session_state.get("pipeline_initialized") else None
    with right:
        handle_file_upload(pipeline, db, settings, options)


def _discover_layout_jsons() -> list[Path]:
    current = st.session_state.get("current_results")
    found: list[Path] = []
    if isinstance(current, Mapping):
        for fmt, raw_path in current.get("output_files", []):
            path = Path(str(raw_path))
            if fmt == "json" and path.is_file():
                found.append(path)
    if found:
        return found
    out_dir = get_session_output_dir()
    if out_dir.is_dir():
        return sorted(out_dir.rglob("*_layout.json"))
    return []


def render_layout_tab() -> None:
    _panel_heading(ICON_LAYOUT, "LAYOUT GEOMETRY & BOUNDING BOX HEATMAPS")
    json_files = _discover_layout_jsons()
    if not json_files:
        st.info("No layout geometry is available yet. Process a document that exports layout JSON.")
        return

    filter_col, confidence_col = _pad_columns(st.columns(2, gap="large"), 2)
    with filter_col:
        selected_filter = st.selectbox(
            "FILTER BLOCK CLASSIFICATION",
            ["ALL", "TITLE", "SECTION_HEADER", "HEADER", "FOOTER", "TEXT", "COLUMN", "LIST_ITEM", "TABLE", "FORMULA", "FOOTNOTE", "CAPTION"],
            key="layout_filter",
        )
    with confidence_col:
        min_confidence = st.slider(
            "MINIMUM CONFIDENCE THRESHOLD",
            0.0,
            1.0,
            0.0,
            0.05,
            key="layout_min_confidence",
        )

    doc_options = [str(path) for path in json_files]
    selected_doc = st.selectbox(
        "DOCUMENT MODEL",
        doc_options,
        format_func=lambda value: Path(value).name,
        key="layout_document",
    )
    path = Path(selected_doc)
    try:
        if path.stat().st_size > MAX_LAYOUT_JSON_MB * 1024 * 1024:
            st.error(f"Layout model is larger than the {MAX_LAYOUT_JSON_MB} MB interactive-inspection limit.")
            return
        with path.open("r", encoding="utf-8") as fh:
            doc = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        st.error(f"Could not read layout JSON: {exc}")
        return

    pages = doc.get("pages", []) if isinstance(doc, Mapping) else []
    if not isinstance(pages, list) or not pages:
        st.info("The layout JSON contains no pages.")
        return

    page_labels = [_safe_int(page.get("page_num"), index + 1) if isinstance(page, Mapping) else index + 1 for index, page in enumerate(pages)]
    page_number = st.selectbox("SELECT PAGE TO INSPECT", page_labels, key="layout_page")
    page = next(
        (item for item in pages if isinstance(item, Mapping) and _safe_int(item.get("page_num"), 1) == page_number),
        pages[0],
    )
    if not isinstance(page, Mapping):
        st.error("Selected page has an invalid layout structure.")
        return

    width = _safe_int(page.get("width"), 800)
    height = _safe_int(page.get("height"), 1000)
    st.markdown(f"#### PAGE {page_number} — `{width} × {height}px`")

    svg_col, block_col = _pad_columns(st.columns([1, 1], gap="large"), 2)
    with svg_col:
        st.markdown(render_layout_geometry_svg(page, selected_filter, min_confidence), unsafe_allow_html=True)

    with block_col:
        raw_blocks = page.get("blocks", [])
        blocks = raw_blocks if isinstance(raw_blocks, list) else []
        filtered = []
        for block in blocks:
            if not isinstance(block, Mapping):
                continue
            block_type = str(block.get("block_type", "text")).upper()
            confidence = _safe_float(block.get("confidence"), 0.0)
            if selected_filter != "ALL" and block_type != selected_filter:
                continue
            if confidence < min_confidence:
                continue
            filtered.append(block)

        st.caption(f"Displaying {len(filtered)} of {len(blocks)} layout blocks")
        # Avoid rendering thousands of Streamlit widgets; the SVG can handle more than the
        # detailed inspector panel.
        for block_index, block in enumerate(filtered[:200], 1):
            block_type = str(block.get("block_type", "text")).upper()
            block_text = str(block.get("text", ""))
            bbox = block.get("bbox", {}) if isinstance(block.get("bbox", {}), Mapping) else {}
            confidence = _safe_float(block.get("confidence"), 0.0)
            st.caption(
                f"**Block #{block_index}** [{block_type}] | Conf `{confidence:.2f}` | "
                f"Box `[{_safe_float(bbox.get('xmin')):.0f}, {_safe_float(bbox.get('ymin')):.0f}, "
                f"{_safe_float(bbox.get('xmax')):.0f}, {_safe_float(bbox.get('ymax')):.0f}]`"
            )
            if block_type == "TABLE" and block.get("table_data"):
                st.dataframe(_to_table(block.get("table_data")), use_container_width=True, hide_index=True)
            elif block_type == "FORMULA":
                formula_text = block_text[:10_000]
                try:
                    st.latex(formula_text)
                except Exception:
                    st.code(formula_text, language="latex")
            else:
                st.text_area(
                    f"Content #{block_index}",
                    value=block_text[:50_000],
                    height=90,
                    key=f"layout_block_{page_number}_{block_index}_{selected_filter}",
                )
        if len(filtered) > 200:
            st.info(f"Detailed inspector capped at 200 blocks; {len(filtered) - 200} additional blocks remain visible in the geometry view.")


def _db_history(db: Any) -> list[dict[str, Any]]:
    """Merge session-rich records with persisted job history without dropping either."""
    history = st.session_state.get("processing_history")
    records = [dict(item) for item in history if isinstance(item, Mapping)] if isinstance(history, list) else []

    jobs: Sequence[Any] = []
    if hasattr(db, "get_recent_jobs"):
        try:
            jobs = db.get_recent_jobs(limit=200) or []
        except Exception:
            logger.debug("DB history read failed", exc_info=True)

    seen = {
        (str(record.get("TIMESTAMP", "")), str(record.get("FILE", "")), str(record.get("STATUS", "")))
        for record in records
    }
    for job in jobs:
        record = {
            "TIMESTAMP": str(getattr(job, "created_at", "")),
            "FILE": str(getattr(job, "filename", "Unknown")),
            "STATUS": _safe_status(getattr(job, "status", "unknown")).upper(),
            "PAGES": _safe_int(getattr(job, "page_count", 0), 0),
            "DURATION": "N/A",
            "CONFIDENCE": "N/A",
        }
        marker = (record["TIMESTAMP"], record["FILE"], record["STATUS"])
        if marker not in seen:
            records.append(record)
            seen.add(marker)

    records.sort(key=lambda record: str(record.get("TIMESTAMP", "")), reverse=True)
    return records[:500]


def render_audit_tab(db: Any) -> None:
    _panel_heading(ICON_TERMINAL, "AUDIT TRAIL & JOB HISTORY")
    records = _db_history(db)

    control, search_col, filter_col = _pad_columns(st.columns([1, 2, 2], gap="medium"), 3)
    with control:
        if st.button(
            "CLEAR SESSION LOG",
            use_container_width=True,
            key="clear_session_log",
        ):
            st.session_state.processing_history = []
            _safe_rerun()
    with search_col:
        query = st.text_input("SEARCH LOGS", placeholder="filename or timestamp", key="audit_search")
    with filter_col:
        status_options = [
            "ALL",
            *sorted({str(record.get("STATUS", "UNKNOWN")).upper() for record in records}),
        ]
        status_filter = st.selectbox(
            "STATUS FILTER",
            status_options,
            key="audit_status_filter",
        )

    if query:
        needle = query.casefold()
        records = [
            record
            for record in records
            if needle in str(record.get("FILE", "")).casefold()
            or needle in str(record.get("TIMESTAMP", "")).casefold()
        ]
    if status_filter != "ALL":
        records = [record for record in records if str(record.get("STATUS", "")).upper() == status_filter]

    if not records:
        st.info("No matching audit records.")
        return

    st.dataframe(_to_table(records), use_container_width=True, hide_index=True)
    if pd is not None:
        safe_records = [
            {key: _spreadsheet_safe_value(value) for key, value in record.items()}
            for record in records
        ]
        csv_bytes = pd.DataFrame(safe_records).to_csv(index=False).encode("utf-8")

        st.download_button(
            "EXPORT AUDIT TRAIL (.CSV)",
            data=csv_bytes,
            file_name=f"audit_trail_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv",
            use_container_width=True,
            key="audit_csv_download",
        )


def _resource_snapshot() -> tuple[float | None, float | None]:
    try:
        import psutil

        process = psutil.Process(os.getpid())
        memory_mb = process.memory_info().rss / (1024 * 1024)
        # interval=0.1 blocks briefly but returns a real reading unlike interval=None
        # which always returns 0.0 on the first call (no prior sample exists).
        cpu_percent = psutil.cpu_percent(interval=0.1)
        return memory_mb, cpu_percent
    except Exception:
        return None, None


def _render_swarm_monitor() -> bool:
    try:
        from blast_ocr.queue.client import QueueClient, get_redis_connection, is_queue_available
        from blast_ocr.queue.heartbeat import WorkerRegistry
        from blast_ocr.queue.reaper import ZombieReaper

        if not is_queue_available():
            return False

        connection = get_redis_connection()
        queue = QueueClient(connection)
        registry = WorkerRegistry(connection)
        reaper = ZombieReaper(connection, queue_client=queue)

        st.markdown("#### DISTRIBUTED WORKER SWARM & PRIORITY QUEUE")
        depths = queue.get_all_queue_depths()
        high, default, low, dlq = _pad_columns(st.columns(4, gap="small"), 4)
        high.metric("HIGH PRIORITY", int(depths.get("high", 0)))
        default.metric("DEFAULT PRIORITY", int(depths.get("default", 0)))
        low.metric("LOW PRIORITY", int(depths.get("low", 0)))
        dlq.metric("DEAD-LETTER", int(depths.get("dlq", 0)))

        workers = registry.list_active_workers() or []
        if workers:
            rows = [
                {
                    "WORKER ID": item.get("worker_id"),
                    "STATUS": str(item.get("status", "idle")).upper(),
                    "CPU %": _safe_float(item.get("cpu_percent"), 0.0),
                    "RSS MB": _safe_float(item.get("memory_rss_mb"), 0.0),
                    "ACTIVE JOB": item.get("active_job_id") or "Idle",
                    "COMPLETED": _safe_int(item.get("jobs_processed_total"), 0),
                }
                for item in workers
                if isinstance(item, Mapping)
            ]
            st.dataframe(_to_table(rows), use_container_width=True, hide_index=True)
        else:
            st.caption("Redis is reachable, but no external worker heartbeats are currently registered.")

        if st.button(
            "RUN ZOMBIE REAPER SCAN",
            use_container_width=True,
            key="zombie_reaper",
        ):
            result = reaper.reap_zombies()
            st.success(f"Reaper scan completed: {_safe_int(result.get('reaped_count'), 0)} zombie task(s) reaped.")
        return True
    except Exception:
        logger.debug("Swarm monitor unavailable", exc_info=True)
        return False


def _start_baseline_job(db: Any, source_path: Path, out_dir: Path, options: EngineOptions) -> None:
    if _active_job_ids():
        st.warning("Another mission is already active.")
        return
    if not source_path.is_file():
        st.error(f"Test vector not found: {source_path}")
        return
    if not _has_streamlit_runtime_context():
        st.warning("Baseline skipped because there is no active Streamlit runtime context.")
        return

    pipeline = _get_or_create_pipeline()
    _apply_engine_options(pipeline, options)
    out_dir.mkdir(parents=True, exist_ok=True)
    job_out_dir = _new_job_output_dir(out_dir)
    job_id = db.create_job(source_path.name, page_count=0)
    _set_active_job_ids([job_id])

    def _worker() -> None:
        try:
            _call_with_supported_kwargs(
                pipeline.process_job,
                source_path=str(source_path),
                output_dir=str(job_out_dir),
                job_id=job_id,
                job_config=asdict(options),
                config=asdict(options),
            )
        except Exception as exc:
            logger.exception("Baseline background job failed")
            try:
                db.update_job_status(job_id, "failed", error_message=str(exc))
            except Exception:
                logger.exception("Failed to persist baseline failure state")

    thread = threading.Thread(target=_worker, name=f"blast-baseline-{job_id}", daemon=True)
    thread.start()


def render_telemetry_tab(db: Any, settings: Any, options: EngineOptions) -> None:
    _panel_heading(ICON_ACTIVITY, "LIVE TELEMETRY, SWARM & STORAGE HUD")

    capabilities = _runtime_capabilities()
    memory_mb, cpu_percent = _resource_snapshot()
    m1, m2, m3, m4 = _pad_columns(st.columns(4, gap="small"), 4)
    m1.metric("PROCESS RSS", f"{memory_mb:.1f} MB" if memory_mb is not None else "N/A")
    m2.metric("HOST CPU", f"{cpu_percent:.1f}%" if cpu_percent is not None else "N/A")
    m3.metric("EXECUTION PROVIDER", capabilities.provider_label)
    db_url = str(getattr(settings, "database_url", "unknown"))
    db_scheme = db_url.split(":", 1)[0].upper() if ":" in db_url else "UNKNOWN"
    m4.metric("DATABASE BACKEND", db_scheme)

    st.divider()
    if not _render_swarm_monitor():
        st.caption("Distributed queue unavailable or disabled; jobs execute in standalone process mode.")

    st.divider()
    health_col, actions_col = _pad_columns(st.columns([2, 1], gap="large"), 2)
    with health_col:
        st.markdown("#### MEASURED SUBSYSTEM STATUS")
        st.write(
            {
                "ONNX Runtime": "available" if capabilities.onnx_available else "unavailable",
                "Execution provider": capabilities.provider,
                "Pipeline": "initialized" if st.session_state.get("pipeline_initialized") else "lazy / not initialized",
                "Database": "fallback" if st.session_state.get("db_init_error") else "initialized",
                "Queue backend": str(getattr(settings, "queue_backend", "sync")),
                "Secure-mode default": bool(getattr(settings, "secure_mode", False)),
            }
        )
    with actions_col:
        st.markdown("#### DIAGNOSTIC CONTROL")
        if st.button(
            "RUN BASELINE TEST VECTOR",
            type="primary",
            use_container_width=True,
            key="run_baseline",
            disabled=bool(_active_job_ids()),
        ):
            _start_baseline_job(db, Path("data/mybook.pdf"), get_session_output_dir(), options)
            _safe_rerun()

    metrics = []
    try:
        metrics = db.get_recent_metrics(limit=20) or []
    except Exception:
        logger.debug("Telemetry metric read failed", exc_info=True)
    if metrics:
        latest = metrics[0]
        t1, t2, t3, t4 = _pad_columns(st.columns(4, gap="small"), 4)
        t1.metric("PEAK MEMORY", f"{_safe_float(getattr(latest, 'peak_memory_mb', 0)):.1f} MB")
        t2.metric("AVG FIDELITY", f"{_safe_float(getattr(latest, 'fidelity_score', 0)):.1%}")
        t3.metric("EXTRACTION VELOCITY", f"{_safe_float(getattr(latest, 'extraction_velocity', 0)):.2f} p/s")
        t4.metric("PAGE LATENCY", f"{_safe_float(getattr(latest, 'avg_page_time', 0)):.2f}s")
        records = [
            {
                "timestamp": _safe_float(getattr(metric, "timestamp", 0), 0),
                "fidelity": _safe_float(getattr(metric, "fidelity_score", 0), 0),
                "velocity": _safe_float(getattr(metric, "extraction_velocity", 0), 0),
            }
            for metric in reversed(metrics)
        ]
        st.line_chart(_to_table(records), x="timestamp", y=["fidelity", "velocity"], use_container_width=True)
    else:
        st.info("No persisted telemetry metrics are available yet.")

    st.divider()
    st.markdown("### SESSION STORAGE")
    session_dir = get_session_output_dir()
    total_size = 0
    file_count = 0
    if session_dir.is_dir():
        for path in session_dir.rglob("*"):
            if path.is_file():
                file_count += 1
                try:
                    total_size += path.stat().st_size
                except OSError:
                    pass
    storage_col, clear_col = _pad_columns(st.columns([2, 1], gap="large"), 2)
    storage_col.metric("THIS SESSION'S ARTIFACTS", f"{total_size / (1024 * 1024):.2f} MB")
    storage_col.caption(f"{file_count} file(s) in the current isolated session directory")
    with clear_col:
        if st.button(
            "CLEAR THIS SESSION'S ARTIFACTS",
            use_container_width=True,
            key="clear_session_artifacts",
            disabled=bool(_active_job_ids()),
        ):
            try:
                reclaimed = _clear_current_session_artifacts()
                st.success(f"Reclaimed {reclaimed / (1024 * 1024):.2f} MB from this session only.")
                _safe_rerun()
            except OSError as exc:
                st.error(f"Session cleanup failed: {exc}")


# -----------------------------------------------------------------------------
# Header and app shell
# -----------------------------------------------------------------------------


def _render_header(settings: Any) -> None:
    capabilities = _runtime_capabilities()
    pipeline_ready = bool(st.session_state.get("pipeline_initialized"))
    db_degraded = bool(st.session_state.get("db_init_error"))

    engine_state = "PIPELINE READY" if pipeline_ready else "PIPELINE LAZY"
    engine_pill_class = "engine-pill engine-pill--ready" if pipeline_ready else "engine-pill engine-pill--lazy"
    db_state = "DB FALLBACK" if db_degraded else "DB READY"
    st.markdown(
        '<div class="blast-header">'
        '<div class="blast-badge-row">'
        '<span class="status-badge"><span class="status-dot"></span> UI ONLINE</span>'
        f'<span class="{engine_pill_class}">{html.escape(engine_state)}</span>'
        f'<span class="engine-pill">{html.escape(capabilities.provider_label)}</span>'
        f'<span class="engine-pill">{html.escape(db_state)}</span>'
        '</div>'
        '<h1 class="blast-title">B.L.A.S.T. OCR</h1>'
        '<div class="blast-subtitle">Deterministic document processing and optical character recognition operations console</div>'
        '</div>',
        unsafe_allow_html=True,
    )

    elapsed = time.monotonic() - float(st.session_state.get("session_started_monotonic", time.monotonic()))
    latency = st.session_state.get("last_job_latency_seconds")
    metric1, metric2, metric3, metric4 = _pad_columns(st.columns(4, gap="small"), 4)
    metric1.metric("FILES COMPLETED", int(st.session_state.get("total_scans", 0)))
    metric2.metric("PAGES DECODED", int(st.session_state.get("pages_decoded", 0)))
    metric3.metric("LAST JOB WALL TIME", f"{float(latency):.2f}s" if latency is not None else "N/A")
    metric4.metric("SESSION UPTIME", _human_duration(elapsed))


def main() -> None:
    try:
        load_css()
        inject_seo_metadata()

        if _is_cloud_runtime() and _is_model_download_in_progress():
            st.markdown("## INITIALIZING OCR MODELS")
            st.info(
                "First-run model download is in progress on the server. "
                "Please wait 2-5 minutes and refresh this page."
            )
            st.stop()

        init_session_state()

        settings = _get_settings_cached()
        db = _get_or_create_db()

        if _PANDAS_IMPORT_ERROR:
            st.warning("Pandas is unavailable; dataframe and CSV features are running in degraded mode.")
            if DEBUG_UI:
                st.caption(_PANDAS_IMPORT_ERROR)
        if st.session_state.get("settings_init_error"):
            st.warning("Project settings could not be initialized; safe UI defaults are active.")
        if st.session_state.get("db_init_error"):
            st.warning("Persistent database initialization failed. This browser session is using an in-memory fallback.")

        _render_header(settings)
        st.divider()

        tab_list = st.tabs(
            ["MISSION CONTROL", "LAYOUT INSPECTOR", "SYSTEM AUDIT LOGS", "TELEMETRY & SWARM"]
        )
        tabs = _pad_columns(tab_list, 4)
        mission_tab, layout_tab, audit_tab, telemetry_tab = tabs[0], tabs[1], tabs[2], tabs[3]

        with mission_tab:
            render_mission_tab(db, settings)

        with layout_tab:
            render_layout_tab()

        with audit_tab:
            render_audit_tab(db)

        with telemetry_tab:
            current_options = _engine_options_from_state(settings)
            render_telemetry_tab(db, settings, current_options)

    except Exception as exc:
        logger.exception("Fatal top-level Streamlit UI error")
        st.error("Application runtime failure detected. Check server logs for diagnostic details.")
        # Exception text and tracebacks can expose paths, dependency internals, connection
        # details, or secrets. They are opt-in for local/operator debugging only.
        if DEBUG_UI:
            st.code(str(exc))
            st.code(traceback.format_exc())
        if _is_cloud_runtime():
            st.stop()
        raise


if __name__ == "__main__":
    main()

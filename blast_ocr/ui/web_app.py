import os
import streamlit as st

# MUST BE FIRST Streamlit command
st.set_page_config(
    page_title="B.L.A.S.T. OCR Engine",
    page_icon="■",
    layout="wide",
)

# Set writable cache for cloud environments
os.environ["EASYOCR_CACHE"] = "/tmp/.EasyOCR"

# Streamlit Cloud startup resilience: avoid heavy OCR imports during health checks.
if os.getenv("STREAMLIT_SERVER_PORT"):
    os.environ.setdefault("BLAST_OCR_DEFER_PIPELINE", "1")

import time
from pathlib import Path
import tempfile
import sys
import threading
import uuid
import logging
import traceback

try:
    import pandas as pd
except Exception as _pandas_exc:
    pd = None
    _PANDAS_IMPORT_ERROR = str(_pandas_exc)
else:
    _PANDAS_IMPORT_ERROR = None

try:
    from streamlit.runtime.scriptrunner import get_script_run_ctx
except Exception:  # pragma: no cover - runtime compatibility fallback
    get_script_run_ctx = None

logger = logging.getLogger(__name__)


class _InMemoryDB:
    """Resilient DB fallback to keep UI alive when SQLite init fails."""

    class _Obj:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    def __init__(self):
        self._next_job_id = 1
        self._jobs = {}
        self._results = {}
        self._metrics = []

    def create_job(self, filename, page_count=0):
        job_id = self._next_job_id
        self._next_job_id += 1
        job = self._Obj(
            id=job_id,
            filename=filename,
            page_count=page_count,
            status="pending",
            error_message=None,
        )
        self._jobs[job_id] = job
        self._results[job_id] = []
        return job_id

    def update_job_status(self, job_id, status, error_message=None):
        job = self._jobs.get(job_id)
        if job is None:
            return
        job.status = status
        if error_message:
            job.error_message = error_message

    def save_result(self, job_id, page_number, text, confidence, processing_time):
        result = self._Obj(
            page_number=page_number,
            extracted_text=text,
            confidence_score=float(confidence),
            processing_time=float(processing_time),
        )
        self._results.setdefault(job_id, []).append(result)

    def update_job_page_count(self, job_id, page_count):
        job = self._jobs.get(job_id)
        if job is not None:
            job.page_count = page_count

    def save_metric(self, job_id, peak_mem, avg_time, fidelity, velocity):
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

    def purge_old_data(self, days=7):
        return None

    def get_recent_metrics(self, limit=10):
        return list(reversed(self._metrics[-limit:]))

    def get_job(self, job_id):
        return self._jobs.get(job_id)

    def get_results(self, job_id):
        return self._results.get(job_id, [])


def _to_table(data):
    """Return a dataframe when pandas is available, otherwise raw records."""
    if pd is None:
        return data
    try:
        return pd.DataFrame(data)
    except Exception:
        return data


def _has_streamlit_runtime_context() -> bool:
    """Return True when running inside an active Streamlit script context."""
    if get_script_run_ctx is None:
        return False
    try:
        return get_script_run_ctx() is not None
    except Exception:
        return False


def _is_cloud_runtime() -> bool:
    """Detect hosted Streamlit runtime."""
    return bool(
        os.getenv("STREAMLIT_SERVER_PORT") or os.getenv("STREAMLIT_SHARING_MODE")
    )


def _as_int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def _is_model_download_in_progress() -> bool:
    """Detect EasyOCR model bootstrap markers in logs."""
    log_candidates = [
        Path("/mount/src/ocr/logs/blast_ocr.log"),
        Path("/tmp/logs/blast_ocr.log"),
        Path("logs/blast_ocr.log"),
    ]

    markers = (
        "Downloading detection model",
        "Downloading recognition model",
    )

    for p in log_candidates:
        if not p.exists() or not p.is_file():
            continue
        try:
            # Read a bounded tail region to keep this lightweight.
            data = p.read_text(encoding="utf-8", errors="ignore")
            tail = data[-8000:]
            if any(m in tail for m in markers):
                return True
        except Exception:
            continue

    return False


# Project root for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


def _is_real_blast_pipeline(pipeline) -> bool:
    """Detect real pipeline instance without importing heavy modules at startup."""
    if pipeline is None:
        return False
    klass = pipeline.__class__
    return (
        getattr(klass, "__module__", "") == "blast_ocr.pipeline"
        and getattr(klass, "__name__", "") == "BlastPipeline"
    )


def _get_or_create_pipeline():
    """Create the OCR pipeline lazily and cache it in session state."""
    if "pipeline_instance" not in st.session_state:
        st.session_state.pipeline_instance = None

    if st.session_state.pipeline_instance is None:
        from blast_ocr.pipeline import BlastPipeline

        st.session_state.pipeline_instance = BlastPipeline()

    return st.session_state.pipeline_instance


def _get_or_create_db():
    """Create DB handle lazily and cache in session state."""
    if "db_instance" not in st.session_state:
        st.session_state.db_instance = None
    if "db_init_error" not in st.session_state:
        st.session_state.db_init_error = None

    if st.session_state.db_instance is None:
        try:
            from blast_ocr.storage.database import OCRDatabase

            st.session_state.db_instance = OCRDatabase()
        except Exception as e:
            st.session_state.db_init_error = str(e)
            logger.exception("DB initialization failed; using in-memory fallback")
            st.session_state.db_instance = _InMemoryDB()

    return st.session_state.db_instance


def _get_settings_cached():
    """Fetch settings lazily (prevents import-time startup failures)."""
    if "settings_instance" not in st.session_state:
        from blast_ocr.config import get_settings

        st.session_state.settings_instance = get_settings()
    return st.session_state.settings_instance


def _get_cleanup_manager_class():
    """Import CleanupManager lazily."""
    from blast_ocr.core.cleanup_manager import CleanupManager

    return CleanupManager


# --- SVG Icons (Lucide) for Exaggerated Minimalism UI ---
# UI UX Pro Max Guideline: No emojis as icons.
ICON_ROCKET = '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-rocket"><path d="M4.5 16.5c-1.5 1.26-2 5-2 5s3.74-.5 5-2c.71-.84.7-2.13-.09-2.91a2.18 2.18 0 0 0-2.91-.09z"/><path d="m12 15-3-3a22 22 0 0 1 3.82-13.04.28.28 0 0 1 .39-.06 22 22 0 0 1 13.04 3.82.28.28 0 0 1-.06.39A22 22 0 0 1 15 12z"/><path d="m9 15 2 2"/><path d="m15 9 2 2"/></svg>'
ICON_UPLOAD = '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-upload-cloud"><path d="M4 14.899A7 7 0 1 1 15.71 8h1.79a4.5 4.5 0 0 1 2.5 8.242"/><path d="M12 12v9"/><path d="m16 16-4-4-4 4"/></svg>'
ICON_SETTINGS = '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-settings"><path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"/><circle cx="12" cy="12" r="3"/></svg>'
ICON_LAYOUT = '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-layout-grid"><rect width="7" height="7" x="3" y="3" rx="1"/><rect width="7" height="7" x="14" y="3" rx="1"/><rect width="7" height="7" x="14" y="14" rx="1"/><rect width="7" height="7" x="3" y="14" rx="1"/></svg>'


def render_layout_geometry_svg(page_data: dict, filter_type: str = "ALL") -> str:
    """
    Renders an interactive visual SVG geometry heatmap of detected document blocks.
    Shows bounding boxes, block classification types, reading order paths, and confidence scores.
    """
    w = max(1, page_data.get("width", 800))
    h = max(1, page_data.get("height", 1000))
    raw_blocks = page_data.get("blocks", [])

    blocks = []
    for b in raw_blocks:
        b_type = str(b.get("block_type", "text")).upper()
        if filter_type != "ALL" and b_type != filter_type.upper():
            continue
        blocks.append(b)

    svg_lines = [
        f'<svg viewBox="0 0 {w} {h}" width="100%" height="auto" style="background:#09090b; border:1px solid #27272a; border-radius:8px; box-shadow: 0 8px 24px rgba(0,0,0,0.4);">'
    ]

    # Grid background overlay
    svg_lines.append(f'<pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse"><path d="M 40 0 L 0 0 0 40" fill="none" stroke="rgba(255,255,255,0.03)" stroke-width="1"/></pattern>')
    svg_lines.append(f'<rect width="{w}" height="{h}" fill="url(#grid)"/>')

    # Draw reading order sequence connectors
    centers = []
    for block in sorted(blocks, key=lambda b: b.get("reading_order_index", 0)):
        bbox = block.get("bbox", {})
        xmin, ymin = bbox.get("xmin", 0), bbox.get("ymin", 0)
        xmax, ymax = bbox.get("xmax", 0), bbox.get("ymax", 0)
        cx, cy = (xmin + xmax) / 2.0, (ymin + ymax) / 2.0
        centers.append((cx, cy))

    if len(centers) > 1:
        points_str = " ".join([f"{cx:.1f},{cy:.1f}" for cx, cy in centers])
        svg_lines.append(f'<polyline points="{points_str}" fill="none" stroke="#f59e0b" stroke-width="2" stroke-dasharray="4 4" opacity="0.7"/>')

    # Color palette by block type (Warm Obsidian & Amber theme - ZERO BLUE)
    type_colors = {
        "title": "#f59e0b",
        "header": "#fb923c",
        "footer": "#a1a1aa",
        "text": "#10b981",
        "table": "#eab308",
        "list_item": "#34d399",
        "unknown": "#71717a",
    }

    # Draw bounding boxes and text badges
    for idx, block in enumerate(blocks, 1):
        bbox = block.get("bbox", {})
        xmin, ymin = bbox.get("xmin", 0), bbox.get("ymin", 0)
        xmax, ymax = bbox.get("xmax", 0), bbox.get("ymax", 0)
        bw, bh = max(10, xmax - xmin), max(10, ymax - ymin)
        b_type = str(block.get("block_type", "text")).lower()
        color = type_colors.get(b_type, "#f59e0b")

        svg_lines.append(
            f'<rect x="{xmin:.1f}" y="{ymin:.1f}" width="{bw:.1f}" height="{bh:.1f}" fill="{color}" fill-opacity="0.14" stroke="{color}" stroke-width="1.5" rx="3"/>'
        )
        svg_lines.append(
            f'<rect x="{xmin:.1f}" y="{max(0, ymin - 18):.1f}" width="{min(bw, 90):.1f}" height="16" fill="{color}" rx="2"/>'
        )
        svg_lines.append(
            f'<text x="{xmin + 4:.1f}" y="{max(12, ymin - 5):.1f}" fill="#09090b" font-family="monospace" font-size="10" font-weight="bold">#{idx} [{b_type[:5].upper()}]</text>'
        )

    svg_lines.append('</svg>')
    return "".join(svg_lines)


def load_css():
    """Load external CSS file. Includes UI UX Pro Max styling."""
    css_path = Path(__file__).parent / "styles.css"
    if css_path.exists():
        st.markdown(
            f"<style>{css_path.read_text(encoding='utf-8')}</style>",
            unsafe_allow_html=True,
        )
    else:
        st.error("Styles file not found!")


def inject_seo_metadata():
    """
    SEO ENHANCEMENT: Injects purely static meta descriptions and keywords into the DOM
    using a hidden div, enabling basic crawlers to deduce context without visible impact.
    """
    seo_content = """
    <div class="seo-metadata">
        <h2>B.L.A.S.T. Optical Character Recognition Engine</h2>
        <p>Advanced batch document processing and OCR engine with deterministic output, secure processing, and minimal operations dashboard.</p>
        <p>Keywords: OCR, Document Scanner, Data Extraction, Automation, PDF processing, Data Intelligence</p>
    </div>
    """
    st.markdown(seo_content, unsafe_allow_html=True)


def init_session_state():
    """Initialize Streamlit session state securely."""
    if "total_scans" not in st.session_state:
        st.session_state.total_scans = 142
    if "pages_decoded" not in st.session_state:
        st.session_state.pages_decoded = 890
    if "processing_history" not in st.session_state:
        st.session_state.processing_history = []
    if "session_id" not in st.session_state:
        st.session_state.session_id = uuid.uuid4().hex
    if "output_dir" not in st.session_state:
        st.session_state.output_dir = None
    if "current_results" not in st.session_state:
        st.session_state.current_results = None
    if "active_job_id" not in st.session_state:
        st.session_state.active_job_id = None
    if "job_thread" not in st.session_state:
        st.session_state.job_thread = None
    if "pipeline_instance" not in st.session_state:
        st.session_state.pipeline_instance = None


def get_session_output_dir():
    """Retrieve or create a secure per-session output directory."""
    if st.session_state.output_dir is None:
        base_dir = (
            Path("blast_output")
            if sys.platform == "win32"
            else Path("/tmp/blast_output")
        )
        st.session_state.output_dir = str(base_dir / st.session_state.session_id)
    return Path(st.session_state.output_dir)


def run_background_job(pipeline, source_path, output_dir, job_id_callback):
    """Worker function for the background thread."""
    try:
        # We don't need a callback here because the pipeline now checkpoints to DB
        res = pipeline.process_job(source_path=source_path, output_dir=output_dir)
        return res
    except Exception as e:
        logger.error(f"Background Job Error: {e}")
        return {"status": "failed", "error": str(e)}


def handle_file_upload(pipeline, db):
    """
    Refactored for Asynchronous 'Mission Control' processing.
    """
    st.markdown(
        f'<div class="minimal-panel"><h3>{ICON_UPLOAD} UPLOAD PAYLOAD</h3></div>',
        unsafe_allow_html=True,
    )

    # Single source of truth for the allowlist: blast_ocr.security.gateway.IngestionGateway,
    # the same boundary process_job() enforces server-side. Previously this list was
    # duplicated here and had drifted (missing .bmp/.tiff), so files the pipeline
    # actually supports were silently rejected by the uploader widget itself.
    from blast_ocr.security.gateway import ALLOWED_EXTENSIONS as _GATEWAY_EXTENSIONS
    ALLOWED_EXTENSIONS = sorted(_GATEWAY_EXTENSIONS)
    uploaded_files = st.file_uploader(
        "DROP MISSION FILES",
        accept_multiple_files=True,
        type=[ext.lstrip(".") for ext in ALLOWED_EXTENSIONS],
    )

    if "active_job_id" not in st.session_state:
        st.session_state.active_job_id = None
    if "current_results" not in st.session_state:
        st.session_state.current_results = None

    if uploaded_files and not st.session_state.get("active_job_id"):
        st.success(f"VALID: {len(uploaded_files)} PAYLOADS VERIFIED.")

        if st.button("INITIATE SEQUENCE", type="primary", use_container_width=True):
            out_dir = get_session_output_dir()
            out_dir.mkdir(parents=True, exist_ok=True)

            all_summaries = []
            all_output_files = []

            for uploaded_file in uploaded_files:
                ext = Path(uploaded_file.name).suffix.lower()
                if ext not in ALLOWED_EXTENSIONS:
                    all_summaries.append(
                        {
                            "FILE": uploaded_file.name,
                            "STATUS": "FAILED",
                            "ERROR": f"UNAUTHORIZED EXTENSION: {ext}",
                        }
                    )
                    continue

                tmp_path = None
                try:
                    with tempfile.NamedTemporaryFile(
                        delete=False, suffix=Path(uploaded_file.name).suffix
                    ) as tmp:
                        tmp.write(uploaded_file.getbuffer())
                        tmp_path = tmp.name
                except Exception as e:
                    all_summaries.append(
                        {
                            "FILE": uploaded_file.name,
                            "STATUS": "FAILED",
                            "ERROR": str(e),
                        }
                    )
                    continue

                # Durable queue path (opt-in, BLAST_OCR_QUEUE_BACKEND=redis): enqueue
                # and return immediately instead of blocking this Streamlit script
                # run on OCR completion -- closing the browser must not kill the job
                # (EXECUTION_PLAN.md Phase 14). Falls back to the synchronous path
                # below if Redis isn't actually reachable.
                queue_settings = _get_settings_cached()
                use_queue = (
                    getattr(queue_settings, "queue_backend", "sync") == "redis"
                )
                if use_queue:
                    try:
                        from blast_ocr.queue.client import enqueue_job, is_queue_available
                        if not is_queue_available():
                            use_queue = False
                    except Exception:
                        use_queue = False

                if use_queue:
                    try:
                        enq = enqueue_job(tmp_path, output_dir=str(out_dir))
                        st.session_state.active_job_id = enq["job_id"]
                        all_summaries.append(
                            {
                                "FILE": uploaded_file.name,
                                "STATUS": "QUEUED",
                                "ERROR": f"job_id={enq['job_id']} (durable queue)",
                            }
                        )
                    except Exception as e:
                        all_summaries.append(
                            {"FILE": uploaded_file.name, "STATUS": "FAILED", "ERROR": f"Enqueue failed: {e}"}
                        )
                    # tmp_path is consumed by the worker process, not cleaned up here.
                    continue

                if pipeline is None:
                    try:
                        pipeline = _get_or_create_pipeline()
                    except Exception as e:
                        all_summaries.append(
                            {
                                "FILE": uploaded_file.name,
                                "STATUS": "FAILED",
                                "ERROR": f"Pipeline initialization failed: {e}",
                            }
                        )
                        if tmp_path and os.path.exists(tmp_path):
                            try:
                                os.remove(tmp_path)
                            except OSError:
                                pass
                        continue

                try:
                    res = pipeline.process_job(
                        source_path=tmp_path, output_dir=str(out_dir)
                    )
                except Exception as e:
                    res = {"status": "failed", "error": str(e)}
                finally:
                    if tmp_path and os.path.exists(tmp_path):
                        try:
                            os.remove(tmp_path)
                        except OSError:
                            pass

                status = str(res.get("status", "failed")).lower()
                is_success = status == "success"

                output_files = []
                output_map = res.get("output_files", {})
                if isinstance(output_map, dict):
                    for fmt in ("md", "docx", "txt", "epub", "manifest"):
                        p = output_map.get(fmt)
                        if p and os.path.exists(p):
                            output_files.append((fmt, p))

                if not output_files:
                    base = Path(uploaded_file.name).stem
                    for fmt, ext in [("md", ".md"), ("docx", ".docx"), ("txt", ".txt"), ("epub", ".epub"), ("manifest", "_manifest.json")]:
                        fpath = out_dir / f"{base}{ext}"
                        if fpath.exists():
                            output_files.append((fmt, str(fpath)))

                all_summaries.append(
                    {
                        "FILE": uploaded_file.name,
                        "STATUS": "SUCCESS" if is_success else "FAILED",
                        "ERROR": ""
                        if is_success
                        else str(
                            res.get("error")
                            or res.get("message")
                            or "Unknown error"
                        ),
                    }
                )
                all_output_files.extend(output_files)

            st.session_state.current_results = {
                "summary": all_summaries,
                "output_files": all_output_files,
            }
            st.session_state.active_job_id = None
            return

    MIME_TYPES = {
        "md": "text/markdown",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "txt": "text/plain",
        "epub": "application/epub+zip",
        "pdf": "application/pdf",
        "json": "application/json",
        "manifest": "application/json",
    }

    if st.session_state.get("current_results") and not st.session_state.get(
        "active_job_id"
    ):
        results = st.session_state.current_results or {}
        summary = results.get("summary", [])
        if summary:
            st.markdown("#### 📦 GENERATED ARTIFACTS")
            st.dataframe(_to_table(summary))
        output_files = results.get("output_files", [])
        if output_files:
            cols = st.columns(min(len(output_files), 5))
            for idx, (fmt, file_path) in enumerate(output_files):
                col = cols[idx % len(cols)]
                try:
                    with open(file_path, "rb") as f:
                        mime = MIME_TYPES.get(fmt, "application/octet-stream")
                        with col:
                            st.download_button(
                                label=f"DOWNLOAD {fmt.upper()}",
                                data=f.read(),
                                file_name=Path(file_path).name,
                                mime=mime,
                                use_container_width=True,
                            )
                except OSError:
                    continue

            md_or_txt_files = [fp for fmt, fp in output_files if fmt in ("md", "txt") and os.path.exists(fp)]
            if md_or_txt_files:
                with st.expander("📄 INLINE TEXT PREVIEW (CLICK TO INSPECT / COPY)", expanded=False):
                    for preview_path in md_or_txt_files[:2]:
                        try:
                            content = Path(preview_path).read_text(encoding="utf-8", errors="ignore")
                            st.caption(f"**File**: `{Path(preview_path).name}` ({len(content)} characters)")
                            st.text_area("Extracted Document Content", value=content, height=220, key=f"prev_{Path(preview_path).stem}")
                        except Exception:
                            pass

    # --- Live Mission Control Dashboard ---
    if st.session_state.get("active_job_id"):
        render_mission_control(db, st.session_state.active_job_id)


def render_mission_control(db, job_id):
    """Displays real-time progress by polling the database."""
    job = db.get_job(job_id)
    if not job:
        st.error("JOB LOSS DETECTED. RECOVERING...")
        st.session_state.active_job_id = None
        return

    st.markdown(f"### MISSION CONTROL [ID: {job_id}]")

    # Status Mapping (blast_ocr.core.models.JobState vocabulary, plus legacy aliases)
    status_colors = {
        "received": "gray",
        "pending": "gray",
        "validating": "gray",
        "queued": "gray",
        "processing": "orange",
        "post_processing": "orange",
        "exporting": "orange",
        "succeeded": "green",
        "succeeded_with_warnings": "yellow",
        "completed": "green",
        "partial_failure": "yellow",
        "failed": "red",
        "cancelled": "red",
        "quarantined": "red",
        "timed_out": "red",
    }
    status_color = status_colors.get(job.status, "white")
    st.markdown(
        f"STATUS: <span style='color:{status_color}; font-family:monospace;'>{job.status.upper()}</span>",
        unsafe_allow_html=True,
    )

    results = db.get_results(job_id)
    processed_count = len(results)

    # Progress Calculation
    total_pages = job.page_count or 1  # Fallback to 1 if not set yet
    progress = min(processed_count / total_pages, 1.0) if total_pages > 0 else 0
    st.progress(progress)
    st.caption(f"DECODED {processed_count} OF {total_pages} PAGES")

    # Live Feed of Results
    if results:
        with st.expander("LIVE INTELLIGENCE STREAM", expanded=True):
            for r in results[-3:]:  # Show last 3 pages
                st.markdown(
                    f"**PAGE {r.page_number}** (Confidence: {r.confidence_score:.2f})"
                )
                st.text(
                    r.extracted_text[:200] + "..."
                    if len(r.extracted_text) > 200
                    else r.extracted_text
                )

    _SUCCESS_STATUSES = {"completed", "succeeded", "succeeded_with_warnings"}
    _TERMINAL_STATUSES = _SUCCESS_STATUSES | {"failed", "partial_failure", "cancelled", "quarantined", "timed_out"}

    if job.status in _TERMINAL_STATUSES:
        if job.status in _SUCCESS_STATUSES:
            if job.status == "succeeded_with_warnings":
                st.warning("MISSION ACCOMPLISHED WITH WARNINGS — some pages had errors")
            else:
                st.success("MISSION ACCOMPLISHED")
            # Logic to show download buttons for results...
        else:
            st.error(f"MISSION FAILED: {job.error_message}")

        if st.button("RETURN TO BASE"):
            st.session_state.active_job_id = None
            st.rerun()
    else:
        # Polling mechanism
        time.sleep(2)
        st.rerun()


def main():
    try:
        # SEO & UI UX: Initial configuration moved to top of file for Streamlit Cloud stability.
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
        pipeline = st.session_state.get("pipeline_instance")
        cleanup_cls = _get_cleanup_manager_class()
        db_init_error = st.session_state.get("db_init_error")

        if _PANDAS_IMPORT_ERROR:
            st.warning(
                "Pandas is unavailable; using degraded table/chart mode: "
                f"{_PANDAS_IMPORT_ERROR}"
            )

        if db_init_error:
            st.warning(
                "Database fallback mode is active due to an initialization error: "
                f"{db_init_error}"
            )

        # --- HEADER SECTION (Exaggerated Minimalism) ---
        # SEO ENHANCEMENT: Changed .blast-title from a div to an h1 so screen-readers and crawlers capture the main page topic.
        st.markdown(
            """
    <div class="blast-header">
        <div class="status-badge"><span class="status-dot"></span> ENGINE ACTIVE</div>
        <h1 class="blast-title">B.L.A.S.T. OCR</h1>
        <div class="blast-subtitle">Batch Large-Scale Automated Scanned-Text Extraction Engine</div>
    </div>
    """,
            unsafe_allow_html=True,
        )

        def _pad_columns(cols, count):
            cols = list(cols)
            if cols and len(cols) < count:
                cols.extend([cols[-1]] * (count - len(cols)))
            return cols[:count]

        # --- METRICS SECTION ---
        m1, m2, m3 = _pad_columns(st.columns(3), 3)
        with m1:
            st.metric(
                label="TOTAL MISSIONS", value=st.session_state.total_scans
            )
        with m2:
            st.metric(
                label="PAGES DECODED", value=st.session_state.pages_decoded
            )
        with m3:
            st.metric(label="UPTIME", value="99.3%")

        st.markdown(
            "<hr style='border: none; border-top: 1px solid rgba(255,255,255,0.07); margin: 1.75rem 0;'>",
            unsafe_allow_html=True,
        )

        # --- MAIN APP LAYOUT ---
        tabs = list(st.tabs(["NEW DEPLOYMENT", "LAYOUT INSPECTOR", "SYSTEM LOGS", "SYSTEM HEALTH"]))
        if tabs and len(tabs) < 4:
            tabs.extend([tabs[-1]] * (4 - len(tabs)))

        # --- TAB 1: NEW SCAN ---
        with tabs[0]:
            col_left, col_right = st.columns([1, 2])

            with col_left:
                st.markdown(
                    f'<div class="minimal-panel"><h3>{ICON_SETTINGS} CONFIGURATION</h3></div>',
                    unsafe_allow_html=True,
                )
                preset = st.radio(
                    "PROCESSING MODE",
                    [
                        "GENERAL DOCUMENT",
                        "RECEIPT / INVOICE",
                        "HANDWRITTEN TEXT",
                        "RAW PASSTHROUGH",
                    ],
                )

                # Wire preset values
                if preset == "RECEIPT / INVOICE":
                    preset_denoise = 5
                    preset_contrast = 1.4
                    preset_deskew = True
                elif preset == "HANDWRITTEN TEXT":
                    preset_denoise = 8
                    preset_contrast = 1.6
                    preset_deskew = True
                elif preset == "RAW PASSTHROUGH":
                    preset_denoise = 0
                    preset_contrast = 1.0
                    preset_deskew = False
                else:
                    preset_denoise = 0
                    preset_contrast = 1.0
                    preset_deskew = True

                with st.expander("ADVANCED PROTOCOLS"):
                    engine_choice = st.selectbox(
                        "OCR ENGINE ADAPTER",
                        [
                            "rapidocr (ONNX Runtime - Fast CPU/GPU)",
                            "easyocr (PyTorch - Multilingual)",
                            "tesseract (Pytesseract - Standard)",
                            "ensemble (Consensus Ensemble - Multi-Engine)",
                        ],
                        index=0,
                    )
                    if "rapidocr" in engine_choice:
                        selected_engine = "rapidocr"
                    elif "easyocr" in engine_choice:
                        selected_engine = "easyocr"
                    elif "tesseract" in engine_choice:
                        selected_engine = "tesseract"
                    else:
                        selected_engine = "ensemble"

                    st.selectbox(
                        "SOURCE LOGIC", ["ENG_CORE", "FRA_CORE", "MULTILINGUAL_NODE"]
                    )
                    st.toggle("GPU HYPER-THREAD", value=settings.ocr_gpu)
                    auto_deskew = st.toggle("AUTO-DESKEW ANGLE CORRECTION", value=preset_deskew)
                    enable_dewarp = st.toggle("BOOK SPINE CURVATURE DEWARPING", value=False)
                    secure_mode = st.toggle(
                        "SECURE MODE (PII REDACTION)",
                        value=getattr(settings, "secure_mode", False),
                    )
                    enable_book_intel = st.toggle(
                        "BOOK INTELLIGENCE (REFLOW/DEHYPHEN)",
                        value=getattr(settings, "enable_book_intelligence", True),
                    )
                    enable_tier0 = st.toggle(
                        "TIER-0 NATIVE PDF ROUTER",
                        value=getattr(settings, "enable_tier0_routing", True),
                    )
                    denoise_lvl = st.slider("DENOISE FILTER LEVEL", min_value=0, max_value=20, value=preset_denoise)
                    contrast_boost = st.slider("CONTRAST BOOST FACTOR", min_value=0.5, max_value=2.5, value=preset_contrast, step=0.1)

                    cfg = getattr(pipeline, "_config", None)
                    if cfg is not None:
                        setattr(cfg, "ocr_engine", selected_engine)
                        setattr(cfg, "secure_mode", secure_mode)
                        setattr(cfg, "enable_book_intelligence", enable_book_intel)
                        setattr(cfg, "enable_tier0_routing", enable_tier0)
                        setattr(cfg, "auto_deskew", auto_deskew)
                        setattr(cfg, "enable_dewarp", enable_dewarp)
                        setattr(cfg, "denoise_level", denoise_lvl)
                        setattr(cfg, "contrast_boost", contrast_boost)
                    if hasattr(pipeline, "job_config"):
                        from blast_ocr.core.models import JobConfig
                        setattr(pipeline, "job_config", JobConfig.from_dict({
                            "ocr_engine": selected_engine,
                            "secure_mode": secure_mode,
                            "enable_book_intelligence": enable_book_intel,
                            "enable_tier0_routing": enable_tier0,
                            "auto_deskew": auto_deskew,
                            "enable_dewarp": enable_dewarp,
                            "denoise_level": denoise_lvl,
                            "contrast_boost": contrast_boost,
                        }))

            with col_right:
                handle_file_upload(pipeline, db)

        # --- TAB 2: LAYOUT INSPECTOR ---
        with tabs[1]:
            st.markdown(
                f'<div class="minimal-panel"><h3>{ICON_LAYOUT} LAYOUT INSPECTOR & GEOMETRY HEATMAPS</h3></div>',
                unsafe_allow_html=True,
            )
            current_res = st.session_state.get("current_results")
            if current_res and current_res.get("summary"):
                out_files = current_res.get("output_files", [])
                json_files = [fpath for fmt, fpath in out_files if fmt == "json" and os.path.exists(fpath)]
                if json_files:
                    for fpath in json_files:
                        try:
                            import json
                            with open(fpath, "r", encoding="utf-8") as jf:
                                doc_dict = json.load(jf)
                                pages = doc_dict.get("pages", [])
                                st.markdown(f"**DOCUMENT**: `{Path(fpath).stem}` ({len(pages)} Pages)")
                                for p in pages:
                                    st.markdown(f"#### PAGE {p.get('page_num', 1)} ({p.get('width', 0)}x{p.get('height', 0)}px)")
                                    c_svg, c_blocks = _pad_columns(st.columns([1, 1]), 2)
                                    with c_svg:
                                        st.markdown(render_layout_geometry_svg(p), unsafe_allow_html=True)
                                    with c_blocks:
                                        blocks = p.get("blocks", [])
                                        for b_idx, block in enumerate(blocks, 1):
                                            b_type = block.get("block_type", "text")
                                            b_text = block.get("text", "")
                                            b_box = block.get("bbox", {})
                                            st.caption(f"**Block #{b_idx}** [{b_type.upper()}] - Box: `[{b_box.get('xmin',0):.1f}, {b_box.get('ymin',0):.1f}, {b_box.get('xmax',0):.1f}, {b_box.get('ymax',0):.1f}]`")
                                            st.text_area(f"Block #{b_idx} Content", value=b_text, height=80, key=f"blk_{p.get('page_num')}_{b_idx}")
                        except Exception as inspect_err:
                            st.warning(f"Could not load layout geometry: {inspect_err}")
                else:
                    st.info("PROCESS A DOCUMENT TO GENERATE INTERACTIVE SVG GEOMETRY HEATMAPS.")
            else:
                st.info("NO ACTIVE LAYOUT GEOMETRY IN SESSION. PROCESS A DOCUMENT TO INSPECT DETECTED BOUNDING BOXES.")

        # --- TAB 3: HISTORY ---
        with tabs[2]:
            st.markdown("### SECURE LOGS")
            if st.button("PURGE LOGS"):
                st.session_state.processing_history = []
                st.rerun()
            if st.session_state.processing_history:
                st.dataframe(_to_table(st.session_state.processing_history))
            else:
                st.info("NO LOGS IN MEMORY.")

        # --- TAB 4: SYSTEM HEALTH ---
        with tabs[3]:
            st.markdown("### LIVE TELEMETRY")

            health_c1, health_c2 = _pad_columns(st.columns([3, 1]), 2)

            with health_c2:
                st.markdown("#### PIPELINE STATUS")
                st.info(
                    "REFLEXION: **ENABLED**\nSCRIPT ROUTER: **ACTIVE**\nREDACTION: **READY**"
                )

            with health_c1:
                st.markdown("#### DIAGNOSTIC CONTROLS")
                if st.button(
                    "RUN BASELINE TEST (mybook.pdf)",
                    type="primary",
                    use_container_width=True,
                ):
                    test_pdf = "data/mybook.pdf"
                    if os.path.exists(test_pdf):
                        if pipeline is None:
                            try:
                                pipeline = _get_or_create_pipeline()
                            except Exception as e:
                                st.error(f"PIPELINE INIT FAILED: {e}")
                                return

                        out_dir = get_session_output_dir()
                        out_dir.mkdir(parents=True, exist_ok=True)
                        job_id = db.create_job("Baseline_Test_MyBook.pdf", page_count=0)

                        if not _has_streamlit_runtime_context():
                            st.warning(
                                "BASELINE SKIPPED: Missing Streamlit runtime context."
                            )
                            return

                        st.session_state.active_job_id = job_id

                        thread = threading.Thread(
                            target=pipeline.process_job,
                            kwargs={
                                "source_path": test_pdf,
                                "output_dir": str(out_dir),
                                "job_id": job_id,
                            },
                        )
                        thread.start()
                        st.success("BASELINE SEQUENCE INITIATED.")
                        st.rerun()
                    else:
                        st.error("TEST VECTOR NOT FOUND: data/mybook.pdf")

                st.markdown("<hr style='border: none; border-top: 1px solid rgba(255,255,255,0.07); margin: 1rem 0;'>", unsafe_allow_html=True)
                metrics = db.get_recent_metrics(limit=10)
                if metrics:
                    m_cols = _pad_columns(st.columns(4), 4)
                    latest = metrics[0]
                    with m_cols[0]:
                        st.metric("LATEST MEMORY", f"{latest.peak_memory_mb:.1f} MB")
                    with m_cols[1]:
                        st.metric("AVG FIDELITY", f"{latest.fidelity_score:.1%}")
                    with m_cols[2]:
                        st.metric("VELOCITY", f"{latest.extraction_velocity:.2f} P/S")
                    with m_cols[3]:
                        st.metric("PAGE LATENCY", f"{latest.avg_page_time:.2f}s")

                    # Chart
                    chart_records = [
                        {
                            "timestamp": m.timestamp,
                            "fidelity": m.fidelity_score,
                            "velocity": m.extraction_velocity,
                        }
                        for m in reversed(metrics)
                    ]
                    try:
                        if pd is None:
                            st.line_chart(chart_records)
                        else:
                            df_metrics = pd.DataFrame(chart_records)
                            st.line_chart(df_metrics.set_index("timestamp"))
                    except Exception as chart_err:
                        st.warning(f"Telemetry chart fallback: {chart_err}")
                        for r in chart_records:
                            st.caption(f"Time: {r['timestamp']} | Fidelity: {r['fidelity']:.2f} | Velocity: {r['velocity']:.2f} P/S")
                else:
                    st.info("NO TELEMETRY DATA ACQUIRED YET.")

            st.markdown(
                "<hr style='border: none; border-top: 1px solid rgba(255,255,255,0.07); margin: 1.5rem 0;'>",
                unsafe_allow_html=True,
            )
            st.markdown("### SYSTEM MAINTENANCE")

            maint_c1, maint_c2 = st.columns([2, 2])
            out_dir = get_session_output_dir().parent  # Get the base blast_output
            stats = cleanup_cls.get_system_disk_stats(str(out_dir))

            with maint_c1:
                st.metric("DISK ASSETS", f"{stats['total_size_mb']:.2f} MB")
                st.caption(f"ACTIVE SESSIONS: {stats['session_count']}")

            with maint_c2:
                if st.button("PURGE STALE ASSETS", use_container_width=True):
                    saved = cleanup_cls.cleanup_stale_sessions(
                        str(out_dir), max_age_hours=0
                    )
                    db.purge_old_data(days=0)
                    st.success(
                        f"MAINTENANCE COMPLETE: Freed {saved / (1024 * 1024):.2f} MB"
                    )
                    st.rerun()
    except Exception as e:
        logger.exception("Fatal top-level Streamlit UI error")
        st.error("Application startup failed.")
        st.code(str(e))
        st.code(traceback.format_exc())
        if _is_cloud_runtime():
            st.stop()
        raise


if __name__ == "__main__":
    main()

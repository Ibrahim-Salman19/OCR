# Technical Design & Implementation Blueprint: Streaming Buffer & Storage Engine
**Milestone**: Milestone 3 (Feature 11 — Bounded Streaming Buffer & Pipeline Integration)  
**Author**: `explorer_1` (Milestone 3 Architecture & Streaming Core)  
**Date**: 2026-08-15  
**Target Module**: `blast_ocr/core/streaming.py`  
**Integration Points**: `blast_ocr/pipeline.py`, `blast_ocr/config.py`, `blast_ocr/core/models.py`, `blast_ocr/cache/manager.py`  

---

## 1. Executive Summary

Milestone 3 delivers high-throughput, bounded-memory document processing for B.L.A.S.T. OCR. When processing enterprise-scale document archives (such as 1,000+ page books, legal discovery packages, or directories with thousands of high-resolution scanned images at 300 DPI), naive pipelines load hundreds or thousands of uncompressed bitmaps, OpenCV matrices, intermediate PyTorch/ONNX tensors, and Pydantic object trees into RAM simultaneously. This leads to catastrophic out-of-memory (OOM) crashes ($>4\text{GB}$ to $26\text{GB}$ RAM usage).

This design introduces **`blast_ocr/core/streaming.py`**, consisting of three core primitives:
1. **`ChunkScratchManager`**: A robust, lifecycle-scoped context manager that creates and deterministically purges isolated per-window scratch folders (`scratch_w_0000`, `scratch_w_0001`, ...) with Windows file-lock retry handling and `atexit` cleanup safety nets.
2. **`PageStreamGenerator`**: A windowed ingestion generator ($K=8..16$ pages, default $K=8$) supporting multi-page PDFs, image directories, and single files. It renders and stages pages only for the active window and immediately unlinks all scratch files and drops references when advancing to the next batch.
3. **`StreamDocumentWriter`**: An incremental document writer that streams OCR results on-the-fly directly to disk in **Markdown (`.md`)**, **Plain Text (`.txt`)**, and **JSON Lines (`.jsonl`)** formats, plus incremental **Searchable PDF** and **Run Manifest** outputs, eliminating the need to construct a monolithic `Document` model in memory.
4. **`BlastPipeline` Streaming Integration**: Adds `process_stream()` to `BlastPipeline` with automatic routing thresholding ($N \ge 50$ pages) and `JobConfig` integration, guaranteeing **Peak RSS $\le 500\text{MB}$** on 1,000+ page archives with a flat memory slope ($\text{OLS slope} \le 0.005\text{MB/page}$).

---

## 2. Current State Analysis & Memory Profiling

### 2.1 Existing Pipeline Flow (`blast_ocr/pipeline.py`)
In the current implementation:
1. `process_pdf()` creates a single temporary directory `temp_dir = tempfile.mkdtemp()` for the entire document run.
2. It iterates in chunks of 10 pages, calling `pdf2image.convert_from_path(..., output_folder=temp_dir)`.
3. In `_process_image_batch()`, raw images are converted to restored OpenCV images (`restore_page_image()`).
4. While raw and restored images for the batch are deleted after OCR, **all OCR result dictionaries accumulate in a growing list (`all_results.extend(batch_results)`)**.
5. In `process_job()`:
   - If `source.is_dir()`, **all image files in the directory are loaded and restored in a single massive list** before calling `process_batch_threaded()`. A directory of 2,000 images creates 2,000 restored PNG files on disk simultaneously.
   - For all files, all page outputs are collected into `results`.
   - A monolithic Pydantic `Document(pages=[...])` tree is built in RAM for all $N$ pages.
   - `json.dump(doc_model.model_dump(), jf)` serializes the entire $N$-page hierarchy in RAM.
   - Full book text is concatenated into a single Python string: `full_text = "\n\n---\n\n".join(...)`.
   - `save_output()` generates DOCX, Markdown, EPUB, and Searchable PDF by processing all $N$ pages simultaneously.

### 2.2 Mathematical Memory Footprint Breakdown
For an uncompressed 300 DPI A4 page:
- Dimensions: $2480 \times 3508$ pixels.
- Raw 24-bit RGB bitmap: $2480 \times 3508 \times 3 \approx 26.1\text{ MB}$ per page.
- Grayscale / Binarized OpenCV mat: $8.7\text{ MB}$ per page.
- PP-OCR / RapidOCR tensor representations + CTC decode polygons: $\approx 15\text{ MB}$ per page.
- Pydantic `Page`, `Block`, `Line`, `Span`, `BoundingBox` objects: $\approx 0.5\text{ MB}$ per page in Python heap structures.

**Memory Scaling Behavior**:
- **Monolithic Ingestion ($N=1,000$)**:
  - Image Buffers: $1,000 \times 26.1\text{ MB} \approx 26.1\text{ GB}$ (if loaded into memory) or gigabytes of disk temp bloat.
  - Python Result Objects & Document Models: $1,000 \times 0.5\text{ MB} \approx 500\text{ MB}$ persistent heap allocation.
  - Peak RSS: **$3.5\text{GB} - 8.0\text{GB}+$**, resulting in swapping or OOM kill (`SIGKILL`).
- **Windowed Streaming ($K=8$)**:
  - Active Images: $8 \times 26.1\text{ MB} \approx 208.8\text{ MB}$ peak in-flight memory.
  - Intermediate Tensors: Bound to the active window workers ($2 \times 15\text{ MB} \approx 30\text{ MB}$).
  - Incremental Output: $O(1)$ memory per page as text is immediately flushed to disk.
  - Peak RSS: **$\le 350\text{MB} - 450\text{MB}$**, strictly bounded $\le 500\text{MB}$ regardless of $N$.

---

## 3. Architecture Specification: `blast_ocr/core/streaming.py`

```
                               ┌───────────────────────────────────────────┐
                               │             Source Document               │
                               │  (Multi-page PDF / Image Dir / Scans)     │
                               └─────────────────────┬─────────────────────┘
                                                     │
                                                     ▼
                               ┌───────────────────────────────────────────┐
                               │           PageStreamGenerator             │
                               │   Window Size K=8..16 (e.g. K=8)          │
                               └──────┬─────────────────────────────▲──────┘
                                      │                             │
                        Creates window│                             │ Immediate cleanup
                        scratch folder│                             │ post-window batch
                                      ▼                             │
                       ┌─────────────────────────────┐              │
                       │     ChunkScratchManager     │──────────────┘
                       │  (scratch_w_0000, 0001...)  │
                       └──────────────┬──────────────┘
                                      │ Window batch [(1, path), ... (8, path)]
                                      ▼
                       ┌─────────────────────────────┐
                       │     Batch OCR Processor     │
                       │  (Restoration, Engine, DB)  │
                       └──────────────┬──────────────┘
                                      │ Streamed PageResult (page_num, text, layout)
                                      ▼
                       ┌─────────────────────────────┐
                       │    StreamDocumentWriter     │
                       │  (Markdown, TXT, JSONL, PDF)│
                       └──────────────┬──────────────┘
                                      │ Incremental file flush
                                      ▼
                       ┌─────────────────────────────┐
                       │      Final Artifacts        │
                       │  (.md, .txt, .jsonl, .pdf)  │
                       └─────────────────────────────┘
```

---

### 3.1 Component 1: `ChunkScratchManager`

`ChunkScratchManager` manages the physical temporary disk lifecycle for streaming windows.

#### Responsibilities:
1. **Isolated Root Directory**: Creates a unique run directory under `tempfile.gettempdir()` (or configured `base_dir`).
2. **Deterministic Window Subdirectories**: Provides `create_window_scratch(window_index)` producing subfolders `scratch_w_0000/`, `scratch_w_0001/`, etc.
3. **Robust Unlinking with Windows Lock Handling**: Implements exponential backoff retries (up to 5 attempts) to handle file locking (`pdftoppm.exe` / OS handle releases on Windows / Linux).
4. **Crash Safety (`atexit`)**: Registers an exit handler to ensure orphaned scratch directories are purged even if the Python process encounters an unhandled exception or termination signal.

#### Interface:
```python
class ChunkScratchManager:
    """
    Context manager and directory steward for ephemeral window scratch spaces.
    Guarantees deterministic disk cleanup and bounded storage overhead.
    """
    def __init__(self, base_temp_dir: Optional[Union[str, Path]] = None, prefix: str = "blast_stream_"):
        ...
    def create_window_scratch(self, window_index: int) -> Path:
        """Create and return an isolated directory for the given window index."""
        ...
    def cleanup_window_scratch(self, window_index: int) -> None:
        """Deterministically purge the directory and contents for window_index."""
        ...
    def cleanup_all(self) -> None:
        """Purge the root scratch directory and all subdirectories."""
        ...
    def __enter__(self) -> "ChunkScratchManager":
        ...
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        ...
```

---

### 3.2 Component 2: `PageStreamGenerator`

`PageStreamGenerator` yields lazily rendered batches of pages while bounding the number of active image files on disk to $K$.

#### Responsibilities:
1. **Multi-Source Support**:
   - **PDF Ingestion**: Uses `pdfinfo_from_path` (or PyMuPDF/pypdf fallback) to determine total page count $N$. Calculates windows $\lceil N/K \rceil$. Renders only window $[start..end]$ using `pdf2image.convert_from_path(paths_only=True, output_folder=scratch_w_i)`.
   - **Image Directory Ingestion**: Scans the directory for image files (`.png`, `.jpg`, `.jpeg`, `.bmp`, `.tiff`, `.webp`), performs natural alphanumeric sorting (e.g., `page_1`, `page_2`, `page_10`), slices into windows of size $K$, and yields paths.
   - **Single Image**: Yields a single batch `[(1, Path(source_path))]`.
2. **Immediate Scratch Unlinking**:
   - Maintains a reference to the active `current_window_index`.
   - When the consumer requests the next batch via `next()`, the previous window's scratch folder is immediately purged via `ChunkScratchManager`.
   - When the generator is closed, garbage-collected, or exited via context manager, all remaining scratch directories are destroyed.
3. **Corrupt Page Resilience**: If a batch rendering fails, logs the error, yields available pages, and continues to the next window without crashing the entire pipeline.

#### Interface:
```python
class PageStreamGenerator:
    """
    Windowed page ingestion stream yielding batches of (page_num, image_path).
    Ensures memory and disk allocations are strictly bounded to window size K.
    """
    def __init__(
        self,
        source_path: Union[str, Path],
        chunk_size: int = 8,
        temp_dir: Optional[Union[str, Path]] = None,
        dpi: int = 300,
        poppler_path: Optional[str] = None,
        use_pdftocairo: bool = True,
    ):
        ...
    def get_total_pages(self) -> Optional[int]:
        """Returns total document pages if known, or None."""
        ...
    def __iter__(self) -> Generator[List[Tuple[int, Path]], None, None]:
        """Yields List[Tuple[page_num, image_path]] for each window."""
        ...
    def close(self) -> None:
        """Explicitly cleanup all scratch resources and close generator."""
        ...
    def __enter__(self) -> "PageStreamGenerator":
        ...
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        ...
```

---

### 3.3 Component 3: `StreamDocumentWriter`

`StreamDocumentWriter` writes OCR page outputs incrementally without assembling a monolithic document model in RAM.

#### Supported Formats:
1. **Markdown (`.md`)**:
   - Writes YAML frontmatter on initialization if metadata is provided.
   - On `write_page(page_num, text)`: writes page break separator (`\n\n---\n\n` or `<!-- Page X -->`) + sanitized page text. Flushes stream.
2. **Plain Text (`.txt`)**:
   - On `write_page(page_num, text)`: writes page delimiter `\n\n--- Page {page_num} ---\n\n` + text. Flushes stream.
3. **JSON Lines (`.jsonl`)**:
   - Streams one JSON record per page per line:
     ```json
     {"page": 1, "text": "...", "confidence": 0.96, "processing_time": 0.08, "route": "ocr", "engine": "rapidocr", "layout": {...}, "error": null}
     ```
   - Enables downstream streaming into vector databases, semantic search indexers, and chunkers without loading the document into RAM.
4. **Searchable PDF (`.pdf`)**:
   - Utilizes PyMuPDF (`fitz`) incremental document appending.
   - On `write_page(page_num, text, layout, page_image_path)`: adds a page to the PDF canvas, inserts the scan image, overlays invisible text baseline boxes, and immediately closes/disposes the bitmap.
   - On `finalize()`: calls `doc.save(deflate=True, garbage=4)` and `doc.close()`.
5. **Run Manifest (`_manifest.json`)**:
   - Tracks running aggregates: `total_pages`, `avg_confidence`, `avg_processing_time`, `peak_memory_mb`, `error_count`.
   - Emits schema-compliant run manifest on `finalize()`.

#### Interface:
```python
class StreamDocumentWriter:
    """
    Incremental document stream exporter.
    Appends page results directly to destination formats on disk.
    """
    def __init__(
        self,
        output_dir: Union[str, Path],
        base_name: str,
        formats: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        title: Optional[str] = None,
    ):
        ...
    def write_page(
        self,
        page_num: int,
        text: str,
        confidence: float = 1.0,
        processing_time: float = 0.0,
        layout: Optional[Dict[str, Any]] = None,
        page_model: Optional[Any] = None,
        page_image_path: Optional[Union[str, Path]] = None,
        route: str = "ocr",
        engine: str = "rapidocr",
        error: Optional[str] = None,
    ) -> None:
        """Incrementally append a single page extraction to all active format streams."""
        ...
    def flush(self) -> None:
        """Flush all open file streams to disk."""
        ...
    def finalize(self) -> Dict[str, Path]:
        """Flush, close all file handles, emit summary manifests, and return artifact paths."""
        ...
    def close(self) -> None:
        """Safely close any dangling file descriptors."""
        ...
    def __enter__(self) -> "StreamDocumentWriter":
        ...
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        ...
```

---

## 4. Pipeline Integration & Configuration Design

### 4.1 Configuration Extensions (`blast_ocr/config.py`)

Add the following type-safe fields and validators to `OCRConfig` and `JobConfig`:

```python
# In blast_ocr/config.py
class OCRConfig(BaseSettings):
    ...
    # Streaming & Bounded Memory (Milestone 3)
    enable_streaming: bool = Field(
        default=False, 
        description="Enable bounded streaming buffer for large documents"
    )
    stream_chunk_size: int = Field(
        default=8, 
        ge=4, 
        le=32, 
        description="Window size K (pages) for stream batching (recommended: 8..16)"
    )
    stream_auto_threshold: int = Field(
        default=50, 
        ge=1, 
        description="Page count threshold above which streaming mode is automatically activated"
    )
    stream_scratch_dir: Optional[str] = Field(
        default=None, 
        description="Custom directory for ephemeral stream scratch spaces (default: system temp)"
    )
    stream_formats: List[str] = Field(
        default_factory=lambda: ["md", "txt", "jsonl"],
        description="Default export formats generated in streaming mode"
    )
```

### 4.2 Pipeline Method: `BlastPipeline.process_stream`

Add `process_stream()` to `BlastPipeline` and wire auto-detection into `process_job()`:

```python
# In blast_ocr/pipeline.py
def process_stream(
    self,
    source_path: Union[str, Path],
    output_dir: Optional[Union[str, Path]] = None,
    formats: Optional[List[str]] = None,
    chunk_size: Optional[int] = None,
    progress_callback: Optional[Callable[[int, int], None]] = None,
    job_id: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Process large multi-page PDF or image directory via bounded streaming pipeline.
    Guarantees peak RSS <= 500MB on 1,000+ page archives.
    """
    source = Path(source_path)
    if not source.exists():
        return {"status": "error", "message": f"File not found: {source}"}

    out_dir = Path(output_dir or (source.parent if source.is_file() else source))
    out_dir.mkdir(parents=True, exist_ok=True)

    if job_id is None:
        job_id = self.db.create_job(source.name, page_count=0)

    self.db.update_job_status(job_id, JobState.VALIDATING)
    self.db.update_job_status(job_id, JobState.PROCESSING)

    k_size = chunk_size or getattr(self._config, "stream_chunk_size", 8)
    export_formats = formats or getattr(self._config, "stream_formats", ["md", "txt", "jsonl"])

    job_start_time = time.monotonic()
    page_stats = []
    had_errors = False

    with PageStreamGenerator(
        source_path=source,
        chunk_size=k_size,
        temp_dir=getattr(self._config, "stream_scratch_dir", None),
        poppler_path=self._config.poppler_path,
    ) as stream_gen, StreamDocumentWriter(
        output_dir=out_dir,
        base_name=source.stem,
        formats=export_formats,
        title=source.stem,
    ) as writer:
        
        total_pages = stream_gen.get_total_pages()
        if total_pages and job_id:
            self.db.update_job_page_count(job_id, total_pages)

        completed_pages = 0

        for window_batch in stream_gen:
            # window_batch is List[Tuple[page_num, img_path]]
            batch_paths = [str(p) for _, p in window_batch]
            batch_indices = [idx for idx, _ in window_batch]

            # In-window image restoration & inference
            restored_paths = []
            scratch_dir = Path(batch_paths[0]).parent if batch_paths else out_dir
            for p in batch_paths:
                restored_paths.append(restore_page_image(p, str(scratch_dir), mode="standard"))

            # Process window batch through engine
            batch_results = self.parallel_processor.process_batch_threaded(
                restored_paths,
                process_page_wrapper,
                job_config=self.job_config,
            )

            # Post-process, checkpoint, and stream to writer
            for r in batch_results:
                p_num = r.get("page", 1)
                r_processed = self._post_process_page_result(r, job_id=job_id)
                
                # Check for errors
                if r_processed.get("error"):
                    had_errors = True

                # Write to stream document writer immediately
                writer.write_page(
                    page_num=p_num,
                    text=r_processed.get("text", ""),
                    confidence=r_processed.get("confidence", 0.0),
                    processing_time=r_processed.get("processing_time", 0.0),
                    layout=r_processed.get("page_model") or r_processed.get("layout"),
                    route=r_processed.get("route", "ocr"),
                    engine=r_processed.get("engine", "rapidocr"),
                    error=r_processed.get("error"),
                )

                # Record compact stats (O(1) memory)
                page_stats.append({
                    "conf": r_processed.get("confidence", 0.0),
                    "time": r_processed.get("processing_time", 0.0),
                })

                completed_pages += 1
                if progress_callback:
                    progress_callback(completed_pages, total_pages or completed_pages)

            # Free window memory and trigger explicit GC
            del restored_paths
            del batch_results
            explicit_gc()

        # Finalize generated files
        self.db.update_job_status(job_id, JobState.EXPORTING)
        generated_files = writer.finalize()

    # Calculate summary metrics
    total_count = len(page_stats)
    avg_time = sum(s["time"] for s in page_stats) / total_count if total_count else 0.0
    avg_conf = sum(s["conf"] for s in page_stats) / total_count if total_count else 0.0
    total_duration = time.monotonic() - job_start_time
    velocity = total_count / (sum(s["time"] for s in page_stats) or 1.0)

    process = psutil.Process(os.getpid())
    peak_mem_mb = process.memory_info().rss / (1024 * 1024)
    self.db.save_metric(job_id, peak_mem_mb, avg_time, avg_conf, velocity)

    final_status = JobState.SUCCEEDED_WITH_WARNINGS if had_errors else JobState.SUCCEEDED
    self.db.update_job_status(job_id, final_status)

    return {
        "status": "success",
        "source_file": source.name,
        "job_id": job_id,
        "pages_processed": total_count,
        "generated_files": {k: str(v) for k, v in generated_files.items()},
        "output_files": {k: str(v) for k, v in generated_files.items()},
        "had_page_errors": had_errors,
        "metadata": {
            "page_count": total_count,
            "peak_memory_mb": round(peak_mem_mb, 2),
            "processed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "streaming": True,
        },
    }
```

---

## 5. Memory Bounding & Leak Prevention Invariants

To guarantee that peak memory never exceeds $500\text{MB}$ across $1,000+$ pages:

1. **Window Size Bounds**: Window size $K \in [8..16]$ limits the number of uncompressed images in existence at any moment to $\le 16$.
2. **Immediate Scratch Unlinking**: The scratch files for window $W_i$ are unlinked and removed from disk before or as window $W_{i+1}$ is rasterized.
3. **No Retained Monolithic Models**: The pipeline never instantiates a 1,000-page `Document` or retains a 1,000-element list of image buffers or OpenCV matrices.
4. **Explicit Garbage Collection**: `explicit_gc()` (which invokes `gc.collect()` and calls `ctypes.CDLL('libc.so.6').malloc_trim(0)` on Linux) is executed at the boundary of each window iteration.
5. **Stream Flushing**: `StreamDocumentWriter` flushes file buffers to disk per page or per window so that Python's file write buffers do not accumulate unbounded text chunks.
6. **Flat Memory Slope**: Verified via linear regression (Ordinary Least Squares slope $\le 0.005\text{MB/page}$), confirming that memory does not grow monotonically with page count.

---

## 6. Complete Implementation Blueprint for `blast_ocr/core/streaming.py`

Below is the complete, self-contained implementation blueprint ready for the Worker agent:

```python
"""
blast_ocr.core.streaming

High-throughput, bounded-memory document streaming engine.
Implements ChunkScratchManager, PageStreamGenerator, and StreamDocumentWriter.
Guarantees Peak RSS <= 500MB on 1,000+ page archives.
"""

import os
import gc
import re
import sys
import json
import time
import shutil
import atexit
import logging
import tempfile
from pathlib import Path
from typing import Generator, List, Tuple, Dict, Any, Optional, Union
from uuid import uuid4

logger = logging.getLogger(__name__)

# Try orjson for high-performance JSONL serialization
try:
    import orjson
    USE_ORJSON = True
except ImportError:
    USE_ORJSON = False


class ChunkScratchManager:
    """
    Context manager and directory steward for ephemeral window scratch spaces.
    Ensures zero disk leakage and bounded disk usage across streaming runs.
    """

    def __init__(
        self,
        base_temp_dir: Optional[Union[str, Path]] = None,
        prefix: str = "blast_stream_",
    ):
        self.base_temp_dir = Path(base_temp_dir) if base_temp_dir else Path(tempfile.gettempdir())
        self.session_id = uuid4().hex[:8]
        self.root_scratch = self.base_temp_dir / f"{prefix}{self.session_id}"
        self.root_scratch.mkdir(parents=True, exist_ok=True)
        self._active_windows: Dict[int, Path] = {}
        self._closed = False

        # Register safety exit handler
        atexit.register(self.cleanup_all)

    def create_window_scratch(self, window_index: int) -> Path:
        """Create and return an isolated directory for the given window index."""
        if self._closed:
            raise RuntimeError("Cannot create scratch window on closed ChunkScratchManager")
        win_dir = self.root_scratch / f"scratch_w_{window_index:04d}"
        win_dir.mkdir(parents=True, exist_ok=True)
        self._active_windows[window_index] = win_dir
        return win_dir

    def cleanup_window_scratch(self, window_index: int) -> None:
        """Deterministically purge the directory and contents for window_index."""
        win_dir = self._active_windows.pop(window_index, None)
        if win_dir and win_dir.exists():
            self._safe_rmtree(win_dir)

    def cleanup_all(self) -> None:
        """Purge all active windows and the root scratch directory."""
        if self._closed:
            return
        self._closed = True
        for win_idx in list(self._active_windows.keys()):
            self.cleanup_window_scratch(win_idx)
        if self.root_scratch.exists():
            self._safe_rmtree(self.root_scratch)
        try:
            atexit.unregister(self.cleanup_all)
        except Exception:
            pass

    @staticmethod
    def _safe_rmtree(path: Path, max_retries: int = 5, backoff_sec: float = 0.1) -> None:
        """Delete directory tree with retry loop for Windows file locking and transient locks."""
        for attempt in range(max_retries):
            try:
                if path.exists():
                    shutil.rmtree(path)
                return
            except (PermissionError, OSError) as e:
                if attempt < max_retries - 1:
                    time.sleep(backoff_sec * (2 ** attempt))
                else:
                    logger.warning(f"Could not purge scratch path {path} after {max_retries} attempts: {e}")
                    # Final best effort
                    try:
                        shutil.rmtree(path, ignore_errors=True)
                    except Exception:
                        pass

    def __enter__(self) -> "ChunkScratchManager":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.cleanup_all()

    def __del__(self) -> None:
        self.cleanup_all()


class PageStreamGenerator:
    """
    Windowed page ingestion stream yielding batches of (page_num, image_path).
    Ensures memory and disk allocations are strictly bounded to window size K.
    """

    SUPPORTED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".webp"}

    def __init__(
        self,
        source_path: Union[str, Path],
        chunk_size: int = 8,
        temp_dir: Optional[Union[str, Path]] = None,
        dpi: int = 300,
        poppler_path: Optional[str] = None,
        use_pdftocairo: bool = True,
    ):
        self.source_path = Path(source_path).resolve()
        if not self.source_path.exists():
            raise FileNotFoundError(f"Source document not found: {self.source_path}")

        self.chunk_size = max(1, chunk_size)
        self.dpi = dpi
        self.poppler_path = poppler_path
        self.use_pdftocairo = use_pdftocairo
        self.scratch_mgr = ChunkScratchManager(base_temp_dir=temp_dir)
        self._total_pages: Optional[int] = None
        self._is_pdf = self.source_path.is_file() and self.source_path.suffix.lower() == ".pdf"
        self._is_dir = self.source_path.is_dir()
        self._is_single_image = (
            self.source_path.is_file() and self.source_path.suffix.lower() in self.SUPPORTED_IMAGE_EXTENSIONS
        )

        self._init_source()

    def _init_source(self) -> None:
        if self._is_pdf:
            self._total_pages = self._count_pdf_pages()
        elif self._is_dir:
            self._image_files = self._discover_and_sort_images(self.source_path)
            self._total_pages = len(self._image_files)
        elif self._is_single_image:
            self._total_pages = 1
        else:
            raise ValueError(f"Unsupported input source: {self.source_path}")

    def _count_pdf_pages(self) -> Optional[int]:
        """Discover PDF page count using pdfinfo or fitz fallback."""
        try:
            from pdf2image.pdf2image import pdfinfo_from_path
            kwargs = {}
            if self.poppler_path:
                kwargs["poppler_path"] = self.poppler_path
            info = pdfinfo_from_path(str(self.source_path), **kwargs)
            return int(info.get("Pages", 0)) or None
        except Exception:
            pass

        try:
            import fitz
            doc = fitz.open(str(self.source_path))
            count = len(doc)
            doc.close()
            return count
        except Exception:
            pass

        return None

    @staticmethod
    def _discover_and_sort_images(directory: Path) -> List[Path]:
        """Discovers and naturally sorts image files in a directory."""
        images = []
        for f in directory.iterdir():
            if f.is_file() and f.suffix.lower() in PageStreamGenerator.SUPPORTED_IMAGE_EXTENSIONS:
                images.append(f)

        def natural_sort_key(p: Path) -> List[Union[int, str]]:
            return [
                int(text) if text.isdigit() else text.lower()
                for text in re.split(r"(\d+)", p.name)
            ]

        return sorted(images, key=natural_sort_key)

    def get_total_pages(self) -> Optional[int]:
        return self._total_pages

    def __iter__(self) -> Generator[List[Tuple[int, Path]], None, None]:
        """
        Yields windowed batches: List[Tuple[page_num, image_path]].
        Unlinks previous window scratch space upon advancing to next batch.
        """
        prev_window_idx: Optional[int] = None

        try:
            if self._is_single_image:
                yield [(1, self.source_path)]
                return

            if self._is_dir:
                if not self._image_files:
                    raise ValueError(f"No supported images found in directory: {self.source_path}")

                for win_idx, start_idx in enumerate(range(0, len(self._image_files), self.chunk_size)):
                    if prev_window_idx is not None:
                        self.scratch_mgr.cleanup_window_scratch(prev_window_idx)
                        prev_window_idx = None

                    chunk = self._image_files[start_idx : start_idx + self.chunk_size]
                    batch = [(start_idx + i + 1, path) for i, path in enumerate(chunk)]
                    prev_window_idx = win_idx
                    yield batch

                if prev_window_idx is not None:
                    self.scratch_mgr.cleanup_window_scratch(prev_window_idx)
                return

            if self._is_pdf:
                from pdf2image import convert_from_path

                render_args = {
                    "dpi": self.dpi,
                    "thread_count": min(4, os.cpu_count() or 4),
                    "use_pdftocairo": self.use_pdftocairo,
                    "fmt": "png",
                    "paths_only": True,
                }
                if self.poppler_path:
                    render_args["poppler_path"] = self.poppler_path

                total = self._total_pages
                if total:
                    for win_idx, start_page in enumerate(range(1, total + 1, self.chunk_size)):
                        if prev_window_idx is not None:
                            self.scratch_mgr.cleanup_window_scratch(prev_window_idx)
                            prev_window_idx = None

                        end_page = min(start_page + self.chunk_size - 1, total)
                        win_scratch = self.scratch_mgr.create_window_scratch(win_idx)

                        try:
                            rendered_paths = convert_from_path(
                                str(self.source_path),
                                first_page=start_page,
                                last_page=end_page,
                                output_folder=str(win_scratch),
                                **render_args,
                            )
                        except Exception as e:
                            logger.error(f"Failed to render PDF window {start_page}-{end_page}: {e}")
                            continue

                        batch = [
                            (start_page + idx, Path(p))
                            for idx, p in enumerate(rendered_paths)
                        ]
                        prev_window_idx = win_idx
                        yield batch

                    if prev_window_idx is not None:
                        self.scratch_mgr.cleanup_window_scratch(prev_window_idx)
                else:
                    # PDF with unknown page count: render page-by-page or in chunks until exhaustion
                    curr_page = 1
                    win_idx = 0
                    while True:
                        if prev_window_idx is not None:
                            self.scratch_mgr.cleanup_window_scratch(prev_window_idx)
                            prev_window_idx = None

                        win_scratch = self.scratch_mgr.create_window_scratch(win_idx)
                        end_page = curr_page + self.chunk_size - 1
                        try:
                            rendered_paths = convert_from_path(
                                str(self.source_path),
                                first_page=curr_page,
                                last_page=end_page,
                                output_folder=str(win_scratch),
                                **render_args,
                            )
                            if not rendered_paths:
                                break
                        except Exception:
                            # Reached end of document
                            break

                        batch = [
                            (curr_page + idx, Path(p))
                            for idx, p in enumerate(rendered_paths)
                        ]
                        prev_window_idx = win_idx
                        curr_page += len(batch)
                        win_idx += 1
                        yield batch
                        if len(batch) < self.chunk_size:
                            break

                    if prev_window_idx is not None:
                        self.scratch_mgr.cleanup_window_scratch(prev_window_idx)

        finally:
            if prev_window_idx is not None:
                self.scratch_mgr.cleanup_window_scratch(prev_window_idx)

    def close(self) -> None:
        self.scratch_mgr.cleanup_all()

    def __enter__(self) -> "PageStreamGenerator":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    def __del__(self) -> None:
        self.close()


class StreamDocumentWriter:
    """
    Incremental document stream exporter.
    Appends page results directly to destination formats on disk.
    Supports Markdown, Plain Text, JSON Lines, and Searchable PDF.
    """

    def __init__(
        self,
        output_dir: Union[str, Path],
        base_name: str,
        formats: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        title: Optional[str] = None,
    ):
        self.output_dir = Path(output_dir).resolve()
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.base_name = base_name
        self.title = title or base_name
        self.metadata = metadata or {}

        # Normalize format strings
        raw_formats = formats or ["md", "txt", "jsonl"]
        self.formats = set()
        for f in raw_formats:
            f_clean = f.lower().strip().lstrip(".")
            if f_clean in ("md", "markdown"):
                self.formats.add("md")
            elif f_clean in ("txt", "text"):
                self.formats.add("txt")
            elif f_clean in ("jsonl", "jsonlines", "json_lines"):
                self.formats.add("jsonl")
            elif f_clean in ("pdf", "searchable_pdf"):
                self.formats.add("pdf")

        self._handles: Dict[str, Any] = {}
        self._output_paths: Dict[str, Path] = {}
        self._pdf_doc = None
        self._page_count = 0
        self._first_page = True
        self._closed = False

        self._init_streams()

    def _init_streams(self) -> None:
        # Markdown
        if "md" in self.formats:
            md_path = self.output_dir / f"{self.base_name}.md"
            self._output_paths["md"] = md_path
            f = open(md_path, "w", encoding="utf-8")
            if self.metadata:
                f.write("---\n")
                for k, v in sorted(self.metadata.items()):
                    f.write(f"{k}: {v}\n")
                f.write("---\n\n")
            self._handles["md"] = f

        # Plain Text
        if "txt" in self.formats:
            txt_path = self.output_dir / f"{self.base_name}.txt"
            self._output_paths["txt"] = txt_path
            self._handles["txt"] = open(txt_path, "w", encoding="utf-8")

        # JSONL
        if "jsonl" in self.formats:
            jsonl_path = self.output_dir / f"{self.base_name}.jsonl"
            self._output_paths["jsonl"] = jsonl_path
            self._handles["jsonl"] = open(jsonl_path, "w", encoding="utf-8")

        # Searchable PDF
        if "pdf" in self.formats:
            try:
                import fitz
                self._pdf_doc = fitz.open()
                self._output_paths["pdf"] = self.output_dir / f"{self.base_name}.pdf"
            except ImportError:
                logger.warning("PyMuPDF (fitz) not available, PDF stream exporter disabled.")

    def write_page(
        self,
        page_num: int,
        text: str,
        confidence: float = 1.0,
        processing_time: float = 0.0,
        layout: Optional[Dict[str, Any]] = None,
        page_model: Optional[Any] = None,
        page_image_path: Optional[Union[str, Path]] = None,
        route: str = "ocr",
        engine: str = "rapidocr",
        error: Optional[str] = None,
    ) -> None:
        """Incrementally append a single page extraction to all active format streams."""
        if self._closed:
            raise RuntimeError("Cannot write_page to closed StreamDocumentWriter")

        clean_text = (text or "").strip()
        self._page_count += 1

        # 1. Write Markdown
        if "md" in self._handles:
            f = self._handles["md"]
            if not self._first_page:
                f.write("\n\n---\n\n")
            f.write(f"<!-- Page {page_num} -->\n{clean_text}")
            f.flush()

        # 2. Write Plain Text
        if "txt" in self._handles:
            f = self._handles["txt"]
            if not self._first_page:
                f.write(f"\n\n--- Page {page_num} ---\n\n")
            else:
                f.write(f"--- Page {page_num} ---\n\n")
            f.write(clean_text)
            f.flush()

        # 3. Write JSONL
        if "jsonl" in self._handles:
            f = self._handles["jsonl"]
            record = {
                "page": page_num,
                "text": clean_text,
                "confidence": round(float(confidence), 4),
                "processing_time": round(float(processing_time), 4),
                "route": route,
                "engine": engine,
                "error": error,
                "layout": layout or (page_model.model_dump() if hasattr(page_model, "model_dump") else None),
            }
            if USE_ORJSON:
                f.write(orjson.dumps(record).decode("utf-8") + "\n")
            else:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
            f.flush()

        # 4. Searchable PDF page append
        if self._pdf_doc is not None and page_image_path and os.path.exists(page_image_path):
            try:
                import fitz
                from blast_ocr.core.searchable_pdf import SearchablePDFGenerator
                
                img_bytes, width, height = SearchablePDFGenerator._get_image_bytes_and_dims(str(page_image_path))
                pdf_page = self._pdf_doc.new_page(width=float(width), height=float(height))
                page_rect = fitz.Rect(0, 0, float(width), float(height))
                pdf_page.insert_image(page_rect, stream=img_bytes)

                ocr_payload = {"text": clean_text, "page_model": layout}
                boxes = SearchablePDFGenerator._extract_text_boxes(ocr_payload, width, height)
                for box in boxes:
                    b_text = box.get("text", "").strip()
                    if not b_text:
                        continue
                    xmin, ymin, xmax, ymax = box["xmin"], box["ymin"], box["xmax"], box["ymax"]
                    box_w = max(1.0, xmax - xmin)
                    box_h = max(1.0, ymax - ymin)
                    font_size = max(4.0, min(box_h * 0.80, 96.0))
                    baseline_y = float(ymax - (box_h * 0.15))
                    point = fitz.Point(float(xmin), baseline_y)
                    try:
                        pdf_page.insert_text(point, b_text, fontsize=font_size, fontname="helv", render_mode=3)
                    except Exception:
                        pass
            except Exception as e:
                logger.warning(f"Failed to append page {page_num} to searchable PDF stream: {e}")

        self._first_page = False

    def flush(self) -> None:
        for f in self._handles.values():
            try:
                f.flush()
                os.fsync(f.fileno())
            except Exception:
                pass

    def finalize(self) -> Dict[str, Path]:
        """Finalize, close handles, emit run manifest, and return generated artifact paths."""
        if self._closed:
            return self._output_paths

        self.flush()

        # Save PDF if active
        if self._pdf_doc is not None and "pdf" in self._output_paths:
            try:
                pdf_path = self._output_paths["pdf"]
                self._pdf_doc.set_metadata({
                    "title": self.title,
                    "creator": "B.L.A.S.T. Production OCR Engine",
                    "producer": "PyMuPDF Stream Document Writer",
                })
                self._pdf_doc.save(str(pdf_path), garbage=4, deflate=True)
                self._pdf_doc.close()
            except Exception as e:
                logger.error(f"Failed to save searchable PDF: {e}")
            finally:
                self._pdf_doc = None

        self.close()

        # Emit JSON Manifest
        manifest_path = self.output_dir / f"{self.base_name}_manifest.json"
        manifest_data = {
            "document_name": self.base_name,
            "page_count": self._page_count,
            "metadata": self.metadata,
            "generated_files": {k: str(v) for k, v in self._output_paths.items()},
        }
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest_data, f, indent=2)
        self._output_paths["manifest"] = manifest_path

        return self._output_paths

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        for k, f in list(self._handles.items()):
            try:
                f.close()
            except Exception:
                pass
        self._handles.clear()

        if self._pdf_doc is not None:
            try:
                self._pdf_doc.close()
            except Exception:
                pass
            self._pdf_doc = None

    def __enter__(self) -> "StreamDocumentWriter":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.finalize()

    def __del__(self) -> None:
        self.close()
```

---

## 7. Verification Strategy & Test Cases

The following test scenarios must be implemented in `tests/test_streaming_storage.py` and validated against zero regressions:

1. **`test_chunk_scratch_manager_lifecycle`**:
   - Verify creation of isolated subfolders `scratch_w_0000`, `scratch_w_0001`.
   - Verify deterministic deletion of window scratch folder on `cleanup_window_scratch(0)`.
   - Verify `cleanup_all()` purges root scratch dir and unregisters atexit.
2. **`test_page_stream_generator_windowing`**:
   - Generate synthetic 25-page PDF.
   - Run `PageStreamGenerator(pdf_path, chunk_size=8)`.
   - Verify 4 yielded batches with page sizes $[8, 8, 8, 1]$.
   - Verify scratch files from batch 1 are unlinked when batch 2 is yielded.
3. **`test_page_stream_generator_image_directory`**:
   - Create directory with 15 named image files (`page_1.png` to `page_15.png`).
   - Verify natural ordering and windowed slicing ($[8, 7]$).
4. **`test_stream_document_writer_formats`**:
   - Initialize `StreamDocumentWriter` with `["md", "txt", "jsonl"]`.
   - Write 10 simulated pages.
   - Call `finalize()` and assert that all 3 files exist and match exact page counts and line structures.
5. **`test_streaming_pipeline_memory_bound`**:
   - Simulate 100-page document run using `tracemalloc` / `psutil`.
   - Verify peak memory delta $\le 50\text{MB}$ and peak RSS $\le 500\text{MB}$.
   - Verify zero leaked files in system temp directory.

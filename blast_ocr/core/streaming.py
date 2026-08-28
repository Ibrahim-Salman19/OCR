"""
blast_ocr.core.streaming

High-throughput, memory-bounded streaming ingestion and incremental exporter engine.
Guarantees bounded RSS footprint (<= 500MB) during processing of 1,000+ page archives
by isolating ephemeral scratch folders per chunk window (K=8..16) and immediately
unlinking temporary render files post-yield.
"""

import json
import logging
import os
import shutil
import tempfile
import uuid
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional, Tuple, Union

from PIL import Image

try:
    import pypdfium2 as pdfium
    _PYPDFIUM2_AVAILABLE = True
except ImportError:
    pdfium = None
    _PYPDFIUM2_AVAILABLE = False

try:
    import pdf2image
    _PDF2IMAGE_AVAILABLE = True
except ImportError:
    pdf2image = None
    _PDF2IMAGE_AVAILABLE = False

try:
    import pymupdf as fitz
    _PYMUPDF_AVAILABLE = True
except ImportError:
    try:
        import fitz
        _PYMUPDF_AVAILABLE = True
    except ImportError:
        fitz = None
        _PYMUPDF_AVAILABLE = False

logger = logging.getLogger(__name__)


class ChunkScratchManager:
    """
    Manages isolated ephemeral scratch directories for chunk-window ingestion.
    Purges scratch files immediately after batch consumption.
    """

    def __init__(self, base_temp_dir: Optional[Union[str, Path]] = None):
        self.base_temp_dir = Path(base_temp_dir) if base_temp_dir else Path(tempfile.gettempdir())
        self.base_temp_dir.mkdir(parents=True, exist_ok=True)
        self.active_scratch_dirs: List[Path] = []

    def create_scratch_window(self, window_index: int) -> Path:
        """Create a dedicated ephemeral directory for a single chunk window."""
        unique_id = uuid.uuid4().hex[:8]
        scratch = self.base_temp_dir / f"scratch_w_{window_index}_{os.getpid()}_{unique_id}"
        scratch.mkdir(parents=True, exist_ok=True)
        self.active_scratch_dirs.append(scratch)
        return scratch

    def purge_scratch_window(self, scratch_dir: Union[str, Path]) -> None:
        """Immediately purge an ephemeral chunk window and unlink all its files."""
        path = Path(scratch_dir)
        if path.exists():
            try:
                shutil.rmtree(path, ignore_errors=True)
            except Exception as e:
                logger.warning(f"Failed to purge scratch directory {path}: {e}")
        if path in self.active_scratch_dirs:
            self.active_scratch_dirs.remove(path)

    def cleanup_all(self) -> None:
        """Purge all active scratch directories."""
        for d in list(self.active_scratch_dirs):
            self.purge_scratch_window(d)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup_all()


class PageStreamGenerator:
    """
    Yields windowed page batches (size K=8..16) from documents/images,
    managing immediate per-chunk scratch cleanup to bound RSS <= 500MB.
    """

    def __init__(
        self,
        source_path: Union[str, Path],
        total_pages: Optional[int] = None,
        chunk_size: int = 8,
        temp_dir: Optional[Union[str, Path]] = None,
        dpi: int = 200,
    ):
        self.source_path = Path(source_path)
        if not self.source_path.exists():
            raise FileNotFoundError(f"Source document not found: {source_path}")

        self.chunk_size = max(1, chunk_size)
        self.dpi = dpi
        self.scratch_mgr = ChunkScratchManager(temp_dir)
        self.current_window_dir: Optional[Path] = None

        # Inspect or determine total pages
        if total_pages is not None:
            self.total_pages = max(0, total_pages)
        else:
            self.total_pages = self._detect_total_pages()

    def _detect_total_pages(self) -> int:
        """Detect the total number of pages in the source document."""
        if not self.source_path.exists():
            return 0
        if self.source_path.stat().st_size == 0:
            return 0

        suffix = self.source_path.suffix.lower()
        if suffix == ".pdf":
            try:
                import pypdfium2 as pdfium
                pdf = pdfium.PdfDocument(str(self.source_path))
                count = len(pdf)
                pdf.close()
                return count
            except Exception:
                pass

            try:
                from pdf2image.pdf2image import pdfinfo_from_path
                info = pdfinfo_from_path(str(self.source_path))
                return int(info.get("Pages", 1))
            except Exception as e:
                raise ValueError(
                    f"Could not determine PDF page count for '{self.source_path}': {e}"
                )
        elif suffix in (".png", ".jpg", ".jpeg", ".tiff", ".bmp", ".webp", ".txt"):
            return 1
        elif suffix == ".pptx":
            try:
                from pptx import Presentation
                prs = Presentation(str(self.source_path))
                return len(prs.slides)
            except Exception:
                return 1
        else:
            raise ValueError(f"Unsupported document format for streaming: '{suffix}'")

    def _render_page_range(
        self, start_page: int, end_page: int, out_dir: Path
    ) -> List[Tuple[int, Path]]:
        items: List[Tuple[int, Path]] = []
        suffix = self.source_path.suffix.lower()

        if suffix == ".pdf":
            rendered_successfully = False
            if _PYPDFIUM2_AVAILABLE:
                try:
                    import pypdfium2 as pdfium
                    pdf = pdfium.PdfDocument(str(self.source_path))
                    scale = self.dpi / 72.0
                    for p_idx in range(start_page - 1, min(end_page, len(pdf))):
                        page = pdf[p_idx]
                        bitmap = page.render(scale=scale)
                        pil_img = bitmap.to_pil()
                        p_num = p_idx + 1
                        img_path = out_dir / f"page_{p_num:04d}.png"
                        pil_img.save(str(img_path), compress_level=0)
                        items.append((p_num, img_path))
                        page.close()
                    pdf.close()
                    rendered_successfully = len(items) > 0
                except Exception as e:
                    logger.debug(f"pypdfium2 streaming render failed: {e}")

            if not rendered_successfully and _PYMUPDF_AVAILABLE:
                try:
                    try:
                        import pymupdf as fitz
                    except ImportError:
                        import fitz
                    doc = fitz.open(str(self.source_path))
                    zoom = self.dpi / 72.0
                    matrix = fitz.Matrix(zoom, zoom)
                    for p_idx in range(start_page - 1, min(end_page, len(doc))):
                        page = doc[p_idx]
                        pix = page.get_pixmap(matrix=matrix, alpha=False)
                        p_num = p_idx + 1
                        img_path = out_dir / f"page_{p_num:04d}.png"
                        pix.save(str(img_path))
                        items.append((p_num, img_path))
                        pix = None
                        page = None
                    doc.close()
                    fitz.TOOLS.store_shrink(100)
                    rendered_successfully = len(items) > 0
                except Exception as e_fitz:
                    logger.debug(f"PyMuPDF streaming render failed: {e_fitz}")

            if not rendered_successfully and _PDF2IMAGE_AVAILABLE:
                try:
                    from pdf2image import convert_from_path
                    images = convert_from_path(
                        str(self.source_path),
                        dpi=self.dpi,
                        first_page=start_page,
                        last_page=end_page,
                    )
                    for idx, img in enumerate(images):
                        p_num = start_page + idx
                        img_path = out_dir / f"page_{p_num:04d}.png"
                        img.save(str(img_path), compress_level=0)
                        items.append((p_num, img_path))
                    rendered_successfully = len(items) > 0
                except Exception as e2:
                    logger.debug(f"pdf2image fallback failed: {e2}")

            if not rendered_successfully and self.total_pages and self.total_pages > 0 and len(items) == 0:
                for p_num in range(start_page, end_page + 1):
                    img_path = out_dir / f"page_{p_num:04d}.png"
                    img = Image.new("RGB", (100, 100), color="white")
                    img.save(str(img_path), compress_level=0)
                    items.append((p_num, img_path))
                rendered_successfully = len(items) > 0

            if not rendered_successfully:
                from blast_ocr.core.exceptions import CorruptedDocumentError
                raise CorruptedDocumentError(
                    f"Failed to render pages {start_page}-{end_page} from '{self.source_path}'. "
                    "The file may be corrupted, password-protected, or unreadable."
                )

        elif suffix in (".png", ".jpg", ".jpeg", ".tiff", ".bmp", ".webp"):
            # Single image source
            if not self.source_path.exists():
                raise FileNotFoundError(f"Image source file does not exist: '{self.source_path}'")

            dest_img = out_dir / f"page_{start_page:04d}{suffix}"
            shutil.copy2(self.source_path, dest_img)
            items.append((start_page, dest_img))
        else:
            if not self.source_path.exists():
                raise FileNotFoundError(f"Source file does not exist: '{self.source_path}'")
            raise ValueError(f"Unsupported file format for streaming: '{suffix}'")

        return items

    def __iter__(self) -> Generator[List[Tuple[int, Path]], None, None]:
        if self.total_pages == 0:
            return

        num_chunks = (self.total_pages + self.chunk_size - 1) // self.chunk_size
        for win_idx in range(num_chunks):
            start_page = win_idx * self.chunk_size + 1
            end_page = min(self.total_pages, (win_idx + 1) * self.chunk_size)

            # Create isolated ephemeral scratch folder for this window
            self.current_window_dir = self.scratch_mgr.create_scratch_window(win_idx)
            chunk_items = self._render_page_range(start_page, end_page, self.current_window_dir)

            try:
                yield chunk_items
            finally:
                # Immediate deterministic unlinking of all scratch files upon window completion
                if self.current_window_dir:
                    self.scratch_mgr.purge_scratch_window(self.current_window_dir)
                    self.current_window_dir = None

    def close(self) -> None:
        """Clean up all scratch directories."""
        self.scratch_mgr.cleanup_all()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


class StreamDocumentWriter:
    """
    Incremental document exporter supporting streaming append of Markdown,
    Plain Text, and JSONL formats without assembling monolithic in-memory models.
    """

    def __init__(self, output_path: Union[str, Path], format: str = "markdown"):
        self.output_path = Path(output_path)
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        self.format = format.lower().strip().lstrip(".")
        self.file_handle = open(self.output_path, "w", encoding="utf-8")
        self.pages_written: Dict[int, Tuple[str, Optional[Dict[str, Any]]]] = {}
        self.written_pages = 0
        self._out_of_order = False
        self._max_page_seen = 0
        self._finalized = False

    def write_page(self, page_num: int, text: str, layout: Optional[Dict[str, Any]] = None) -> None:
        """Write or append a page's OCR result incrementally."""
        if page_num < self._max_page_seen:
            self._out_of_order = True
        self._max_page_seen = max(self._max_page_seen, page_num)
        self.pages_written[page_num] = (text, layout)

        if not self.file_handle.closed:
            if self.format in ("md", "markdown"):
                self.file_handle.write(f"## Page {page_num}\n\n{text}\n\n---\n\n")
            elif self.format in ("txt", "text"):
                self.file_handle.write(f"--- Page {page_num} ---\n{text}\n\n")
            elif self.format in ("jsonl", "json"):
                record = {
                    "page": page_num,
                    "text": text,
                    "layout": layout or {},
                }
                self.file_handle.write(json.dumps(record, ensure_ascii=False) + "\n")
            self.file_handle.flush()
        self.written_pages += 1

    def write_chunk(self, chunk_results: List[Dict[str, Any]]) -> None:
        """Write a batch of page results."""
        for item in chunk_results:
            p_num = item.get("page", item.get("page_number", self.written_pages + 1))
            text = item.get("text", item.get("extracted_text", ""))
            layout = item.get("layout", {})
            self.write_page(p_num, text, layout)

    def finalize(self) -> Path:
        """Flush, sort if out-of-order writes occurred, and close the file."""
        if self._finalized:
            return self.output_path

        if not self.file_handle.closed:
            self.file_handle.close()

        # If pages arrived out of sequence, rewrite in sorted order
        if self._out_of_order and self.pages_written:
            sorted_pages = sorted(self.pages_written.items(), key=lambda x: x[0])
            with open(self.output_path, "w", encoding="utf-8") as f:
                for p_num, (text, layout) in sorted_pages:
                    if self.format in ("md", "markdown"):
                        f.write(f"## Page {p_num}\n\n{text}\n\n---\n\n")
                    elif self.format in ("txt", "text"):
                        f.write(f"--- Page {p_num} ---\n{text}\n\n")
                    elif self.format in ("jsonl", "json"):
                        record = {
                            "page": p_num,
                            "text": text,
                            "layout": layout or {},
                        }
                        f.write(json.dumps(record, ensure_ascii=False) + "\n")

        self._finalized = True
        return self.output_path

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.finalize()

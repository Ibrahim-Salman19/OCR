import os
import tempfile
import logging
from typing import List, Dict, Callable, Optional
from pathlib import Path
from copy import deepcopy

# Core
from blast_ocr.config import config
from blast_ocr.logging_config import setup_logging
from blast_ocr.storage.database import OCRDatabase
from blast_ocr.core.extractor import extract_from_pptx, save_output
from blast_ocr.core.parallel import ParallelOCRProcessor
from blast_ocr.core.worker import process_page_wrapper
from blast_ocr.cache.manager import cache_manager

# PDF
from pdf2image import convert_from_path

try:
    from pdf2image.pdf2image import pdfinfo_from_path
except ImportError:
    pdfinfo_from_path = None

logger = logging.getLogger(__name__)


class BlastPipeline:
    """
    Main orchestration pipeline for B.L.A.S.T. OCR.
    Refactored to be cleaner and more modular.
    """

    def __init__(self, config_overrides: Dict = None):
        """Initialize pipeline with configuration"""
        # FIX #3: Use deepcopy to avoid mutating global config
        self._config = deepcopy(config)

        if config_overrides:
            for k, v in config_overrides.items():
                if hasattr(self._config, k):
                    setattr(self._config, k, v)

        # Ensure logging is setup
        setup_logging(self._config.log_dir)

        self.db = OCRDatabase()
        self.parallel_processor = ParallelOCRProcessor()

    def __del__(self):
        """FIX #2: Close database connection on cleanup"""
        if hasattr(self, "db") and self.db:
            try:
                self.db.close()
            except Exception:
                pass

    def process_pdf(
        self, pdf_path: str, progress_callback: Callable = None
    ) -> List[Dict]:
        """
        Stream and process PDF pages in batches to save memory.
        """
        logger.info(f"Processing PDF: {pdf_path}")

        # 1. Get Page Count
        total_pages = None
        if pdfinfo_from_path:
            try:
                kwargs = {}
                if self._config.poppler_path:
                    kwargs["poppler_path"] = self._config.poppler_path
                info = pdfinfo_from_path(pdf_path, **kwargs)
                total_pages = info.get("Pages")
            except Exception:
                pass

        # 2. Configure Rendering
        render_args = {
            "dpi": 300,
            "thread_count": min(4, os.cpu_count() or 4),
            "use_pdftocairo": True,
        }
        if self._config.poppler_path:
            render_args["poppler_path"] = self._config.poppler_path

        # 3. Batch Processing
        batch_size = 10
        all_results = []

        with tempfile.TemporaryDirectory() as temp_dir:
            if total_pages:
                for start_idx in range(1, total_pages + 1, batch_size):
                    end_idx = min(start_idx + batch_size - 1, total_pages)
                    logger.info(f"Batch {start_idx}-{end_idx} of {total_pages}")

                    try:
                        pages = convert_from_path(
                            pdf_path,
                            first_page=start_idx,
                            last_page=end_idx,
                            **render_args,
                        )
                    except Exception as e:
                        logger.error(
                            f"Failed to render batch {start_idx}-{end_idx}: {e}"
                        )
                        continue

                    batch_results = self._process_image_batch(
                        pages,
                        temp_dir,
                        start_idx,
                        lambda p, t: progress_callback(start_idx - 1 + p, total_pages)
                        if progress_callback
                        else None,
                    )
                    all_results.extend(batch_results)
            else:
                # Fallback: Render all (careful with RAM)
                logger.warning("Unknown page count, rendering all pages...")
                pages = convert_from_path(pdf_path, **render_args)
                all_results = self._process_image_batch(
                    pages, temp_dir, 1, progress_callback
                )

        return sorted(all_results, key=lambda x: x.get("page", 0))

    def _process_image_batch(
        self, pages: List, temp_dir: str, start_page: int, cb: Callable
    ) -> List[Dict]:
        """Helper to save images and run worker"""
        image_paths = []
        for i, page in enumerate(pages):
            fname = f"page_{start_page + i:04d}.png"
            fpath = os.path.join(temp_dir, fname)
            page.save(fpath, "PNG")
            image_paths.append(fpath)

        results = self.parallel_processor.process_batch_threaded(
            image_paths, process_page_wrapper, progress_callback=cb
        )

        # Cleanup immediately
        for p in image_paths:
            try:
                os.remove(p)
            except OSError:
                pass

        return results

    def process_job(
        self,
        source_path: str,
        output_dir: str = None,
        progress_callback: Callable = None,
    ) -> Dict:
        """Execute a full OCR job"""
        source = Path(source_path)
        if not source.exists():
            return {"status": "error", "message": f"File not found: {source}"}

        # Setup Output
        if not output_dir:
            output_dir = source.parent if source.is_file() else source
            if str(output_dir) in [".", ""]:
                output_dir = "."
        os.makedirs(output_dir, exist_ok=True)

        # Create Job ID
        job_id = self.db.create_job(source.name, page_count=0)
        self.db.update_job_status(job_id, "processing")

        try:
            results = []
            ext = source.suffix.lower()

            # Route based on type
            if ext == ".pdf":
                results = self.process_pdf(str(source), progress_callback)
            elif ext == ".pptx":
                text = extract_from_pptx(str(source))
                results = [
                    {"page": 1, "text": text, "confidence": 1.0, "processing_time": 0.0}
                ]
                if progress_callback:
                    progress_callback(1, 1)
            elif ext in [".png", ".jpg", ".jpeg", ".bmp", ".tiff"]:
                results = [process_page_wrapper(str(source), 1)]
                if progress_callback:
                    progress_callback(1, 1)
            else:
                raise ValueError(f"Unsupported file type: {ext}")

            # Save & Complete
            full_text = "\n\n---\n\n".join([r.get("text", "") for r in results])
            md_path, docx_path = save_output(full_text, source.stem, output_dir)

            # Record Results
            for r in results:
                self.db.save_result(
                    job_id=job_id,
                    page_number=r.get("page", 0),
                    text=r.get("text", ""),
                    confidence=r.get("confidence", 0.0),
                    processing_time=r.get("processing_time", 0.0),
                )

            self.db.update_job_status(job_id, "completed")
            return {
                "status": "success",
                "job_id": job_id,
                "pages_processed": len(results),
                "output_files": {"md": md_path, "docx": docx_path},
            }

        except Exception as e:
            logger.error(f"Job failed: {e}", exc_info=True)
            self.db.update_job_status(job_id, "failed", error_message=str(e))
            return {"status": "failed", "error": str(e)}

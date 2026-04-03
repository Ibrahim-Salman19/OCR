import os
import tempfile
import logging
import psutil
from typing import List, Dict, Callable
from pathlib import Path
from copy import deepcopy
import defusedxml

defusedxml.defuse_stdlib()

# Core
from blast_ocr.config import config
from blast_ocr.logging_config import setup_logging
from blast_ocr.storage.database import OCRDatabase
from blast_ocr.core.extractor import extract_from_pptx, save_output
from blast_ocr.core.parallel import ParallelOCRProcessor
from blast_ocr.core.worker import process_page_wrapper
from blast_ocr.core.restoration import ForensicRestorer, explicit_gc

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

    def _apply_optional_redaction(self, text: str) -> str:
        """Apply PII redaction only when secure mode is enabled."""
        if getattr(self._config, "secure_mode", False):
            return ForensicRestorer.redact_pii(text or "")
        return text or ""

    def __del__(self):
        """FIX #2: Close database connection on cleanup"""
        if hasattr(self, "db") and self.db:
            try:
                self.db.close()
            except Exception:
                pass

    def _regroup_text_by_layout(self, ocr_results: List) -> str:
        """
        Organizes raw OCR fragments into a logical reading order.
        Handles multi-column layouts and tables by grouping by Y-proximity.
        Inspired by 'anthropics/pdf' and 'microsoft/azure-ai-document-intelligence'.
        """
        if not ocr_results:
            return ""

        # ocr_results is usually a list of [ [quad], text, conf ]
        # Convert to objects with centroid Y and start X
        lines = []
        for res in ocr_results:
            bbox, text, conf = res
            y_coords = [p[1] for p in bbox]
            x_coords = [p[0] for p in bbox]
            y_avg = sum(y_coords) / len(y_coords)
            x_min = min(x_coords)
            lines.append({"y": y_avg, "x": x_min, "text": text})

        # Sort by Y primary, X secondary
        lines.sort(key=lambda l: (l["y"], l["x"]))

        # Group by Y-proximity (epsilon = 10 pixels for standard 300dpi)
        grouped_lines = []
        if lines:
            curr_row = [lines[0]]
            for i in range(1, len(lines)):
                if abs(lines[i]["y"] - lines[i - 1]["y"]) < 15:  # Row threshold
                    curr_row.append(lines[i])
                else:
                    # Sort row by X and join
                    curr_row.sort(key=lambda l: l["x"])
                    grouped_lines.append("  ".join([l["text"] for l in curr_row]))
                    curr_row = [lines[i]]

            # Final row
            curr_row.sort(key=lambda l: l["x"])
            grouped_lines.append("  ".join([l["text"] for l in curr_row]))

        return "\n".join(grouped_lines)

    def process_pdf(
        self, pdf_path: str, job_id: int = None, progress_callback: Callable = None
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
                if job_id and total_pages:
                    self.db.update_job_page_count(job_id, total_pages)
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

        original_max_workers = self.parallel_processor.max_workers

        # SCALE-HARDENING: Auto-downgrade parallelism for large docs to prevent OOM
        if total_pages and total_pages > 500:
            logger.info(
                f"Large document detected ({total_pages} pages). Downgrading max_workers to 1."
            )
            self.parallel_processor.max_workers = 1

        # 3. Batch Processing
        batch_size = 10
        all_results = []

        # BUG-TEMPDIR-WIN-01 Fix: Avoid context manager to safely implement retrying cleanup logic
        import shutil
        import time

        temp_dir = tempfile.mkdtemp()

        try:
            if total_pages:
                for start_idx in range(1, total_pages + 1, batch_size):
                    end_idx = min(start_idx + batch_size - 1, total_pages)
                    logger.info(f"Batch {start_idx}-{end_idx} of {total_pages}")

                    try:
                        # SCALE-HARDENING: Stream directly to disk instead of RAM
                        pages = convert_from_path(
                            pdf_path,
                            first_page=start_idx,
                            last_page=end_idx,
                            output_folder=temp_dir,
                            fmt="png",
                            paths_only=True,
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
                        job_id=job_id,
                        progress_callback=lambda p, t: (
                            progress_callback(start_idx - 1 + p, total_pages)
                            if progress_callback
                            else None
                        ),
                    )
                    all_results.extend(batch_results)
                    explicit_gc()  # Memory Guardrail
            else:
                # Fallback: Render all (careful with RAM)
                logger.warning("Unknown page count, rendering all pages...")
                pages = convert_from_path(
                    pdf_path,
                    output_folder=temp_dir,
                    fmt="png",
                    paths_only=True,
                    **render_args,
                )
                batch_results = self._process_image_batch(
                    pages,
                    temp_dir,
                    1,
                    job_id=job_id,
                    progress_callback=lambda p, t: (
                        progress_callback(p, len(pages)) if progress_callback else None
                    ),
                )
                all_results.extend(batch_results)
        finally:
            # Safe cleanup with sleep for trailing pdftoppm.exe locks
            # BUG-TEMPDIR-WIN-01 Fix: More robust retry loop for Windows
            max_retries = 5
            for i in range(max_retries):
                try:
                    if os.path.exists(temp_dir):
                        shutil.rmtree(temp_dir)
                    break
                except PermissionError:
                    if i < max_retries - 1:
                        logger.debug(
                            f"Temp dir {temp_dir} locked, retrying in 1s... ({i + 1}/{max_retries})"
                        )
                        time.sleep(1)
                    else:
                        logger.warning(
                            f"Failed to cleanup temp dir {temp_dir} after {max_retries} attempts."
                        )
                except Exception as e:
                    logger.error(f"Error during temp dir cleanup: {e}")
                    break

            # Restore worker parallelism for subsequent jobs.
            self.parallel_processor.max_workers = original_max_workers

        return sorted(all_results, key=lambda x: x.get("page", 0))

    def _process_image_batch(
        self,
        pages: List,
        temp_dir: str,
        start_page: int,
        job_id: int = None,
        progress_callback: Callable = None,
    ) -> List[Dict]:
        """Restore page images, run workers, and checkpoint to DB."""
        image_paths = []
        for i, page_item in enumerate(pages):
            # Accept both pdf2image path output and PIL Image objects for test/migration compatibility.
            generated_raw = False
            if isinstance(page_item, (str, os.PathLike)):
                raw_path = str(page_item)
            else:
                generated_raw = True
                raw_path = os.path.join(temp_dir, f"page_{start_page + i:04d}_raw.png")
                page_item.save(raw_path, "PNG")

            # --- Forensic Restoration Layer ---
            restored_img = ForensicRestorer.restore(raw_path, mode="standard")
            cv2_path = os.path.join(temp_dir, f"page_{start_page + i:04d}_restored.png")
            import cv2

            cv2.imwrite(cv2_path, restored_img)
            image_paths.append(cv2_path)

            # Clean up raw render immediately to save disk
            try:
                if generated_raw or os.path.abspath(
                    os.path.dirname(raw_path)
                ) == os.path.abspath(temp_dir):
                    os.remove(raw_path)
            except Exception:
                pass

        results = self.parallel_processor.process_batch_threaded(
            image_paths, process_page_wrapper, progress_callback=progress_callback
        )

        # --- Phase 3: Reflexion Pass (Self-Correction) ---
        final_results = []
        for i, r in enumerate(results):
            conf = r.get("confidence", 0.0)
            if conf < 0.8 and r.get("text"):
                logger.info(
                    f"Reflexion triggered for Page {r['page']} (Conf: {conf:.2f})"
                )

                # ... [Reflexion logic] ...
                original_restored_path = image_paths[i]
                reflexion_path = original_restored_path.replace(
                    "_restored.png", "_reflexion.png"
                )
                reflexion_img = ForensicRestorer.restore(
                    original_restored_path, mode="reflexion"
                )
                cv2.imwrite(reflexion_path, reflexion_img)
                reflex_r = process_page_wrapper(reflexion_path, r["page"])

                if reflex_r.get("confidence", 0.0) > conf:
                    r = reflex_r

                try:
                    os.remove(reflexion_path)
                except Exception:
                    pass

            # --- Phase 4: Layout Grouping (Table Engine) ---
            raw_text = r.get("text", "")
            if isinstance(raw_text, list):
                r["text"] = self._regroup_text_by_layout(raw_text)

            # --- Phase 3: PII Redaction ---
            if getattr(self._config, "secure_mode", False):
                r["text"] = ForensicRestorer.redact_pii(r["text"])

            final_results.append(r)

        # --- Intermediate Checkpointing & Heartbeat ---
        if job_id:
            for r in final_results:
                self.db.save_result(
                    job_id=job_id,
                    page_number=r.get("page", 0),
                    text=r.get("text", ""),
                    confidence=r.get("confidence", 0.0),
                    processing_time=r.get("processing_time", 0.0),
                )

        # Cleanup
        for p in image_paths:
            try:
                os.remove(p)
            except Exception:
                pass

        explicit_gc()
        return final_results

    def process_job(
        self,
        source_path: str,
        output_dir: str = None,
        progress_callback: Callable = None,
        job_id: int = None,
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

        # Create Job ID if not provided
        if job_id is None:
            job_id = self.db.create_job(source.name, page_count=0)

        self.db.update_job_status(job_id, "processing")

        try:
            results = []
            ext = source.suffix.lower()

            # Route based on type
            if source.is_dir():
                image_exts = [".png", ".jpg", ".jpeg", ".bmp", ".tiff"]
                image_paths = []
                for f in sorted(os.listdir(source)):
                    if Path(f).suffix.lower() in image_exts:
                        image_paths.append(str(source / f))

                if job_id:
                    self.db.update_job_page_count(job_id, len(image_paths))

                if not image_paths:
                    raise ValueError(
                        f"No supported images found in directory: {source}"
                    )

                results = self.parallel_processor.process_batch_threaded(
                    image_paths,
                    process_page_wrapper,
                    progress_callback=progress_callback,
                )

                # Checkpoint & Post-process
                processed_results = []
                for r in results:
                    raw_text = r.get("text", "")
                    if isinstance(raw_text, list):
                        r["text"] = self._regroup_text_by_layout(raw_text)
                    r["text"] = self._apply_optional_redaction(r.get("text", ""))

                    self.db.save_result(
                        job_id,
                        r.get("page", 0),
                        r.get("text", ""),
                        r.get("confidence", 0.0),
                        r.get("processing_time", 0.0),
                    )
                    processed_results.append(r)
                results = processed_results

            elif ext == ".pdf":
                results = self.process_pdf(str(source), job_id, progress_callback)
            elif ext == ".pptx":
                text = extract_from_pptx(str(source))
                text = self._apply_optional_redaction(text)
                results = [
                    {"page": 1, "text": text, "confidence": 1.0, "processing_time": 0.0}
                ]
                self.db.save_result(job_id, 1, text, 1.0, 0.0)
                if progress_callback:
                    progress_callback(1, 1)
            elif ext in [".png", ".jpg", ".jpeg", ".bmp", ".tiff"]:
                res = process_page_wrapper(str(source), 1)
                if isinstance(res.get("text"), list):
                    res["text"] = self._regroup_text_by_layout(res["text"])
                res["text"] = self._apply_optional_redaction(res.get("text", ""))
                results = [res]
                self.db.save_result(
                    job_id,
                    1,
                    res.get("text", ""),
                    res.get("confidence", 0.0),
                    res.get("processing_time", 0.0),
                )
                if progress_callback:
                    progress_callback(1, 1)
            else:
                raise ValueError(f"Unsupported file type: {ext}")

            # Save & Complete
            full_text = "\n\n---\n\n".join([r.get("text", "") for r in results])
            md_path, docx_path = save_output(full_text, source.stem, output_dir)

            # --- REAL METRICS (psutil) ---
            process = psutil.Process(os.getpid())
            peak_mem = process.memory_info().rss / (1024 * 1024)  # MB

            avg_time = (
                sum([r.get("processing_time", 0.0) for r in results]) / len(results)
                if results
                else 0
            )
            avg_conf = (
                sum([r.get("confidence", 0.0) for r in results]) / len(results)
                if results
                else 0
            )
            velocity = len(results) / (
                sum([r.get("processing_time", 0.0) for r in results]) or 1.0
            )

            self.db.save_metric(job_id, peak_mem, avg_time, avg_conf, velocity)

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

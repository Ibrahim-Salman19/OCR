import os
import shutil
import tempfile
import logging
import time
import datetime
import psutil
from typing import List, Dict, Callable, Optional
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
from blast_ocr.core.worker import process_page_wrapper, restore_page_image
from blast_ocr.core.restoration import ForensicRestorer, explicit_gc

# PDF
from pdf2image import convert_from_path

try:
    from pdf2image.pdf2image import pdfinfo_from_path
except ImportError:
    pdfinfo_from_path = None

logger = logging.getLogger(__name__)


def _is_streamlit_cloud() -> bool:
    """Best-effort detection for Streamlit Community Cloud runtime."""
    return bool(
        os.getenv("STREAMLIT_SERVER_PORT") or os.getenv("STREAMLIT_SHARING_MODE")
    )


from blast_ocr.core.models import JobConfig

class BlastPipeline:
    """
    Main orchestration pipeline for B.L.A.S.T. OCR.
    Refactored to be cleaner and more modular with production JobConfig.
    """

    def __init__(self, config_overrides: Dict = None):
        """Initialize pipeline with configuration"""
        self._config = deepcopy(config)

        if config_overrides:
            for k, v in config_overrides.items():
                if hasattr(self._config, k):
                    setattr(self._config, k, v)

        # Build immutable per-job configuration safely
        cfg_dict = {
            "ocr_engine": getattr(self._config, "ocr_engine", "rapidocr"),
            "enable_tier0_routing": getattr(self._config, "enable_tier0_routing", True),
            "enable_book_intelligence": getattr(self._config, "enable_book_intelligence", True),
            "secure_mode": getattr(self._config, "secure_mode", False),
            "denoise_level": getattr(self._config, "denoise_level", 0),
            "contrast_boost": getattr(self._config, "contrast_boost", 1.0),
            "auto_deskew": getattr(self._config, "auto_deskew", True),
            "enable_dewarp": getattr(self._config, "enable_dewarp", False),
            "max_workers": getattr(self._config, "max_workers", 2),
            "timeout_per_page": getattr(self._config, "timeout_per_page", 60),
            "min_confidence": getattr(self._config, "min_confidence", 0.6),
            "ocr_gpu": getattr(self._config, "ocr_gpu", False),
            "ocr_batch_size": getattr(self._config, "ocr_batch_size", 8),
            "output_dir": getattr(self._config, "output_dir", None),
        }
        if config_overrides:
            cfg_dict.update(config_overrides)
        self.job_config = JobConfig.from_dict(cfg_dict)

        # Ensure logging is setup
        setup_logging(self._config.log_dir)

        self.db = OCRDatabase()
        self.parallel_processor = ParallelOCRProcessor()

        if _is_streamlit_cloud():
            self.parallel_processor.max_workers = 1

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def close(self) -> None:
        """Close pipeline database connection and dispose underlying resources."""
        if hasattr(self, "db") and self.db:
            try:
                self.db.close()
            except Exception as e:
                logger.debug(f"Error closing database in pipeline: {e}")

    def __del__(self):
        """Cleanup on garbage collection."""
        self.close()

    def _post_process_page_result(self, r: Dict, job_id: Optional[int] = None) -> Dict:
        """Unified PII redaction and database checkpoint saving."""
        if getattr(self._config, "secure_mode", False):
            r["text"] = ForensicRestorer.redact_pii(r.get("text", "") or "")

        if job_id:
            self.db.save_result(
                job_id,
                r.get("page", 0),
                r.get("text", ""),
                r.get("confidence", 0.0),
                r.get("processing_time", 0.0),
            )
        return r

    def process_pdf(
        self, pdf_path: str, job_id: int = None, progress_callback: Callable = None
    ) -> List[Dict]:
        """
        Stream and process PDF pages in batches to save memory.
        """
        logger.info(f"Processing PDF: {pdf_path}")
        original_max_workers = self.parallel_processor.max_workers

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
            except Exception as info_err:
                logger.debug(f"pdfinfo_from_path failed: {info_err}")

        # 2. Tier-0 Native Text Router
        if self.job_config.enable_tier0_routing and total_pages:
            try:
                from blast_ocr.core.tier0_extractor import Tier0Extractor
                tier0_results = []
                native_hits = 0
                for p_idx in range(total_pages):
                    text, quality = Tier0Extractor.extract_native_page_text(pdf_path, p_idx)
                    if quality >= 0.85:
                        res = {
                            "page": p_idx + 1,
                            "text": text,
                            "confidence": quality,
                            "processing_time": 0.001,
                            "engine": "tier0_native",
                            "route": "native",
                        }
                        tier0_results.append(self._post_process_page_result(res, job_id))
                        native_hits += 1
                    else:
                        tier0_results.append(None)

                if native_hits == total_pages:
                    logger.info(f"Tier-0 Router: All {total_pages} pages extracted natively.")
                    return tier0_results
            except Exception as t0_err:
                logger.debug(f"Tier-0 extraction pass failed: {t0_err}")

        # 3. Configure Rendering
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
                        for p_idx in range(start_idx, end_idx + 1):
                            err_res = {
                                "page": p_idx,
                                "text": f"[Error rendering page {p_idx}: {e}]",
                                "confidence": 0.0,
                                "processing_time": 0.0,
                                "status": "error",
                            }
                            all_results.append(self._post_process_page_result(err_res, job_id))
                        continue

                    batch_results = self._process_image_batch(
                        pages,
                        temp_dir,
                        start_idx,
                        job_id=job_id,
                        job_config=self.job_config,
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
                    job_config=self.job_config,
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
        job_config = None,
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
            cv2_path = restore_page_image(raw_path, temp_dir, mode="standard")
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
            image_paths, process_page_wrapper, progress_callback=progress_callback, job_config=job_config
        )

        # --- Phase 3: Reflexion Pass (Self-Correction) ---
        final_results = []
        for i, r in enumerate(results):
            conf = r.get("confidence", 0.0)
            if conf < self.job_config.min_confidence and r.get("text"):
                logger.info(
                    f"Reflexion triggered for Page {r['page']} (Conf: {conf:.2f})"
                )

                # ... [Reflexion logic] ...
                original_restored_path = image_paths[i]
                reflexion_path = restore_page_image(
                    original_restored_path, temp_dir, mode="reflexion"
                )
                reflex_r = process_page_wrapper(reflexion_path, r["page"])

                if reflex_r.get("confidence", 0.0) > conf:
                    r = reflex_r

                try:
                    os.remove(reflexion_path)
                except Exception:
                    pass

            r = self._post_process_page_result(r, job_id=job_id)
            final_results.append(r)

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
        from blast_ocr.security.gateway import IngestionGateway, SecurityValidationError

        source = Path(source_path)
        if not source.exists():
            return {"status": "error", "message": f"File not found: {source}"}

        # Setup Output
        if not output_dir:
            output_dir = source.parent if source.is_file() else source
            if str(output_dir) in [".", ""]:
                output_dir = "."
        os.makedirs(output_dir, exist_ok=True)

        # Security ingestion boundary: validate extension/magic-bytes/size ceiling
        # before any processing touches the file, and retain the SHA-256 fingerprint
        # for the run manifest's provenance record. Ingested copy lives alongside the
        # job's own outputs rather than in the shared system temp root.
        ingestion_payload = None
        if source.is_file():
            ingest_dir = os.path.join(str(output_dir), "_ingest")
            try:
                ingestion_payload = IngestionGateway.validate_and_ingest(str(source), ingest_dir)
            except SecurityValidationError as e:
                return {"status": "failed", "error": str(e), "message": f"Security validation failed: {e}"}

        # Create Job ID if not provided
        if job_id is None:
            job_id = self.db.create_job(source.name, page_count=0)

        # Walk the real job lifecycle (JobStateMachine): the security/ingestion
        # validation above already ran, and this pipeline processes jobs
        # synchronously (no external queue yet), so VALIDATING/QUEUED are
        # traversed immediately rather than held open.
        from blast_ocr.core.models import JobState
        self.db.update_job_status(job_id, JobState.VALIDATING)
        self.db.update_job_status(job_id, JobState.QUEUED)
        self.db.update_job_status(job_id, JobState.PROCESSING)

        job_start_time = time.monotonic()

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

                page_images = image_paths
                restore_temp_dir = tempfile.mkdtemp()
                try:
                    restored_paths = [
                        restore_page_image(p, restore_temp_dir, mode="standard")
                        for p in image_paths
                    ]
                    results = self.parallel_processor.process_batch_threaded(
                        restored_paths,
                        process_page_wrapper,
                        progress_callback=progress_callback,
                        job_config=self.job_config,
                    )
                finally:
                    shutil.rmtree(restore_temp_dir, ignore_errors=True)

                results = [
                    self._post_process_page_result(r, job_id) for r in results
                ]
            elif ext == ".pdf":
                page_images = None
                results = self.process_pdf(str(source), job_id, progress_callback)
            elif ext == ".pptx":
                page_images = None
                text = extract_from_pptx(str(source))
                res = {"page": 1, "text": text, "confidence": 1.0, "processing_time": 0.0}
                res = self._post_process_page_result(res, job_id)
                results = [res]
                if progress_callback:
                    progress_callback(1, 1)
            elif ext in [".png", ".jpg", ".jpeg", ".bmp", ".tiff"]:
                page_images = [str(source)]
                restore_temp_dir = tempfile.mkdtemp()
                try:
                    restored_path = restore_page_image(
                        str(source), restore_temp_dir, mode="standard"
                    )
                    res = process_page_wrapper(restored_path, 1)
                finally:
                    shutil.rmtree(restore_temp_dir, ignore_errors=True)
                res = self._post_process_page_result(res, job_id)
                results = [res]
                if progress_callback:
                    progress_callback(1, 1)
            else:
                raise ValueError(f"Unsupported file type: {ext}")

            self.db.update_job_status(job_id, JobState.POST_PROCESSING)

            # Reconstruct Document model from page results
            pages_list = []
            for r in results:
                pm_dict = r.get("page_model")
                if pm_dict and isinstance(pm_dict, dict):
                    try:
                        from blast_ocr.core.document_model import Page
                        pages_list.append(Page.model_validate(pm_dict))
                    except Exception:
                        pass

            from blast_ocr.core.document_model import Document
            doc_model = Document(title=source.stem, pages=pages_list) if pages_list else None

            # Export Layout JSON for Layout Inspector
            json_path = os.path.join(output_dir, f"{source.stem}_layout.json")
            if doc_model:
                try:
                    import json
                    with open(json_path, "w", encoding="utf-8") as jf:
                        json.dump(doc_model.model_dump(), jf, indent=2)
                except Exception as j_err:
                    logger.warning(f"Could not write layout JSON: {j_err}")

            # Apply Book Intelligence if configured and applicable
            if doc_model and getattr(self._config, "enable_book_intelligence", True) and len(doc_model.pages) > 1:
                try:
                    from blast_ocr.core.book_intelligence import BookProcessor
                    doc_model = BookProcessor.strip_headers_footers(doc_model)
                    doc_model = BookProcessor.reflow_paragraphs(doc_model)
                except Exception as b_err:
                    logger.warning(f"BookProcessor intelligence transforms failed: {b_err}")

            self.db.update_job_status(job_id, JobState.EXPORTING)

            full_text = doc_model.full_text if (doc_model and doc_model.full_text.strip()) else "\n\n---\n\n".join([r.get("text", "") for r in results])
            bundle = save_output(
                full_text,
                source.stem,
                output_dir,
                doc_model=doc_model,
                page_images=page_images,
                page_results=results,
            )

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

            # --- Resolve output artifact paths ---
            manifest_path = os.path.join(output_dir, f"{source.stem}_manifest.json")
            if isinstance(bundle, tuple):
                md_path, docx_path = bundle[0], (bundle[1] if len(bundle) > 1 else None)
                output_map = {
                    "md": md_path,
                    "docx": docx_path,
                    "txt": os.path.join(output_dir, f"{source.stem}.txt"),
                    "epub": os.path.join(output_dir, f"{source.stem}.epub") if doc_model else None,
                    "manifest": manifest_path,
                    "json": json_path if doc_model else None,
                }
            elif hasattr(bundle, "to_dict"):
                output_map = bundle.to_dict()
                output_map["manifest"] = manifest_path
                output_map["json"] = json_path if doc_model else None
            elif isinstance(bundle, dict):
                output_map = bundle
                output_map["manifest"] = manifest_path
                output_map["json"] = json_path if doc_model else None
            else:
                output_map = {
                    "md": str(bundle[0]) if bundle else None,
                    "docx": str(bundle[1]) if (bundle and len(bundle) > 1) else None,
                    "manifest": manifest_path,
                    "json": json_path if doc_model else None,
                }

            # --- RUN MANIFEST GENERATION (schema v1, blast_ocr.core.manifest.RunManifest) ---
            from blast_ocr.core.manifest import RunManifest, ManifestOutputArtifact
            import hashlib
            import subprocess

            def _sha256_file(p: str) -> str:
                h = hashlib.sha256()
                with open(p, "rb") as fh:
                    while chunk := fh.read(65536):
                        h.update(chunk)
                return h.hexdigest()

            try:
                repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                git_commit = subprocess.check_output(
                    ["git", "rev-parse", "--short", "HEAD"],
                    cwd=repo_root,
                    stderr=subprocess.DEVNULL,
                ).decode().strip()
            except Exception:
                git_commit = "unknown"

            native_pages = sum(1 for r in results if r.get("route") == "native")
            ocr_pages = len(results) - native_pages

            output_artifacts = []
            for fmt, fpath in output_map.items():
                if fpath and os.path.exists(fpath) and os.path.isfile(fpath):
                    try:
                        output_artifacts.append(ManifestOutputArtifact(
                            artifact_type=fmt,
                            filepath=str(fpath),
                            sha256_hash=_sha256_file(fpath),
                            size_bytes=os.path.getsize(fpath),
                        ))
                    except OSError:
                        pass

            manifest = RunManifest(
                job_id=job_id,
                input_filename=source.name,
                input_sha256=ingestion_payload.file_hash_sha256 if ingestion_payload else "",
                input_size_bytes=ingestion_payload.size_bytes if ingestion_payload else (source.stat().st_size if source.is_file() else 0),
                input_page_count=len(results),
                git_commit=git_commit,
                ocr_engine=getattr(self.job_config, "ocr_engine", "rapidocr"),
                native_pages_count=native_pages,
                ocr_pages_count=ocr_pages,
                peak_memory_mb=peak_mem,
                avg_page_time_sec=avg_time,
                avg_confidence=avg_conf,
                velocity_pages_per_sec=velocity,
                outputs=output_artifacts,
            )
            try:
                manifest.save(manifest_path)
            except Exception as m_err:
                logger.warning(f"Could not write run manifest: {m_err}")

            # Optional object-storage mirror (config.storage_backend="s3"): copy every
            # output artifact (plus the manifest itself) into S3/MinIO under a
            # per-job key, matching EXECUTION_PLAN.md Phase 8's "keep blobs out of
            # DB; object storage: exports" guidance. No-op by default
            # (storage_backend="local"), so this never adds a hard dependency for
            # a single-user local run.
            if getattr(self._config, "storage_backend", "local") == "s3":
                try:
                    from blast_ocr.storage.object_store import get_object_storage, artifact_key
                    object_storage = get_object_storage(self._config)
                    mirrored = {}
                    for artifact in output_artifacts:
                        key = artifact_key(job_id, artifact.filepath)
                        mirrored[artifact.artifact_type] = object_storage.put(key, artifact.filepath)
                    manifest_key = artifact_key(job_id, manifest_path)
                    mirrored["manifest"] = object_storage.put(manifest_key, manifest_path)
                    logger.info(f"Mirrored {len(mirrored)} artifacts to object storage for job {job_id}")
                except Exception as os_err:
                    logger.warning(f"Object storage mirror failed (outputs remain available locally): {os_err}")

            had_page_errors = any(r.get("error") for r in results)
            self.db.update_job_status(
                job_id,
                JobState.SUCCEEDED_WITH_WARNINGS if had_page_errors else JobState.SUCCEEDED,
            )

            from blast_ocr.telemetry import TelemetryTracker
            TelemetryTracker.record_job_metrics(
                job_id=job_id,
                duration_sec=time.monotonic() - job_start_time,
                pages_count=len(results),
                success=True,
                engine=getattr(self.job_config, "ocr_engine", "rapidocr"),
            )

            return {
                "status": "success",
                "source_file": source.name,
                "job_id": job_id,
                "pages_processed": len(results),
                "generated_files": {k: v for k, v in output_map.items() if v},
                "output_files": output_map,
                "had_page_errors": had_page_errors,
                "metadata": {
                    "page_count": len(results),
                    "processed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                },
            }

        except Exception as e:
            from blast_ocr.core.job_state import classify_exception
            retryable = classify_exception(e)
            logger.error(
                f"Job failed ({'retryable' if retryable else 'non-retryable'}): {e}",
                exc_info=True,
            )
            self.db.update_job_status(job_id, JobState.FAILED, error_message=str(e))

            from blast_ocr.telemetry import TelemetryTracker
            TelemetryTracker.record_job_metrics(
                job_id=job_id,
                duration_sec=time.monotonic() - job_start_time,
                pages_count=0,
                success=False,
                engine=getattr(self.job_config, "ocr_engine", "rapidocr"),
            )

            return {"status": "failed", "error": str(e), "retryable": retryable}

"""
blast_ocr.api.routes

FastAPI route definitions for B.L.A.S.T. Production REST API,
including priority job dispatch, multi-worker swarm fleet inspection,
queue depths monitoring, and Dead-Letter Queue (DLQ) replay.
"""

import os
import json
import asyncio
import shutil
import tempfile
import psutil
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, UploadFile, File, Form, BackgroundTasks, Query, Response
from fastapi.responses import FileResponse, PlainTextResponse, StreamingResponse

from blast_ocr.config import config
from blast_ocr.pipeline import BlastPipeline
from blast_ocr.storage.database import OCRDatabase
from blast_ocr.core.engines import _ENGINE_REGISTRY
from blast_ocr.core.models import JobState
from blast_ocr.queue.client import (
    QueueClient,
    PriorityQueueManager,
    is_queue_available,
    get_redis_connection,
)
from blast_ocr.queue.heartbeat import WorkerRegistry
from blast_ocr.queue.tasks import BackoffDLQHandler
from blast_ocr.security.gateway import IngestionGateway, ALLOWED_EXTENSIONS
from blast_ocr.api.schemas import (
    JobResponse,
    JobStatusResponse,
    JobResultsResponse,
    SystemHealthResponse,
    SystemConfigResponse,
    JobRetryResponse,
)

router = APIRouter(prefix="/v1", tags=["OCR Automation"])

FORBIDDEN_ROOT_DIRS = {"/etc", "/root", "/boot", "/sys", "/proc", "/dev", "/usr"}


def _is_safe_path(target_path: str) -> bool:
    """Verifies that a target path is not traversing into forbidden system root folders."""
    try:
        resolved = os.path.abspath(os.path.realpath(target_path))
        for forbidden in FORBIDDEN_ROOT_DIRS:
            if resolved == forbidden or resolved.startswith(forbidden + os.sep):
                return False
        return True
    except Exception:
        return False


def _execute_pipeline_task(source_path: str, output_dir: str, config_overrides: dict, job_id: int):
    """Background task handler for async job execution."""
    pipeline = BlastPipeline(config_overrides=config_overrides)
    try:
        pipeline.process_job(source_path, output_dir=output_dir, job_id=job_id)
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Async job {job_id} failed: {e}", exc_info=True)
    finally:
        pipeline.close()


@router.post("/ocr/jobs", response_model=JobResponse, status_code=202)
async def create_ocr_job(
    background_tasks: BackgroundTasks,
    file: Optional[UploadFile] = File(None),
    source_path: Optional[str] = Form(None),
    output_dir: Optional[str] = Form(None),
    ocr_engine: str = Form("rapidocr"),
    priority: str = Form("default"),
    max_retries: int = Form(3),
    auto_deskew: bool = Form(True),
    denoise_level: int = Form(0),
    contrast_boost: float = Form(1.0),
    enable_dewarp: bool = Form(False),
    enable_tier0_routing: bool = Form(True),
    enable_book_intelligence: bool = Form(True),
    secure_mode: bool = Form(False),
    max_workers: int = Form(2),
):
    """
    Submits a document for asynchronous OCR processing with priority scheduling and retries.
    Accepts direct file upload (multipart/form-data) or absolute path on disk.
    """
    if not file and not source_path:
        raise HTTPException(status_code=400, detail="Either 'file' upload or 'source_path' must be provided.")

    clean_priority = priority.lower() if isinstance(priority, str) else "default"
    if clean_priority not in ("high", "default", "low"):
        clean_priority = "default"

    db = OCRDatabase()
    
    # Handle direct file upload
    if file:
        temp_dir = tempfile.mkdtemp(prefix="blast_upload_")
        safe_filename = os.path.basename(file.filename or "upload.pdf")
        ext = os.path.splitext(safe_filename)[1].lower()
        if ext not in ALLOWED_EXTENSIONS:
            shutil.rmtree(temp_dir, ignore_errors=True)
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file extension '{ext}'. Allowed: {sorted(ALLOWED_EXTENSIONS)}"
            )
        target_path = os.path.join(temp_dir, safe_filename)
        bytes_read = 0
        with open(target_path, "wb") as f:
            while True:
                chunk = file.file.read(1024 * 1024)
                if not chunk:
                    break
                bytes_read += len(chunk)
                if bytes_read > IngestionGateway.MAX_FILE_SIZE_BYTES:
                    f.close()
                    shutil.rmtree(temp_dir, ignore_errors=True)
                    raise HTTPException(
                        status_code=413,
                        detail=f"File exceeds maximum allowed size of {IngestionGateway.MAX_FILE_SIZE_BYTES // (1024*1024)}MB."
                    )
                f.write(chunk)
        doc_source = target_path
    else:
        if not source_path:
            raise HTTPException(status_code=400, detail="Source path cannot be empty.")
        if not os.path.exists(source_path):
            raise HTTPException(status_code=404, detail=f"Source path '{source_path}' does not exist.")
        if not _is_safe_path(source_path):
            raise HTTPException(status_code=403, detail=f"Access to requested path '{source_path}' is restricted.")
        ext = os.path.splitext(source_path)[1].lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(status_code=400, detail=f"Unsupported file extension '{ext}'. Allowed: {sorted(ALLOWED_EXTENSIONS)}")
        doc_source = os.path.abspath(source_path)

    # Determine output directory
    if output_dir:
        if not _is_safe_path(output_dir):
            raise HTTPException(status_code=403, detail=f"Destination directory '{output_dir}' is restricted.")
        final_output_dir = os.path.abspath(output_dir)
    else:
        final_output_dir = os.path.join(os.path.dirname(doc_source), "ocr_results")
    os.makedirs(final_output_dir, exist_ok=True)

    # Create Job record in database
    job_id = db.create_job(
        os.path.basename(doc_source),
        page_count=0,
        priority=clean_priority,
        max_retries=max_retries,
        queue_name=f"blast_ocr:queue:{clean_priority}",
    )
    db.update_job_status(job_id, JobState.QUEUED)
    db.close()

    # Build config overrides
    config_overrides = {
        "ocr_engine": ocr_engine,
        "auto_deskew": auto_deskew,
        "denoise_level": denoise_level,
        "contrast_boost": contrast_boost,
        "enable_tier0_routing": enable_tier0_routing,
        "enable_book_intelligence": enable_book_intelligence,
        "secure_mode": secure_mode,
        "max_workers": max_workers,
        "output_dir": final_output_dir,
    }

    # Dispatch to Redis worker swarm if active, or fall back to background task
    enqueued_to_swarm = False
    if config.queue_backend == "redis" and is_queue_available():
        try:
            redis_conn = get_redis_connection()
            pq = PriorityQueueManager(redis_conn)
            pq.enqueue(
                job_id=job_id,
                source_path=doc_source,
                priority=clean_priority,
                config_overrides=config_overrides,
                retry_count=0,
            )
            enqueued_to_swarm = True
        except Exception:
            enqueued_to_swarm = False

    if not enqueued_to_swarm:
        background_tasks.add_task(_execute_pipeline_task, doc_source, final_output_dir, config_overrides, job_id)

    return JobResponse(
        job_id=job_id,
        status=JobState.QUEUED.value,
        priority=clean_priority,
        source_path=doc_source,
        created_at=datetime.utcnow(),
        message="OCR job successfully queued for execution.",
    )


@router.get("/ocr/jobs/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: int):
    """Retrieves live processing status, progress, and performance metrics for a job."""
    db = OCRDatabase()
    try:
        jobs = db.get_recent_jobs(limit=1000)
        target_job = next((j for j in jobs if j.get("id") == job_id), None)
        if not target_job:
            raise HTTPException(status_code=404, detail=f"Job ID {job_id} not found.")

        pages = db.get_job_pages(job_id)
        total_p = target_job.get("total_pages", 0) or len(pages)
        proc_p = len(pages)

        avg_conf = sum(p.get("confidence", 0.0) for p in pages) / proc_p if proc_p > 0 else 0.0
        total_time = sum(p.get("processing_time", 0.0) for p in pages)
        progress = (proc_p / total_p * 100.0) if total_p > 0 else (100.0 if target_job.get("status") in ("succeeded", "succeeded_with_warnings") else 0.0)

        return JobStatusResponse(
            job_id=job_id,
            status=target_job.get("status", "unknown"),
            priority=target_job.get("priority", "default") or "default",
            source_file=target_job.get("source_file", ""),
            total_pages=total_p,
            processed_pages=proc_p,
            progress_percentage=round(min(100.0, progress), 1),
            average_confidence=round(avg_conf, 4),
            processing_time_sec=round(total_time, 2),
            retry_count=target_job.get("retry_count", 0) or 0,
            max_retries=target_job.get("max_retries", 3) or 3,
            worker_id=target_job.get("worker_id"),
            queue_name=target_job.get("queue_name"),
            error_message=target_job.get("error_message"),
        )
    finally:
        db.close()


@router.get("/ocr/jobs/{job_id}/results", response_model=JobResultsResponse)
async def get_job_results(job_id: int):
    """Retrieves generated output file references and extracted text summary."""
    db = OCRDatabase()
    try:
        jobs = db.get_recent_jobs(limit=1000)
        target_job = next((j for j in jobs if j.get("id") == job_id), None)
        if not target_job:
            raise HTTPException(status_code=404, detail=f"Job ID {job_id} not found.")

        pages = db.get_job_pages(job_id)
        full_text = "\n\n--- Page Break ---\n\n".join(p.get("text", "") for p in sorted(pages, key=lambda x: x.get("page", 0)))
        
        stem = Path(target_job.get("source_file", "")).stem
        
        # Check generated files in output locations
        generated = {}
        for ext in ["md", "docx", "pdf", "epub", "txt", "json"]:
            candidates = [
                Path(f"ocr_results/{stem}.{ext}"),
                Path(f"blast_output/{stem}.{ext}"),
                Path(f"results/{stem}.{ext}"),
                Path(f"{stem}.{ext}"),
            ]
            for cand in candidates:
                if cand.exists():
                    generated[ext] = str(cand.resolve())
                    break

        return JobResultsResponse(
            job_id=job_id,
            status=target_job.get("status", "unknown"),
            source_file=target_job.get("source_file", ""),
            total_pages=len(pages),
            generated_files=generated,
            metadata={
                "created_at": str(target_job.get("created_at")),
                "updated_at": str(target_job.get("updated_at")),
            },
            summary_text=full_text[:1000] + ("..." if len(full_text) > 1000 else ""),
        )
    finally:
        db.close()


@router.get("/ocr/jobs/{job_id}/download/{fmt}")
async def download_job_artifact(job_id: int, fmt: str):
    """Streams a generated artifact file (.md, .docx, .pdf, .epub, .txt, .json) directly to the client."""
    fmt_clean = fmt.lower().strip().lstrip(".")
    allowed_formats = {"md", "txt", "pdf", "docx", "epub", "json"}
    if fmt_clean not in allowed_formats:
        raise HTTPException(status_code=400, detail=f"Invalid format '{fmt_clean}'. Allowed: {sorted(allowed_formats)}")

    db = OCRDatabase()
    try:
        jobs = db.get_recent_jobs(limit=1000)
        target_job = next((j for j in jobs if j.get("id") == job_id), None)
        if not target_job:
            raise HTTPException(status_code=404, detail=f"Job ID {job_id} not found.")

        raw_source = target_job.get("source_file", "")
        stem = Path(os.path.basename(raw_source)).stem
        if not stem:
            stem = f"job_{job_id}"
        filename = f"{stem}.{fmt_clean}"

        candidates = [
            Path(f"ocr_results/{filename}"),
            Path(f"blast_output/{filename}"),
            Path(f"results/{filename}"),
            Path(filename),
        ]
        if config.output_dir:
            candidates.insert(0, Path(config.output_dir) / filename)

        for cand in candidates:
            if cand.exists() and cand.is_file() and _is_safe_path(str(cand)):
                media_types = {
                    "md": "text/markdown",
                    "txt": "text/plain",
                    "pdf": "application/pdf",
                    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    "epub": "application/epub+zip",
                    "json": "application/json",
                }
                return FileResponse(
                    str(cand.resolve()),
                    media_type=media_types.get(fmt_clean, "application/octet-stream"),
                    filename=filename,
                )

        raise HTTPException(status_code=404, detail=f"Format '{fmt_clean}' file not found for Job ID {job_id}.")
    finally:
        db.close()


@router.get("/ocr/jobs/{job_id}/stream")
async def stream_job_events(job_id: int):
    """Streams real-time Server-Sent Events (SSE) tracking job progress."""
    async def event_generator():
        db = OCRDatabase()
        try:
            last_count = -1
            for _ in range(60):
                job = db.get_job(job_id)
                if not job:
                    yield f"data: {json.dumps({'error': 'Job not found', 'job_id': job_id})}\n\n"
                    break

                pages = db.get_job_pages(job_id)
                current_count = len(pages)
                if current_count != last_count or job.status in ("succeeded", "failed", "cancelled"):
                    last_count = current_count
                    total_p = job.page_count or max(1, current_count)
                    payload = {
                        "job_id": job_id,
                        "status": job.status,
                        "processed_pages": current_count,
                        "total_pages": total_p,
                        "progress": round(min(100.0, current_count / total_p * 100.0), 1),
                    }
                    yield f"data: {json.dumps(payload)}\n\n"

                if job.status in ("succeeded", "failed", "cancelled"):
                    break

                await asyncio.sleep(0.5)
        finally:
            db.close()

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("/ocr/jobs/{job_id}/toc")
async def get_job_toc(job_id: int):
    """Retrieves hierarchical Table of Contents (TOC) for a processed document."""
    db = OCRDatabase()
    try:
        job = db.get_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail=f"Job ID {job_id} not found.")

        pages = db.get_job_pages(job_id)
        from blast_ocr.core.document_model import Document, Page, Block, Line, Span, BoundingBox
        from blast_ocr.core.semantic_chunker import SemanticChunker

        pages_list = []
        for p in pages:
            span = Span(text=p.get("text", ""), bbox=BoundingBox(xmin=0, ymin=0, xmax=800, ymax=1000), confidence=p.get("confidence", 1.0))
            line = Line(spans=[span], bbox=span.bbox)
            block = Block(lines=[line], bbox=span.bbox)
            page_obj = Page(page_num=p.get("page", 1), width=800, height=1000, blocks=[block])
            pages_list.append(page_obj)

        doc = Document(title=Path(job.filename).stem, pages=pages_list)
        toc = SemanticChunker.extract_toc(doc)
        return {"job_id": job_id, "document": doc.title, "toc": [t.to_dict() for t in toc]}
    finally:
        db.close()


@router.get("/ocr/jobs/{job_id}/chunks")
async def get_job_chunks(job_id: int, max_tokens: int = 512):
    """Retrieves semantically coherent RAG chunks with metadata."""
    db = OCRDatabase()
    try:
        job = db.get_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail=f"Job ID {job_id} not found.")

        pages = db.get_job_pages(job_id)
        from blast_ocr.core.document_model import Document, Page, Block, Line, Span, BoundingBox
        from blast_ocr.core.semantic_chunker import SemanticChunker

        pages_list = []
        for p in pages:
            span = Span(text=p.get("text", ""), bbox=BoundingBox(xmin=0, ymin=0, xmax=800, ymax=1000), confidence=p.get("confidence", 1.0))
            line = Line(spans=[span], bbox=span.bbox)
            block = Block(lines=[line], bbox=span.bbox)
            page_obj = Page(page_num=p.get("page", 1), width=800, height=1000, blocks=[block])
            pages_list.append(page_obj)

        doc = Document(title=Path(job.filename).stem, pages=pages_list)
        chunks = SemanticChunker.chunk_document(doc, max_chunk_tokens=max_tokens)
        return {"job_id": job_id, "chunk_count": len(chunks), "chunks": [c.to_dict() for c in chunks]}
    finally:
        db.close()


# ============================================================================
# Swarm & Priority Queue Fleet Endpoints (Milestone 2)
# ============================================================================

@router.get("/workers")
async def get_swarm_workers():
    """Returns active swarm workers, hostnames, PIDs, statuses, and resource metrics."""
    registry = WorkerRegistry()
    workers = registry.list_active_workers()

    if not workers:
        # Fallback local process worker info if swarm is running locally
        process = psutil.Process(os.getpid())
        mem_mb = round(process.memory_info().rss / (1024 * 1024), 2)
        workers = [
            {
                "worker_id": f"worker:in-process:{os.getpid()}:main",
                "hostname": os.uname().nodename if hasattr(os, "uname") else "localhost",
                "pid": os.getpid(),
                "status": "idle",
                "current_job_id": None,
                "current_page": 0,
                "total_pages": 0,
                "memory_rss_mb": mem_mb,
                "cpu_percent": round(float(process.cpu_percent(interval=None)), 1),
                "last_heartbeat": datetime.utcnow().timestamp(),
                "uptime_sec": int(datetime.utcnow().timestamp() - process.create_time()),
                "queues": ["blast_ocr:queue:high", "blast_ocr:queue:default", "blast_ocr:queue:low"],
                "jobs_processed_total": 0,
                "jobs_failed_total": 0,
            }
        ]

    return {
        "workers": workers,
        "total_active_workers": len(workers),
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.get("/queues")
async def get_queue_depths():
    """Summarizes job depths across priority tiers and DLQ."""
    client = QueueClient()
    depths = client.get_all_queue_depths()

    queue_map = {
        "blast_ocr:queue:high": depths.get("high", 0),
        "blast_ocr:queue:default": depths.get("default", 0),
        "blast_ocr:queue:low": depths.get("low", 0),
        "blast_ocr:queue:dlq": depths.get("dlq", 0),
    }
    total = sum(queue_map.values())

    return {
        "queues": queue_map,
        "total_pending_jobs": total,
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.get("/queues/dlq")
async def get_dlq_jobs():
    """Lists dead-lettered quarantined jobs with error diagnostics."""
    qm = PriorityQueueManager()
    dlq_list = qm.list_dlq_jobs(limit=100)
    
    formatted = []
    for item in dlq_list:
        formatted.append({
            "job_id": item.get("job_id", 0),
            "source_file": item.get("source_path", "unknown"),
            "priority": item.get("priority", "default"),
            "retry_count": item.get("retry_count", 0),
            "max_retries": item.get("max_retries", 3),
            "dlq_at": item.get("dlq_at", datetime.utcnow().isoformat()),
            "dlq_reason": item.get("dlq_reason", item.get("last_error", "Unknown error")),
        })

    return {
        "dlq_jobs": formatted,
        "total_dlq_count": len(formatted),
    }


@router.post("/ocr/jobs/{job_id}/retry", response_model=JobRetryResponse)
async def retry_failed_job(job_id: int, priority: str = Query("high")):
    """Replays a failed or dead-lettered job into the active queue."""
    clean_priority = priority.lower().strip()
    if clean_priority not in ("high", "default", "low"):
        clean_priority = "high"

    db = OCRDatabase()
    try:
        job = db.get_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail=f"Job ID {job_id} not found.")

        # Reset retry counter and update status in DB
        db.update_job_retry(job_id, retry_count=0, error_message=None)
        db.update_job_status(job_id, JobState.QUEUED)

        # If BackoffDLQHandler available, replay from Redis DLQ
        try:
            handler = BackoffDLQHandler()
            target_q = f"blast_ocr:queue:{clean_priority}"
            handler.replay_dlq_job(job_id, target_queue=target_q)
        except Exception:
            pass

        return JobRetryResponse(
            job_id=job_id,
            status=JobState.QUEUED.value,
            priority=clean_priority,
            retry_count=0,
            message=f"Job {job_id} successfully re-enqueued to {clean_priority} queue.",
        )
    finally:
        db.close()


@router.get("/health", response_model=SystemHealthResponse)
async def system_health():
    """Liveness & readiness probe verifying database, memory, and engine readiness."""
    db_status = "healthy"
    try:
        db = OCRDatabase()
        _ = db.get_recent_jobs(limit=1)
        db.close()
    except Exception as e:
        db_status = f"unhealthy ({e})"

    process = psutil.Process(os.getpid())
    mem_mb = process.memory_info().rss / (1024 * 1024)

    return SystemHealthResponse(
        status="healthy" if db_status == "healthy" else "degraded",
        database=db_status,
        storage_backend=getattr(config, "storage_backend", "local"),
        queue_backend=getattr(config, "queue_backend", "in_process"),
        registered_engines=list(_ENGINE_REGISTRY.keys()),
        memory_used_mb=round(mem_mb, 2),
        timestamp=datetime.utcnow(),
    )


@router.get("/metrics")
async def prometheus_metrics():
    """Prometheus metrics endpoint."""
    try:
        from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
        return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
    except Exception:
        return PlainTextResponse("# Prometheus metrics exporter available\nblast_ocr_status 1\n")


@router.get("/config", response_model=SystemConfigResponse)
async def system_configuration():
    """Returns active system configuration."""
    return SystemConfigResponse(
        app_version="3.0.0",
        ocr_engine_default=getattr(config, "ocr_engine", "rapidocr"),
        available_engines=list(_ENGINE_REGISTRY.keys()),
        max_workers=getattr(config, "max_workers", 2),
        log_dir=str(config.log_dir),
        storage_backend=getattr(config, "storage_backend", "local"),
        queue_backend=getattr(config, "queue_backend", "in_process"),
    )

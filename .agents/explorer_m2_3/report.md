# B.L.A.S.T. OCR — Milestone 2: API Extensions & Comprehensive Test Strategy Report

**Author:** `explorer_m2_3` (Teamwork Explorer / API & Test Architect)  
**Date:** 2026-08-15  
**Milestone:** Milestone 2 — Distributed Multi-Worker Swarm & Durable Queue (Requirement R2)  
**Target Output Artifact:** `blast_ocr/api/schemas.py`, `blast_ocr/api/routes.py`, `tests/test_queue_swarm.py`  

---

## 1. Executive Summary

This investigation designs the REST API extensions and comprehensive test architecture for **Milestone 2 (Distributed Multi-Worker Swarm & Durable Queue)**. 

### Core Deliverables Designed:
1. **API Schema & Route Extensions (`blast_ocr/api/schemas.py` & `routes.py`)**:
   - **Priority-Aware Job Submission**: `POST /v1/ocr/jobs` supporting `priority: "high" | "default" | "low"` and `max_retries: int`.
   - **Worker Swarm Telemetry Endpoint**: `GET /v1/workers` reporting active/idle/busy/draining workers, heartbeats, process IDs, memory RSS, CPU %, and active jobs.
   - **Queue Analytics Endpoint**: `GET /v1/queues` providing real-time statistics (enqueued, active, failed count, DLQ depth) across `high`, `default`, `low`, and `dlq`.
   - **Job Retry & DLQ Replay Endpoint**: `POST /v1/ocr/jobs/{id}/retry` allowing manual or automated replay of failed / quarantined jobs with optional priority upgrade.
2. **Deterministic Fast Test Harness (`fakeredis` + In-Memory SQLite)**:
   - Completely decoupled from external network services: uses `fakeredis.FakeStrictRedis` (v2.37.0 installed) to simulate Redis data structures, TTL expiration, and RQ queue operations in under 0.05s per test.
   - Mocked OCR engine inference to eliminate neural model startup overhead during queue and lifecycle testing.
3. **Comprehensive 7-Category Test Suite (`tests/test_queue_swarm.py`)**:
   - 25+ structured unit, integration, and edge-case tests covering QueueClient priority routing, SwarmSupervisor process management, HeartbeatDaemon registration, ZombieReaper failover, Exponential Backoff retry, Dead-Letter Queue (DLQ) isolation, FastAPI TestClient integration, and resilience against Redis outages or worker crashes.

---

## 2. API Schema Extensions (`blast_ocr/api/schemas.py`)

### 2.1 Model Upgrades & New Pydantic Models

```python
"""
blast_ocr.api.schemas (Extensions for Milestone 2)
"""

from typing import List, Dict, Optional, Any, Literal
from pydantic import BaseModel, Field, field_validator
from datetime import datetime


# ---------------------------------------------------------------------------
# Job Submission & Status Enhancements
# ---------------------------------------------------------------------------

class JobCreateRequest(BaseModel):
    source_path: Optional[str] = Field(None, description="Path to input document (PDF, PPTX, image, directory)")
    output_dir: Optional[str] = Field(None, description="Directory where output artifacts will be saved")
    ocr_engine: str = Field("rapidocr", description="Target OCR engine: rapidocr, easyocr, tesseract, ensemble")
    priority: Literal["high", "default", "low"] = Field(
        "default", description="Execution priority tier: high (urgent/single-page), default (batch), low (bulk)"
    )
    max_retries: int = Field(3, ge=0, le=10, description="Maximum retry attempts for transient failures")
    auto_deskew: bool = Field(True, description="Enable automatic image deskewing")
    denoise_level: int = Field(0, description="Denoising filter level (0-20)")
    contrast_boost: float = Field(1.0, description="Contrast enhancement boost factor")
    enable_dewarp: bool = Field(False, description="Enable book spine curvature dewarping")
    enable_tier0_routing: bool = Field(True, description="Enable native PDF vector text fast-path routing")
    enable_book_intelligence: bool = Field(True, description="Enable running header/footer strip & dehyphenation")
    secure_mode: bool = Field(False, description="Enable enterprise PII redaction")
    max_workers: int = Field(2, description="Number of parallel OCR worker threads")
    formats: List[str] = Field(default_factory=lambda: ["markdown", "docx", "pdf", "txt", "epub", "json"])


class JobResponse(BaseModel):
    job_id: int
    status: str
    priority: str = "default"
    source_path: str
    rq_job_id: Optional[str] = None
    queue_name: Optional[str] = None
    total_pages: Optional[int] = None
    created_at: Optional[datetime] = None
    message: Optional[str] = None


class JobStatusResponse(BaseModel):
    job_id: int
    status: str
    priority: str = "default"
    source_file: str
    total_pages: int
    processed_pages: int
    progress_percentage: float
    average_confidence: float
    processing_time_sec: float
    retry_count: int = 0
    max_retries: int = 3
    worker_id: Optional[str] = None
    queue_name: Optional[str] = None
    error_message: Optional[str] = None
    dlq_at: Optional[datetime] = None
    dlq_reason: Optional[str] = None


# ---------------------------------------------------------------------------
# Swarm Worker Telemetry Schemas
# ---------------------------------------------------------------------------

class WorkerInfoResponse(BaseModel):
    worker_id: str = Field(..., description="Unique worker process identity")
    hostname: str = Field(..., description="Node hostname where worker runs")
    pid: int = Field(..., description="Operating System Process ID")
    started_at: str = Field(..., description="ISO-8601 worker launch timestamp")
    last_heartbeat: float = Field(..., description="Unix timestamp of most recent heartbeat")
    heartbeat_age_sec: float = Field(0.0, description="Elapsed seconds since last heartbeat")
    status: str = Field("idle", description="Worker state: idle, busy, draining, offline")
    current_job_id: Optional[int] = Field(None, description="Active job ID currently processing")
    current_page: Optional[int] = Field(None, description="Current page number being processed")
    total_pages: Optional[int] = Field(None, description="Total pages of the active job")
    memory_rss_mb: float = Field(0.0, description="Worker RSS memory footprint in MB")
    cpu_percent: float = Field(0.0, description="Worker CPU utilization percentage")
    queues: List[str] = Field(default_factory=list, description="Queue names worker is listening on")
    jobs_processed_total: int = Field(0, description="Count of successfully finished jobs")
    jobs_failed_total: int = Field(0, description="Count of failed jobs on this worker")


class SwarmStatusResponse(BaseModel):
    active_workers_count: int = Field(..., description="Count of responsive swarm workers")
    busy_workers_count: int = Field(0, description="Workers currently executing tasks")
    idle_workers_count: int = Field(0, description="Workers idle waiting for jobs")
    draining_workers_count: int = Field(0, description="Workers in graceful drain mode")
    workers: List[WorkerInfoResponse] = Field(default_factory=list, description="Worker records")


# ---------------------------------------------------------------------------
# Queue Telemetry Schemas
# ---------------------------------------------------------------------------

class QueueStatItem(BaseModel):
    name: str = Field(..., description="Queue key name in Redis")
    priority: str = Field(..., description="Priority classification (high, default, low, dlq)")
    enqueued_count: int = Field(..., description="Number of pending jobs waiting in queue")
    active_count: int = Field(0, description="Number of jobs currently in-flight on workers")
    failed_count: int = Field(0, description="Number of failed jobs tracked for this queue")


class QueuesOverviewResponse(BaseModel):
    total_enqueued: int = Field(..., description="Total pending jobs across all priority queues")
    total_active: int = Field(0, description="Total in-flight jobs being processed")
    total_failed: int = Field(0, description="Total failed / dead-lettered jobs")
    dlq_depth: int = Field(0, description="Number of quarantined jobs in Dead Letter Queue")
    queues: Dict[str, QueueStatItem] = Field(..., description="Detailed statistics per queue")


# ---------------------------------------------------------------------------
# Job Retry & DLQ Replay Schemas
# ---------------------------------------------------------------------------

class JobRetryRequest(BaseModel):
    priority_override: Optional[Literal["high", "default", "low"]] = Field(
        None, description="Optional override priority tier for re-enqueueing"
    )
    reset_retries: bool = Field(True, description="Reset retry_count counter back to 0")
    config_overrides: Optional[Dict[str, Any]] = Field(
        None, description="Optional configuration parameter adjustments for retry"
    )


class JobRetryResponse(BaseModel):
    job_id: int
    previous_status: str
    new_status: str
    priority: str
    rq_job_id: Optional[str] = None
    message: str
    requeued_at: datetime = Field(default_factory=datetime.utcnow)
```

---

## 3. REST API Endpoint Specifications (`blast_ocr/api/routes.py`)

### 3.1 Endpoint Routing Table

| HTTP Method | Route Path | Request Schema | Response Schema | Description & Status Code |
| :--- | :--- | :--- | :--- | :--- |
| `POST` | `/v1/ocr/jobs` | Form / `JobCreateRequest` | `JobResponse` | **202 Accepted**: Enqueues job to priority queue (`high`/`default`/`low`) |
| `GET` | `/v1/workers` | None | `SwarmStatusResponse` | **200 OK**: Lists all active swarm workers and telemetry |
| `GET` | `/v1/queues` | None | `QueuesOverviewResponse` | **200 OK**: Aggregates queue depths, active counts, and DLQ |
| `POST` | `/v1/ocr/jobs/{job_id}/retry` | `JobRetryRequest` (optional) | `JobRetryResponse` | **200 OK**: Replays failed or DLQ job with reset counter |
| `GET` | `/v1/ocr/jobs/{job_id}` | Path `job_id` | `JobStatusResponse` | **200 OK**: Retrieves job status, priority, worker_id, retry_count |

---

### 3.2 Endpoint Implementations Detail

#### 1. `POST /v1/ocr/jobs` (Priority Dispatch & Storage Decoupling)
- **Logic**:
  1. Validates input (`file` upload or `source_path` parameter).
  2. Validates `priority` in `["high", "default", "low"]` (default: `"default"`).
  3. Checks `config.queue_backend`:
     - **When `redis`**:
       Calls `QueueClient.enqueue_job(source_path=doc_source, output_dir=final_output_dir, priority=priority, max_retries=max_retries, config_overrides=config_overrides)`.
       The `QueueClient` creates the `OCRJob` DB record with `priority=priority`, `max_retries=max_retries`, and `status=JobState.QUEUED.value`, then dispatches to the corresponding Redis queue (`blast_ocr:queue:{priority}`).
     - **When `sync` / `in_process`**:
       Creates DB job record, marks `JobState.QUEUED`, and dispatches `_execute_pipeline_task` via `BackgroundTasks`, passing `job_id=job_id` to fix duplicate job creation.
  4. Returns `JobResponse` with `job_id`, `status="queued"`, `priority`, and `created_at`.

```python
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
    if not file and not source_path:
        raise HTTPException(status_code=400, detail="Either 'file' upload or 'source_path' must be provided.")

    if priority not in ("high", "default", "low"):
        raise HTTPException(status_code=400, detail=f"Invalid priority '{priority}'. Must be 'high', 'default', or 'low'.")

    # Handle direct file upload
    if file:
        temp_dir = tempfile.mkdtemp(prefix="blast_upload_")
        target_path = os.path.join(temp_dir, file.filename)
        with open(target_path, "wb") as f:
            shutil.copyfileobj(file.file, f)
        doc_source = target_path
    else:
        if not os.path.exists(source_path):
            raise HTTPException(status_code=404, detail=f"Source path '{source_path}' does not exist.")
        doc_source = source_path

    final_output_dir = output_dir or os.path.join(os.path.dirname(doc_source), "ocr_results")
    os.makedirs(final_output_dir, exist_ok=True)

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

    # Queue Dispatch: Check backend configuration
    if getattr(config, "queue_backend", "sync") == "redis":
        from blast_ocr.queue.client import enqueue_job
        enqueue_res = enqueue_job(
            source_path=doc_source,
            output_dir=final_output_dir,
            priority=priority,
            max_retries=max_retries,
            config_overrides=config_overrides,
        )
        return JobResponse(
            job_id=enqueue_res["job_id"],
            status=JobState.QUEUED.value,
            priority=priority,
            source_path=doc_source,
            rq_job_id=enqueue_res.get("rq_job_id"),
            queue_name=enqueue_res.get("queue_name", f"blast_ocr:queue:{priority}"),
            created_at=datetime.utcnow(),
            message=f"OCR job queued on priority '{priority}' queue.",
        )
    else:
        db = OCRDatabase()
        job_id = db.create_job(os.path.basename(doc_source), 0)
        db.update_job_status(job_id, JobState.QUEUED)
        db.close()

        background_tasks.add_task(_execute_pipeline_task, doc_source, final_output_dir, config_overrides, job_id)
        return JobResponse(
            job_id=job_id,
            status=JobState.QUEUED.value,
            priority=priority,
            source_path=doc_source,
            created_at=datetime.utcnow(),
            message="OCR job successfully queued for execution.",
        )
```

---

#### 2. `GET /v1/workers` (Swarm Telemetry Endpoint)
- **Logic**:
  1. Inspects Redis worker registry (`blast_ocr:workers:active`).
  2. For each worker ID, retrieves hash metadata `blast_ocr:worker:<id>`.
  3. Computes `heartbeat_age_sec = time.time() - last_heartbeat`.
  4. Classifies worker as `idle`, `busy`, `draining`, or `offline` (if heartbeat > TTL).
  5. If Redis is down or in sync mode, gracefully returns zero workers without throwing HTTP 500.

```python
@router.get("/workers", response_model=SwarmStatusResponse)
async def list_swarm_workers():
    """Lists all active worker processes, heartbeats, status, and telemetry metrics."""
    try:
        from blast_ocr.queue.heartbeat import HeartbeatRegistry
        registry = HeartbeatRegistry()
        workers_data = registry.get_all_workers()
        
        workers_list = []
        busy = idle = draining = 0
        now = datetime.utcnow().timestamp()

        for w in workers_data:
            age = max(0.0, now - float(w.get("last_heartbeat", now)))
            status = w.get("status", "idle")
            if status == "busy":
                busy += 1
            elif status == "draining":
                draining += 1
            else:
                idle += 1

            workers_list.append(WorkerInfoResponse(
                worker_id=w["worker_id"],
                hostname=w.get("hostname", "unknown"),
                pid=int(w.get("pid", 0)),
                started_at=str(w.get("started_at", "")),
                last_heartbeat=float(w.get("last_heartbeat", 0.0)),
                heartbeat_age_sec=round(age, 2),
                status=status,
                current_job_id=w.get("current_job_id"),
                current_page=w.get("current_page"),
                total_pages=w.get("total_pages"),
                memory_rss_mb=float(w.get("memory_rss_mb", 0.0)),
                cpu_percent=float(w.get("cpu_percent", 0.0)),
                queues=w.get("queues", []),
                jobs_processed_total=int(w.get("jobs_processed_total", 0)),
                jobs_failed_total=int(w.get("jobs_failed_total", 0)),
            ))

        return SwarmStatusResponse(
            active_workers_count=len(workers_list),
            busy_workers_count=busy,
            idle_workers_count=idle,
            draining_workers_count=draining,
            workers=workers_list,
        )
    except Exception as e:
        # Graceful fallback if Redis is unreachable or running in sync mode
        return SwarmStatusResponse(
            active_workers_count=0,
            busy_workers_count=0,
            idle_workers_count=0,
            draining_workers_count=0,
            workers=[],
        )
```

---

#### 3. `GET /v1/queues` (Queue Statistics & Metrics Endpoint)
- **Logic**:
  1. Queries queue depths for `high`, `default`, `low`, and `dlq` using `QueueClient.get_queue_depths()`.
  2. Aggregates total enqueued, active in-flight, failed, and DLQ depth.
  3. Returns `QueuesOverviewResponse`.

```python
@router.get("/queues", response_model=QueuesOverviewResponse)
async def get_queue_statistics():
    """Retrieves real-time queue statistics across priority tiers and DLQ."""
    try:
        from blast_ocr.queue.client import QueueClient
        client = QueueClient()
        stats = client.get_queue_statistics()
        return QueuesOverviewResponse(**stats)
    except Exception:
        # Fallback for sync mode
        return QueuesOverviewResponse(
            total_enqueued=0,
            total_active=0,
            total_failed=0,
            dlq_depth=0,
            queues={
                "blast_ocr:queue:high": QueueStatItem(name="blast_ocr:queue:high", priority="high", enqueued_count=0),
                "blast_ocr:queue:default": QueueStatItem(name="blast_ocr:queue:default", priority="default", enqueued_count=0),
                "blast_ocr:queue:low": QueueStatItem(name="blast_ocr:queue:low", priority="low", enqueued_count=0),
                "blast_ocr:queue:dlq": QueueStatItem(name="blast_ocr:queue:dlq", priority="dlq", enqueued_count=0),
            },
        )
```

---

#### 4. `POST /v1/ocr/jobs/{job_id}/retry` (Job Retry & DLQ Replay)
- **Logic**:
  1. Checks if job exists in `OCRDatabase`. If not found, raises HTTP 404.
  2. Verifies job state: only `FAILED`, `QUARANTINED`, `TIMED_OUT`, or `PARTIAL_FAILURE` jobs are eligible for retry. If job is `PROCESSING` or `SUCCEEDED`, raises HTTP 400 Bad Request.
  3. Updates DB:
     - Sets `status = JobState.QUEUED.value`
     - If `reset_retries=True`: `retry_count = 0`
     - Clears `error_message = None`, `dlq_at = None`, `dlq_reason = None`
     - Updates `priority = priority_override or job.priority`
  4. Enqueues job to Redis priority queue (or sync background task).
  5. Returns `JobRetryResponse`.

```python
@router.post("/ocr/jobs/{job_id}/retry", response_model=JobRetryResponse)
async def retry_failed_job(
    job_id: int,
    retry_req: Optional[JobRetryRequest] = None,
    background_tasks: BackgroundTasks = BackgroundTasks(),
):
    """Replays or retries a failed or Dead-Letter Queue (DLQ) job with reset counters."""
    db = OCRDatabase()
    try:
        job = db.get_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail=f"Job ID {job_id} not found.")

        current_status = job.status
        if current_status not in (JobState.FAILED.value, JobState.QUARANTINED.value, JobState.TIMED_OUT.value, JobState.PARTIAL_FAILURE.value):
            raise HTTPException(
                status_code=400,
                detail=f"Job ID {job_id} is in status '{current_status}' and cannot be retried. Only failed or quarantined jobs can be retried.",
            )

        new_priority = (retry_req.priority_override if retry_req and retry_req.priority_override else getattr(job, "priority", "default")) or "default"
        reset_retries = retry_req.reset_retries if retry_req else True
        config_overrides = (retry_req.config_overrides if retry_req else {}) or {}

        # Reset DB job state
        db.update_job_status(job_id, JobState.QUEUED)
        with db.session_scope() as session:
            job_obj = session.query(OCRJob).filter_by(id=job_id).first()
            if job_obj:
                if reset_retries:
                    job_obj.retry_count = 0
                if hasattr(job_obj, "priority"):
                    job_obj.priority = new_priority
                if hasattr(job_obj, "dlq_at"):
                    job_obj.dlq_at = None
                if hasattr(job_obj, "dlq_reason"):
                    job_obj.dlq_reason = None
                job_obj.error_message = None

        # Re-enqueue
        rq_job_id = None
        if getattr(config, "queue_backend", "sync") == "redis":
            from blast_ocr.queue.client import QueueClient
            q_client = QueueClient()
            enq_res = q_client.requeue_job(
                job_id=job_id,
                source_path=job.filename,
                priority=new_priority,
                config_overrides=config_overrides,
            )
            rq_job_id = enq_res.get("rq_job_id")
        else:
            output_dir = os.path.join(os.path.dirname(job.filename), "ocr_results")
            background_tasks.add_task(_execute_pipeline_task, job.filename, output_dir, config_overrides, job_id)

        return JobRetryResponse(
            job_id=job_id,
            previous_status=current_status,
            new_status=JobState.QUEUED.value,
            priority=new_priority,
            rq_job_id=rq_job_id,
            message=f"Job {job_id} successfully re-enqueued on '{new_priority}' priority queue.",
            requeued_at=datetime.utcnow(),
        )
    finally:
        db.close()
```

---

## 4. Deterministic Fakeredis Test Harness & Fixture Design

To satisfy the requirement that all test suites run **deterministically, fast (< 1s per suite), and without requiring an active `redis-server` process**, we architect an in-memory test harness based on `fakeredis` (version 2.37.0).

### 4.1 Test Fixture Architecture (`tests/conftest.py` / `tests/test_queue_swarm.py`)

```python
import pytest
import fakeredis
from unittest.mock import patch, MagicMock
from blast_ocr.config import config
from blast_ocr.storage.database import OCRDatabase

@pytest.fixture
def fake_redis_server():
    """Shared FakeServer instance for multi-connection synchronization."""
    return fakeredis.FakeServer()

@pytest.fixture
def fake_redis(fake_redis_server, monkeypatch):
    """
    Patches get_redis_connection across all queue modules to return an in-memory FakeStrictRedis client.
    """
    client = fakeredis.FakeStrictRedis(server=fake_redis_server, version=6)
    
    # Patch connection providers across all swarm and queue modules
    monkeypatch.setattr("blast_ocr.queue.client.get_redis_connection", lambda: client)
    monkeypatch.setattr("blast_ocr.queue.heartbeat.get_redis_connection", lambda: client)
    monkeypatch.setattr("blast_ocr.queue.reaper.get_redis_connection", lambda: client)
    monkeypatch.setattr("blast_ocr.queue.swarm.get_redis_connection", lambda: client)
    monkeypatch.setattr("blast_ocr.queue.tasks.get_redis_connection", lambda: client)
    
    # Configure backend to redis
    monkeypatch.setattr(config, "queue_backend", "redis")
    return client

@pytest.fixture
def mock_ocr_pipeline(monkeypatch):
    """
    Mocks actual OCR page processing to return instant results (0ms latency),
    isolating queue plumbing, serialization, and worker supervisor logic from ONNX runtime.
    """
    fake_page_result = {
        "page": 1,
        "text": "Simulated OCR Text Output",
        "confidence": 0.98,
        "processing_time": 0.005,
    }
    monkeypatch.setattr("blast_ocr.core.worker.process_page_wrapper", lambda *args, **kwargs: fake_page_result)
    monkeypatch.setattr("blast_ocr.pipeline.process_page_wrapper", lambda *args, **kwargs: fake_page_result)
    return fake_page_result

@pytest.fixture
def clean_db(tmp_path, monkeypatch):
    """Provides an isolated temporary database for each test run."""
    db_file = tmp_path / "test_swarm.db"
    db_url = f"sqlite:///{db_file}"
    monkeypatch.setattr(config, "database_url", db_url)
    db = OCRDatabase(db_url)
    yield db
    db.close()
```

---

## 5. Comprehensive 7-Category Test Suite Specification (`tests/test_queue_swarm.py`)

Below is the complete architectural specification and test matrix for `tests/test_queue_swarm.py`.

### 5.1 Test Matrix Overview

```
+---------------------------------------------------------------------------------------------------------+
| CATEGORY                         | TEST FUNCTION                                | VERIFICATION TARGET  |
+----------------------------------+----------------------------------------------+----------------------+
| 1. QueueClient Unit Tests        | test_queue_client_priority_routing           | high/default/low routing|
|                                  | test_queue_client_deduplication_lock         | Idempotency lease    |
|                                  | test_queue_client_metrics_and_depths         | Queue depth counters |
| 2. SwarmSupervisor Management    | test_swarm_supervisor_pool_initialization    | Worker pool creation |
|                                  | test_swarm_supervisor_worker_scaling         | Dynamic scale up/down|
|                                  | test_swarm_supervisor_crash_respawn          | Auto worker respawn  |
|                                  | test_swarm_supervisor_graceful_drain         | SIGTERM / drain cycle|
| 3. HeartbeatDaemon & TTL Expiry  | test_heartbeat_daemon_registration           | Redis HSET & SADD    |
|                                  | test_heartbeat_daemon_periodic_emission      | Telemetry update     |
|                                  | test_heartbeat_daemon_clean_unregistration   | Unregister on exit   |
| 4. Zombie Reaper & Recovery      | test_zombie_reaper_detects_dead_worker       | Dead worker detection|
|                                  | test_zombie_reaper_recovers_orphaned_job     | Job failover retry   |
|                                  | test_zombie_reaper_quarantines_to_dlq        | Max retry DLQ move   |
| 5. Exponential Backoff & DLQ     | test_retry_taxonomy_classification          | Transient vs deterministic|
|                                  | test_exponential_backoff_delay_calculation   | 2^k * base + jitter  |
|                                  | test_transient_failure_reschedules_job       | Backoff rescheduling |
|                                  | test_deterministic_failure_immediate_dlq     | Instant DLQ isolation|
|                                  | test_dlq_inspection_and_quarantine_metadata  | DLQ error audit trail|
| 6. FastAPI TestClient API Tests  | test_api_submit_job_with_priority            | POST /v1/ocr/jobs    |
|                                  | test_api_get_workers_endpoint                | GET /v1/workers      |
|                                  | test_api_get_queues_endpoint                 | GET /v1/queues       |
|                                  | test_api_retry_failed_job_success            | POST /v1/ocr/jobs/retry|
|                                  | test_api_retry_rejects_active_job            | 400 on processing job|
|                                  | test_api_retry_404_on_missing_job            | 404 on invalid ID    |
| 7. Edge Cases & Resilience       | test_redis_disconnect_graceful_fallback      | Degraded sync mode   |
|                                  | test_poisoned_payload_dlq_isolation          | Unpicklable payload  |
|                                  | test_concurrent_worker_dequeue_no_race       | Exactly-once claim   |
+---------------------------------------------------------------------------------------------------------+
```

---

### 5.2 Test Implementations Detail (`tests/test_queue_swarm.py`)

#### Category 1: QueueClient Unit Tests
```python
def test_queue_client_priority_routing(fake_redis, clean_db, tmp_path):
    """Verifies that jobs submitted with high, default, or low priority land on the exact corresponding RQ queues."""
    from blast_ocr.queue.client import QueueClient
    
    src = tmp_path / "doc.pdf"
    src.write_bytes(b"%PDF-1.4 simulated pdf")

    client = QueueClient()
    
    # 1. Enqueue High
    res_high = client.enqueue_job(str(src), priority="high")
    assert res_high["priority"] == "high"
    q_high = client.get_queue("high")
    assert len(q_high) == 1

    # 2. Enqueue Default
    res_def = client.enqueue_job(str(src), priority="default")
    assert res_def["priority"] == "default"
    q_def = client.get_queue("default")
    assert len(q_def) == 1

    # 3. Enqueue Low
    res_low = client.enqueue_job(str(src), priority="low")
    assert res_low["priority"] == "low"
    q_low = client.get_queue("low")
    assert len(q_low) == 1


def test_queue_client_deduplication_lock(fake_redis, clean_db, tmp_path):
    """Verifies distributed idempotency lock prevents duplicate processing of identical payload hashes."""
    from blast_ocr.queue.client import QueueClient
    
    src = tmp_path / "duplicate.png"
    src.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 32)
    
    client = QueueClient()
    res1 = client.enqueue_job(str(src), input_sha256="abc123hash", priority="high")
    res2 = client.enqueue_job(str(src), input_sha256="abc123hash", priority="high")
    
    # Second enqueue should return existing job without double-enqueueing
    assert res1["job_id"] == res2["job_id"]
    q_high = client.get_queue("high")
    assert len(q_high) == 1


def test_queue_client_metrics_and_depths(fake_redis, clean_db, tmp_path):
    """Verifies QueueClient aggregates queue depths and metrics accurately."""
    from blast_ocr.queue.client import QueueClient
    
    src = tmp_path / "metric_doc.pdf"
    src.write_bytes(b"%PDF-1.4 test")

    client = QueueClient()
    client.enqueue_job(str(src), priority="high")
    client.enqueue_job(str(src), priority="high")
    client.enqueue_job(str(src), priority="default")
    
    depths = client.get_queue_depths()
    assert depths["high"] == 2
    assert depths["default"] == 1
    assert depths["low"] == 0
    assert depths["dlq"] == 0
```

---

#### Category 2: SwarmSupervisor Process Management Tests
```python
def test_swarm_supervisor_pool_initialization(fake_redis):
    """Verifies supervisor initializes worker process metadata and pool size."""
    from blast_ocr.queue.swarm import SwarmSupervisor
    
    supervisor = SwarmSupervisor(worker_count=3, queues=["high", "default", "low"])
    assert supervisor.worker_count == 3
    assert supervisor.queues == ["high", "default", "low"]
    assert len(supervisor.workers) == 0  # not started yet


def test_swarm_supervisor_worker_scaling(fake_redis, monkeypatch):
    """Verifies dynamic scale-up and scale-down of worker processes."""
    from blast_ocr.queue.swarm import SwarmSupervisor
    
    supervisor = SwarmSupervisor(worker_count=2)
    mock_spawn = MagicMock()
    mock_drain = MagicMock()
    monkeypatch.setattr(supervisor, "_spawn_worker", mock_spawn)
    monkeypatch.setattr(supervisor, "_drain_worker", mock_drain)
    
    supervisor.scale(4)
    assert supervisor.worker_count == 4
    assert mock_spawn.call_count == 2
    
    supervisor.scale(2)
    assert supervisor.worker_count == 2
    assert mock_drain.call_count == 2


def test_swarm_supervisor_crash_respawn(fake_redis, monkeypatch):
    """Verifies supervisor detects crashed child process and respawns replacement."""
    from blast_ocr.queue.swarm import SwarmSupervisor
    
    supervisor = SwarmSupervisor(worker_count=2)
    fake_proc = MagicMock()
    fake_proc.is_alive.return_value = False
    fake_proc.exitcode = 1
    fake_proc.pid = 9999
    
    supervisor.worker_processes = {9999: fake_proc}
    
    mock_spawn = MagicMock()
    monkeypatch.setattr(supervisor, "_spawn_worker", mock_spawn)
    
    supervisor.check_and_heal_workers()
    assert 9999 not in supervisor.worker_processes
    assert mock_spawn.call_count == 1
```

---

#### Category 3: Heartbeat Daemon & TTL Expiry Tests
```python
def test_heartbeat_daemon_registration(fake_redis):
    """Verifies worker heartbeat registration in Redis with TTL."""
    from blast_ocr.queue.heartbeat import HeartbeatDaemon, HeartbeatRegistry
    
    daemon = HeartbeatDaemon(worker_id="worker:test-host:1001:abcd", heartbeat_interval=1.0, ttl=20)
    daemon._emit_heartbeat()
    
    registry = HeartbeatRegistry()
    active_workers = registry.get_active_worker_ids()
    assert "worker:test-host:1001:abcd" in active_workers
    
    meta = registry.get_worker_metadata("worker:test-host:1001:abcd")
    assert meta["worker_id"] == "worker:test-host:1001:abcd"
    assert meta["status"] == "idle"
    assert "last_heartbeat" in meta


def test_heartbeat_daemon_periodic_emission(fake_redis):
    """Verifies updating worker job progress and CPU/memory telemetry."""
    from blast_ocr.queue.heartbeat import HeartbeatDaemon, HeartbeatRegistry
    
    daemon = HeartbeatDaemon(worker_id="worker:test-host:1002:efgh", heartbeat_interval=1.0)
    daemon.set_status(status="busy", job_id=55, current_page=3, total_pages=10)
    daemon._emit_heartbeat()
    
    registry = HeartbeatRegistry()
    meta = registry.get_worker_metadata("worker:test-host:1002:efgh")
    assert meta["status"] == "busy"
    assert int(meta["current_job_id"]) == 55
    assert int(meta["current_page"]) == 3
    assert int(meta["total_pages"]) == 10
```

---

#### Category 4: Zombie Reaper & Dead-Worker Recovery Tests
```python
def test_zombie_reaper_detects_dead_worker(fake_redis):
    """Verifies reaper identifies workers whose heartbeats have expired."""
    import time
    from blast_ocr.queue.heartbeat import HeartbeatRegistry
    from blast_ocr.queue.reaper import ZombieReaper
    
    registry = HeartbeatRegistry()
    # Register a worker with stale heartbeat (30s ago)
    stale_time = time.time() - 30.0
    registry.register_worker_raw("worker:dead:5001:xxxx", {"last_heartbeat": stale_time, "status": "busy"})
    
    reaper = ZombieReaper(heartbeat_ttl=20.0)
    dead_workers = reaper.find_dead_workers()
    assert "worker:dead:5001:xxxx" in dead_workers


def test_zombie_reaper_recovers_orphaned_job(fake_redis, clean_db):
    """Verifies reaper rescues in-flight jobs from dead workers and re-enqueues them."""
    import time
    from blast_ocr.queue.heartbeat import HeartbeatRegistry
    from blast_ocr.queue.reaper import ZombieReaper
    from blast_ocr.core.models import JobState
    
    job_id = clean_db.create_job("orphaned.pdf", 5)
    clean_db.update_job_status(job_id, JobState.PROCESSING)
    
    registry = HeartbeatRegistry()
    stale_time = time.time() - 40.0
    registry.register_worker_raw(
        "worker:crashed:6001:yyyy",
        {"last_heartbeat": stale_time, "status": "busy", "current_job_id": job_id}
    )
    
    reaper = ZombieReaper(heartbeat_ttl=20.0)
    reaper.reap_and_recover()
    
    # Check that worker was removed from active set
    assert "worker:crashed:6001:yyyy" not in registry.get_active_worker_ids()
    
    # Check that job was re-queued
    job = clean_db.get_job(job_id)
    assert job.status == JobState.QUEUED.value


def test_zombie_reaper_quarantines_to_dlq(fake_redis, clean_db):
    """Verifies reaper isolates jobs that have exhausted max_retries directly to DLQ."""
    import time
    from blast_ocr.queue.heartbeat import HeartbeatRegistry
    from blast_ocr.queue.reaper import ZombieReaper
    from blast_ocr.storage.database import OCRJob
    from blast_ocr.core.models import JobState
    
    job_id = clean_db.create_job("exhausted.pdf", 5)
    with clean_db.session_scope() as session:
        j = session.query(OCRJob).filter_by(id=job_id).first()
        j.status = JobState.PROCESSING.value
        j.retry_count = 3
        j.max_retries = 3
    
    registry = HeartbeatRegistry()
    registry.register_worker_raw(
        "worker:fatal:7001:zzzz",
        {"last_heartbeat": time.time() - 50.0, "status": "busy", "current_job_id": job_id}
    )
    
    reaper = ZombieReaper(heartbeat_ttl=20.0)
    reaper.reap_and_recover()
    
    job = clean_db.get_job(job_id)
    assert job.status == JobState.FAILED.value
    assert "Worker lost" in (job.error_message or "")
```

---

#### Category 5: Exponential Backoff & DLQ Isolation Tests
```python
def test_retry_taxonomy_classification():
    """Verifies exception classification for transient vs deterministic errors."""
    from blast_ocr.core.job_state import classify_exception
    from blast_ocr.core.exceptions import OCREngineError
    from blast_ocr.security.gateway import SecurityValidationError
    
    # Transient -> True
    assert classify_exception(OCREngineError("CUDA OOM")) is True
    assert classify_exception(TimeoutError("Redis timeout")) is True
    assert classify_exception(ConnectionError("Socket closed")) is True
    
    # Deterministic -> False
    assert classify_exception(SecurityValidationError("Disallowed format")) is False
    assert classify_exception(ValueError("Invalid argument")) is False
    assert classify_exception(FileNotFoundError("No file")) is False


def test_exponential_backoff_delay_calculation():
    """Verifies exponential backoff delay curve and bounding."""
    from blast_ocr.queue.tasks import compute_backoff_delay
    
    # Attempt 1: ~2.0s
    d1 = compute_backoff_delay(retry_count=1, base_delay=2.0, backoff_factor=2.0, max_backoff=60.0, jitter=0.0)
    assert d1 == 2.0
    
    # Attempt 2: ~4.0s
    d2 = compute_backoff_delay(retry_count=2, base_delay=2.0, backoff_factor=2.0, max_backoff=60.0, jitter=0.0)
    assert d2 == 4.0
    
    # Attempt 3: ~8.0s
    d3 = compute_backoff_delay(retry_count=3, base_delay=2.0, backoff_factor=2.0, max_backoff=60.0, jitter=0.0)
    assert d3 == 8.0
    
    # Bounded to max_backoff
    d_huge = compute_backoff_delay(retry_count=10, base_delay=2.0, backoff_factor=2.0, max_backoff=60.0, jitter=0.0)
    assert d_huge == 60.0


def test_transient_failure_reschedules_job(fake_redis, clean_db, mock_ocr_pipeline, monkeypatch):
    """Verifies that transient errors increment retry_count and reschedule execution."""
    from blast_ocr.queue.tasks import execute_ocr_task
    from blast_ocr.core.exceptions import OCREngineError
    
    job_id = clean_db.create_job("transient.pdf", 1)
    
    def raise_transient(*args, **kwargs):
        raise OCREngineError("Simulated ONNX model fault")
    
    monkeypatch.setattr("blast_ocr.pipeline.BlastPipeline.process_job", raise_transient)
    
    execute_ocr_task("transient.pdf", "/tmp/out", job_id=job_id, priority="high")
    
    job = clean_db.get_job(job_id)
    assert job.retry_count == 1
    assert job.status in ("queued", "processing")


def test_deterministic_failure_immediate_dlq(fake_redis, clean_db, monkeypatch):
    """Verifies that deterministic errors fail immediately and route to DLQ without retrying."""
    from blast_ocr.queue.tasks import execute_ocr_task
    from blast_ocr.security.gateway import SecurityValidationError
    
    job_id = clean_db.create_job("malicious.pdf", 1)
    
    def raise_security(*args, **kwargs):
        raise SecurityValidationError("Executable payload detected")
    
    monkeypatch.setattr("blast_ocr.pipeline.BlastPipeline.process_job", raise_security)
    
    execute_ocr_task("malicious.pdf", "/tmp/out", job_id=job_id, priority="high")
    
    job = clean_db.get_job(job_id)
    assert job.status == "failed"
    assert job.retry_count == 0  # No retry attempted
```

---

#### Category 6: FastAPI Route Integration Tests (with TestClient)
```python
from fastapi.testclient import TestClient
from blast_ocr.api.app import app

client = TestClient(app)

def test_api_submit_job_with_priority(fake_redis, clean_db, mock_ocr_pipeline, tmp_path):
    """Tests POST /v1/ocr/jobs with high priority."""
    img_path = tmp_path / "high_prio.png"
    img_path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 32)
    
    response = client.post(
        "/v1/ocr/jobs",
        data={"source_path": str(img_path), "priority": "high", "max_retries": "3"}
    )
    assert response.status_code == 202
    data = response.json()
    assert data["status"] == "queued"
    assert data["priority"] == "high"
    assert "job_id" in data


def test_api_get_workers_endpoint(fake_redis):
    """Tests GET /v1/workers returning active worker telemetry."""
    from blast_ocr.queue.heartbeat import HeartbeatRegistry
    import time
    
    registry = HeartbeatRegistry()
    registry.register_worker_raw("worker:api-test:101:abcd", {
        "hostname": "test-node",
        "pid": 101,
        "last_heartbeat": time.time(),
        "status": "busy",
        "current_job_id": 12,
        "memory_rss_mb": 256.0,
        "cpu_percent": 15.5,
    })
    
    response = client.get("/v1/workers")
    assert response.status_code == 200
    data = response.json()
    assert data["active_workers_count"] >= 1
    assert data["busy_workers_count"] >= 1
    assert data["workers"][0]["worker_id"] == "worker:api-test:101:abcd"


def test_api_get_queues_endpoint(fake_redis, clean_db, tmp_path):
    """Tests GET /v1/queues reporting queue depths."""
    from blast_ocr.queue.client import QueueClient
    
    src = tmp_path / "queue_test.pdf"
    src.write_bytes(b"%PDF-1.4 test")
    
    q_client = QueueClient()
    q_client.enqueue_job(str(src), priority="high")
    q_client.enqueue_job(str(src), priority="low")
    
    response = client.get("/v1/queues")
    assert response.status_code == 200
    data = response.json()
    assert data["total_enqueued"] >= 2
    assert "queues" in data


def test_api_retry_failed_job_success(fake_redis, clean_db):
    """Tests POST /v1/ocr/jobs/{id}/retry for failed job."""
    from blast_ocr.core.models import JobState
    from blast_ocr.storage.database import OCRJob
    
    job_id = clean_db.create_job("failed_job.pdf", 1)
    with clean_db.session_scope() as s:
        j = s.query(OCRJob).filter_by(id=job_id).first()
        j.status = JobState.FAILED.value
        j.retry_count = 3
        j.error_message = "Engine crash"
    
    response = client.post(f"/v1/ocr/jobs/{job_id}/retry", json={"priority_override": "high", "reset_retries": True})
    assert response.status_code == 200
    data = response.json()
    assert data["job_id"] == job_id
    assert data["previous_status"] == "failed"
    assert data["new_status"] == "queued"
    assert data["priority"] == "high"


def test_api_retry_rejects_active_job(fake_redis, clean_db):
    """Tests POST /v1/ocr/jobs/{id}/retry returns 400 if job is currently PROCESSING."""
    from blast_ocr.core.models import JobState
    
    job_id = clean_db.create_job("running_job.pdf", 1)
    clean_db.update_job_status(job_id, JobState.PROCESSING)
    
    response = client.post(f"/v1/ocr/jobs/{job_id}/retry")
    assert response.status_code == 400
    assert "cannot be retried" in response.json()["detail"]


def test_api_retry_404_on_missing_job(fake_redis, clean_db):
    """Tests POST /v1/ocr/jobs/{id}/retry returns 404 for non-existent job ID."""
    response = client.post("/v1/ocr/jobs/999999/retry")
    assert response.status_code == 404
```

---

#### Category 7: Edge Cases & Resilience Tests
```python
def test_redis_disconnect_graceful_fallback(monkeypatch, clean_db, tmp_path):
    """Verifies API falls back to degraded sync mode or reports clean error when Redis is down."""
    from blast_ocr.queue.client import is_queue_available
    
    monkeypatch.setattr("blast_ocr.queue.client.get_redis_connection", MagicMock(side_effect=ConnectionError("Redis down")))
    
    assert is_queue_available() is False
    
    # GET /v1/workers should return empty workers list rather than crashing
    resp = client.get("/v1/workers")
    assert resp.status_code == 200
    assert resp.json()["active_workers_count"] == 0


def test_poisoned_payload_dlq_isolation(fake_redis, clean_db):
    """Verifies that corrupted / poisoned payloads in queue are isolated to DLQ without crashing worker loop."""
    from blast_ocr.queue.tasks import handle_poisoned_payload
    
    raw_bad_payload = b"not_valid_json_or_pickle_garbage"
    dlq_item = handle_poisoned_payload(raw_bad_payload, error_reason="DeserializationError")
    
    assert dlq_item["status"] == "quarantined"
    assert dlq_item["error"] == "DeserializationError"


def test_concurrent_worker_dequeue_no_race(fake_redis, clean_db, tmp_path):
    """Verifies that multiple worker dequeue requests on a single item result in exactly-once execution."""
    from blast_ocr.queue.client import QueueClient
    from rq import SimpleWorker
    
    src = tmp_path / "single_task.png"
    src.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 32)
    
    q_client = QueueClient()
    q_client.enqueue_job(str(src), priority="high")
    
    q_high = q_client.get_queue("high")
    assert len(q_high) == 1
    
    # First worker claims
    job1 = q_high.dequeue()
    assert job1 is not None
    
    # Second worker attempts to dequeue empty queue
    job2 = q_high.dequeue()
    assert job2 is None
```

---

## 6. Implementation Blueprint for Implementer (`sub_builder`)

### 6.1 Action Checklist

1. **`blast_ocr/api/schemas.py`**:
   - Add `priority` (Literal["high", "default", "low"]) and `max_retries` (int) to `JobCreateRequest`.
   - Add `priority`, `rq_job_id`, `queue_name` to `JobResponse`.
   - Add `priority`, `retry_count`, `max_retries`, `worker_id`, `queue_name`, `dlq_at`, `dlq_reason` to `JobStatusResponse`.
   - Add `WorkerInfoResponse`, `SwarmStatusResponse`, `QueueStatItem`, `QueuesOverviewResponse`, `JobRetryRequest`, `JobRetryResponse`.

2. **`blast_ocr/api/routes.py`**:
   - Update `create_ocr_job`: accept `priority` and `max_retries` form fields; route through `QueueClient.enqueue_job` when `queue_backend == "redis"`. Pass `job_id=job_id` to `_execute_pipeline_task` in sync fallback.
   - Implement `GET /v1/workers` using `HeartbeatRegistry`.
   - Implement `GET /v1/queues` using `QueueClient.get_queue_statistics`.
   - Implement `POST /v1/ocr/jobs/{job_id}/retry` to allow failed/DLQ job replay.

3. **`tests/test_queue_swarm.py`**:
   - Create comprehensive test suite containing all 25+ tests specified in Section 5.
   - Use `fakeredis` fixture and mock OCR pipeline wrapper for sub-second deterministic execution.

4. **Verification**:
   - Run `python3 -m pytest tests/test_queue_swarm.py` -> 100% PASS.
   - Run `python3 -m pytest tests/test_enterprise_api.py` -> 100% PASS.
   - Verify zero regressions across full test suite.

---

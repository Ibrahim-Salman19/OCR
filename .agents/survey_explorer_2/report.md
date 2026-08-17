# B.L.A.S.T. OCR — Architecture Survey Report: Distributed Multi-Worker Swarm & Durable Queue (Requirement R2)

**Author:** `survey_explorer_2` (Teamwork Explorer / System Architect)  
**Date:** 2026-08-15  
**Milestone:** Phase 0 — Survey & Architectural Decomposition  
**Target:** High-Throughput Distributed Queue & Multi-Worker Swarm Engine  

---

## 1. Executive Summary & Survey Objectives

This survey investigates the B.L.A.S.T. OCR architecture with specific focus on **Requirement R2 (Distributed Multi-Worker Swarm & Durable Queue)**. 

### Core Objectives
1. Map and analyze existing FastAPI service routes, job submission, tracking, in-process background tasks, and current RQ queue plumbing.
2. Determine technical design for an enterprise-grade **Distributed Multi-Worker Swarm** (Redis / RQ worker pool with process supervision).
3. Design **Automated Worker Heartbeats & Health Monitoring** for real-time worker tracking and dead worker / zombie job failover.
4. Design **Dynamic Job Priority Scheduling** (3-tier priority queues: High, Normal/Default, Low) with worker multiplexing and anti-starvation mechanisms.
5. Design **Task Retry with Exponential Backoff & Dead-Letter Queue (DLQ)** with deterministic vs. transient error classification.
6. Design **Concurrency, Idempotency & Distributed Lock Management** to guarantee zero race conditions, double-claiming, or database deadlocks during multi-worker scaling.
7. Enumerate all required features, modules, files, database schema changes, and dependency contracts.

---

## 2. Current Architecture & Codebase Map

### 2.1 Service & API Layer (`blast_ocr/api/`)
- **`blast_ocr/api/app.py`**:
  - Sets up FastAPI app (version 3.0.0), CORS middleware, latency recording middleware (`X-Process-Time-Sec`), global exception handler returning JSON, and root router (`/`).
- **`blast_ocr/api/routes.py`**:
  - `POST /v1/ocr/jobs`: Accepts file upload (`UploadFile`) or disk path (`source_path`).
    - *Observation / Defect Identified*: It creates an `OCRJob` in `OCRDatabase`, marks state as `QUEUED`, but uses FastAPI's in-process `BackgroundTasks` calling `_execute_pipeline_task(...)`.
    - *Defect at Line 42*: `pipeline.process_job(source_path, output_dir=output_dir)` fails to pass `job_id=job_id`, causing `BlastPipeline` to create a *duplicate* secondary job record instead of updating the existing one.
    - *Queue Decoupling*: The API currently bypasses `blast_ocr/queue/client.py` and runs solely in-process. If the FastAPI process restarts or crashes, all in-flight jobs are killed.
  - `GET /v1/ocr/jobs/{job_id}`: Retrieves job status, progress %, average confidence, duration, and error message.
  - `GET /v1/ocr/jobs/{job_id}/results`: Checks output directory for `.md`, `.docx`, `.pdf`, `.epub`, `.txt`, `.json` and returns generated file paths.
  - `GET /v1/ocr/jobs/{job_id}/download/{fmt}`: Streams output artifact directly to client using `FileResponse`.
  - `GET /v1/ocr/jobs/{job_id}/stream`: SSE endpoint (`text/event-stream`) polling DB every 0.5s for 60 iterations (30s max duration).
  - `GET /v1/ocr/jobs/{job_id}/toc` & `/v1/ocr/jobs/{job_id}/chunks`: Hierarchical Table of Contents and Semantic RAG chunking.
  - `GET /v1/health`: Checks DB liveness, memory usage (`psutil`), storage backend, and registered OCR engines.
  - `GET /v1/metrics`: Serves Prometheus metrics.
  - `GET /v1/config`: Serves active runtime configuration.

### 2.2 Existing Queue Subsystem (`blast_ocr/queue/`)
- **`blast_ocr/queue/client.py`**:
  - `get_redis_connection()`: Connects to Redis via `config.redis_url` (default `redis://localhost:6379/0`).
  - `is_queue_available()`: Health check pinging Redis.
  - `get_queue(name)`: Returns `rq.Queue(name, connection=...)` (default queue: `"blast_ocr_jobs"`).
  - `enqueue_job()`: Creates a DB job record (`status="received"`), calculates SHA-256 fingerprint, and enqueues `run_ocr_job` to RQ.
- **`blast_ocr/queue/tasks.py`**:
  - `run_ocr_job(source_path, output_dir, job_id, config_overrides)`: Module-level RQ task that invokes `BlastPipeline(config_overrides=...).process_job(source_path, output_dir, job_id=job_id)`.
- **`blast_ocr/queue/worker.py`**:
  - `main()`: Instantiates single `rq.Worker([queue])` and runs `worker.work(with_scheduler=False)`.
- **Gaps in Current Queue**:
  1. Single queue name (`blast_ocr_jobs`); no priority tiers (`high`, `default`, `low`).
  2. No automated worker heartbeat registration in Redis or DB.
  3. No supervisor / swarm manager to launch, monitor, scale, and gracefully drain multiple worker processes.
  4. No exponential backoff retry scheduler; failed tasks fail immediately.
  5. No Dead-Letter Queue (DLQ) routing or DLQ replay/management API.
  6. File access assumes shared local disk between API and Worker nodes.

### 2.3 Storage, State Machine & Database Layer (`blast_ocr/storage/`, `blast_ocr/core/job_state.py`)
- **`blast_ocr/storage/database.py`**:
  - SQLAlchemy ORM with `scoped_session(scopefunc=threading.get_ident)`.
  - Tables: `ocr_jobs` (id, filename, page_count, status, created_at, completed_at, error_message), `ocr_results`, `ocr_metrics`.
  - SQLite WAL mode with `BEGIN IMMEDIATE` connection pragma (`isolation_level="IMMEDIATE"`, `timeout=30`) preventing SQLite shared lock deadlocks.
  - Lifecycle management: `purge_old_data(days=7)`.
  - Missing columns for distributed swarm: `priority`, `retry_count`, `max_retries`, `worker_id`, `started_at`, `updated_at`, `fingerprint`, `dlq_reason`, `dlq_at`.
- **`blast_ocr/core/job_state.py`**:
  - `JobStateMachine`: Strict state validation (`RECEIVED` -> `VALIDATING` -> `QUEUED` -> `PROCESSING` -> `POST_PROCESSING` -> `EXPORTING` -> `SUCCEEDED` / `SUCCEEDED_WITH_WARNINGS` / `FAILED` / `CANCELLED` / `QUARANTINED` / `TIMED_OUT`).
  - `classify_exception(exc)`: Differentiates transient errors (`OCREngineError`, `TimeoutError`, `ConnectionError`, `MemoryError`, `WorkerLostError`) from deterministic input errors (`SecurityValidationError`, `ValueError`, `FileNotFoundError`, `UnsupportedPDFError`, `EncryptedPDFError`, `InvalidDocumentError`).

### 2.4 Existing Concurrency Primitives (`blast_ocr/core/worker.py`, `parallel.py`, `extractor.py`)
- **`blast_ocr/core/extractor.py`**: Module-level singleton `_ocr_global_lock = threading.Lock()` serializing EasyOCR calls within a single process.
- **`blast_ocr/core/worker.py`**: Double-checked locking `_worker_init_lock` for extractor and `EngineRegistry._lock` for thread-safe engine creation.
- **`blast_ocr/core/parallel.py`**: `ParallelOCRProcessor` managing thread pool (capped at 2 workers per job to prevent RAM explosion).
- **Process Isolation Advantage**: Distributed worker processes run in separate OS address spaces; each worker process has its own ONNX Runtime / RapidOCR / EasyOCR instances, completely bypassing Python GIL constraints and eliminating thread lock contention across workers.

---

## 3. Technical Design for Requirement R2

```
+---------------------------------------------------------------------------------------------------+
|                                       FASTAPI REST API LAYER                                      |
|  POST /v1/ocr/jobs (priority: high/normal/low) | GET /v1/ocr/jobs/{id} | GET /v1/workers | GET /v1/queues |
+-------------------------------------------------+-------------------------------------------------+
                                                  | Enqueue with Priority & Lock Guard
                                                  v
+---------------------------------------------------------------------------------------------------+
|                                      REDIS DURABLE QUEUE & BROKER                                 |
|  +--------------------------+  +--------------------------+  +--------------------------+         |
|  |   blast_ocr:queue:high   |  |  blast_ocr:queue:default |  |   blast_ocr:queue:low    |         |
|  +--------------------------+  +--------------------------+  +--------------------------+         |
|  +--------------------------------------------------------------------------------------+         |
|  |  Delayed / Retry ZSET: blast_ocr:delayed_jobs  |  Dead Letter Queue: blast_ocr:queue:dlq     | |
|  |  Worker Heartbeat Registry: blast_ocr:workers:active, blast_ocr:worker:<id>          |         |
|  |  Deduplication Locks: blast_ocr:lock:fingerprint:<sha256> (TTL 600s)                 |         |
|  +--------------------------------------------------------------------------------------+         |
+-------------------------------------------------+-------------------------------------------------+
                                                  | Priority Multiplex Dequeue [high, default, low]
                                                  v
+---------------------------------------------------------------------------------------------------+
|                                  DISTRIBUTED MULTI-WORKER SWARM                                   |
|  +------------------------------+  +------------------------------+  +--------------------------+ |
|  |        Swarm Worker 1        |  |        Swarm Worker 2        |  |      Swarm Worker N      | |
|  |  - Heartbeat Daemon (5s)     |  |  - Heartbeat Daemon (5s)     |  |  - Heartbeat Daemon (5s) | |
|  |  - ONNX / GPU Engine Model   |  |  - ONNX / GPU Engine Model   |  |  - ONNX / GPU Engine Model| |
|  |  - Object Storage Sync       |  |  - Object Storage Sync       |  |  - Object Storage Sync   | |
|  +------------------------------+  +------------------------------+  +--------------------------+ |
+-------------------------------------------------+-------------------------------------------------+
                                                  | Progress Updates / Results Persistence
                                                  v
+---------------------------------------------------------------------------------------------------+
|                                   STORAGE & PERSISTENCE LAYER                                     |
|  - Relational Database (PostgreSQL / SQLite WAL): ocr_jobs, ocr_results, ocr_metrics              |
|  - Object Storage (MinIO / S3 / Local): Ingested Documents, Export Bundles, Run Manifests         |
|  - Prometheus Observability: Worker count, Queue depths, Job latencies, DLQ totals                |
+---------------------------------------------------------------------------------------------------+
```

---

### 3.1 Distributed Multi-Worker Swarm Architecture

#### 1. Worker Swarm Process Model (`blast_ocr/queue/swarm.py`, `blast_ocr/queue/worker.py`)
- **`SwarmWorker`**:
  - Subclasses / wraps RQ `Worker` to listen across multiple priority queues simultaneously.
  - Generates unique worker identity: `worker:{hostname}:{pid}:{uuid4_hex[:8]}`.
  - Spawns a background **Heartbeat Daemon** thread upon initialization.
  - Hooks into task pre-execution (`job.meta['worker_id'] = worker_id`, updates DB `started_at`, `worker_id`) and post-execution.
  - Automatically handles S3/MinIO payload staging if worker runs on a separate node without shared filesystem.
- **`SwarmSupervisor` / `WorkerSwarmManager`**:
  - Multi-process manager capable of spawning and monitoring $N$ worker processes (e.g. `SwarmSupervisor(worker_count=4)`).
  - Listens for OS process exit codes; if a worker crashes (OOM, segfault, unhandled signal), the supervisor immediately respawns a fresh worker to maintain target swarm capacity.
  - Handles `SIGTERM` and `SIGINT`: signals all child workers to initiate graceful draining (`status="draining"`), finishes in-flight pages within a configurable grace period (e.g. 30s), and unregisters cleanly.

#### 2. Swarm CLI Entrypoint
```bash
# Start a multi-worker swarm with 4 parallel worker processes
python -m blast_ocr.queue.swarm --workers 4 --queues high,default,low --heartbeat-interval 5

# Start a single dedicated worker for high-priority jobs only (e.g., dedicated fast node)
python -m blast_ocr.queue.worker --worker-id fast-node-1 --queues high
```

---

### 3.2 Automated Worker Heartbeats & Health Monitoring

#### 1. Worker Registration Schema (Redis)
- **Active Workers Set**: `blast_ocr:workers:active` (Redis Set containing active `worker_id`s).
- **Worker Metadata Hash**: `blast_ocr:worker:<worker_id>` with TTL (e.g., 20 seconds):
  ```json
  {
    "worker_id": "worker:worker-node-1:48201:9a8f12bc",
    "hostname": "worker-node-1",
    "pid": 48201,
    "started_at": "2026-08-15T14:50:00Z",
    "last_heartbeat": 1786805400.12,
    "status": "busy",  // "idle" | "busy" | "draining" | "offline"
    "current_job_id": 142,
    "current_page": 12,
    "total_pages": 50,
    "memory_rss_mb": 420.5,
    "cpu_percent": 18.2,
    "queues": ["blast_ocr:queue:high", "blast_ocr:queue:default", "blast_ocr:queue:low"],
    "jobs_processed_total": 48,
    "jobs_failed_total": 1
  }
  ```

#### 2. Heartbeat Daemon Thread (`blast_ocr/queue/heartbeat.py`)
- Lightweight daemon thread executing in each `SwarmWorker` process every `heartbeat_interval_sec` (default: 5.0s).
- Uses Redis pipeline to execute:
  1. `HSET blast_ocr:worker:<worker_id> ...`
  2. `EXPIRE blast_ocr:worker:<worker_id> 20`
  3. `SADD blast_ocr:workers:active <worker_id>`
  4. Updates Prometheus gauge: `blast_worker_memory_bytes.labels(worker_id=...).set(rss_bytes)`.

#### 3. Zombie Job Reaper & Health Monitor (`blast_ocr/queue/reaper.py`)
- Standalone or background supervisor task running every `reap_interval_sec` (default: 15.0s).
- **Failure Detection Logic**:
  1. Iterate over all members of `blast_ocr:workers:active`.
  2. Check if key `blast_ocr:worker:<worker_id>` exists.
  3. If key expired or `time.time() - last_heartbeat > heartbeat_ttl` (20s):
     - Remove worker from active set: `SREM blast_ocr:workers:active <worker_id>`.
     - Log warning: `Worker <worker_id> lost (heartbeat timeout)`.
     - Check if worker had an active job assigned:
       - If `current_job_id` is set: query DB `ocr_jobs` for job state.
       - If job is in `PROCESSING` state: mark failed with `WorkerLostError("Worker died unexpectedly during execution")`.
       - Execute Retry / DLQ policy: if `retry_count < max_retries`, re-enqueue to priority queue with backoff; otherwise push to DLQ.
       - Increment Prometheus metric: `blast_worker_failures_total.inc()`.

---

### 3.3 Dynamic Job Priority Scheduling

#### 1. Three-Tier Priority Queues
| Priority Tier | Queue Name | Intended Workload | SLA Target |
| :--- | :--- | :--- | :--- |
| **`HIGH`** (1) | `blast_ocr:queue:high` | Single-page scans, interactive UI uploads, urgent re-evaluations | < 1.0s page latency |
| **`DEFAULT` / `NORMAL`** (2) | `blast_ocr:queue:default` | Standard multi-page documents (10–100 pages) | High throughput batching |
| **`LOW`** (3) | `blast_ocr:queue:low` | Bulk archival jobs, 1,000+ page books, background backfills | Bounded background execution |

#### 2. Worker Multiplexing & Consumption Order
- Workers consume queues using strict left-to-right priority:
  `worker = SwarmWorker([queue_high, queue_default, queue_low], connection=redis_conn)`
- Redis `BLPOP` / RQ dequeue guarantees that any pending item on `blast_ocr:queue:high` will *always* be fetched before any item on `blast_ocr:queue:default`, which is always fetched before `blast_ocr:queue:low`.

#### 3. Anti-Starvation Dynamic Promotion
- For large workloads where high-priority jobs arrive continuously, low-priority jobs could theoretically experience starvation.
- **Dynamic Escalation Policy**:
  - A scheduled scanner checks `blast_ocr:queue:low` jobs.
  - If a job has been waiting in queue longer than `max_wait_seconds` (e.g. 300 seconds), it is atomically moved from `blast_ocr:queue:low` to `blast_ocr:queue:default`.

---

### 3.4 Task Retry with Exponential Backoff & Dead-Letter Queue (DLQ)

#### 1. Failure Taxonomy & Exception Classification
Reuses and extends `blast_ocr/core/job_state.py:classify_exception(exc)`:
- **Transient / Retryable Errors**:
  - `OCREngineError`: Temporary ONNX Runtime or GPU allocation failure.
  - `TimeoutError` / `ConnectionError`: Transient Redis, DB, or Object Storage network blip.
  - `WorkerLostError`: Worker process killed or node terminated.
  - `MemoryError`: Transient host memory pressure.
  - *Action*: Retry with exponential backoff.
- **Deterministic / Non-Retryable Errors**:
  - `SecurityValidationError`: Magic byte mismatch, file size exceeded, malicious extension.
  - `UnsupportedPDFError` / `EncryptedPDFError`: Password-protected or corrupt PDF.
  - `InvalidDocumentError`: Zero bytes, unparseable image header.
  - `ValueError` / `FileNotFoundError`: Invalid parameters.
  - *Action*: Fail immediately, DO NOT retry; transition directly to `FAILED` / `QUARANTINED`.

#### 2. Exponential Backoff Algorithm with Jitter
When a transient failure occurs on attempt $k$ (where $1 \le k \le \text{max\_retries}$):
$$\text{delay} = \min\left(\text{max\_backoff},\; \text{base\_delay} \times (\text{backoff\_factor})^{k-1}\right) + \text{uniform}(0, \text{jitter\_max})$$
- Default settings: `base_delay = 2.0s`, `backoff_factor = 2.0`, `max_backoff = 60.0s`, `jitter_max = 1.0s`.
- Attempt 1 failure $\rightarrow$ Retry scheduled in $\approx 2.0\text{s} - 3.0\text{s}$.
- Attempt 2 failure $\rightarrow$ Retry scheduled in $\approx 4.0\text{s} - 5.0\text{s}$.
- Attempt 3 failure $\rightarrow$ Retry scheduled in $\approx 8.0\text{s} - 9.0\text{s}$.
- RQ supports scheduled retry via `Retry(max=3, backoff=[2, 4, 8])` or Redis Sorted Set delayed execution.

#### 3. Dead-Letter Queue (DLQ) Architecture
- When `retry_count >= max_retries` (or upon non-retryable error):
  1. Job payload is moved to `blast_ocr:queue:dlq`.
  2. Database `OCRJob` status is set to `JobState.FAILED.value` with `error_message = f"Exhausted {max_retries} retries. Last error: {last_exc}"`.
  3. `OCRJob.dlq_at = datetime.utcnow()` and `OCRJob.dlq_reason = str(last_exc)`.
  4. Prometheus metric is incremented: `blast_dlq_jobs_total.labels(reason=exc_type).inc()`.
  5. Telemetry event is published: `{"event": "job_sent_to_dlq", "job_id": job_id, "retry_count": k, "error": str(last_exc)}`.

#### 4. DLQ Inspection & Replay API
- `GET /v1/queues/dlq`: Lists all jobs currently in the Dead-Letter Queue with full stack trace, failure timestamp, and original parameters.
- `POST /v1/ocr/jobs/{job_id}/retry`: Replays a failed or DLQ job:
  - Resets `retry_count = 0`, clears `error_message`.
  - Transitions state `FAILED -> QUEUED`.
  - Re-enqueues into `blast_ocr:queue:high` (or specified priority queue).

---

### 3.5 Concurrency, Idempotency & Distributed Lock Management

#### 1. Atomic Dequeue (Zero Race Conditions)
- Multi-worker pools pulling from Redis use atomic operations (`BLPOP` / `BRPOPLPUSH` / RQ connection leases).
- Guarantees that even with 50 concurrent worker processes, exactly one worker claims a job; zero risk of duplicate execution.

#### 2. Distributed Idempotency Guard (Deduplication Lock)
- When a document is submitted, calculate its deterministic SHA-256 fingerprint:
  `fingerprint = JobFingerprint.compute(input_sha256, job_config)`
- Acquire an atomic Redis lease:
  `SET blast_ocr:lock:fingerprint:<fingerprint> <job_id> NX EX 600`
- **Behavior**:
  - If key did not exist: Lock acquired, proceed with enqueue.
  - If key already exists: Another worker/request is actively processing the identical file with identical parameters. Return the existing `job_id` and status `queued`/`processing`, preventing redundant GPU/CPU compute.

#### 3. Database Concurrency & Connection Pooling
- **PostgreSQL / MySQL (Production Multi-Host)**:
  - Configure SQLAlchemy engine with `pool_size=20`, `max_overflow=40`, `pool_pre_ping=True`, and short, scoped transactions (`session_scope()`).
- **SQLite (Local / Embedded)**:
  - Enforce WAL mode (`PRAGMA journal_mode=WAL`) and `BEGIN IMMEDIATE` transactions (already validated in `test_concurrency_advanced.py`) to prevent SHARED lock deadlocks during concurrent worker writes.

#### 4. Multi-Host Object Storage Integration
- In multi-node swarms where worker processes run on separate hosts without a shared network filesystem:
  - Client / API uploads input document to `ObjectStorage` (`blast-ocr-artifacts/jobs/{job_id}/source.pdf`).
  - Job payload in Redis contains `{ "job_id": 101, "storage_key": "jobs/101/source.pdf" }`.
  - Worker node downloads the document via `ObjectStorage.get()`, processes it locally in temporary scratch space, and uploads all output artifacts (`ExportBundle`, `RunManifest`) back to `ObjectStorage.put()`.
  - Cleans up local worker scratch files immediately after upload.

---

## 4. REST API Endpoints & Interface Contracts Specification

### 4.1 Enhanced & New API Routes

```
+---------------------------------------------------------------------------------------------------------+
| ROUTE                            | METHOD | DESCRIPTION                                                 |
+----------------------------------+--------+-------------------------------------------------------------+
| /v1/ocr/jobs                     | POST   | Submits document for async processing with priority & retry |
| /v1/ocr/jobs/{job_id}            | GET    | Retrieves live job status, progress, worker_id, priority    |
| /v1/ocr/jobs/{job_id}/results    | GET    | Retrieves generated output artifacts and summary            |
| /v1/ocr/jobs/{job_id}/download/{fmt}| GET | Streams output artifact (.md, .docx, .pdf, .epub, .txt)    |
| /v1/ocr/jobs/{job_id}/stream     | GET    | SSE stream tracking real-time job progress & page events    |
| /v1/ocr/jobs/{job_id}/retry      | POST   | Retries or replays a failed / DLQ job with reset counter    |
| /v1/ocr/jobs/{job_id}/cancel     | POST   | Cancels a queued or in-flight job                           |
| /v1/workers                      | GET    | Lists all active swarm workers, heartbeats, and metrics     |
| /v1/queues                       | GET    | Summarizes queue depths (high, default, low, dlq)           |
| /v1/queues/dlq                   | GET    | Lists dead-lettered jobs with failure diagnostics           |
| /v1/health                       | GET    | Liveness & readiness probe (DB, Redis, Swarm, Storage)      |
| /v1/metrics                      | GET    | Prometheus metrics endpoint                                 |
+---------------------------------------------------------------------------------------------------------+
```

### 4.2 Pydantic Schemas (`blast_ocr/api/schemas.py`)

```python
from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any
from datetime import datetime

class JobCreateRequest(BaseModel):
    source_path: Optional[str] = None
    output_dir: Optional[str] = None
    ocr_engine: str = Field("rapidocr", description="rapidocr, easyocr, tesseract, ensemble")
    priority: str = Field("default", description="high, default, low")
    max_retries: int = Field(3, ge=0, le=10, description="Max retry attempts for transient failures")
    auto_deskew: bool = True
    denoise_level: int = 0
    contrast_boost: float = 1.0
    enable_tier0_routing: bool = True
    enable_book_intelligence: bool = True
    secure_mode: bool = False
    max_workers: int = 2
    formats: List[str] = Field(default_factory=lambda: ["markdown", "docx", "pdf", "txt", "epub", "json"])

class JobResponse(BaseModel):
    job_id: int
    status: str
    priority: str
    source_path: str
    rq_job_id: Optional[str] = None
    created_at: datetime
    message: str

class JobStatusResponse(BaseModel):
    job_id: int
    status: str
    priority: str
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

class WorkerInfoResponse(BaseModel):
    worker_id: str
    hostname: str
    pid: int
    started_at: str
    last_heartbeat: float
    status: str  # idle, busy, draining, offline
    current_job_id: Optional[int] = None
    current_page: Optional[int] = None
    total_pages: Optional[int] = None
    memory_rss_mb: float
    cpu_percent: float
    queues: List[str]
    jobs_processed_total: int
    jobs_failed_total: int

class SwarmHealthResponse(BaseModel):
    active_workers_count: int
    busy_workers_count: int
    idle_workers_count: int
    workers: List[WorkerInfoResponse]

class QueueDepthResponse(BaseModel):
    high_priority_depth: int
    default_priority_depth: int
    low_priority_depth: int
    dlq_depth: int
    scheduled_retry_depth: int
```

---

## 5. Required Modules, Files & Database Migrations

### 5.1 New & Modified Files Inventory

| File Path | Action | Purpose / Responsibilities |
| :--- | :--- | :--- |
| `blast_ocr/queue/client.py` | Modify | Multi-queue support (`get_queue(priority)`), priority enqueue, retry policy, deduplication locking |
| `blast_ocr/queue/worker.py` | Modify | Multi-queue listening (`high`, `default`, `low`), heartbeat integration, graceful draining |
| `blast_ocr/queue/tasks.py` | Modify | `run_ocr_job` with worker heartbeat reporting, retry classification, DLQ pushing, storage sync |
| `blast_ocr/queue/heartbeat.py` | **Create** | Background worker heartbeat daemon and Redis status updater |
| `blast_ocr/queue/reaper.py` | **Create** | Swarm health scanner, zombie job reaper, and automatic failover handler |
| `blast_ocr/queue/swarm.py` | **Create** | CLI & Swarm supervisor to launch, manage, and scale $N$ worker processes |
| `blast_ocr/api/routes.py` | Modify | Wire `/v1/ocr/jobs` to priority queues; add `/v1/workers`, `/v1/queues`, `/v1/ocr/jobs/{id}/retry` |
| `blast_ocr/api/schemas.py` | Modify | Add priority, retry, worker info, and queue depth schemas |
| `blast_ocr/storage/database.py` | Modify | Add `priority`, `retry_count`, `max_retries`, `worker_id`, `started_at`, `dlq_at` to `OCRJob` |
| `blast_ocr/storage/alembic/versions/002_swarm_and_priority.py` | **Create** | Database migration adding priority, retry, and worker columns |
| `blast_ocr/config.py` | Modify | Add `swarm_workers`, `heartbeat_interval`, `max_retries`, `retry_backoff_factor` |
| `tests/test_swarm_and_queue.py` | **Create** | Comprehensive integration tests for multi-worker swarm, priority, retry backoff, and DLQ |

### 5.2 Database Schema Migration (`002_swarm_and_priority.py`)
```python
"""add swarm, priority, retry, and dlq columns to ocr_jobs

Revision ID: 002_swarm_and_priority
Revises: 001_initial_schema
Create Date: 2026-08-15
"""
from alembic import op
import sqlalchemy as sa

def upgrade():
    op.add_column("ocr_jobs", sa.Column("priority", sa.String(20), server_default="default", nullable=False))
    op.add_column("ocr_jobs", sa.Column("retry_count", sa.Integer(), server_default="0", nullable=False))
    op.add_column("ocr_jobs", sa.Column("max_retries", sa.Integer(), server_default="3", nullable=False))
    op.add_column("ocr_jobs", sa.Column("worker_id", sa.String(100), nullable=True))
    op.add_column("ocr_jobs", sa.Column("queue_name", sa.String(50), nullable=True))
    op.add_column("ocr_jobs", sa.Column("started_at", sa.DateTime(), nullable=True))
    op.add_column("ocr_jobs", sa.Column("dlq_at", sa.DateTime(), nullable=True))
    op.add_column("ocr_jobs", sa.Column("dlq_reason", sa.Text(), nullable=True))
    op.create_index("idx_ocr_jobs_priority_status", "ocr_jobs", ["priority", "status"])

def downgrade():
    op.drop_index("idx_ocr_jobs_priority_status", "ocr_jobs")
    op.drop_column("ocr_jobs", "dlq_reason")
    op.drop_column("ocr_jobs", "dlq_at")
    op.drop_column("ocr_jobs", "started_at")
    op.drop_column("ocr_jobs", "queue_name")
    op.drop_column("ocr_jobs", "worker_id")
    op.drop_column("ocr_jobs", "max_retries")
    op.drop_column("ocr_jobs", "retry_count")
    op.drop_column("ocr_jobs", "priority")
```

---

## 6. Prometheus Metrics & Observability (`blast_ocr/telemetry.py`)

New Prometheus metrics for Requirement R2:
- `blast_active_workers` (Gauge, labels: `[hostname, status]`): Total active swarm workers.
- `blast_queue_depth` (Gauge, labels: `[queue_name, priority]`): Pending jobs count per queue.
- `blast_job_retries_total` (Counter, labels: `[engine, retry_attempt]`): Total retries performed.
- `blast_dlq_jobs_total` (Counter, labels: `[reason]`): Total jobs sent to Dead-Letter Queue.
- `blast_worker_failures_total` (Counter, labels: `[hostname]`): Dead workers detected by reaper.
- `blast_worker_heartbeat_seconds` (Gauge, labels: `[worker_id]`): Seconds since last heartbeat.

---

## 7. Implementation Recommendations & Safety Guidelines

1. **Zero-Regression Guarantee**:
   - The default configuration must remain `queue_backend="sync"` so that local CLI and simple runs require no Redis server.
   - When `queue_backend="redis"`, the system activates the multi-worker swarm and priority queues.
   - If Redis becomes unreachable, the system gracefully logs a degraded warning and falls back to synchronous processing.
2. **Deterministic Locking**:
   - Avoid distributed deadlock hazards: use short TTLs on Redis locks (e.g. 600s) and avoid holding DB transactions across long OCR model execution steps.
3. **Clean Process Lifecycle**:
   - Swarm supervisor must use `multiprocessing` with explicit exit code handling and SIGTERM forwarding to avoid orphan / zombie processes on Linux and Windows.
4. **Test Strategy**:
   - Add unit tests with `fakeredis` for CI/environments without Redis.
   - Add real integration tests with live `redis-server` when available.

---

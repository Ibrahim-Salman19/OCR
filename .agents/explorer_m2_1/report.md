# Milestone 2 Technical Exploration & Design Report: Distributed Multi-Worker Swarm & Durable Queue

**Author:** Explorer 1 (Milestone 2)  
**Date:** 2026-08-15  
**Scope Reference:** `.agents/sub_orch_m2/SCOPE.md`  
**System Target:** B.L.A.S.T. OCR Distributed Queue & Worker Swarm Engine  

---

## 1. Executive Summary & Problem Scope

Milestone 2 transforms B.L.A.S.T. OCR from single-node/in-process background execution into an enterprise-grade, distributed, fault-tolerant execution engine.

### Key Requirements (R2)
1. **3-Tier Priority Queue Scheduling**: Strict multi-tier queues (`high`, `default`, `low`) plus Dead Letter Queue (`dlq`) with worker priority multiplexing.
2. **Multi-Worker Swarm Supervision**: Multi-process worker supervisor (`SwarmSupervisor`) managing worker pools across CPU/GPU resources, monitoring process liveness, auto-recovering crashed workers, and supporting graceful draining.
3. **Automated Heartbeats & Worker Telemetry**: Dedicated `HeartbeatDaemon` in every worker process, periodically updating worker health (CPU, RSS memory, current job, active page) with Redis TTL leases and active sets.
4. **Zombie Job Reaper & Automatic Failover**: Dedicated `ZombieReaper` detecting stale/dead worker keys, recovering orphaned in-flight jobs, re-enqueuing retryable tasks, and routing exhausted tasks to DLQ.
5. **Exponential Backoff Retry & DLQ Quarantine**: Error-classified retry policy (transient vs deterministic errors), exponential backoff with jitter, and dead-letter quarantine for exhausted retries.
6. **FastAPI Endpoints**: `/v1/ocr/jobs` with priority dispatch, `/v1/workers` swarm health monitoring, `/v1/queues` queue depth metrics, and `/v1/ocr/jobs/{id}/retry` DLQ replay.
7. **Production Database & Migrations**: Schema updates to `ocr_jobs` (`priority`, `retry_count`, `max_retries`, `worker_id`, `started_at`, `dlq_at`, `dlq_reason`) with SQLite batch-safe Alembic migration (`002_swarm_and_priority.py`).

---

## 2. Environment & Existing Codebase Verification

### 2.1 Dependencies & Environment Audit
- **`redis`**: `8.1.0` (Installed & operational)
- **`rq`**: `2.10.0` (Installed & operational)
- **`fakeredis`**: `2.37.0` (Installed & operational)
- **Local Redis Server**: Running on `redis://localhost:6379/0`
- **Existing Queue Tests**: `tests/test_queue.py` passes 3/3 tests against live Redis (`test_redis_reachable`, `test_enqueue_creates_db_job_and_rq_job`, `test_worker_processes_queued_job_end_to_end`).
- **Alembic Migration System**: `tests/test_alembic_migration.py` passes 3/3 tests verifying clean schema bootstrapping and migration compatibility.

### 2.2 Existing Flow Analysis & Defects Identified
1. **API Job Submission (`blast_ocr/api/routes.py`)**:
   - Currently, `POST /v1/ocr/jobs` uses FastAPI's `BackgroundTasks.add_task(_execute_pipeline_task)`. If the API process restarts or crashes, all in-flight jobs are abruptly lost.
   - **Critical Bug at Line 42**: `_execute_pipeline_task` invokes `pipeline.process_job(source_path, output_dir=output_dir)` without passing `job_id=job_id`. This causes `BlastPipeline` to create a *duplicate* secondary job record in the database instead of updating the existing `job_id`.
   - **Queue Decoupling**: API currently has no logic to check `config.queue_backend == "redis"` or dispatch to `blast_ocr.queue.client.enqueue_job`.
2. **Current Queue Module (`blast_ocr/queue/`)**:
   - `client.py`: Has only a single queue (`"blast_ocr_jobs"`), no priority support, no retry configuration, no DLQ handling.
   - `worker.py`: Runs a single RQ `Worker([queue])` with no heartbeat registration, no multi-queue listening, and no supervisor management.
   - `tasks.py`: Invokes `BlastPipeline.process_job` with basic logging; lacks retry backoff, exception classification, DLQ quarantine, and heartbeat progress callbacks.
3. **Database Schema (`blast_ocr/storage/database.py`)**:
   - `OCRJob` model is currently missing distributed execution columns: `priority`, `retry_count`, `max_retries`, `worker_id`, `queue_name`, `started_at`, `dlq_at`, `dlq_reason`.
4. **State Machine (`blast_ocr/core/job_state.py`)**:
   - Already provides robust `JobStateMachine` and `classify_exception(exc)` classifying `RetryableJobError` vs `NonRetryableJobError`. This must be leveraged by `tasks.py` and `reaper.py`.

---

## 3. Comprehensive Technical Design

```
+---------------------------------------------------------------------------------------------------------+
|                                           FASTAPI REST API                                              |
|   POST /v1/ocr/jobs (priority: high/default/low)  |  GET /v1/workers  |  GET /v1/queues  |  POST retry  |
+----------------------------------------------------+----------------------------------------------------+
                                                     |
                 +-----------------------------------+-----------------------------------+
                 | queue_backend == "redis"                                              | queue_backend == "sync"
                 v                                                                       v
+--------------------------------------------------+                   +----------------------------------+
|            REDIS / RQ DURABLE BROKER             |                   |       In-Process Execution       |
|  - blast_ocr:queue:high                          |                   |  - Immediate pipeline execution  |
|  - blast_ocr:queue:default                       |                   |  - Single-node / test fallback   |
|  - blast_ocr:queue:low                           |                   +----------------------------------+
|  - blast_ocr:queue:dlq                           |
|  - blast_ocr:delayed_jobs (retry ZSET)           |
|  - blast_ocr:workers:active (Set)                |
|  - blast_ocr:worker:<id> (Hash with TTL)         |
|  - blast_ocr:lock:fingerprint:<hash> (TTL lock)  |
+--------------------------------------------------+
                 |
                 | Atomic Dequeue [high, default, low]
                 v
+---------------------------------------------------------------------------------------------------------+
|                                      DISTRIBUTED MULTI-WORKER SWARM                                     |
|  +-------------------------------------+         +-------------------------------------+                |
|  |           Swarm Worker 1            |         |           Swarm Worker N            |                |
|  | - Process isolated (ONNX / EasyOCR) |         | - Process isolated (ONNX / EasyOCR) |                |
|  | - HeartbeatDaemon (5s interval)     | <=====> | - HeartbeatDaemon (5s interval)     |                |
|  | - Progress callback hooks           |         | - Progress callback hooks           |                |
|  +-------------------------------------+         +-------------------------------------+                |
|                                                     ^                                                   |
|  +-----------------------------------------------+  | Supervises & Auto-Restarts                        |
|  |     SwarmSupervisor (Multi-Process Mgr)       |--+                                                   |
|  |     + ZombieReaper (Stale Worker Failover)    |                                                      |
|  +-----------------------------------------------+                                                      |
+---------------------------------------------------------------------------------------------------------+
                                                     |
                                                     v
+---------------------------------------------------------------------------------------------------------+
|                                      STORAGE & TELEMETRY LAYER                                          |
|  - SQLAlchemy DB (WAL mode / PostgreSQL): ocr_jobs (with worker_id, priority, retry_count, dlq_reason)  |
|  - Prometheus Observability: blast_active_workers, blast_queue_depth, blast_job_retries_total, dlq      |
+---------------------------------------------------------------------------------------------------------+
```

---

## 4. Detailed Component Design & Specifications

### 4.1 `blast_ocr/queue/client.py` (Queue Client & Multi-Tier Priority Dispatch)
- **Priority Constants**:
  ```python
  QUEUE_HIGH = "blast_ocr:queue:high"
  QUEUE_DEFAULT = "blast_ocr:queue:default"
  QUEUE_LOW = "blast_ocr:queue:low"
  QUEUE_DLQ = "blast_ocr:queue:dlq"
  PRIORITY_MAP = {
      "high": QUEUE_HIGH,
      "default": QUEUE_DEFAULT,
      "normal": QUEUE_DEFAULT,
      "low": QUEUE_LOW,
      "dlq": QUEUE_DLQ,
  }
  ```
- **Connection Management**:
  - `get_redis_connection(url: Optional[str] = None)`: Connects using `config.redis_url` or test override.
  - `is_queue_available() -> bool`: Pings Redis; returns False if unreachable.
- **Queue Accessors**:
  - `get_queue(priority_or_name: str = "default", connection=None) -> rq.Queue`: Normalizes priority and returns `rq.Queue(name, connection=conn)`.
  - `get_all_queues(connection=None) -> List[rq.Queue]`: Returns `[get_queue("high"), get_queue("default"), get_queue("low")]` in priority order.
  - `get_queue_depths(connection=None) -> Dict[str, int]`: Returns depths for `"high"`, `"default"`, `"low"`, `"dlq"`.
- **Job Enqueueing**:
  - `enqueue_job(source_path, output_dir=None, input_sha256=None, config_overrides=None, priority="default", max_retries=3, connection=None) -> Dict[str, Any]`:
    - Checks deduplication lock: `SET blast_ocr:lock:fingerprint:<fingerprint> <job_id> NX EX 600`.
    - If lock exists, returns existing job record without re-enqueueing duplicate compute.
    - Creates DB record in `OCRJob` with `status=JobState.QUEUED.value`, `priority=priority`, `max_retries=max_retries`, `queue_name=queue_name`.
    - Enqueues `blast_ocr.queue.tasks.run_ocr_job` to the target priority queue with RQ `job_timeout=config.queue_job_timeout`, `retry=...`.
    - Returns `{"job_id": job_id, "rq_job_id": rq_job.id, "priority": priority, "fingerprint": fingerprint}`.
- **Retry & DLQ Replay**:
  - `retry_job(job_id: int, priority: Optional[str] = None, connection=None) -> Dict[str, Any]`:
    - Resets `retry_count = 0`, clears `error_message`, sets `status = JobState.QUEUED.value`.
    - Re-enqueues into priority queue.
  - `get_dlq_jobs(connection=None, limit=100) -> List[Dict[str, Any]]`:
    - Queries jobs currently in DLQ state or queue.

---

### 4.2 `blast_ocr/queue/heartbeat.py` (Heartbeat Daemon & Active Worker Registry)
- **`HeartbeatDaemon` Class**:
  - Encapsulates background daemon thread per worker.
  - **Attributes**: `worker_id`, `hostname`, `pid`, `started_at`, `interval` (5.0s), `ttl` (20.0s), `status` ("idle" | "busy" | "draining" | "offline"), `current_job_id`, `current_page`, `total_pages`, `jobs_processed`, `jobs_failed`.
  - **Thread Execution**:
    - Periodically samples RSS memory and CPU via `psutil`.
    - Executes Redis pipeline:
      1. `HSET blast_ocr:worker:{worker_id} ...`
      2. `EXPIRE blast_ocr:worker:{worker_id} {ttl}`
      3. `SADD blast_ocr:workers:active {worker_id}`
    - Updates Prometheus metric: `blast_worker_memory_bytes.labels(worker_id=...).set(rss_bytes)`.
  - **Lifecycle & Draining**:
    - `start()`: Launches daemon thread, registers worker.
    - `set_busy(job_id, total_pages=0)`: Transitions status to `"busy"`.
    - `set_idle()`: Transitions status to `"idle"`.
    - `update_progress(current_page, total_pages)`: Updates page progress in heartbeat hash.
    - `stop()`: Marks status `"offline"`, sends `SREM blast_ocr:workers:active {worker_id}`, deletes hash key, joins thread.
- **Registry Inspection Functions**:
  - `get_active_workers(connection=None) -> List[Dict[str, Any]]`: Reads all active workers, computes `seconds_since_heartbeat`.
  - `get_worker_info(worker_id, connection=None) -> Optional[Dict[str, Any]]`.

---

### 4.3 `blast_ocr/queue/reaper.py` (Zombie Job Reaper & Failover Handler)
- **Zombie Detection Logic**:
  - Fetches all `worker_id`s in `blast_ocr:workers:active`.
  - For each `worker_id`:
    - Checks `EXISTS blast_ocr:worker:{worker_id}` and `time.time() - last_heartbeat > ttl`.
    - If expired/stale:
      1. Remove from active set: `SREM blast_ocr:workers:active {worker_id}`.
      2. Query DB `OCRJob` for jobs assigned to this `worker_id` where `status == "processing"`.
      3. For each orphaned job:
         - If `job.retry_count < job.max_retries`:
           - Increment `job.retry_count += 1`.
           - Set `job.status = JobState.QUEUED.value`, `job.worker_id = None`.
           - Re-enqueue to target priority queue.
           - Log failover event and increment Prometheus counter `blast_job_retries_total`.
         - If `job.retry_count >= job.max_retries`:
           - Set `job.status = JobState.FAILED.value`, `job.dlq_at = now()`, `job.dlq_reason = f"Worker {worker_id} died and retries ({job.max_retries}) exhausted"`.
           - Push to `blast_ocr:queue:dlq`.
           - Increment Prometheus counter `blast_dlq_jobs_total`.
- **`ZombieReaperDaemon` Class**:
  - Background daemon thread running `reap_dead_workers()` every `reap_interval` (15.0s).

---

### 4.4 `blast_ocr/queue/swarm.py` & `blast_ocr/queue/worker.py` (Multi-Worker Supervisor)
- **`SwarmWorker`**:
  - Subclasses / wraps RQ `Worker` to listen across `[queue_high, queue_default, queue_low]`.
  - Starts `HeartbeatDaemon` upon initialization.
  - Hooks into task lifecycle:
    - Pre-execute: updates DB `worker_id`, `started_at`, `status=JobState.PROCESSING.value`; sets heartbeat status to `"busy"`.
    - Post-execute: sets heartbeat status to `"idle"`.
  - Signal handling: catches `SIGTERM`/`SIGINT`, initiates graceful draining (`status="draining"`), finishes active job, stops heartbeat daemon.
- **`SwarmSupervisor`**:
  - Manages $N$ worker processes using `multiprocessing.Process`.
  - Supervisor Loop (`run()` / `step()`):
    - Monitors child process health via `proc.is_alive()`.
    - If child process exits unexpectedly (e.g. OOM killer, segfault):
      - Logs warning.
      - Triggers `reap_dead_workers()` to recover any orphaned jobs.
      - Spawns a replacement worker process to maintain swarm capacity.
    - Signal Handling: catches `SIGTERM`/`SIGINT`, forwards termination to child workers, waits up to `graceful_timeout` (30s), kills unresponsive children.
- **CLI Entrypoints**:
  - `python -m blast_ocr.queue.swarm --workers 4 --queues high,default,low --heartbeat-interval 5`
  - `python -m blast_ocr.queue.worker --worker-id worker-1 --queues high,default,low`

---

### 4.5 `blast_ocr/queue/tasks.py` (Worker Task Execution, Backoff & DLQ)
- **`run_ocr_job(source_path, output_dir, job_id, config_overrides, priority="default", retry_count=0, max_retries=3)`**:
  - Updates DB `OCRJob`: `status=JobState.PROCESSING.value`, `worker_id=current_worker_id`, `started_at=now()`.
  - Hooks pipeline `progress_callback` to update DB and heartbeat daemon (`current_page`, `total_pages`).
  - Executes `BlastPipeline.process_job(source_path=source_path, output_dir=output_dir, job_id=job_id)`.
  - **Exception & Retry Handling**:
    ```python
    try:
        with BlastPipeline(config_overrides=config_overrides) as pipeline:
            return pipeline.process_job(source_path, output_dir=output_dir, job_id=job_id, progress_callback=progress_cb)
    except Exception as exc:
        is_retryable = classify_exception(exc)
        if is_retryable and retry_count < max_retries:
            next_retry = retry_count + 1
            delay = min(60.0, 2.0 * (2.0 ** retry_count)) + random.uniform(0.0, 1.0)
            db.record_retry(job_id, next_retry, str(exc))
            # Re-enqueue to priority queue with delay
            re_enqueue_job(job_id, source_path, output_dir, config_overrides, priority, next_retry, max_retries, delay)
        else:
            db.quarantine_job(job_id, dlq_reason=str(exc))
            push_to_dlq(job_id, source_path, output_dir, config_overrides, str(exc))
        raise exc
    ```

---

### 4.6 `blast_ocr/api/routes.py` & `blast_ocr/api/schemas.py` (REST API Integration)
- **`POST /v1/ocr/jobs`**:
  - Accepts `priority: str = Form("default")` and `max_retries: int = Form(3)`.
  - If `config.queue_backend == "redis"`:
    - Calls `blast_ocr.queue.client.enqueue_job(...)`.
    - Returns `JobResponse` with `job_id`, `rq_job_id`, `priority`, `status="queued"`.
  - If `config.queue_backend == "sync"`:
    - Uses in-process `BackgroundTasks` (fixing line 42 to pass `job_id=job_id`).
- **`GET /v1/workers`**:
  - Calls `HeartbeatDaemon.get_active_workers()`.
  - Returns `SwarmHealthResponse` (`active_workers_count`, `busy_workers_count`, `idle_workers_count`, `workers: List[WorkerInfoResponse]`).
- **`GET /v1/queues`**:
  - Calls `get_queue_depths()`.
  - Returns `QueueDepthResponse` (`high_priority_depth`, `default_priority_depth`, `low_priority_depth`, `dlq_depth`).
- **`GET /v1/queues/dlq`**:
  - Returns list of dead-lettered jobs with error diagnostics.
- **`POST /v1/ocr/jobs/{job_id}/retry`**:
  - Resets retry counter, re-enqueues job into priority queue.
- **`POST /v1/ocr/jobs/{job_id}/cancel`**:
  - Cancels job in DB and RQ.

---

### 4.7 Database Schema & Alembic Migration
- **Schema Updates in `blast_ocr/storage/database.py`**:
  ```python
  class OCRJob(Base):
      __tablename__ = "ocr_jobs"
      id = Column(Integer, primary_key=True)
      filename = Column(String(255), nullable=False)
      page_count = Column(Integer)
      status = Column(String(50))
      priority = Column(String(20), default="default", nullable=False)
      retry_count = Column(Integer, default=0, nullable=False)
      max_retries = Column(Integer, default=3, nullable=False)
      worker_id = Column(String(100), nullable=True)
      queue_name = Column(String(50), nullable=True)
      started_at = Column(DateTime, nullable=True)
      completed_at = Column(DateTime, nullable=True)
      dlq_at = Column(DateTime, nullable=True)
      dlq_reason = Column(Text, nullable=True)
      error_message = Column(Text, nullable=True)
      created_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc))
  ```
- **Alembic Migration (`002_swarm_and_priority.py`)**:
  - Uses `batch_alter_table` so SQLite supports adding columns seamlessly without lock or schema issues.
- **Database Helper Methods**:
  - `claim_job(job_id, worker_id)`
  - `record_retry(job_id, retry_count, error_message)`
  - `quarantine_job(job_id, dlq_reason)`
  - `get_dlq_jobs(limit=100)`

---

## 5. Testing & Verification Strategy (`tests/test_queue_swarm.py`)

The test suite must cover 100% of the distributed swarm, queue, retry, and reaper components:

| Test Group | Test Case | Target Verification |
| :--- | :--- | :--- |
| **Priority Queuing** | `test_priority_queue_enqueue_and_depth` | Verify `high`, `default`, `low`, `dlq` queues receive jobs and report depths accurately. |
| **Priority Ordering** | `test_priority_order_consumption` | Verify worker drains `high` queue before `default` and `low`. |
| **Idempotency** | `test_deduplication_lock` | Verify duplicate submissions with identical fingerprint return existing `job_id`. |
| **Heartbeat Daemon** | `test_heartbeat_lifecycle_and_registry` | Verify heartbeat thread registers in active set, sets TTL, updates busy/idle, unregisters on stop. |
| **Zombie Reaper** | `test_reaper_detects_dead_worker_and_failover` | Verify reaper detects expired worker key, recovers `PROCESSING` job, increments retry, re-queues. |
| **DLQ Exhaustion** | `test_reaper_quarantines_exhausted_retries` | Verify reaper moves job to DLQ when `retry_count >= max_retries`. |
| **Backoff & DLQ** | `test_task_retry_transient_vs_deterministic` | Verify transient error retries with backoff; deterministic error goes directly to DLQ. |
| **DLQ Replay** | `test_dlq_retry_endpoint` | Verify `/v1/ocr/jobs/{id}/retry` resets retry count and re-enqueues job. |
| **Swarm Supervisor** | `test_swarm_supervisor_respawns_crashed_worker` | Verify supervisor detects dead child process and launches replacement. |
| **REST API Routes** | `test_api_workers_and_queues_endpoints` | Verify `/v1/workers`, `/v1/queues`, `/v1/queues/dlq` return valid JSON schemas. |
| **Fakeredis Fallback** | `test_queue_with_fakeredis` | Verify unit tests run hermetically with `fakeredis` when Redis is unavailable. |

---

## 6. Implementation Sequence & Instructions for Implementer

1. **Step 1: Database Migration & Model Updates**
   - Update `blast_ocr/storage/database.py` with new `OCRJob` columns and helper methods.
   - Create `blast_ocr/storage/alembic/versions/002_swarm_and_priority.py`.
2. **Step 2: Core Queue Infrastructure (`client.py`, `heartbeat.py`, `reaper.py`)**
   - Implement `blast_ocr/queue/heartbeat.py` (`HeartbeatDaemon`, active worker registry).
   - Implement `blast_ocr/queue/reaper.py` (`ZombieReaper`, stale detection, job failover).
   - Update `blast_ocr/queue/client.py` (Priority queues, queue depths, DLQ replay, deduplication).
3. **Step 3: Worker & Supervisor Execution (`tasks.py`, `swarm.py`, `worker.py`)**
   - Update `blast_ocr/queue/tasks.py` (`run_ocr_job` with exception classification, backoff retry, DLQ).
   - Implement `blast_ocr/queue/swarm.py` (`SwarmSupervisor`, multi-process manager, auto-restart, graceful drain).
   - Update `blast_ocr/queue/worker.py` (`SwarmWorker` multi-queue listener with heartbeat).
4. **Step 4: API & Telemetry Integration**
   - Update `blast_ocr/api/schemas.py` and `blast_ocr/api/routes.py` (priority dispatch, `/v1/workers`, `/v1/queues`, retry, bug fix at line 42).
   - Update `blast_ocr/telemetry.py` with swarm gauges/counters.
5. **Step 5: Test Suite & Verification**
   - Implement comprehensive tests in `tests/test_queue_swarm.py`.
   - Run full test suite with `pytest` ensuring 100% pass rate.

# HANDOFF — survey_explorer_2

**Role:** teamwork_preview_explorer / System Architect  
**Task:** Survey B.L.A.S.T. OCR Codebase for Requirement R2 (Distributed Multi-Worker Swarm & Durable Queue)  
**Report Path:** `/mnt/d/code/Projects/Python/OCR_Book/.agents/survey_explorer_2/report.md`  
**Date:** 2026-08-15  

---

## 1. Observation

1. **FastAPI Job Submission & In-Process Execution**:
   - `blast_ocr/api/routes.py:50-118` defines `POST /v1/ocr/jobs` which creates an `OCRJob` in `OCRDatabase` and dispatches `background_tasks.add_task(_execute_pipeline_task, doc_source, final_output_dir, config_overrides, job_id)`.
   - `blast_ocr/api/routes.py:38-48`: `_execute_pipeline_task` invokes `pipeline.process_job(source_path, output_dir=output_dir)` without passing `job_id=job_id`.
   - As a result, FastAPI job processing currently runs purely in-process inside FastAPI's event loop worker, is not durable across server restarts, and fails to associate the created `job_id` with page results.

2. **Existing Queue Subsystem**:
   - `blast_ocr/queue/client.py:18` defines `DEFAULT_QUEUE_NAME = "blast_ocr_jobs"`.
   - `blast_ocr/queue/client.py:44-80` defines `enqueue_job()` which connects to Redis, creates an `OCRJob` in DB, computes SHA256 fingerprint, and enqueues `run_ocr_job` to a single queue.
   - `blast_ocr/queue/tasks.py:16-41` defines `run_ocr_job()` which runs `BlastPipeline.process_job(source_path, output_dir, job_id=job_id)`.
   - `blast_ocr/queue/worker.py:18-40` defines `main()` running `rq.Worker([queue])`.
   - The queue subsystem lacks:
     - Priority tiers (`high`, `default`, `low`).
     - Worker heartbeat daemon and registration registry.
     - Swarm supervisor / manager to orchestrate $N$ worker processes with auto-restart and graceful draining.
     - Exponential backoff retry policies and Dead-Letter Queue (DLQ) routing.
     - Multi-node object storage staging (currently passes local filesystem path).

3. **State Machine & Retry Classification**:
   - `blast_ocr/core/job_state.py:32-81` implements `classify_exception(exc)` classifying exceptions into retryable (`OCREngineError`, `TimeoutError`, `ConnectionError`, `MemoryError`, `WorkerLostError`) vs non-retryable (`SecurityValidationError`, `ValueError`, `UnsupportedPDFError`, `InvalidDocumentError`).
   - `JobStateMachine` supports states: `RECEIVED`, `VALIDATING`, `QUEUED`, `PROCESSING`, `POST_PROCESSING`, `EXPORTING`, `SUCCEEDED`, `SUCCEEDED_WITH_WARNINGS`, `PARTIAL_FAILURE`, `FAILED`, `CANCELLED`, `QUARANTINED`, `TIMED_OUT`.
   - Transitions allow `FAILED -> QUEUED` and `TIMED_OUT -> QUEUED`.

4. **Database & Concurrency Primitives**:
   - `blast_ocr/storage/database.py:35-47` defines table `ocr_jobs` with columns: `id`, `filename`, `page_count`, `status`, `created_at`, `completed_at`, `error_message`.
   - `blast_ocr/storage/database.py:80-118` configures SQLAlchemy `scoped_session` with `threading.get_ident` and SQLite WAL mode `isolation_level="IMMEDIATE"`.
   - `blast_ocr/core/extractor.py:24` uses module-level singleton `_ocr_global_lock = threading.Lock()` for in-process EasyOCR serialization.
   - In distributed worker processes (separate OS processes), each worker process runs its own engine instance in isolated memory, eliminating Python GIL bottlenecks across workers.

5. **Dependencies & Optional Infra**:
   - `requirements-production.txt:16-17` lists `rq>=2.0.0` and `redis>=5.0.0`.
   - `requirements-dev.txt:8` lists `fakeredis>=2.20.0`.
   - `blast_ocr/config.py:90-92` defines `queue_backend` (`"sync"` default / `"redis"`) and `redis_url`.

---

## 2. Logic Chain

1. **From In-Process FastAPI to Distributed Durable Queue**:
   - Observations 1 & 2 show that while `blast_ocr/queue/client.py` and `blast_ocr/queue/tasks.py` exist, the REST API `routes.py` is bypassed and currently dispatches ephemeral in-process `BackgroundTasks`.
   - Transitioning `POST /v1/ocr/jobs` to conditionally dispatch through `enqueue_job()` when `config.queue_backend == "redis"` (or when requested by caller) provides true process-boundary durability, surviving web server restarts.
   - Fixing `routes.py:42` to pass `job_id=job_id` ensures consistent job tracking.

2. **From Single Queue to 3-Tier Priority Multiplexing**:
   - Observation 2 shows a single queue name `blast_ocr_jobs`.
   - Splitting into `blast_ocr:queue:high`, `blast_ocr:queue:default`, and `blast_ocr:queue:low` allows urgent single-page interactive jobs to be processed with <1s latency even under heavy multi-page book batch processing loads.
   - Setting `SwarmWorker` consumption order to `[queue_high, queue_default, queue_low]` guarantees strict priority execution via Redis atomic dequeue without extra scheduler complexity.

3. **From Unsupervised Workers to Swarm Manager & Automated Heartbeats**:
   - Observation 2 shows `blast_ocr/queue/worker.py` only runs a single worker in the foreground.
   - Creating `blast_ocr/queue/swarm.py` (`SwarmSupervisor`) allows operators to launch $N$ worker processes (e.g. `python -m blast_ocr.queue.swarm --workers 4`) with automatic process restart on unexpected crash and graceful draining on `SIGTERM`.
   - Introducing a background Heartbeat Daemon in each worker (`blast_ocr/queue/heartbeat.py`) that periodically updates `blast_ocr:worker:<id>` in Redis allows the system to monitor worker health, memory, CPU, and active job status.
   - Introducing `blast_ocr/queue/reaper.py` (Zombie Job Reaper) ensures that if a worker dies mid-job, the job is detected within 20s and automatically rescheduled or dead-lettered.

4. **From Immediate Failure to Exponential Backoff & Dead-Letter Queue (DLQ)**:
   - Observation 3 shows that error classification already exists (`classify_exception`), but is not integrated into a retry scheduler.
   - Implementing an exponential backoff formula ($\text{delay} = \text{base\_delay} \times 2^{\text{attempt}-1} + \text{jitter}$) with max retries (default 3) allows transient failures (`OCREngineError`, `TimeoutError`, `WorkerLostError`) to recover automatically.
   - When retries are exhausted or upon deterministic failure (`SecurityValidationError`), routing the job to `blast_ocr:queue:dlq` and updating DB status to `FAILED` / `QUARANTINED` with error diagnostics prevents toxic job loops while enabling operator inspection and replay via `POST /v1/ocr/jobs/{id}/retry`.

5. **From Single-Node Path Passing to Multi-Node Storage Sync**:
   - Observations 2 & 4 show that workers currently expect local file paths.
   - Integrating `blast_ocr.storage.object_store.ObjectStorage` allows distributed workers on separate servers/containers to download inputs from S3/MinIO and upload completed `ExportBundle` artifacts without assuming a shared disk.

---

## 3. Caveats

1. **Redis Requirement for Distributed Mode**:
   - Distributed multi-worker mode requires a running Redis instance (or AWS ElastiCache / Redis Cloud). When Redis is not available, the codebase defaults to `queue_backend="sync"` for single-machine synchronous execution.
2. **Database Concurrency in Multi-Host Setups**:
   - SQLite is excellent for single-node deployments using WAL mode + `BEGIN IMMEDIATE`. However, for multi-host deployments running workers across multiple virtual machines without a shared NFS, a centralized database (PostgreSQL / MySQL) is recommended.
3. **GPU Allocation per Worker**:
   - When running multiple worker processes on a single GPU node, GPU memory must be budgeted (e.g., ONNX Runtime CUDA execution provider memory limits) to prevent CUDA out-of-memory errors.

---

## 4. Conclusion

The existing B.L.A.S.T. OCR codebase possesses strong foundational building blocks (a clean `JobStateMachine`, domain `JobConfig`, pluggable `BaseOCREngine`, and baseline RQ queue client).

To achieve **Requirement R2 (Distributed Multi-Worker Swarm & Durable Queue)**:
1. Implement the **3-Tier Priority Queue System** (`blast_ocr:queue:high`, `default`, `low`) in `blast_ocr/queue/client.py`.
2. Build the **Swarm Supervisor & Worker Swarm Manager** (`blast_ocr/queue/swarm.py`) and **Worker Heartbeat Daemon** (`blast_ocr/queue/heartbeat.py`).
3. Build the **Zombie Job Reaper & Health Monitor** (`blast_ocr/queue/reaper.py`) for automatic dead worker failover.
4. Implement **Exponential Backoff Retry & Dead-Letter Queue (DLQ)** in `blast_ocr/queue/tasks.py` with failure taxonomy gating.
5. Enhance the **FastAPI Service** (`blast_ocr/api/routes.py` and `schemas.py`) with `/v1/workers`, `/v1/queues`, `/v1/ocr/jobs/{id}/retry`, and wire `/v1/ocr/jobs` to the priority queue.
6. Add the Alembic database migration (`002_swarm_and_priority.py`) adding `priority`, `retry_count`, `max_retries`, `worker_id`, `started_at`, and `dlq_reason` columns to `ocr_jobs`.

All technical details, architecture diagrams, schemas, and file specifications are documented in `/mnt/d/code/Projects/Python/OCR_Book/.agents/survey_explorer_2/report.md`.

---

## 5. Verification Method

To independently verify the survey observations and architecture:
1. **Inspect API & Queue Code**:
   - `view_file` on `blast_ocr/api/routes.py:38-118` to verify in-process background execution and missing `job_id`.
   - `view_file` on `blast_ocr/queue/client.py` and `blast_ocr/queue/worker.py` to verify current single-queue implementation.
   - `view_file` on `blast_ocr/core/job_state.py` to verify `classify_exception` and `JobStateMachine`.
2. **Run Existing Test Suite**:
   ```bash
   pytest
   # Verified baseline: 376 passed, 2 skipped in 308.42s (0 failures, 100% pass rate)
   ```
3. **Survey Report Invalidation Conditions**:
   - If Redis/RQ is replaced with Celery or RabbitMQ, queue broker topology would need adjustment (though the priority tiers, heartbeats, backoff, and DLQ concepts remain identical).
   - If FastAPI is deprecated in favor of gRPC, route contracts would change to protobuf IDL.

---

# Handoff Report: Milestone 2 Technical Exploration & Architecture Design

**Author:** Explorer 1 (Milestone 2)  
**Recipient:** Parent Orchestrator (`sub_orch_m2`)  
**Working Directory:** `/mnt/d/code/Projects/Python/OCR_Book/.agents/explorer_m2_1`  
**Date:** 2026-08-15  

---

## 1. Observation

1. **Environment & Dependencies**:
   - `python3 -c "import redis, rq, fakeredis; print(redis.__version__, rq.__version__, fakeredis.__version__)"` returned:
     - `redis: 8.1.0`
     - `rq: 2.10.0`
     - `fakeredis: 2.37.0`
   - Active Redis service verified on `redis://localhost:6379/0`.
   - `pytest tests/test_queue.py` executed and passed 3/3 tests (`test_redis_reachable`, `test_enqueue_creates_db_job_and_rq_job`, `test_worker_processes_queued_job_end_to_end`).
   - `pytest tests/test_alembic_migration.py` passed 3/3 tests verifying clean Alembic migrations.

2. **API & Routes Audit (`blast_ocr/api/routes.py`, `blast_ocr/api/schemas.py`)**:
   - `POST /v1/ocr/jobs` currently creates a DB record with state `QUEUED` but executes via FastAPI `BackgroundTasks.add_task(_execute_pipeline_task)` rather than Redis/RQ queue.
   - **Line 42 Bug**: `_execute_pipeline_task` calls `pipeline.process_job(source_path, output_dir=output_dir)` without passing `job_id=job_id`, causing `BlastPipeline` to create a duplicate job row.
   - API lacks endpoints for `/v1/workers` (worker telemetry), `/v1/queues` (queue depths), and `/v1/ocr/jobs/{job_id}/retry` (DLQ/failed job replay).

3. **Current Queue Plumbing (`blast_ocr/queue/`)**:
   - `client.py`: Supports only single queue `"blast_ocr_jobs"` without priority scheduling (`high`, `default`, `low`) or DLQ routing.
   - `tasks.py`: Module-level `run_ocr_job` does not handle exponential backoff, worker heartbeat callbacks, or DLQ quarantine.
   - `worker.py`: Single-process RQ worker without heartbeat daemon, multi-queue listening, or supervisor lifecycle management.
   - Missing modules: `blast_ocr/queue/heartbeat.py`, `blast_ocr/queue/reaper.py`, `blast_ocr/queue/swarm.py`.

4. **Database & Migrations (`blast_ocr/storage/database.py`)**:
   - `OCRJob` model has columns: `id`, `filename`, `page_count`, `status`, `created_at`, `completed_at`, `error_message`.
   - Missing distributed columns: `priority`, `retry_count`, `max_retries`, `worker_id`, `queue_name`, `started_at`, `dlq_at`, `dlq_reason`.
   - Existing migration is `001_initial_schema.py`. Migration `002_swarm_and_priority.py` needs to be created using SQLite batch alter mode.

---

## 2. Logic Chain

1. **Decoupled Distributed Queue**:
   - By structuring 3 priority queues (`blast_ocr:queue:high`, `blast_ocr:queue:default`, `blast_ocr:queue:low`), single-page and interactive requests take precedence over large background batches while worker multiplexing (`Worker([high, default, low])`) maintains strict SLA targets.
2. **Worker Liveness & Heartbeat Daemon**:
   - Running a background `HeartbeatDaemon` per worker updating Redis `HSET blast_ocr:worker:{id}` with a 20s TTL and `SADD blast_ocr:workers:active {id}` guarantees non-blocking, real-time worker telemetry without adding latency to OCR inference.
3. **Zombie Detection & Failover**:
   - `ZombieReaper` scans active worker IDs against existing Redis keys. If a worker key expires while a job remains in `PROCESSING` status, the reaper detects the failure, checks `retry_count < max_retries`, and automatically re-enqueues the job to its priority queue or transfers it to the DLQ.
4. **Exponential Backoff & Classification**:
   - Using `blast_ocr.core.job_state:classify_exception(exc)` differentiates transient network/resource errors (which receive exponential backoff jittered retry) from deterministic input/security errors (which immediately fail to prevent infinite retry loops).
5. **Multi-Process Swarm Supervisor**:
   - `SwarmSupervisor` using `multiprocessing.Process` maintains $N$ worker processes, traps OS exit codes, auto-spawns replacement workers if any child crashes (OOM, segfault), and ensures clean `SIGTERM` draining.
6. **API Integration & Bug Fix**:
   - Routing `POST /v1/ocr/jobs` to `enqueue_job` when `queue_backend == "redis"` connects API callers to the distributed swarm, and passing `job_id=job_id` ensures idempotent database state tracking.

---

## 3. Caveats

1. **SQLite Database Locking**:
   - When running tests with SQLite, concurrent writes from multiple processes must use WAL mode (`BEGIN IMMEDIATE`) already established in `database.py`.
2. **Fakeredis vs Live Redis**:
   - Tests in `tests/test_queue_swarm.py` should test both against live Redis (when available) and support hermetic testing via `fakeredis` or mocks.
3. **Subprocess Signal Handling**:
   - Multi-process worker management in `SwarmSupervisor` must properly handle `SIGINT`/`SIGTERM` on Linux to avoid lingering background worker processes.

---

## 4. Conclusion

The architecture for Milestone 2 is fully specified, verified against the existing codebase, and ready for immediate implementation. 

### Key Artifacts Produced
- Complete Exploration & Architecture Design Report: `/mnt/d/code/Projects/Python/OCR_Book/.agents/explorer_m2_1/report.md`
- Target Implementation Modules:
  1. `blast_ocr/storage/database.py` & `blast_ocr/storage/alembic/versions/002_swarm_and_priority.py`
  2. `blast_ocr/queue/heartbeat.py`
  3. `blast_ocr/queue/reaper.py`
  4. `blast_ocr/queue/client.py`
  5. `blast_ocr/queue/tasks.py`
  6. `blast_ocr/queue/swarm.py` & `blast_ocr/queue/worker.py`
  7. `blast_ocr/api/routes.py` & `blast_ocr/api/schemas.py`
  8. `tests/test_queue_swarm.py`

---

## 5. Verification Method

To verify the investigation and design findings independently:

1. **Check Dependencies and Live Redis**:
   ```bash
   python3 -c "import redis, rq, fakeredis; print(redis.__version__, rq.__version__, fakeredis.__version__)"
   pytest tests/test_queue.py
   pytest tests/test_alembic_migration.py
   ```
2. **Inspect Exploration Report**:
   - Read `/mnt/d/code/Projects/Python/OCR_Book/.agents/explorer_m2_1/report.md`

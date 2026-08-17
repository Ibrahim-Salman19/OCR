# DISPATCH — worker_m2

**Task**: Implement Milestone 2 (Distributed Multi-Worker Swarm & Durable Queue)
**Working Directory**: `/mnt/d/code/Projects/Python/OCR_Book/.agents/worker_m2`
**Scope Document**: `/mnt/d/code/Projects/Python/OCR_Book/PROJECT.md`
**Original Request**: `/mnt/d/code/Projects/Python/OCR_Book/.agents/ORIGINAL_REQUEST.md`
**Survey Blueprint**: `/mnt/d/code/Projects/Python/OCR_Book/.agents/survey_explorer_2/report.md`

### Mandatory Integrity Warning
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

### Implementation Checklist
1. `blast_ocr/queue/client.py`:
   - `JobPriority` enum (`high`, `default`, `low`).
   - 3-tier queue names (`blast_ocr:queue:high`, `blast_ocr:queue:default`, `blast_ocr:queue:low`, DLQ `blast_ocr:queue:dlq`).
   - `enqueue_job()` supporting priority routing, deduplication locks, and Redis connection fallback.
2. `blast_ocr/queue/swarm.py`:
   - `SwarmSupervisor` & `SwarmWorker`: Multi-process swarm manager supporting $N$ worker processes, signal handling (`SIGTERM`/`SIGINT`), worker recycling, and graceful draining.
3. `blast_ocr/queue/heartbeat.py`:
   - `WorkerHeartbeatDaemon` & `WorkerRegistry`: Background thread reporting worker metrics (CPU, RSS memory, state `IDLE`/`BUSY`, active job ID) to Redis key `blast_ocr:worker:<id>` with TTL.
4. `blast_ocr/queue/reaper.py`:
   - `ZombieJobReaper`: Inspects dead worker heartbeats and orphan jobs in `PROCESSING` state, requeuing or DLQ routing.
5. `blast_ocr/queue/tasks.py`:
   - `run_ocr_job()`: Resilient task execution with `classify_exception()`, exponential backoff retry ($2^n + \text{jitter}$), max retries, and DLQ routing.
6. `blast_ocr/api/routes.py` & `blast_ocr/api/schemas.py`:
   - `POST /v1/ocr/jobs` supporting `priority` parameter.
   - `GET /v1/workers` (swarm worker list, health, status).
   - `GET /v1/queues` (queue depths across high/default/low/dlq).
   - `POST /v1/ocr/jobs/{id}/retry` (replay failed/quarantined job).
7. `tests/test_queue_swarm.py`:
   - Comprehensive unit and integration tests using `fakeredis` or real redis mock, testing priority ordering, swarm process management, heartbeats, reaper zombie failover, exponential backoff, DLQ, and API routes.
8. Run `pytest tests/test_queue_swarm.py -v` and `pytest` for 0 regressions.
9. Write `handoff.md` and report completion.

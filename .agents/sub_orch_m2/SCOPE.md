# Scope: Milestone 2 — Distributed Multi-Worker Swarm & Durable Queue

## Architecture
BLAST OCR distributed queue and worker swarm system powered by Redis / RQ / Fakeredis-compatible architecture:
- 3-tier priority queues: `high`, `default`, `low`
- Multi-process worker swarm supervisor managing worker pools
- Worker heartbeat daemon registering worker status, active jobs, CPU/mem/heartbeat TTL in Redis
- Zombie job reaper detecting dead workers and failing over / re-queueing orphaned jobs
- Exponential backoff retry handler with Dead Letter Queue (DLQ) quarantine for exhausted retries
- FastAPI integration: priority job dispatch, worker status monitoring endpoint (`/v1/workers`), queue metrics (`/v1/queues`), job retry endpoint (`/v1/ocr/jobs/{id}/retry`)
- Comprehensive test coverage in `tests/test_queue_swarm.py`

## Target Modules & Files
1. `blast_ocr/queue/client.py`: QueueClient with high/default/low priority dispatch, queue metrics, job enqueueing.
2. `blast_ocr/queue/swarm.py`: SwarmSupervisor & SwarmWorker multi-process lifecycle manager.
3. `blast_ocr/queue/heartbeat.py`: HeartbeatDaemon, worker registration, TTL management.
4. `blast_ocr/queue/reaper.py`: ZombieReaper detecting stale worker keys, recovering abandoned jobs.
5. `blast_ocr/queue/tasks.py`: Task definitions, worker execution wrapper, exponential backoff, DLQ quarantine.
6. `blast_ocr/api/routes.py` & `blast_ocr/api/schemas.py`: REST API endpoints and Pydantic models for priority dispatch, workers, queues, retry.
7. `tests/test_queue_swarm.py`: Multi-tier unit and integration tests for swarm, queues, heartbeats, reaper, backoff, DLQ, API routes.

## Status
- Status: IN_PROGRESS

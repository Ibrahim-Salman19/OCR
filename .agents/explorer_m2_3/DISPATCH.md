## 2026-08-15T14:59:58Z
You are Explorer 3 for Milestone 2 (Distributed Multi-Worker Swarm & Durable Queue).
Your working directory for metadata: /mnt/d/code/Projects/Python/OCR_Book/.agents/explorer_m2_3
Scope document: /mnt/d/code/Projects/Python/OCR_Book/.agents/sub_orch_m2/SCOPE.md
Original request: /mnt/d/code/Projects/Python/OCR_Book/.agents/ORIGINAL_REQUEST.md
Survey report: /mnt/d/code/Projects/Python/OCR_Book/.agents/survey_explorer_2/report.md

Task:
1. Investigate the API extensions and test strategy for Milestone 2:
   - API endpoints in `blast_ocr/api/routes.py` and models in `blast_ocr/api/schemas.py`:
     * Priority support in job submission (`priority: "high" | "default" | "low"`)
     * `GET /v1/workers`: list active workers, their status, heartbeat timestamp, active jobs
     * `GET /v1/queues`: stats across high, default, low, dlq queues (enqueued count, active count, failed count)
     * `POST /v1/ocr/jobs/{id}/retry`: manual retry of failed / DLQ jobs
   - Test suite design for `tests/test_queue_swarm.py`:
     * Unit tests for QueueClient (priority routing, queue inspection)
     * SwarmSupervisor process management & worker scaling
     * Heartbeat daemon & Redis TTL expiry / alive checking
     * Zombie Reaper dead-worker detection and job recovery
     * Exponential backoff retry mechanism & DLQ isolation
     * API route integration tests with TestClient
     * Edge cases (redis disconnect, unhandled worker crashes, poisoned payloads)
2. Detail test setup (using fakeredis or redis mock) ensuring tests run deterministically and fast without requiring an external live Redis server if not running.
3. Write your report to `/mnt/d/code/Projects/Python/OCR_Book/.agents/explorer_m2_3/report.md`.
4. Write handoff.md in your directory and send a message back to parent.

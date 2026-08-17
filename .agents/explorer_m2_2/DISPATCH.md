## 2026-08-15T14:59:57Z

<USER_REQUEST>
You are Explorer 2 for Milestone 2 (Distributed Multi-Worker Swarm & Durable Queue).
Your working directory for metadata: /mnt/d/code/Projects/Python/OCR_Book/.agents/explorer_m2_2
Scope document: /mnt/d/code/Projects/Python/OCR_Book/.agents/sub_orch_m2/SCOPE.md
Original request: /mnt/d/code/Projects/Python/OCR_Book/.agents/ORIGINAL_REQUEST.md
Survey report: /mnt/d/code/Projects/Python/OCR_Book/.agents/survey_explorer_2/report.md

Task:
1. Deep-dive into the architectural specifications for the Distributed Queue & Swarm:
   - `blast_ocr/queue/client.py`: 3-tier priority queues (`high`, `default`, `low`), enqueueing, queue length/metrics inspection, connection handling with redis/fakeredis.
   - `blast_ocr/queue/swarm.py`: `SwarmSupervisor` and `SwarmWorker` multi-process worker management, graceful shutdown (SIGTERM/SIGINT), concurrency control, dynamic scaling/worker pooling.
   - `blast_ocr/queue/heartbeat.py`: Heartbeat daemon, TTL key expiry in Redis (e.g. `worker:{id}:heartbeat`), metrics reporting (active jobs, CPU/mem/status).
   - `blast_ocr/queue/reaper.py`: Zombie job reaper detecting dead workers, orphaned job recovery, failover/re-queueing.
   - `blast_ocr/queue/tasks.py`: Task worker wrapper, exponential backoff retry logic, Dead Letter Queue (DLQ) quarantine upon max retries exhausted.
2. Provide concrete interface signatures, data structures, Redis key conventions, and fail-safe designs.
3. Write your report to `/mnt/d/code/Projects/Python/OCR_Book/.agents/explorer_m2_2/report.md`.
4. Write handoff.md in your directory and send a message back to parent.
</USER_REQUEST>

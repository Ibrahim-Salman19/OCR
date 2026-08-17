# DISPATCH — survey_explorer_2

**Objective**: Survey the service architecture, job management, queue systems, and worker orchestration.
**Key Focus**:
1. Map out current `blast_ocr/service`, FastAPI routes, job submission/polling/streaming endpoints.
2. Investigate how a distributed multi-worker swarm (Redis/Celery/RQ or lightweight async distributed worker swarm) can be integrated with automated worker heartbeats, dynamic job priority scheduling, task retry with exponential backoff, and dead-letter queue (DLQ) handling.
3. Identify existing lock/concurrency mechanisms and how to ensure clean scaling without race conditions.
4. Enumerate all required features, dependencies, and interface contracts for R2.
5. Write your comprehensive survey report to `/mnt/d/code/Projects/Python/OCR_Book/.agents/survey_explorer_2/report.md` and handoff to `/mnt/d/code/Projects/Python/OCR_Book/.agents/survey_explorer_2/handoff.md`.

"""
blast_ocr.queue

Durable job queue (Phase 5/8 of Execution Plan v2: "Durable Jobs Instead of
Synchronous Processing"). Backed by Redis + RQ.

Synchronous, zero-infra processing (BlastPipeline.process_job() called
directly) remains the default -- this package is opt-in via
`config.queue_backend = "redis"`, so nothing about running BLAST requires a
Redis server unless a deployment explicitly wants durable, out-of-process job
execution (closing the browser must not kill OCR -- see EXECUTION_PLAN.md
Phase 14).
"""

from blast_ocr.queue.client import enqueue_job, get_queue, get_redis_connection, is_queue_available

__all__ = ["enqueue_job", "get_queue", "get_redis_connection", "is_queue_available"]

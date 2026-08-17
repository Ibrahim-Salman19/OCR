"""
blast_ocr.queue.tasks

The single RQ/Swarm task entrypoint. Kept as a plain, module-level, importable
function ("blast_ocr.queue.tasks.run_ocr_job").
Includes BackoffDLQHandler for categorized failure retries with exponential
backoff ($2^n + \text{jitter}$) and Dead-Letter Queue (DLQ) quarantine.
"""

import json
import logging
import random
import time
from datetime import datetime
from typing import Any, Dict, Optional

from blast_ocr.core.job_state import (
    classify_exception,
)
from blast_ocr.core.models import JobState

logger = logging.getLogger(__name__)


class BackoffDLQHandler:
    """
    Handles exponential backoff delay calculation, exception classification,
    and routing between scheduled retry queues and Dead-Letter Queues (DLQ).
    """

    def __init__(
        self,
        base_delay: float = 2.0,
        backoff_factor: float = 2.0,
        max_backoff: float = 60.0,
        jitter_max: float = 1.0,
        max_retries: int = 3,
        redis_client: Optional[Any] = None,
    ):
        self.base_delay = base_delay
        self.backoff_factor = backoff_factor
        self.max_backoff = max_backoff
        self.jitter_max = jitter_max
        self.max_retries = max_retries
        self.redis = redis_client
        self.dlq_key = "blast_ocr:queue:dlq"
        self.delayed_key = "blast_ocr:delayed_jobs"

    def compute_backoff_delay(self, attempt: int, jitter_seed: Optional[int] = None) -> float:
        """
        Calculate backoff delay: min(max_backoff, base_delay * (backoff_factor ** (attempt - 1))) + jitter
        """
        if attempt < 1:
            attempt = 1
        nominal_delay = min(self.max_backoff, self.base_delay * (self.backoff_factor ** (attempt - 1)))
        rng = random.Random(jitter_seed) if jitter_seed is not None else random
        jitter = rng.uniform(0.0, self.jitter_max) if self.jitter_max > 0 else 0.0
        return nominal_delay + jitter

    def handle_task_failure(
        self,
        job_id: int,
        exc: BaseException,
        current_retry_count: int,
        job_payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Processes a task failure, classifying exception and either scheduling retry or routing to DLQ.
        """
        is_retryable = classify_exception(exc)

        if is_retryable and current_retry_count < self.max_retries:
            next_retry = current_retry_count + 1
            delay = self.compute_backoff_delay(next_retry)
            scheduled_time = time.time() + delay
            job_payload.update({
                "job_id": job_id,
                "retry_count": next_retry,
                "max_retries": self.max_retries,
                "last_error": str(exc),
                "scheduled_retry_time": scheduled_time,
                "status": "retry_scheduled",
            })
            if self.redis:
                self.redis.hset(f"blast_ocr:job:{job_id}", mapping={
                    "status": "retry_scheduled",
                    "retry_count": next_retry,
                    "last_error": str(exc),
                })
                self.redis.rpush(self.delayed_key, json.dumps(job_payload))
            return {
                "action": "retry",
                "retry_count": next_retry,
                "delay_seconds": delay,
                "job_payload": job_payload,
            }
        else:
            # Quarantine in DLQ
            job_payload.update({
                "job_id": job_id,
                "status": JobState.FAILED.value,
                "retry_count": current_retry_count,
                "dlq_at": datetime.utcnow().isoformat(),
                "dlq_reason": str(exc),
                "exc_type": type(exc).__name__,
                "is_retryable": is_retryable,
            })
            if self.redis:
                self.redis.hset(f"blast_ocr:job:{job_id}", mapping={
                    "status": JobState.FAILED.value,
                    "dlq_at": job_payload["dlq_at"],
                    "dlq_reason": str(exc),
                })
                self.redis.rpush(self.dlq_key, json.dumps(job_payload))
            return {
                "action": "dlq",
                "dlq_reason": str(exc),
                "job_payload": job_payload,
            }

    def handle_failure(
        self,
        job_id: Any,
        source_path: str = "",
        retry_count: int = 0,
        exc: Optional[BaseException] = None,
    ) -> Dict[str, Any]:
        """
        Convenience alias conforming to eval and stress test harnesses.
        """
        return self.handle_task_failure(
            job_id=job_id,
            exc=exc or Exception("Unknown error"),
            current_retry_count=retry_count,
            job_payload={"job_id": job_id, "source_path": source_path},
        )

    def replay_dlq_job(self, job_id: int, target_queue: str = "blast_ocr:queue:high") -> Dict[str, Any]:
        """
        Replays a dead-lettered job: resets retry count, clears failure metadata, re-enqueues.
        """
        replayed_payload = None
        if self.redis:
            raw_dlq_jobs = self.redis.lrange(self.dlq_key, 0, -1)
            remaining_dlq = []
            for raw in raw_dlq_jobs:
                data = json.loads(raw) if isinstance(raw, (str, bytes)) else raw
                if data.get("job_id") == job_id:
                    replayed_payload = data
                else:
                    remaining_dlq.append(raw)

            if replayed_payload:
                self.redis.delete(self.dlq_key)
                for item in remaining_dlq:
                    self.redis.rpush(self.dlq_key, item)

                replayed_payload["retry_count"] = 0
                replayed_payload["status"] = JobState.QUEUED.value
                replayed_payload.pop("dlq_at", None)
                replayed_payload.pop("dlq_reason", None)

                self.redis.hset(f"blast_ocr:job:{job_id}", mapping={
                    "status": JobState.QUEUED.value,
                    "retry_count": 0,
                    "error_message": "",
                })
                self.redis.rpush(target_queue, json.dumps(replayed_payload))

        return {
            "success": replayed_payload is not None,
            "job_id": job_id,
            "target_queue": target_queue,
            "payload": replayed_payload,
        }

    def process_delayed_jobs(self, queue_manager=None) -> int:
        """
        Polls delayed jobs queue and promotes matured retryable jobs back to active priority queues.
        Returns the number of promoted jobs.
        """
        if not self.redis:
            return 0

        now = time.time()
        promoted = 0
        total = self.redis.llen(self.delayed_key)
        for _ in range(total):
            raw = self.redis.lpop(self.delayed_key)
            if not raw:
                break
            try:
                payload = json.loads(raw if isinstance(raw, str) else raw.decode("utf-8"))
            except Exception:
                continue

            scheduled_time = payload.get("scheduled_retry_time", 0)
            if now >= scheduled_time:
                priority = payload.get("priority", "default")
                job_id = payload.get("job_id")
                if queue_manager:
                    queue_manager.enqueue(
                        job_id=job_id,
                        source_path=payload.get("source_path", ""),
                        priority=priority,
                        config_overrides=payload.get("config_overrides"),
                        retry_count=payload.get("retry_count", 0),
                    )
                else:
                    target_queue = f"blast_ocr:queue:{priority}"
                    self.redis.lpush(target_queue, json.dumps(payload))
                promoted += 1
            else:
                self.redis.rpush(self.delayed_key, json.dumps(payload))
        return promoted


def run_ocr_job(
    source_path: str,
    output_dir: Optional[str] = None,
    job_id: Optional[int] = None,
    config_overrides: Optional[Dict[str, Any]] = None,
    worker_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Worker-side task body. Runs inside the worker process, updating DB execution
    metadata and processing document through BlastPipeline.
    """
    from blast_ocr.pipeline import BlastPipeline
    from blast_ocr.storage.database import OCRDatabase

    logger.info(f"[queue worker] Starting job_id={job_id} source={source_path} worker={worker_id}")

    db = OCRDatabase()
    if job_id:
        try:
            db.update_job_execution(job_id=job_id, worker_id=worker_id, started_at=datetime.utcnow())
        except Exception as e:
            logger.debug(f"Could not record job execution start in database: {e}")
    db.close()

    try:
        with BlastPipeline(config_overrides=config_overrides) as pipeline:
            result = pipeline.process_job(
                source_path=source_path, output_dir=output_dir, job_id=job_id
            )
        logger.info(f"[queue worker] Finished job_id={job_id} status={result.get('status')}")
        return result
    except Exception as e:
        logger.error(f"[queue worker] Job execution failed for job_id={job_id}: {e}", exc_info=True)
        # Handle failure tracking
        handler = BackoffDLQHandler()
        handler.handle_task_failure(
            job_id=job_id or 0,
            exc=e,
            current_retry_count=0,
            job_payload={"source_path": source_path, "output_dir": output_dir, "config_overrides": config_overrides},
        )
        raise e

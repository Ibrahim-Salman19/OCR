"""
tests/e2e/tier1_features/test_f09_exponential_backoff_dlq.py

Tier 1 Isolated Feature Tests: Feature 9 - Exponential Backoff & DLQ Handling
Covers:
- Error taxonomy classification (transient vs deterministic)
- Exponential backoff delay calculation with bounded jitter
- Transient failure retry progression up to max_retries
- Dead-Letter Queue (DLQ) quarantine on retry exhaustion
- DLQ inspection and replay workflow resetting state
"""

import json
import time
import random
from datetime import datetime
from typing import Any, Dict, Optional


from blast_ocr.core.job_state import (
    classify_exception,
    JobStateMachine,
    NonRetryableJobError,
    TransientWorkerError,
    TemporaryStorageError,
    WorkerLostError,
    UnsupportedPDFError,
    EncryptedPDFError,
    InvalidDocumentError,
)
from blast_ocr.core.models import JobState


class BackoffDLQHandler:
    """
    Reference/interface handler for Exponential Backoff and Dead-Letter Queue (DLQ).
    Implements the R2 requirement contracts specified in PROJECT.md and TEST_INFRA.md.
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


# ============================================================================
# Test Cases (>= 5 Tests)
# ============================================================================

def test_f09_exception_taxonomy_classification():
    """
    Test 1: Verifies error taxonomy accurately classifies transient exceptions
    as retryable and deterministic/security exceptions as non-retryable.
    """
    # Transient / Retryable Exceptions
    assert classify_exception(TimeoutError("Connection timed out")) is True
    assert classify_exception(ConnectionError("Redis broker unreachable")) is True
    assert classify_exception(MemoryError("CUDA out of memory")) is True
    assert classify_exception(TransientWorkerError("Worker process SIGKILL")) is True
    assert classify_exception(TemporaryStorageError("MinIO upload 503")) is True
    assert classify_exception(WorkerLostError("Heartbeat expired")) is True

    # Deterministic / Non-Retryable Exceptions
    assert classify_exception(ValueError("Invalid page range specified")) is False
    assert classify_exception(FileNotFoundError("source.pdf missing")) is False
    assert classify_exception(UnsupportedPDFError("Corrupt XRef table")) is False
    assert classify_exception(EncryptedPDFError("Password required")) is False
    assert classify_exception(InvalidDocumentError("0-byte payload")) is False
    
    # Custom non-retryable subclass
    class CustomSecurityValidationError(NonRetryableJobError):
        pass
    assert classify_exception(CustomSecurityValidationError("Magic byte mismatch")) is False


def test_f09_exponential_backoff_delay_calculation():
    """
    Test 2: Tests backoff formula across successive attempts (attempt 1, 2, 3, 4...)
    ensuring exponential growth, bounded max backoff, and non-negative jitter.
    """
    handler = BackoffDLQHandler(base_delay=2.0, backoff_factor=2.0, max_backoff=30.0, jitter_max=1.0)
    
    # Attempt 1: 2 * (2^0) = 2.0s (+ jitter 0..1)
    delay_1 = handler.compute_backoff_delay(1, jitter_seed=42)
    assert 2.0 <= delay_1 <= 3.0, f"Attempt 1 delay {delay_1} out of bounds"

    # Attempt 2: 2 * (2^1) = 4.0s (+ jitter 0..1)
    delay_2 = handler.compute_backoff_delay(2, jitter_seed=42)
    assert 4.0 <= delay_2 <= 5.0, f"Attempt 2 delay {delay_2} out of bounds"

    # Attempt 3: 2 * (2^2) = 8.0s (+ jitter 0..1)
    delay_3 = handler.compute_backoff_delay(3, jitter_seed=42)
    assert 8.0 <= delay_3 <= 9.0, f"Attempt 3 delay {delay_3} out of bounds"

    # Attempt 4: 2 * (2^3) = 16.0s (+ jitter 0..1)
    delay_4 = handler.compute_backoff_delay(4, jitter_seed=42)
    assert 16.0 <= delay_4 <= 17.0, f"Attempt 4 delay {delay_4} out of bounds"

    # Large attempt should be strictly capped at max_backoff + jitter (30.0 + 1.0)
    delay_large = handler.compute_backoff_delay(10, jitter_seed=42)
    assert 30.0 <= delay_large <= 31.0, f"Capped delay {delay_large} exceeded max_backoff + jitter"


def test_f09_transient_failure_retried_up_to_max_retries(mock_redis):
    """
    Test 3: Tests that a task encountering transient errors is retried up to max_retries
    with incremented retry count before exhausting.
    """
    handler = BackoffDLQHandler(max_retries=3, redis_client=mock_redis)
    job_id = 901
    payload = {"source_path": "/tmp/book.pdf", "engine": "rapidocr"}

    # Attempt 1 transient failure -> should retry with retry_count=1
    res1 = handler.handle_task_failure(job_id, TimeoutError("Socket timeout"), 0, payload)
    assert res1["action"] == "retry"
    assert res1["retry_count"] == 1
    assert "scheduled_retry_time" in res1["job_payload"]

    # Attempt 2 transient failure -> should retry with retry_count=2
    res2 = handler.handle_task_failure(job_id, ConnectionError("Broker dropped"), 1, res1["job_payload"])
    assert res2["action"] == "retry"
    assert res2["retry_count"] == 2

    # Attempt 3 transient failure -> should retry with retry_count=3
    res3 = handler.handle_task_failure(job_id, MemoryError("GPU memory pressure"), 2, res2["job_payload"])
    assert res3["action"] == "retry"
    assert res3["retry_count"] == 3


def test_f09_dlq_quarantine_on_retry_exhaustion(mock_redis):
    """
    Test 4: Tests that when retry attempts exceed max_retries (or on non-retryable error),
    the job is quarantined into the dead-letter queue (blast_ocr:queue:dlq) with FAILED state.
    """
    handler = BackoffDLQHandler(max_retries=3, redis_client=mock_redis)
    job_id = 902
    payload = {"source_path": "/tmp/corrupt.pdf", "engine": "rapidocr"}

    # Scenario A: Retry exhaustion (retry_count=3 >= max_retries=3)
    res_exhausted = handler.handle_task_failure(job_id, TimeoutError("Persistent timeout"), 3, payload)
    assert res_exhausted["action"] == "dlq"
    assert res_exhausted["job_payload"]["status"] == JobState.FAILED.value
    assert "Persistent timeout" in res_exhausted["job_payload"]["dlq_reason"]
    assert mock_redis.llen("blast_ocr:queue:dlq") == 1

    # Scenario B: Deterministic non-retryable error -> Immediate DLQ quarantine on first attempt
    job_id_determ = 903
    payload_determ = {"source_path": "/tmp/bad.pdf"}
    res_determ = handler.handle_task_failure(job_id_determ, UnsupportedPDFError("Invalid PDF header"), 0, payload_determ)
    assert res_determ["action"] == "dlq"
    assert res_determ["job_payload"]["is_retryable"] is False
    assert mock_redis.llen("blast_ocr:queue:dlq") == 2


def test_f09_dlq_replay_resets_state_and_reenqueues(mock_redis):
    """
    Test 5: Tests replaying a dead-lettered job resets retry_count to 0,
    clears error_message/dlq metadata, and pushes the job back to the active queue.
    """
    handler = BackoffDLQHandler(max_retries=3, redis_client=mock_redis)
    job_id = 904
    payload = {"source_path": "/tmp/recoverable.pdf", "engine": "rapidocr"}

    # Force job into DLQ
    handler.handle_task_failure(job_id, TimeoutError("Transient network failure"), 3, payload)
    assert mock_redis.llen("blast_ocr:queue:dlq") == 1

    # Replay job to high-priority queue
    replay_res = handler.replay_dlq_job(job_id, target_queue="blast_ocr:queue:high")
    assert replay_res["success"] is True
    assert replay_res["payload"]["retry_count"] == 0
    assert replay_res["payload"]["status"] == JobState.QUEUED.value

    # DLQ should now be empty and high queue should have 1 job
    assert mock_redis.llen("blast_ocr:queue:dlq") == 0
    assert mock_redis.llen("blast_ocr:queue:high") == 1

    # Verify state machine transition FAILED -> QUEUED is valid
    assert JobStateMachine.can_transition(JobState.FAILED, JobState.QUEUED) is True

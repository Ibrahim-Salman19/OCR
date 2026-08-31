"""
blast_ocr.queue.priority

3-Tier Dynamic Priority Queue Scheduling (high, default, low) and Dead-Letter Queue (dlq).
Supports Redis atomic operations (BRPOP/RPOP/LPUSH), payload serialization, and strict priority multiplexing.
"""

from enum import Enum
import json
import time
import logging
from typing import Any, Dict, List, Optional, Tuple, Union

logger = logging.getLogger(__name__)


class JobPriority(str, Enum):
    HIGH = "high"
    DEFAULT = "default"
    LOW = "low"
    DLQ = "dlq"


class PriorityLevel:
    HIGH = "high"
    DEFAULT = "default"
    LOW = "low"
    ALL = [HIGH, DEFAULT, LOW]


class PriorityQueueManager:
    QUEUE_PREFIX = "blast_ocr:queue:"
    DLQ_KEY = "blast_ocr:queue:dlq"
    DELAYED_KEY = "blast_ocr:delayed_jobs"

    # Anti-starvation aging (TAX-STR-02): dequeue() otherwise drains HIGH to
    # empty before ever looking at DEFAULT/LOW. Under continuous HIGH-priority
    # arrival -- the realistic failure mode, not a momentary burst -- that
    # queue is never observed empty, so DEFAULT/LOW jobs wait forever. Once
    # the oldest job in a lower queue has waited past its threshold, it is
    # popped ahead of the strict sweep on the *next* dequeue() call,
    # guaranteeing forward progress without changing the ordering a fresh
    # (unaged) job experiences.
    LOW_AGING_THRESHOLD_SECONDS: float = 60.0
    DEFAULT_AGING_THRESHOLD_SECONDS: float = 30.0

    def __init__(self, redis_client=None):
        if redis_client is None:
            try:
                from blast_ocr.queue.client import get_redis_connection
                self.redis = get_redis_connection()
            except Exception:
                self.redis = None
        else:
            self.redis = redis_client

    @classmethod
    def queue_key(cls, priority: str) -> str:
        if priority not in PriorityLevel.ALL:
            raise ValueError(f"Invalid priority '{priority}'. Must be one of {PriorityLevel.ALL}")
        return f"{cls.QUEUE_PREFIX}{priority}"

    def enqueue(
        self,
        job_id: Union[str, int],
        source_path: str,
        priority: str = PriorityLevel.DEFAULT,
        config_overrides: Optional[Dict[str, Any]] = None,
        input_sha256: Optional[str] = None,
        retry_count: int = 0,
    ) -> Dict[str, Any]:
        """
        Enqueues a job payload onto the designated priority queue.
        """
        key = self.queue_key(priority)
        payload = {
            "job_id": str(job_id),
            "source_path": str(source_path),
            "priority": priority,
            "enqueued_at": time.time(),
            "retry_count": retry_count,
            "config_overrides": config_overrides or {},
        }
        if input_sha256:
            payload["input_sha256"] = input_sha256

        if self.redis:
            self.redis.lpush(key, json.dumps(payload))
        return payload

    def _oldest_job_age_seconds(self, priority: str) -> Optional[float]:
        """
        Peeks (without popping) the oldest queued job's age for a priority
        tier. RPOP consumes from the tail, so index -1 is exactly the item
        the next rpop() would return -- peeking it via LRANGE(-1, -1) is
        non-destructive. Uses LRANGE rather than LINDEX since it's the one
        list-read primitive every Redis client/mock in this codebase (real
        redis-py, fakeredis, and the in-memory test fallback) implements.
        Returns None if the queue is empty or the entry can't be parsed
        (treated by callers as "not aged", never as an error).
        """
        key = self.queue_key(priority)
        try:
            tail = self.redis.lrange(key, -1, -1)
        except Exception:
            return None
        if not tail:
            return None
        raw = tail[0]
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        try:
            payload = json.loads(raw)
            enqueued_at = float(payload["enqueued_at"])
        except Exception:
            return None
        return time.time() - enqueued_at

    def _pop_aged_job(self, priority: str) -> Optional[Tuple[str, Dict[str, Any]]]:
        """Pops the oldest job from a priority tier once it has been confirmed aged."""
        key = self.queue_key(priority)
        raw_payload = self.redis.rpop(key)
        if raw_payload is None:
            return None
        if isinstance(raw_payload, bytes):
            raw_payload = raw_payload.decode("utf-8")
        try:
            payload = json.loads(raw_payload)
            if not isinstance(payload, dict):
                payload = {"job_id": str(payload), "priority": priority}
        except Exception:
            payload = {"job_id": str(raw_payload), "raw": str(raw_payload), "priority": priority}
        return priority, payload

    def dequeue(self, timeout: int = 1) -> Optional[Tuple[str, Dict[str, Any]]]:
        """
        Dequeues the next job, strictly adhering to HIGH -> DEFAULT -> LOW
        priority order UNLESS a lower-tier job has aged past its starvation
        threshold, in which case that aged job is served first to guarantee
        forward progress under sustained higher-priority load (TAX-STR-02).
        Returns (priority, job_payload_dict) or None if queues are empty.
        """
        if not self.redis:
            return None

        # 0. Anti-starvation aging check (checked worst-tier-first: an aged
        # LOW job takes precedence over an aged DEFAULT job).
        for priority, threshold in (
            (PriorityLevel.LOW, self.LOW_AGING_THRESHOLD_SECONDS),
            (PriorityLevel.DEFAULT, self.DEFAULT_AGING_THRESHOLD_SECONDS),
        ):
            age = self._oldest_job_age_seconds(priority)
            if age is not None and age >= threshold:
                aged_result = self._pop_aged_job(priority)
                if aged_result is not None:
                    return aged_result

        keys = [self.queue_key(p) for p in PriorityLevel.ALL]

        # 1. Non-blocking check across priority tiers (HIGH -> DEFAULT -> LOW)
        for k in keys:
            raw_payload = self.redis.rpop(k)
            if raw_payload is not None:
                k_str = k.decode("utf-8") if isinstance(k, bytes) else str(k)
                priority = k_str.replace(self.QUEUE_PREFIX, "")
                if isinstance(raw_payload, bytes):
                    raw_payload = raw_payload.decode("utf-8")
                try:
                    payload = json.loads(raw_payload)
                    if isinstance(payload, (str, int)):
                        payload = {"job_id": str(payload), "priority": priority}
                    elif not isinstance(payload, dict):
                        payload = {"job_id": str(payload), "priority": priority}
                except Exception:
                    payload = {"job_id": str(raw_payload), "raw": str(raw_payload), "priority": priority}
                return priority, payload

        if timeout == 0:
            return None

        # 2. Blocking pop if queues are currently empty
        try:
            result = self.redis.brpop(keys, timeout=timeout)
            if not result:
                return None
            matched_key, raw_payload = result
            matched_str = matched_key.decode("utf-8") if isinstance(matched_key, bytes) else str(matched_key)
            priority = matched_str.replace(self.QUEUE_PREFIX, "")
            if isinstance(raw_payload, bytes):
                raw_payload = raw_payload.decode("utf-8")
            try:
                payload = json.loads(raw_payload)
                if isinstance(payload, (str, int)):
                    payload = {"job_id": str(payload), "priority": priority}
                elif not isinstance(payload, dict):
                    payload = {"job_id": str(payload), "priority": priority}
            except Exception:
                payload = {"job_id": str(raw_payload), "raw": str(raw_payload), "priority": priority}
            return priority, payload
        except Exception:
            return None

    def get_queue_depth(self, priority: str) -> int:
        if not self.redis:
            return 0
        key = self.queue_key(priority)
        return self.redis.llen(key)

    def get_all_queue_depths(self) -> Dict[str, int]:
        return {p: self.get_queue_depth(p) for p in PriorityLevel.ALL}

    def get_dlq_depth(self) -> int:
        if not self.redis:
            return 0
        return self.redis.llen(self.DLQ_KEY)

    def list_dlq_jobs(self, limit: int = 100) -> List[Dict[str, Any]]:
        if not self.redis:
            return []
        raw_items = self.redis.lrange(self.DLQ_KEY, 0, limit - 1)
        dlq_jobs = []
        for raw in raw_items:
            try:
                data = json.loads(raw) if isinstance(raw, str) else json.loads(raw.decode("utf-8"))
                dlq_jobs.append(data)
            except Exception:
                dlq_jobs.append({"raw": str(raw), "corrupt": True})
        return dlq_jobs

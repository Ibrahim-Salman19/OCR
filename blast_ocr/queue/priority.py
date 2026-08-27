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

    def dequeue(self, timeout: int = 1) -> Optional[Tuple[str, Dict[str, Any]]]:
        """
        Dequeues next job strictly adhering to HIGH -> DEFAULT -> LOW priority order.
        Returns (priority, job_payload_dict) or None if queues are empty.
        """
        if not self.redis:
            return None

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

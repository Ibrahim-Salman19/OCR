"""
blast_ocr.queue.client

Thin wrapper around redis-py + RQ with 3-tier priority queue scheduling,
deduplication lock guards, and multi-queue management.
Imports of `redis`/`rq` are deferred so that installations running with
queue_backend="sync" (the default) do not require those dependencies.
"""

import json
import logging
import time
import uuid
from typing import Any, Dict, Optional

from blast_ocr.config import config
from blast_ocr.core.job_state import JobFingerprint
from blast_ocr.core.models import JobConfig
from blast_ocr.queue.priority import JobPriority, PriorityLevel, PriorityQueueManager

import threading

logger = logging.getLogger(__name__)

__all__ = [
    "get_redis_connection",
    "is_queue_available",
    "get_queue",
    "enqueue_job",
    "QueueClient",
    "PriorityQueueManager",
    "PriorityLevel",
    "JobPriority",
    "DEFAULT_QUEUE_NAME",
    "HIGH_QUEUE_NAME",
    "LOW_QUEUE_NAME",
    "DLQ_QUEUE_NAME",
]

DEFAULT_QUEUE_NAME = "blast_ocr:queue:default"
HIGH_QUEUE_NAME = "blast_ocr:queue:high"
LOW_QUEUE_NAME = "blast_ocr:queue:low"
DLQ_QUEUE_NAME = "blast_ocr:queue:dlq"
QUEUE_PREFIX = "blast_ocr:queue:"
LOCK_PREFIX = "blast_ocr:lock:fingerprint:"

_REDIS_POOLS: Dict[str, Any] = {}
_REDIS_LOCK = threading.Lock()


def get_redis_connection(redis_url: Optional[str] = None):
    """Returns a Redis client connected to configured redis_url using a shared ConnectionPool."""
    import redis

    target_url = redis_url or config.redis_url
    with _REDIS_LOCK:
        if target_url not in _REDIS_POOLS:
            _REDIS_POOLS[target_url] = redis.ConnectionPool.from_url(
                target_url,
                max_connections=50,
                socket_connect_timeout=1.0,
                socket_timeout=1.0,
            )
        pool = _REDIS_POOLS[target_url]
    return redis.Redis(connection_pool=pool)


def is_queue_available() -> bool:
    """
    Best-effort reachability check, used by the UI/CLI/API to decide whether to
    offer the queued path or fall back to synchronous processing.
    """
    try:
        conn = get_redis_connection()
        return bool(conn.ping())
    except Exception as e:
        logger.debug(f"Redis queue backend not reachable: {e}")
        return False


def get_queue(name: str = DEFAULT_QUEUE_NAME):
    """
    Returns an RQ Queue instance. Accepts queue names (e.g. 'blast_ocr:queue:high')
    or priority tiers ('high', 'default', 'low', 'dlq').
    """
    from rq import Queue

    clean_name = name
    if clean_name in ("high", "default", "low", "dlq"):
        clean_name = f"{QUEUE_PREFIX}{clean_name}"
    elif clean_name == "blast_ocr_jobs":
        clean_name = DEFAULT_QUEUE_NAME

    return Queue(clean_name, connection=get_redis_connection())


class QueueClient:
    """
    Direct Redis-backed client for multi-tier priority job dispatching,
    atomic priority dequeuing, deduplication locking, and depth inspection.
    """

    VALID_PRIORITIES = ("high", "default", "low")

    def __init__(self, redis_client=None, prefix: str = QUEUE_PREFIX):
        if redis_client is None:
            try:
                self.redis = get_redis_connection()
            except Exception:
                self.redis = None
        else:
            self.redis = redis_client
        self.prefix = prefix

    def _get_queue_key(self, priority: Optional[str]) -> str:
        p = priority.lower() if isinstance(priority, str) else "default"
        if p not in self.VALID_PRIORITIES:
            p = "default"
        return f"{self.prefix}{p}"

    def enqueue(self, job_data: dict, priority: str = "default") -> str:
        """Enqueues job dictionary to designated priority queue."""
        if not self.redis:
            raise ConnectionError("Redis is not connected.")

        job_id = str(job_data.get("job_id") or uuid.uuid4())
        job_data["job_id"] = job_id
        if "enqueued_at" not in job_data:
            job_data["enqueued_at"] = time.time()
        job_data["priority"] = priority if priority in self.VALID_PRIORITIES else "default"

        queue_key = self._get_queue_key(priority)
        payload = json.dumps(job_data)
        self.redis.lpush(queue_key, payload)
        return job_id

    def pop_next_job(self, timeout: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """
        Dequeues next job strictly adhering to HIGH -> DEFAULT -> LOW priority order.
        """
        if not self.redis:
            return None

        keys = [f"{self.prefix}{p}" for p in self.VALID_PRIORITIES]
        if timeout is None or timeout == 0:
            for k in keys:
                raw = self.redis.rpop(k)
                if raw:
                    return json.loads(raw) if isinstance(raw, str) else json.loads(raw.decode("utf-8"))
            return None
        else:
            res = self.redis.brpop(keys, timeout=timeout)
            if not res:
                return None
            queue_name, raw_payload = res
            return json.loads(raw_payload) if isinstance(raw_payload, str) else json.loads(raw_payload.decode("utf-8"))

    def get_queue_lengths(self) -> Dict[str, int]:
        """Returns lengths of standard priority queues."""
        if not self.redis:
            return {p: 0 for p in self.VALID_PRIORITIES}
        return {
            p: self.redis.llen(f"{self.prefix}{p}") for p in self.VALID_PRIORITIES
        }

    def get_all_queue_depths(self) -> Dict[str, int]:
        """Returns depths across high, default, low, and dlq."""
        depths = self.get_queue_lengths()
        dlq_depth = self.redis.llen(DLQ_QUEUE_NAME) if self.redis else 0
        depths["dlq"] = dlq_depth
        return depths

    def acquire_dedup_lock(self, fingerprint: str, job_id: Any, ttl: int = 600) -> bool:
        """Acquires an atomic deduplication lock for a job execution fingerprint."""
        if not self.redis or not fingerprint:
            return True
        lock_key = f"{LOCK_PREFIX}{fingerprint}"
        return bool(self.redis.set(lock_key, str(job_id), nx=True, ex=ttl))

    def get_dedup_lock(self, fingerprint: str) -> Optional[str]:
        """Returns job_id holding deduplication lock for fingerprint if active."""
        if not self.redis or not fingerprint:
            return None
        lock_key = f"{LOCK_PREFIX}{fingerprint}"
        raw = self.redis.get(lock_key)
        return raw.decode("utf-8") if isinstance(raw, bytes) else raw

    def release_dedup_lock(self, fingerprint: str) -> None:
        """Releases the deduplication lock for a fingerprint."""
        if self.redis and fingerprint:
            lock_key = f"{LOCK_PREFIX}{fingerprint}"
            self.redis.delete(lock_key)


def enqueue_job(
    source_path: str,
    output_dir: Optional[str] = None,
    input_sha256: Optional[str] = None,
    config_overrides: Optional[Dict[str, Any]] = None,
    priority: str = "default",
    max_retries: int = 3,
) -> Dict[str, Any]:
    """
    Create a durable DB job record and enqueue its processing on the Redis
    queue with specified priority and deduplication lock checks.
    """
    from pathlib import Path
    from blast_ocr.queue.tasks import run_ocr_job
    from blast_ocr.storage.database import OCRDatabase

    job_priority = priority.lower() if isinstance(priority, str) else "default"
    if job_priority not in ("high", "default", "low"):
        job_priority = "default"

    job_config = JobConfig.from_dict(config_overrides or {})
    fingerprint = (
        JobFingerprint.compute(input_sha256, job_config) if input_sha256 else None
    )

    client = QueueClient()

    # Idempotency check via deduplication lock
    if fingerprint and client.redis:
        existing_job_id = client.get_dedup_lock(fingerprint)
        if existing_job_id:
            logger.info(f"Duplicate job detected for fingerprint {fingerprint}. Returning existing job_id={existing_job_id}")
            return {
                "job_id": int(existing_job_id) if str(existing_job_id).isdigit() else existing_job_id,
                "rq_job_id": None,
                "fingerprint": fingerprint,
                "priority": job_priority,
                "deduplicated": True,
            }

    db = OCRDatabase()
    queue_target_name = f"{QUEUE_PREFIX}{job_priority}"
    job_id = db.create_job(
        Path(source_path).name,
        page_count=0,
        priority=job_priority,
        max_retries=max_retries,
        queue_name=queue_target_name,
    )

    if fingerprint and client.redis:
        client.acquire_dedup_lock(fingerprint, job_id, ttl=600)

    rq_job_id = None
    try:
        q = get_queue(job_priority)
        rq_job = q.enqueue(
            run_ocr_job,
            source_path,
            output_dir,
            job_id,
            config_overrides,
            job_timeout=config.queue_job_timeout,
            result_ttl=86400,
            failure_ttl=86400,
        )
        rq_job_id = rq_job.id
    except Exception as e:
        logger.warning(f"Could not enqueue via RQ, writing directly to Redis priority queue: {e}")
        qm = PriorityQueueManager(client.redis)
        qm.enqueue(
            job_id=job_id,
            source_path=source_path,
            priority=job_priority,
            config_overrides=config_overrides,
            input_sha256=input_sha256,
        )

    logger.info(f"Enqueued job_id={job_id} priority={job_priority} (fingerprint={fingerprint})")
    return {
        "job_id": job_id,
        "rq_job_id": rq_job_id,
        "fingerprint": fingerprint,
        "priority": job_priority,
    }

"""
blast_ocr.queue.reaper

Zombie Job Reaper and Failover Engine.
Detects abandoned or orphaned jobs from crashed workers, automatically
re-enqueues them to priority queues with incremented retry counters,
or escalates to Dead-Letter Queue (DLQ) upon retry threshold exhaustion.
"""

import json
import logging
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ReaperResult(dict):
    """
    Result container for reaper executions.
    Provides dictionary access (for statistics) and list comparison (for reaped IDs).
    """

    def __init__(self, reaped_ids: Optional[List[str]] = None, reaped_count: int = 0, dlq_count: int = 0, checked_leases: int = 0):
        self.reaped_ids = reaped_ids or []
        super().__init__({
            "reaped_count": reaped_count,
            "dlq_count": dlq_count,
            "checked_leases": checked_leases,
            "reaped_jobs": self.reaped_ids,
        })

    def __eq__(self, other):
        if isinstance(other, list):
            return self.reaped_ids == other
        return super().__eq__(other)


class ZombieReaper:
    """
    Inspects active worker leases, heartbeat registries, and processing state.
    Recovers orphaned tasks when worker processes crash or freeze.
    """

    LEASE_PREFIX = "blast_ocr:leases:"
    DLQ_KEY = "blast_ocr:queue:dlq"
    MAX_REAP_ATTEMPTS = 3

    def __init__(
        self,
        redis_client=None,
        queue_manager=None,
        queue_client=None,
        lease_timeout_sec: float = 30.0,
        grace_sec: float = 30.0,
        max_retries: int = 3,
    ):
        if redis_client is None:
            try:
                from blast_ocr.queue.client import get_redis_connection
                self.redis = get_redis_connection()
            except Exception:
                self.redis = None
        else:
            self.redis = redis_client

        self.queue_manager = queue_manager
        self.queue_client = queue_client
        self.lease_timeout = lease_timeout_sec
        self.grace_sec = grace_sec
        self.max_retries = max_retries

    def record_lease(self, worker_id: str, job_payload: Dict[str, Any]):
        """Records an active job execution lease for a worker."""
        if not self.redis:
            return
        job_id = str(job_payload.get("job_id"))
        lease_data = {
            "worker_id": worker_id,
            "job_payload": job_payload,
            "leased_at": time.time(),
        }
        self.redis.set(f"{self.LEASE_PREFIX}{job_id}", json.dumps(lease_data))
        self.redis.set(f"blast_ocr:worker:{worker_id}:current_job", json.dumps(job_payload))

    def release_lease(self, job_id: str, worker_id: Optional[str] = None):
        """Releases the execution lease upon job completion."""
        if not self.redis:
            return
        self.redis.delete(f"{self.LEASE_PREFIX}{job_id}")
        if worker_id:
            self.redis.delete(f"blast_ocr:worker:{worker_id}:current_job")

    def reap_zombies(self) -> ReaperResult:
        """
        Scans active leases and worker registries for dead workers and orphan jobs.
        Requeues retryable jobs or moves exhausted jobs to DLQ.
        """
        if not self.redis:
            return ReaperResult([], 0, 0, 0)

        now = time.time()
        reaped_count = 0
        dlq_count = 0
        reaped_job_ids: List[str] = []
        seen_job_ids = set()

        # 1. Check Lease Keys (blast_ocr:leases:*)
        if hasattr(self.redis, "scan_iter"):
            lease_keys = list(self.redis.scan_iter(f"{self.LEASE_PREFIX}*"))
        else:
            lease_keys = list(self.redis.keys(f"{self.LEASE_PREFIX}*"))
        for lk in lease_keys:
            raw = self.redis.get(lk)
            if not raw:
                continue
            try:
                data = json.loads(raw) if isinstance(raw, str) else json.loads(raw.decode("utf-8"))
            except Exception:
                continue

            worker_id = data.get("worker_id")
            job_payload = data.get("job_payload", {})
            leased_at = data.get("leased_at", 0)
            job_id = str(job_payload.get("job_id"))

            if job_id in seen_job_ids:
                continue

            # Check worker vitality
            worker_alive = bool(
                self.redis.exists(f"blast_ocr:workers:{worker_id}")
                or self.redis.exists(f"blast_ocr:worker:{worker_id}")
                or self.redis.exists(f"blast_ocr:heartbeat:{worker_id}")
            )
            lease_expired = (now - leased_at) > self.lease_timeout

            if worker_alive and lease_expired:
                # Worker is still actively running; extend lease instead of false-positive reaping
                data["leased_at"] = now
                self.redis.set(lk, json.dumps(data), ex=int(self.lease_timeout * 3))
                continue

            if not worker_alive or lease_expired:
                seen_job_ids.add(job_id)
                retry_count = job_payload.get("retry_count", 0) + 1
                job_payload["retry_count"] = retry_count
                job_payload["last_reaped_at"] = now

                if retry_count > self.max_retries:
                    # Quarantine to DLQ
                    job_payload["dlq_reason"] = "Max retries exceeded due to worker crashes"
                    self.redis.lpush(self.DLQ_KEY, json.dumps(job_payload))
                    dlq_count += 1
                else:
                    priority = job_payload.get("priority", "default")
                    if self.queue_manager:
                        self.queue_manager.enqueue(
                            job_id=job_id,
                            source_path=job_payload.get("source_path", ""),
                            priority=priority,
                            config_overrides=job_payload.get("config_overrides"),
                            retry_count=retry_count,
                        )
                    elif self.queue_client:
                        self.queue_client.enqueue(job_payload, priority=priority)
                    else:
                        from blast_ocr.queue.client import QueueClient
                        QueueClient(self.redis).enqueue(job_payload, priority=priority)
                    reaped_count += 1
                    reaped_job_ids.append(job_id)

                self.redis.delete(lk)
                if worker_id:
                    self.redis.delete(f"blast_ocr:worker:{worker_id}:current_job")

        # 2. Check Worker Registry (blast_ocr:workers_registry)
        registry = self.redis.hgetall("blast_ocr:workers_registry") or {}
        for worker_id, last_seen_raw in registry.items():
            w_id = worker_id.decode("utf-8") if isinstance(worker_id, bytes) else str(worker_id)
            try:
                last_seen = float(last_seen_raw)
            except (ValueError, TypeError):
                continue

            if (now - last_seen) > self.grace_sec:
                # Stale worker detected
                job_key = f"blast_ocr:worker:{w_id}:current_job"
                raw_job = self.redis.get(job_key)
                if raw_job:
                    try:
                        job_data = json.loads(raw_job) if isinstance(raw_job, str) else json.loads(raw_job.decode("utf-8"))
                        job_id = str(job_data.get("job_id"))
                        if job_id and job_id not in seen_job_ids:
                            seen_job_ids.add(job_id)
                            reap_count = job_data.get("reap_count", 0) + 1
                            job_data["reap_count"] = reap_count
                            job_data["last_reaped_at"] = now

                            if reap_count > self.MAX_REAP_ATTEMPTS:
                                # Escalate to DLQ
                                self.redis.rpush(self.DLQ_KEY, json.dumps(job_data))
                                dlq_count += 1
                                reaped_job_ids.append(job_id)
                            else:
                                if self.queue_client:
                                    self.queue_client.enqueue(job_data, priority="high")
                                elif self.queue_manager:
                                    self.queue_manager.enqueue(
                                        job_id=job_id,
                                        source_path=job_data.get("source_path", ""),
                                        priority="high",
                                    )
                                else:
                                    from blast_ocr.queue.client import QueueClient
                                    QueueClient(self.redis).enqueue(job_data, priority="high")
                                reaped_count += 1
                                reaped_job_ids.append(job_id)
                    except Exception:
                        # Malformed job payload -> quarantine to DLQ
                        self.redis.rpush(self.DLQ_KEY, str(raw_job))
                        dlq_count += 1

                    self.redis.delete(job_key)

                # Cleanup stale worker entries
                self.redis.hdel("blast_ocr:workers_registry", w_id)
                self.redis.delete(f"blast_ocr:worker:{w_id}")
                self.redis.delete(f"blast_ocr:workers:{w_id}")
                self.redis.srem("blast_ocr:workers:active", w_id)

        # 3. Process any matured delayed retry jobs
        try:
            from blast_ocr.queue.tasks import BackoffDLQHandler
            promoted = BackoffDLQHandler(self.redis).process_delayed_jobs(self.queue_manager)
            if promoted > 0:
                logger.info(f"Reaper promoted {promoted} delayed retry jobs back to active queues")
        except Exception as e:
            logger.debug(f"Delayed jobs processing in reaper encountered error: {e}")

        return ReaperResult(
            reaped_ids=reaped_job_ids,
            reaped_count=reaped_count,
            dlq_count=dlq_count,
            checked_leases=len(lease_keys),
        )


ZombieJobReaper = ZombieReaper

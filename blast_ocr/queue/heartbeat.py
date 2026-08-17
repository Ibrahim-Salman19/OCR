"""
blast_ocr.queue.heartbeat

Worker Heartbeat Daemon and Fleet Registry.
Reports telemetry (CPU, RSS memory, active jobs, uptime) to Redis keys with TTL
and maintains the active swarm worker registry.
"""

import json
import logging
import os
import threading
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class HeartbeatDaemon:
    """
    Lightweight background daemon thread running inside each worker process.
    Periodically refreshes worker heartbeat and telemetry in Redis with TTL.
    """

    DEFAULT_KEY_PREFIX = "blast_ocr:workers:"

    def __init__(
        self,
        redis_client,
        worker_id: str,
        ttl_seconds: int = 30,
        interval_seconds: float = 5.0,
        ttl_sec: Optional[int] = None,
        interval_sec: Optional[float] = None,
        queues: Optional[List[str]] = None,
        key_prefix: Optional[str] = None,
    ):
        actual_interval = interval_sec if interval_sec is not None else interval_seconds
        if actual_interval <= 0:
            raise ValueError("Heartbeat interval must be strictly positive (> 0s).")

        self.redis = redis_client
        self.worker_id = worker_id
        self.ttl = ttl_sec if ttl_sec is not None else ttl_seconds
        self.interval = actual_interval
        self.queues = queues or ["blast_ocr:queue:high", "blast_ocr:queue:default", "blast_ocr:queue:low"]

        if key_prefix:
            self.key_prefix = key_prefix
        elif ttl_sec is not None or interval_sec is not None:
            self.key_prefix = "blast_ocr:worker:"
        else:
            self.key_prefix = self.DEFAULT_KEY_PREFIX

        self.status = "idle"
        self.active_job_id = None
        self.current_page = None
        self.total_pages = None
        self.start_time = time.time()
        self.jobs_processed_total = 0
        self.jobs_failed_total = 0
        self._running = False
        self._thread: Optional[threading.Thread] = None

    @property
    def worker_key(self) -> str:
        return f"{self.key_prefix}{self.worker_id}"

    def send_heartbeat(
        self,
        cpu_percent: Optional[float] = None,
        rss_bytes: Optional[int] = None,
        active_job_id: Optional[str] = None,
    ) -> bool:
        """Publishes heartbeat payload and updates Redis TTLs and registry."""
        if not self.redis:
            return False

        if active_job_id is not None:
            self.active_job_id = str(active_job_id)
            self.status = "busy"

        # Collect CPU percent if not provided
        if cpu_percent is None:
            try:
                import psutil
                cpu_val = float(psutil.cpu_percent(interval=None))
            except Exception:
                cpu_val = 0.0
        else:
            cpu_val = float(cpu_percent)
        cpu_val = max(0.0, min(100.0, cpu_val))

        # Collect RSS memory if not provided
        if rss_bytes is None:
            try:
                import psutil
                rss_val = int(psutil.Process().memory_info().rss)
            except Exception:
                rss_val = 0
        else:
            rss_val = max(0, int(rss_bytes))

        rss_mb = round(rss_val / (1024 * 1024), 2)
        now = time.time()

        payload = {
            "worker_id": self.worker_id,
            "hostname": os.uname().nodename if hasattr(os, "uname") else "localhost",
            "pid": os.getpid(),
            "status": self.status,
            "active_job_id": self.active_job_id,
            "current_page": self.current_page,
            "total_pages": self.total_pages,
            "uptime_sec": int(now - self.start_time),
            "last_heartbeat": now,
            "timestamp": now,
            "cpu_percent": cpu_val,
            "rss_bytes": rss_val,
            "memory_rss_mb": rss_mb,
            "queues": self.queues,
            "jobs_processed_total": self.jobs_processed_total,
            "jobs_failed_total": self.jobs_failed_total,
        }

        payload_json = json.dumps(payload)
        try:
            self.redis.set(self.worker_key, payload_json, ex=self.ttl)
            self.redis.hset("blast_ocr:workers_registry", self.worker_id, now)
            self.redis.sadd("blast_ocr:workers:active", self.worker_id)
            return True
        except Exception as e:
            logger.debug(f"Failed to publish heartbeat for {self.worker_id}: {e}")
            return False

    def get_status(self) -> Optional[Dict[str, Any]]:
        """Reads worker status payload from Redis."""
        if not self.redis:
            return None
        raw = None
        try:
            raw = self.redis.get(self.worker_key)
        except Exception:
            return None
        if not raw:
            return None
        try:
            return json.loads(raw) if isinstance(raw, str) else json.loads(raw.decode("utf-8"))
        except Exception:
            return None

    def start(self):
        """Starts background heartbeat sender loop."""
        self._running = True
        self.send_heartbeat()
        self._thread = threading.Thread(target=self._heartbeat_loop, daemon=True, name=f"heartbeat-{self.worker_id}")
        self._thread.start()

    def _heartbeat_loop(self):
        while self._running:
            time.sleep(self.interval)
            if self._running:
                self.send_heartbeat()

    def stop(self, timeout: float = 2.0):
        """Stops background loop and cleans up keys."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=timeout)
        if self.redis:
            try:
                self.redis.delete(self.worker_key)
                self.redis.hdel("blast_ocr:workers_registry", self.worker_id)
                self.redis.srem("blast_ocr:workers:active", self.worker_id)
            except Exception:
                pass

    def set_busy(self, job_id: Any, current_page: Optional[int] = None, total_pages: Optional[int] = None):
        """Transitions status to busy."""
        self.status = "busy"
        self.active_job_id = str(job_id) if job_id is not None else None
        self.current_page = current_page
        self.total_pages = total_pages
        self.send_heartbeat()

    def set_idle(self):
        """Transitions status to idle."""
        self.status = "idle"
        self.active_job_id = None
        self.current_page = None
        self.total_pages = None
        self.send_heartbeat()

    def set_draining(self):
        """Transitions status to draining."""
        self.status = "draining"
        self.send_heartbeat()

    def record_job_completed(self):
        """Increments completed jobs counter."""
        self.jobs_processed_total += 1
        self.set_idle()

    def record_job_failed(self):
        """Increments failed jobs counter."""
        self.jobs_failed_total += 1
        self.set_idle()


WorkerHeartbeatDaemon = HeartbeatDaemon


class WorkerRegistry:
    """
    Registry for inspecting live swarm workers and querying fleet health.
    """

    KEY_PREFIX = "blast_ocr:workers:"

    def __init__(self, redis_client=None):
        if redis_client is None:
            try:
                from blast_ocr.queue.client import get_redis_connection
                self.redis = get_redis_connection()
            except Exception:
                self.redis = None
        else:
            self.redis = redis_client

    def list_active_workers(self) -> List[Dict[str, Any]]:
        """Discovers all currently registered active swarm workers."""
        if not self.redis:
            return []

        workers_map = {}
        # 1. Scan primary keys and alternate prefix keys
        if hasattr(self.redis, "scan_iter"):
            keys = list(self.redis.scan_iter(f"{self.KEY_PREFIX}*")) + list(self.redis.scan_iter("blast_ocr:worker:*"))
        else:
            keys = list(self.redis.keys(f"{self.KEY_PREFIX}*")) + list(self.redis.keys("blast_ocr:worker:*"))
        for k in keys:
            k_str = k.decode("utf-8") if isinstance(k, bytes) else str(k)
            # Skip registry collections and current_job keys
            if (
                k_str in ("blast_ocr:workers:active", "blast_ocr:workers_registry")
                or k_str.endswith(":current_job")
                or k_str.endswith(":active")
            ):
                continue

            try:
                raw = self.redis.get(k)
                if raw:
                    data = json.loads(raw) if isinstance(raw, str) else json.loads(raw.decode("utf-8"))
                    w_id = data.get("worker_id")
                    if w_id:
                        workers_map[w_id] = data
            except Exception:
                pass
        return list(workers_map.values())

    def get_worker(self, worker_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves info dictionary for a specific worker ID."""
        if not self.redis:
            return None
        key = f"{self.KEY_PREFIX}{worker_id}"
        alt_key = f"blast_ocr:worker:{worker_id}"
        raw = None
        try:
            raw = self.redis.get(key) or self.redis.get(alt_key)
        except Exception:
            return None
        if not raw:
            return None
        try:
            return json.loads(raw) if isinstance(raw, str) else json.loads(raw.decode("utf-8"))
        except Exception:
            return None

    def remove_worker(self, worker_id: str):
        """Deregisters a worker."""
        if self.redis:
            self.redis.delete(f"{self.KEY_PREFIX}{worker_id}")
            self.redis.delete(f"blast_ocr:worker:{worker_id}")
            self.redis.hdel("blast_ocr:workers_registry", worker_id)
            self.redis.srem("blast_ocr:workers:active", worker_id)

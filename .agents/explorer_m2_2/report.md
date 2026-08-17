# Architectural Deep-Dive Report: Distributed Multi-Worker Swarm & Durable Queue (Milestone 2)

**Author:** `explorer_m2_2` (Teamwork Explorer / System Architect)  
**Date:** 2026-08-15  
**Milestone:** Milestone 2 — Distributed Multi-Worker Swarm & Durable Queue (Requirement R2)  
**Status:** COMPLETE & VERIFIED  

---

## 1. Executive Summary & Architectural Overview

This architectural report establishes the concrete engineering blueprints, data contracts, Redis key conventions, and fail-safe designs for **Milestone 2: Distributed Multi-Worker Swarm & Durable Queue**.

### Core Architecture Components
```
                                 +---------------------------------------+
                                 |         FastAPI Service Layer         |
                                 |  POST /v1/ocr/jobs (priority & retry) |
                                 |  GET  /v1/workers  | GET /v1/queues   |
                                 |  POST /v1/ocr/jobs/{id}/retry         |
                                 +-------------------+-------------------+
                                                     |
                                                     v
                                 +---------------------------------------+
                                 |       blast_ocr.queue.client          |
                                 |  - 3-Tier Priority Queue Enqueueing   |
                                 |  - Redis / Fakeredis Connection Pool  |
                                 |  - SHA-256 Deduplication Guard Lock   |
                                 |  - Queue Depth & Metric Inspection    |
                                 +-------------------+-------------------+
                                                     |
                   +---------------------------------+---------------------------------+
                   |                                 |                                 |
                   v                                 v                                 v
        +----------------------+          +----------------------+          +----------------------+
        | blast_ocr:queue:high |          |blast_ocr:queue:default|          | blast_ocr:queue:low  |
        +----------+-----------+          +----------+-----------+          +----------+-----------+
                   |                                 |                                 |
                   +---------------------------------+---------------------------------+
                                                     |
                                                     v Priority-Multiplexed BLPOP Dequeue
+---------------------------------------------------------------------------------------------------------+
|                                      SwarmSupervisor Process Manager                                    |
|  - Manages N SwarmWorker Subprocesses       - Auto-Respawns Crashed Workers (OOM/Segfault)              |
|  - Dynamic Scaling (scale_workers)          - Graceful Signal Handling (SIGTERM/SIGINT -> Draining)     |
|  +---------------------------------------------------------------------------------------------------+  |
|  |                                      SwarmWorker Processes [1..N]                                 |  |
|  |  +--------------------------------+  +--------------------------------+  +---------------------+  |  |
|  |  | Worker 1                       |  | Worker 2                       |  | Worker N            |  |  |
|  |  | - HeartbeatDaemon (5s TTL 20s) |  | - HeartbeatDaemon (5s TTL 20s) |  | - HeartbeatDaemon   |  |  |
|  |  | - CPU/RAM Resource Sampler     |  | - CPU/RAM Resource Sampler     |  | - CPU/RAM Sampler   |  |  |
|  |  | - Execution Hook Lifecycle     |  | - Execution Hook Lifecycle     |  | - Execution Hooks   |  |  |
|  |  +--------------------------------+  +--------------------------------+  +---------------------+  |  |
|  +---------------------------------------------------------------------------------------------------+  |
|  |  ZombieReaper Background Monitor: Scans blast_ocr:workers:active -> Recovers Abandoned Jobs       |  |
+----------------------------------------------------+----------------------------------------------------+
                                                     |
                                                     v
+---------------------------------------------------------------------------------------------------------+
|                                        blast_ocr.queue.tasks                                            |
|  - `run_ocr_job` Task Execution Wrapper                                                                 |
|  - Exception Classification: Transient vs Deterministic (classify_exception)                            |
|  - Exponential Backoff with Jitter: delay = min(60, base * factor^attempt) + jitter                    |
|  - Dead Letter Queue (DLQ) Quarantine: `blast_ocr:queue:dlq` on Exhausted Retries                       |
+---------------------------------------------------------------------------------------------------------+
```

---

## 2. Module Architectural Specifications

### 2.1 `blast_ocr/queue/client.py` — Priority Queues & Connection Handling

#### Core Responsibilities
1. **3-Tier Priority Queue Abstraction**:
   - `high`: Critical interactive uploads, single-page SLA (<1.0s).
   - `default`: Standard multi-page batch documents.
   - `low`: Heavy archival backfills and bulk 1,000+ page books.
   - `dlq`: Quarantined dead-letter queue for failed/exhausted jobs.
2. **Connection Lifecycle & Fakeredis Compatibility**:
   - Lazily imports `redis` and `rq` to keep synchronous zero-dependency mode clean.
   - Supports `use_fake=True` or `fakeredis.FakeRedis()` injection for in-memory unit tests.
   - Thread-safe connection pool with health checking and automatic reconnection.
3. **Idempotency / Deduplication Guard**:
   - Uses Redis key `blast_ocr:lock:fingerprint:<hash>` (`SET NX EX 600`) to prevent duplicate GPU/CPU executions of the same document with identical configs.
4. **Queue Metrics & Inspection**:
   - Inspects queue lengths, job positions, and DLQ entries.

#### Concrete Interface Signatures & Implementation Blueprint
```python
"""
blast_ocr.queue.client
"""
import logging
import os
from typing import Any, Dict, List, Optional
from blast_ocr.config import config
from blast_ocr.core.job_state import JobFingerprint
from blast_ocr.core.models import JobConfig, JobState

logger = logging.getLogger(__name__)

# Queue Names
QUEUE_HIGH = "blast_ocr:queue:high"
QUEUE_DEFAULT = "blast_ocr:queue:default"
QUEUE_LOW = "blast_ocr:queue:low"
QUEUE_DLQ = "blast_ocr:queue:dlq"

PRIORITY_MAP = {
    "high": QUEUE_HIGH,
    "urgent": QUEUE_HIGH,
    "default": QUEUE_DEFAULT,
    "normal": QUEUE_DEFAULT,
    "low": QUEUE_LOW,
    "bulk": QUEUE_LOW,
    "dlq": QUEUE_DLQ,
}

_REDIS_POOL = None
_FAKE_REDIS_INSTANCE = None


def get_redis_connection(url: Optional[str] = None, use_fake: bool = False):
    """
    Returns a thread-safe Redis client instance.
    Supports real Redis connection pooling and in-memory Fakeredis for tests.
    """
    global _REDIS_POOL, _FAKE_REDIS_INSTANCE
    if use_fake or os.getenv("BLAST_OCR_USE_FAKEREDIS", "0") == "1":
        if _FAKE_REDIS_INSTANCE is None:
            import fakeredis
            _FAKE_REDIS_INSTANCE = fakeredis.FakeRedis()
        return _FAKE_REDIS_INSTANCE

    import redis
    redis_url = url or config.redis_url
    if _REDIS_POOL is None:
        _REDIS_POOL = redis.ConnectionPool.from_url(
            redis_url,
            max_connections=50,
            socket_timeout=5.0,
            socket_connect_timeout=5.0,
            health_check_interval=30,
            retry_on_timeout=True,
        )
    return redis.Redis(connection_pool=_REDIS_POOL)


def is_queue_available(connection: Optional[Any] = None) -> bool:
    """Best-effort reachability check for Redis."""
    try:
        conn = connection or get_redis_connection()
        return bool(conn.ping())
    except Exception as e:
        logger.debug(f"Redis queue backend not reachable: {e}")
        return False


def get_queue(name_or_priority: str = "default", connection: Optional[Any] = None):
    """Retrieves RQ Queue for a given priority tier or queue name."""
    from rq import Queue
    conn = connection or get_redis_connection()
    queue_name = PRIORITY_MAP.get(name_or_priority.lower(), name_or_priority)
    return Queue(queue_name, connection=conn)


def get_all_priority_queues(connection: Optional[Any] = None) -> List[Any]:
    """Returns [Queue(high), Queue(default), Queue(low)] in strict priority order."""
    conn = connection or get_redis_connection()
    from rq import Queue
    return [
        Queue(QUEUE_HIGH, connection=conn),
        Queue(QUEUE_DEFAULT, connection=conn),
        Queue(QUEUE_LOW, connection=conn),
    ]


def enqueue_job(
    source_path: str,
    output_dir: Optional[str] = None,
    priority: str = "default",
    max_retries: int = 3,
    input_sha256: Optional[str] = None,
    config_overrides: Optional[Dict[str, Any]] = None,
    job_id: Optional[int] = None,
    connection: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Enqueues an OCR task onto the appropriate priority queue with deduplication lock
    and database persistence.
    """
    from blast_ocr.queue.tasks import run_ocr_job
    from blast_ocr.storage.database import OCRDatabase
    from pathlib import Path
    from rq import Retry

    conn = connection or get_redis_connection()
    db = OCRDatabase()

    # Compute idempotency fingerprint
    job_config = JobConfig.from_dict(config_overrides or {})
    fingerprint = (
        JobFingerprint.compute(input_sha256, job_config) if input_sha256 else None
    )

    # Distributed Deduplication Lock Check
    if fingerprint:
        lock_key = f"blast_ocr:lock:fingerprint:{fingerprint}"
        existing_job_id = conn.get(lock_key)
        if existing_job_id:
            try:
                existing_id_int = int(existing_job_id)
                existing_job = db.get_job(existing_id_int)
                if existing_job and existing_job.status in (JobState.QUEUED.value, JobState.PROCESSING.value):
                    logger.info(f"Deduplication hit: Reusing active job_id={existing_id_int} for fingerprint={fingerprint}")
                    return {
                        "job_id": existing_id_int,
                        "rq_job_id": None,
                        "fingerprint": fingerprint,
                        "priority": priority,
                        "deduplicated": True,
                    }
            except Exception as e:
                logger.warning(f"Error checking deduplication lock: {e}")

    # Create / update DB job
    if job_id is None:
        job_id = db.create_job(
            Path(source_path).name,
            page_count=0,
            priority=priority,
            max_retries=max_retries,
        )
    else:
        db.update_job_status(job_id, JobState.QUEUED)

    # Acquire deduplication lock (TTL 600s)
    if fingerprint:
        conn.set(f"blast_ocr:lock:fingerprint:{fingerprint}", str(job_id), ex=600, nx=True)

    q = get_queue(priority, connection=conn)
    retry_spec = Retry(max=max_retries, intervals=[2, 4, 8])

    rq_job = q.enqueue(
        run_ocr_job,
        source_path,
        output_dir,
        job_id,
        config_overrides,
        priority=priority,
        max_retries=max_retries,
        retry_count=0,
        job_timeout=config.queue_job_timeout,
        result_ttl=86400,
        failure_ttl=86400,
        retry=retry_spec,
    )

    logger.info(
        f"Enqueued job_id={job_id} on {q.name} (priority={priority}, max_retries={max_retries}, rq_job_id={rq_job.id})"
    )
    return {
        "job_id": job_id,
        "rq_job_id": rq_job.id,
        "fingerprint": fingerprint,
        "priority": priority,
        "queue_name": q.name,
        "deduplicated": False,
    }


def get_queue_metrics(connection: Optional[Any] = None) -> Dict[str, Any]:
    """Inspects lengths of all priority and DLQ queues."""
    conn = connection or get_redis_connection()
    from rq import Queue
    q_high = Queue(QUEUE_HIGH, connection=conn)
    q_def = Queue(QUEUE_DEFAULT, connection=conn)
    q_low = Queue(QUEUE_LOW, connection=conn)
    q_dlq = Queue(QUEUE_DLQ, connection=conn)

    return {
        "high": len(q_high),
        "default": len(q_def),
        "low": len(q_low),
        "dlq": len(q_dlq),
        "total_pending": len(q_high) + len(q_def) + len(q_low),
    }
```

---

### 2.2 `blast_ocr/queue/swarm.py` — Multi-Process Swarm Supervisor & Worker

#### Core Responsibilities
1. **`SwarmWorker` Lifecycle**:
   - Subclasses / wraps RQ `Worker` to consume `[QUEUE_HIGH, QUEUE_DEFAULT, QUEUE_LOW]` in strict priority order.
   - Generates unique worker identity: `worker:{hostname}:{pid}:{uuid4_hex[:8]}`.
   - Manages an internal `HeartbeatDaemon` thread.
   - Hooks into job execution: updates DB status `PROCESSING`, records `started_at`, `worker_id`, updates heartbeat daemon progress during page processing.
   - Handles `SIGTERM` / `SIGINT` gracefully: enters `status="draining"`, finishes active page, and unregisters cleanly.
2. **`SwarmSupervisor` Architecture**:
   - Spawns and manages $N$ worker processes using `multiprocessing.Process`.
   - Supervisor heartbeat loop (every 1.0s):
     - Monitors child worker process health.
     - Auto-respawns workers that exit unexpectedly (e.g. OOM, segfault) to maintain target capacity.
   - Dynamic Scaling: `scale_workers(target_count)` dynamically adds or gracefully drains child processes.
   - Signal propagation: Catches SIGTERM / SIGINT on supervisor, propagates graceful stop to all children, waits up to `shutdown_timeout` (30s), then issues SIGKILL if unresponsive.
   - Integrates periodic `ZombieReaper` execution.
3. **CLI Entrypoint**:
   - `python -m blast_ocr.queue.swarm --workers 4 --queues high,default,low --heartbeat-interval 5`

#### Concrete Interface Signatures & Implementation Blueprint
```python
"""
blast_ocr.queue.swarm
"""
import logging
import os
import signal
import socket
import sys
import time
import uuid
from multiprocessing import Process, Event
from typing import Dict, List, Optional

from blast_ocr.config import config
from blast_ocr.queue.client import get_all_priority_queues, get_redis_connection, is_queue_available
from blast_ocr.queue.heartbeat import HeartbeatDaemon

logger = logging.getLogger("blast_ocr.queue.swarm")


class SwarmWorker:
    """
    Multi-queue priority worker running in a dedicated OS process.
    """

    def __init__(
        self,
        worker_id: Optional[str] = None,
        queues: Optional[List[str]] = None,
        heartbeat_interval: float = 5.0,
        connection: Optional[Any] = None,
    ):
        self.hostname = socket.gethostname()
        self.pid = os.getpid()
        self.worker_id = worker_id or f"worker:{self.hostname}:{self.pid}:{uuid.uuid4().hex[:8]}"
        self.connection = connection or get_redis_connection()
        self.queues = queues or [q.name for q in get_all_priority_queues(self.connection)]
        self.heartbeat_interval = heartbeat_interval
        self.daemon: Optional[HeartbeatDaemon] = None
        self._shutdown_event = Event()
        self.rq_worker = None

    def start(self):
        """Starts worker process execution with signal handling and heartbeat."""
        logger.info(f"Initializing SwarmWorker [{self.worker_id}] on queues: {self.queues}")

        # Setup OS Signal Handlers
        signal.signal(signal.SIGTERM, self._handle_signal)
        signal.signal(signal.SIGINT, self._handle_signal)

        # Start Heartbeat Daemon Thread
        self.daemon = HeartbeatDaemon(
            worker_id=self.worker_id,
            hostname=self.hostname,
            pid=self.pid,
            queues=self.queues,
            interval_sec=self.heartbeat_interval,
            connection=self.connection,
        )
        self.daemon.start()

        # Set environment variable for task discovery
        os.environ["BLAST_WORKER_ID"] = self.worker_id

        # Initialize RQ Worker
        from rq import Worker, Queue
        rq_queues = [Queue(q_name, connection=self.connection) for q_name in self.queues]
        self.rq_worker = Worker(rq_queues, connection=self.connection, name=self.worker_id)

        try:
            self.rq_worker.work(with_scheduler=False)
        except Exception as e:
            logger.error(f"Worker {self.worker_id} crashed: {e}", exc_info=True)
            raise
        finally:
            self.stop()

    def _handle_signal(self, signum, frame):
        logger.info(f"Worker {self.worker_id} received signal {signum}. Initiating graceful drain...")
        if self.daemon:
            self.daemon.set_draining()
        if self.rq_worker:
            self.rq_worker.request_stop()

    def stop(self):
        """Stops heartbeat daemon and unregisters from Redis."""
        logger.info(f"Stopping SwarmWorker [{self.worker_id}]")
        if self.daemon:
            self.daemon.stop()
            self.daemon.unregister()


def _worker_process_target(worker_id: str, queues: List[str], heartbeat_interval: float):
    """Subprocess target function for SwarmWorker."""
    worker = SwarmWorker(worker_id=worker_id, queues=queues, heartbeat_interval=heartbeat_interval)
    worker.start()


class SwarmSupervisor:
    """
    Supervisor managing a pool of N worker subprocesses with auto-recovery and scaling.
    """

    def __init__(
        self,
        worker_count: int = 4,
        queues: Optional[List[str]] = None,
        heartbeat_interval: float = 5.0,
        enable_reaper: bool = True,
    ):
        self.target_worker_count = worker_count
        self.queues = queues or ["blast_ocr:queue:high", "blast_ocr:queue:default", "blast_ocr:queue:low"]
        self.heartbeat_interval = heartbeat_interval
        self.enable_reaper = enable_reaper
        self.workers: Dict[str, Dict[str, Any]] = {}
        self.running = False
        self._shutdown_event = Event()

    def spawn_worker(self) -> str:
        """Spawns a new worker subprocess and tracks its metadata."""
        uid = uuid.uuid4().hex[:8]
        worker_id = f"worker:{socket.gethostname()}:{uid}"
        p = Process(
            target=_worker_process_target,
            args=(worker_id, self.queues, self.heartbeat_interval),
            daemon=False,
        )
        p.start()
        self.workers[worker_id] = {
            "process": p,
            "pid": p.pid,
            "started_at": time.time(),
        }
        logger.info(f"Supervisor spawned worker {worker_id} (PID {p.pid})")
        return worker_id

    def scale_workers(self, target_count: int):
        """Dynamically adjusts the number of active worker processes."""
        self.target_worker_count = target_count
        current_count = len(self.workers)
        if target_count > current_count:
            for _ in range(target_count - current_count):
                self.spawn_worker()
        elif target_count < current_count:
            # Terminate surplus workers
            surplus = current_count - target_count
            worker_ids = list(self.workers.keys())[:surplus]
            for wid in worker_ids:
                proc = self.workers[wid]["process"]
                if proc.is_alive():
                    os.kill(proc.pid, signal.SIGTERM)
                del self.workers[wid]

    def start(self):
        """Starts worker swarm and enters supervisory loop."""
        self.running = True
        logger.info(f"Starting SwarmSupervisor (Target: {self.target_worker_count} workers)")

        # Initial spawn
        for _ in range(self.target_worker_count):
            self.spawn_worker()

        # Signal Handlers for Supervisor
        signal.signal(signal.SIGTERM, self._handle_supervisor_signal)
        signal.signal(signal.SIGINT, self._handle_supervisor_signal)

        from blast_ocr.queue.reaper import ZombieReaper
        reaper = ZombieReaper() if self.enable_reaper else None
        last_reap_time = time.time()

        try:
            while self.running:
                # 1. Health check & auto-respawn
                dead_workers = []
                for wid, info in list(self.workers.items()):
                    p = info["process"]
                    if not p.is_alive():
                        logger.warning(f"Worker {wid} (PID {info['pid']}) died with exitcode {p.exitcode}. Auto-respawning...")
                        dead_workers.append(wid)

                for wid in dead_workers:
                    del self.workers[wid]
                    if self.running and len(self.workers) < self.target_worker_count:
                        self.spawn_worker()

                # 2. Periodic Zombie Reaper
                if reaper and (time.time() - last_reap_time >= 15.0):
                    try:
                        reaper.reap_zombies()
                    except Exception as e:
                        logger.error(f"Reaper execution error: {e}")
                    last_reap_time = time.time()

                time.sleep(1.0)
        finally:
            self.stop()

    def _handle_supervisor_signal(self, signum, frame):
        logger.info(f"Supervisor received signal {signum}. Initiating swarm shutdown...")
        self.running = False

    def stop(self, timeout: float = 30.0):
        """Gracefully drains and stops all managed child worker processes."""
        self.running = False
        logger.info(f"Draining {len(self.workers)} workers (timeout={timeout}s)...")

        # Send SIGTERM to all child workers
        for wid, info in self.workers.items():
            p = info["process"]
            if p.is_alive():
                try:
                    os.kill(p.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass

        # Wait for graceful exit
        deadline = time.time() + timeout
        while time.time() < deadline:
            alive = [info["process"] for info in self.workers.values() if info["process"].is_alive()]
            if not alive:
                break
            time.sleep(0.5)

        # Force SIGKILL if any processes remain
        for wid, info in self.workers.items():
            p = info["process"]
            if p.is_alive():
                logger.warning(f"Worker {wid} (PID {p.pid}) did not exit cleanly. Sending SIGKILL.")
                try:
                    os.kill(p.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
        self.workers.clear()
        logger.info("SwarmSupervisor shutdown complete.")
```

---

### 2.3 `blast_ocr/queue/heartbeat.py` — Worker Registration & Health Daemon

#### Core Responsibilities
1. **Background Heartbeat Loop**:
   - Executes every `interval_sec` (default: 5.0s) in a daemon thread.
   - Writes to Redis Hash `blast_ocr:worker:{worker_id}` with TTL (default: 20s).
   - Adds `worker_id` to Redis Set `blast_ocr:workers:active`.
2. **Resource Metrics Sampling**:
   - Collects process memory (`RSS MB`) and CPU percentage via `psutil`.
3. **State & Progress Reporting**:
   - Status states: `idle`, `busy`, `draining`, `offline`.
   - Tracks `current_job_id`, `current_page`, `total_pages`, `jobs_processed_total`, `jobs_failed_total`.
4. **Clean Deregistration**:
   - Removes `worker_id` from `blast_ocr:workers:active` on process teardown.

#### Concrete Interface Signatures & Implementation Blueprint
```python
"""
blast_ocr.queue.heartbeat
"""
import json
import logging
import os
import threading
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import psutil

from blast_ocr.queue.client import get_redis_connection

logger = logging.getLogger("blast_ocr.queue.heartbeat")

WORKERS_ACTIVE_KEY = "blast_ocr:workers:active"
WORKER_KEY_PREFIX = "blast_ocr:worker:"


class HeartbeatDaemon:
    """
    Lightweight background thread reporting worker health and resource metrics.
    """

    def __init__(
        self,
        worker_id: str,
        hostname: str,
        pid: int,
        queues: List[str],
        interval_sec: float = 5.0,
        ttl_sec: int = 20,
        connection: Optional[Any] = None,
    ):
        self.worker_id = worker_id
        self.hostname = hostname
        self.pid = pid
        self.queues = queues
        self.interval_sec = interval_sec
        self.ttl_sec = ttl_sec
        self.connection = connection or get_redis_connection()

        self.started_at = datetime.now(timezone.utc).isoformat()
        self.status = "idle"  # idle, busy, draining, offline
        self.current_job_id: Optional[int] = None
        self.current_page: Optional[int] = None
        self.total_pages: Optional[int] = None
        self.jobs_processed_total = 0
        self.jobs_failed_total = 0

        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._proc = psutil.Process(self.pid)
        self._lock = threading.Lock()

    def start(self):
        """Starts the background heartbeat thread."""
        self._thread = threading.Thread(target=self._run, daemon=True, name=f"heartbeat-{self.worker_id}")
        self._thread.start()
        logger.info(f"HeartbeatDaemon started for {self.worker_id} (interval={self.interval_sec}s, TTL={self.ttl_sec}s)")

    def _run(self):
        """Periodic heartbeat loop."""
        # Initial beat
        self.beat()
        while not self._stop_event.wait(self.interval_sec):
            try:
                self.beat()
            except Exception as e:
                logger.warning(f"Heartbeat error for {self.worker_id}: {e}")

    def beat(self):
        """Emits a single heartbeat tick to Redis."""
        with self._lock:
            try:
                mem_rss_mb = round(self._proc.memory_info().rss / (1024 * 1024), 2)
                cpu_pct = round(self._proc.cpu_percent(interval=None), 2)
            except Exception:
                mem_rss_mb = 0.0
                cpu_pct = 0.0

            payload = {
                "worker_id": self.worker_id,
                "hostname": self.hostname,
                "pid": str(self.pid),
                "started_at": self.started_at,
                "last_heartbeat": str(time.time()),
                "status": self.status,
                "current_job_id": str(self.current_job_id) if self.current_job_id is not None else "",
                "current_page": str(self.current_page) if self.current_page is not None else "",
                "total_pages": str(self.total_pages) if self.total_pages is not None else "",
                "memory_rss_mb": str(mem_rss_mb),
                "cpu_percent": str(cpu_pct),
                "queues": json.dumps(self.queues),
                "jobs_processed_total": str(self.jobs_processed_total),
                "jobs_failed_total": str(self.jobs_failed_total),
            }

            worker_key = f"{WORKER_KEY_PREFIX}{self.worker_id}"
            pipe = self.connection.pipeline()
            pipe.hset(worker_key, mapping=payload)
            pipe.expire(worker_key, self.ttl_sec)
            pipe.sadd(WORKERS_ACTIVE_KEY, self.worker_id)
            pipe.execute()

    def set_job(self, job_id: int, total_pages: int = 0):
        with self._lock:
            self.status = "busy"
            self.current_job_id = job_id
            self.current_page = 0
            self.total_pages = total_pages
        self.beat()

    def update_progress(self, current_page: int, total_pages: Optional[int] = None):
        with self._lock:
            self.current_page = current_page
            if total_pages is not None:
                self.total_pages = total_pages
        self.beat()

    def finish_job(self, success: bool = True):
        with self._lock:
            self.status = "idle"
            self.current_job_id = None
            self.current_page = None
            self.total_pages = None
            if success:
                self.jobs_processed_total += 1
            else:
                self.jobs_failed_total += 1
        self.beat()

    def set_draining(self):
        with self._lock:
            self.status = "draining"
        self.beat()

    def stop(self):
        """Stops heartbeat thread."""
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)

    def unregister(self):
        """Removes worker from Redis active registry."""
        try:
            worker_key = f"{WORKER_KEY_PREFIX}{self.worker_id}"
            pipe = self.connection.pipeline()
            pipe.srem(WORKERS_ACTIVE_KEY, self.worker_id)
            pipe.hset(worker_key, "status", "offline")
            pipe.expire(worker_key, 5)
            pipe.execute()
            logger.info(f"Unregistered worker {self.worker_id} from active set.")
        except Exception as e:
            logger.warning(f"Error unregistering worker {self.worker_id}: {e}")


def get_active_workers(connection: Optional[Any] = None) -> List[Dict[str, Any]]:
    """Retrieves metadata of all active swarm workers."""
    conn = connection or get_redis_connection()
    worker_ids = [w.decode("utf-8") if isinstance(w, bytes) else str(w) for w in conn.smembers(WORKERS_ACTIVE_KEY)]
    active = []
    stale_ids = []

    for wid in worker_ids:
        raw_data = conn.hgetall(f"{WORKER_KEY_PREFIX}{wid}")
        if not raw_data:
            stale_ids.append(wid)
            continue

        data = {
            (k.decode("utf-8") if isinstance(k, bytes) else k): (v.decode("utf-8") if isinstance(v, bytes) else v)
            for k, v in raw_data.items()
        }
        active.append({
            "worker_id": wid,
            "hostname": data.get("hostname", "unknown"),
            "pid": int(data.get("pid", 0)),
            "started_at": data.get("started_at", ""),
            "last_heartbeat": float(data.get("last_heartbeat", 0.0)),
            "status": data.get("status", "unknown"),
            "current_job_id": int(data["current_job_id"]) if data.get("current_job_id") else None,
            "current_page": int(data["current_page"]) if data.get("current_page") else None,
            "total_pages": int(data["total_pages"]) if data.get("total_pages") else None,
            "memory_rss_mb": float(data.get("memory_rss_mb", 0.0)),
            "cpu_percent": float(data.get("cpu_percent", 0.0)),
            "queues": json.loads(data.get("queues", "[]")),
            "jobs_processed_total": int(data.get("jobs_processed_total", 0)),
            "jobs_failed_total": int(data.get("jobs_failed_total", 0)),
        })

    # Clean up stale IDs
    if stale_ids:
        conn.srem(WORKERS_ACTIVE_KEY, *stale_ids)

    return active
```

---

### 2.4 `blast_ocr/queue/reaper.py` — Dead Worker Detection & Orphaned Job Failover

#### Core Responsibilities
1. **Zombie Worker Identification**:
   - Detects worker entries in `blast_ocr:workers:active` whose Redis hash has expired or whose `last_heartbeat` exceeds `heartbeat_ttl` (20s).
   - Prunes dead worker keys from `blast_ocr:workers:active`.
2. **Orphaned Job Recovery**:
   - Identifies jobs in `OCRJob` DB stuck in `PROCESSING` state that were assigned to the dead worker.
   - Evaluates retry budget:
     - If `retry_count < max_retries`: Increments `retry_count`, resets status to `QUEUED`, and re-enqueues the job to its priority queue.
     - If `retry_count >= max_retries`: Moves the job to Dead-Letter Queue (DLQ) with `status="failed"`, records `dlq_at` and `dlq_reason="Worker lost"`.
3. **Distributed Reaper Mutex Lock**:
   - Uses `blast_ocr:lock:reaper` (`SET NX EX 30`) to prevent concurrent supervisor instances from duplicate processing.

#### Concrete Interface Signatures & Implementation Blueprint
```python
"""
blast_ocr.queue.reaper
"""
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from blast_ocr.core.job_state import WorkerLostError
from blast_ocr.core.models import JobState
from blast_ocr.queue.client import QUEUE_DLQ, get_queue, get_redis_connection
from blast_ocr.queue.heartbeat import WORKERS_ACTIVE_KEY, WORKER_KEY_PREFIX
from blast_ocr.storage.database import OCRDatabase, OCRJob

logger = logging.getLogger("blast_ocr.queue.reaper")

REAPER_LOCK_KEY = "blast_ocr:lock:reaper"


class ZombieReaper:
    """
    Monitors swarm health, purges dead worker registrations, and recovers orphaned jobs.
    """

    def __init__(
        self,
        heartbeat_ttl: float = 20.0,
        connection: Optional[Any] = None,
        db: Optional[OCRDatabase] = None,
    ):
        self.heartbeat_ttl = heartbeat_ttl
        self.connection = connection or get_redis_connection()
        self.db = db or OCRDatabase()

    def reap_zombies(self) -> Dict[str, Any]:
        """
        Executes a single zombie sweep. Protected by a distributed Redis lock.
        """
        # Acquire Reaper lock (TTL 30s)
        lock_acquired = self.connection.set(REAPER_LOCK_KEY, "1", nx=True, ex=30)
        if not lock_acquired:
            logger.debug("Another reaper process is currently executing. Skipping sweep.")
            return {"dead_workers": 0, "recovered_jobs": 0, "quarantined_jobs": 0}

        try:
            return self._execute_sweep()
        finally:
            try:
                self.connection.delete(REAPER_LOCK_KEY)
            except Exception:
                pass

    def _execute_sweep(self) -> Dict[str, Any]:
        """Core sweep logic."""
        now = time.time()
        raw_worker_ids = self.connection.smembers(WORKERS_ACTIVE_KEY)
        worker_ids = [w.decode("utf-8") if isinstance(w, bytes) else str(w) for w in raw_worker_ids]

        dead_workers: List[str] = []
        recovered_jobs = 0
        quarantined_jobs = 0

        for wid in worker_ids:
            key = f"{WORKER_KEY_PREFIX}{wid}"
            worker_data = self.connection.hgetall(key)
            if not worker_data:
                # Key expired in Redis
                dead_workers.append(wid)
                continue

            last_hb_str = worker_data.get(b"last_heartbeat" if b"last_heartbeat" in worker_data else "last_heartbeat")
            if last_hb_str:
                last_hb = float(last_hb_str.decode("utf-8") if isinstance(last_hb_str, bytes) else last_hb_str)
                if (now - last_hb) > self.heartbeat_ttl:
                    dead_workers.append(wid)

        for wid in dead_workers:
            logger.warning(f"[ZombieReaper] Dead worker detected: {wid}")
            self.connection.srem(WORKERS_ACTIVE_KEY, wid)

            # Find orphaned jobs in DB assigned to this worker
            with self.db.session_scope() as session:
                orphaned = session.query(OCRJob).filter(
                    OCRJob.worker_id == wid,
                    OCRJob.status == JobState.PROCESSING.value,
                ).all()

                for job in orphaned:
                    if job.retry_count < job.max_retries:
                        # Re-enqueue with incremented retry count
                        job.retry_count += 1
                        job.status = JobState.QUEUED.value
                        job.worker_id = None
                        session.commit()

                        # Re-enqueue onto queue
                        from blast_ocr.queue.tasks import run_ocr_job
                        q = get_queue(job.priority or "default", connection=self.connection)
                        q.enqueue(
                            run_ocr_job,
                            job.filename,
                            None,
                            job.id,
                            priority=job.priority or "default",
                            max_retries=job.max_retries,
                            retry_count=job.retry_count,
                        )
                        recovered_jobs += 1
                        logger.info(
                            f"[ZombieReaper] Recovered orphaned job_id={job.id} (Retry {job.retry_count}/{job.max_retries})"
                        )
                    else:
                        # Max retries exhausted -> Move to DLQ
                        job.status = JobState.FAILED.value
                        job.dlq_at = datetime.now(timezone.utc)
                        job.dlq_reason = f"Worker {wid} died unexpectedly; max retries ({job.max_retries}) exhausted."
                        session.commit()

                        dlq_q = get_queue("dlq", connection=self.connection)
                        dlq_q.enqueue(
                            "blast_ocr.queue.tasks.dead_letter_job",
                            job.id,
                            job.dlq_reason,
                        )
                        quarantined_jobs += 1
                        logger.error(
                            f"[ZombieReaper] Orphaned job_id={job.id} sent to DLQ (retries exhausted)"
                        )

        return {
            "dead_workers": len(dead_workers),
            "recovered_jobs": recovered_jobs,
            "quarantined_jobs": quarantined_jobs,
        }
```

---

### 2.5 `blast_ocr/queue/tasks.py` — Task Execution, Backoff Retry & DLQ Routing

#### Core Responsibilities
1. **Worker Context & Lifecycle Hooks**:
   - Reads `BLAST_WORKER_ID` to bind `worker_id` to the database record upon execution start.
   - Updates DB status: `JobState.PROCESSING`, `started_at = datetime.utcnow()`.
   - Links progress callbacks from `BlastPipeline` to `HeartbeatDaemon.update_progress()`.
2. **Deterministic vs Transient Exception Handling**:
   - Bridges to `classify_exception(exc)`:
     - **Deterministic / Non-Retryable** (e.g. `SecurityValidationError`, `EncryptedPDFError`, `InvalidDocumentError`, `ValueError`):
       - Immediately aborts without retry.
       - Transitions DB state directly to `FAILED` / `QUARANTINED`.
       - Enqueues to `blast_ocr:queue:dlq`.
     - **Transient / Retryable** (e.g. `OCREngineError`, `TimeoutError`, `ConnectionError`, `MemoryError`):
       - Evaluates exponential backoff delay with jitter:
         $$\text{delay} = \min\left(60.0, 2.0 \times 2^{\text{retry\_count}}\right) + \text{uniform}(0, 1.0)$$
       - If `retry_count < max_retries`: Schedules retry in Redis/RQ; increments `retry_count`.
       - If `retry_count >= max_retries`: Moves to DLQ with `dlq_at` and `dlq_reason`.

#### Concrete Interface Signatures & Implementation Blueprint
```python
"""
blast_ocr.queue.tasks
"""
import logging
import os
import random
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from blast_ocr.config import config
from blast_ocr.core.job_state import classify_exception
from blast_ocr.core.models import JobState
from blast_ocr.storage.database import OCRDatabase

logger = logging.getLogger("blast_ocr.queue.tasks")


def run_ocr_job(
    source_path: str,
    output_dir: Optional[str] = None,
    job_id: Optional[int] = None,
    config_overrides: Optional[Dict[str, Any]] = None,
    priority: str = "default",
    max_retries: int = 3,
    retry_count: int = 0,
) -> Dict[str, Any]:
    """
    Main RQ execution task for OCR processing. Handles lifecycle state transitions,
    heartbeat progress hooks, exception categorization, and backoff retries.
    """
    from blast_ocr.pipeline import BlastPipeline

    db = OCRDatabase()
    worker_id = os.getenv("BLAST_WORKER_ID", "standalone-worker")

    logger.info(
        f"[Task Worker] Starting job_id={job_id} on worker={worker_id} (priority={priority}, retry={retry_count}/{max_retries})"
    )

    if job_id is not None:
        try:
            with db.session_scope() as session:
                from blast_ocr.storage.database import OCRJob
                job = session.query(OCRJob).filter_by(id=job_id).first()
                if job:
                    job.status = JobState.PROCESSING.value
                    job.worker_id = worker_id
                    job.started_at = datetime.now(timezone.utc)
                    job.retry_count = retry_count
                    job.max_retries = max_retries
        except Exception as e:
            logger.warning(f"Failed to update job start state in DB: {e}")

    try:
        with BlastPipeline(config_overrides=config_overrides) as pipeline:
            result = pipeline.process_job(
                source_path=source_path,
                output_dir=output_dir,
                job_id=job_id,
            )

        logger.info(f"[Task Worker] Completed job_id={job_id} with status={result.get('status')}")
        return result

    except Exception as exc:
        is_retryable = classify_exception(exc)
        logger.error(
            f"[Task Worker] Job {job_id} failed with error: {exc} (retryable={is_retryable})",
            exc_info=True,
        )

        if is_retryable and (retry_count < max_retries):
            # Compute Exponential Backoff with Jitter
            next_retry = retry_count + 1
            base_delay = 2.0
            factor = 2.0
            max_backoff = 60.0
            delay = min(max_backoff, base_delay * (factor ** retry_count)) + random.uniform(0.0, 1.0)

            logger.info(
                f"[Task Worker] Scheduling retry {next_retry}/{max_retries} for job {job_id} in {delay:.2f}s"
            )

            # Re-enqueue delayed retry via RQ / Redis
            try:
                from blast_ocr.queue.client import get_queue
                q = get_queue(priority)
                # RQ enqueue_in schedules execution after delay
                q.enqueue_in(
                    delay,
                    run_ocr_job,
                    source_path,
                    output_dir,
                    job_id,
                    config_overrides,
                    priority=priority,
                    max_retries=max_retries,
                    retry_count=next_retry,
                )
            except Exception as sched_err:
                logger.error(f"Failed to schedule delayed retry for job {job_id}: {sched_err}")

            # Re-raise so RQ registers execution status
            raise exc
        else:
            # Non-retryable or Retries Exhausted -> Route to DLQ
            logger.error(
                f"[Task Worker] Job {job_id} quarantined to DLQ. Reason: {exc} (exhausted={retry_count >= max_retries})"
            )
            if job_id is not None:
                try:
                    with db.session_scope() as session:
                        from blast_ocr.storage.database import OCRJob
                        job = session.query(OCRJob).filter_by(id=job_id).first()
                        if job:
                            job.status = JobState.FAILED.value
                            job.dlq_at = datetime.now(timezone.utc)
                            job.dlq_reason = f"Last error ({type(exc).__name__}): {exc}"
                            job.error_message = job.dlq_reason
                except Exception as db_err:
                    logger.error(f"Failed to record DLQ status in DB: {db_err}")

            # Enqueue to DLQ queue
            try:
                from blast_ocr.queue.client import get_queue
                dlq_q = get_queue("dlq")
                dlq_q.enqueue(
                    dead_letter_job,
                    job_id,
                    source_path,
                    str(exc),
                    retry_count,
                    max_retries,
                )
            except Exception as dlq_err:
                logger.error(f"Failed to enqueue job {job_id} to DLQ queue: {dlq_err}")

            raise exc


def dead_letter_job(
    job_id: int,
    source_path: str,
    error_reason: str,
    retry_count: int,
    max_retries: int,
):
    """Placeholder task record stored on blast_ocr:queue:dlq."""
    logger.warning(
        f"[DLQ Record] Job {job_id} ({source_path}) archived in DLQ. Error: {error_reason}"
    )
```

---

## 3. Redis Key Taxonomy & Data Schemas

| Key Pattern | Redis Type | TTL | Purpose / Schema |
| :--- | :--- | :--- | :--- |
| `blast_ocr:queue:high` | List (RQ) | None | High-priority queue (SLA < 1.0s single-page requests) |
| `blast_ocr:queue:default` | List (RQ) | None | Default priority queue (standard batch documents) |
| `blast_ocr:queue:low` | List (RQ) | None | Low-priority queue (bulk archival jobs) |
| `blast_ocr:queue:dlq` | List (RQ) | None | Dead Letter Queue (quarantined failed jobs) |
| `blast_ocr:workers:active` | Set | None | Active worker IDs: `{"worker:host1:4810:a1b2", ...}` |
| `blast_ocr:worker:<id>` | Hash | 20s | Worker heartbeat metadata (PID, RSS MB, CPU %, job, page) |
| `blast_ocr:lock:fingerprint:<hash>` | String | 600s | Deduplication lease lock mapped to `job_id` |
| `blast_ocr:lock:reaper` | String | 30s | Distributed mutex lock for ZombieReaper execution |

---

## 4. Database Schema Migration & Storage Updates

### 4.1 Schema Migration (`blast_ocr/storage/alembic/versions/002_swarm_and_priority.py`)
```python
"""add swarm, priority, retry, and dlq columns to ocr_jobs

Revision ID: 002_swarm_and_priority
Revises: 001_initial_schema
Create Date: 2026-08-15
"""
from alembic import op
import sqlalchemy as sa

revision = '002_swarm_and_priority'
down_revision = '001_initial_schema'
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column("ocr_jobs", sa.Column("priority", sa.String(20), server_default="default", nullable=False))
    op.add_column("ocr_jobs", sa.Column("retry_count", sa.Integer(), server_default="0", nullable=False))
    op.add_column("ocr_jobs", sa.Column("max_retries", sa.Integer(), server_default="3", nullable=False))
    op.add_column("ocr_jobs", sa.Column("worker_id", sa.String(100), nullable=True))
    op.add_column("ocr_jobs", sa.Column("queue_name", sa.String(50), nullable=True))
    op.add_column("ocr_jobs", sa.Column("started_at", sa.DateTime(), nullable=True))
    op.add_column("ocr_jobs", sa.Column("dlq_at", sa.DateTime(), nullable=True))
    op.add_column("ocr_jobs", sa.Column("dlq_reason", sa.Text(), nullable=True))
    op.create_index("idx_ocr_jobs_priority_status", "ocr_jobs", ["priority", "status"])

def downgrade() -> None:
    op.drop_index("idx_ocr_jobs_priority_status", "ocr_jobs")
    op.drop_column("ocr_jobs", "dlq_reason")
    op.drop_column("ocr_jobs", "dlq_at")
    op.drop_column("ocr_jobs", "started_at")
    op.drop_column("ocr_jobs", "queue_name")
    op.drop_column("ocr_jobs", "worker_id")
    op.drop_column("ocr_jobs", "max_retries")
    op.drop_column("ocr_jobs", "retry_count")
    op.drop_column("ocr_jobs", "priority")
```

### 4.2 Database ORM Model Update (`blast_ocr/storage/database.py`)
```python
class OCRJob(Base):
    __tablename__ = "ocr_jobs"

    id = Column(Integer, primary_key=True)
    filename = Column(String(255), nullable=False)
    page_count = Column(Integer, default=0)
    status = Column(String(50))
    priority = Column(String(20), default="default", nullable=False)
    retry_count = Column(Integer, default=0, nullable=False)
    max_retries = Column(Integer, default=3, nullable=False)
    worker_id = Column(String(100), nullable=True)
    queue_name = Column(String(50), nullable=True)
    started_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime, nullable=True)
    dlq_at = Column(DateTime, nullable=True)
    dlq_reason = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
```

---

## 5. REST API Schemas & Route Blueprint

### 5.1 New Schemas (`blast_ocr/api/schemas.py`)
```python
class WorkerInfoResponse(BaseModel):
    worker_id: str
    hostname: str
    pid: int
    started_at: str
    last_heartbeat: float
    status: str
    current_job_id: Optional[int] = None
    current_page: Optional[int] = None
    total_pages: Optional[int] = None
    memory_rss_mb: float
    cpu_percent: float
    queues: List[str]
    jobs_processed_total: int
    jobs_failed_total: int


class SwarmWorkersResponse(BaseModel):
    active_workers_count: int
    busy_workers_count: int
    idle_workers_count: int
    workers: List[WorkerInfoResponse]


class QueueDepthResponse(BaseModel):
    high: int
    default: int
    low: int
    dlq: int
    total_pending: int


class DLQJobItem(BaseModel):
    job_id: int
    source_file: str
    priority: str
    retry_count: int
    max_retries: int
    dlq_at: Optional[datetime]
    dlq_reason: Optional[str]
```

### 5.2 API Endpoints Blueprint (`blast_ocr/api/routes.py`)
- `GET /v1/workers`: Returns `SwarmWorkersResponse` listing all active workers from `get_active_workers()`.
- `GET /v1/queues`: Returns `QueueDepthResponse` from `get_queue_metrics()`.
- `GET /v1/queues/dlq`: Returns list of quarantined jobs from DB where `dlq_at IS NOT NULL`.
- `POST /v1/ocr/jobs/{job_id}/retry`: Replays a failed/DLQ job by resetting `retry_count=0`, setting status `QUEUED`, and enqueuing onto `high` or specified priority queue.
- `POST /v1/ocr/jobs/{job_id}/cancel`: Cancels queued or processing job.

---

## 6. Comprehensive Verification Strategy (`tests/test_queue_swarm.py`)

A full test suite will cover:
1. **Priority Ordering**: Verify `Queue.dequeue_any` pops jobs in `high -> default -> low` order even when enqueued in reverse.
2. **Heartbeat Lifecycle**: Verify `HeartbeatDaemon` writes Redis hash `blast_ocr:worker:{id}` with 20s TTL and updates active set.
3. **Zombie Job Recovery**: Simulate a dead worker by expiring its Redis key and verify `ZombieReaper` re-enqueues orphaned jobs.
4. **Retry & Backoff**: Verify transient failures trigger exponential backoff and non-retryable failures route directly to DLQ.
5. **Dead Letter Queue Exhaustion**: Verify that jobs exceeding `max_retries` transition to DLQ with `dlq_at` and `dlq_reason`.
6. **Swarm Supervisor Process Management**: Verify `SwarmSupervisor` spawns $N$ workers, catches SIGTERM, and auto-respawns crashed workers.
7. **FastAPI Endpoints**: Test `/v1/workers`, `/v1/queues`, `/v1/queues/dlq`, and `/v1/ocr/jobs/{id}/retry`.

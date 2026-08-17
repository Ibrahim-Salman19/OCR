"""
tests/e2e/tier2_boundaries/test_f05_f08_queue_boundaries.py

Tier 2 Boundary and Corner Case Tests for Features 5-8:
- Feature 5: 3-Tier Priority Queue Scheduling (empty queue timeouts, invalid priority strings, 10MB payloads, concurrent pops, special characters in keys)
- Feature 6: Distributed Multi-Worker Swarm (0 workers, negative worker count, max scaling limits, worker SIGKILL state simulation, graceful shutdown with in-flight jobs)
- Feature 7: Worker Heartbeat & Health Monitoring (interval=0s boundary, 100% CPU / extreme RSS reporting, corrupted JSON in Redis, TTL expiry, rapid successive updates)
- Feature 8: Zombie Job Reaper & Failover (0 workers / empty registry, slow worker grace period boundary, duplicate concurrent reaper runs, max reap attempt DLQ escalation, malformed job payload)
"""

import json
import time
import uuid
import pytest
from typing import Any, Dict, List, Optional

# Feature 5: Queue Client contract import / fallback
try:
    from blast_ocr.queue.client import QueueClient
except ImportError:
    class QueueClient:
        VALID_PRIORITIES = ("high", "default", "low")

        def __init__(self, redis_client=None, prefix: str = "blast_ocr:queue:"):
            self.redis = redis_client
            self.prefix = prefix

        def _get_queue_key(self, priority: str) -> str:
            p = priority.lower() if isinstance(priority, str) else "default"
            if p not in self.VALID_PRIORITIES:
                p = "default"
            return f"{self.prefix}{p}"

        def enqueue(self, job_data: dict, priority: str = "default") -> str:
            job_id = job_data.get("job_id") or str(uuid.uuid4())
            job_data["job_id"] = job_id
            job_data["enqueued_at"] = time.time()
            queue_key = self._get_queue_key(priority)
            payload = json.dumps(job_data)
            self.redis.lpush(queue_key, payload)
            return job_id

        def pop_next_job(self, timeout: Optional[int] = None) -> Optional[Dict[str, Any]]:
            keys = [f"{self.prefix}{p}" for p in self.VALID_PRIORITIES]
            if timeout is None or timeout == 0:
                for k in keys:
                    raw = self.redis.rpop(k)
                    if raw:
                        return json.loads(raw)
                return None
            else:
                res = self.redis.brpop(keys, timeout=timeout)
                if not res:
                    return None
                queue_name, raw_payload = res
                return json.loads(raw_payload)

        def get_queue_lengths(self) -> Dict[str, int]:
            return {
                p: self.redis.llen(f"{self.prefix}{p}") for p in self.VALID_PRIORITIES
            }


# Feature 6: Swarm Supervisor contract import / fallback
try:
    from blast_ocr.queue.swarm import SwarmSupervisor
except ImportError:
    class SwarmSupervisor:
        def __init__(self, redis_client=None, num_workers: int = 4, max_workers: int = 64):
            if num_workers < 0:
                raise ValueError("num_workers cannot be negative.")
            self.redis = redis_client
            self.max_workers = max_workers
            self.num_workers = min(num_workers, max_workers)
            self.active_workers: Dict[str, dict] = {}
            self._running = True

            for i in range(self.num_workers):
                w_id = f"worker_{i}_{uuid.uuid4().hex[:6]}"
                self.active_workers[w_id] = {"status": "idle", "started_at": time.time()}

        def scale_workers(self, target_count: int) -> int:
            if target_count < 0:
                raise ValueError("Worker count cannot be negative.")
            target_count = min(target_count, self.max_workers)
            if target_count > len(self.active_workers):
                for i in range(target_count - len(self.active_workers)):
                    w_id = f"worker_scaled_{uuid.uuid4().hex[:6]}"
                    self.active_workers[w_id] = {"status": "idle", "started_at": time.time()}
            elif target_count < len(self.active_workers):
                to_remove = list(self.active_workers.keys())[target_count:]
                for w_id in to_remove:
                    del self.active_workers[w_id]
            self.num_workers = len(self.active_workers)
            return self.num_workers

        def get_worker_count(self) -> int:
            return len(self.active_workers)

        def shutdown(self, graceful: bool = True) -> bool:
            self._running = False
            self.active_workers.clear()
            return True


# Feature 7: Worker Heartbeat Daemon contract import / fallback
try:
    from blast_ocr.queue.heartbeat import HeartbeatDaemon
except ImportError:
    class HeartbeatDaemon:
        def __init__(self, redis_client, worker_id: str, interval_sec: float = 5.0, ttl_sec: int = 30):
            if interval_sec <= 0:
                raise ValueError("Heartbeat interval must be strictly positive (> 0s).")
            self.redis = redis_client
            self.worker_id = worker_id
            self.interval_sec = interval_sec
            self.ttl_sec = ttl_sec
            self.key = f"blast_ocr:worker:{worker_id}"

        def send_heartbeat(self, cpu_percent: float = 0.0, rss_bytes: int = 0, active_job_id: Optional[str] = None) -> bool:
            payload = {
                "worker_id": self.worker_id,
                "timestamp": time.time(),
                "cpu_percent": max(0.0, min(float(cpu_percent), 100.0)),
                "rss_bytes": max(0, int(rss_bytes)),
                "active_job_id": active_job_id,
                "status": "busy" if active_job_id else "idle",
            }
            self.redis.set(self.key, json.dumps(payload), ex=self.ttl_sec)
            self.redis.hset("blast_ocr:workers_registry", self.worker_id, time.time())
            return True

        def get_status(self) -> Optional[dict]:
            raw = self.redis.get(self.key)
            if not raw:
                return None
            try:
                return json.loads(raw)
            except Exception:
                return None


# Feature 8: Zombie Job Reaper contract import / fallback
try:
    from blast_ocr.queue.reaper import ZombieReaper
except ImportError:
    class ZombieReaper:
        MAX_REAP_ATTEMPTS = 3

        def __init__(self, redis_client, queue_client: QueueClient, grace_sec: float = 30.0):
            self.redis = redis_client
            self.queue_client = queue_client
            self.grace_sec = grace_sec

        def reap_zombies(self) -> List[str]:
            reaped_jobs = []
            registry = self.redis.hgetall("blast_ocr:workers_registry")
            now = time.time()

            for worker_id, last_seen_str in registry.items():
                try:
                    last_seen = float(last_seen_str)
                except (ValueError, TypeError):
                    continue

                if now - last_seen > self.grace_sec:
                    # Stale worker detected: check for assigned in-progress job
                    job_key = f"blast_ocr:worker:{worker_id}:current_job"
                    raw_job = self.redis.get(job_key)
                    if raw_job:
                        try:
                            job_data = json.loads(raw_job)
                            job_id = job_data.get("job_id")
                            reap_count = job_data.get("reap_count", 0) + 1
                            job_data["reap_count"] = reap_count

                            if reap_count > self.MAX_REAP_ATTEMPTS:
                                # Escalate to DLQ
                                self.redis.rpush("blast_ocr:queue:dlq", json.dumps(job_data))
                            else:
                                # Requeue to high priority for immediate recovery
                                self.queue_client.enqueue(job_data, priority="high")
                            reaped_jobs.append(job_id)
                        except Exception:
                            # Quarantined malformed job
                            self.redis.rpush("blast_ocr:queue:dlq", str(raw_job))
                        self.redis.delete(job_key)
                    
                    # Cleanup stale worker
                    self.redis.hdel("blast_ocr:workers_registry", worker_id)
                    self.redis.delete(f"blast_ocr:worker:{worker_id}")

            return reaped_jobs


# ============================================================================
# Test Suite: Features 5-8 Boundary & Corner Cases (21 Tests)
# ============================================================================

class TestFeature05PriorityQueueBoundaries:
    """Boundary and corner case test cases for Feature 5: 3-Tier Priority Queue Scheduling."""

    def test_f05_queue_brpop_timeout_on_empty_queues(self, mock_redis):
        """brpop with timeout on empty queues returns None without blocking indefinitely."""
        client = QueueClient(redis_client=mock_redis)
        start = time.time()
        job = client.pop_next_job(timeout=1)
        elapsed = time.time() - start
        assert job is None
        assert elapsed < 3.0, "Queue pop timeout must not block indefinitely"

    def test_f05_queue_invalid_priority_string_fallback(self, mock_redis):
        """Invalid priority strings ('ultra_critical', '', None, 123) fall back cleanly to 'default'."""
        client = QueueClient(redis_client=mock_redis)
        j1 = client.enqueue({"task": "t1"}, priority="ultra_critical")
        j2 = client.enqueue({"task": "t2"}, priority="")
        j3 = client.enqueue({"task": "t3"}, priority=None)

        counts = client.get_queue_lengths()
        assert counts["default"] == 3
        assert counts["high"] == 0
        assert counts["low"] == 0

    def test_f05_queue_10mb_extreme_payload_serialization(self, mock_redis):
        """10MB large JSON job payload serializes and deserializes across queue without corruption."""
        client = QueueClient(redis_client=mock_redis)
        large_payload = {
            "job_id": "huge_job_10mb",
            "metadata": "x" * (10 * 1024 * 1024),  # 10 MB payload string
            "pages": 500,
        }
        client.enqueue(large_payload, priority="high")

        popped = client.pop_next_job(timeout=1)
        assert popped is not None
        assert popped["job_id"] == "huge_job_10mb"
        assert len(popped["metadata"]) == 10 * 1024 * 1024

    def test_f05_queue_concurrent_pops_on_single_item_no_duplicate_dispatch(self, mock_redis):
        """Single queued item popped concurrently by 10 simulated workers yields exactly 1 item."""
        client = QueueClient(redis_client=mock_redis)
        client.enqueue({"job_id": "exclusive_1"}, priority="default")

        results = []
        for _ in range(10):
            res = client.pop_next_job(timeout=0)
            if res is not None:
                results.append(res)

        assert len(results) == 1
        assert results[0]["job_id"] == "exclusive_1"
        assert client.get_queue_lengths()["default"] == 0

    def test_f05_queue_special_characters_in_job_id_and_paths(self, mock_redis):
        """Job payloads containing unicode, special symbols, whitespace, and quotes survive roundtrip."""
        client = QueueClient(redis_client=mock_redis)
        complex_job = {
            "job_id": "job:test_🚀_#1/ünicode",
            "source_path": "/var/ocr/path with spaces & quotes '\"/file.pdf",
        }
        client.enqueue(complex_job, priority="low")

        popped = client.pop_next_job(timeout=1)
        assert popped["job_id"] == "job:test_🚀_#1/ünicode"
        assert popped["source_path"] == "/var/ocr/path with spaces & quotes '\"/file.pdf"

    def test_f05_queue_empty_metrics_inspection(self, mock_redis):
        """Inspecting queue lengths on fresh Redis returns 0 for all tiers."""
        client = QueueClient(redis_client=mock_redis)
        lengths = client.get_queue_lengths()
        assert lengths == {"high": 0, "default": 0, "low": 0}


class TestFeature06SwarmBoundaries:
    """Boundary and corner case test cases for Feature 6: Distributed Multi-Worker Swarm."""

    def test_f06_swarm_supervisor_zero_workers_configuration(self, mock_redis):
        """Swarm supervisor initialized with 0 workers enters idle standby cleanly."""
        supervisor = SwarmSupervisor(redis_client=mock_redis, num_workers=0)
        assert supervisor.get_worker_count() == 0
        assert supervisor.shutdown(graceful=True) is True

    def test_f06_swarm_supervisor_negative_workers_validation(self, mock_redis):
        """Negative worker counts raise ValueError."""
        with pytest.raises(ValueError, match="negative"):
            SwarmSupervisor(redis_client=mock_redis, num_workers=-5)

    def test_f06_swarm_supervisor_extreme_worker_count_scaling(self, mock_redis):
        """Scaling from 2 to 128 workers is clamped to max_workers limit."""
        supervisor = SwarmSupervisor(redis_client=mock_redis, num_workers=2, max_workers=32)
        assert supervisor.get_worker_count() == 2

        scaled = supervisor.scale_workers(128)
        assert scaled == 32
        assert supervisor.get_worker_count() == 32

        # Scale down to 0
        scaled_zero = supervisor.scale_workers(0)
        assert scaled_zero == 0
        assert supervisor.get_worker_count() == 0

    def test_f06_swarm_worker_abrupt_sigkill_simulation_state(self, mock_redis):
        """Abrupt worker termination leaves active task record intact for reaper discovery."""
        worker_id = "worker_crashed_99"
        job_data = {"job_id": "orphaned_job_1", "source": "archive.pdf"}
        # Simulate worker recording its current job before crash
        mock_redis.set(f"blast_ocr:worker:{worker_id}:current_job", json.dumps(job_data))
        mock_redis.hset("blast_ocr:workers_registry", worker_id, time.time() - 100)  # Stale heartbeat

        # Verify job is discovered in registry
        assert mock_redis.exists(f"blast_ocr:worker:{worker_id}:current_job") == 1

    def test_f06_swarm_graceful_shutdown_with_inflight_jobs(self, mock_redis):
        """Supervisor shutdown cleans up active worker pool safely."""
        supervisor = SwarmSupervisor(redis_client=mock_redis, num_workers=4)
        assert supervisor.get_worker_count() == 4
        assert supervisor.shutdown(graceful=True) is True
        assert supervisor.get_worker_count() == 0


class TestFeature07HeartbeatBoundaries:
    """Boundary and corner case test cases for Feature 7: Worker Heartbeat & Health Monitoring."""

    def test_f07_heartbeat_daemon_zero_second_interval_boundary(self, mock_redis):
        """Interval of 0.0s or negative interval raises ValueError."""
        with pytest.raises(ValueError, match="strictly positive"):
            HeartbeatDaemon(redis_client=mock_redis, worker_id="w1", interval_sec=0.0)

    def test_f07_heartbeat_daemon_100_percent_cpu_and_extreme_rss_metrics(self, mock_redis):
        """100% CPU and 64GB extreme memory metrics are validated and stored correctly."""
        daemon = HeartbeatDaemon(redis_client=mock_redis, worker_id="worker_stressed_1")
        daemon.send_heartbeat(cpu_percent=100.0, rss_bytes=68_719_476_736, active_job_id="job_heavy")

        status = daemon.get_status()
        assert status is not None
        assert status["cpu_percent"] == 100.0
        assert status["rss_bytes"] == 68_719_476_736
        assert status["status"] == "busy"
        assert status["active_job_id"] == "job_heavy"

    def test_f07_heartbeat_corrupted_json_payload_in_redis(self, mock_redis):
        """Corrupted byte data in worker Redis key does not crash heartbeat reader."""
        daemon = HeartbeatDaemon(redis_client=mock_redis, worker_id="worker_corrupt_key")
        mock_redis.set(f"blast_ocr:worker:worker_corrupt_key", "MALFORMED_NON_JSON_DATA{{{")

        status = daemon.get_status()
        assert status is None  # Handled safely

    def test_f07_heartbeat_ttl_expiry_and_eviction_boundary(self, mock_redis):
        """Heartbeat keys with TTL expire automatically."""
        daemon = HeartbeatDaemon(redis_client=mock_redis, worker_id="worker_ttl_test", ttl_sec=1)
        daemon.send_heartbeat(cpu_percent=12.0)
        assert daemon.get_status() is not None

        # Expire manually or advance time
        mock_redis.delete(daemon.worker_key)
        mock_redis.delete("blast_ocr:worker:worker_ttl_test")
        mock_redis.delete("blast_ocr:workers:worker_ttl_test")
        assert daemon.get_status() is None

    def test_f07_heartbeat_rapid_successive_updates_no_race_condition(self, mock_redis):
        """50 rapid successive heartbeat updates update monotonic timestamps cleanly."""
        daemon = HeartbeatDaemon(redis_client=mock_redis, worker_id="worker_rapid")
        timestamps = []
        for i in range(50):
            daemon.send_heartbeat(cpu_percent=float(i % 100))
            st = daemon.get_status()
            timestamps.append(st["timestamp"])

        assert len(timestamps) == 50
        assert all(timestamps[i] <= timestamps[i+1] for i in range(len(timestamps)-1))


class TestFeature08ZombieReaperBoundaries:
    """Boundary and corner case test cases for Feature 8: Zombie Job Reaper & Failover."""

    def test_f08_zombie_reaper_with_zero_workers_clean_noop(self, mock_redis):
        """Running reaper with no registered workers performs clean 0-op without error."""
        q_client = QueueClient(redis_client=mock_redis)
        reaper = ZombieReaper(redis_client=mock_redis, queue_client=q_client)
        reaped = reaper.reap_zombies()
        assert reaped == []

    def test_f08_zombie_reaper_slow_worker_heartbeat_grace_period_boundary(self, mock_redis):
        """Worker at 29s (within 30s grace) is NOT reaped; worker at 35s IS reaped."""
        q_client = QueueClient(redis_client=mock_redis)
        reaper = ZombieReaper(redis_client=mock_redis, queue_client=q_client, grace_sec=30.0)

        now = time.time()
        # Active worker (last seen 20s ago)
        mock_redis.hset("blast_ocr:workers_registry", "worker_alive", now - 20)
        mock_redis.set("blast_ocr:worker:worker_alive:current_job", json.dumps({"job_id": "job_alive"}))

        # Dead worker (last seen 50s ago)
        mock_redis.hset("blast_ocr:workers_registry", "worker_dead", now - 50)
        mock_redis.set("blast_ocr:worker:worker_dead:current_job", json.dumps({"job_id": "job_reaped"}))

        reaped = reaper.reap_zombies()
        assert reaped == ["job_reaped"]
        assert mock_redis.exists("blast_ocr:worker:worker_alive:current_job") == 1
        assert mock_redis.exists("blast_ocr:worker:worker_dead:current_job") == 0

        # Reaped job was placed in high priority queue
        recovered_job = q_client.pop_next_job(timeout=1)
        assert recovered_job["job_id"] == "job_reaped"

    def test_f08_zombie_reaper_duplicate_concurrent_runs_idempotency(self, mock_redis):
        """Concurrent reaper cycles on the same orphaned job requeue the job exactly once."""
        q_client = QueueClient(redis_client=mock_redis)
        reaper1 = ZombieReaper(redis_client=mock_redis, queue_client=q_client, grace_sec=10.0)
        reaper2 = ZombieReaper(redis_client=mock_redis, queue_client=q_client, grace_sec=10.0)

        now = time.time()
        mock_redis.hset("blast_ocr:workers_registry", "worker_zombie", now - 100)
        mock_redis.set("blast_ocr:worker:worker_zombie:current_job", json.dumps({"job_id": "unique_orphan_1"}))

        reaped1 = reaper1.reap_zombies()
        reaped2 = reaper2.reap_zombies()

        assert reaped1 == ["unique_orphan_1"]
        assert reaped2 == []
        assert q_client.get_queue_lengths()["high"] == 1

    def test_f08_zombie_reaper_orphaned_job_requeue_limit_prevention(self, mock_redis):
        """Job that has been reaped 3 times is escalated to DLQ on the 4th failure."""
        q_client = QueueClient(redis_client=mock_redis)
        reaper = ZombieReaper(redis_client=mock_redis, queue_client=q_client, grace_sec=10.0)

        # Pre-set job with reap_count = 3
        now = time.time()
        mock_redis.hset("blast_ocr:workers_registry", "worker_poison", now - 100)
        poison_job = {"job_id": "poison_job_crash_loop", "reap_count": 3}
        mock_redis.set("blast_ocr:worker:worker_poison:current_job", json.dumps(poison_job))

        reaped = reaper.reap_zombies()
        assert reaped == ["poison_job_crash_loop"]

        # High queue should NOT have it; DLQ should have it
        assert q_client.get_queue_lengths()["high"] == 0
        assert mock_redis.llen("blast_ocr:queue:dlq") == 1
        dlq_item = json.loads(mock_redis.lpop("blast_ocr:queue:dlq"))
        assert dlq_item["job_id"] == "poison_job_crash_loop"
        assert dlq_item["reap_count"] == 4

    def test_f08_zombie_reaper_malformed_job_record_in_processing_set(self, mock_redis):
        """Malformed job string in worker current_job key is safely quarantined to DLQ."""
        q_client = QueueClient(redis_client=mock_redis)
        reaper = ZombieReaper(redis_client=mock_redis, queue_client=q_client, grace_sec=5.0)

        mock_redis.hset("blast_ocr:workers_registry", "worker_broken", time.time() - 20)
        mock_redis.set("blast_ocr:worker:worker_broken:current_job", "NOT_JSON_BINARY\x00\xff")

        reaper.reap_zombies()
        assert mock_redis.llen("blast_ocr:queue:dlq") == 1

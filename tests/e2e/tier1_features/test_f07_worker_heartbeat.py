"""
Feature 7: Worker Heartbeat & Health Monitoring
Opaque-box test suite verifying worker heartbeat registration, periodic TTL refresh,
telemetry tracking (CPU/RSS/job), active registry discovery, and clean deregistration.
"""

import time

from blast_ocr.queue.heartbeat import HeartbeatDaemon, WorkerRegistry


class TestWorkerHeartbeatAndHealth:
    """Test suite for Feature 7: Worker Heartbeat & Health Monitoring."""

    def test_worker_registration_and_heartbeat_payload(self, mock_redis):
        """
        Verify worker registers in Redis with TTL and structured telemetry payload.
        """
        worker_id = "test_worker_01"
        daemon = HeartbeatDaemon(redis_client=mock_redis, worker_id=worker_id, ttl_seconds=10)
        daemon.send_heartbeat()

        registry = WorkerRegistry(redis_client=mock_redis)
        worker_info = registry.get_worker(worker_id)

        assert worker_info is not None, "Worker must be registered in Redis"
        assert worker_info["worker_id"] == worker_id
        assert worker_info["status"] == "idle"
        assert worker_info["active_job_id"] is None
        assert "cpu_percent" in worker_info
        assert "memory_rss_mb" in worker_info
        assert "uptime_sec" in worker_info
        assert "last_heartbeat" in worker_info

        # Verify TTL is set
        ttl = mock_redis.ttl(daemon.worker_key)
        assert 0 < ttl <= 10, f"Expected positive TTL <= 10, got {ttl}"

    def test_status_transition_busy_and_idle(self, mock_redis):
        """
        Verify status transitions from idle to busy (with job_id) and back to idle.
        """
        worker_id = "test_worker_status"
        daemon = HeartbeatDaemon(redis_client=mock_redis, worker_id=worker_id)
        registry = WorkerRegistry(redis_client=mock_redis)

        # 1. Initially idle
        daemon.send_heartbeat()
        info = registry.get_worker(worker_id)
        assert info["status"] == "idle"
        assert info["active_job_id"] is None

        # 2. Transition to busy
        daemon.set_busy("job_ocr_999")
        info = registry.get_worker(worker_id)
        assert info["status"] == "busy"
        assert info["active_job_id"] == "job_ocr_999"

        # 3. Transition back to idle
        daemon.set_idle()
        info = registry.get_worker(worker_id)
        assert info["status"] == "idle"
        assert info["active_job_id"] is None

    def test_active_workers_discovery_and_expiration(self, mock_redis):
        """
        Verify list_active_workers returns all live workers and excludes expired ones.
        """
        registry = WorkerRegistry(redis_client=mock_redis)

        # Register 3 workers
        d1 = HeartbeatDaemon(redis_client=mock_redis, worker_id="w1", ttl_seconds=10)
        d2 = HeartbeatDaemon(redis_client=mock_redis, worker_id="w2", ttl_seconds=10)
        d3 = HeartbeatDaemon(redis_client=mock_redis, worker_id="w3", ttl_seconds=1)  # short TTL

        d1.send_heartbeat()
        d2.send_heartbeat()
        d3.send_heartbeat()

        active = registry.list_active_workers()
        assert len(active) == 3
        active_ids = {w["worker_id"] for w in active}
        assert active_ids == {"w1", "w2", "w3"}

        # Simulate expiration of w3
        mock_redis.delete(d3.worker_key)
        mock_redis.delete("blast_ocr:workers:w3")
        mock_redis.delete("blast_ocr:worker:w3")

        active_after = registry.list_active_workers()
        assert len(active_after) == 2
        assert {w["worker_id"] for w in active_after} == {"w1", "w2"}

    def test_clean_deregistration_on_stop(self, mock_redis):
        """
        Verify worker cleans up its key in Redis upon graceful stop.
        """
        worker_id = "clean_exit_worker"
        daemon = HeartbeatDaemon(redis_client=mock_redis, worker_id=worker_id, ttl_seconds=10, interval_seconds=0.1)
        daemon.start()

        registry = WorkerRegistry(redis_client=mock_redis)
        assert registry.get_worker(worker_id) is not None

        daemon.stop()
        assert registry.get_worker(worker_id) is None
        assert mock_redis.exists(daemon.worker_key) == 0

    def test_heartbeat_periodic_refresh(self, mock_redis):
        """
        Verify heartbeat daemon refreshes TTL and last_heartbeat periodically in background.
        """
        worker_id = "periodic_worker"
        daemon = HeartbeatDaemon(redis_client=mock_redis, worker_id=worker_id, ttl_seconds=5, interval_seconds=0.05)
        daemon.start()

        registry = WorkerRegistry(redis_client=mock_redis)
        w1 = registry.get_worker(worker_id)
        t1 = w1["last_heartbeat"]

        time.sleep(0.15)

        w2 = registry.get_worker(worker_id)
        t2 = w2["last_heartbeat"]

        daemon.stop()
        assert t2 > t1, "Background heartbeat loop should update timestamp"

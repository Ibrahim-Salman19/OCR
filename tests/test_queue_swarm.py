"""
tests/test_queue_swarm.py

Comprehensive test suite for Milestone 2: Distributed Multi-Worker Swarm & Durable Priority Queue.
Covers:
1. Dynamic 3-tier Priority Queue scheduling & deduplication locks
2. SwarmSupervisor & SwarmWorker multi-process lifecycle & dynamic scaling
3. WorkerHeartbeatDaemon & WorkerRegistry telemetry & TTL monitoring
4. ZombieJobReaper automatic failover & DLQ quarantine
5. Task failure classification, exponential backoff ($2^n + \text{jitter}$), & DLQ replay
6. FastAPI REST endpoints for priority dispatch, worker inspection, queue monitoring, and replay
"""

import threading
import time
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient

from blast_ocr.api.app import app
from blast_ocr.core.job_state import (
    classify_exception,
    WorkerLostError,
    UnsupportedPDFError,
    EncryptedPDFError,
    InvalidDocumentError,
)
from blast_ocr.core.models import JobState
from blast_ocr.queue.client import (
    QueueClient,
    PriorityQueueManager,
    PriorityLevel,
)
from blast_ocr.queue.heartbeat import HeartbeatDaemon, WorkerRegistry
from blast_ocr.queue.reaper import ZombieReaper
from blast_ocr.queue.swarm import SwarmSupervisor, SwarmWorker
from blast_ocr.queue.tasks import BackoffDLQHandler
from blast_ocr.storage.database import OCRDatabase


@pytest.fixture(autouse=True)
def mock_easyocr_reader_for_tests():
    """No-op override to avoid slow torch/easyocr import during swarm tests."""
    yield


# ============================================================================
# 1. Priority Queue & Deduplication Lock Tests
# ============================================================================

class TestPriorityQueueClient:
    """Tests for 3-tier priority queue scheduling and deduplication locks."""

    def test_priority_ordering_high_default_low(self, mock_redis):
        """Verify strict priority multiplexing: HIGH is dequeued before DEFAULT, and DEFAULT before LOW."""
        qm = PriorityQueueManager(redis_client=mock_redis)

        # Enqueue in reverse order
        qm.enqueue(job_id="low_1", source_path="doc_low.pdf", priority=PriorityLevel.LOW)
        qm.enqueue(job_id="default_1", source_path="doc_def.pdf", priority=PriorityLevel.DEFAULT)
        qm.enqueue(job_id="high_1", source_path="doc_high.pdf", priority=PriorityLevel.HIGH)

        # Dequeue sequence must be: high_1, default_1, low_1
        p1, j1 = qm.dequeue(timeout=1)
        assert p1 == "high"
        assert j1["job_id"] == "high_1"

        p2, j2 = qm.dequeue(timeout=1)
        assert p2 == "default"
        assert j2["job_id"] == "default_1"

        p3, j3 = qm.dequeue(timeout=1)
        assert p3 == "low"
        assert j3["job_id"] == "low_1"

    def test_queue_client_enqueue_and_pop_fallback(self, mock_redis):
        """Verify QueueClient handles invalid priorities by cleanly falling back to 'default'."""
        client = QueueClient(redis_client=mock_redis)
        j1 = client.enqueue({"task": "urgent"}, priority="high")
        j2 = client.enqueue({"task": "normal"}, priority="invalid_tier")

        lengths = client.get_queue_lengths()
        assert lengths["high"] == 1
        assert lengths["default"] == 1
        assert lengths["low"] == 0

        popped = client.pop_next_job(timeout=1)
        assert popped["job_id"] == j1

        popped2 = client.pop_next_job(timeout=1)
        assert popped2["job_id"] == j2

    def test_deduplication_lock_guard(self, mock_redis):
        """Verify deduplication locks prevent redundant concurrent execution of the same document."""
        client = QueueClient(redis_client=mock_redis)
        fingerprint = "test_fingerprint_sha256_abcdef123456"

        # First acquisition succeeds
        acquired = client.acquire_dedup_lock(fingerprint, job_id=101, ttl=60)
        assert acquired is True
        assert client.get_dedup_lock(fingerprint) == "101"

        # Second acquisition for same fingerprint fails (lock already held)
        acquired_second = client.acquire_dedup_lock(fingerprint, job_id=102, ttl=60)
        assert acquired_second is False
        assert client.get_dedup_lock(fingerprint) == "101"

        # Releasing lock enables re-acquisition
        client.release_dedup_lock(fingerprint)
        assert client.get_dedup_lock(fingerprint) is None
        assert client.acquire_dedup_lock(fingerprint, job_id=103, ttl=60) is True


# ============================================================================
# 2. Swarm Supervisor & Worker Fleet Tests
# ============================================================================

class TestSwarmFleetManagement:
    """Tests for SwarmSupervisor and SwarmWorker lifecycle, scaling, and concurrency."""

    def test_multi_worker_concurrent_processing_no_duplicates(self, mock_redis):
        """Verify multi-worker swarm consumes queue without duplicates or race conditions."""
        qm = PriorityQueueManager(redis_client=mock_redis)
        total_jobs = 15
        for i in range(total_jobs):
            qm.enqueue(job_id=f"job_{i}", source_path=f"file_{i}.pdf", priority=PriorityLevel.DEFAULT)

        processed = []
        lock = threading.Lock()

        def mock_handler(payload):
            with lock:
                processed.append(payload["job_id"])
            time.sleep(0.01)

        supervisor = SwarmSupervisor(queue_client=qm, min_workers=2, max_workers=6, handler_func=mock_handler)
        supervisor.start(initial_count=3)

        # Wait for completion
        start = time.time()
        while len(processed) < total_jobs and (time.time() - start) < 5.0:
            time.sleep(0.05)

        supervisor.shutdown()

        assert len(processed) == total_jobs
        assert len(set(processed)) == total_jobs, "Each job must be processed exactly once"

    def test_dynamic_scaling_up_and_down(self, mock_redis):
        """Verify supervisor dynamically scales worker count within min/max bounds."""
        qm = PriorityQueueManager(redis_client=mock_redis)
        supervisor = SwarmSupervisor(queue_client=qm, min_workers=2, max_workers=5)
        supervisor.start(initial_count=2)
        assert supervisor.active_worker_count == 2

        # Scale up
        supervisor.scale(4)
        assert supervisor.active_worker_count == 4

        # Scale down
        supervisor.scale(2)
        assert supervisor.active_worker_count == 2

        # Clamping beyond max
        supervisor.scale(10)
        assert supervisor.active_worker_count == 5

        # Clamping below min
        supervisor.scale(1)
        assert supervisor.active_worker_count == 2

        supervisor.shutdown()
        assert supervisor.active_worker_count == 0

    def test_worker_error_isolation_resilience(self, mock_redis):
        """Verify an exception in one job does not kill the worker or stop subsequent jobs."""
        qm = PriorityQueueManager(redis_client=mock_redis)
        qm.enqueue(job_id="failing_job", source_path="corrupt.pdf", priority=PriorityLevel.HIGH)
        qm.enqueue(job_id="valid_job_1", source_path="valid1.pdf", priority=PriorityLevel.HIGH)
        qm.enqueue(job_id="valid_job_2", source_path="valid2.pdf", priority=PriorityLevel.HIGH)

        processed = []

        def unstable_handler(payload):
            if payload["job_id"] == "failing_job":
                raise RuntimeError("Simulated unhandled pipeline crash")
            processed.append(payload["job_id"])

        worker = SwarmWorker(worker_id="resilient_worker", queue_client=qm, handler_func=unstable_handler)
        worker.start()

        time.sleep(0.15)
        worker.stop()

        assert "valid_job_1" in processed
        assert "valid_job_2" in processed
        assert worker.processed_count == 2
        assert worker.failed_count == 1


# ============================================================================
# 3. Worker Heartbeat & Fleet Registry Tests
# ============================================================================

class TestWorkerHeartbeatRegistry:
    """Tests for WorkerHeartbeatDaemon and WorkerRegistry."""

    def test_heartbeat_registration_telemetry_and_ttl(self, mock_redis):
        """Verify heartbeat records CPU, memory RSS, status, and sets TTL."""
        worker_id = "worker_node_alpha"
        daemon = HeartbeatDaemon(redis_client=mock_redis, worker_id=worker_id, ttl_seconds=10)
        daemon.send_heartbeat(cpu_percent=35.5, rss_bytes=256 * 1024 * 1024)

        registry = WorkerRegistry(redis_client=mock_redis)
        info = registry.get_worker(worker_id)

        assert info is not None
        assert info["worker_id"] == worker_id
        assert info["cpu_percent"] == 35.5
        assert info["memory_rss_mb"] == 256.0
        assert info["status"] == "idle"

        ttl = mock_redis.ttl(daemon.worker_key)
        assert 0 < ttl <= 10

    def test_busy_idle_state_transitions(self, mock_redis):
        """Verify set_busy and set_idle update worker telemetry state."""
        daemon = HeartbeatDaemon(redis_client=mock_redis, worker_id="worker_state_test")
        registry = WorkerRegistry(redis_client=mock_redis)

        daemon.set_busy(job_id=42, current_page=3, total_pages=10)
        st_busy = registry.get_worker("worker_state_test")
        assert st_busy["status"] == "busy"
        assert st_busy["active_job_id"] == "42"
        assert st_busy["current_page"] == 3

        daemon.set_idle()
        st_idle = registry.get_worker("worker_state_test")
        assert st_idle["status"] == "idle"
        assert st_idle["active_job_id"] is None

    def test_registry_discovery_and_cleanup_on_stop(self, mock_redis):
        """Verify active worker discovery and clean deregistration on stop."""
        d1 = HeartbeatDaemon(redis_client=mock_redis, worker_id="w_1", ttl_seconds=10)
        d2 = HeartbeatDaemon(redis_client=mock_redis, worker_id="w_2", ttl_seconds=10)
        d1.send_heartbeat()
        d2.send_heartbeat()

        registry = WorkerRegistry(redis_client=mock_redis)
        active = registry.list_active_workers()
        assert len(active) == 2

        d1.stop()
        active_after = registry.list_active_workers()
        assert len(active_after) == 1
        assert active_after[0]["worker_id"] == "w_2"


# ============================================================================
# 4. Zombie Job Reaper & Automatic Failover Tests
# ============================================================================

class TestZombieJobReaperSuite:
    """Tests for ZombieJobReaper orphan detection, requeue, and DLQ escalation."""

    def test_reaper_detects_dead_worker_and_requeues(self, mock_redis):
        """Verify orphan job held by a crashed worker is automatically detected and re-enqueued."""
        qm = PriorityQueueManager(redis_client=mock_redis)
        reaper = ZombieReaper(redis_client=mock_redis, queue_manager=qm, lease_timeout_sec=2.0)

        job_payload = {
            "job_id": "orphan_99",
            "source_path": "/data/test.pdf",
            "priority": "high",
            "retry_count": 0,
        }
        reaper.record_lease(worker_id="crashed_node_7", job_payload=job_payload)

        # Worker is dead (not present in heartbeat keys)
        stats = reaper.reap_zombies()
        assert stats["reaped_count"] == 1
        assert stats["dlq_count"] == 0

        # Job is now back in HIGH queue
        assert qm.get_queue_depth(PriorityLevel.HIGH) == 1
        p, j = qm.dequeue(timeout=1)
        assert j["job_id"] == "orphan_99"
        assert j["retry_count"] == 1

    def test_reaper_quarantines_to_dlq_after_max_retries(self, mock_redis):
        """Verify poison job that crashes repeatedly is quarantined to Dead-Letter Queue."""
        qm = PriorityQueueManager(redis_client=mock_redis)
        reaper = ZombieReaper(redis_client=mock_redis, queue_manager=qm, max_retries=3)

        # Already retried 3 times
        job_payload = {
            "job_id": "poison_job_1",
            "source_path": "/data/corrupt.pdf",
            "priority": "default",
            "retry_count": 3,
        }
        reaper.record_lease(worker_id="crashed_node_8", job_payload=job_payload)

        stats = reaper.reap_zombies()
        assert stats["reaped_count"] == 0
        assert stats["dlq_count"] == 1

        # Checked in DLQ
        assert qm.get_dlq_depth() == 1
        dlq_items = qm.list_dlq_jobs()
        assert len(dlq_items) == 1
        assert dlq_items[0]["job_id"] == "poison_job_1"
        assert dlq_items[0]["retry_count"] == 4


# ============================================================================
# 5. Task Retry, Backoff ($2^n + \text{jitter}$), & DLQ Replay Tests
# ============================================================================

class TestBackoffAndDLQ:
    """Tests for BackoffDLQHandler, exception taxonomy, and DLQ replay."""

    def test_exception_classification_taxonomy(self):
        """Verify transient errors are classified retryable; deterministic errors are non-retryable."""
        # Retryable
        assert classify_exception(TimeoutError("Read timeout")) is True
        assert classify_exception(ConnectionError("Connection lost")) is True
        assert classify_exception(MemoryError("OOM")) is True
        assert classify_exception(WorkerLostError("Worker SIGKILL")) is True

        # Non-retryable
        assert classify_exception(ValueError("Bad parameter")) is False
        assert classify_exception(FileNotFoundError("Missing file")) is False
        assert classify_exception(UnsupportedPDFError("Unreadable PDF")) is False
        assert classify_exception(EncryptedPDFError("Encrypted")) is False
        assert classify_exception(InvalidDocumentError("0 bytes")) is False

    def test_exponential_backoff_with_jitter_formula(self):
        """Verify exponential backoff progression $2^n + \\text{jitter}$."""
        handler = BackoffDLQHandler(base_delay=2.0, backoff_factor=2.0, max_backoff=30.0, jitter_max=1.0)

        # Attempt 1: 2.0 * (2^0) = 2.0s (+ 0..1s jitter)
        d1 = handler.compute_backoff_delay(1, jitter_seed=10)
        assert 2.0 <= d1 <= 3.0

        # Attempt 2: 2.0 * (2^1) = 4.0s (+ 0..1s jitter)
        d2 = handler.compute_backoff_delay(2, jitter_seed=10)
        assert 4.0 <= d2 <= 5.0

        # Attempt 3: 2.0 * (2^2) = 8.0s (+ 0..1s jitter)
        d3 = handler.compute_backoff_delay(3, jitter_seed=10)
        assert 8.0 <= d3 <= 9.0

        # High attempt capped at max_backoff + jitter
        d_cap = handler.compute_backoff_delay(10, jitter_seed=10)
        assert 30.0 <= d_cap <= 31.0

    def test_dlq_quarantine_and_replay_workflow(self, mock_redis):
        """Verify exhausting retries quarantines job, and replay resets state to QUEUED."""
        handler = BackoffDLQHandler(max_retries=2, redis_client=mock_redis)
        job_id = 777
        payload = {"job_id": job_id, "source_path": "doc.pdf"}

        # Attempt 1 transient failure -> retry
        r1 = handler.handle_task_failure(job_id, TimeoutError("Timeout 1"), 0, payload)
        assert r1["action"] == "retry"
        assert r1["retry_count"] == 1

        # Attempt 2 transient failure -> retry
        r2 = handler.handle_task_failure(job_id, TimeoutError("Timeout 2"), 1, r1["job_payload"])
        assert r2["action"] == "retry"
        assert r2["retry_count"] == 2

        # Attempt 3 (retry_count=2 >= max_retries=2) -> DLQ
        r3 = handler.handle_task_failure(job_id, TimeoutError("Timeout 3"), 2, r2["job_payload"])
        assert r3["action"] == "dlq"
        assert mock_redis.llen("blast_ocr:queue:dlq") == 1

        # Replay DLQ job
        replay = handler.replay_dlq_job(job_id, target_queue="blast_ocr:queue:high")
        assert replay["success"] is True
        assert replay["payload"]["status"] == JobState.QUEUED.value
        assert replay["payload"]["retry_count"] == 0
        assert mock_redis.llen("blast_ocr:queue:dlq") == 0
        assert mock_redis.llen("blast_ocr:queue:high") == 1


# ============================================================================
# 6. REST API Endpoints Integration Tests
# ============================================================================

class TestSwarmAPIRoutes:
    """Tests for /v1/workers, /v1/queues, /v1/queues/dlq, and /v1/ocr/jobs/{id}/retry."""

    @pytest.fixture
    def api_client(self):
        return TestClient(app)

    def test_create_ocr_job_with_priority_and_retries(self, api_client, tmp_path):
        """Verify POST /v1/ocr/jobs accepts priority and max_retries parameters."""
        dummy_file = tmp_path / "test.txt"
        dummy_file.write_text("Test content for OCR")

        with patch("blast_ocr.api.routes._execute_pipeline_task"):
            response = api_client.post(
                "/v1/ocr/jobs",
                data={
                    "source_path": str(dummy_file),
                    "ocr_engine": "rapidocr",
                    "priority": "high",
                    "max_retries": 5,
                },
            )
            assert response.status_code == 202
            data = response.json()
            assert data["job_id"] > 0
            assert data["status"] == "queued"
            assert data["priority"] == "high"

    def test_get_workers_fleet_telemetry(self, api_client, mock_redis):
        """Verify GET /v1/workers returns active swarm worker registry."""
        d = HeartbeatDaemon(redis_client=mock_redis, worker_id="worker_api_node_1")
        d.send_heartbeat(cpu_percent=15.0, rss_bytes=128 * 1024 * 1024)

        response = api_client.get("/v1/workers")
        assert response.status_code == 200
        data = response.json()
        assert "workers" in data
        assert data["total_active_workers"] >= 1
        w = data["workers"][0]
        assert "worker_id" in w
        assert "memory_rss_mb" in w

    def test_get_queues_depths_monitoring(self, api_client, mock_redis):
        """Verify GET /v1/queues returns depths for high, default, low, and dlq."""
        qm = PriorityQueueManager(redis_client=mock_redis)
        qm.enqueue("job_h", "h.pdf", priority=PriorityLevel.HIGH)
        qm.enqueue("job_d", "d.pdf", priority=PriorityLevel.DEFAULT)

        response = api_client.get("/v1/queues")
        assert response.status_code == 200
        data = response.json()
        assert data["queues"]["blast_ocr:queue:high"] == 1
        assert data["queues"]["blast_ocr:queue:default"] == 1
        assert data["total_pending_jobs"] >= 2

    def test_post_job_retry_failed_job(self, api_client):
        """Verify POST /v1/ocr/jobs/{id}/retry transitions job from FAILED to QUEUED."""
        db = OCRDatabase()
        job_id = db.create_job("failed_sample.pdf", 1)
        db.update_job_status(job_id, JobState.FAILED)
        db.close()

        response = api_client.post(f"/v1/ocr/jobs/{job_id}/retry?priority=high")
        assert response.status_code == 200
        data = response.json()
        assert data["job_id"] == job_id
        assert data["status"] == "queued"
        assert data["priority"] == "high"
        assert data["retry_count"] == 0

        # Verify DB status
        db_v = OCRDatabase()
        job = db_v.get_job(job_id)
        db_v.close()
        assert job.status == JobState.QUEUED.value

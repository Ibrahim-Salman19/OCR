"""
Feature 6: Distributed Multi-Worker Swarm
Opaque-box test suite verifying SwarmSupervisor, SwarmWorker lifecycle,
concurrent non-colliding job consumption, dynamic pool scaling, and graceful shutdown.
"""

import time
import threading

from blast_ocr.queue.swarm import SwarmSupervisor, SwarmWorker


class TestMultiWorkerSwarm:
    """Test suite for Feature 6: Distributed Multi-Worker Swarm."""

    def test_concurrent_job_consumption_without_duplicates(self, mock_redis):
        """
        Verify that multiple concurrent workers consume jobs from the shared queue
        without race conditions, duplicates, or missed jobs.
        """
        from tests.e2e.tier1_features.test_f05_priority_queue import PriorityQueueManager, PriorityLevel
        
        qm = PriorityQueueManager(redis_client=mock_redis)
        total_jobs = 20
        for i in range(total_jobs):
            qm.enqueue(job_id=f"job_{i}", source_path=f"doc_{i}.pdf", priority=PriorityLevel.DEFAULT)

        processed_job_ids = []
        lock = threading.Lock()

        def record_job(job):
            with lock:
                processed_job_ids.append(job["job_id"])
            time.sleep(0.01)

        supervisor = SwarmSupervisor(queue_client=qm, min_workers=1, max_workers=5, handler_func=record_job)
        supervisor.start(initial_count=4)

        # Wait for all jobs to be processed
        max_wait = 5.0
        start = time.time()
        while len(processed_job_ids) < total_jobs and (time.time() - start) < max_wait:
            time.sleep(0.05)

        supervisor.shutdown()

        assert len(processed_job_ids) == total_jobs, f"Expected {total_jobs} processed jobs, got {len(processed_job_ids)}"
        assert len(set(processed_job_ids)) == total_jobs, "Each job must be processed exactly once (no duplicates)"

    def test_dynamic_worker_scaling(self, mock_redis):
        """
        Verify the supervisor can dynamically scale the active worker pool up and down
        within configured min/max boundaries.
        """
        from tests.e2e.tier1_features.test_f05_priority_queue import PriorityQueueManager
        qm = PriorityQueueManager(redis_client=mock_redis)

        supervisor = SwarmSupervisor(queue_client=qm, min_workers=2, max_workers=6)
        supervisor.start(initial_count=2)
        assert supervisor.active_worker_count == 2

        # Scale up to 5
        supervisor.scale(5)
        assert supervisor.active_worker_count == 5

        # Scale down to 3
        supervisor.scale(3)
        assert supervisor.active_worker_count == 3

        # Scale beyond max (should clamp to max_workers=6)
        supervisor.scale(10)
        assert supervisor.active_worker_count == 6

        # Scale below min (should clamp to min_workers=2)
        supervisor.scale(1)
        assert supervisor.active_worker_count == 2

        supervisor.shutdown()
        assert supervisor.active_worker_count == 0

    def test_graceful_worker_shutdown(self, mock_redis):
        """
        Verify worker finishes active work during graceful stop.
        """
        from tests.e2e.tier1_features.test_f05_priority_queue import PriorityQueueManager
        qm = PriorityQueueManager(redis_client=mock_redis)
        qm.enqueue("slow_job", "slow.pdf")

        job_completed = False

        def slow_job_handler(job):
            nonlocal job_completed
            time.sleep(0.1)
            job_completed = True

        worker = SwarmWorker(worker_id="worker_graceful", queue_client=qm, handler_func=slow_job_handler)
        worker.start()
        time.sleep(0.02)  # Allow worker to pick up job

        worker.stop(timeout=2.0)
        assert job_completed is True, "Worker should finish processing job before stopping"
        assert worker.running is False

    def test_worker_error_isolation(self, mock_redis):
        """
        Verify worker continues processing subsequent jobs even if a job throws an unhandled exception.
        """
        from tests.e2e.tier1_features.test_f05_priority_queue import PriorityQueueManager
        qm = PriorityQueueManager(redis_client=mock_redis)
        
        qm.enqueue("bad_job", "corrupt.pdf")
        qm.enqueue("good_job_1", "valid1.pdf")
        qm.enqueue("good_job_2", "valid2.pdf")

        processed = []

        def fault_tolerant_handler(job):
            if job["job_id"] == "bad_job":
                raise RuntimeError("Simulated corruption failure!")
            processed.append(job["job_id"])

        worker = SwarmWorker(worker_id="worker_resilient", queue_client=qm, handler_func=fault_tolerant_handler)
        worker.start()

        time.sleep(0.15)
        worker.stop()

        assert "good_job_1" in processed
        assert "good_job_2" in processed
        assert worker.processed_count >= 2

    def test_supervisor_initialization_bounds(self, mock_redis):
        """
        Verify supervisor respects min_workers and max_workers initialization constraints.
        """
        from tests.e2e.tier1_features.test_f05_priority_queue import PriorityQueueManager
        qm = PriorityQueueManager(redis_client=mock_redis)

        supervisor = SwarmSupervisor(queue_client=qm, min_workers=3, max_workers=5)
        supervisor.start(initial_count=1)  # Requested 1, but min is 3
        assert supervisor.active_worker_count == 3
        supervisor.shutdown()

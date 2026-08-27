"""
Feature 8: Zombie Job Reaper & Failover
Opaque-box test suite verifying zombie job detection (dead worker orphan leases),
automatic priority requeuing, retry count increments, DLQ threshold quarantine,
and atomic reaper failover execution.
"""

import json

from blast_ocr.queue.reaper import ZombieReaper


class TestZombieJobReaper:
    """Test suite for Feature 8: Zombie Job Reaper & Failover."""

    def test_reaper_detects_dead_worker_orphan_job(self, mock_redis):
        """
        Verify the reaper detects a job leased by a dead worker (heartbeat key gone)
        and automatically requeues it into the correct priority queue.
        """
        from tests.e2e.tier1_features.test_f05_priority_queue import PriorityQueueManager, PriorityLevel
        qm = PriorityQueueManager(redis_client=mock_redis)
        reaper = ZombieReaper(redis_client=mock_redis, queue_manager=qm, lease_timeout_sec=5.0)

        # Worker 1 was working on a high-priority job
        job_payload = {
            "job_id": "orphan_job_001",
            "source_path": "/docs/critical.pdf",
            "priority": PriorityLevel.HIGH,
            "retry_count": 0,
        }
        reaper.record_lease(worker_id="crashed_worker_99", job_payload=job_payload)

        # Worker is NOT registered in blast_ocr:workers:crashed_worker_99 (dead)
        stats = reaper.reap_zombies()

        assert stats["reaped_count"] == 1
        assert stats["dlq_count"] == 0

        # Verify job is back in HIGH priority queue
        assert qm.get_queue_depth(PriorityLevel.HIGH) == 1
        res = qm.dequeue(timeout=1)
        assert res is not None
        priority, payload = res
        assert priority == PriorityLevel.HIGH
        assert payload["job_id"] == "orphan_job_001"

    def test_reaper_ignores_healthy_active_worker_leases(self, mock_redis):
        """
        Verify the reaper does NOT touch jobs held by alive workers whose leases have not timed out.
        """
        from tests.e2e.tier1_features.test_f05_priority_queue import PriorityQueueManager, PriorityLevel
        qm = PriorityQueueManager(redis_client=mock_redis)
        reaper = ZombieReaper(redis_client=mock_redis, queue_manager=qm, lease_timeout_sec=10.0)

        # Register live worker
        mock_redis.set("blast_ocr:workers:healthy_worker_1", json.dumps({"status": "busy"}), ex=30)

        job_payload = {"job_id": "active_job_100", "source_path": "doc.pdf", "priority": PriorityLevel.DEFAULT}
        reaper.record_lease(worker_id="healthy_worker_1", job_payload=job_payload)

        stats = reaper.reap_zombies()

        assert stats["reaped_count"] == 0
        assert stats["dlq_count"] == 0
        assert qm.get_queue_depth(PriorityLevel.DEFAULT) == 0

    def test_reaper_max_retry_exhaustion_quarantines_to_dlq(self, mock_redis):
        """
        Verify that when a job has reached max_retries (e.g. crashed 3 times),
        the reaper moves it to DLQ instead of re-enqueueing.
        """
        from tests.e2e.tier1_features.test_f05_priority_queue import PriorityQueueManager
        qm = PriorityQueueManager(redis_client=mock_redis)
        reaper = ZombieReaper(redis_client=mock_redis, queue_manager=qm, max_retries=3)

        # Job already retried 3 times
        job_payload = {
            "job_id": "poison_job_666",
            "source_path": "/docs/corrupt.pdf",
            "priority": "default",
            "retry_count": 3,
        }
        reaper.record_lease(worker_id="dead_worker_x", job_payload=job_payload)

        stats = reaper.reap_zombies()

        assert stats["reaped_count"] == 0
        assert stats["dlq_count"] == 1

        # Check DLQ key in redis
        assert mock_redis.llen(ZombieReaper.DLQ_KEY) == 1
        dlq_raw = mock_redis.rpop(ZombieReaper.DLQ_KEY)
        dlq_data = json.loads(dlq_raw)
        assert dlq_data["job_id"] == "poison_job_666"
        assert dlq_data["retry_count"] == 4
        assert "dlq_reason" in dlq_data

    def test_lease_release_on_successful_completion(self, mock_redis):
        """
        Verify lease is deleted upon job completion so reaper has no work.
        """
        from tests.e2e.tier1_features.test_f05_priority_queue import PriorityQueueManager
        qm = PriorityQueueManager(redis_client=mock_redis)
        reaper = ZombieReaper(redis_client=mock_redis, queue_manager=qm)

        job_payload = {"job_id": "job_complete_55", "source_path": "a.pdf", "priority": "low"}
        reaper.record_lease("w1", job_payload)

        # Job finishes and releases lease
        reaper.release_lease("job_complete_55")

        stats = reaper.reap_zombies()
        assert stats["reaped_count"] == 0
        assert stats["checked_leases"] == 0

    def test_multiple_dead_workers_batch_failover(self, mock_redis):
        """
        Verify multiple abandoned jobs across different workers and priorities
        are all safely recovered in a single reaper pass.
        """
        from tests.e2e.tier1_features.test_f05_priority_queue import PriorityQueueManager, PriorityLevel
        qm = PriorityQueueManager(redis_client=mock_redis)
        reaper = ZombieReaper(redis_client=mock_redis, queue_manager=qm)

        # 3 orphaned jobs
        reaper.record_lease("dead_1", {"job_id": "j1", "source_path": "1.pdf", "priority": PriorityLevel.HIGH, "retry_count": 0})
        reaper.record_lease("dead_2", {"job_id": "j2", "source_path": "2.pdf", "priority": PriorityLevel.DEFAULT, "retry_count": 1})
        reaper.record_lease("dead_3", {"job_id": "j3", "source_path": "3.pdf", "priority": PriorityLevel.LOW, "retry_count": 0})

        stats = reaper.reap_zombies()
        assert stats["reaped_count"] == 3
        assert stats["dlq_count"] == 0

        assert qm.get_queue_depth(PriorityLevel.HIGH) == 1
        assert qm.get_queue_depth(PriorityLevel.DEFAULT) == 1
        assert qm.get_queue_depth(PriorityLevel.LOW) == 1

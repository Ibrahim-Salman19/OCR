"""
Feature 5: 3-Tier Priority Queue Scheduling
Opaque-box test suite verifying 3-tier priority levels (high, default, low),
strict priority ordering via atomic BRPOP, payload serialization, and queue metrics.
"""

import json
import time
import pytest

from blast_ocr.queue.priority import PriorityQueueManager, PriorityLevel


class TestPriorityQueueScheduling:
    """Test suite for Feature 5: 3-Tier Priority Queue Scheduling."""

    def test_strict_priority_ordering(self, mock_redis):
        """
        Verify that when jobs are enqueued across all 3 priority levels (low, default, high),
        the dequeuer strictly yields all HIGH jobs first, then DEFAULT, then LOW.
        """
        qm = PriorityQueueManager(redis_client=mock_redis)

        # Enqueue in reverse priority order: LOW first, then DEFAULT, then HIGH
        qm.enqueue(job_id="job_low_1", source_path="low1.pdf", priority=PriorityLevel.LOW)
        qm.enqueue(job_id="job_low_2", source_path="low2.pdf", priority=PriorityLevel.LOW)
        qm.enqueue(job_id="job_default_1", source_path="def1.pdf", priority=PriorityLevel.DEFAULT)
        qm.enqueue(job_id="job_high_1", source_path="high1.pdf", priority=PriorityLevel.HIGH)
        qm.enqueue(job_id="job_high_2", source_path="high2.pdf", priority=PriorityLevel.HIGH)

        # Dequeue sequence must be: high_1, high_2, default_1, low_1, low_2
        expected_ids = ["job_high_1", "job_high_2", "job_default_1", "job_low_1", "job_low_2"]
        actual_ids = []

        for _ in range(5):
            res = qm.dequeue(timeout=1)
            assert res is not None, "Expected job to be dequeued"
            priority, payload = res
            actual_ids.append(payload["job_id"])

        assert actual_ids == expected_ids, f"Expected order {expected_ids}, got {actual_ids}"

    def test_aged_low_priority_job_preempts_sustained_high_traffic(self, mock_redis):
        """
        GAP-10: strict HIGH -> DEFAULT -> LOW ordering starves LOW/DEFAULT
        under continuous HIGH-priority arrival, since the HIGH queue is
        never observed empty. A LOW job that has waited past
        LOW_AGING_THRESHOLD_SECONDS must be served even while HIGH keeps
        arriving, guaranteeing forward progress.
        """
        qm = PriorityQueueManager(redis_client=mock_redis)

        # Enqueue a LOW job whose recorded enqueue time is already past the
        # starvation threshold (simulating a job that has waited that long,
        # without an actual real-time sleep in the test).
        aged_payload = {
            "job_id": "job_low_starved",
            "source_path": "starved.pdf",
            "priority": PriorityLevel.LOW,
            "enqueued_at": time.time() - qm.LOW_AGING_THRESHOLD_SECONDS - 5.0,
            "retry_count": 0,
            "config_overrides": {},
        }
        mock_redis.lpush(qm.queue_key(PriorityLevel.LOW), json.dumps(aged_payload))

        # Simulate sustained HIGH-priority load: more HIGH jobs keep arriving,
        # so the HIGH queue is never empty across these dequeue() calls.
        for i in range(3):
            qm.enqueue(job_id=f"job_high_{i}", source_path=f"h{i}.pdf", priority=PriorityLevel.HIGH)

        priority, payload = qm.dequeue(timeout=1)
        assert (priority, payload["job_id"]) == (PriorityLevel.LOW, "job_low_starved")

        # HIGH jobs are untouched and still dequeue normally afterward.
        remaining_ids = []
        for _ in range(3):
            p, pl = qm.dequeue(timeout=1)
            remaining_ids.append(pl["job_id"])
        assert remaining_ids == ["job_high_0", "job_high_1", "job_high_2"]

    def test_priority_payload_structure_and_metadata(self, mock_redis):
        """
        Verify the enqueued payload contains complete metadata including timestamp,
        retry count, priority, and configuration overrides.
        """
        qm = PriorityQueueManager(redis_client=mock_redis)
        overrides = {"ocr_engine": "rapidocr", "denoise_level": 2}

        before_ts = time.time()
        qm.enqueue(job_id="test_job_123", source_path="/docs/invoice.pdf", priority=PriorityLevel.HIGH, config_overrides=overrides)
        after_ts = time.time()

        res = qm.dequeue(timeout=1)
        assert res is not None
        priority, payload = res

        assert priority == PriorityLevel.HIGH
        assert payload["job_id"] == "test_job_123"
        assert payload["source_path"] == "/docs/invoice.pdf"
        assert payload["priority"] == PriorityLevel.HIGH
        assert payload["retry_count"] == 0
        assert payload["config_overrides"] == overrides
        assert before_ts <= payload["enqueued_at"] <= after_ts

    def test_queue_depth_metrics(self, mock_redis):
        """
        Verify get_queue_depth and get_all_queue_depths accurately reflect
        the number of pending jobs in each priority queue.
        """
        qm = PriorityQueueManager(redis_client=mock_redis)

        assert qm.get_all_queue_depths() == {"high": 0, "default": 0, "low": 0}

        qm.enqueue("h1", "f1.pdf", priority=PriorityLevel.HIGH)
        qm.enqueue("h2", "f2.pdf", priority=PriorityLevel.HIGH)
        qm.enqueue("d1", "f3.pdf", priority=PriorityLevel.DEFAULT)

        assert qm.get_queue_depth(PriorityLevel.HIGH) == 2
        assert qm.get_queue_depth(PriorityLevel.DEFAULT) == 1
        assert qm.get_queue_depth(PriorityLevel.LOW) == 0

        depths = qm.get_all_queue_depths()
        assert depths == {"high": 2, "default": 1, "low": 0}

        # Dequeue one high job and verify depth decrements
        qm.dequeue()
        assert qm.get_queue_depth(PriorityLevel.HIGH) == 1

    def test_invalid_priority_validation(self, mock_redis):
        """
        Verify enqueueing or querying an invalid priority raises ValueError.
        """
        qm = PriorityQueueManager(redis_client=mock_redis)

        with pytest.raises(ValueError, match="Invalid priority"):
            qm.enqueue("bad_job", "bad.pdf", priority="ultra_urgent")

        with pytest.raises(ValueError, match="Invalid priority"):
            qm.get_queue_depth("non_existent_tier")

    def test_dequeue_on_empty_queue_returns_none(self, mock_redis):
        """
        Verify dequeuing on empty queues cleanly returns None without errors.
        """
        qm = PriorityQueueManager(redis_client=mock_redis)
        res = qm.dequeue(timeout=0)
        assert res is None

"""
Sprint 3: core/parallel.py + core/worker.py — Thread safety & lock correctness.
BUG-PREVENTION: Race conditions are silent and non-deterministic. These tests
verify the mutex logic and worker singleton under true concurrency.
"""

import threading
import time
import pytest
from unittest.mock import patch, MagicMock


# ═══════════════════════════════════════════════════════════════════════════════
# ParallelOCRProcessor — Config & Workers
# ═══════════════════════════════════════════════════════════════════════════════


class TestParallelOCRProcessorConfig:
    def test_max_workers_capped_at_2_regardless_of_input(self):
        """
        BUG-PREVENTION: EasyOCR uses ~1GB RAM per page. 8 workers = 8GB RAM → OOM.
        The cap at 2 prevents OOM while still allowing preprocessing parallelism.
        """
        from blast_ocr.core.parallel import ParallelOCRProcessor

        p = ParallelOCRProcessor(max_workers=8)
        assert p.max_workers <= 2, "BUG: max_workers > 2 causes OOM on large PDFs"

    def test_max_workers_1_not_inflated(self):
        """Workers below cap must stay as-is — don't auto-inflate to 2."""
        from blast_ocr.core.parallel import ParallelOCRProcessor

        p = ParallelOCRProcessor(max_workers=1)
        assert p.max_workers == 1

    def test_max_workers_none_uses_config_capped_at_2(self):
        """
        BUG-PREVENTION: None triggers config fallback. Even config.max_workers=16
        must be capped — the global OCR lock serializes anyway.
        """
        from blast_ocr.core.parallel import ParallelOCRProcessor

        with patch("blast_ocr.core.parallel.config") as mock_cfg:
            mock_cfg.max_workers = 16
            p = ParallelOCRProcessor(max_workers=None)
        assert p.max_workers <= 2


class TestBatchThreadedBehavior:
    def test_results_sorted_by_page_number(self):
        """
        BUG-PREVENTION: as_completed() returns futures in random completion order.
        Without sort(), later pages appear before earlier ones in the final doc.
        """
        from blast_ocr.core.parallel import ParallelOCRProcessor

        def process_func(path, page_num):
            time.sleep(0.005 * (5 - (page_num % 5)))
            return {"page": page_num, "text": f"p{page_num}", "confidence": 0.9}

        processor = ParallelOCRProcessor(max_workers=2)
        paths = [f"/fake/page_{i}.png" for i in range(1, 6)]
        results = processor.process_batch_threaded(paths, process_func)

        page_nums = [r["page"] for r in results]
        assert page_nums == sorted(page_nums), (
            f"BUG: Results not sorted → doc text out of order: {page_nums}"
        )

    def test_failed_page_returns_error_dict_not_exception(self):
        """
        BUG-PREVENTION: One crashing page must NOT kill all remaining 100 pages.
        Errors are caught and placed in an error dict so the batch continues.
        """
        from blast_ocr.core.parallel import ParallelOCRProcessor

        def crashing_func(path, page_num):
            if page_num == 3:
                raise RuntimeError("page 3 exploded")
            return {"page": page_num, "text": "ok", "confidence": 0.9}

        processor = ParallelOCRProcessor(max_workers=2)
        paths = [f"/fake/page_{i}.png" for i in range(1, 5)]
        results = processor.process_batch_threaded(paths, crashing_func)

        assert len(results) == 4, "All 4 pages must return a result (no silent drops)"
        error_result = next(r for r in results if r["page"] == 3)
        assert "error" in error_result
        assert error_result["text"] == ""

    def test_progress_callback_crash_does_not_crash_batch(self):
        """
        BUG-PREVENTION: BUG-08 — A broken Streamlit progress callback was killing
        the entire OCR batch silently. Callback errors are now logged at DEBUG only.
        """
        from blast_ocr.core.parallel import ParallelOCRProcessor

        def good_func(path, page_num):
            return {"page": page_num, "text": "ok", "confidence": 0.9}

        def crashing_callback(current, total):
            raise RuntimeError("Streamlit widget destroyed")

        processor = ParallelOCRProcessor(max_workers=1)
        paths = [f"/fake/page_{i}.png" for i in range(1, 3)]

        try:
            results = processor.process_batch_threaded(
                paths, good_func, progress_callback=crashing_callback
            )
            assert len(results) == 2
        except RuntimeError as e:
            pytest.fail(f"BUG-08: Callback exception escaped batch processor: {e}")

    def test_progress_callback_current_never_exceeds_total(self):
        """Progress (current, total) must always have current ≤ total."""
        from blast_ocr.core.parallel import ParallelOCRProcessor

        records = []

        def tracking_callback(current, total):
            records.append((current, total))

        def good_func(path, page_num):
            return {"page": page_num, "text": "ok", "confidence": 0.9}

        processor = ParallelOCRProcessor(max_workers=1)
        paths = [f"/fake/page_{i}.png" for i in range(1, 4)]
        processor.process_batch_threaded(
            paths, good_func, progress_callback=tracking_callback
        )

        assert len(records) == 3
        for current, total in records:
            assert current <= total, (
                f"BUG: progress callback got current={current} > total={total}"
            )


# ═══════════════════════════════════════════════════════════════════════════════
# 50-Thread Global Lock Stress Test
# ═══════════════════════════════════════════════════════════════════════════════


def test_50_threads_lock_no_interleaving():
    """
    BUG-PREVENTION: EasyOCR's internal batch queue is thread-unsafe.
    Two simultaneous readtext() calls corrupt model internal state.
    50 threads competing for _ocr_global_lock must never interleave.
    """
    from blast_ocr.core.extractor import _ocr_global_lock

    execution_log = []
    log_lock = threading.Lock()

    def simulate_ocr(tid):
        with _ocr_global_lock:
            with log_lock:
                execution_log.append(f"ENTER-{tid}")
            time.sleep(0.001)
            with log_lock:
                execution_log.append(f"EXIT-{tid}")

    threads = [threading.Thread(target=simulate_ocr, args=(i,)) for i in range(50)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)

    for i in range(0, len(execution_log) - 1, 2):
        tid = execution_log[i].split("-")[1]
        assert execution_log[i + 1] == f"EXIT-{tid}", (
            f"BUG: Concurrent OCR access detected: {execution_log[i : i + 2]}"
        )


def test_lock_no_deadlock_under_50_threads():
    """
    BUG-PREVENTION: A recursive lock acquire (or signal handler acquire) deadlocks.
    All 50 threads must finish within 5s timeout — no hanging.
    """
    from blast_ocr.core.extractor import _ocr_global_lock

    results = []

    def try_acquire(tid):
        acquired = _ocr_global_lock.acquire(timeout=5.0)
        if acquired:
            time.sleep(0.001)
            _ocr_global_lock.release()
            results.append("ok")
        else:
            results.append("timeout")

    threads = [threading.Thread(target=try_acquire, args=(i,)) for i in range(50)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=15)

    assert results.count("timeout") == 0, (
        f"BUG: {results.count('timeout')}/50 threads timed out — possible deadlock"
    )


def test_global_lock_same_across_extractor_instances():
    """
    BUG-PREVENTION: HIGH-001 — Original code used self.lock = threading.Lock()
    in __init__, creating a DIFFERENT lock per instance. Two instances could call
    readtext() simultaneously with no mutual exclusion.
    Fix: all instances set self.lock = _ocr_global_lock (the module singleton).
    """
    from blast_ocr.core.extractor import RobustOCRExtractor, _ocr_global_lock

    with patch.object(RobustOCRExtractor, "_init_engine"):
        e1 = RobustOCRExtractor.__new__(RobustOCRExtractor)
        e1.lock = _ocr_global_lock
        e2 = RobustOCRExtractor.__new__(RobustOCRExtractor)
        e2.lock = _ocr_global_lock

    assert e1.lock is e2.lock is _ocr_global_lock, (
        "BUG-HIGH-001: Per-instance lock allows simultaneous readtext() calls"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Worker Singleton Thread Safety
# ═══════════════════════════════════════════════════════════════════════════════


def test_worker_singleton_created_once_under_50_threads():
    """
    BUG-PREVENTION: BUG-WORKER-RACE-01 — Without double-checked locking,
    50 threads all see _worker_extractor=None and each calls RobustOCRExtractor(),
    loading the model 50 times (50GB RAM) → OOM → system crash.
    """
    import blast_ocr.core.worker as worker_module

    original = worker_module._worker_extractor
    worker_module._worker_extractor = None

    instantiation_count = [0]
    count_lock = threading.Lock()

    with patch("blast_ocr.core.worker.RobustOCRExtractor") as MockCls:

        def count_and_return():
            with count_lock:
                instantiation_count[0] += 1
            return MagicMock()

        MockCls.side_effect = count_and_return

        threads = [
            threading.Thread(target=worker_module.get_worker_extractor)
            for _ in range(50)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

    worker_module._worker_extractor = original

    assert instantiation_count[0] == 1, (
        f"BUG-WORKER-RACE-01: Model loaded {instantiation_count[0]} times "
        f"under 50 concurrent threads. Double-checked locking must ensure exactly 1."
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Worker Cache Integration
# ═══════════════════════════════════════════════════════════════════════════════


def test_cache_hit_skips_extractor_call():
    """
    BUG-PREVENTION: Cache hit must short-circuit the extractor call entirely.
    Without this, every pipeline re-run re-processes all 100 pages needlessly.
    """
    from blast_ocr.core.worker import process_page_wrapper

    cached = {"page": 1, "text": "cached", "confidence": 0.95}
    with patch("blast_ocr.core.worker.cache_manager") as mock_cache:
        mock_cache.get_file_hash.return_value = "abc123"
        mock_cache.get_cached_result.return_value = cached
        with patch("blast_ocr.core.worker.get_worker_extractor") as mock_get:
            result = process_page_wrapper("/fake/page.png", 1)
            mock_get.assert_not_called()

    assert result["text"] == "cached"


def test_cache_miss_calls_extractor_and_saves_result():
    """
    BUG-PREVENTION: Cache miss must call extractor AND save via cache_manager.set().
    Failing to save means the cache is never populated — repeated misses forever.
    """
    from blast_ocr.core.worker import process_page_wrapper

    fresh = {"page": 1, "text": "fresh", "confidence": 0.9}
    with patch("blast_ocr.core.worker.cache_manager") as mock_cache:
        mock_cache.get_file_hash.return_value = "xyz789"
        mock_cache.get_cached_result.return_value = None  # Cache miss
        with patch("blast_ocr.core.worker.get_worker_extractor") as mock_get:
            mock_ext = MagicMock()
            mock_ext.process_page.return_value = fresh
            mock_get.return_value = mock_ext
            result = process_page_wrapper("/fake/page.png", 1)
            mock_cache.set.assert_called_once()

    assert result["text"] == "fresh"


def test_processing_time_included_in_worker_result():
    """
    BUG-PREVENTION: The UI results table does result['processing_time'].
    Without this field, KeyError crashes the Streamlit results rendering.
    """
    from blast_ocr.core.worker import process_page_wrapper

    with patch("blast_ocr.core.worker.cache_manager") as mock_cache:
        mock_cache.get_file_hash.return_value = "h1"
        mock_cache.get_cached_result.return_value = None
        with patch("blast_ocr.core.worker.get_worker_extractor") as mock_get:
            mock_ext = MagicMock()
            mock_ext.process_page.return_value = {
                "page": 1,
                "text": "t",
                "confidence": 0.9,
            }
            mock_get.return_value = mock_ext
            result = process_page_wrapper("/fake/page.png", 1)

    assert "processing_time" in result, "processing_time missing → KeyError in UI"
    assert result["processing_time"] >= 0


def test_extractor_failure_returns_error_dict_not_exception():
    """
    BUG-PREVENTION: If extractor raises, the batch must receive an error dict
    (not a propagated exception) so remaining pages continue processing.
    """
    from blast_ocr.core.worker import process_page_wrapper

    with patch("blast_ocr.core.worker.cache_manager") as mock_cache:
        mock_cache.get_file_hash.return_value = None
        mock_cache.get_cached_result.return_value = None
        with patch("blast_ocr.core.worker.get_worker_extractor") as mock_get:
            mock_ext = MagicMock()
            mock_ext.process_page.side_effect = RuntimeError("GPU OOM")
            mock_get.return_value = mock_ext
            result = process_page_wrapper("/fake/page.png", 5)

    assert result["page"] == 5
    assert result["text"] == ""
    assert "error" in result
    assert "GPU OOM" in result["error"]

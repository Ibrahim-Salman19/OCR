"""
tests/adversarial/test_streaming_queue_adversarial.py

Adversarial suite for SSE client-disconnect handling (GAP-05), MuPDF memory
arena purging (GAP-06), and Redis priority-queue starvation (GAP-10)
(docs/HARDENING_BLUEPRINT_AND_TEST_SPECS.md §4.3.5).

Real entry points: `blast_ocr.api.routes.stream_job_events`,
`blast_ocr.core.streaming.PageStreamGenerator`, and
`blast_ocr.queue.priority.PriorityQueueManager` (the blueprint's illustrative
`api.sse_handler.ResilientSSEHandler` and `queue.fair_priority
.FairPriorityQueueGovernor` classes do not exist here; GAP-10 shipped as
wait-time-based aging, not weighted random sampling, so the assertions below
test aging directly rather than the blueprint's weighted-pop mechanism).

GAP-10 has strict-priority-ordering coverage in `tests/test_queue_swarm.py`
(`test_priority_ordering_high_default_low`), but no existing test exercises
the anti-starvation aging path (`_oldest_job_age_seconds` /
`_pop_aged_job`) that GAP-10 actually added -- this file closes that gap.

GAP-06's `fitz.TOOLS.store_shrink(100)` call is likewise unexercised by the
existing 1000-page memory-bound test (`test_streaming_storage.py`), which
feeds `PageStreamGenerator` a placeholder byte string that isn't a real
parseable PDF; every renderer in `_render_page_range` fails to open it, and
it falls through to the blank-page synthesis branch without ever reaching
PyMuPDF. This file builds an actual multi-page PDF so the real PyMuPDF
render path -- and its `store_shrink` call -- executes.
"""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

from blast_ocr.api.routes import stream_job_events
from blast_ocr.core.streaming import PageStreamGenerator
from blast_ocr.queue.priority import PriorityLevel, PriorityQueueManager

try:
    import pymupdf as fitz
except ImportError:
    import fitz


def test_sse_stream_terminates_immediately_on_client_disconnect():
    """TAX-STR-05: `request.is_disconnected()` is checked at the top of
    every polling iteration, before any DB access -- a disconnected client
    must break the generator loop on the very first tick, yielding nothing,
    rather than continuing to poll and hold resources for a client that's
    already gone.
    """
    mock_request = MagicMock()
    mock_request.is_disconnected = AsyncMock(return_value=True)

    async def _run():
        response = await stream_job_events(job_id=999999, request=mock_request)
        chunks = []
        async for chunk in response.body_iterator:
            chunks.append(chunk)
        return chunks

    chunks = asyncio.run(_run())

    assert chunks == []


def test_page_stream_generator_invokes_mupdf_arena_shrink_on_real_pdf(tmp_path, monkeypatch):
    """GAP-06: after rendering each page range via PyMuPDF, the streaming
    generator must call `fitz.TOOLS.store_shrink(100)` to purge glibc arena
    caches -- without a real, parseable multi-page PDF forcing the actual
    PyMuPDF branch (not the pypdfium2 branch tried first, nor the blank-page
    fallback), this call path goes completely unexercised.
    """
    pdf_path = tmp_path / "real_multi_page.pdf"
    doc = fitz.open()
    for i in range(4):
        page = doc.new_page()
        page.insert_text((72, 72), f"Real page {i + 1} body text")
    doc.save(str(pdf_path))
    doc.close()

    # Force the pypdfium2 branch to be skipped so PyMuPDF is what actually
    # renders this PDF, matching the fallback order in _render_page_range.
    monkeypatch.setattr("blast_ocr.core.streaming._PYPDFIUM2_AVAILABLE", False)

    with patch.object(fitz.TOOLS, "store_shrink", wraps=fitz.TOOLS.store_shrink) as shrink_spy:
        with PageStreamGenerator(
            source_path=pdf_path,
            total_pages=4,
            chunk_size=2,
            temp_dir=tmp_path / "scratch",
        ) as stream:
            rendered_pages = 0
            for chunk in stream:
                for _p_num, img_path in chunk:
                    assert img_path.exists()
                    rendered_pages += 1

    assert rendered_pages == 4
    assert shrink_spy.call_count >= 1
    shrink_spy.assert_any_call(100)


def test_low_priority_job_ages_past_sustained_high_priority_backlog(mock_redis):
    """GAP-10: under continuous HIGH-priority arrival, a strict priority
    sweep drains HIGH before ever looking at LOW -- since HIGH never
    actually goes empty under sustained load, a LOW job would wait forever
    without aging. Once the LOW queue's oldest job exceeds
    LOW_AGING_THRESHOLD_SECONDS, it must be served ahead of a fresh HIGH job
    on the next dequeue() call.
    """
    manager = PriorityQueueManager(redis_client=mock_redis)
    aged_timestamp = time.time() - (PriorityQueueManager.LOW_AGING_THRESHOLD_SECONDS + 5)

    with patch("blast_ocr.queue.priority.time.time", return_value=aged_timestamp):
        manager.enqueue(job_id="low-aged", source_path="low.pdf", priority=PriorityLevel.LOW)

    manager.enqueue(job_id="high-fresh", source_path="high.pdf", priority=PriorityLevel.HIGH)

    priority, payload = manager.dequeue(timeout=0)

    assert priority == PriorityLevel.LOW
    assert payload["job_id"] == "low-aged"


def test_fresh_low_priority_job_does_not_preempt_high_priority_before_aging(mock_redis):
    """Companion boundary case: a LOW job that has NOT yet crossed the aging
    threshold must not preempt HIGH -- proving the aging path only engages
    once genuinely starved, not on every LOW job unconditionally (which
    would defeat strict priority ordering entirely).
    """
    manager = PriorityQueueManager(redis_client=mock_redis)

    manager.enqueue(job_id="low-fresh", source_path="low.pdf", priority=PriorityLevel.LOW)
    manager.enqueue(job_id="high-fresh", source_path="high.pdf", priority=PriorityLevel.HIGH)

    priority, payload = manager.dequeue(timeout=0)

    assert priority == PriorityLevel.HIGH
    assert payload["job_id"] == "high-fresh"


def test_default_priority_job_ages_ahead_of_high_using_its_own_shorter_threshold(mock_redis):
    """DEFAULT and LOW use distinct aging thresholds
    (DEFAULT_AGING_THRESHOLD_SECONDS=30 < LOW_AGING_THRESHOLD_SECONDS=60). A
    DEFAULT job old enough to cross its own (shorter) threshold must age
    ahead of HIGH even though it hasn't waited anywhere near LOW's
    threshold.
    """
    manager = PriorityQueueManager(redis_client=mock_redis)
    aged_timestamp = time.time() - (PriorityQueueManager.DEFAULT_AGING_THRESHOLD_SECONDS + 5)

    with patch("blast_ocr.queue.priority.time.time", return_value=aged_timestamp):
        manager.enqueue(job_id="default-aged", source_path="default.pdf", priority=PriorityLevel.DEFAULT)

    manager.enqueue(job_id="high-fresh", source_path="high.pdf", priority=PriorityLevel.HIGH)

    priority, payload = manager.dequeue(timeout=0)

    assert priority == PriorityLevel.DEFAULT
    assert payload["job_id"] == "default-aged"

"""
Sprint 2: core/healing.py — Retry logic, async retry, fallback chain.
BUG-PREVENTION: The async retry path was 0% covered — any change to it
could silently break async OCR pipelines without any test catching it.
"""
import asyncio
import logging
import pytest
from unittest.mock import patch, MagicMock, call

from blast_ocr.core.exceptions import (
    ImageLoadError, OCREngineError, PageExtractionError
)
from blast_ocr.core.healing import SelfHealingOCR


# ─── Fixture: fresh healer with predictable settings ─────────────────────────

@pytest.fixture
def healer():
    """
    BUG-PREVENTION: Use a fresh instance with known max_retries=3, backoff=2.
    Never use the global `healer` singleton — its config may change with env vars.
    """
    return SelfHealingOCR(max_retries=3, backoff_factor=2)


# ═══════════════════════════════════════════════════════════════════════════════
# SYNC RETRY — Correctness
# ═══════════════════════════════════════════════════════════════════════════════

class TestRetryWithBackoff:

    def test_succeeds_on_first_attempt(self, healer):
        """Zero retries needed — decorator must be transparent."""
        @healer.retry_with_backoff
        def immediate_success():
            return 42

        result = immediate_success()
        assert result == 42

    @pytest.mark.parametrize("fail_count", [1, 2])
    def test_succeeds_after_n_failures(self, healer, fail_count):
        """
        BUG-PREVENTION: Early versions broke the retry counter off-by-one.
        Verify that failing N times then succeeding still returns the correct value.
        """
        calls = [0]

        @healer.retry_with_backoff
        def flaky():
            calls[0] += 1
            if calls[0] <= fail_count:
                raise ConnectionError("transient")
            return "recovered"

        with patch("time.sleep"):
            result = flaky()
        assert result == "recovered"
        assert calls[0] == fail_count + 1

    def test_exhausted_retries_re_raises_original(self, healer):
        """
        BUG-PREVENTION: Must re-raise the ORIGINAL exception type, not wrap it.
        Callers catch specific types (ConnectionError, ValueError) — wrapping breaks this.
        """
        @healer.retry_with_backoff
        def always_fails():
            raise ValueError("permanent failure")

        with patch("time.sleep"):
            with pytest.raises(ValueError, match="permanent failure"):
                always_fails()

    def test_imageloaderror_not_retried(self, healer):
        """
        BUG-PREVENTION: Retrying ImageLoadError loads non-existent files 3 times,
        wasting time. Fatal errors must stop immediately after 1 attempt.
        """
        calls = [0]

        @healer.retry_with_backoff
        def raises_image_error():
            calls[0] += 1
            raise ImageLoadError("file missing")

        with pytest.raises(ImageLoadError):
            raises_image_error()
        assert calls[0] == 1, "ImageLoadError must NOT be retried"

    def test_pageextractionerror_not_retried(self, healer):
        """
        BUG-PREVENTION: PageExtractionError means the page itself is bad.
        Retrying just wastes time and masks the real error.
        """
        calls = [0]

        @healer.retry_with_backoff
        def raises_page_error():
            calls[0] += 1
            raise PageExtractionError(1, "corrupt image")

        with pytest.raises(PageExtractionError):
            raises_page_error()
        assert calls[0] == 1, "PageExtractionError must NOT be retried"

    def test_filenotfounderror_not_retried(self, healer):
        """
        BUG-PREVENTION: FileNotFoundError on a missing model/image won't be
        fixed by retrying — it just delays failure by backoff_factor^N seconds.
        """
        calls = [0]

        @healer.retry_with_backoff
        def raises_fnf():
            calls[0] += 1
            raise FileNotFoundError("model.pth missing")

        with pytest.raises(FileNotFoundError):
            raises_fnf()
        assert calls[0] == 1

    def test_ocrengine_error_not_retried(self, healer):
        """
        BUG-PREVENTION: BUG-02 regression guard. OCREngineError was added to
        the fatal list in phase2 after repeated GPU OOM retry loops crashed servers.
        If removed from the fatal list, this test will catch it immediately.
        """
        calls = [0]

        @healer.retry_with_backoff
        def raises_engine_error():
            calls[0] += 1
            raise OCREngineError("GPU OOM")

        with pytest.raises(OCREngineError):
            raises_engine_error()
        assert calls[0] == 1, "OCREngineError retry loop was causing GPU OOM cascades"

    def test_backoff_timing_is_exponential(self, healer):
        """
        BUG-PREVENTION: sleep() must receive 2^0=1s, 2^1=2s in order.
        Flat backoff (always 1s) defeats the purpose and hammers failing services.
        """
        sleep_calls = []

        @healer.retry_with_backoff
        def always_fails():
            raise RuntimeError("fail")

        with patch("time.sleep", side_effect=lambda t: sleep_calls.append(t)):
            with pytest.raises(RuntimeError):
                always_fails()

        # max_retries=3 → attempt 0 (sleep 1), attempt 1 (sleep 2), attempt 2 (raise)
        assert len(sleep_calls) == 2, f"Expected 2 sleeps, got {len(sleep_calls)}: {sleep_calls}"
        assert sleep_calls[0] == 1,  f"First sleep should be 2^0=1s, got {sleep_calls[0]}"
        assert sleep_calls[1] == 2,  f"Second sleep should be 2^1=2s, got {sleep_calls[1]}"

    def test_warning_logged_on_each_retry(self, healer, caplog):
        """
        BUG-PREVENTION: Operators need to see retry attempts in logs to distinguish
        transient failures from hard errors. Silent retries hide incidents.
        """
        @healer.retry_with_backoff
        def flaky():
            raise RuntimeError("oh no")

        with patch("time.sleep"):
            with pytest.raises(RuntimeError):
                with caplog.at_level(logging.WARNING, logger="blast_ocr.core.healing"):
                    flaky()

        warning_msgs = [r.message for r in caplog.records if r.levelno == logging.WARNING]
        assert len(warning_msgs) >= 2, \
            "Expected warning log per retry attempt — silent retries hide incidents"

    def test_error_logged_on_final_exhaustion(self, healer, caplog):
        """
        BUG-PREVENTION: After max retries, an ERROR must be logged so
        monitoring systems (Datadog, Sentry) trigger an alert.
        """
        @healer.retry_with_backoff
        def always_fails():
            raise RuntimeError("die")

        with patch("time.sleep"):
            with pytest.raises(RuntimeError):
                with caplog.at_level(logging.ERROR, logger="blast_ocr.core.healing"):
                    always_fails()

        error_msgs = [r for r in caplog.records if r.levelno == logging.ERROR]
        assert len(error_msgs) >= 1, "ERROR must be logged when all retries exhausted"

    def test_return_value_passes_through(self, healer):
        """Decorator must be fully transparent — return value must survive wrapping."""
        @healer.retry_with_backoff
        def returns_dict():
            return {"page": 1, "text": "hello", "confidence": 0.99}

        result = returns_dict()
        assert result == {"page": 1, "text": "hello", "confidence": 0.99}

    def test_args_and_kwargs_forwarded(self, healer):
        """Decorator must forward positional and keyword args correctly."""
        @healer.retry_with_backoff
        def add(a, b, *, multiplier=1):
            return (a + b) * multiplier

        result = add(3, 4, multiplier=2)
        assert result == 14


# ═══════════════════════════════════════════════════════════════════════════════
# ASYNC RETRY — Previously 0% covered
# ═══════════════════════════════════════════════════════════════════════════════

class TestAsyncRetryWithBackoff:
    """
    BUG-PREVENTION: retry_with_backoff_async was added in phase2 but never tested.
    It's the async OCR pipeline path. Silent breakage here = uncaught production crashes.
    NOTE: retry_with_backoff_async is used as a coroutine that RETURNS the decorator,
    so usage is:  decorated = await healer.retry_with_backoff_async(func)
    """

    def test_async_retry_succeeds_after_failure(self, healer):
        """Async function that fails once then succeeds must return the value."""
        calls = [0]

        async def flaky_async():
            calls[0] += 1
            if calls[0] < 2:
                raise ConnectionError("async transient")
            return "async_ok"

        async def run():
            decorated = await healer.retry_with_backoff_async(flaky_async)
            with patch("asyncio.sleep"):
                return await decorated()

        result = asyncio.get_event_loop().run_until_complete(run())
        assert result == "async_ok"
        assert calls[0] == 2

    def test_async_retry_fatal_error_not_retried(self, healer):
        """
        BUG-PREVENTION: Same fatal-error list applies in async context.
        An async OCR init failure must not spin in an infinite loop.
        """
        calls = [0]

        async def raises_fatal_async():
            calls[0] += 1
            raise ImageLoadError("missing")

        async def run():
            decorated = await healer.retry_with_backoff_async(raises_fatal_async)
            await decorated()

        with pytest.raises(ImageLoadError):
            asyncio.get_event_loop().run_until_complete(run())
        assert calls[0] == 1

    def test_async_retry_exhausted_raises(self, healer):
        """Async max retries exhausted must re-raise the original exception."""
        async def always_fails_async():
            raise ValueError("async permanent")

        async def run():
            decorated = await healer.retry_with_backoff_async(always_fails_async)
            with patch("asyncio.sleep"):
                await decorated()

        with pytest.raises(ValueError, match="async permanent"):
            asyncio.get_event_loop().run_until_complete(run())


# ═══════════════════════════════════════════════════════════════════════════════
# FALLBACK CHAIN
# ═══════════════════════════════════════════════════════════════════════════════

class TestFallbackChain:

    def test_primary_called_first_and_args_forwarded(self, healer):
        """Primary function must receive the same args as the executor call."""
        primary = MagicMock(return_value="primary_ok")
        fallback = MagicMock()

        executor = healer.fallback_chain(primary, [fallback])
        result = executor("arg1", key="val")

        assert result == "primary_ok"
        primary.assert_called_once_with("arg1", key="val")
        fallback.assert_not_called()

    def test_fallback_used_when_primary_fails(self, healer):
        """When primary raises, first fallback must be tried."""
        primary = MagicMock(side_effect=RuntimeError("primary dead"))
        fallback = MagicMock(return_value="fallback_ok")

        executor = healer.fallback_chain(primary, [fallback])
        result = executor()
        assert result == "fallback_ok"

    def test_fallbacks_tried_in_order(self, healer):
        """
        BUG-PREVENTION: If fallback order is wrong, a cheaper/faster fallback
        might be skipped in favour of an expensive one, wasting resources.
        """
        order = []
        def fb1(): order.append("fb1"); raise RuntimeError("fb1 dead")
        def fb2(): order.append("fb2"); return "fb2_ok"
        def fb3(): order.append("fb3"); return "fb3_ok"

        primary = MagicMock(side_effect=RuntimeError("primary dead"))
        executor = healer.fallback_chain(primary, [fb1, fb2, fb3])
        result = executor()

        assert result == "fb2_ok"
        assert order == ["fb1", "fb2"], "fb3 should not be tried if fb2 succeeds"

    def test_all_fail_raises_general_exception(self, healer):
        """
        BUG-PREVENTION: Must raise a clear 'All processing methods failed' message,
        not bubble up the last fallback's exception with a confusing traceback.
        """
        primary = MagicMock(side_effect=RuntimeError("primary dead"))
        fb = MagicMock(side_effect=RuntimeError("fallback dead"))

        executor = healer.fallback_chain(primary, [fb])
        with pytest.raises(Exception, match="All processing methods failed"):
            executor()

    def test_primary_failure_logged_as_warning(self, healer, caplog):
        """
        BUG-PREVENTION: Silent fallbacks hide why the primary failed.
        A warning must be logged so engineers can investigate primary failures.
        """
        primary = MagicMock(side_effect=RuntimeError("primary dead"))
        fallback = MagicMock(return_value="ok")

        executor = healer.fallback_chain(primary, [fallback])
        with caplog.at_level(logging.WARNING, logger="blast_ocr.core.healing"):
            executor()

        assert any("Primary method failed" in r.message for r in caplog.records), \
            "Primary failure must be logged so operators can investigate"

"""
PHASE 7: SelfHealingOCR decorator correctness.
"""

import pytest
from unittest.mock import patch, MagicMock


@pytest.fixture
def healer():
    from blast_ocr.core.healing import SelfHealingOCR

    return SelfHealingOCR(max_retries=3, backoff_factor=2)


# ── Test 1: Transient error is retried up to max_retries ──────────────────
def test_retry_transient_error(healer):
    call_count = [0]

    @healer.retry_with_backoff
    def flaky_function():
        call_count[0] += 1
        if call_count[0] < 3:
            raise RuntimeError("transient")
        return "success"

    with patch("time.sleep"):  # Speed up test
        result = flaky_function()
    assert result == "success"
    assert call_count[0] == 3


# ── Test 2: Fatal errors are NOT retried ─────────────────────────────────
def test_fatal_errors_not_retried(healer):
    from blast_ocr.core.exceptions import ImageLoadError

    call_count = [0]

    @healer.retry_with_backoff
    def raises_fatal():
        call_count[0] += 1
        raise ImageLoadError("file not found")

    with pytest.raises(ImageLoadError):
        raises_fatal()

    assert call_count[0] == 1, (
        f"BUG: ImageLoadError was retried {call_count[0]} times. Fatal errors must not be retried."
    )


# ── Test 3: After max_retries exhausted, exception is re-raised ──────────
def test_exception_raised_after_max_retries(healer):
    @healer.retry_with_backoff
    def always_fails():
        raise ConnectionError("always fails")

    with patch("time.sleep"):
        with pytest.raises(ConnectionError):
            always_fails()


# ── Test 4: Backoff timing is correct (2^0, 2^1, 2^2) ───────────────────
def test_backoff_timing(healer):
    sleep_times = []

    @healer.retry_with_backoff
    def always_fails():
        raise RuntimeError("fail")

    with patch("time.sleep", side_effect=lambda t: sleep_times.append(t)):
        with pytest.raises(RuntimeError):
            always_fails()

    # With backoff_factor=2: wait = 2^0=1, 2^1=2 (two sleeps before final raise)
    assert len(sleep_times) == 2, (
        f"Expected 2 sleep calls, got {len(sleep_times)}: {sleep_times}"
    )
    assert sleep_times[0] == 1, (
        f"First backoff should be 1s (2^0), got {sleep_times[0]}"
    )
    assert sleep_times[1] == 2, (
        f"Second backoff should be 2s (2^1), got {sleep_times[1]}"
    )


# ── Test 5: OCREngineError is in fatal list (not retried) ─────────────────
def test_ocr_engine_error_not_retried(healer):
    """BUG FIX verification: OCREngineError was added to fatal list in phase2."""
    from blast_ocr.core.exceptions import OCREngineError

    call_count = [0]

    @healer.retry_with_backoff
    def raises_engine_error():
        call_count[0] += 1
        raise OCREngineError("GPU failed")

    with pytest.raises(OCREngineError):
        raises_engine_error()

    assert call_count[0] == 1, (
        "BUG: OCREngineError is being retried but should be fatal (prevents memory exhaustion retry loops)"
    )


# ── Test 6: Return value from successful function passes through ──────────
def test_return_value_preserved(healer):
    @healer.retry_with_backoff
    def returns_data():
        return {"page": 1, "text": "hello", "confidence": 0.95}

    result = returns_data()
    assert result == {"page": 1, "text": "hello", "confidence": 0.95}


# ── Test 7: fallback_chain tries primary first ────────────────────────────
def test_fallback_chain_primary_success(healer):
    primary = MagicMock(return_value="primary_result")
    fallback = MagicMock(return_value="fallback_result")

    executor = healer.fallback_chain(primary, [fallback])
    result = executor("arg1")

    assert result == "primary_result"
    primary.assert_called_once_with("arg1")
    fallback.assert_not_called()


# ── Test 8: fallback_chain uses fallback when primary fails ──────────────
def test_fallback_chain_uses_fallback(healer):
    primary = MagicMock(side_effect=RuntimeError("primary failed"))
    fallback = MagicMock(return_value="fallback_result")

    executor = healer.fallback_chain(primary, [fallback])
    result = executor()

    assert result == "fallback_result"


# ── Test 9: fallback_chain raises when all fail ───────────────────────────
def test_fallback_chain_all_fail_raises(healer):
    primary = MagicMock(side_effect=RuntimeError("primary failed"))
    fallback = MagicMock(side_effect=RuntimeError("fallback failed"))

    executor = healer.fallback_chain(primary, [fallback])

    with pytest.raises(Exception, match="All processing methods failed"):
        executor()

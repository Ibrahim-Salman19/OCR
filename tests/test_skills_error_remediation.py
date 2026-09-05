"""
tests/test_skills_error_remediation.py

Verification suite directly implementing:
- skills/error_analysis.md: 4 categories of document failure modes and remediations
- skills/error_recovery.md: Self-healing retry backoff and fatal vs transient classification
"""

import numpy as np
import cv2
import pytest
from unittest.mock import patch

from blast_ocr.core.healing import SelfHealingOCR
from blast_ocr.core.exceptions import (
    OCREngineError,
)
from blast_ocr.core.restoration import ForensicRestorer


# ============================================================================
# 1. Error Analysis: Low-Fidelity Capture (Noise, Blur, Low Contrast)
# ============================================================================

def test_restoration_low_fidelity_denoising():
    clean = np.full((100, 100), 200, dtype=np.uint8)
    noise = np.random.randint(-20, 20, (100, 100), dtype=np.int16)
    noisy = np.clip(clean.astype(np.int16) + noise, 0, 255).astype(np.uint8)

    sigma = ForensicRestorer.estimate_noise_sigma(noisy)
    assert sigma > 0.0

    denoised = ForensicRestorer.apply_denoising(noisy)
    assert denoised is not None
    assert denoised.shape == noisy.shape


def test_restoration_poor_contrast_clahe():
    low_contrast = np.full((100, 100), 185, dtype=np.uint8)
    low_contrast[40:60, 40:60] = 175  # Faint box

    enhanced = ForensicRestorer.apply_clahe(low_contrast)
    assert enhanced is not None
    assert enhanced.shape == low_contrast.shape
    assert enhanced.dtype == np.uint8


def test_restoration_full_pipeline_standard_and_reflexion(tmp_path):
    img_path = str(tmp_path / "restore_test.png")
    img = np.full((120, 250), 240, dtype=np.uint8)
    cv2.putText(img, "Faded Ink Text", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, 100, 2)
    cv2.imwrite(img_path, img)

    # Standard mode
    restored_std = ForensicRestorer.restore(img_path, mode="standard")
    assert restored_std is not None
    assert restored_std.shape == (120, 250)

    # Reflexion mode
    restored_refl = ForensicRestorer.restore(img_path, mode="reflexion")
    assert restored_refl is not None
    assert restored_refl.shape == (120, 250)


# ============================================================================
# 2. Error Recovery: Fatal vs. Transient Error Classification
# ============================================================================

def test_healer_fatal_errors_never_retried():
    """Verify fatal exceptions bypass retry decorator and raise immediately."""
    healer = SelfHealingOCR(max_retries=3, backoff_factor=1.5)
    call_count = 0

    @healer.retry_with_backoff
    def fail_file_not_found():
        nonlocal call_count
        call_count += 1
        raise FileNotFoundError("Missing target asset")

    with pytest.raises(FileNotFoundError):
        fail_file_not_found()
    assert call_count == 1


def test_healer_ocr_engine_error_fatal_immediate_raise():
    healer = SelfHealingOCR(max_retries=3, backoff_factor=1.5)
    call_count = 0

    @healer.retry_with_backoff
    def fail_engine():
        nonlocal call_count
        call_count += 1
        raise OCREngineError("Engine binary corrupted")

    with pytest.raises(OCREngineError):
        fail_engine()
    assert call_count == 1


def test_healer_transient_error_retries_and_succeeds():
    """Verify transient exceptions retry up to max_retries with backoff."""
    healer = SelfHealingOCR(max_retries=3, backoff_factor=1.1)
    attempts = 0

    @healer.retry_with_backoff
    def transient_network_or_io():
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise ConnectionResetError("Temporary socket timeout")
        return "recovered_data"

    with patch("time.sleep"):  # Speed up tests
        result = transient_network_or_io()

    assert result == "recovered_data"
    assert attempts == 3

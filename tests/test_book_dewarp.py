"""
tests/test_book_dewarp.py

Unit tests for BookDewarper module.
"""

import numpy as np
import cv2

from blast_ocr.core.book_dewarp import BookDewarper


def test_dewarp_flat_page_skips_processing():
    flat_img = np.full((300, 400, 3), 255, dtype=np.uint8)
    cv2.putText(flat_img, "Straight line of flat book text", (50, 100), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2)

    result_img, curvature = BookDewarper.dewarp_page(flat_img, curvature_threshold=4.0)
    assert result_img.shape == flat_img.shape
    assert curvature <= 4.0


def test_dewarp_curved_page_detects_and_remaps():
    curved_img = np.full((300, 500, 3), 255, dtype=np.uint8)
    for row in range(4):
        y_base = 60 + row * 50
        for x in range(30, 470):
            # 15px sinusoidal curvature
            y = int(y_base + 15.0 * np.sin(np.pi * (x - 30) / 440))
            cv2.circle(curved_img, (x, y), 2, (0, 0, 0), -1)

    result_img, curvature = BookDewarper.dewarp_page(curved_img, curvature_threshold=2.0)
    assert curvature > 2.0
    assert result_img.shape == curved_img.shape


def test_dewarp_small_or_invalid_image():
    small_img = np.zeros((10, 10), dtype=np.uint8)
    res, c = BookDewarper.dewarp_page(small_img)
    assert res.shape == (10, 10)
    assert c == 0.0

    res_none, c_none = BookDewarper.dewarp_page(None)
    assert res_none is None
    assert c_none == 0.0

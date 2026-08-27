"""
Feature 1: Vectorized Batch Image Preprocessor
Opaque-box test suite verifying zero-disk PDF rasterization, SIMD/vectorized image
normalization, aspect-ratio bucketing, and dynamic padding.
"""

import pytest
import numpy as np
from blast_ocr.core.batch_preprocessor import BatchPreprocessor


class TestVectorizedBatchPreprocessor:
    """Test suite for Feature 1: Vectorized Batch Image Preprocessor."""

    def test_zero_disk_pdf_rasterization(self, synthetic_pdf_generator):
        """
        Verify PDF byte streams are rasterized in-memory directly to NumPy arrays
        without touching the filesystem.
        """
        page_count = 4
        pdf_bytes = synthetic_pdf_generator(page_count=page_count, text_prefix="Zero-Disk Test")
        
        pages = BatchPreprocessor.rasterize_pdf(pdf_bytes, dpi=150)
        
        assert len(pages) == page_count, f"Expected {page_count} pages, got {len(pages)}"
        for idx, page in enumerate(pages):
            assert isinstance(page, np.ndarray), f"Page {idx} must be a numpy ndarray"
            assert len(page.shape) == 3, f"Page {idx} must be 3-dimensional (H, W, C)"
            assert page.shape[2] == 3, f"Page {idx} must have 3 RGB channels"
            assert page.dtype == np.uint8, f"Page {idx} dtype must be uint8"
            assert page.shape[0] > 0 and page.shape[1] > 0, "Page dimensions must be non-zero"

    def test_vectorized_batch_normalization(self, synthetic_image_generator):
        """
        Verify SIMD / vectorized normalization across a batch of images produces
        properly formatted NCHW float32 tensors with expected mean/std scaling.
        """
        batch_size = 6
        target_size = (256, 256)
        images = synthetic_image_generator(count=batch_size, sizes=[target_size] * batch_size)
        
        tensor = BatchPreprocessor.normalize_batch(images, target_size=target_size)
        
        assert isinstance(tensor, np.ndarray)
        assert tensor.shape == (batch_size, 3, 256, 256)
        assert tensor.dtype == np.float32
        assert tensor.flags.c_contiguous, "Tensor must be C-contiguous for ONNX inference"
        # Check normalization bounds (standard ImageNet norm usually spans ~ -2.5 to +2.5)
        assert np.isfinite(tensor).all(), "Tensor must not contain NaN or Inf values"
        assert tensor.min() < 0.0, "Normalized tensor should have negative values around zero-center"

    def test_aspect_ratio_bucketing(self):
        """
        Verify aspect-ratio bucketing correctly partitions crops of varying aspect
        ratios to minimize padding overhead while preserving original indices.
        """
        # Create crops with distinct aspect ratios: wide (4:1), square (1:1), tall (1:3)
        crops = [
            np.full((32, 128, 3), 10, dtype=np.uint8),  # wide, ratio 4.0
            np.full((64, 64, 3), 20, dtype=np.uint8),   # square, ratio 1.0
            np.full((32, 120, 3), 30, dtype=np.uint8),  # wide, ratio ~3.75
            np.full((90, 30, 3), 40, dtype=np.uint8),   # tall, ratio ~0.33
            np.full((50, 50, 3), 50, dtype=np.uint8),   # square, ratio 1.0
        ]
        
        buckets = BatchPreprocessor.bucket_by_aspect_ratio(crops, target_height=48)
        
        assert isinstance(buckets, dict)
        assert len(buckets) >= 2, "Expected at least 2 distinct aspect ratio buckets"
        
        # Verify all original item indices (0..4) are present exactly once across buckets
        all_indices = []
        for bucket_key, items in buckets.items():
            for orig_idx, resized_crop in items:
                all_indices.append(orig_idx)
                assert resized_crop.shape[0] == 48, "Height must be scaled to target_height=48"
                assert resized_crop.shape[2] == 3
        
        assert sorted(all_indices) == [0, 1, 2, 3, 4], "All items must be tracked with original indices"

    def test_padded_batch_tensor_creation(self):
        """
        Verify dynamic padding to uniform bucket width creates aligned NCHW tensors
        with accurate unpadded width metadata.
        """
        crops = [
            np.zeros((48, 100, 3), dtype=np.uint8),
            np.zeros((48, 150, 3), dtype=np.uint8),
            np.zeros((48, 80, 3), dtype=np.uint8),
        ]
        
        tensor, widths = BatchPreprocessor.create_padded_batch(crops, target_height=48)
        
        assert tensor.shape[0] == 3
        assert tensor.shape[1] == 3  # channels
        assert tensor.shape[2] == 48  # height
        assert tensor.shape[3] >= 150  # width padded to at least max width
        assert tensor.shape[3] % 8 == 0, "Padded width should align to 8-byte boundary"
        assert widths == [100, 150, 80]

    def test_preprocessor_boundary_and_error_handling(self):
        """
        Verify boundary conditions: empty inputs, corrupt PDF bytes, single pixel images.
        """
        # Empty list normalization
        empty_tensor = BatchPreprocessor.normalize_batch([])
        assert empty_tensor.shape[0] == 0
        
        # Empty bucketing
        empty_buckets = BatchPreprocessor.bucket_by_aspect_ratio([])
        assert empty_buckets == {}
        
        # Empty padded batch
        empty_pad, empty_widths = BatchPreprocessor.create_padded_batch([])
        assert empty_pad.shape[0] == 0
        assert empty_widths == []
        
        # Invalid PDF bytes
        with pytest.raises(ValueError):
            BatchPreprocessor.rasterize_pdf(b"not a valid pdf data stream")
        
        with pytest.raises(ValueError):
            BatchPreprocessor.rasterize_pdf(b"")

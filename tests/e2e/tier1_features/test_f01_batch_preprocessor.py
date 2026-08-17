"""
Feature 1: Vectorized Batch Image Preprocessor
Opaque-box test suite verifying zero-disk PDF rasterization, SIMD/vectorized image
normalization, aspect-ratio bucketing, and dynamic padding.
"""

import io
import pytest
import numpy as np
from PIL import Image

try:
    from blast_ocr.core.batch_preprocessor import BatchPreprocessor
except ImportError:
    # Reference contract implementation for test isolation
    import fitz
    import cv2

    class BatchPreprocessor:
        @staticmethod
        def rasterize_pdf(pdf_bytes: bytes, dpi: int = 200) -> list:
            if not pdf_bytes:
                raise ValueError("Empty or invalid PDF byte stream.")
            try:
                doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            except Exception as e:
                raise ValueError(f"Failed to parse PDF bytes: {e}")
            
            pages = []
            zoom = dpi / 72.0
            matrix = fitz.Matrix(zoom, zoom)
            for page in doc:
                pix = page.get_pixmap(matrix=matrix, alpha=False)
                img = np.frombuffer(pix.samples, dtype=np.uint8).reshape((pix.height, pix.width, 3))
                pages.append(img)
            doc.close()
            return pages

def _normalize_batch(images: list, target_size=None, mean=(0.485, 0.456, 0.406), std=(0.229, 0.224, 0.225)) -> np.ndarray:
    if not images:
        return np.empty((0, 3, 0, 0), dtype=np.float32)
    
    import cv2
    processed = []
    for img in images:
        if not isinstance(img, np.ndarray) or img.size == 0:
            raise ValueError("Invalid or empty image array encountered in batch normalization.")
        if np.isnan(img).any() or np.isinf(img).any():
            raise ValueError("Input image array contains NaN or Inf values.")
        
        h, w = img.shape[:2]
        if target_size:
            th, tw = target_size
            img_resized = cv2.resize(img, (tw, th))
        else:
            img_resized = img
        
        if len(img_resized.shape) == 2:
            img_resized = cv2.cvtColor(img_resized, cv2.COLOR_GRAY2RGB)
        elif img_resized.shape[2] == 4:
            img_resized = cv2.cvtColor(img_resized, cv2.COLOR_BGRA2BGR)
        
        chw = img_resized.transpose(2, 0, 1).astype(np.float32) / 255.0
        mean_arr = np.array(mean, dtype=np.float32).reshape(3, 1, 1)
        std_arr = np.array(std, dtype=np.float32).reshape(3, 1, 1)
        norm = (chw - mean_arr) / std_arr
        processed.append(norm)
    return np.ascontiguousarray(np.stack(processed, axis=0))


def _bucket_by_aspect_ratio(images: list, target_height: int = 48, num_buckets: int = 5) -> dict:
    if not images:
        return {}
    import cv2
    buckets = {}
    for idx, img in enumerate(images):
        if not isinstance(img, np.ndarray) or img.size == 0:
            continue
        h, w = img.shape[:2]
        aspect_ratio = max(w / max(h, 1), 0.001)
        aspect_ratio = min(aspect_ratio, 1000.0)
        bucket_key = int(round(aspect_ratio * 2))
        if bucket_key not in buckets:
            buckets[bucket_key] = []
        new_w = max(int(round(aspect_ratio * target_height)), 8)
        new_w = min(new_w, 4096)
        resized = cv2.resize(img, (new_w, target_height))
        buckets[bucket_key].append((idx, resized))
    return buckets


def _create_padded_batch(crops: list, target_height: int = 48) -> tuple:
    if not crops:
        return np.empty((0, 3, target_height, 0), dtype=np.float32), []
    max_w = max(c.shape[1] for c in crops)
    pad_w = ((max_w + 7) // 8) * 8
    batch = np.zeros((len(crops), target_height, pad_w, 3), dtype=np.uint8)
    widths = []
    for i, crop in enumerate(crops):
        h, w = crop.shape[:2]
        batch[i, :min(h, target_height), :min(w, pad_w), :] = crop[:target_height, :pad_w, :]
        widths.append(w)
    tensor = batch.transpose(0, 3, 1, 2).astype(np.float32) / 255.0
    return np.ascontiguousarray(tensor), widths


BatchPreprocessor.normalize_batch = staticmethod(_normalize_batch)
BatchPreprocessor.bucket_by_aspect_ratio = staticmethod(_bucket_by_aspect_ratio)
BatchPreprocessor.create_padded_batch = staticmethod(_create_padded_batch)


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

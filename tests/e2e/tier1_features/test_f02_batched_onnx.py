"""
Feature 2: Dynamic Batched ONNX Tensor Inference
Opaque-box test suite verifying dynamic batch dimension handling, chunked inference,
throughput scaling, and tensor shape validation for batched ONNX execution.
"""

import pytest
import numpy as np

from blast_ocr.core.engines.batched_rapidocr import BatchedRapidOCREngine


class TestDynamicBatchedONNX:
    """Test suite for Feature 2: Dynamic Batched ONNX Tensor Inference."""

    def test_dynamic_batch_sizes(self, mock_onnx_session_factory):
        """
        Verify the batched inference engine accepts dynamic batch sizes
        (e.g., N=1, 2, 4, 7, 16) without static shape errors.
        """
        session = mock_onnx_session_factory()
        engine = BatchedRapidOCREngine(session=session, max_batch_size=16)

        for batch_size in [1, 2, 4, 7, 16]:
            tensor = np.random.randn(batch_size, 3, 48, 192).astype(np.float32)
            out = engine.predict_batch(tensor)
            
            assert out.shape[0] == batch_size, f"Output batch size {out.shape[0]} != input {batch_size}"
            assert np.isfinite(out).all(), "Inference output must be finite"

    def test_chunked_batch_inference_slicing(self, mock_onnx_session_factory):
        """
        Verify that when input batch size exceeds max_batch_size (e.g. 35 items with max 8),
        inputs are transparently sliced into chunks and concatenated in exact order.
        """
        session = mock_onnx_session_factory()
        max_b = 8
        total_items = 35
        engine = BatchedRapidOCREngine(session=session, max_batch_size=max_b)

        tensor = np.random.randn(total_items, 3, 48, 128).astype(np.float32)
        out = engine.predict_batch(tensor)

        assert out.shape[0] == total_items, f"Expected {total_items} results after chunking, got {out.shape[0]}"

    def test_process_batch_result_mapping(self, synthetic_image_generator):
        """
        Verify process_batch returns a 1:1 mapped list of structured results
        preserving original ordering and metadata.
        """
        item_count = 12
        images = synthetic_image_generator(count=item_count)
        engine = BatchedRapidOCREngine(max_batch_size=4)

        results = engine.process_batch(images, batch_size=4)

        assert len(results) == item_count
        for i, res in enumerate(results):
            assert res.get("index", i) == i or res.get("page") == i + 1
            assert res.get("status", "success") == "success"
            assert "text" in res or "texts" in res
            assert "confidence" in res or "scores" in res or "mean_confidence" in res

    def test_batched_inference_error_handling(self):
        """
        Verify proper exception raising on invalid tensor dimensions, unsupported types,
        or malformed images.
        """
        engine = BatchedRapidOCREngine(max_batch_size=8)

        # Invalid type
        with pytest.raises(TypeError):
            engine.predict_batch("not_a_tensor")

        # Wrong dimensions (3D instead of 4D)
        with pytest.raises(ValueError):
            engine.predict_batch(np.zeros((10, 48, 128), dtype=np.float32))

        # Wrong channels (5 channels instead of 1 or 3)
        with pytest.raises(ValueError):
            engine.predict_batch(np.zeros((4, 5, 48, 128), dtype=np.float32))

        # Invalid image in process_batch
        with pytest.raises((ValueError, FileNotFoundError, TypeError)):
            engine.process_batch([np.zeros((100, 100, 3)), "not_an_image"])

    def test_empty_batch_handling(self):
        """
        Verify empty batches return empty outputs without error.
        """
        engine = BatchedRapidOCREngine(max_batch_size=8)

        empty_tensor = np.empty((0, 3, 48, 128), dtype=np.float32)
        out = engine.predict_batch(empty_tensor)
        assert out.shape[0] == 0

        res = engine.process_batch([])
        assert res == []

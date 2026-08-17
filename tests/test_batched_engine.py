"""
tests.test_batched_engine

Comprehensive unit and integration test suite for Milestone 1:
High-Throughput Batch Pipeline, Vectorized Batch Preprocessor,
ONNX Multi-Provider Session Manager, Vectorized CTC Tensor Decoder,
Parallel DBNet Post-Processing, and Batched RapidOCR Engine.
"""

import os
from pathlib import Path
import tempfile
import time
from typing import List

import cv2
import numpy as np
from PIL import Image
import pytest

from blast_ocr.config import OCRConfig, get_settings
from blast_ocr.core.batch_preprocessor import BatchPreprocessor
from blast_ocr.core.engines import BatchedRapidOCREngine, BaseOCREngine, get_engine
from blast_ocr.core.onnx_session import ONNXSessionManager
from blast_ocr.core.tensor_decoder import (
    ParallelDBPostProcessor,
    VectorizedCTCDecoder,
    VectorizedTensorDecoder,
    extract_rotate_crop_image,
)


@pytest.fixture
def sample_text_image() -> np.ndarray:
    """Create a synthetic document image with black text on white background."""
    img = np.full((120, 400, 3), 255, dtype=np.uint8)
    cv2.putText(
        img,
        "BLAST OCR PIPELINE",
        (20, 70),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.1,
        (0, 0, 0),
        2,
        cv2.LINE_AA,
    )
    return img


@pytest.fixture
def sample_multi_page_images() -> List[np.ndarray]:
    """Create multiple distinct synthetic document page images."""
    pages = []
    texts = ["CHAPTER 1 INTRODUCTION", "DATA PROCESSING PIPELINE", "CONCLUSION AND SUMMARY"]
    for text in texts:
        page = np.full((200, 500, 3), 255, dtype=np.uint8)
        cv2.putText(
            page,
            text,
            (30, 110),
            cv2.FONT_HERSHEY_SIMPLEX,
            1.0,
            (0, 0, 0),
            2,
            cv2.LINE_AA,
        )
        pages.append(page)
    return pages


# =============================================================================
# 1. BatchPreprocessor Tests
# =============================================================================


class TestBatchPreprocessor:
    """Tests for in-memory rasterization, SIMD normalization, and tensor packing."""

    def test_load_image_from_numpy(self, sample_text_image: np.ndarray):
        preprocessor = BatchPreprocessor()
        loaded = preprocessor.load_image(sample_text_image)
        assert isinstance(loaded, np.ndarray)
        assert loaded.shape == sample_text_image.shape
        assert loaded.dtype == np.uint8

    def test_load_image_from_grayscale_and_rgba(self):
        preprocessor = BatchPreprocessor()
        gray = np.full((100, 100), 200, dtype=np.uint8)
        loaded_gray = preprocessor.load_image(gray)
        assert loaded_gray.ndim == 3
        assert loaded_gray.shape == (100, 100, 3)

        rgba = np.full((100, 100, 4), 255, dtype=np.uint8)
        loaded_rgba = preprocessor.load_image(rgba)
        assert loaded_rgba.ndim == 3
        assert loaded_rgba.shape == (100, 100, 3)

    def test_load_image_from_pil(self, sample_text_image: np.ndarray):
        preprocessor = BatchPreprocessor()
        pil_img = Image.fromarray(cv2.cvtColor(sample_text_image, cv2.COLOR_BGR2RGB))
        loaded = preprocessor.load_image(pil_img)
        assert isinstance(loaded, np.ndarray)
        assert loaded.shape == sample_text_image.shape

    def test_load_image_from_bytes(self, sample_text_image: np.ndarray):
        preprocessor = BatchPreprocessor()
        _, buf = cv2.imencode(".png", sample_text_image)
        loaded = preprocessor.load_image(buf.tobytes())
        assert isinstance(loaded, np.ndarray)
        assert loaded.shape == sample_text_image.shape

    def test_load_image_from_file_path(self, sample_text_image: np.ndarray):
        preprocessor = BatchPreprocessor()
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp_path = tmp.name
        try:
            cv2.imwrite(tmp_path, sample_text_image)
            loaded = preprocessor.load_image(tmp_path)
            assert loaded.shape == sample_text_image.shape
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def test_normalize_tensor_chw(self, sample_text_image: np.ndarray):
        preprocessor = BatchPreprocessor()
        norm = preprocessor.normalize_tensor_chw(sample_text_image)
        h, w, c = sample_text_image.shape
        assert norm.shape == (3, h, w)
        assert norm.dtype == np.float32
        # White pixel (255): (255/255 - 0.5) / 0.5 = 1.0
        assert np.isclose(norm[:, 0, 0], 1.0, atol=1e-3).all()

    def test_compute_det_resize_dimensions(self):
        preprocessor = BatchPreprocessor()
        # Test max limit constraint
        res_h, res_w, r_h, r_w = preprocessor.compute_det_resize_dimensions(
            height=1000, width=2000, limit_side_len=960, limit_type="max"
        )
        assert res_h % 32 == 0
        assert res_w % 32 == 0
        assert res_w <= 960
        assert res_h <= 960
        assert r_h > 0 and r_w > 0

    def test_preprocess_detection_batch(self, sample_multi_page_images: List[np.ndarray]):
        preprocessor = BatchPreprocessor()
        batch_tensor, meta_list, loaded = preprocessor.preprocess_detection_batch(
            sample_multi_page_images, limit_side_len=960, limit_type="max"
        )
        assert batch_tensor.ndim == 4
        assert batch_tensor.shape[0] == len(sample_multi_page_images)
        assert batch_tensor.shape[1] == 3
        assert batch_tensor.shape[2] % 32 == 0
        assert batch_tensor.shape[3] % 32 == 0
        assert len(meta_list) == len(sample_multi_page_images)
        assert len(loaded) == len(sample_multi_page_images)
        for meta in meta_list:
            assert "src_shape" in meta
            assert "resized_shape" in meta
            assert "ratio_h" in meta
            assert "ratio_w" in meta

    def test_bucket_and_batch_crops(self):
        preprocessor = BatchPreprocessor()
        # Create crops with varied aspect ratios
        crop1 = np.full((32, 64, 3), 255, dtype=np.uint8)  # aspect 2
        crop2 = np.full((32, 160, 3), 255, dtype=np.uint8)  # aspect 5
        crop3 = np.full((32, 320, 3), 255, dtype=np.uint8)  # aspect 10
        crops = [crop1, crop2, crop3]

        batches = preprocessor.bucket_and_batch_crops(crops, rec_batch_size=2)
        assert len(batches) == 2

        # First batch has 2 items
        tensor1, indices1, max_wh1 = batches[0]
        assert tensor1.shape[0] == 2
        assert tensor1.shape[1] == 3
        assert tensor1.shape[2] == 48
        assert len(indices1) == 2

        # Second batch has 1 item
        tensor2, indices2, max_wh2 = batches[1]
        assert tensor2.shape[0] == 1
        assert tensor2.shape[1] == 3
        assert tensor2.shape[2] == 48
        assert len(indices2) == 1

        # Check that all original indices are preserved
        all_indices = sorted(indices1 + indices2)
        assert all_indices == [0, 1, 2]


# =============================================================================
# 2. ONNXSessionManager Tests
# =============================================================================


class TestONNXSessionManager:
    """Tests for multi-provider fallback hierarchy and session management."""

    def test_provider_hierarchy_cpu_mode(self):
        mgr = ONNXSessionManager(preferred_provider="cpu")
        providers = mgr.get_provider_hierarchy()
        assert len(providers) == 1
        assert providers[0][0] == "CPUExecutionProvider"

    def test_provider_hierarchy_cuda_fallback(self):
        mgr = ONNXSessionManager(preferred_provider="cuda")
        providers = mgr.get_provider_hierarchy()
        provider_names = [p[0] for p in providers]
        # Always includes CPUExecutionProvider as safety fallback
        assert "CPUExecutionProvider" in provider_names

    def test_provider_hierarchy_auto(self):
        mgr = ONNXSessionManager(preferred_provider="auto")
        providers = mgr.get_provider_hierarchy()
        assert len(providers) >= 1
        assert any(p[0] == "CPUExecutionProvider" for p in providers)

    def test_build_session_options(self):
        mgr = ONNXSessionManager(intra_op_num_threads=2, inter_op_num_threads=1)
        opts = mgr.build_session_options()
        assert opts.intra_op_num_threads == 2
        assert opts.inter_op_num_threads == 1

    def test_resolve_model_path_det_and_rec(self):
        det_path = ONNXSessionManager.resolve_model_path("det")
        rec_path = ONNXSessionManager.resolve_model_path("rec")
        assert os.path.exists(det_path)
        assert os.path.exists(rec_path)
        assert det_path.endswith(".onnx")
        assert rec_path.endswith(".onnx")

    def test_session_caching(self):
        mgr = ONNXSessionManager(preferred_provider="cpu")
        det_path = ONNXSessionManager.resolve_model_path("det")
        sess1 = mgr.get_or_create_session(det_path)
        sess2 = mgr.get_or_create_session(det_path)
        assert sess1 is sess2


# =============================================================================
# 3. VectorizedTensorDecoder Tests
# =============================================================================


class TestVectorizedTensorDecoder:
    """Tests for CTC greedy decoding, DBNet polygon extraction, and crop transformation."""

    def test_ctc_greedy_decoder_synthetic_logits(self):
        vocab = ["blank", "A", "B", "C", "D", " "]
        decoder = VectorizedCTCDecoder(character_list=vocab)

        # Batch of 1, seq len 6, vocab 6
        # Sequence: [blank(0), A(1), A(1), B(2), blank(0), C(3)] -> Decoded: "ABC"
        logits = np.zeros((1, 6, 6), dtype=np.float32)
        logits[0, 0, 0] = 10.0  # blank
        logits[0, 1, 1] = 10.0  # A
        logits[0, 2, 1] = 10.0  # A (duplicate)
        logits[0, 3, 2] = 10.0  # B
        logits[0, 4, 0] = 10.0  # blank
        logits[0, 5, 3] = 10.0  # C

        results = decoder.decode_batch(logits)
        assert len(results) == 1
        text, conf = results[0]
        assert text == "ABC"
        assert conf > 0.9

    def test_ctc_decoder_empty_input(self):
        decoder = VectorizedCTCDecoder(character_list=["blank", "A", " "])
        results = decoder.decode_batch(np.zeros((0, 5, 3), dtype=np.float32))
        assert results == []

    def test_extract_rotate_crop_image(self):
        # Create an image with an identifiable pattern
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        img[20:40, 20:80] = 255
        box = np.array([[20, 20], [80, 20], [80, 40], [20, 40]], dtype=np.int32)
        crop = extract_rotate_crop_image(img, box)
        assert isinstance(crop, np.ndarray)
        assert crop.ndim == 3
        assert crop.shape[0] > 0 and crop.shape[1] > 0

    def test_db_postprocessor_box_extraction(self):
        processor = ParallelDBPostProcessor(thresh=0.3, box_thresh=0.4)
        # Create a synthetic probability map with a high-confidence rectangular region
        pred_map = np.zeros((128, 128), dtype=np.float32)
        pred_map[32:64, 32:96] = 0.95

        meta = {
            "src_shape": (256, 256),
            "resized_shape": (128, 128),
            "ratio_h": 0.5,
            "ratio_w": 0.5,
        }

        boxes = processor.process_single_page(pred_map, meta)
        assert len(boxes) >= 1
        box = boxes[0]
        assert box.shape == (4, 2)
        # Scaled coordinates should span approximately [64, 64] to [192, 128]
        assert np.any(box[:, 0] > 50)


# =============================================================================
# 4. BatchedRapidOCREngine & BaseOCREngine Tests
# =============================================================================


class TestBatchedRapidOCREngine:
    """Integration and verification tests for BatchedRapidOCREngine."""

    def test_engine_registry_lookup(self):
        engine = get_engine("batched_rapidocr")
        assert isinstance(engine, BatchedRapidOCREngine)
        assert engine.engine_name == "batched_rapidocr"

    def test_engine_metadata(self):
        engine = BatchedRapidOCREngine(preferred_provider="cpu")
        meta = engine.metadata()
        assert meta["engine"] == "batched_rapidocr"
        assert meta["backend"] == "onnxruntime"
        assert "providers" in meta
        assert "det_batch_size" in meta
        assert "rec_batch_size" in meta

    def test_single_page_processing(self, sample_text_image: np.ndarray):
        engine = BatchedRapidOCREngine(preferred_provider="cpu")
        res = engine.process_page(sample_text_image, page_number=1)

        # Validate uniform dictionary contract
        assert "page" in res and res["page"] == 1
        assert "text" in res and isinstance(res["text"], str)
        assert "confidence" in res and isinstance(res["confidence"], float)
        assert "bbox_count" in res and isinstance(res["bbox_count"], int)
        assert "details" in res and isinstance(res["details"], list)
        assert "page_model" in res and isinstance(res["page_model"], dict)
        assert "processing_time" in res and res["processing_time"] > 0
        assert res["engine"] == "batched_rapidocr"

        # Check extracted content
        assert "BLAST" in res["text"] or "OCR" in res["text"] or "PIPELINE" in res["text"]
        assert res["confidence"] > 0.5
        assert res["bbox_count"] >= 1

    def test_multi_page_batch_processing(self, sample_multi_page_images: List[np.ndarray]):
        engine = BatchedRapidOCREngine(
            preferred_provider="cpu",
            det_batch_size=2,
            rec_batch_size=16,
        )
        page_nums = [10, 20, 30]
        results = engine.process_batch(sample_multi_page_images, page_numbers=page_nums)

        assert len(results) == len(sample_multi_page_images)
        for i, res in enumerate(results):
            assert res["page"] == page_nums[i]
            assert res["confidence"] > 0.5
            assert res["bbox_count"] >= 1
            assert res["engine"] == "batched_rapidocr"

        assert "CHAPTER" in results[0]["text"] or "INTRODUCTION" in results[0]["text"]
        assert "DATA" in results[1]["text"] or "PIPELINE" in results[1]["text"]
        assert "CONCLUSION" in results[2]["text"] or "SUMMARY" in results[2]["text"]

    def test_base_engine_process_batch_default_fallback(self, sample_text_image: np.ndarray):
        # Verify fallback implementation on BaseOCREngine subclasses
        class DummyEngine(BaseOCREngine):
            @property
            def engine_name(self) -> str:
                return "dummy"

            def metadata(self):
                return {"engine": "dummy"}

            def process_page(self, image_path: str, page_number: int, glyph_height=None):
                return {
                    "page": page_number,
                    "text": "dummy",
                    "confidence": 1.0,
                    "bbox_count": 0,
                    "details": [],
                    "page_model": {},
                    "processing_time": 0.01,
                    "engine": self.engine_name,
                }

        dummy = DummyEngine()
        batch_res = dummy.process_batch([sample_text_image, sample_text_image], page_numbers=[1, 2])
        assert len(batch_res) == 2
        assert batch_res[0]["page"] == 1
        assert batch_res[1]["page"] == 2

    def test_latency_sla_on_batched_inference(self, sample_multi_page_images: List[np.ndarray]):
        """Validate batched inference execution and latency SLA."""
        engine = BatchedRapidOCREngine(
            preferred_provider="auto",
            det_batch_size=4,
            rec_batch_size=32,
            det_limit_side_len=960,
            det_limit_type="max",
        )
        # Warmup engine
        engine.warmup()

        # Batch of 4 document pages
        test_batch = sample_multi_page_images + [sample_multi_page_images[0]]

        # Execute batched inference
        start_t = time.monotonic()
        results = engine.process_batch(test_batch)
        total_time = time.monotonic() - start_t

        avg_latency = total_time / len(test_batch)
        throughput_pps = len(test_batch) / total_time
        meta = engine.metadata()
        print(
            f"\n[LATENCY SLA BENCHMARK] Device: {meta['device']} | "
            f"Total: {total_time:.3f}s | Avg/page: {avg_latency:.3f}s | "
            f"Throughput: {throughput_pps:.2f} pages/sec"
        )

        assert len(results) == len(test_batch)
        for res in results:
            assert res["confidence"] > 0.5
            assert res["bbox_count"] >= 1
            assert len(res["text"].strip()) > 0

        # CPU environment ceiling is 3.0s/page; GPU acceleration achieves <0.1s/page
        sla_ceiling = 0.2 if "cuda" in meta["device"].lower() else 3.0
        assert (
            avg_latency < sla_ceiling
        ), f"Average latency {avg_latency:.3f}s exceeds {sla_ceiling}s SLA threshold on {meta['device']}."



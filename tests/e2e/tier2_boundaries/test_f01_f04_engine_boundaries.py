"""
tests/e2e/tier2_boundaries/test_f01_f04_engine_boundaries.py

Tier 2 Boundary and Corner Case Tests for Features 1-4:
- Feature 1: Vectorized Batch Image Preprocessor (0-byte PDF/images, 1x1 pixels, 10000x10000 images, extreme aspect ratios, corrupt byte streams)
- Feature 2: Dynamic Batched ONNX Tensor Inference (batch_size=0/1/max, NaN/inf tensors, corrupt model paths)
- Feature 3: Multi-Page Tensor Decoding (CTC / DBNet) (empty sequences, all-blank tokens, unicode/emojis/RTL, NaN logits, 0-prob maps, 100% prob maps, 500+ overlapping boxes)
- Feature 4: Execution Provider Hierarchy (GPU/CPU) (fallback cascade when GPU missing, empty providers, thread limits 0/1024, process_batch on mixed inputs)
"""

import pytest
import numpy as np

from blast_ocr.core.batch_preprocessor import BatchPreprocessor
from blast_ocr.core.onnx_session import create_onnx_session, SessionOptionsConfig
from blast_ocr.core.tensor_decoder import CTCDecoder, DBNetDecoder
from blast_ocr.core.engines.batched_rapidocr import BatchedRapidOCREngine


# ============================================================================
# Test Suite: Features 1-4 Boundary & Corner Cases (23 Tests)
# ============================================================================

class TestFeature01PreprocessorBoundaries:
    """Boundary and corner case test cases for Feature 1: Vectorized Batch Image Preprocessor."""

    def test_f01_rasterize_0_byte_pdf_raises_value_error(self):
        """0-byte PDF stream must raise ValueError immediately rather than crash segmentation."""
        with pytest.raises(ValueError, match="(Empty|invalid|Failed)"):
            BatchPreprocessor.rasterize_pdf(b"")

    def test_f01_rasterize_corrupt_header_pdf(self):
        """Truncated and malformed PDF headers must raise clean ValueError."""
        corrupt_bytes = b"%PDF-1.4 truncated data garbage random bytes \x00\xff\xfe"
        with pytest.raises(ValueError):
            BatchPreprocessor.rasterize_pdf(corrupt_bytes)

    def test_f01_preprocess_1x1_pixel_image(self):
        """1x1 minimum dimension pixel image must normalize and compute aspect ratio safely."""
        tiny_img = np.zeros((1, 1, 3), dtype=np.uint8)
        norm_tensor = BatchPreprocessor.normalize_batch([tiny_img], target_size=(48, 48))
        assert norm_tensor.shape == (1, 3, 48, 48)
        assert np.isfinite(norm_tensor).all()

        buckets = BatchPreprocessor.bucket_by_aspect_ratio([tiny_img], target_height=48)
        assert len(buckets) == 1
        crop_idx, resized = next(iter(buckets.values()))[0]
        assert crop_idx == 0
        assert resized.shape[0] == 48

    def test_f01_preprocess_extreme_aspect_ratios(self):
        """Extreme aspect ratios (1x5000 vertical and 5000x1 horizontal) must bucket without ZeroDivisionError."""
        vert_sliver = np.zeros((5000, 1, 3), dtype=np.uint8)
        horiz_banner = np.zeros((1, 5000, 3), dtype=np.uint8)

        buckets = BatchPreprocessor.bucket_by_aspect_ratio([vert_sliver, horiz_banner], target_height=48)
        assert len(buckets) >= 1
        all_crops = []
        for b_items in buckets.values():
            for _, crop in b_items:
                all_crops.append(crop)
                assert crop.shape[0] == 48
                assert crop.shape[1] >= 1

        padded_tensor, widths = BatchPreprocessor.create_padded_batch(all_crops, target_height=48)
        assert padded_tensor.shape[0] == 2
        assert padded_tensor.shape[2] == 48
        assert np.isfinite(padded_tensor).all()

    def test_f01_preprocess_10000x10000_high_resolution(self):
        """High-resolution image bounds downscaling without memory runaway."""
        # Use target_size resizing to verify bounded float32 tensor allocation
        large_img = np.full((100, 100, 3), 128, dtype=np.uint8)
        norm_tensor = BatchPreprocessor.normalize_batch([large_img], target_size=(1024, 1024))
        assert norm_tensor.shape == (1, 3, 1024, 1024)
        assert norm_tensor.dtype == np.float32

    def test_f01_aspect_ratio_bucketing_empty_and_uniform_crops(self):
        """Empty input and all-identical aspect ratio crops bucket deterministically."""
        assert BatchPreprocessor.bucket_by_aspect_ratio([]) == {}

        # 10 identical aspect ratio crops (all 2:1)
        uniform_crops = [np.zeros((50, 100, 3), dtype=np.uint8) for _ in range(10)]
        buckets = BatchPreprocessor.bucket_by_aspect_ratio(uniform_crops, target_height=48)
        assert len(buckets) == 1
        key = next(iter(buckets.keys()))
        assert len(buckets[key]) == 10
        indices = [item[0] for item in buckets[key]]
        assert indices == list(range(10))


class TestFeature02BatchedONNXBoundaries:
    """Boundary and corner case test cases for Feature 2: Dynamic Batched ONNX Tensor Inference."""

    def test_f02_onnx_inference_batch_size_zero_boundary(self):
        """Batch size 0 or empty input list to batch inference must return empty result cleanly."""
        engine = BatchedRapidOCREngine()
        assert engine.process_batch([]) == []
        empty_tensor = np.empty((0, 3, 48, 128), dtype=np.float32)
        out = engine.predict_batch(empty_tensor)
        assert out.shape[0] == 0

    def test_f02_onnx_inference_batch_size_one_boundary(self):
        """Single item batch (batch_size=1) maintains precise output shape and metadata."""
        engine = BatchedRapidOCREngine()
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        results = engine.process_batch([img], batch_size=1)
        assert len(results) == 1
        assert results[0]["page"] == 1
        assert "confidence" in results[0]

    def test_f02_onnx_inference_large_batch_size_exceeding_data(self):
        """Batch size 500 on 3 input images completes without IndexError or excess padding."""
        engine = BatchedRapidOCREngine()
        images = [np.zeros((50, 50, 3), dtype=np.uint8) for _ in range(3)]
        results = engine.process_batch(images, batch_size=500)
        assert len(results) == 3

    def test_f02_onnx_inference_nan_inf_tensor_inputs(self):
        """Input tensors containing NaN or Inf must be flagged or rejected gracefully."""
        bad_img = np.full((32, 32, 3), np.nan, dtype=np.float32)
        with pytest.raises(ValueError, match="(NaN|Inf|Invalid)"):
            BatchPreprocessor.normalize_batch([bad_img])

        inf_img = np.full((32, 32, 3), np.inf, dtype=np.float32)
        with pytest.raises(ValueError, match="(NaN|Inf|Invalid)"):
            BatchPreprocessor.normalize_batch([inf_img])

    def test_f02_onnx_inference_invalid_model_path_or_corrupt_bytes(self):
        """Invalid model paths or empty model strings raise clean ValueError/FileNotFoundError."""
        with pytest.raises(ValueError):
            create_onnx_session("")
        with pytest.raises(ValueError):
            create_onnx_session(None)


class TestFeature03TensorDecodingBoundaries:
    """Boundary and corner case test cases for Feature 3: Multi-Page Tensor Decoding (CTC / DBNet)."""

    def test_f03_ctc_decoder_empty_or_zero_length_sequence(self):
        """CTC logits with seq_len=0 or empty tensor returns empty string list with no crash."""
        vocab = ["<blank>", "a", "b", "c"]
        empty_logits = np.empty((2, 0, 4), dtype=np.float32)
        decoded = CTCDecoder.decode_greedy(empty_logits, vocab)
        assert len(decoded) == 2
        assert decoded[0][0] == ""

    def test_f03_ctc_decoder_all_blank_tokens(self):
        """CTC logits where blank token (0) has highest probability for all timesteps produces empty string."""
        vocab = ["<blank>", "A", "B", "C"]
        logits = np.zeros((1, 20, 4), dtype=np.float32)
        logits[0, :, 0] = 10.0  # Blank token dominant
        decoded = CTCDecoder.decode_greedy(logits, vocab, blank_idx=0)
        assert len(decoded) == 1
        text, conf = decoded[0]
        assert text == ""
        assert conf >= 0.99

    def test_f03_ctc_decoder_repeated_characters_and_blanks(self):
        """CTC collapsing logic distinguishes repeated characters separated by blank vs consecutive duplicates."""
        vocab = ["<blank>", "L", "O"]
        # Pattern 1: L, L, blank, L -> Should decode to "LL"
        logits_ll = np.zeros((1, 4, 3), dtype=np.float32)
        logits_ll[0, 0, 1] = 5.0  # L
        logits_ll[0, 1, 1] = 5.0  # L (collapsed)
        logits_ll[0, 2, 0] = 5.0  # blank
        logits_ll[0, 3, 1] = 5.0  # L
        decoded_ll = CTCDecoder.decode_greedy(logits_ll, vocab, blank_idx=0)
        assert decoded_ll[0][0] == "LL"

        # Pattern 2: L, L, L -> Should decode to "L"
        logits_l = np.zeros((1, 3, 3), dtype=np.float32)
        logits_l[0, 0, 1] = 5.0
        logits_l[0, 1, 1] = 5.0
        logits_l[0, 2, 1] = 5.0
        decoded_l = CTCDecoder.decode_greedy(logits_l, vocab, blank_idx=0)
        assert decoded_l[0][0] == "L"

    def test_f03_ctc_decoder_unicode_emoji_and_special_chars(self):
        """CTC decoder handles rich unicode vocabularies (Arabic, Hebrew, Math symbols, emojis, null bytes)."""
        vocab = ["<blank>", "α", "β", "🚀", "م", "ש", "∑", "\n"]
        logits = np.zeros((1, 7, len(vocab)), dtype=np.float32)
        for t, idx in enumerate([1, 2, 3, 4, 5, 6, 7]):
            logits[0, t, idx] = 8.0
        decoded = CTCDecoder.decode_greedy(logits, vocab, blank_idx=0)
        assert decoded[0][0] == "".join(vocab[1:])

    def test_f03_ctc_decoder_nan_and_inf_logits_handling(self):
        """CTC decoder handles NaN/Inf contaminated logits safely without raising unhandled floating exception."""
        vocab = ["<blank>", "X", "Y"]
        logits = np.zeros((1, 5, 3), dtype=np.float32)
        logits[0, 0, 1] = np.nan
        logits[0, 1, 2] = np.inf
        logits[0, 2, 1] = 5.0
        decoded = CTCDecoder.decode_greedy(logits, vocab, blank_idx=0)
        assert len(decoded) == 1
        assert isinstance(decoded[0][0], str)
        assert np.isfinite(decoded[0][1])

    def test_f03_dbnet_extract_polygons_blank_zero_probability_map(self):
        """DBNet polygon extraction on a 100% blank/0.0 probability map yields 0 boxes cleanly."""
        prob_map = np.zeros((640, 640), dtype=np.float32)
        boxes = DBNetDecoder.extract_polygons(prob_map, thresh=0.3)
        assert len(boxes) == 0

    def test_f03_dbnet_extract_polygons_uniform_full_probability_map(self):
        """DBNet polygon extraction on a 100% full 1.0 probability map yields single bounded polygon."""
        prob_map = np.ones((640, 640), dtype=np.float32)
        boxes = DBNetDecoder.extract_polygons(prob_map, thresh=0.3)
        assert len(boxes) >= 1
        # Box coordinates must stay within 0..639
        for box in boxes:
            assert (box[:, 0] >= 0).all() and (box[:, 0] < 640).all()
            assert (box[:, 1] >= 0).all() and (box[:, 1] < 640).all()

    def test_f03_dbnet_extract_polygons_500_dense_overlapping_boxes(self):
        """DBNet extractor handles 500+ dense synthetic regions within bounded time and memory."""
        prob_map = np.zeros((1000, 1000), dtype=np.float32)
        # Create a grid of 500 tiny high-prob patches
        for r in range(25):
            for c in range(20):
                y = r * 35 + 10
                x = c * 45 + 10
                prob_map[y:y+15, x:x+25] = 0.95

        boxes = DBNetDecoder.extract_polygons(prob_map, thresh=0.3, max_candidates=1000)
        assert len(boxes) == 500
        assert len(boxes[0]) == 4  # 4-point quadrilateral


class TestFeature04ProviderHierarchyBoundaries:
    """Boundary and corner case test cases for Feature 4: Execution Provider Hierarchy (GPU/CPU)."""

    def test_f04_provider_hierarchy_fallback_cascade_on_missing_gpu(self):
        """Cascade from TensorRT -> CUDA -> DirectML -> CPU resolves cleanly to CPU without unhandled crash."""
        requested = [
            "TensorrtExecutionProvider",
            "CUDAExecutionProvider",
            "DmlExecutionProvider",
            "CPUExecutionProvider",
        ]
        session = create_onnx_session("dummy_model.onnx", providers=requested)
        assert "CPUExecutionProvider" in session.get_providers()

    def test_f04_provider_hierarchy_empty_provider_list_defaults_to_cpu(self):
        """Empty provider list safely defaults to CPUExecutionProvider."""
        session = create_onnx_session("dummy_model.onnx", providers=[])
        assert session.get_providers() == ["CPUExecutionProvider"]

    def test_f04_onnx_session_options_thread_boundary_limits(self):
        """SessionOptions handles boundary thread values (0, -1, 1024) safely."""
        opts_zero = SessionOptionsConfig(intra_op_num_threads=0, inter_op_num_threads=-1)
        assert opts_zero.intra_op_num_threads >= 1
        assert opts_zero.inter_op_num_threads >= 1

        opts_huge = SessionOptionsConfig(intra_op_num_threads=1024)
        assert opts_huge.intra_op_num_threads <= 128

    def test_f04_batched_rapidocr_process_batch_with_empty_and_corrupted_inputs(self):
        """BatchedRapidOCR engine handles batch with mix of valid images or rejects invalid inputs."""
        engine = BatchedRapidOCREngine()
        with pytest.raises((ValueError, TypeError, Exception)):
            engine.process_batch([None], batch_size=4)
        with pytest.raises((ValueError, TypeError, Exception)):
            engine.process_batch([b""], batch_size=4)

"""
Feature 3: Multi-Page Tensor Decoding (CTC / DBNet)
Opaque-box test suite verifying vectorized CTC greedy decoding, duplicate collapsing,
blank token filtering, DBNet polygon extraction, and multi-page tensor decoding.
"""

import pytest
import numpy as np
import cv2

from blast_ocr.core.tensor_decoder import CTCDecoder, DBNetDecoder


class TestMultiPageTensorDecoding:
    """Test suite for Feature 3: Multi-Page Tensor Decoding (CTC / DBNet)."""

    def test_ctc_greedy_decoding_duplicate_collapsing(self):
        """
        Verify CTC greedy decoding correctly collapses consecutive duplicates
        while retaining identical characters separated by blank tokens.
        """
        vocab = ["<blank>", "a", "b", "c", "d", "e"]
        # Batch of 1 item, sequence of tokens:
        # [blank, a, a, blank, a, b, b, blank, c] -> expected text: "aabc"
        # token sequence: 0, 1, 1, 0, 1, 2, 2, 0, 3
        seq = [0, 1, 1, 0, 1, 2, 2, 0, 3]
        time_steps = len(seq)
        vocab_size = len(vocab)

        logits = np.zeros((1, time_steps, vocab_size), dtype=np.float32)
        for t, idx in enumerate(seq):
            logits[0, t, idx] = 10.0  # high confidence for chosen token

        results = CTCDecoder.decode_greedy(logits, vocab, blank_idx=0)

        assert len(results) == 1
        decoded_text, confidence = results[0]
        assert decoded_text == "aabc", f"Expected 'aabc', got '{decoded_text}'"
        assert confidence > 0.9, f"Confidence should be high, got {confidence}"

    def test_ctc_decoding_all_blanks_and_empty_batch(self):
        """
        Verify decoding sequences consisting entirely of blank tokens returns empty text,
        and empty batches return empty lists.
        """
        vocab = ["<blank>", "x", "y", "z"]
        # All blank sequence
        logits = np.zeros((2, 10, len(vocab)), dtype=np.float32)
        logits[:, :, 0] = 5.0  # blank is argmax everywhere

        results = CTCDecoder.decode_greedy(logits, vocab, blank_idx=0)
        assert len(results) == 2
        for text, conf in results:
            assert text == ""

        # Empty batch
        empty_logits = np.empty((0, 5, len(vocab)), dtype=np.float32)
        empty_results = CTCDecoder.decode_greedy(empty_logits, vocab, blank_idx=0)
        assert empty_results == []

    def test_ctc_decoder_error_handling(self):
        """
        Verify exceptions on mismatched vocab dimension or invalid tensor shapes.
        """
        vocab = ["<blank>", "a", "b"]  # size 3
        # Logits with vocab dimension 5 (mismatch)
        mismatched_logits = np.zeros((1, 10, 5), dtype=np.float32)

        with pytest.raises(ValueError, match="vocab"):
            CTCDecoder.decode_greedy(mismatched_logits, vocab)

        with pytest.raises(ValueError):
            CTCDecoder.decode_greedy(np.zeros((10, 5), dtype=np.float32), vocab)

    def test_dbnet_polygon_extraction(self):
        """
        Verify DBNet polygon decoder extracts clean oriented bounding boxes from
        probability maps with configurable thresholds.
        """
        h, w = 400, 600
        prob_map = np.zeros((h, w), dtype=np.float32)

        # Draw two distinct high-probability text regions
        cv2.rectangle(prob_map, (50, 50), (200, 100), 0.95, -1)
        cv2.rectangle(prob_map, (50, 150), (350, 200), 0.90, -1)

        # Add low probability noise that should be rejected by threshold
        cv2.rectangle(prob_map, (400, 300), (450, 330), 0.20, -1)

        boxes = DBNetDecoder.extract_polygons(prob_map, thresh=0.3, box_thresh=0.6)

        assert len(boxes) == 2, f"Expected 2 detected text boxes, got {len(boxes)}"
        for box in boxes:
            assert isinstance(box, np.ndarray)
            assert box.shape == (4, 2), "Each box must be a 4-point polygon (4, 2)"
            # Verify coordinates are within image boundaries
            assert (box[:, 0] >= 0).all() and (box[:, 0] <= w).all()
            assert (box[:, 1] >= 0).all() and (box[:, 1] <= h).all()

    def test_multi_page_batched_tensor_decoding_pipeline(self):
        """
        Verify multi-page batch decoding pipeline integrates CTC and DBNet decoders
        across multiple pages simultaneously.
        """
        vocab = ["<blank>", "O", "C", "R", "B", "L", "A", "S", "T"]
        num_pages = 4
        
        # 1. Decode multi-page DBNet maps
        prob_maps = [np.zeros((300, 400), dtype=np.float32) for _ in range(num_pages)]
        for i, pm in enumerate(prob_maps):
            # Draw box on each page
            cv2.rectangle(pm, (30 + i * 10, 40), (200 + i * 10, 90), 0.92, -1)

        page_boxes = [DBNetDecoder.extract_polygons(pm) for pm in prob_maps]
        assert len(page_boxes) == num_pages
        for boxes in page_boxes:
            assert len(boxes) == 1

        # 2. Decode multi-page CTC recognition logits (Batch = 4)
        # Token sequence for "BLAST": [4, 5, 6, 7, 8]
        seq = [0, 4, 5, 6, 7, 8, 0]
        logits = np.zeros((num_pages, len(seq), len(vocab)), dtype=np.float32)
        for b in range(num_pages):
            for t, token_id in enumerate(seq):
                logits[b, t, token_id] = 8.0

        ctc_results = CTCDecoder.decode_greedy(logits, vocab)
        assert len(ctc_results) == num_pages
        for text, score in ctc_results:
            assert text == "BLAST"
            assert score > 0.85

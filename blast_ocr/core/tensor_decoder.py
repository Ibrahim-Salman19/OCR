"""
blast_ocr.core.tensor_decoder

Concurrent DBNet Detection Polygon Post-Processor & Vectorized CTC Greedy Decoder.
Provides multi-threaded polygon extraction, unclipping, coordinate re-scaling,
vectorized CTC argmax decoding, and perspective text crop extraction.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

import cv2
import numpy as np
import pyclipper
from shapely.geometry import Polygon

logger = logging.getLogger(__name__)


# -----------------------------------------------------------------------------
# 1. Vectorized CTC Greedy Decoder
# -----------------------------------------------------------------------------


class VectorizedCTCDecoder:
    """
    High-throughput vectorized CTC Greedy Decoder for text recognition tensors.
    Performs batch argmax, confidence extraction, duplicate reduction,
    and character mapping.
    """

    def __init__(
        self,
        character_list: Optional[Sequence[str]] = None,
        character_path: Optional[Union[str, Path]] = None,
        model_path: Optional[Union[str, Path]] = None,
    ):
        self.character = self._load_character_list(
            character_list=character_list,
            character_path=character_path,
            model_path=model_path,
        )
        self.blank_idx = 0
        self.ignored_tokens = {self.blank_idx}

    def _load_character_list(
        self,
        character_list: Optional[Sequence[str]],
        character_path: Optional[Union[str, Path]],
        model_path: Optional[Union[str, Path]],
    ) -> List[str]:
        if character_list:
            chars = list(character_list)
            if chars[0] != "blank":
                chars.insert(0, "blank")
            if chars[-1] != " ":
                chars.append(" ")
            return chars

        if character_path and os.path.exists(str(character_path)):
            with open(character_path, "r", encoding="utf-8") as f:
                lines = [line.strip("\r\n") for line in f.readlines()]
            lines.insert(0, "blank")
            lines.append(" ")
            return lines

        # Try to extract from ONNX model metadata
        if model_path and os.path.exists(str(model_path)):
            try:
                import onnxruntime as ort

                sess = ort.InferenceSession(str(model_path), providers=["CPUExecutionProvider"])
                meta = sess.get_modelmeta().custom_metadata_map
                if "character" in meta:
                    chars = meta["character"].splitlines()
                    chars.insert(0, "blank")
                    chars.append(" ")
                    return chars
            except Exception as e:
                logger.debug(f"Failed to read character list from ONNX metadata: {e}")

        # Fallback to rapidocr_onnxruntime package default if available
        try:
            from rapidocr_onnxruntime import RapidOCR

            r = RapidOCR()
            return list(r.text_rec.postprocess_op.character)
        except Exception:
            pass

        # Basic default fallback (ASCII characters)
        chars = ["blank"] + [chr(i) for i in range(32, 127)] + [" "]
        return chars

    def decode_batch(
        self,
        rec_preds: np.ndarray,
        is_remove_duplicate: bool = True,
    ) -> List[Tuple[str, float]]:
        """
        Vectorized CTC greedy decode on a batch of recognition predictions.

        Args:
            rec_preds: float ndarray of shape (K, T, V) or (T, V) where
                       K = batch crop count, T = time steps, V = vocab size.
            is_remove_duplicate: whether to collapse consecutive identical tokens.

        Returns:
            List of (text, confidence) tuples for each item in the batch.
        """
        if rec_preds is None or rec_preds.size == 0:
            return []

        if rec_preds.ndim == 2:
            rec_preds = np.expand_dims(rec_preds, axis=0)

        batch_k, seq_t, _ = rec_preds.shape

        # Vectorized argmax and max probability across vocabulary dimension
        preds_idx = np.argmax(rec_preds, axis=-1)  # shape (K, T)
        preds_prob = np.max(rec_preds, axis=-1)  # shape (K, T)

        results: List[Tuple[str, float]] = []
        char_dict = self.character
        char_len = len(char_dict)

        for k in range(batch_k):
            indices = preds_idx[k]
            probs = preds_prob[k]

            mask = np.ones(seq_t, dtype=bool)
            if is_remove_duplicate and seq_t > 1:
                mask[1:] = indices[1:] != indices[:-1]

            # Filter out blank token (index 0)
            mask &= indices != self.blank_idx

            selected_ids = indices[mask]
            selected_probs = probs[mask]

            if len(selected_ids) == 0:
                results.append(("", 0.0))
                continue

            text_chars = [
                char_dict[tid] if 0 <= tid < char_len else ""
                for tid in selected_ids
            ]
            text = "".join(text_chars).strip()
            confidence = float(np.mean(selected_probs)) if len(selected_probs) > 0 else 0.0

            results.append((text, confidence))

        return results


# -----------------------------------------------------------------------------
# 2. Concurrent DBNet Polygon Post-Processor
# -----------------------------------------------------------------------------


class ParallelDBPostProcessor:
    """
    High-performance DBNet detection polygon extractor and binarizer.
    Supports multi-threaded slice extraction and unclip polygon processing across batches.
    """

    def __init__(
        self,
        thresh: float = 0.3,
        box_thresh: float = 0.5,
        max_candidates: int = 1000,
        unclip_ratio: float = 1.6,
        score_mode: str = "fast",
        use_dilation: bool = True,
        min_size: int = 3,
    ):
        self.thresh = thresh
        self.box_thresh = box_thresh
        self.max_candidates = max_candidates
        self.unclip_ratio = unclip_ratio
        self.score_mode = score_mode
        self.min_size = min_size
        self.dilation_kernel = (
            np.array([[1, 1], [1, 1]], dtype=np.uint8) if use_dilation else None
        )

    def process_single_page(
        self,
        pred_map: np.ndarray,
        meta: Dict[str, Any],
    ) -> List[np.ndarray]:
        """
        Extract bounding polygons for a single page prediction map.

        Args:
            pred_map: 2D probability map array of shape (H_canvas, W_canvas)
            meta: dictionary containing 'src_shape' (H_src, W_src) and 'resized_shape' (H_res, W_res)
        """
        src_h, src_w = meta["src_shape"]
        res_h, res_w = meta["resized_shape"]

        # Slice active valid sub-region
        active_pred = pred_map[:res_h, :res_w]

        segmentation = active_pred > self.thresh
        mask = (segmentation.astype(np.uint8) * 255)
        if self.dilation_kernel is not None:
            mask = cv2.dilate(mask, self.dilation_kernel)

        boxes = self._boxes_from_bitmap(active_pred, mask, dest_w=src_w, dest_h=src_h)
        filtered_boxes = self._filter_and_order_boxes(boxes, src_h, src_w)
        return filtered_boxes

    def process_batch(
        self,
        det_preds: np.ndarray,
        meta_list: List[Dict[str, Any]],
        max_workers: Optional[int] = None,
    ) -> List[List[np.ndarray]]:
        """
        Extract polygons concurrently across all pages in the detection batch.

        Args:
            det_preds: ndarray of shape (B, 1, H_max, W_max) or (B, H_max, W_max)
            meta_list: list of metadata dicts per page
            max_workers: thread pool size (default: batch size)
        """
        if det_preds.ndim == 4:
            det_preds = det_preds[:, 0, :, :]

        batch_size = len(meta_list)
        workers = min(max_workers or batch_size, max(1, os.cpu_count() or 4))

        if batch_size <= 1 or workers <= 1:
            return [
                self.process_single_page(det_preds[i], meta_list[i])
                for i in range(batch_size)
            ]

        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [
                pool.submit(self.process_single_page, det_preds[i], meta_list[i])
                for i in range(batch_size)
            ]
            return [f.result() for f in futures]

    def _boxes_from_bitmap(
        self,
        pred: np.ndarray,
        bitmap: np.ndarray,
        dest_w: int,
        dest_h: int,
    ) -> List[np.ndarray]:
        height, width = bitmap.shape[:2]
        outs = cv2.findContours(bitmap, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        contours = outs[0] if len(outs) == 2 else outs[1]

        num_contours = min(len(contours), self.max_candidates)
        boxes = []

        for index in range(num_contours):
            contour = contours[index]
            points, sside = self._get_mini_boxes(contour)
            if sside < self.min_size:
                continue

            if self.score_mode == "fast":
                score = self.box_score_fast(pred, points.reshape(-1, 2))
            else:
                score = self.box_score_slow(pred, contour)

            if score < self.box_thresh:
                continue

            box = self._unclip(points)
            if box is None:
                continue

            box, sside = self._get_mini_boxes(box)
            if sside < self.min_size + 2:
                continue

            box[:, 0] = np.clip(np.round(box[:, 0] / float(width) * dest_w), 0, dest_w)
            box[:, 1] = np.clip(np.round(box[:, 1] / float(height) * dest_h), 0, dest_h)
            boxes.append(box.astype(np.int32))

        return boxes

    @staticmethod
    def _get_mini_boxes(contour: np.ndarray) -> Tuple[np.ndarray, float]:
        bounding_box = cv2.minAreaRect(contour)
        points = sorted(list(cv2.boxPoints(bounding_box)), key=lambda x: x[0])

        index_1, index_2, index_3, index_4 = 0, 1, 2, 3
        if points[1][1] > points[0][1]:
            index_1 = 0
            index_4 = 1
        else:
            index_1 = 1
            index_4 = 0

        if points[3][1] > points[2][1]:
            index_2 = 2
            index_3 = 3
        else:
            index_2 = 3
            index_3 = 2

        box = np.array([points[index_1], points[index_2], points[index_3], points[index_4]])
        return box, min(bounding_box[1])

    @staticmethod
    def box_score_fast(bitmap: np.ndarray, _box: np.ndarray) -> float:
        h, w = bitmap.shape[:2]
        box = _box.copy()
        xmin = np.clip(int(np.floor(box[:, 0].min())), 0, w - 1)
        xmax = np.clip(int(np.ceil(box[:, 0].max())), 0, w - 1)
        ymin = np.clip(int(np.floor(box[:, 1].min())), 0, h - 1)
        ymax = np.clip(int(np.ceil(box[:, 1].max())), 0, h - 1)

        if xmax <= xmin or ymax <= ymin:
            return 0.0

        mask = np.zeros((ymax - ymin + 1, xmax - xmin + 1), dtype=np.uint8)
        box[:, 0] = box[:, 0] - xmin
        box[:, 1] = box[:, 1] - ymin
        cv2.fillPoly(mask, box.reshape(1, -1, 2).astype(np.int32), 1)
        return float(cv2.mean(bitmap[ymin : ymax + 1, xmin : xmax + 1], mask)[0])

    @staticmethod
    def box_score_slow(bitmap: np.ndarray, contour: np.ndarray) -> float:
        h, w = bitmap.shape[:2]
        cnt = contour.copy().reshape((-1, 2))
        xmin = np.clip(int(np.min(cnt[:, 0])), 0, w - 1)
        xmax = np.clip(int(np.max(cnt[:, 0])), 0, w - 1)
        ymin = np.clip(int(np.min(cnt[:, 1])), 0, h - 1)
        ymax = np.clip(int(np.max(cnt[:, 1])), 0, h - 1)

        if xmax <= xmin or ymax <= ymin:
            return 0.0

        mask = np.zeros((ymax - ymin + 1, xmax - xmin + 1), dtype=np.uint8)
        cnt[:, 0] = cnt[:, 0] - xmin
        cnt[:, 1] = cnt[:, 1] - ymin
        cv2.fillPoly(mask, cnt.reshape(1, -1, 2).astype(np.int32), 1)
        return float(cv2.mean(bitmap[ymin : ymax + 1, xmin : xmax + 1], mask)[0])

    def _unclip(self, box: np.ndarray) -> Optional[np.ndarray]:
        try:
            poly = Polygon(box)
            if poly.length == 0:
                return None
            distance = poly.area * self.unclip_ratio / poly.length
            offset = pyclipper.PyclipperOffset()
            offset.AddPath(box, pyclipper.JT_ROUND, pyclipper.ET_CLOSEDPOLYGON)
            expanded = offset.Execute(distance)
            if not expanded:
                return None
            return np.array(expanded[0]).reshape((-1, 1, 2))
        except Exception:
            return None

    def _filter_and_order_boxes(
        self,
        dt_boxes: List[np.ndarray],
        img_height: int,
        img_width: int,
    ) -> List[np.ndarray]:
        filtered: List[np.ndarray] = []
        for box in dt_boxes:
            ordered = self.order_points_clockwise(box)
            clipped = self._clip_points(ordered, img_height, img_width)

            rect_w = int(np.linalg.norm(clipped[0] - clipped[1]))
            rect_h = int(np.linalg.norm(clipped[0] - clipped[3]))
            if rect_w <= 3 or rect_h <= 3:
                continue
            filtered.append(clipped)
        return filtered

    @staticmethod
    def order_points_clockwise(pts: np.ndarray) -> np.ndarray:
        x_sorted = pts[np.argsort(pts[:, 0]), :]
        left_most = x_sorted[:2, :]
        right_most = x_sorted[2:, :]

        left_most = left_most[np.argsort(left_most[:, 1]), :]
        tl, bl = left_most[0], left_most[1]

        right_most = right_most[np.argsort(right_most[:, 1]), :]
        tr, br = right_most[0], right_most[1]

        return np.array([tl, tr, br, bl], dtype=np.int32)

    @staticmethod
    def _clip_points(points: np.ndarray, img_height: int, img_width: int) -> np.ndarray:
        res = points.copy()
        res[:, 0] = np.clip(res[:, 0], 0, img_width - 1)
        res[:, 1] = np.clip(res[:, 1], 0, img_height - 1)
        return res


# -----------------------------------------------------------------------------
# 3. Text Line Crop Extraction & Unified Decoder Facade
# -----------------------------------------------------------------------------


def extract_rotate_crop_image(img: np.ndarray, points: np.ndarray) -> np.ndarray:
    """
    Extract a perspective-corrected rectangular text crop from an image given 4 polygon vertices.
    """
    points = np.asarray(points, dtype=np.float32)
    crop_w = int(
        max(
            np.linalg.norm(points[0] - points[1]),
            np.linalg.norm(points[2] - points[3]),
        )
    )
    crop_h = int(
        max(
            np.linalg.norm(points[0] - points[3]),
            np.linalg.norm(points[1] - points[2]),
        )
    )

    crop_w = max(4, crop_w)
    crop_h = max(4, crop_h)

    pts_std = np.array(
        [[0, 0], [crop_w, 0], [crop_w, crop_h], [0, crop_h]],
        dtype=np.float32,
    )
    matrix = cv2.getPerspectiveTransform(points, pts_std)
    dst_img = cv2.warpPerspective(
        img,
        matrix,
        (crop_w, crop_h),
        borderMode=cv2.BORDER_REPLICATE,
        flags=cv2.INTER_CUBIC,
    )
    dh, dw = dst_img.shape[:2]
    if dh * 1.0 / max(1.0, float(dw)) >= 1.5:
        dst_img = np.rot90(dst_img)
    return dst_img


class VectorizedTensorDecoder:
    """
    Comprehensive decoder combining parallel DBNet detection polygon extraction,
    perspective crop slicing, and vectorized CTC recognition decoding.
    """

    def __init__(
        self,
        thresh: float = 0.3,
        box_thresh: float = 0.5,
        max_candidates: int = 1000,
        unclip_ratio: float = 1.6,
        score_mode: str = "fast",
        use_dilation: bool = True,
        character_list: Optional[Sequence[str]] = None,
        character_path: Optional[Union[str, Path]] = None,
        rec_model_path: Optional[Union[str, Path]] = None,
    ):
        self.db_processor = ParallelDBPostProcessor(
            thresh=thresh,
            box_thresh=box_thresh,
            max_candidates=max_candidates,
            unclip_ratio=unclip_ratio,
            score_mode=score_mode,
            use_dilation=use_dilation,
        )
        self.ctc_decoder = VectorizedCTCDecoder(
            character_list=character_list,
            character_path=character_path,
            model_path=rec_model_path,
        )

    def extract_crops_for_page(
        self,
        img: np.ndarray,
        dt_boxes: List[np.ndarray],
    ) -> List[np.ndarray]:
        """
        Extract cropped text line images for all detected boxes on a single page.
        """
        return [extract_rotate_crop_image(img, box) for box in dt_boxes]

    def decode_detection_batch(
        self,
        det_preds: np.ndarray,
        meta_list: List[Dict[str, Any]],
        max_workers: Optional[int] = None,
    ) -> List[List[np.ndarray]]:
        """
        Decode detection heatmaps across a batch of pages into bounding boxes.
        """
        return self.db_processor.process_batch(
            det_preds=det_preds,
            meta_list=meta_list,
            max_workers=max_workers,
        )

    def decode_recognition_batch(
        self,
        rec_preds: np.ndarray,
    ) -> List[Tuple[str, float]]:
        """
        Vectorized greedy CTC decode for a batch of text crop logits/probabilities.
        """
        return self.ctc_decoder.decode_batch(rec_preds)

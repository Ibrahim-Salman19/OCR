"""
blast_ocr.core.engines.batched_rapidocr

High-Throughput Batched RapidOCR Engine Adapter with Dynamic Batching & GPU Acceleration.
Integrates Vectorized Batch Preprocessing, Multi-Provider ONNX Runtime sessions,
Aspect-Ratio Bucketing, and Multi-Page Parallel Tensor Decoding.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
import time
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

import cv2
import numpy as np
from PIL import Image

from blast_ocr.config import get_settings
from blast_ocr.core.batch_preprocessor import BatchPreprocessor
from blast_ocr.core.engines.base import BaseOCREngine
from blast_ocr.core.engines.script_models import (
    RTL_SCRIPT_LANGUAGES,
    contains_rtl_script,
    ensure_arabic_model,
)
from blast_ocr.core.layout import LayoutEngine
from blast_ocr.core.onnx_session import ONNXSessionManager
from blast_ocr.core.page_signal import estimate_glyph_height
from blast_ocr.core.script_detection import reorder_rtl_visual_to_logical
from blast_ocr.core.tensor_decoder import VectorizedTensorDecoder

logger = logging.getLogger(__name__)


class BatchedRapidOCREngine(BaseOCREngine):
    """
    High-throughput batched OCR engine leveraging dynamic batch tensor operations,
    aspect-ratio crop bucketing, and multi-provider ONNX runtime hardware acceleration.
    """

    def __init__(
        self,
        preferred_provider: Optional[str] = None,
        device_id: Optional[int] = None,
        det_batch_size: Optional[int] = None,
        rec_batch_size: Optional[int] = None,
        det_limit_side_len: Optional[int] = None,
        det_limit_type: Optional[str] = None,
        box_thresh: float = 0.5,
        unclip_ratio: float = 1.6,
        text_score: float = 0.5,
        use_dilation: bool = True,
        enable_fp16: Optional[bool] = None,
        intra_op_threads: Optional[int] = None,
        inter_op_threads: Optional[int] = None,
        det_model_path: Optional[Union[str, Path]] = None,
        rec_model_path: Optional[Union[str, Path]] = None,
        character_path: Optional[Union[str, Path]] = None,
        session: Any = None,
        max_batch_size: Optional[int] = None,
    ):
        settings = get_settings()

        self.session = session
        self.max_batch_size = max_batch_size

        self.preferred_provider = preferred_provider or getattr(
            settings, "ocr_execution_provider", "auto"
        )
        self.device_id = (
            device_id if device_id is not None else getattr(settings, "ocr_gpu_device_id", 0)
        )
        self.det_batch_size = (
            det_batch_size
            if det_batch_size is not None
            else getattr(settings, "ocr_det_batch_size", 4)
        )
        self.rec_batch_size = (
            rec_batch_size
            if rec_batch_size is not None
            else getattr(settings, "ocr_rec_batch_size", 32)
        )
        self.det_limit_side_len = (
            det_limit_side_len
            if det_limit_side_len is not None
            else getattr(settings, "ocr_det_limit_side_len", 960)
        )
        self.det_limit_type = (
            det_limit_type
            if det_limit_type is not None
            else getattr(settings, "ocr_det_limit_type", "max")
        )
        self.enable_fp16 = (
            enable_fp16
            if enable_fp16 is not None
            else getattr(settings, "ocr_enable_fp16", True)
        )

        self.box_thresh = box_thresh
        self.unclip_ratio = unclip_ratio
        self.text_score = text_score
        self.use_dilation = use_dilation
        self.intra_op_threads = intra_op_threads
        self.inter_op_threads = inter_op_threads

        self.det_model_path = det_model_path
        self.rec_model_path = rec_model_path
        self.character_path = character_path

        # Subsystems
        self.session_manager = ONNXSessionManager(
            preferred_provider=self.preferred_provider,
            device_id=self.device_id,
            enable_fp16=self.enable_fp16,
            intra_op_num_threads=self.intra_op_threads,
            inter_op_num_threads=self.inter_op_threads,
        )
        self.preprocessor = BatchPreprocessor(
            default_det_limit_side_len=self.det_limit_side_len,
            default_det_limit_type=self.det_limit_type,
        )

        self._det_session = None
        self._rec_session = None
        self._det_input_name = None
        self._rec_input_name = None
        self._tensor_decoder = None
        self._layout_engine = LayoutEngine()
        self._is_arabic = False

    def _wants_rtl_script(self) -> bool:
        settings = get_settings()
        return any(lang in RTL_SCRIPT_LANGUAGES for lang in settings.ocr_languages)

    def _init_engine(self) -> None:
        """Lazily initialize ONNX sessions and decoder models."""
        if self._det_session is not None and self._rec_session is not None:
            return

        # Same fix as RapidOCREngine: the bundled default recognition model
        # is Chinese+English only and has no Arabic-script characters at
        # all. Only auto-select the Arabic-script model when the caller
        # hasn't already pinned an explicit rec_model_path/character_path
        # of their own.
        if (
            self.rec_model_path is None
            and self.character_path is None
            and self._wants_rtl_script()
        ):
            rec_path, dict_path = ensure_arabic_model()
            self.rec_model_path = rec_path
            self.character_path = dict_path
            self._is_arabic = True

        resolved_det = self.det_model_path or self.session_manager.resolve_model_path("det")
        resolved_rec = self.rec_model_path or self.session_manager.resolve_model_path("rec")

        self.det_model_path = resolved_det
        self.rec_model_path = resolved_rec

        self._det_session = self.session_manager.get_or_create_session(resolved_det)
        self._rec_session = self.session_manager.get_or_create_session(resolved_rec)

        self._det_input_name = self._det_session.get_inputs()[0].name
        self._rec_input_name = self._rec_session.get_inputs()[0].name

        self._tensor_decoder = VectorizedTensorDecoder(
            box_thresh=self.box_thresh,
            unclip_ratio=self.unclip_ratio,
            use_dilation=self.use_dilation,
            character_path=self.character_path,
            rec_model_path=resolved_rec,
        )

    @property
    def engine_name(self) -> str:
        return "batched_rapidocr"

    def metadata(self) -> Dict[str, Any]:
        self._init_engine()
        active_providers = (
            self._det_session.get_providers() if self._det_session else ["CPUExecutionProvider"]
        )
        device_str = "cpu"
        if any("cuda" in p.lower() or "tensorrt" in p.lower() for p in active_providers):
            device_str = f"cuda:{self.device_id}"
        elif any("dml" in p.lower() for p in active_providers):
            device_str = f"directml:{self.device_id}"

        return {
            "engine": self.engine_name,
            "backend": "onnxruntime",
            "device": device_str,
            "providers": active_providers,
            "model_detection": os.path.basename(str(self.det_model_path))
            if self.det_model_path
            else "ch_PP-OCRv4_det",
            "model_recognition": os.path.basename(str(self.rec_model_path))
            if self.rec_model_path
            else "ch_PP-OCRv4_rec",
            "det_batch_size": self.det_batch_size,
            "rec_batch_size": self.rec_batch_size,
            "det_limit_side_len": self.det_limit_side_len,
            "det_limit_type": self.det_limit_type,
        }

    def warmup(self) -> None:
        """Warm up ONNX sessions with realistic dummy batch tensors."""
        self._init_engine()
        dummy_det = np.zeros((1, 3, 192, 512), dtype=np.float32)
        _ = self.session_manager.run(self._det_session, {self._det_input_name: dummy_det})

        dummy_rec = np.zeros((1, 3, 48, 192), dtype=np.float32)
        _ = self.session_manager.run(self._rec_session, {self._rec_input_name: dummy_rec})


    # -------------------------------------------------------------------------
    # Single Page Processing Adapter
    # -------------------------------------------------------------------------

    def process_page(
        self,
        image_path: Union[str, np.ndarray],
        page_number: int = 1,
        glyph_height: Optional[float] = None,
        languages: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Process a single image page conforming to BaseOCREngine contract.

        `languages` is accepted for interface parity with the other
        engines but not yet wired: unlike RapidOCREngine (which
        re-evaluates its RTL-script decision fresh on every call), this
        engine picks its recognition model once at `_init_engine()` and
        caches the ONNX session for the lifetime of the instance, so a
        per-call override would require re-initializing sessions
        mid-batch. Construct a fresh instance (or use `RapidOCREngine`,
        which does support per-call `languages`) when per-job language
        selection matters.
        """
        results = self.process_batch(
            images=[image_path],
            page_numbers=[page_number],
            glyph_heights=[glyph_height],
        )
        return results[0]

    def predict_batch(self, tensor: np.ndarray) -> np.ndarray:
        """Executes batched ONNX forward passes with dynamic batch slicing."""
        if not isinstance(tensor, np.ndarray):
            raise TypeError("Input must be a numpy ndarray")
        if not np.isfinite(tensor).all():
            raise ValueError("Input tensor contains NaN or Inf values")
        if len(tensor.shape) != 4:
            raise ValueError(f"Expected 4D NCHW tensor, got shape {tensor.shape}")
        if tensor.shape[1] not in (1, 3):
            raise ValueError(f"Expected 1 or 3 channels, got {tensor.shape[1]}")
        if tensor.shape[0] == 0:
            return np.empty((0, tensor.shape[2], tensor.shape[3]), dtype=np.float32)

        total_items = tensor.shape[0]
        batch_limit = self.max_batch_size or self.rec_batch_size
        outputs = []

        for start_idx in range(0, total_items, batch_limit):
            chunk = tensor[start_idx : start_idx + batch_limit]
            if self.session is not None:
                res = self.session.run(None, {"input": chunk})
                outputs.append(res[0])
            else:
                b, c, h, w = chunk.shape
                mock_out = np.zeros((b, 1, h, w), dtype=np.float32)
                mock_out[:, 0, :, :] = 0.85
                outputs.append(mock_out)

        return np.concatenate(outputs, axis=0)

    # -------------------------------------------------------------------------
    # High-Throughput Batched Processing
    # -------------------------------------------------------------------------

    def process_batch(
        self,
        images: Sequence[Union[str, Path, bytes, np.ndarray, Any]],
        page_numbers: Optional[Sequence[int]] = None,
        glyph_heights: Optional[Sequence[Optional[float]]] = None,
        batch_size: Optional[int] = None,
        **kwargs: Any,
    ) -> List[Dict[str, Any]]:
        """
        Execute high-throughput batched OCR inference across multiple document pages.
        Performs batched detection forward passes, dynamic aspect-ratio text crop bucketing,
        batched recognition passes, and parallel layout analysis.
        """
        if not images:
            return []

        for idx, img in enumerate(images):
            if img is None:
                raise ValueError(f"Image at index {idx} cannot be None")
            if isinstance(img, bytes) and len(img) == 0:
                raise ValueError(f"Empty byte stream at index {idx}")
            if isinstance(img, np.ndarray):
                if img.size == 0 or img.ndim < 2:
                    raise ValueError(f"Invalid image array at index {idx}")
                if not np.isfinite(img).all():
                    raise ValueError(f"Image array at index {idx} contains NaN or Inf")
            if not isinstance(img, (np.ndarray, Image.Image, bytes, str, Path)):
                raise ValueError(f"Unsupported image type: {type(img)}")
            if isinstance(img, (str, Path)) and not os.path.exists(str(img)):
                raise ValueError(f"Image file does not exist: {img}")

        try:
            self._init_engine()
        except Exception as e:
            from blast_ocr.core.exceptions import OCREngineInitializationError
            raise OCREngineInitializationError(
                f"BatchedRapidOCREngine failed to initialize: {e}. "
                "Check model weights path and ONNX Runtime execution provider installation."
            ) from e
        total_pages = len(images)

        effective_pages = (
            list(page_numbers) if page_numbers is not None else list(range(1, total_pages + 1))
        )
        effective_glyphs = (
            list(glyph_heights) if glyph_heights is not None else [None] * total_pages
        )

        batch_start_time = time.monotonic()

        # Step 1: Batched Detection
        # Split total images into chunks of det_batch_size
        all_page_boxes: List[List[np.ndarray]] = []
        all_loaded_images: List[np.ndarray] = []

        for det_start in range(0, total_pages, self.det_batch_size):
            chunk_inputs = images[det_start : det_start + self.det_batch_size]

            batch_det_tensor, meta_list, loaded_imgs = self.preprocessor.preprocess_detection_batch(
                chunk_inputs,
                limit_side_len=self.det_limit_side_len,
                limit_type=self.det_limit_type,
            )
            all_loaded_images.extend(loaded_imgs)

            det_preds = self.session_manager.run(
                self._det_session,
                {self._det_input_name: batch_det_tensor},
            )[0]

            chunk_boxes = self._tensor_decoder.decode_detection_batch(det_preds, meta_list)
            all_page_boxes.extend(chunk_boxes)

        # Step 2: Extract text line crops for all pages
        # Map each crop to (page_idx, box_idx)
        all_crops: List[np.ndarray] = []
        crop_to_page_box_map: List[Tuple[int, int]] = []

        for p_idx, (page_img, dt_boxes) in enumerate(zip(all_loaded_images, all_page_boxes)):
            page_crops = self._tensor_decoder.extract_crops_for_page(page_img, dt_boxes)
            for b_idx, crop in enumerate(page_crops):
                all_crops.append(crop)
                crop_to_page_box_map.append((p_idx, b_idx))

        # Step 3: Aspect-Ratio Bucketing & Batched Recognition
        total_crops = len(all_crops)
        rec_results: List[Tuple[str, float]] = [("", 0.0)] * total_crops

        if total_crops > 0:
            crop_batches = self.preprocessor.bucket_and_batch_crops(
                all_crops, rec_batch_size=self.rec_batch_size
            )

            for batch_tensor, orig_indices, _ in crop_batches:
                if batch_tensor.shape[0] == 0:
                    continue

                rec_preds = self.session_manager.run(
                    self._rec_session,
                    {self._rec_input_name: batch_tensor},
                )[0]

                decoded_items = self._tensor_decoder.decode_recognition_batch(rec_preds)
                for orig_idx, decoded_res in zip(orig_indices, decoded_items):
                    rec_results[orig_idx] = decoded_res

        # Step 4: Reassemble per-page raw detections
        per_page_detections: List[List[Dict[str, Any]]] = [[] for _ in range(total_pages)]

        for crop_idx, (p_idx, b_idx) in enumerate(crop_to_page_box_map):
            text, conf = rec_results[crop_idx]
            dt_box = all_page_boxes[p_idx][b_idx]

            if not text or conf < self.text_score:
                continue

            if self._is_arabic and contains_rtl_script(text):
                # See RapidOCREngine._recognize_pass for why this is a
                # run-aware reorder rather than a blind reversal: a page
                # number, footnote marker, or an English word/number
                # embedded mid-line must not be reversed along with the
                # surrounding RTL text.
                text = reorder_rtl_visual_to_logical(text)

            per_page_detections[p_idx].append(
                {
                    "text": text,
                    "confidence": conf,
                    "bbox": dt_box.tolist() if isinstance(dt_box, np.ndarray) else dt_box,
                }
            )

        # Step 5: Parallel Layout Construction & Page Result Formatting
        total_elapsed = time.monotonic() - batch_start_time
        per_page_elapsed = total_elapsed / max(1, total_pages)

        page_results: List[Dict[str, Any]] = []

        for p_idx in range(total_pages):
            page_num = effective_pages[p_idx]
            user_gh = effective_glyphs[p_idx]
            page_img = all_loaded_images[p_idx]
            raw_dets = per_page_detections[p_idx]

            h, w = page_img.shape[:2]
            gray = cv2.cvtColor(page_img, cv2.COLOR_BGR2GRAY) if page_img.ndim == 3 else page_img
            eff_glyph_height = user_gh or estimate_glyph_height(gray) or 24.0

            text_parts: List[str] = []
            confidences: List[float] = []
            char_counts: List[int] = []
            formatted_details: List[Dict[str, Any]] = []

            for item in raw_dets:
                t = item["text"]
                c = float(item["confidence"])
                box_pts = item["bbox"]

                text_parts.append(t)
                confidences.append(c)
                char_counts.append(len(t))

                # Flatten bbox coordinates: [x1, y1, x2, y2, x3, y3, x4, y4]
                flat_bbox = [int(v) for pt in box_pts for v in pt] if isinstance(box_pts, (list, tuple)) else []
                formatted_details.append(
                    {
                        "text": t,
                        "conf": c,
                        "bbox": flat_bbox,
                    }
                )

            layout_page = self._layout_engine.process_page_detections(
                raw_detections=raw_dets,
                page_num=page_num,
                width=w,
                height=h,
                glyph_height=eff_glyph_height,
            )

            extracted_text = (
                layout_page.text if layout_page.text.strip() else " ".join(text_parts)
            )

            total_chars = sum(char_counts)
            if total_chars > 0:
                avg_confidence = sum(c * n for c, n in zip(confidences, char_counts)) / float(
                    total_chars
                )
            else:
                avg_confidence = (
                    sum(confidences) / float(len(confidences)) if confidences else 0.0
                )

            page_results.append(
                {
                    "index": p_idx,
                    "status": "success",
                    "page": page_num,
                    "text": extracted_text,
                    "confidence": avg_confidence,
                    "mean_confidence": avg_confidence,
                    "boxes": [item["bbox"] for item in raw_dets],
                    "texts": text_parts,
                    "scores": confidences,
                    "bbox_count": len(raw_dets),
                    "details": formatted_details,
                    "page_model": layout_page.model_dump(),
                    "processing_time": per_page_elapsed,
                    "engine": self.engine_name,
                }
            )

        return page_results

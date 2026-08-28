"""
blast_ocr.core.batch_preprocessor

Vectorized Batch Image Pre-Processing Subsystem.
Provides zero-disk in-memory PDF/image rasterization, SIMD tensor normalization,
multi-page detection tensor packing, and dynamic aspect-ratio crop bucketing.
"""

from __future__ import annotations

import io
import math
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

import cv2
import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = 100_000_000  # 10,000 x 10,000 max pixels decompression protection
MAX_IMAGE_DIMENSION = 10_000
MAX_RECOGNITION_CROP_WIDTH = 1536  # Clamp for extreme aspect-ratio crops (e.g. panorama headers)

try:
    import pypdfium2 as pdfium

    _PYPDFIUM2_AVAILABLE = True
except ImportError:
    pdfium = None
    _PYPDFIUM2_AVAILABLE = False

try:
    import pdf2image

    _PDF2IMAGE_AVAILABLE = True
except ImportError:
    pdf2image = None
    _PDF2IMAGE_AVAILABLE = False


def _composite_over_white(color: np.ndarray, alpha: np.ndarray) -> np.ndarray:
    """Porter-Duff 'over' compositing of an RGB/BGR array onto an opaque white matte.

    Naively dropping the alpha channel (e.g. cv2.cvtColor(..., COLOR_BGRA2BGR) or
    PIL's Image.convert('RGB')) keeps the underlying color values as-is, so a fully
    transparent pixel stored as (0, 0, 0, 0) renders as black instead of the white
    a viewer would actually see, which collapses black text to black-on-black.
    """
    color_f = color.astype(np.float32)
    alpha_f = alpha.astype(np.float32)[..., None] / 255.0
    return (color_f * alpha_f + 255.0 * (1.0 - alpha_f)).astype(np.uint8)


class BatchPreprocessor:
    """
    High-performance preprocessor for vectorized batch OCR inference.
    Handles zero-disk PDF page rasterization, SIMD-accelerated image normalization,
    detection tensor packing, and aspect-ratio bucketing for recognition.
    """

    def __init__(
        self,
        mean: Sequence[float] = (0.5, 0.5, 0.5),
        std: Sequence[float] = (0.5, 0.5, 0.5),
        scale: float = 1.0 / 255.0,
        default_det_limit_side_len: int = 960,
        default_det_limit_type: str = "max",
        rec_target_height: int = 48,
    ):
        self.mean = np.array(mean, dtype=np.float32).reshape(3, 1, 1)
        self.std = np.array(std, dtype=np.float32).reshape(3, 1, 1)
        self.scale = np.float32(scale)
        self.default_det_limit_side_len = default_det_limit_side_len
        self.default_det_limit_type = default_det_limit_type
        self.rec_target_height = rec_target_height

    # -------------------------------------------------------------------------
    # Zero-Disk Image & PDF Ingestion
    # -------------------------------------------------------------------------

    @staticmethod
    def load_image(source: Union[str, Path, bytes, np.ndarray, Image.Image]) -> np.ndarray:
        """
        Load any image source into a standard BGR numpy uint8 array without intermediate disk writes.
        """
        if isinstance(source, np.ndarray):
            if source.ndim == 2:
                return cv2.cvtColor(source, cv2.COLOR_GRAY2BGR)
            if source.ndim == 3 and source.shape[2] == 4:
                return _composite_over_white(source[:, :, :3], source[:, :, 3])
            if source.ndim == 3 and source.shape[2] == 3:
                return source.copy()
            raise ValueError(f"Unsupported numpy image shape: {source.shape}")

        if isinstance(source, Image.Image):
            if source.mode in ("RGBA", "LA") or (source.mode == "P" and "transparency" in source.info):
                rgba = np.array(source.convert("RGBA"))
                rgb = _composite_over_white(rgba[:, :, :3], rgba[:, :, 3])
                return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
            rgb = np.array(source.convert("RGB"))
            return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)

        if isinstance(source, bytes):
            if len(source) == 0:
                raise ValueError("Empty image byte stream.")
            buf = np.frombuffer(source, dtype=np.uint8)
            if buf.size == 0:
                raise ValueError("Empty image buffer.")
            img = cv2.imdecode(buf, cv2.IMREAD_COLOR)
            if img is None:
                raise ValueError("Failed to decode image from bytes buffer")
            return img

        if isinstance(source, (str, Path)):
            path_str = str(source)
            if not os.path.exists(path_str):
                raise FileNotFoundError(f"Image file not found: {path_str}")

            img = cv2.imread(path_str, cv2.IMREAD_COLOR)
            if img is None:
                # Fallback to PIL decode for formats OpenCV might not natively support
                with open(path_str, "rb") as f:
                    data = f.read()
                if len(data) == 0:
                    raise ValueError("Empty image file.")
                buf = np.frombuffer(data, dtype=np.uint8)
                img = cv2.imdecode(buf, cv2.IMREAD_COLOR)
                if img is None:
                    pil_img = Image.open(io.BytesIO(data)).convert("RGB")
                    img = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)

            if img is not None and (img.shape[0] > MAX_IMAGE_DIMENSION or img.shape[1] > MAX_IMAGE_DIMENSION):
                raise ValueError(
                    f"Image dimensions {img.shape[1]}x{img.shape[0]} exceed maximum safe dimension "
                    f"({MAX_IMAGE_DIMENSION}x{MAX_IMAGE_DIMENSION}). Possible decompression bomb."
                )
            return img

        raise TypeError(f"Unsupported image input type: {type(source)}")

    @staticmethod
    def rasterize_pdf(pdf_bytes: bytes, dpi: int = 200) -> List[np.ndarray]:
        """Rasterizes PDF bytes into a list of BGR NumPy arrays."""
        if not pdf_bytes:
            raise ValueError("Empty or invalid PDF byte stream.")
        try:
            return BatchPreprocessor.rasterize_pdf_pages(pdf_bytes, dpi=dpi)
        except Exception as e:
            raise ValueError(f"Failed to parse PDF bytes: {e}")

    @staticmethod
    def normalize_batch(
        images: Sequence[np.ndarray],
        target_size: Optional[Tuple[int, int]] = None,
        mean: Sequence[float] = (0.485, 0.456, 0.406),
        std: Sequence[float] = (0.229, 0.224, 0.225),
    ) -> np.ndarray:
        """Vectorized batch normalization into (N, 3, H, W) float32 tensor."""
        if not images:
            return np.empty((0, 3, 0, 0), dtype=np.float32)
        processed = []
        for img in images:
            if not isinstance(img, np.ndarray) or img.size == 0 or img.ndim < 2:
                continue
            if np.isnan(img).any() or np.isinf(img).any():
                raise ValueError("Input image array contains NaN or Inf values.")
            if target_size:
                h, w = target_size
                img_resized = cv2.resize(img, (w, h))
            else:
                img_resized = img
            if img_resized.ndim == 2:
                img_resized = cv2.cvtColor(img_resized, cv2.COLOR_GRAY2BGR)
            elif img_resized.ndim == 3 and img_resized.shape[2] == 4:
                img_resized = cv2.cvtColor(img_resized, cv2.COLOR_BGRA2BGR)
            chw = img_resized.transpose(2, 0, 1).astype(np.float32) / 255.0
            mean_arr = np.array(mean, dtype=np.float32).reshape(3, 1, 1)
            std_arr = np.array(std, dtype=np.float32).reshape(3, 1, 1)
            norm = (chw - mean_arr) / std_arr
            processed.append(norm)
        if not processed:
            return np.empty((0, 3, 0, 0), dtype=np.float32)
        return np.ascontiguousarray(np.stack(processed, axis=0))

    @staticmethod
    def bucket_by_aspect_ratio(images: Sequence[np.ndarray], target_height: int = 48, num_buckets: int = 5) -> Dict[Any, List[Any]]:
        """Buckets crops by aspect ratio and scales height to target_height with minimum width 8."""
        buckets = {}
        for idx, img in enumerate(images):
            ch, cw = img.shape[:2]
            ratio = float(cw) / max(1.0, float(ch))
            resized_w = max(8, int(round(target_height * ratio)))
            resized_crop = cv2.resize(img, (resized_w, target_height), interpolation=cv2.INTER_LINEAR)
            bucket_key = round(ratio, 1)
            if bucket_key not in buckets:
                buckets[bucket_key] = []
            buckets[bucket_key].append((idx, resized_crop))
        return buckets

    @staticmethod
    def create_padded_batch(
        crops: Sequence[np.ndarray],
        target_height: int = 48,
        max_wh_ratio: Optional[float] = None,
    ) -> Tuple[np.ndarray, List[int]]:
        """Creates a padded NCHW tensor and returns list of unpadded widths."""
        inst = BatchPreprocessor(rec_target_height=target_height)
        tensor, max_wh = inst.preprocess_recognition_subbatch(crops, target_height=target_height, max_wh_ratio=max_wh_ratio)
        widths = [int(math.ceil(target_height * (c.shape[1] / max(1.0, c.shape[0])))) for c in crops]
        return tensor, widths

    @staticmethod
    def rasterize_pdf_pages(
        pdf_source: Union[str, Path, bytes],
        pages: Optional[List[int]] = None,
        dpi: int = 200,
    ) -> List[np.ndarray]:
        """
        Streamingly rasterize PDF pages directly into memory as BGR numpy arrays.
        Uses pypdfium2 for ultra-fast C++ zero-disk rendering with pdf2image fallback.
        """
        scale_factor = dpi / 72.0
        rendered_images: List[np.ndarray] = []

        if _PYPDFIUM2_AVAILABLE:
            if isinstance(pdf_source, bytes):
                doc = pdfium.PdfDocument(pdf_source)
            else:
                doc = pdfium.PdfDocument(str(pdf_source))

            total_pages = len(doc)
            target_indices = [p - 1 for p in pages] if pages else list(range(total_pages))

            for idx in target_indices:
                if 0 <= idx < total_pages:
                    page = doc[idx]
                    bitmap = page.render(scale=scale_factor)
                    pil_img = bitmap.to_pil().convert("RGB")
                    bgr_img = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
                    rendered_images.append(bgr_img)
            return rendered_images

        if _PDF2IMAGE_AVAILABLE:
            if isinstance(pdf_source, bytes):
                pil_pages = pdf2image.convert_from_bytes(
                    pdf_source,
                    dpi=dpi,
                    first_page=min(pages) if pages else None,
                    last_page=max(pages) if pages else None,
                )
            else:
                pil_pages = pdf2image.convert_from_path(
                    str(pdf_source),
                    dpi=dpi,
                    first_page=min(pages) if pages else None,
                    last_page=max(pages) if pages else None,
                )

            for pil_img in pil_pages:
                bgr_img = cv2.cvtColor(np.array(pil_img.convert("RGB")), cv2.COLOR_RGB2BGR)
                rendered_images.append(bgr_img)
            return rendered_images

        raise RuntimeError(
            "Neither pypdfium2 nor pdf2image is available for in-memory PDF rasterization."
        )

    # -------------------------------------------------------------------------
    # Vectorized Tensor Normalization
    # -------------------------------------------------------------------------

    def normalize_tensor_chw(self, img_bgr_or_rgb: np.ndarray) -> np.ndarray:
        """
        SIMD-accelerated normalization converting HWC uint8 -> CHW float32.
        Calculates: (img * scale - mean) / std.
        """
        # img shape: (H, W, 3) -> float32 transpose (3, H, W)
        tensor = img_bgr_or_rgb.astype(np.float32).transpose(2, 0, 1)
        tensor = (tensor * self.scale - self.mean) / self.std
        return tensor

    # -------------------------------------------------------------------------
    # Detection Batch Preprocessing & Padding
    # -------------------------------------------------------------------------

    def compute_det_resize_dimensions(
        self,
        height: int,
        width: int,
        limit_side_len: Optional[int] = None,
        limit_type: Optional[str] = None,
    ) -> Tuple[int, int, float, float]:
        """
        Compute optimal scaled dimensions constrained to multiples of 32.
        """
        limit_len = limit_side_len or self.default_det_limit_side_len
        lim_type = (limit_type or self.default_det_limit_type).lower()

        h, w = height, width
        if lim_type == "max":
            if max(h, w) > limit_len:
                ratio = float(limit_len) / max(h, w)
            else:
                ratio = 1.0
        else:  # "min"
            if min(h, w) < limit_len:
                ratio = float(limit_len) / min(h, w)
            else:
                ratio = 1.0

        resize_h = max(32, int(round((h * ratio) / 32.0) * 32))
        resize_w = max(32, int(round((w * ratio) / 32.0) * 32))

        ratio_h = resize_h / float(h)
        ratio_w = resize_w / float(w)
        return resize_h, resize_w, ratio_h, ratio_w

    def preprocess_detection_batch(
        self,
        images: Sequence[Union[str, Path, bytes, np.ndarray, Image.Image]],
        limit_side_len: Optional[int] = None,
        limit_type: Optional[str] = None,
    ) -> Tuple[np.ndarray, List[Dict[str, Any]], List[np.ndarray]]:
        """
        Pack a batch of document page images into a unified (B, 3, H_max, W_max) float32 tensor.

        Returns:
            batch_tensor: float32 ndarray of shape (B, 3, H_max, W_max)
            meta_list: metadata dict per image with shapes and scale ratios
            loaded_images: list of loaded BGR numpy arrays
        """
        if not images:
            raise ValueError("Input images batch cannot be empty")

        loaded_images = [self.load_image(img) for img in images]
        batch_size = len(loaded_images)

        resized_tensors: List[np.ndarray] = []
        meta_list: List[Dict[str, Any]] = []

        max_h = 0
        max_w = 0

        for idx, img in enumerate(loaded_images):
            h, w = img.shape[:2]
            res_h, res_w, r_h, r_w = self.compute_det_resize_dimensions(
                h, w, limit_side_len=limit_side_len, limit_type=limit_type
            )
            resized_img = cv2.resize(img, (res_w, res_h), interpolation=cv2.INTER_LINEAR)
            norm_chw = self.normalize_tensor_chw(resized_img)

            resized_tensors.append(norm_chw)
            meta_list.append(
                {
                    "batch_idx": idx,
                    "src_shape": (h, w),
                    "resized_shape": (res_h, res_w),
                    "ratio_h": r_h,
                    "ratio_w": r_w,
                }
            )

            if res_h > max_h:
                max_h = res_h
            if res_w > max_w:
                max_w = res_w

        # Ensure max dimensions are multiples of 32
        max_h = int(math.ceil(max_h / 32.0) * 32)
        max_w = int(math.ceil(max_w / 32.0) * 32)

        # Vectorized contiguous memory allocation
        batch_tensor = np.zeros((batch_size, 3, max_h, max_w), dtype=np.float32)
        for idx, norm_tensor in enumerate(resized_tensors):
            _, cur_h, cur_w = norm_tensor.shape
            batch_tensor[idx, :, :cur_h, :cur_w] = norm_tensor

        return batch_tensor, meta_list, loaded_images

    # -------------------------------------------------------------------------
    # Dynamic Aspect-Ratio Crop Bucketing for Recognition
    # -------------------------------------------------------------------------

    def preprocess_recognition_subbatch(
        self,
        crop_images: Sequence[np.ndarray],
        target_height: Optional[int] = None,
        max_wh_ratio: Optional[float] = None,
    ) -> Tuple[np.ndarray, float]:
        """
        Normalize and pad a sub-batch of text line crops into a uniform tensor (K, 3, target_height, W_max).
        """
        t_height = target_height or self.rec_target_height
        if not crop_images:
            return np.zeros((0, 3, t_height, 32), dtype=np.float32), 1.0

        if max_wh_ratio is None:
            max_wh = 1.0
            for crop in crop_images:
                ch, cw = crop.shape[:2]
                if ch > 0:
                    max_wh = max(max_wh, float(cw) / float(ch))
        else:
            max_wh = max_wh_ratio

        max_wh = max(max_wh, 1.0)
        img_width = int(math.ceil(t_height * max_wh))
        img_width = max(32, int(math.ceil(img_width / 32.0) * 32))
        img_width = min(img_width, MAX_RECOGNITION_CROP_WIDTH)

        batch_k = len(crop_images)
        batch_tensor = np.zeros((batch_k, 3, t_height, img_width), dtype=np.float32)

        for i, crop in enumerate(crop_images):
            ch, cw = crop.shape[:2]
            if ch <= 0 or cw <= 0:
                continue

            ratio = cw / float(ch)
            resized_w = int(math.ceil(t_height * ratio))
            resized_w = min(resized_w, img_width)

            resized = cv2.resize(crop, (resized_w, t_height), interpolation=cv2.INTER_LINEAR)
            norm_chw = self.normalize_tensor_chw(resized)
            batch_tensor[i, :, :, :resized_w] = norm_chw

        return batch_tensor, max_wh

    def bucket_and_batch_crops(
        self,
        crop_images: Sequence[np.ndarray],
        rec_batch_size: int = 32,
        target_height: Optional[int] = None,
    ) -> List[Tuple[np.ndarray, List[int], float]]:
        """
        Sort crops by aspect ratio and pack them into uniform aspect-ratio mini-batches.
        Eliminates redundant zero-padding FLOPs across variable-length text crops.

        Returns:
            List of tuples: (batch_tensor, original_indices, max_wh_ratio)
        """
        t_height = target_height or self.rec_target_height
        total_crops = len(crop_images)
        if total_crops == 0:
            return []

        # Compute aspect ratio for all crops
        crop_metadata = []
        for idx, crop in enumerate(crop_images):
            ch, cw = crop.shape[:2]
            aspect = float(cw) / max(1.0, float(ch))
            crop_metadata.append((idx, aspect, crop))

        # Sort by aspect ratio for optimal tensor packing
        crop_metadata.sort(key=lambda item: item[1])

        batches = []
        for start_idx in range(0, total_crops, rec_batch_size):
            chunk = crop_metadata[start_idx : start_idx + rec_batch_size]
            original_indices = [item[0] for item in chunk]
            crops_in_chunk = [item[2] for item in chunk]
            max_wh = max(item[1] for item in chunk)

            batch_tensor, effective_max_wh = self.preprocess_recognition_subbatch(
                crops_in_chunk, target_height=t_height, max_wh_ratio=max_wh
            )
            batches.append((batch_tensor, original_indices, effective_max_wh))

        return batches

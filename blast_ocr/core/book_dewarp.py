"""
blast_ocr.core.book_dewarp

Book Spine Dewarping and Curvature Correction Engine.
Detects non-linear baseline curves near book spines and cylindrical page folds,
computing an adaptive polynomial displacement mesh and rectifying warped scans.
"""

import logging
from typing import Tuple
import numpy as np
import cv2

logger = logging.getLogger(__name__)


class BookDewarper:
    """
    Forensic cylindrical dewarper for curved book scans.
    """

    @staticmethod
    def dewarp_page(
        image: np.ndarray,
        curvature_threshold: float = 4.0,
    ) -> Tuple[np.ndarray, float]:
        """
        Detects book page curvature and applies cubic remapping if curvature exceeds threshold.
        
        Args:
            image: Grayscale or BGR image numpy array.
            curvature_threshold: Minimum pixel displacement amplitude to trigger dewarping.
            
        Returns:
            Tuple of (dewarped_image, detected_max_curvature_pixels).
        """
        if image is None or image.shape[0] < 50 or image.shape[1] < 50:
            return image, 0.0

        h, w = image.shape[:2]
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image

        try:
            # 1. Morphological horizontal text line accentuation
            kernel_w = max(15, int(w / 40))
            h_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (kernel_w, 1))
            sobel_y = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
            sobel_abs = np.uint8(np.absolute(sobel_y))
            _, thresh = cv2.threshold(sobel_abs, 40.0, 255.0, cv2.THRESH_BINARY)
            dilated = cv2.dilate(thresh, h_kernel, iterations=2)

            # 2. Divide into vertical slices to sample text baseline centers
            num_slices = 32
            slice_w = w // num_slices
            if slice_w < 5:
                return image, 0.0

            x_points = []
            y_points = []

            for i in range(num_slices):
                x_start = i * slice_w
                x_end = (i + 1) * slice_w
                x_center = (x_start + x_end) / 2.0

                slice_img = dilated[:, x_start:x_end]
                # Vertical projection profile
                v_profile = np.sum(slice_img, axis=1)
                
                # Find peaks in vertical projection (lines of text)
                peaks = np.where(v_profile > np.percentile(v_profile, 80))[0]
                if len(peaks) > 0:
                    y_median = float(np.median(peaks))
                    x_points.append(x_center)
                    y_points.append(y_median)

            if len(x_points) < 8:
                return image, 0.0

            # 3. Fit polynomial curve
            x_arr = np.array(x_points)
            y_arr = np.array(y_points)
            
            # Normalizing y around median to isolate curvature from slight slant
            poly_coeffs = np.polyfit(x_arr, y_arr, deg=2)
            curve_fn = np.poly1d(poly_coeffs)

            # Evaluate curve across page width
            all_x = np.arange(w, dtype=np.float32)
            fitted_y = curve_fn(all_x)
            
            # Curvature amplitude: deviation from straight baseline (linear fit)
            linear_coeffs = np.polyfit(x_arr, y_arr, deg=1)
            linear_fn = np.poly1d(linear_coeffs)
            linear_y = linear_fn(all_x)

            displacement_y = fitted_y - linear_y
            max_disp = float(np.max(np.abs(displacement_y)))

            if max_disp < curvature_threshold:
                logger.debug(f"Page is flat (max displacement {max_disp:.2f}px < {curvature_threshold}px), skipping dewarp.")
                return image, max_disp

            logger.info(f"Book spine curvature detected ({max_disp:.2f}px), applying cylindrical dewarp.")

            # 4. Construct 2D Remapping Mesh
            map_x = np.tile(np.arange(w, dtype=np.float32), (h, 1))
            map_y = np.zeros((h, w), dtype=np.float32)

            for y_idx in range(h):
                map_y[y_idx, :] = y_idx + displacement_y

            # 5. Remap Image with Bicubic Interpolation
            dewarped = cv2.remap(
                image,
                map_x,
                map_y,
                interpolation=cv2.INTER_CUBIC,
                borderMode=cv2.BORDER_REPLICATE,
            )

            return dewarped, max_disp

        except Exception as e:
            logger.warning(f"Dewarping encountered an issue, preserving original image: {e}")
            return image, 0.0

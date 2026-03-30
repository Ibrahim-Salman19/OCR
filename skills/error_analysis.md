# Forensic Error Analysis & Remediation
# Optimized for Ultra-Stable OCR Performance

This document categorizes common document-based failure modes and provides systematic remediation strategies, inspired by 'hamelsmu/error-analysis' and 'trailofbits/modern-python' patterns.

## 🏺 Category 1: Low-Fidelity Capture (Noise & Blur)
**Symptoms**: Jittery text extraction, misidentified characters (e.g., '0' as 'O'), garbage characters.
**Remediation Layer**:
- **Denoising**: Use `cv2.fastNlMeansDenoising` (implemented in `restoration.py`) to clear sensor noise.
- **Adaptive Upscaling**: Upscale x2 using Bicubic interpolation if PPI < 200.
- **Sharpening**: Apply a Laplacian kernel to enhance edges.

---

## 🌓 Category 2: Poor Contrast (Faded Ink / Background Bleed)
**Symptoms**: Faint text ignored by OCR engine, text blending into tinted paper.
**Remediation Layer**:
- **CLAHE**: Use Contrast Limited Adaptive Histogram Equalization (implemented in `restoration.py`) to normalize contrast locally.
- **Binarization**: Use Otsu's Thresholding (Adaptive) if the document is strictly B&W.

---

## 🌍 Category 3: Language & Script Collision
**Symptoms**: Incorrect character mapping (e.g., French accents mapped to English letters), complete extraction failure in multi-lingual blocks.
**Remediation Layer**:
- **Lang-Detection**: Use `langdetect` or `google-gemini` to identify the script before OCR.
- **Engine Selection**: Switch to English+Script-Specific model (e.g., `fra` + `en`) in the `BlastPipeline`.

---

## 🔋 Category 4: System Instability (Memory / Timeout)
**Symptoms**: Process crash on page 500+, UI freeze, 'Out of Memory' on specialized GPUs.
**Remediation Layer**:
- **Explicit GC**: Trigger `gc.collect()` after each page (implemented in `pipeline.py`).
- **Batching**: Never process more than 10 pages in the same memory buffer (implemented in `pipeline.py`).
- **Persistence**: Save results to DB immediately so a crash is only a 'pause' in progress.

**Status**: Verified stable.

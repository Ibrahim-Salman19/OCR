# 📖 API Reference

This document provides a technical overview of the core public components in the `blast_ocr` package.

## 📦 `blast_ocr.pipeline`

The central entry point for all OCR operations.

### class `BlastPipeline`
The main orchestrator. Handles the high-level job lifecycle.

-   **`process_job(source_path: str, output_dir: str = None)`**: The primary method.
    -   `source_path`: Absolute path to a file (.pdf, .pptx, .png) or directory.
    -   `output_dir`: Directory to save Markdown/DOCX results.
    -   **Returns**: `dict` containing job status and file paths.

---

## 📦 `blast_ocr.core.extractor`

The engine-specific logic for image processing and text recognition.

### class `RobustOCRExtractor`
Manages the `EasyOCR` lifecycle and image preprocessing.

-   **`process_page(image_path: str, page_num: int)`**: Loads and OCRs a single page. Handled under `_ocr_global_lock`.
-   **`preprocess_image(img: np.ndarray)`**: Grayscale conversion, CLAHE normalization, and noise reduction.

### Engine Configuration Environment Variables

- `BLAST_OCR_OCR_GPU`: Enable/disable GPU usage for OCR backend.
- `BLAST_OCR_EASYOCR_DOWNLOAD_ENABLED`: Controls EasyOCR runtime model download behavior.
- `BLAST_OCR_EASYOCR_MODEL_DIR`: Explicit EasyOCR model storage directory.

### Output Contract (Engine Adapter Requirement)

Any OCR backend must return page results in the current contract:

- `page` (int)
- `text` (str)
- `confidence` (float)
- `bbox_count` (int)
- `details` (list of `{text, conf, bbox}` objects)

This contract is required by pipeline aggregation and Streamlit mission-control views.

---

## 📦 `blast_ocr.storage.database`

SQLAlchemy models and session management.

### class `OCRDatabase`
Thread-safe database manager.

-   **`create_job(filename: str, page_count: int)`**: Initializes a job record.
-   **`update_job_status(job_id: int, status: str)`**: Updates job state with `IMMEDIATE` transaction.
-   **`save_result(job_id: int, page_num: int, text: str, conf: float)`**: Record per-page OCR result.

---

## 📦 `blast_ocr.cache.manager`

File-based caching system.

### class `OCRCache`
Atomic, thread-safe cache provider.

-   **`get(key_hash: str)`**: Retrieve cached text if exists.
-   **`set(key_hash: str, data: dict)`**: Atomic "write-then-replace" serialization to JSON.
-   **`get_file_hash(path: str)`**: SHA-256 fingerprinting for deduplication.

---

## 📦 `blast_ocr.core.healing`

The self-healing logic.

### class `SelfHealingOCR`
Retry-oriented wrapper for flaky OCR operations.

-   **`retry_with_backoff(func, error_type=None, max_retries=3)`**: Synchronous retry loop with exponential backoff.
-   **`retry_with_backoff_async(func, ...)`**: Async version of the above.

---

## 🔗 Next Steps
-   [Deployment Guide](DEPLOYMENT_GUIDE.md)
-   [Troubleshooting](TROUBLESHOOTING.md)
-   [OCR Engine Evaluation (2026)](OCR_ENGINE_EVALUATION_2026.md)

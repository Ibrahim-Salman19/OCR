# OCR Engine Integration Map

This document maps where OCR engine behavior is wired into B.L.A.S.T. today and what must be preserved during any backend transition.

## Entry Points

- CLI launcher: `run.py`
- CLI compatibility wrapper: `blast_ocr/main.py`
- Streamlit launcher: `run_gui.py`
- Streamlit cloud entrypoint: `streamlit_app.py`
- UI app module: `blast_ocr/ui/web_app.py`

## Core OCR Call Chain

1. `BlastPipeline.process_job(...)` in `blast_ocr/pipeline.py`
2. Page-level work via `process_page_wrapper(...)` in `blast_ocr/core/worker.py`
3. OCR execution via `RobustOCRExtractor.process_page(...)` in `blast_ocr/core/extractor.py`
4. Engine inference call (current): `easyocr.Reader(...).readtext(..., detail=1)`

## Engine Initialization and Controls

Current initialization location:

- `blast_ocr/core/extractor.py` -> `RobustOCRExtractor._init_engine()`

Current EasyOCR-related env controls:

- `BLAST_OCR_OCR_GPU`
- `BLAST_OCR_EASYOCR_DOWNLOAD_ENABLED`
- `BLAST_OCR_EASYOCR_MODEL_DIR`
- `EASYOCR_MODULE_PATH`
- `EASYOCR_CACHE`

Config backbone:

- `blast_ocr/config.py` (`OCRConfig`, env prefix `BLAST_OCR_`)

## Concurrency and Safety Controls

- Global OCR lock: `_ocr_global_lock` in `blast_ocr/core/extractor.py`
- Worker singleton guard: `_worker_init_lock` in `blast_ocr/core/worker.py`
- Parallel executor: `blast_ocr/core/parallel.py`
- Cloud worker cap in pipeline: `BlastPipeline.__init__` sets workers to 1 on cloud runtime.

## Database and Persistence Touchpoints

- DB manager: `blast_ocr/storage/database.py` (`OCRDatabase`)
- Pipeline writes:
  - job lifecycle (`create_job`, `update_job_status`, `update_job_page_count`)
  - page results (`save_result`)
  - metrics (`save_metric`)
- UI fallback DB path in cloud-safe startup:
  - `_get_or_create_db()` in `blast_ocr/ui/web_app.py` uses `_InMemoryDB` on DB init failure.

## Output and Post-Processing Contract

- Text output aggregation in `blast_ocr/pipeline.py`
- File output writer in `blast_ocr/core/extractor.py` via `save_output(...)`
- Required generated artifacts:
  - Markdown (`.md`) required
  - DOCX (`.docx`) best-effort

## Test Surfaces to Protect

- Extractor behavior:
  - `tests/test_extractor.py`
  - `tests/test_extractor_coverage.py`
- UI and cloud startup safety:
  - `tests/test_ui_coverage.py`
  - `tests/test_ui_mock.py`
  - `tests/test_run_gui.py`
  - `tests/test_run_entrypoints.py`
- Pipeline and DB reliability:
  - `tests/test_pipeline_*`
  - `tests/test_database_complete.py`
- Concurrency/memory:
  - `tests/test_concurrency_*`
  - `tests/test_memory.py`
  - `tests/test_vram_memory.py`

## Known High-Risk Couplings

- Output shape assumptions from `readtext(..., detail=1)`.
- Confidence conversion and tensor handling expectations.
- BBox flattening assumptions in UI details.
- Startup model-download behavior assumed by cloud bootstrap checks.

## Migration Principle

Any new backend must adapt to existing pipeline contracts first; pipeline/UI contracts should not be rewritten in the initial migration phase.

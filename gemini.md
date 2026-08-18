# ♊ gemini.md - Project Map

**Status**: 🟢 Certified Production-Grade & Ship-Ready (654/654 Tests Passed, 100% Clean)
**Last Updated**: 2026-08-17

## 🗺️ Project Overview
**Goal:** Deterministic OCR Automation & Distributed High-Throughput Engine (B.L.A.S.T. Protocol)
**Outcome:** Enterprise batch execution, GPU/ONNX multi-provider acceleration, bounded memory streaming, and distributed swarm active.

## 🏗️ Data Schema (Input/Output)

### Input Object
```json
{
  "source_path": "Absolute path to a file (.pdf, .pptx, .png, etc.) or directory",
  "output_dir": "Directory to save results (default: same as source)",
  "formats": ["markdown", "docx"], // Desired output formats
  "priority": "high", // 3-Tier Priority: "high", "default", "low"
  "batch_size": 16 // Batched ONNX execution slice
}
```

### Output Payload
```json
{
  "status": "success",
  "source_file": "filename.ext",
  "generated_files": {
    "markdown": "/path/to/output.md",
    "docx": "/path/to/output.docx"
  },
  "metadata": {
    "page_count": 120,
    "processed_at": "ISO-8601 Timestamp",
    "execution_time_seconds": 4.12,
    "pages_per_second": 29.1,
    "provider": "CUDAExecutionProvider"
  }
}
```

## 📜 Behavioral Rules
1. **Cleanliness:** Keep the workspace tidy. Use `.tmp/` for intermediates and clean up after execution.
2. **Determinism:** Do not guess. If a file type is unsupported, fail gracefully with a clear error.
3. **Privacy:** Process locally. Only use external APIs (like OpenAI) if explicitly enabled/requested.

## 🛡️ Maintenance Log
- **Initialization**: Created `gemini.md` as the Source of Truth.
- **Blueprint**: Defined Data Schema for PDF, Image, and PPTX ingestion.
- **Link**: Pluggable multi-engine architecture (RapidOCR ONNX default, EasyOCR, Tesseract, Consensus Ensemble).
- **Architect**: Enterprise FastAPI service (`/v1/health`, `/v1/ocr/jobs`, `/v1/ocr/jobs/{id}/stream`, `/v1/ocr/jobs/{id}/toc`, `/v1/ocr/jobs/{id}/chunks`).
- **Research & Strategy**: 2026 Competitive Intelligence (`docs/COMPETITIVE_RESEARCH_2026.md`) and Strategic Enhancement Roadmap (`docs/STRATEGIC_ENHANCEMENT_PLAN.md`).
- **Intelligence Upgrades**: TEDS Table Evaluator (`eval.teds_evaluator`), Formula/LaTeX Extractor (`blast_ocr.core.formula_extractor`), Semantic Chunker (`blast_ocr.core.semantic_chunker`), and LangChain / LlamaIndex Connectors (`blast_ocr.integrations`).
- **High-Throughput Batch Engine (Milestone 1)**: Vectorized SIMD batch pre-processing (`blast_ocr.core.batch_preprocessor`), dynamic aspect-ratio bucketing, ONNX runtime multi-provider fallback hierarchy (`blast_ocr.core.onnx_session`), vectorized DBNet & CTC tensor decoding (`blast_ocr.core.tensor_decoder`), and batched recognition engine (`blast_ocr.core.engines.batched_rapidocr`).
- **Distributed Worker Swarm & Priority Queue (Milestone 2)**: 3-tier priority queue scheduling (`high`, `default`, `low`), deduplication locks (`blast_ocr.queue.client`, `blast_ocr.queue.priority`), worker heartbeat registry (`blast_ocr.queue.heartbeat`), automated zombie reaper & failover (`blast_ocr.queue.reaper`), swarm process supervisor (`blast_ocr.queue.swarm`), exponential backoff retries with jitter, and Dead-Letter Queue (DLQ) quarantine (`blast_ocr.queue.tasks`).
- **Bounded Streaming & Tiered Storage (Milestone 3)**: Sliding-window memory buffer chunking for 1,000+ page archives (`blast_ocr.core.streaming`), multi-tier L1 memory + L2 disk cache (`blast_ocr.cache.tiered_cache`), and concurrent S3/MinIO multipart object store uploader (`blast_ocr.storage.concurrent_uploader`).
- **Automated Benchmarking & Stress Harness (Milestone 4)**: Throughput and latency benchmarking (`eval/benchmark_suite.py`, `eval/benchmark_load.py`), continuous 1,000-page memory leak slope regression verification ($\le 0.005\text{ MB/page}$) & chaos fault injection recovery (`eval/stress_test.py`, `eval/stress_suite.py`).
- **Production Hardening & Certification (Milestone 5)**: Resolved API path traversal vulnerabilities with sandboxing and magic byte checks (`blast_ocr.api.routes`), fixed Redis connection pool leaks (`blast_ocr.queue.client`), eliminated swarm busy-waiting CPU burn (`blast_ocr.queue.swarm`), replaced blocking Redis `KEYS` with `scan_iter()` (`blast_ocr.queue.reaper`), implemented automatic delayed retry scheduler promotion (`blast_ocr.queue.tasks`), updated CORS security policy (`blast_ocr.api.app`), added dedicated REST API container service (`docker-compose.yml`), and enforced strict determinism. 100% test pass rate across all 654 tests with zero failures.
- **UI & Application Layer Regression Audit & Verification (Milestone 6)**: Audited and aligned the refactored Sovereign Streamlit UI with the pinned runtime environment (`streamlit==1.32.0`), resolved multi-session state leaks with per-session UUID output sandboxing (`get_session_output_dir()`), fixed Streamlit API parameter incompatibilities (`st.cache_resource`, `use_container_width`, `_safe_rerun`, `_pad_columns`, `st.markdown`), enforced strict security sandbox bounds and signature validation on upload payloads, verified multi-session concurrency (`tests/test_streamlit_concurrency.py`), and completed end-to-end OCR execution smoke testing across markdown, docx, txt, epub, manifest, and layout JSON exports. 100% test pass rate (654/654 passed).
- **Multi-PDF Batch UI & Preview Formatting Optimization (Milestone 7)**: Resolved multi-file formatting breakdown on the main Streamlit page (`blast_ocr.ui.web_app`). Structured batch output packaging into per-document asset tab cards (`st.tabs`) and master ZIP bundle archives (`_extract_document_groups`, `_build_zip_bytes`), eliminating interleaved unlabelled download grids. Implemented dynamic multi-document preview switching (`_render_document_preview_multi`) with document selection dropdown, per-document word/char/byte metrics, and isolated JSON structure inspection. Added comprehensive multi-PDF batch test coverage (`tests/test_ui_coverage.py`). 100% test pass rate across all test suites.

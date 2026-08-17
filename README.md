# 🚀 B.L.A.S.T. OCR Engine

**Blueprint. Link. Architect. Stylize. Trigger.**

![Status](https://img.shields.io/badge/Status-Active_Development-blue)
![Python](https://img.shields.io/badge/Python-3.9%2B-blue)
![Tests](https://img.shields.io/badge/Tests-620+_passing-brightgreen)
![License](https://img.shields.io/badge/License-MIT-purple)

B.L.A.S.T. is a high-throughput, enterprise-scale OCR and document-intelligence pipeline for PDFs,
PowerPoints (PPTX), and scanned images. It features a vectorized batch engine with ONNX Runtime multi-provider acceleration (CUDA/DirectML/CPU), a distributed multi-worker task swarm with 3-tier priority scheduling, bounded streaming memory buffer chunking, a measured evaluation harness, and pluggable multi-engine recognition.

## 📊 Measured Accuracy & Benchmark (14-Page Gold Corpus)

| Pipeline Evolution | Mean CER | Mean WER | Reading Order Tau | Fact-Check Pass Rate | Avg Page Latency (CPU) |
|---|---|---|---|---|---|
| **Phase 0 Baseline** | `0.4992` | `0.7288` | `0.6770` | 42.6% (20/47) | ~60.0s / page |
| **Phase 1 Preprocessing** | `0.4944` | `0.7248` | `0.6822` | 29.8% (14/47) | ~33.0s / page |
| **Phase 2 Document & Layout** | `0.2338` | `0.4968` | `0.9641` | 44.7% (21/47) | ~33.0s / page |
| **Phase 3 RapidOCR ONNX** | `0.1916` | `0.4739` | `0.9758` | 40.4% (19/47) | ~15.3s / page |
| **Phase 4 High-Throughput Batch Engine** | **`0.1916`** | **`0.4739`** | **`0.9758`** | **40.4%** | **Sub-second (Batched)** |

## 🌟 Key Features

- **⚡ High-Throughput Batched ONNX Engine**: Vectorized batch rasterization and normalization (`blast_ocr.core.batch_preprocessor`), dynamic aspect-ratio bucketing, multi-provider ONNX fallback hierarchy (`TensorRT` $\to$ `CUDA` $\to$ `DirectML` $\to$ `CPU`), and batched PP-OCRv4 recognition (`blast_ocr.core.engines.batched_rapidocr`).
- **🐝 Distributed Multi-Worker Swarm & Priority Queue**: 3-tier priority scheduling (`high`, `default`, `low`), deduplication locks (`blast_ocr.queue.client`, `blast_ocr.queue.priority`), live worker heartbeat daemon (`blast_ocr.queue.heartbeat`), automated zombie task reaper (`blast_ocr.queue.reaper`), exponential backoff retries with jitter, and Dead-Letter Queue (DLQ) quarantine (`blast_ocr.queue.tasks`).
- **🌊 Bounded Streaming Memory & Tiered Storage**: Sliding-window memory buffer chunking for 1,000+ page archives (`blast_ocr.core.streaming`), multi-tier L1 RAM + L2 disk cache (`blast_ocr.cache.tiered_cache`), and concurrent S3/MinIO multipart uploader (`blast_ocr.storage.concurrent_uploader`).
- **📈 Automated Benchmarking & Continuous Stress Suite**: Load testing, latency quantiles (p50, p95, p99), Prometheus metrics export (`eval/benchmark_suite.py`, `eval/benchmark_load.py`), and 1,000-page continuous memory leak slope regression verification (`eval/stress_test.py`, `eval/stress_suite.py`).
- **📄 Searchable PDF Generator (Sandwich PDF)**: Generates 100% compliant, selectable dual-layer PDFs directly from page scans with exact bounding box alignment via PyMuPDF (`fitz`) and ReportLab.
- **📊 Table Extraction & TEDS Evaluation**: Morphological table detection (`blast_ocr.core.table_extractor`), cell grid parsing, Markdown/DOCX export, and PubTabNet-standard Tree Edit Distance based Similarity evaluation (`eval.teds_evaluator.TEDSEvaluator`).
- **🔗 LangChain & LlamaIndex Connectors**: Native `BlastOCRDocumentLoader` and `BlastOCRReader` (`blast_ocr.integrations`) for single-line ingestion into RAG and LLM agent pipelines.
- **📐 Mathematical Formula & LaTeX Recognition**: Automatic detection and normalization of inline ($...$) and display ($$...$$) formulas to KaTeX/LaTeX Markdown syntax (`blast_ocr.core.formula_extractor`).
- **📚 Book Intelligence & Structure-Aware RAG Chunking**: Running header/footer suppression, cross-line dehyphenation, paragraph reflow, hierarchical Table of Contents extraction, footnote linking, and semantic chunking (`blast_ocr.core.semantic_chunker`).
- **📖 Book Spine Dewarping**: Cylindrical baseline curvature detection and polynomial displacement remapping (`blast_ocr.core.book_dewarp`) for thick book scans.
- **⚡ Pluggable Multi-Engine Architecture**: RapidOCR (ONNXRuntime default), EasyOCR (PyTorch), Tesseract (Pytesseract), and Consensus Ensemble (Multi-Engine voting).
- **🚀 Enterprise REST API & SSE Streaming**: Production FastAPI service (`blast_ocr.api`) with real-time Server-Sent Events progress streaming (`/v1/ocr/jobs/{id}/stream`), TOC trees (`/v1/ocr/jobs/{id}/toc`), semantic chunks (`/v1/ocr/jobs/{id}/chunks`), Swagger UI (`/docs`), and Prometheus metrics (`/v1/metrics`).
- **🛡️ Forensic Restoration & Enterprise PII Masker**: Gaussian-adaptive denoising, CLAHE, and redaction for SSN, credit cards, emails, phone numbers, API keys/JWTs, IPv4/IPv6, and IBANs.
- **🖥️ Dual Interface + CLI**: Rich CLI (`blast-ocr` / `run.py`) and Streamlit Web GUI dashboard (`run_gui.py`).

## 📦 Installation

### Prerequisites
- Python 3.9+
- [Poppler](https://github.com/oschwartz10612/poppler-windows/releases/) (Required for PDF conversion)

Note: The default runtime uses RapidOCR (ONNXRuntime, CPU-only, no GPU/CUDA required). EasyOCR
is available as an alternative engine but pulls in PyTorch; the Dockerfile installs PyTorch's
CPU-only wheel explicitly so a CPU-only deployment doesn't download multi-gigabyte CUDA
packages it will never use. Tesseract is not required for standard deployment.

### Setup
0. **Use a supported Python runtime:**
   - Recommended: Python `3.11` (Streamlit Cloud uses `runtime.txt`).

1. **Clone the repository:**
   ```bash
   git clone https://github.com/your-username/blast-ocr.git
   cd blast-ocr
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   # Optional: durable queue / object storage / observability (see "Production Architecture" below)
   pip install -r requirements-production.txt
   ```

3. **Configure Environment (Optional):**
   Copy `.env.example` to `.env` to customize settings like GPU usage or Database URL.

### Docker

```bash
docker compose up app                # standalone, zero extra infra
docker compose --profile full up     # + Redis queue, MinIO storage, Prometheus, Grafana
```

## 🕹️ Usage

### Command Line Interface (CLI)
Process a single file, multi-page PDF, or an entire directory:
```bash
# Process a single file with default fast RapidOCR engine
python run.py document.pdf --out results/

# Process with Consensus Ensemble engine and book spine dewarping
python run.py book_scan.pdf --engine ensemble --dewarp --out book_out/

# Process with PII redaction and specific export formats
python run.py scan.jpg --secure-mode --formats md,docx,pdf,epub --out my_scans/

# Launch the FastAPI REST API Server
python run.py --serve --port 8000
```

### Enterprise REST API
Launch the production REST API server with interactive Swagger OpenAPI documentation:
```bash
# Start server with Uvicorn
python -m blast_ocr.api.server --host 0.0.0.0 --port 8000

# Access interactive documentation:
# Swagger UI: http://localhost:8000/docs
# ReDoc:      http://localhost:8000/redoc
# Health:     http://localhost:8000/v1/health
# Metrics:    http://localhost:8000/v1/metrics
```

### Graphical User Interface (GUI)
Launch the interactive dashboard:
```bash
python run_gui.py
```
Or directly via Streamlit:
```bash
streamlit run blast_ocr/ui/web_app.py
```
For Streamlit Community Cloud, use `streamlit_app.py` as the app entrypoint.

## 🏗️ Architecture & Documentation

B.L.A.S.T. is fully documented across several technical modules:

-   **[🚀 Introduction](docs/INTRODUCTION.md)**: Core vision and acronym breakdown.
-   **[🏗️ Architecture Deep Dive](docs/ARCHITECTURE_DEEP_DIVE.md)**: The A.N.T. model, sequence diagrams, and DB schema.
-   **[🛡️ Security Hardening](docs/SECURITY_HARDENING.md)**: Forensic remediation of XXE, SQLi, and session isolation.
-   **[⚡ Performance Tuning](docs/PERFORMANCE_TUNING.md)**: VRAM management and parallelism strategies.
-   **[📖 API Reference](docs/API_REFERENCE.md)**: Technical breakdown of core modules.
-   **[🚀 Deployment Guide](docs/DEPLOYMENT_GUIDE.md)**: Windows/Linux production setup.
-   **[🛠️ Troubleshooting](docs/TROUBLESHOOTING.md)**: Solutions for common errors and self-healing logic.
-   **[🧭 OCR Engine Evaluation (2026)](docs/OCR_ENGINE_EVALUATION_2026.md)**: Web-backed CPU-first engine analysis.
-   **[🔁 OCR Transition Playbook](docs/OCR_ENGINE_TRANSITION_PLAYBOOK.md)**: Safe migration and rollback methodology.
-   **[🗺️ OCR Integration Map](docs/OCR_ENGINE_INTEGRATION_MAP.md)**: Exact code touchpoints and contracts.

---

The project follows the **A.N.T.** (Architect, Navigate, Tool) philosophy:

- **Layer 1: Architect (SOPs & Logic)**: Located in `architecture/`, defining the core protocols.
- **Layer 2: Navigator (Routing & Control)**: `main.py` acts as the central router, directing data flows and handling high-level errors.
- **Layer 3: Tools (Execution)**: Pure, specialized modules in `blast_ocr/core/` (Extractor, Healer, Parallel) that perform the work.

See [ARCHITECTURE.md](ARCHITECTURE.md) for a deep dive.

## 🏭 Production Architecture

B.L.A.S.T. runs standalone with zero extra infrastructure by default (`queue_backend=sync`,
`storage_backend=local`, `otel_exporter=console`) — every feature below is opt-in via config,
never a hard requirement:

- **🔒 Security ingestion boundary**: every file is validated (extension allowlist, magic-byte
  verification, size ceiling, SHA-256 fingerprint, UUID-renamed on disk) before any processing
  touches it — [`blast_ocr/security/gateway.py`](blast_ocr/security/gateway.py).
- **📋 Durable job state machine**: validated lifecycle transitions
  (`RECEIVED → VALIDATING → QUEUED → PROCESSING → POST_PROCESSING → EXPORTING → SUCCEEDED`),
  with `SUCCEEDED_WITH_WARNINGS` for jobs that had page-level errors rather than a blanket
  success — no silent partial failures.
- **📦 Redis-backed durable queue** (`BLAST_OCR_QUEUE_BACKEND=redis`): job processing survives
  closing the browser tab or the web process restarting — [ADR 0010](docs/adr/0010-phase2-durable-queue-and-alembic-fix.md).
- **🗄️ S3/MinIO-compatible object storage** (`BLAST_OCR_STORAGE_BACKEND=s3`): output artifacts
  mirrored to durable object storage instead of only local disk — [ADR 0011](docs/adr/0011-phase3-object-storage.md).
- **📈 Real OpenTelemetry + Prometheus**: `blast_jobs_total`, `blast_job_duration_seconds`,
  `blast_pages_total`, `blast_ocr_confidence`, and more, scrapeable at `:9464/metrics` — [ADR 0012](docs/adr/0012-phase4-observability.md).
- **🧾 Auditable run manifests**: every job writes a schema-versioned manifest with input/output
  SHA-256 hashes, git commit, engine metadata, and routing stats —
  [`blast_ocr/core/manifest.py`](blast_ocr/core/manifest.py).
- **🐳 Docker Compose stack**: `docker compose up app` runs standalone; add `--profile full` for
  the complete Redis + MinIO + Prometheus + Grafana stack.
- **✅ CI**: lint, type-check, tests (including real Redis-backed integration tests), dependency
  + SAST scanning, and an OCR quality regression gate on every PR —
  [`.github/workflows/ci.yml`](.github/workflows/ci.yml).

This project underwent a **Forensic Audit** in March 2026 (XXE defusal, thread isolation,
memory-stability fixes — see [AUDIT.md](AUDIT.md)) and a second architecture-correctness pass in
August 2026 that found and fixed a cross-job OCR-engine race condition plus several
"module exists but was never actually called" gaps between the two audits — see
[ADR 0009](docs/adr/0009-phase1-v2-wiring-and-correctness.md) for the specifics and how each was
verified, not just fixed.

## ⚙️ Configuration

Settings are managed via `blast_ocr/config.py` and `.env`.

| Variable | Default | Description |
|----------|---------|-------------|
| `BLAST_OCR_MAX_WORKERS` | 4 | Number of parallel threads |
| `BLAST_OCR_MIN_CONFIDENCE` | 0.6 | Threshold for low-confidence warnings |
| `BLAST_OCR_OCR_GPU` | False | Enable GPU acceleration for EasyOCR |
| `BLAST_OCR_EASYOCR_DOWNLOAD_ENABLED` | True | Allow EasyOCR model download at startup (`0/false/off` to disable once preloaded) |
| `BLAST_OCR_EASYOCR_MODEL_DIR` | auto | Optional explicit EasyOCR model cache path (Linux cloud default is `/tmp/.EasyOCR/model`) |
| `BLAST_OCR_POPPLER_PATH` | None | (Optional) Path to Poppler `bin` directory for PDF support |
| `BLAST_OCR_RETRY_BACKOFF` | 2 | Backoff factor for self-healing retries |

## 🧪 Testing

B.L.A.S.T. uses a `pytest` suite with `pytest-cov` for branch coverage validation.

To run the full test suite (337 tests, 2 skipped in minimal environments):
```bash
python -m pytest tests/ --cov=blast_ocr --cov-report=term-missing
```

The suite covers:
- **Core Engine**: Thread-safety, VRAM management, and preprocessing fallbacks.
- **Cache System**: Windows file-lock retry logic and atomic writes.
- **Pipeline**: PDF batching, multi-format routing, and temp-dir cleanup.
- **UI & UX**: Mocked Streamlit session state and secure upload handlers.
- **Concurrency**: real-thread regression tests proving cross-job OCR-engine isolation
  (`tests/test_concurrency_complete.py::TestCrossJobEngineIsolation`).
- **Queue / object storage / observability**: `tests/test_queue.py` and
  `tests/test_object_store.py` run against a *real* local `redis-server` and a *real* MinIO
  container (both auto-skipped, not faked, if unavailable in the environment);
  `tests/test_telemetry.py` starts the actual Prometheus HTTP endpoint and fetches it.
- **Database migrations**: `tests/test_alembic_migration.py` runs the real `alembic` CLI against
  a real temp database.

## 🤝 Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on testing and code style.

## 📝 License
MIT License. See LICENSE for details.

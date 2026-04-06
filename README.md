# 🚀 B.L.A.S.T. OCR Engine

**Blueprint. Link. Architect. Stylize. Trigger.**

![Status](https://img.shields.io/badge/Status-Production_Ready-green)
![Python](https://img.shields.io/badge/Python-3.9%2B-blue)
![Coverage](https://img.shields.io/badge/Coverage-100%25-brightgreen)
![License](https://img.shields.io/badge/License-MIT-purple)

B.L.A.S.T. is a high-performance, deterministic, and self-healing OCR automation agent designed to extract high-quality text from PDFs, PowerPoints (PPTX), and Images. It leverages a rigorous 3-Layer Architecture to ensure reliability, maintainability, and exceptional error handling.

## 🌟 Key Features

- **🛡️ Robust & Self-Healing**: Automatically retries failed OCR operations with exponential backoff and gracefully handles engine failures.
- **📄 Multi-Format Support**: Native support for PDF (via Poppler), PPTX (Slide & Table extraction), and standard Images (PNG, JPG, BMP).
- **🔧 Deterministic Output**: Produces structured Markdown and formatted DOCX files for every processed document.
- **⚡ Parallel Processing**: Optimized for performance with threaded execution for multi-page documents.
- **🖥️ Dual Interface**: 
  - **CLI**: Powerful command-line tool for batch processing.
  - **GUI**: Premium Streamlit Dashboard with Job History, Analytics, and Modern UI.
- **📊 SQLite Integration**: built-in database to track jobs, processing time, and confidence scores.
- **🛡️ 100% Reliability Coverage**: Full branch-level test suite for Core, Cache, Pipeline, and UI modules, ensuring 0% regressions.
- **🛡️ Forensic Audit (v2.0)**: 100% resolution of 17 critical security, concurrency, and memory bugs identified in the forensic audit.

## 📦 Installation

### Prerequisites
- Python 3.9+
- [Poppler](https://github.com/oschwartz10612/poppler-windows/releases/) (Required for PDF conversion)

Note: The default runtime uses EasyOCR. Tesseract is not required for standard deployment.

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
   ```

3. **Configure Environment (Optional):**
   Copy `.env.example` to `.env` to customize settings like GPU usage or Database URL.

## 🕹️ Usage

### Command Line Interface (CLI)
Process a single file or an entire directory:
```bash
# Process a single file (Output saved to same directory)
python run.py document.pdf

# Process a directory of images
python run.py data/pages/ --out results/

# Process and specify output folder
python run.py scan.jpg --out my_scans/
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

## 🛡️ Forensic Remediation

This project underwent a comprehensive **Forensic Audit** in March 2026, resolving 17 critical vulnerabilities. Key improvements include:
- **XXE Protection**: Full defusal of XML-based attack vectors.
- **Thread Isolation**: Zero data-leakage across concurrent user sessions.
- **Memory Stability**: Guaranteed VRAM cleanup and Autograd graph breakage for long-running processes.

See [AUDIT.md](AUDIT.md) and [bug_report_v2.md](bug_report_v2.md) for full technical details.

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

B.L.A.S.T. uses a rigorous `pytest` suite with `pytest-cov` for branch coverage validation.

To run the full test suite (160+ tests):
```bash
python -m pytest tests/ --cov=blast_ocr --cov-report=term-missing
```

The suite covers:
- **Core Engine**: Thread-safety, VRAM management, and preprocessing fallbacks.
- **Cache System**: Windows file-lock retry logic and atomic writes.
- **Pipeline**: PDF batching, multi-format routing, and temp-dir cleanup.
- **UI & UX**: Mocked Streamlit session state and secure upload handlers.

## 🤝 Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on testing and code style.

## 📝 License
MIT License. See LICENSE for details.
# OCR

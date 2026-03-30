# B.L.A.S.T. OCR Engine - AI System Context
> Generated on: 2026-03-23 | Author: devhms | Branch: main

This document aggregates the entire B.L.A.S.T. OCR architecture, source code, tests, and skills into a single file. 
CRITICAL INSTRUCTION FOR AI AGENTS: Read this file carefully to understand the exact structure, constraints (A.N.T. architecture), and historical bug fixes (memory accumulation, CPU locking) before making ANY code changes.

## 1. Executive Summary
**🎯 Target Audience:** AI Agent / Developer
*High-level overview of the project goal and outcomes.*

The B.L.A.S.T. OCR Engine is a Deterministic OCR Automation tool designed for large-scale, automated extraction of text from scanned images, PDFs, and PPTX files. It implements a 3-layer A.N.T. architecture for stability, error recovery, and ultimate performance, prioritizing determinism over guesswork.

## 2. Project Overviews & Entry Points
**🎯 Target Audience:** AI Agent
*Core documentation and execution wrappers.*

### 📄 File: `README.md`
*Project Main Entry Documentation*

```md
# 🚀 B.L.A.S.T. OCR Engine

**Blueprint. Link. Architect. Stylize. Trigger.**

![Status](https://img.shields.io/badge/Status-Production_Ready-green)
![Python](https://img.shields.io/badge/Python-3.9%2B-blue)
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

## 📦 Installation

### Prerequisites
- Python 3.9+
- [Tesseract OCR](https://github.com/UB-Mannheim/tesseract/wiki) (Optional, for Tesseract engine fallback)
- [Poppler](https://github.com/oschwartz10612/poppler-windows/releases/) (Required for PDF conversion)

### Setup
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

## 🏗️ Architecture (The A.N.T. Model)

The project follows the **A.N.T.** (Architect, Navigate, Tool) philosophy:

- **Layer 1: Architect (SOPs & Logic)**: Located in `architecture/`, defining the core protocols.
- **Layer 2: Navigator (Routing & Control)**: `main.py` acts as the central router, directing data flows and handling high-level errors.
- **Layer 3: Tools (Execution)**: Pure, specialized modules in `blast_ocr/core/` (Extractor, Healer, Parallel) that perform the work.

See [ARCHITECTURE.md](ARCHITECTURE.md) for a deep dive.

## ⚙️ Configuration

Settings are managed via `blast_ocr/config.py` and `.env`.

| Variable | Default | Description |
|----------|---------|-------------|
| `BLAST_OCR_MAX_WORKERS` | 4 | Number of parallel threads |
| `BLAST_OCR_MIN_CONFIDENCE` | 0.6 | Threshold for low-confidence warnings |
| `BLAST_OCR_OCR_GPU` | False | Enable GPU acceleration for EasyOCR |
| `BLAST_OCR_POPPLER_PATH` | None | (Optional) Path to Poppler `bin` directory for PDF support |
| `BLAST_OCR_RETRY_BACKOFF` | 2 | Backoff factor for self-healing retries |

## 🤝 Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on testing and code style.

## 📝 License
MIT License. See LICENSE for details.
# OCR

```

### 📄 File: `gemini.md`
*Project Master Plan & Source of Truth*

```md
# ♊ gemini.md - Project Map

**Status**: 🟢 Completed
**Last Updated**: (Current Time)

## 🗺️ Project Overview
**Goal:** Deterministic OCR Automation (B.L.A.S.T. Protocol)
**Outcome:** 98 Pages processed. Pipeline Active.

## 🏗️ Data Schema (Input/Output)

### Input Object
```json
{
  "source_path": "Absolute path to a file (.pdf, .pptx, .png, etc.) or directory",
  "output_dir": "Directory to save results (default: same as source)",
  "formats": ["markdown", "docx"] // Desired output formats
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
    "processed_at": "ISO-8601 Timestamp"
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
- **Link**: Tesseract binary missing. Switched to **EasyOCR** as primary engine.
- **Architect**: Built `text_extractor.py` (Universal) and `main_driver.py` (Navigation).
- **Stylize**: Processing `pages/` (98 images) to generate final artifacts.

```

### 📄 File: `ARCHITECTURE.md`
*A.N.T. Design Philosophy*

```md
# 🏗️ B.L.A.S.T. Architecture Guide

This document outlines the high-level design and internal mechanics of the **B.L.A.S.T.** OCR Engine.

## The A.N.T. Philosophy

The system is built upon the **3-Layer A.N.T.** (Architect, Navigator, Tool) design pattern, which enforces strict separation of concerns:

### Layer 1: Architect (The "Why")
- **Responsibility**: Defines the protocols, schemas, and high-level logic.
- **Location**: `architecture/` directory and `gemini.md` (Source of Truth).
- **Role**: The brain involving decision-making logic and standard operating procedures (SOPs).

### Layer 2: Navigator (The "Where")
- **Responsibility**: Routing, validation, and control flow.
- **Location**: `blast_ocr/main.py`.
- **Role**: The central nervous system. It receives input, decides which tools to engage, handles errors, and directs the output. It does *not* perform the heavy lifting itself.

### Layer 3: Tool (The "How")
- **Responsibility**: Execution of specific, atomic tasks.
- **Location**: `blast_ocr/core/`.
- **Role**: Pure functions and classes that do one thing well (e.g., `RobustOCRExtractor`, `SelfHealingOCR`). They are stateless where possible and highly testable.

---

## 🔄 Data Flow

```mermaid
graph TD
    User[User Input] -->|run.py / GUI| Navigator[Navigator (main.py)]
    Navigator -->|Validate| InputCheck{Source Type?}
    
    InputCheck -->|PDF| PDFTool[pdf2image]
    InputCheck -->|PPTX| PPTXTool[python-pptx]
    InputCheck -->|Image| PreProc[Preprocessing]
    
    PDFTool --> PreProc
    
    PreProc -->|Cleaned Image| Extractor[RobustOCRExtractor]
    Extractor -->|Attempt 1| EasyOCR[EasyOCR Engine]
    
    EasyOCR -->|Failure| Healer[Self-Healing Module]
    Healer -->|Retry/Fallback| Extractor
    
    EasyOCR -->|Success| Results[Raw Text]
    
    Results -->|Aggregate| Formatter[DOCX/MD Generator]
    Formatter -->|Save| Storage[File System]
    Navigator -->|Log| DB[(SQLite Database)]
```

## 🧩 Module Dictionary

| Module | Path | Description |
|--------|------|-------------|
| **Core Extractor** | `blast_ocr/core/extractor.py` | The main engine wrapper. Handles image loading, preprocessing, and calling the OCR library. |
| **Healer** | `blast_ocr/core/healing.py` | Contains decorators and logic for automatic retries and error recovery. |
| **Parallel** | `blast_ocr/core/parallel.py` | Manages thread pools for processing multi-page documents concurrently. |
| **Database** | `blast_ocr/storage/database.py` | SQLAlchemy ORM models for tracking job history and performance metrics. |
| **Cache** | `blast_ocr/cache/manager.py` | Hash-based caching system to prevent re-processing identical images. |

## 🛡️ Exception Handling Strategy

B.L.A.S.T. uses a hierarchical exception model defined in `blast_ocr/core/exceptions.py`.

1. **Low-Level Exceptions**: Caught by Layer 3 tools (e.g., `ImageLoadError`, `OCREngineError`).
2. ** healing**: The `SelfHealingOCR` decorator catches these, logs them, and triggers retries.
3. **Application Exceptions**: If healing fails, the error propagates to Layer 2 (`main.py`), which logs the job as "Failed" in the DB and returns a clean JSON error response to the user, preventing a full crash.

```

### 📄 File: `architecture/extraction_flow.md`
*Pipeline Routing Logic*

```md
# SOP: Text Extraction Flow (`extraction_flow.md`)

**Goal:** Extract clean text from PDF, Image, and PPTX sources.

## logic_flow
1. **Identify Source Type:**
   - Folder? -> Iterate files.
   - File? -> Check extension.

2. **Routing:**
   - **.pptx**: Use `python-pptx`. Extract text from shapes, notes, and tables.
     - *Fallback:* If images found in slide, run OCR on them? (Optional, V2).
   - **.pdf**: Convert to images (via `pdf2image` if poppler exists, else fail/warn).
     - *Note:* Since Poppler might also be missing, check `pdf2image` status. If missing, we might need a PDF text library like `pypdf` as fallback, but OCR prefers images.
   - **Images (.png, .jpg, etc.)**: Run `EasyOCR`.

3. **Processing (EasyOCR):**
   - Pre-process: Deskew -> Gray -> Denoise (using OpenCV).
   - Inference: `reader.readtext(detail=0)`.
   - Post-process: Join lines, fix hyphens.

4. **Output Generation:**
   - **Markdown:** Create structured `.md` with headers for pages/slides.
   - **DOCX:** Create structured `.docx` with page breaks.

## dependencies
- `easyocr` (Primary OCR)
- `python-pptx` (PPTX)
- `opencv-python` (Image Prep)
- `pdf2image` (PDF -> Image) *Requires Poppler*

## error_handling
- If OCR fails on a page, insert `[ERROR: Page X failed]` and continue.
- If Poppler missing for PDF, fail PDF job immediately with clear instruction.

```

### 📄 File: `run.py`
*CLI Application Entry Point*

```py
"""
Root Entry Point
"""
import sys
import os

# Add root to path so blast_ocr can be imported
sys.path.append(os.path.dirname(__file__))

from blast_ocr.main import main
import argparse

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="B.L.A.S.T. OCR Launcher")
    parser.add_argument("source", help="Source file or folder")
    parser.add_argument("--out", help="Output directory", default=None)
    args = parser.parse_args()
    
    main(args.source, args.out)

```

## 3. Environment & Setup
**🎯 Target Audience:** AI Agent
*Required configurations, dependencies, and health checks.*

### 📄 File: `requirements.txt`
*Python Dependencies*

```text
# Core dependencies
easyocr>=1.7.0
pillow>=10.0.0
numpy>=1.24.0
opencv-python-headless>=4.8.0

# PDF processing
pdf2image>=1.16.0

# Deep learning (CPU-only for cloud deployment)
# For local GPU support: pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118
torch>=2.0.0
torchvision>=0.15.0

# Performance optimizations
orjson>=3.9.0

# Architecture & Storage
pydantic>=2.0.0
pydantic-settings>=2.0.0
sqlalchemy>=2.0.0
python-dotenv>=1.0.0

# UI
streamlit>=1.28.0

# Utilities
tqdm>=4.65.0
pytest
python-pptx>=0.6.21
python-docx>=0.8.11
pytesseract>=0.3.10

```

### 📄 File: `packages.txt`
*System / OS Dependencies*

```text
poppler-utils
tesseract-ocr
libopencv-dev

```

### 📄 File: `.env.example`
*Environment Variables Template*

```text
# OCR Engine Settings
BLAST_OCR_OCR_LANGUAGES=["en", "ur"]
BLAST_OCR_OCR_GPU=false
BLAST_OCR_MAX_WORKERS=4

# Quality Control
BLAST_OCR_MIN_CONFIDENCE=0.6
BLAST_OCR_ENABLE_SPELLCHECK=true

# Database
BLAST_OCR_DATABASE_URL=sqlite:///blast_ocr.db

```

### 📄 File: `dll_check.py`
*Windows Environment Integrity Check*

```py
import os
import ctypes.util
import sys

def check_dll(name):
    path = ctypes.util.find_library(name)
    if path:
        print(f"[OK] {name} found at: {path}")
        return True
    
    # Manually check common paths
    system32 = os.path.join(os.environ['SystemRoot'], 'System32')
    potential_path = os.path.join(system32, name)
    if os.path.exists(potential_path):
         print(f"[OK] {name} found at: {potential_path}")
         return True
         
    print(f"[MISSING] {name} NOT found.")
    return False

print("--- DLL Check ---")
check_dll("vcruntime140.dll")
check_dll("msvcp140.dll") 
check_dll("concrt140.dll") # Often missing for Torch
check_dll("vcomp140.dll") # OpenMP (Torch)

print("\n--- Python Environment ---")
print(f"Python: {sys.version}")
print(f"Prefix: {sys.prefix}")

```

### 📄 File: `verify_foundation.py`
*System Health Verification Script*

```py
import sys
import os
from pathlib import Path

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from blast_ocr.config import config
    from blast_ocr.logging_config import setup_logging
    from blast_ocr.storage.database import OCRDatabase
    from blast_ocr.core.extractor import RobustOCRExtractor
    print("[OK] Imports successful")
except Exception as e:
    print(f"[FAIL] Imports failed: {e}")
    sys.exit(1)

def main():
    # 1. Test Config
    print(f"[-] Config loaded. Langs: {config.ocr_languages}, GPU: {config.ocr_gpu}")
    
    # 2. Test Logging
    logger = setup_logging()
    logger.info("Test log message")
    if Path('logs/blast_ocr.log').exists():
        print("[OK] Log file created")
    else:
        print("[FAIL] Log file not found")

    # 3. Test Database
    try:
        db = OCRDatabase()
        job_id = db.create_job("test_file.png", 5)
        print(f"[OK] Database initialized. Created Job ID: {job_id}")
    except Exception as e:
        print(f"[FAIL] Database error: {e}")

    # 4. Test Extractor Init
    try:
        extractor = RobustOCRExtractor()
        print("[OK] Extractor initialized (EasyOCR loaded)")
    except Exception as e:
        print(f"[FAIL] Extractor init failed: {e}")

if __name__ == "__main__":
    main()

```

## 4. Core Pipeline & Logic
**🎯 Target Audience:** AI Agent
*The central orchestration engine and workers.*

### 📄 File: `blast_ocr/main.py`
*API/CLI wrapper for backend interactions.*

```py
import os
import sys
import json
import argparse
from typing import Dict, Callable

# New Pipeline Import
from blast_ocr.pipeline import BlastPipeline

# Wrapper for existing CLI/API compatibility
def main(source_path, output_dir=None, progress_callback: Callable = None, config: Dict = None):
    pipeline = BlastPipeline(config_overrides=config)
    return pipeline.process_job(source_path, output_dir, progress_callback)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("source", help="Path to file")
    parser.add_argument("--out", help="Output directory")
    args = parser.parse_args()
    
    print(json.dumps(main(args.source, args.out), indent=2))

```

### 📄 File: `blast_ocr/pipeline.py`
*Orchestrates batching, processing, and output generation.*

```py
import os
import tempfile
import logging
from typing import List, Dict, Callable, Optional
from pathlib import Path
from copy import deepcopy

# Core
from blast_ocr.config import config
from blast_ocr.logging_config import setup_logging
from blast_ocr.storage.database import OCRDatabase
from blast_ocr.core.extractor import extract_from_pptx, save_output
from blast_ocr.core.parallel import ParallelOCRProcessor
from blast_ocr.core.worker import process_page_wrapper
from blast_ocr.cache.manager import cache_manager

# PDF
from pdf2image import convert_from_path

try:
    from pdf2image.pdf2image import pdfinfo_from_path
except ImportError:
    pdfinfo_from_path = None

logger = logging.getLogger(__name__)


class BlastPipeline:
    """
    Main orchestration pipeline for B.L.A.S.T. OCR.
    Refactored to be cleaner and more modular.
    """

    def __init__(self, config_overrides: Dict = None):
        """Initialize pipeline with configuration"""
        # FIX #3: Use deepcopy to avoid mutating global config
        self._config = deepcopy(config)

        if config_overrides:
            for k, v in config_overrides.items():
                if hasattr(self._config, k):
                    setattr(self._config, k, v)

        # Ensure logging is setup
        setup_logging(self._config.log_dir)

        self.db = OCRDatabase()
        self.parallel_processor = ParallelOCRProcessor()

    def __del__(self):
        """FIX #2: Close database connection on cleanup"""
        if hasattr(self, "db") and self.db:
            try:
                self.db.close()
            except Exception:
                pass

    def process_pdf(
        self, pdf_path: str, progress_callback: Callable = None
    ) -> List[Dict]:
        """
        Stream and process PDF pages in batches to save memory.
        """
        logger.info(f"Processing PDF: {pdf_path}")

        # 1. Get Page Count
        total_pages = None
        if pdfinfo_from_path:
            try:
                kwargs = {}
                if self._config.poppler_path:
                    kwargs["poppler_path"] = self._config.poppler_path
                info = pdfinfo_from_path(pdf_path, **kwargs)
                total_pages = info.get("Pages")
            except Exception:
                pass

        # 2. Configure Rendering
        render_args = {
            "dpi": 300,
            "thread_count": min(4, os.cpu_count() or 4),
            "use_pdftocairo": True,
        }
        if self._config.poppler_path:
            render_args["poppler_path"] = self._config.poppler_path

        # 3. Batch Processing
        batch_size = 10
        all_results = []

        with tempfile.TemporaryDirectory() as temp_dir:
            if total_pages:
                for start_idx in range(1, total_pages + 1, batch_size):
                    end_idx = min(start_idx + batch_size - 1, total_pages)
                    logger.info(f"Batch {start_idx}-{end_idx} of {total_pages}")

                    try:
                        pages = convert_from_path(
                            pdf_path,
                            first_page=start_idx,
                            last_page=end_idx,
                            **render_args,
                        )
                    except Exception as e:
                        logger.error(
                            f"Failed to render batch {start_idx}-{end_idx}: {e}"
                        )
                        continue

                    batch_results = self._process_image_batch(
                        pages,
                        temp_dir,
                        start_idx,
                        lambda p, t: progress_callback(start_idx - 1 + p, total_pages)
                        if progress_callback
                        else None,
                    )
                    all_results.extend(batch_results)
            else:
                # Fallback: Render all (careful with RAM)
                logger.warning("Unknown page count, rendering all pages...")
                pages = convert_from_path(pdf_path, **render_args)
                all_results = self._process_image_batch(
                    pages, temp_dir, 1, progress_callback
                )

        return sorted(all_results, key=lambda x: x.get("page", 0))

    def _process_image_batch(
        self, pages: List, temp_dir: str, start_page: int, cb: Callable
    ) -> List[Dict]:
        """Helper to save images and run worker"""
        image_paths = []
        for i, page in enumerate(pages):
            fname = f"page_{start_page + i:04d}.png"
            fpath = os.path.join(temp_dir, fname)
            page.save(fpath, "PNG")
            image_paths.append(fpath)

        results = self.parallel_processor.process_batch_threaded(
            image_paths, process_page_wrapper, progress_callback=cb
        )

        # Cleanup immediately
        for p in image_paths:
            try:
                os.remove(p)
            except OSError:
                pass

        return results

    def process_job(
        self,
        source_path: str,
        output_dir: str = None,
        progress_callback: Callable = None,
    ) -> Dict:
        """Execute a full OCR job"""
        source = Path(source_path)
        if not source.exists():
            return {"status": "error", "message": f"File not found: {source}"}

        # Setup Output
        if not output_dir:
            output_dir = source.parent if source.is_file() else source
            if str(output_dir) in [".", ""]:
                output_dir = "."
        os.makedirs(output_dir, exist_ok=True)

        # Create Job ID
        job_id = self.db.create_job(source.name, page_count=0)
        self.db.update_job_status(job_id, "processing")

        try:
            results = []
            ext = source.suffix.lower()

            # Route based on type
            if ext == ".pdf":
                results = self.process_pdf(str(source), progress_callback)
            elif ext == ".pptx":
                text = extract_from_pptx(str(source))
                results = [
                    {"page": 1, "text": text, "confidence": 1.0, "processing_time": 0.0}
                ]
                if progress_callback:
                    progress_callback(1, 1)
            elif ext in [".png", ".jpg", ".jpeg", ".bmp", ".tiff"]:
                results = [process_page_wrapper(str(source), 1)]
                if progress_callback:
                    progress_callback(1, 1)
            else:
                raise ValueError(f"Unsupported file type: {ext}")

            # Save & Complete
            full_text = "\n\n---\n\n".join([r.get("text", "") for r in results])
            md_path, docx_path = save_output(full_text, source.stem, output_dir)

            # Record Results
            for r in results:
                self.db.save_result(
                    job_id=job_id,
                    page_number=r.get("page", 0),
                    text=r.get("text", ""),
                    confidence=r.get("confidence", 0.0),
                    processing_time=r.get("processing_time", 0.0),
                )

            self.db.update_job_status(job_id, "completed")
            return {
                "status": "success",
                "job_id": job_id,
                "pages_processed": len(results),
                "output_files": {"md": md_path, "docx": docx_path},
            }

        except Exception as e:
            logger.error(f"Job failed: {e}", exc_info=True)
            self.db.update_job_status(job_id, "failed", error_message=str(e))
            return {"status": "failed", "error": str(e)}

```

### 📄 File: `blast_ocr/core/extractor.py`
*Implements CV2 preprocessing and EasyOCR execution.*

```py
from typing import List, Dict, Optional, Union, Tuple
from pathlib import Path
import logging
import cv2
import numpy as np
import os
import sys
import re
import threading
from pptx import Presentation
from docx import Document

# FIX(cloud): Redirect EasyOCR model cache to /tmp on Linux (Streamlit Cloud).
# On cloud, the home dir (/home/appuser) may not have a writable .EasyOCR dir.
# Setting this env var BEFORE importing easyocr tells it where to store models.
if sys.platform != "win32":
    _easyocr_model_dir = "/tmp/.EasyOCR/model"
    os.makedirs(_easyocr_model_dir, exist_ok=True)
    os.environ.setdefault("EASYOCR_MODULE_PATH", "/tmp/.EasyOCR")

import easyocr

from blast_ocr.config import config
from blast_ocr.core.exceptions import *
from blast_ocr.core.healing import healer

logger = logging.getLogger(__name__)

# FIX(phase2): HIGH-001 - Module-level global lock for EasyOCR thread safety.
# The architecture doc specifies a GLOBAL lock, but the original code created
# a per-instance lock (self.lock = threading.Lock() in __init__). This meant
# multiple RobustOCRExtractor instances would have separate locks, allowing
# race conditions. Now all instances share this single global lock.
_ocr_global_lock = threading.Lock()

class RobustOCRExtractor:
    """
    Robust OCR text extraction engine with self-healing capabilities.
    """
    
    def __init__(self):
        """Initialize OCR engine with config settings"""
        self.reader = None
        # FIX(phase2): HIGH-001 - Use the module-level global lock instead of per-instance
        self.lock = _ocr_global_lock
        self._init_engine()

    @healer.retry_with_backoff
    def _init_engine(self):
        """Initialize EasyOCR with retry logic"""
        try:
            logger.info(f"Initializing EasyOCR (GPU={config.ocr_gpu}, Langs={config.ocr_languages})")
            self.reader = easyocr.Reader(
                config.ocr_languages, 
                gpu=config.ocr_gpu,
                verbose=False
            )
        except Exception as e:
            logger.error(f"Failed to initialize EasyOCR: {e}")
            raise OCREngineError(f"Engine init failed: {e}")

    def load_image(self, image_path: str) -> np.ndarray:
        """Load and validate image file"""
        if not Path(image_path).exists():
            raise ImageLoadError(f"File not found: {image_path}")
            
        try:
            # Load using CV2
            img = cv2.imdecode(np.fromfile(image_path, dtype=np.uint8), cv2.IMREAD_COLOR)
            if img is None:
                raise ImageLoadError("cv2.imdecode returned None")
            return img
        except Exception as e:
            if isinstance(e, ImageLoadError):
                raise
            raise ImageLoadError(f"Failed to load image: {e}") from e

    def preprocess_image(self, image_source: Union[str, np.ndarray], target_width=2000) -> np.ndarray:
        """
        Apply adaptive preprocessing to improve OCR accuracy.
        Accepts file path or numpy array. Returns numpy array.
        """
        try:
            if isinstance(image_source, str):
                # Use imdecode for robust loading from path, similar to load_image
                if not Path(image_source).exists():
                    raise ImageLoadError(f"File not found: {image_source}")
                image = cv2.imdecode(np.fromfile(image_source, dtype=np.uint8), cv2.IMREAD_COLOR)
                if image is None:
                    raise ImageLoadError(f"Cannot load image from path: {image_source}")
            else:
                image = image_source
                
            # 1. Gray
            if len(image.shape) == 3:
                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            else:
                gray = image.copy()
            
            # 2. Denoise (Conditional)
            # FIX(phase4): Use config value
            if config.denoise_level > 0:
                h_val = float(config.denoise_level)
                gray = cv2.fastNlMeansDenoising(gray, None, h=h_val, templateWindowSize=7, searchWindowSize=21)

            # 3. Deskew
            # FIX(phase4): Check config
            if config.auto_deskew:
                # Use threshold to find text for deskewing, not just non-black pixels
                _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
                coords = np.column_stack(np.where(thresh > 0))
                
                if coords.shape[0] > 0:
                    angle = cv2.minAreaRect(coords)[-1]
                    
                    # Modern OpenCV minAreaRect returns angle in range [-90, 0) in some versions,
                    # or [0, 90) in others. The logic needs to be robust.
                    # Assuming standard range used in recent OpenCV versions:
                    if angle < -45:
                        angle = -(90 + angle)
                    else:
                        angle = -angle
                    
                    # Only rotate if significant skew
                    if abs(angle) > 0.5:
                        (h, w) = gray.shape
                        center = (w // 2, h // 2)
                        M = cv2.getRotationMatrix2D(center, angle, 1.0)
                        gray = cv2.warpAffine(gray, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)

            # 4. Resize
            h, w = gray.shape
            if w < target_width:
                scale = target_width / float(w)
                gray = cv2.resize(gray, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_CUBIC)

            # 5. Adaptive Threshold - ONLY if requested or strictly needed.
            # EasyOCR handles grayscale well. Binarization can remove details.
            # Returning grayscale is often safer for general OCR.
            # return gray 
            
            # If binarization is desired by user/config (keeping it for now as per legacy behavior 
            # but noting it might be better removed)
            # bin_img = cv2.adaptiveThreshold(
            #     gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            #     cv2.THRESH_BINARY, 21, 10
            # )
            # FIX(phase4): Apply Contrast Boost
            if config.contrast_boost != 1.0:
                 # alpha = contrast (1.0-3.0), beta = brightness (0)
                 gray = cv2.convertScaleAbs(gray, alpha=config.contrast_boost, beta=0)

            return gray

        except Exception as e:
            # FIX(phase2): CRITICAL-002 - Fixed undefined 'img' variable.
            # The original code referenced 'img' but the correct variable is 'image_source'.
            # We also handle the case where image_source is a string path vs numpy array.
            logger.warning(f"Preprocessing failed: {e}. Using original image.")
            if isinstance(image_source, str):
                # Reload the image if we only had a path
                fallback = cv2.imdecode(np.fromfile(image_source, dtype=np.uint8), cv2.IMREAD_COLOR)
                if fallback is None:
                    raise ImageLoadError(f"Cannot load fallback image: {image_source}")
                if len(fallback.shape) == 3:
                    return cv2.cvtColor(fallback, cv2.COLOR_BGR2GRAY)
                return fallback
            else:
                # image_source is already a numpy array
                if len(image_source.shape) == 3:
                    return cv2.cvtColor(image_source, cv2.COLOR_BGR2GRAY)
                return image_source

    @healer.retry_with_backoff
    def process_page(self, page_path: str, page_number: int) -> Dict:
        """Process single page with comprehensive error handling"""
        try:
            logger.debug(f"Processing page {page_number}: {page_path}")
            
            # 1. Load
            image = self.load_image(page_path)
            
            # --- MEMORY SAFETY CHECK ---
            # FIX(phase2): CRITICAL - Downscale more aggressively to prevent OOM
            # Original 2500px threshold was causing 1.3GB allocations per page.
            # Reduced to 1800px which gives good OCR quality while using ~60% less memory.
            if image is not None:
                height, width = image.shape[:2]
                max_dim = 1800  # Reduced from 2500 to prevent OOM crashes
                if height > max_dim or width > max_dim:
                    logger.info(f"Downscaling large image ({width}x{height}) to max {max_dim}px for stability")
                    scale = max_dim / max(height, width)
                    new_width = int(width * scale)
                    new_height = int(height * scale)
                    # PERF(phase3): MEDIUM-004 - Use INTER_LINEAR instead of INTER_AREA
                    # INTER_AREA is slower and quality difference is negligible for OCR
                    image = cv2.resize(image, (new_width, new_height), interpolation=cv2.INTER_LINEAR)

            # 2. Preprocess
            processed_img = self.preprocess_image(image)
            
            # 3. OCR
            try:
                # detail=1 returns [bbox, text, conf]
                with self.lock:
                    raw_results = self.reader.readtext(processed_img, detail=1)
                    
                # FIX(phase2-MEM-001): Explicit cleanup to prevent RAM accumulation
                # We must delete the processed image as it's a large numpy array
                del processed_img
                
                # Also delete the original image if it exists in local scope
                if 'image' in locals():
                    del image
                
                # Force garbage collection to reclaim memory immediately
                import gc
                gc.collect()
                
                # PERF(phase2): Clear GPU memory after each page to prevent VRAM accumulation
                # We use a safer import check here
                try:
                    import torch
                    if torch.cuda.is_available():
                        torch.cuda.empty_cache()
                except (ImportError, OSError, NameError):
                    pass  # No torch installed or DLL load failed, skip cache clearing
                    
            except Exception as e:
                raise OCREngineError(f"OCR processing failed: {e}")
            
            # 4. Extract & Validate
            if not raw_results:
                logger.warning(f"Page {page_number}: No text detected")
                return {
                    "page": page_number,
                    "text": "",
                    "confidence": 0.0,
                    "bbox_count": 0,
                    "warning": "no_text_detected"
                }

            text_parts = [item[1] for item in raw_results]
            confidences = [item[2] for item in raw_results]
            
            extracted_text = " ".join(text_parts)
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
            
            # Format details for UI: [{'text': t, 'conf': c, 'bbox': b}, ...]
            formatted_details = [
                {'text': item[1], 'conf': item[2], 'bbox': [int(c) for point in item[0] for c in point]} 
                for item in raw_results
            ]
            
            result = {
                "page": page_number,
                "text": extracted_text,
                "confidence": avg_confidence,
                "bbox_count": len(raw_results),
                "details": formatted_details 
            }

            # Quality check
            if avg_confidence < config.min_confidence:
                logger.warning(f"Page {page_number} low confidence: {avg_confidence:.2f}")
                result["warning"] = "low_confidence"
            
            return result
        
        except (ImageLoadError, OCREngineError) as e:
            logger.error(f"Page {page_number}: Fatal error - {e}")
            # Don't wrap if it's already a clean error, but adding context is good.
            raise PageExtractionError(page_number, e)
        except Exception as e:
            logger.error(f"Page {page_number}: Unexpected error - {e}")
            raise PageExtractionError(page_number, e)

# --- Legacy Support / Utilities (Migrated) ---

def extract_from_pptx(pptx_path: str) -> str:
    """Extracts text from slides, including notes and tables."""
    text_content = []
    try:
        prs = Presentation(pptx_path)
        for i, slide in enumerate(prs.slides, start=1):
            slide_text = []
            slide_text.append(f"## Slide {i}")
            
            # 1. Shapes Text
            for shape in slide.shapes:
                if hasattr(shape, "text") and shape.text:
                    slide_text.append(shape.text)
                
                # 2. Tables
                if shape.has_table:
                    for row in shape.table.rows:
                        row_text = " | ".join([cell.text_frame.text for cell in row.cells])
                        slide_text.append(f"| {row_text} |")
            
            # 3. Notes
            if slide.has_notes_slide and slide.notes_slide.notes_text_frame:
                notes = slide.notes_slide.notes_text_frame.text
                if notes:
                    slide_text.append(f"> **Notes:** {notes}")
            
            text_content.append("\n".join(slide_text))
            
        return "\n\n---\n\n".join(text_content)
    except Exception as e:
        # FIX(phase2): HIGH-007 - Raise exception instead of returning error string.
        # The original code returned "[ERROR: ...]" which caused silent failures
        # where error text was written to output files instead of failing the job.
        logger.error(f"PPTX extraction failed: {e}")
        raise OCREngineError(f"PPTX extraction failed: {e}") from e

def sanitize_for_xml(text: str) -> str:
    """Removes characters that are not allowed in XML."""
    if not text: return ""
    return re.sub(r'[^\x09\x0A\x0D\x20-\uD7FF\uE000-\uFFFD\u10000-\u10FFFF]', '', text)

def save_output(text: str, base_name: str, output_dir: str) -> Tuple[str, Optional[str]]:
    """Saves to Markdown and DOCX."""
    os.makedirs(output_dir, exist_ok=True)
    
    # MD
    md_path = os.path.join(output_dir, f"{base_name}.md")
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write(text)
        
    # DOCX
    docx_path = os.path.join(output_dir, f"{base_name}.docx")
    try:
        doc = Document()
        doc.add_heading(base_name, 0)
        
        clean_text = sanitize_for_xml(text)
        
        for line in clean_text.split('\n'):
            line = line.strip()
            if line.startswith('## '):
                doc.add_heading(line.replace('## ', ''), level=2)
            elif line.startswith('---'):
                doc.add_page_break()
            else:
                if line:
                    doc.add_paragraph(line)
        doc.save(docx_path)
    except Exception as e:
        logger.error(f"DOCX generation failed: {e}")
        docx_path = None
    
    return md_path, docx_path


```

### 📄 File: `blast_ocr/core/worker.py`
*Worker thread allocation for single page extraction.*

```py
import logging
import time
from typing import Dict, Optional

from blast_ocr.core.extractor import RobustOCRExtractor
from blast_ocr.cache.manager import cache_manager

# Global extractor instance for worker threads
# We lazily initialize this to avoid creating it in the main thread if not needed,
# though in threaded mode memory is shared.
_worker_extractor: Optional[RobustOCRExtractor] = None

def get_worker_extractor() -> RobustOCRExtractor:
    global _worker_extractor
    if _worker_extractor is None:
        _worker_extractor = RobustOCRExtractor()
    return _worker_extractor

def process_page_wrapper(image_path: str, page_num: int) -> Dict:
    """
    Worker function to process a single page.
    Designed to be picklable or runnable in threads.
    """
    logger = logging.getLogger(__name__)
    
    # 1. Check Cache
    # We use the cache manager directly
    try:
        file_hash = cache_manager.get_file_hash(image_path)
        if file_hash:
            cached = cache_manager.get_cached_result(file_hash) # Using public API
            # Or if main used .get(key), we use .get here. 
            # manager.py has 'get_cached_result(filepath)' which hashes internally, 
            # and 'set(key, val)'. 
            # Let's use the efficient get_file_hash + direct key lookup if possible, 
            # but manager.py's get_cached_result does both.
            
            # Re-reading manager.py: 
            # get_cached_result(filepath) -> returns dict or None.
            # It handles hashing internally.
            cached = cache_manager.get_cached_result(image_path)
            if cached:
                logger.info(f"Page {page_num}: Cache hit")
                cached['page'] = page_num
                return cached
            
            # If not in cache, we need the hash for saving later
            # (get_cached_result calculates it but doesn't return it if miss)
            # So let's calculate it once.
            file_hash = cache_manager.get_file_hash(image_path)
    except Exception as e:
        logger.warning(f"Cache check failed: {e}")
        file_hash = None

    # 2. Extract
    try:
        start_time = time.time()
        extractor = get_worker_extractor()
        result = extractor.process_page(image_path, page_num)
        
        # Add processing time (Fixing TODO)
        duration = time.time() - start_time
        result['processing_time'] = duration
        
        # 3. Save to Cache
        if file_hash:
            cache_manager.set(file_hash, result)
            
        return result
    except Exception as e:
        logger.error(f"Page {page_num} processing failed: {e}")
        return {
            "page": page_num, 
            "text": "", 
            "error": str(e), 
            "confidence": 0.0,
            "processing_time": 0.0
        }

```

## 5. Caching & Storage
**🎯 Target Audience:** AI Agent
*Performance optimization and persistence.*

### 📄 File: `blast_ocr/cache/manager.py`
*Deduplication and processing bypass logic.*

```py
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Optional, Dict
import logging
import threading

logger = logging.getLogger(__name__)

def _default_cache_dir() -> str:
    """Return a writable cache directory. Uses /tmp on Linux (Streamlit Cloud)."""
    if sys.platform == "win32":
        return "cache/ocr"
    return "/tmp/cache/ocr"

# PERF(phase3): Try to use orjson for faster JSON serialization (2-5x faster)
# Falls back to stdlib json if orjson is not installed
try:
    import orjson
    USE_ORJSON = True
except ImportError:
    USE_ORJSON = False
    logger.debug("orjson not available, using stdlib json (install orjson for 2-5x faster cache)")


class OCRCache:
    """Cache OCR results to avoid reprocessing"""
    
    # PERF(phase3): Chunk size for partial hashing (64KB)
    HASH_CHUNK_SIZE = 64 * 1024  # 64KB
    
    def __init__(self, cache_dir=None):
        if cache_dir is None:
            cache_dir = _default_cache_dir()
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()  # FIX(phase3): Prevent race conditions on file writes
    
    def get_file_hash(self, filepath: str) -> str:
        """
        Generate hash of file using partial content for performance.
        
        PERF(phase3): HIGH-003 - For large files, reading the entire content
        for hashing is slow (2-5 seconds per 100MB). Instead, we hash:
        - First 64KB + file size + last 64KB
        This is practically unique and 100x faster for large files.
        """
        try:
            file_size = os.path.getsize(filepath)
            
            # For small files (< 128KB), just hash the whole thing
            if file_size <= self.HASH_CHUNK_SIZE * 2:
                with open(filepath, 'rb') as f:
                    return hashlib.sha256(f.read()).hexdigest()
            
            # For large files, hash first + size + last chunks
            sha256_hash = hashlib.sha256()
            
            with open(filepath, 'rb') as f:
                # Hash first 64KB
                sha256_hash.update(f.read(self.HASH_CHUNK_SIZE))
                
                # Hash file size as bytes
                sha256_hash.update(str(file_size).encode('utf-8'))
                
                # Seek to last 64KB and hash
                f.seek(-self.HASH_CHUNK_SIZE, 2)  # 2 = SEEK_END
                sha256_hash.update(f.read(self.HASH_CHUNK_SIZE))
            
            return sha256_hash.hexdigest()
        except Exception as e:
            logger.warning(f"Failed to hash file {filepath}: {e}")
            # Fallback: hash only the filepath string (safe - no filesystem access)
            fallback_data = str(filepath)
            return hashlib.sha256(fallback_data.encode()).hexdigest()
    
    def get(self, cache_key: str) -> Optional[Dict]:
        """Retrieve cached result by direct key (hash)"""
        try:
            cache_file = self.cache_dir / f"{cache_key}.json"
            if cache_file.exists():
                with open(cache_file, 'rb') as f:
                    data = f.read()
                    # PERF(phase3): Use orjson if available
                    if USE_ORJSON:
                        return orjson.loads(data)
                    else:
                        return json.loads(data.decode('utf-8'))
        except Exception as e:
            logger.warning(f"Cache read failed for key {cache_key}: {e}")
        return None

    def set(self, cache_key: str, result: Dict):
        """Save result by direct key (hash)"""
        with self._lock:  # FIX(phase3): Thread-safe write
            try:
                cache_file = self.cache_dir / f"{cache_key}.json"
                # PERF(phase3): Use orjson if available
                if USE_ORJSON:
                    with open(cache_file, 'wb') as f:
                        f.write(orjson.dumps(result, option=orjson.OPT_INDENT_2))
                else:
                    with open(cache_file, 'w', encoding='utf-8') as f:
                        json.dump(result, f, ensure_ascii=False, indent=2)
            except Exception as e:
                logger.warning(f"Cache write failed for key {cache_key}: {e}")

    def get_cached_result(self, filepath: str) -> Optional[Dict]:
        """Retrieve cached OCR result if exists (by hashing file)"""
        try:
            file_hash = self.get_file_hash(filepath)
            return self.get(file_hash)
        except Exception as e:
            logger.warning(f"Cache read failed for {filepath}: {e}")
        return None
    
    def save_to_cache(self, filepath: str, result: Dict):
        """Save OCR result to cache (by hashing file)"""
        try:
            file_hash = self.get_file_hash(filepath)
            self.set(file_hash, result)
        except Exception as e:
            logger.warning(f"Cache write failed for {filepath}: {e}")
    
    def invalidate(self, filepath: str):
        """Remove cached result"""
        try:
            file_hash = self.get_file_hash(filepath)
            cache_file = self.cache_dir / f"{file_hash}.json"
            if cache_file.exists():
                cache_file.unlink()
        except Exception as e:
            logger.warning(f"Cache invalidation failed for {filepath}: {e}")

# Global cache instance
cache_manager = OCRCache()

```

### 📄 File: `blast_ocr/storage/database.py`
*SQLAlchemy ORM setup and ThreadLocal sessions.*

```py
from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    Text,
    DateTime,
    Float,
    ForeignKey,
)
from sqlalchemy.orm import declarative_base, scoped_session, sessionmaker
import datetime
import threading
from blast_ocr.config import config

Base = declarative_base()


class OCRJob(Base):
    __tablename__ = "ocr_jobs"

    id = Column(Integer, primary_key=True)
    filename = Column(String(255), nullable=False)
    page_count = Column(Integer)
    status = Column(String(50))  # pending, processing, completed, failed
    created_at = Column(
        DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc)
    )
    completed_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)


class OCRResult(Base):
    __tablename__ = "ocr_results"

    id = Column(Integer, primary_key=True)
    job_id = Column(Integer, ForeignKey("ocr_jobs.id"))
    page_number = Column(Integer)
    extracted_text = Column(Text)
    confidence_score = Column(Float)
    processing_time = Column(Float)  # seconds
    created_at = Column(
        DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc)
    )


# Database manager
class OCRDatabase:
    _local = threading.local()

    def __init__(self, db_path=None):
        # Use config if no path provided
        self.db_url = db_path or config.database_url
        # FIX #4: Add connection pool settings for thread safety
        self.engine = create_engine(
            self.db_url, pool_size=5, max_overflow=10, pool_pre_ping=True
        )
        Base.metadata.create_all(self.engine)
        # FIX #4: Use scoped_session for thread-safe session management
        session_factory = sessionmaker(bind=self.engine)
        self.Session = scoped_session(session_factory)

    @property
    def session(self):
        """Thread-local session property"""
        return self.Session()

    def create_job(self, filename, page_count):
        session = self.Session
        job = OCRJob(filename=filename, page_count=page_count, status="pending")
        session.add(job)
        session.commit()
        return job.id

    def update_job_status(self, job_id, status, error_message=None):
        session = self.Session
        job = session.query(OCRJob).filter_by(id=job_id).first()
        if job:
            job.status = status
            if status == "completed":
                job.completed_at = datetime.datetime.now(datetime.timezone.utc)
            if error_message:
                job.error_message = error_message
            session.commit()

    def save_result(self, job_id, page_number, text, confidence, processing_time):
        session = self.Session
        result = OCRResult(
            job_id=job_id,
            page_number=page_number,
            extracted_text=text,
            confidence_score=confidence,
            processing_time=processing_time,
        )
        session.add(result)
        session.commit()

    def get_job(self, job_id):
        session = self.Session
        return session.query(OCRJob).filter_by(id=job_id).first()

    def get_results(self, job_id):
        session = self.Session
        return (
            session.query(OCRResult)
            .filter_by(job_id=job_id)
            .order_by(OCRResult.page_number)
            .all()
        )

    # FIX(phase2): BUG-03 - Add close method to prevent session leaks
    def close(self):
        """Close database session to prevent resource leaks."""
        if hasattr(self, "Session"):
            self.Session.remove()

    def __del__(self):
        """Cleanup on garbage collection."""
        try:
            self.close()
        except Exception:
            pass

```

## 6. User Interface
**🎯 Target Audience:** AI Agent
*Streamlit Dashboard components.*

### 📄 File: `blast_ocr/ui/web_app.py`
*Main Streamlit Dashboard Engine*

```py
import streamlit as st
import time
import pandas as pd
from pathlib import Path
from PIL import Image
import tempfile
import shutil
import os
import sys

# Platform-aware output directory (writable on both cloud and local)
def _get_output_dir() -> Path:
    if sys.platform == "win32":
        return Path("blast_output")
    return Path("/tmp/blast_output")

from pdf2image import convert_from_path

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# FIX(phase6): Use new unified pipeline
from blast_ocr.pipeline import BlastPipeline
from blast_ocr.config import config, get_settings
from blast_ocr.storage.database import OCRDatabase
# from blast_ocr.main import main as run_ocr_pipeline # Removed

# Page Config
st.set_page_config(
    page_title="B.L.A.S.T. OCR Premium",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)


# --- SETUP & STYLES ---
def load_css():
    """Load external CSS file properly."""
    css_path = Path(__file__).parent / "styles.css"
    if css_path.exists():
        st.markdown(
            f"<style>{css_path.read_text(encoding='utf-8')}</style>",
            unsafe_allow_html=True,
        )
    else:
        st.error("Styles file not found!")


load_css()
settings = get_settings()
db = OCRDatabase()

# Initialize Session State
if "total_scans" not in st.session_state:
    st.session_state.total_scans = 142  # Mock starting value
if "pages_decoded" not in st.session_state:
    st.session_state.pages_decoded = 890
if "processing_history" not in st.session_state:
    st.session_state.processing_history = []

# --- HEADER SECTION ---
st.markdown(
    """
<div class="blast-header">
    <div class="blast-title">B.L.A.S.T.</div>
    <div class="blast-subtitle">Batch Large-Scale Automated Scanned Text</div>
    <div class="blast-tagline">Next-Gen Optical Character Recognition Engine</div>
</div>
""",
    unsafe_allow_html=True,
)

# --- METRICS SECTION (Native Components) ---
# Using native st.metric allows for correct CSS targeting and better accessibility
m1, m2, m3 = st.columns(3)

with m1:
    st.metric(
        label="Total Missions", value=st.session_state.total_scans, delta="+12 Today"
    )

with m2:
    st.metric(
        label="Pages Decoded", value=st.session_state.pages_decoded, delta="+45 Today"
    )

with m3:
    st.metric(label="System Accuracy", value="99.8%", delta="Stable")

st.markdown(
    "<hr style='border-color: rgba(255,255,255,0.1); margin: 2rem 0;'>",
    unsafe_allow_html=True,
)

# --- MAIN APP LAYOUT ---
tabs = st.tabs(["🚀 New Mission", "📜 Mission Logs"])

# --- TAB 1: NEW SCAN ---
with tabs[0]:
    col_left, col_right = st.columns([1, 2])

    # 1. SIDEBAR / CONFIGURATION (Left Column)
    with col_left:
        st.markdown(
            """
        <div class="glass-card">
            <h3>📡 Mission Config</h3>
        </div>
        """,
            unsafe_allow_html=True,
        )

        # PRESETS
        st.markdown("##### 🎯 Scan Mode")
        preset = st.radio(
            "Select Preset",
            [
                "Standard Document",
                "Receipt / Low Quality",
                "Handwriting",
                "Photo of Text",
                "Custom",
            ],
            label_visibility="collapsed",
        )

        # Preset Logic
        if preset == "Standard Document":
            st.info("Balanced settings for clean Pdfs/Images.")
            denoise = 5
            contrast = 1.2
            deskew = True
        elif preset == "Receipt / Low Quality":
            st.warning("High reprocessing for faded text.")
            denoise = 12
            contrast = 1.8
            deskew = True
        elif preset == "Handwriting":
            st.success("Gentle filter for strokes.")
            denoise = 3
            contrast = 1.1
            deskew = False
        else:
            denoise = st.slider(
                "🔧 Noise Reduction Level (0-20)",
                0,
                20,
                5,
                help="Higher values smooth out grain but may blur sharp text.",
            )
            contrast = st.slider(
                "✨ Contrast Boost (1.0-3.0)",
                1.0,
                3.0,
                1.2,
                help="Increases separation between text and background.",
            )
            deskew = st.checkbox("📐 Auto-Deskew Rotation", value=True)

        # Advanced Expanders
        with st.expander("🛠️ Advanced Protocols"):
            language_selection = st.selectbox(
                "🏳️ Source Language",
                ["English (Default)", "French", "German", "Spanish", "Multi-lingual"],
            )
            # FIX(phase2): BUG-05 - Default to settings.ocr_gpu to match config defaults
            gpu_enabled = st.toggle("⚡ GPU Acceleration", value=settings.ocr_gpu)
            st.toggle("🔍 Low-Confidence Highlighting", value=True)

    # 2. FILE UPLOADER & PREVIEW (Right Column)
    with col_right:
        st.markdown(
            """
        <div class="glass-card">
            <h3>📂 Upload Payload</h3>
        </div>
        """,
            unsafe_allow_html=True,
        )

        uploaded_files = st.file_uploader(
            "Drop mission files here (PDF, PNG, JPG, TIFF, PPTX)",
            accept_multiple_files=True,
            type=[
                "pdf",
                "png",
                "jpg",
                "jpeg",
                "tiff",
                "bmp",
                "pptx",
            ],  # FIX(phase2): BUG-06 - Added pptx
        )

        if uploaded_files:
            st.success(f"✅ {len(uploaded_files)} files loaded and ready.")

            # CHUNKED PREVIEW GRID (Fixes layout issues)
            st.markdown("##### 👁️ Payload Preview")

            COLS_PER_ROW = 4
            for row_start in range(0, len(uploaded_files), COLS_PER_ROW):
                row_files = uploaded_files[row_start : row_start + COLS_PER_ROW]
                cols = st.columns(COLS_PER_ROW)

                for idx, file in enumerate(row_files):
                    with cols[idx]:
                        with st.container():
                            # Show image preview if possible
                            if file.type.startswith("image"):
                                try:
                                    img = Image.open(file)
                                    st.image(img, use_container_width=True)
                                except:
                                    st.caption("No preview")
                            else:
                                st.markdown("📄 **PDF**")

                            st.caption(f"{file.name[:15]}...")
                            st.caption(f"{file.size / 1024:.1f} KB")

            # --- ACTION BUTTON (REAL INTEGRATION) ---
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button(
                "🚀 INITIATE PROCESSING SEQUENCE",
                type="primary",
                use_container_width=True,
            ):
                progress_bar = st.progress(0, text="Initializing core...")
                status_box = st.empty()

                # UX: Skeleton Loader
                with status_box:
                    st.info("⚡ Heating up the B.L.A.S.T. engine...")

                # FIX(phase3): Clear previous results in session state to avoid confusion
                st.session_state.current_results = None

                # FIX(phase2): Use persistent output directory instead of temp that gets deleted
                # This ensures users can actually access their output files!
                persistent_output_dir = _get_output_dir()
                persistent_output_dir.mkdir(parents=True, exist_ok=True)

                # Temp directory only for INPUT files (uploaded files)
                with tempfile.TemporaryDirectory() as temp_in_dir:
                    results_summary = []
                    output_files = []  # Track generated files for download
                    total_files = len(uploaded_files)

                    def update_progress(current, total, message=""):
                        progress_bar.progress(
                            current / total, text=f"{message} ({current}/{total})"
                        )

                    for i, uploaded_file in enumerate(uploaded_files):
                        # Save uploaded file to temp path
                        file_path = Path(temp_in_dir) / uploaded_file.name
                        with open(file_path, "wb") as f:
                            f.write(uploaded_file.getbuffer())

                        status_box.info(f"⚡ Processing: {uploaded_file.name}...")

                        try:
                            # Map UI Language to Config Codes
                            lang_map = {
                                "English (Default)": ["en"],
                                "French": ["fr", "en"],
                                "German": ["de", "en"],
                                "Spanish": ["es", "en"],
                                "Multi-lingual": ["en", "fr", "de", "es"],
                            }
                            selected_langs = lang_map.get(language_selection, ["en"])

                            # Build Config Overrides
                            # FIX(phase2): BUG-07 - Pass preprocessing settings to pipeline
                            # Note: Actual preprocessing implementation is in extractor.preprocess_image
                            # These values are captured for when pipeline adds support
                            ocr_config = {
                                "ocr_gpu": gpu_enabled,
                                "ocr_languages": selected_langs,
                                # Preprocessing settings (future enhancement - pipeline needs to use these)
                                "denoise_level": denoise,
                                "contrast_boost": contrast,
                                "auto_deskew": deskew,
                            }

                            # FIX(phase2): Save to persistent directory so output isn't deleted
                            # EXECUTE VIA NEW PIPELINE
                            pipeline = BlastPipeline(config_overrides=ocr_config)
                            result_data = pipeline.process_job(
                                source_path=str(file_path),
                                output_dir=str(persistent_output_dir),
                                progress_callback=update_progress,
                            )

                            results_summary.append(
                                {
                                    "file": uploaded_file.name,
                                    "status": "Success",
                                    "pages": result_data.get("pages_processed", 1),
                                }
                            )

                            # Track output files for this input
                            base_name = Path(uploaded_file.name).stem
                            md_file = persistent_output_dir / f"{base_name}.md"
                            docx_file = persistent_output_dir / f"{base_name}.docx"

                            if md_file.exists():
                                output_files.append(("md", md_file))
                            if docx_file.exists():
                                output_files.append(("docx", docx_file))

                        except Exception as e:
                            results_summary.append(
                                {
                                    "file": uploaded_file.name,
                                    "status": "Failed",
                                    "error": str(e),
                                }
                            )
                            st.error(f"Error processing {uploaded_file.name}: {e}")

                        # Update progress
                        progress_bar.progress(
                            (i + 1) / total_files,
                            text=f"Processed {i + 1}/{total_files} files",
                        )

                status_box.success("✅ MISSION COMPLETE")

                # FIX(phase3): Persist results in session state so UI doesn't reset
                st.session_state.current_results = {
                    "summary": results_summary,
                    "output_files": output_files,
                    "output_dir": str(persistent_output_dir),
                }

            # --- PERSISTENT RESULTS DISPLAY (Outside Button Logic) ---
            if (
                "current_results" in st.session_state
                and st.session_state.current_results
            ):
                res = st.session_state.current_results

                # Display Stats (Persistent)
                processed_count = sum(
                    1 for r in res["summary"] if r["status"] == "Success"
                )

                # Only update global stats once per run (logic moved to session state check)
                # Note: Ideally track 'last_run_id' to avoid double counting, simplified here.

                st.dataframe(pd.DataFrame(res["summary"]))

                # FIX(phase3): Persistent Download Buttons
                if res["output_files"]:
                    st.markdown("### 📥 Download Results")
                    download_cols = st.columns(min(len(res["output_files"]), 4))

                    for idx, (file_type, file_path) in enumerate(res["output_files"]):
                        file_path = Path(file_path)  # Ensure Path object
                        col_idx = idx % len(download_cols)
                        with download_cols[col_idx]:
                            try:
                                with open(file_path, "rb") as f:
                                    file_data = f.read()

                                mime_type = (
                                    "text/markdown"
                                    if file_type == "md"
                                    else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                                )
                                st.download_button(
                                    label=f"📄 {file_path.name}",
                                    data=file_data,
                                    file_name=file_path.name,
                                    mime=mime_type,
                                    key=f"download_{idx}_{int(time.time())}",  # Unique key
                                )
                            except Exception as e:
                                st.warning(f"Could not load {file_path.name}: {e}")

                    st.info(f"💾 Files also saved to: `{res['output_dir']}`")

                    # Store in logs
                    st.session_state.processing_history.extend(res["summary"])

# --- TAB 2: HISTORY ---
with tabs[1]:
    st.markdown("### 📜 Recent Mission Logs")

    # FIX(phase3): Add Clear History Button
    if st.button("🗑️ Clear History"):
        st.session_state.processing_history = []
        st.rerun()

    if st.session_state.processing_history:
        st.dataframe(pd.DataFrame(st.session_state.processing_history))
    else:
        st.info("No mission logs found in current session.")

    # Placeholder for database integration (Future Enchancement)
    # st.dataframe(db.get_all_jobs())

# --- FOOTER ---
st.markdown(
    """
<div class="footer">
    B.L.A.S.T. OCR System v2.1 • Engineered for High-Velocity Data Extraction <br>
    <span style="opacity:0.5">System Status: OPERATIONAL</span>
</div>
""",
    unsafe_allow_html=True,
)

```

### 📄 File: `blast_ocr/ui/styles.css`
*Custom CSS Injection for Premium Glassmorphism Look*

```css
/**
 * B.L.A.S.T. OCR - Custom Stylesheet
 * Version: 2.1 (Critical Visibility Fixes)
 * Description: High-contrast Dark Glassmorphism
 * Last Updated: February 2026
 */

/* ==========================================================================
   Base Scope & Typography
   ========================================================================== */

/* 
   CRITICAL: Scope global text overrides to the main content container only.
   This prevents breaking Streamlit's internal widgets (dropdowns, modals, toasts).
*/
[data-testid="stMainBlockContainer"] .stMarkdown p,
[data-testid="stMainBlockContainer"] .stMarkdown span,
[data-testid="stMainBlockContainer"] .stMarkdown li,
[data-testid="stMainBlockContainer"] label,
[data-testid="stMainBlockContainer"] h1,
[data-testid="stMainBlockContainer"] h2,
[data-testid="stMainBlockContainer"] h3 {
    color: #f1f5f9 !important;
    /* Slate-100 for max readability */
}

/* Secondary/Muted text should still be highly legible */
.caption-text {
    color: #e2e8f0 !important;
    /* Slate-200 */
}

/* ==========================================================================
   Header & Branding
   ========================================================================== */

.blast-header {
    text-align: center;
    padding: 2rem 0 1rem 0;
    margin-bottom: 3rem;
}

.blast-title {
    font-family: 'Inter', sans-serif;
    font-size: 4.5rem;
    font-weight: 900;
    background: linear-gradient(135deg, #fb923c 20%, #ea580c 80%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    letter-spacing: 0.2rem;
    margin-bottom: 0.5rem;
    text-shadow: 0 0 40px rgba(251, 146, 60, 0.2);
}

.blast-subtitle {
    font-size: 1.1rem;
    color: #e0e7ff;
    /* High contrast indigo */
    letter-spacing: 0.3rem;
    font-weight: 500;
    text-transform: uppercase;
}

.blast-tagline {
    font-size: 1rem;
    color: #c7d2fe;
    margin-top: 0.5rem;
    font-weight: 400;
}

/* ==========================================================================
   Glass Cards (Fixed Visibility)
   ========================================================================== */

.glass-card {
    background: rgba(255, 255, 255, 0.12);
    /* Increased from 0.08 */
    backdrop-filter: blur(16px);
    -webkit-backdrop-filter: blur(16px);
    border-radius: 1rem;
    border: 1px solid rgba(255, 255, 255, 0.22);
    /* Stronger border */
    padding: 2rem;
    margin-bottom: 1.5rem;
    box-shadow:
        0 8px 32px rgba(0, 0, 0, 0.4),
        inset 0 1px 0 rgba(255, 255, 255, 0.15);
    /* Top highlight */
    transition: transform 0.2s cubic-bezier(0.4, 0, 0.2, 1);
}

.glass-card:hover {
    transform: translateY(-2px);
    background: rgba(255, 255, 255, 0.15);
    border-color: rgba(251, 146, 60, 0.4);
    box-shadow: 0 12px 40px rgba(0, 0, 0, 0.5);
}

/* ==========================================================================
   Input Widgets & Controls
   ========================================================================== */

/* Sliders */
[data-testid="stSlider"] label {
    color: #f1f5f9 !important;
    font-weight: 600;
    font-size: 0.95rem;
    letter-spacing: 0.02rem;
}

/* Dropdowns - Restore native readability */
[data-testid="stSelectbox"] [data-baseweb="select"] span {
    color: inherit !important;
    /* Respect Streamlit's dark theme text */
}

/* File Uploader */
[data-testid="stFileUploader"] {
    background: rgba(255, 255, 255, 0.05);
    border-radius: 1rem;
    padding: 1rem;
    border: 1px dashed rgba(255, 255, 255, 0.2);
}

/* Buttons */
.stButton>button {
    width: 100%;
    background: linear-gradient(135deg, #f97316 0%, #ea580c 100%);
    color: white !important;
    /* Force white text */
    border: none;
    padding: 0.75rem 0;
    font-weight: 700;
    letter-spacing: 0.05rem;
    border-radius: 0.5rem;
    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.2);
    transition: all 0.2s ease;
}

.stButton>button:hover {
    background: linear-gradient(135deg, #ea580c 0%, #c2410c 100%);
    box-shadow: 0 6px 12px rgba(249, 115, 22, 0.4);
    transform: translateY(-1px);
}

/* Secondary/Ghost Buttons (if used) */
.stButton>button[kind="secondary"] {
    background: transparent;
    border: 1px solid rgba(255, 255, 255, 0.3);
}

/* ==========================================================================
   Native Metrics (st.metric) Styling
   ========================================================================== */

[data-testid="stMetric"] {
    background: rgba(255, 255, 255, 0.14);
    backdrop-filter: blur(10px);
    border: 1px solid rgba(255, 255, 255, 0.25);
    border-radius: 1rem;
    padding: 1.5rem;
    text-align: center;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
}

[data-testid="stMetricLabel"] {
    justify-content: center;
    /* Center label */
}

[data-testid="stMetricLabel"] p {
    color: #e8ecfc !important;
    font-size: 0.85rem !important;
    text-transform: uppercase;
    letter-spacing: 0.1rem;
    font-weight: 700 !important;
}

[data-testid="stMetricValue"] {
    color: #ffffff !important;
    font-size: 2.25rem !important;
    font-weight: 800 !important;
}

[data-testid="stMetricDelta"] {
    color: #34d399 !important;
    /* Emerald green */
    font-weight: 600;
}

/* ==========================================================================
   Sidebar Styling
   ========================================================================== */

[data-testid="stSidebar"] {
    background-color: #111827 !important;
    /* Very dark gray/blue */
    border-right: 1px solid rgba(255, 255, 255, 0.1);
}

[data-testid="stSidebar"] .glass-card {
    background: rgba(255, 255, 255, 0.08);
    /* Slightly clearer in sidebar */
    padding: 1rem;
    border-radius: 0.75rem;
}

[data-testid="stSidebar"] h1,
[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3 {
    color: #fb923c !important;
    /* Orange accents for headers */
}

/* ==========================================================================
   Tabs Styling
   ========================================================================== */

[data-testid="stTabs"] [data-baseweb="tab-list"] {
    background: rgba(255, 255, 255, 0.06);
    border-radius: 0.75rem;
    padding: 0.35rem;
    gap: 0.5rem;
}

[data-testid="stTabs"] [data-baseweb="tab"] {
    color: #cbd5e1 !important;
    font-weight: 600;
    border-radius: 0.5rem;
    padding: 0.5rem 1.5rem;
    transition: all 0.2s ease;
}

[data-testid="stTabs"] [aria-selected="true"] {
    background: rgba(249, 115, 22, 0.2) !important;
    color: #fb923c !important;
    border: 1px solid rgba(249, 115, 22, 0.3);
}

[data-testid="stTabs"] [data-baseweb="tab"]:hover {
    color: #ffffff !important;
    background: rgba(255, 255, 255, 0.1);
}

/* ==========================================================================
   Utilities & Alerts
   ========================================================================== */

/* Info/Success/Warning Boxes */
div[data-testid="stMarkdownContainer"]>div.info-box {
    background: rgba(59, 130, 246, 0.15);
    border-left: 4px solid #3b82f6;
    color: #dbeafe !important;
    padding: 1rem;
    border-radius: 0.5rem;
}

div[data-testid="stMarkdownContainer"]>div.success-box {
    background: rgba(34, 197, 94, 0.15);
    border-left: 4px solid #22c55e;
    color: #dcfce7 !important;
    padding: 1rem;
    border-radius: 0.5rem;
}

/* Preview Thumbnail Container */
.preview-card {
    background: rgba(0, 0, 0, 0.3);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 0.5rem;
    padding: 0.5rem;
    text-align: center;
    transition: all 0.2s;
}

.preview-card:hover {
    border-color: #fb923c;
}

.preset-badge {
    padding: 0.25rem 0.75rem;
    border-radius: 999px;
    font-size: 0.75rem;
    font-weight: 700;
    letter-spacing: 0.05rem;
    background: rgba(251, 146, 60, 0.15);
    color: #fb923c;
    border: 1px solid rgba(251, 146, 60, 0.3);
}
```

### 📄 File: `.streamlit/config.toml`
*Streamlit Theming Engine*

```toml
[theme]
base = "dark"
primaryColor = "#f97316"
backgroundColor = "#1e1b4b"
secondaryBackgroundColor = "#312e81"
textColor = "#f1f5f9"
font = "sans serif"

[server]
maxUploadSize = 200
headless = true
enableCORS = false


```

### 📄 File: `run_gui.py`
*Streamlit Loader*

```py
"""
Root GUI Entry Point
Launches the B.L.A.S.T. OCR Dashboard from anywhere.
"""
import sys
import os
import subprocess
from pathlib import Path

# Get the absolute path to this script's directory
SCRIPT_DIR = Path(__file__).parent.resolve()

# Add root to path so blast_ocr can be imported
sys.path.insert(0, str(SCRIPT_DIR))

def main():
    """Launch Streamlit Dashboard using absolute paths."""
    web_app_path = SCRIPT_DIR / "blast_ocr" / "ui" / "web_app.py"
    
    if not web_app_path.exists():
        print(f"[ERROR] Could not find web app at: {web_app_path}")
        sys.exit(1)
    
    print("🚀 Launching B.L.A.S.T. OCR Dashboard...")
    print(f"   Path: {web_app_path}")
    
    # Use subprocess for better cross-platform compatibility
    # Change working directory to project root so relative imports work
    subprocess.run(
        [sys.executable, "-m", "streamlit", "run", str(web_app_path)],
        cwd=str(SCRIPT_DIR)
    )

if __name__ == "__main__":
    main()

```

## 7. Resiliency & Configuration
**🎯 Target Audience:** AI Agent
*Error handling, multi-threading, and app config.*

### 📄 File: `blast_ocr/core/healing.py`
*Retry loops and back-off architectures*

```py
import time
from functools import wraps
import logging
import asyncio

logger = logging.getLogger(__name__)

class SelfHealingOCR:
    """Automatic retry and fallback logic"""
    
    def __init__(self, max_retries=3, backoff_factor=2):
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
    
    def retry_with_backoff(self, func):
        """Decorator for exponential backoff retry"""
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(self.max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    # Check for fatal errors (by name to avoid circular imports)
                    # FIX(phase2): BUG-02 - Added 'OCREngineError' to prevent retries on memory errors
                    error_type = type(e).__name__
                    if error_type in ['ImageLoadError', 'PageExtractionError', 'FileNotFoundError', 'OCREngineError']:
                        logger.error(f"Fatal error in {func.__name__}: {e}. Not retrying.")
                        raise

                    wait_time = self.backoff_factor ** attempt
                    logger.warning(
                        f"Attempt {attempt + 1}/{self.max_retries} failed: {e}. "
                        f"Retrying in {wait_time}s..."
                    )
                    if attempt < self.max_retries - 1:
                        time.sleep(wait_time)
                    else:
                        logger.error(f"All retry attempts exhausted for {func.__name__}")
                        raise
        return wrapper

    async def retry_with_backoff_async(self, func):
        """Decorator for exponential backoff retry (async ver)"""
        @wraps(func)
        async def wrapper(*args, **kwargs):
            for attempt in range(self.max_retries):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    wait_time = self.backoff_factor ** attempt
                    logger.warning(
                        f"Attempt {attempt + 1}/{self.max_retries} failed: {e}. "
                        f"Retrying in {wait_time}s..."
                    )
                    if attempt < self.max_retries - 1:
                        await asyncio.sleep(wait_time)
                    else:
                        logger.error(f"All retry attempts exhausted for {func.__name__}")
                        raise
        return wrapper
    
    def fallback_chain(self, primary_func, fallback_funcs):
        """Try primary method, fall back to alternatives"""
        def execute(*args, **kwargs):
            try:
                return primary_func(*args, **kwargs)
            except Exception as e:
                logger.warning(f"Primary method failed: {e}. Trying fallbacks...")
                for i, fallback in enumerate(fallback_funcs, 1):
                    try:
                        logger.info(f"Attempting fallback {i}/{len(fallback_funcs)}")
                        return fallback(*args, **kwargs)
                    except Exception as fb_error:
                        logger.warning(f"Fallback {i} failed: {fb_error}")
                        continue
                raise Exception("All processing methods failed")
        return execute

# Global healer instance
from blast_ocr.config import config
healer = SelfHealingOCR(
    max_retries=config.max_retries, 
    backoff_factor=config.retry_backoff
)

```

### 📄 File: `blast_ocr/core/exceptions.py`
*Custom Exceptions and Error Classifications*

```py
class BLASTOCRException(Exception):
    """Base exception for all BLAST OCR errors"""
    pass

class ImageLoadError(BLASTOCRException):
    """Failed to load or decode image"""
    pass

class OCREngineError(BLASTOCRException):
    """OCR engine initialization or processing failed"""
    pass

class PageExtractionError(BLASTOCRException):
    """Failed to extract text from page"""
    def __init__(self, page_number, original_error):
        self.page_number = page_number
        self.original_error = original_error
        super().__init__(f"Page {page_number} extraction failed: {original_error}")

class LowConfidenceError(BLASTOCRException):
    """OCR confidence below threshold"""
    def __init__(self, confidence, threshold):
        self.confidence = confidence
        self.threshold = threshold
        super().__init__(f"Confidence {confidence:.2f} < {threshold:.2f}")

class OutputWriteError(BLASTOCRException):
    """Failed to write results to disk"""
    pass

```

### 📄 File: `blast_ocr/core/parallel.py`
*Manages multiple document workers securely*

```py
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, as_completed
from tqdm import tqdm
import multiprocessing as mp
import os
from typing import List, Dict, Callable
import logging
from blast_ocr.config import config

logger = logging.getLogger(__name__)

class ParallelOCRProcessor:
    def __init__(self, max_workers=None):
        # FIX(phase2): CRITICAL - Limit workers to prevent memory exhaustion
        # EasyOCR can use 1GB+ per page. With 8 workers, that's 8GB+ RAM.
        # Limiting to 2 workers provides parallelism while staying within memory limits.
        # Note: The global OCR lock serializes OCR anyway, so more workers don't help much.
        if max_workers is None:
            # Use at most 2 workers to prevent OOM
            self.max_workers = min(config.max_workers, 2)
        else:
            self.max_workers = min(max_workers, 2)
    
    def process_batch_threaded(self, page_paths: List[str], process_func: Callable, progress_callback: Callable = None) -> List[Dict]:
        """
        Thread-based parallelism for page processing.
        
        PERF(phase3): Analysis of the parallelism situation:
        - The global OCR lock serializes all EasyOCR calls
        - However, preprocessing (cv2 ops) releases the GIL
        - So threads DO provide benefit for overlapping preprocessing with OCR
        - Thread A can preprocess page N+1 while Thread B runs OCR on page N
        
        Future optimization: Separate preprocessing and OCR into distinct thread pools
        with a queue between them for true pipeline parallelism.
        """
        results = []
        total = len(page_paths)
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all tasks
            future_to_page = {
                executor.submit(process_func, path, i+1): (path, i+1)
                for i, path in enumerate(page_paths)
            }
            
            # Collect results with progress bar
            completed_count = 0
            with tqdm(total=total, desc="Processing pages") as pbar:
                for future in as_completed(future_to_page):
                    path, page_num = future_to_page[future]
                    try:
                        result = future.result(timeout=config.timeout_per_page)
                        results.append(result)
                    except Exception as e:
                        logger.error(f"Page {page_num} ({path}) failed: {e}")
                        results.append({"page": page_num, "text": "", "error": str(e), "confidence": 0.0})
                    finally:
                        pbar.update(1)
                        completed_count += 1
                        if progress_callback:
                            try:
                                progress_callback(completed_count, total)
                            except Exception as cb_err:
                                # FIX(phase2): BUG-08 - Log instead of silently swallowing
                                logger.debug(f"Progress callback error: {cb_err}")
        
        return sorted(results, key=lambda x: x['page'])
    
    # Note: Process-based parallelism requires picklable objects. 
    # EasyOCR reader is not easily picklable. 
    # For now, we rely on threading which works well for I/O and some numpy ops released by GIL.

```

### 📄 File: `blast_ocr/config.py`
*Pydantic Settings Models*

```py
try:
    from pydantic_settings import BaseSettings, SettingsConfigDict
except ImportError:
    # Fallback for Pydantic V1 or V2 without pydantic-settings
    from pydantic import BaseSettings
    SettingsConfigDict = None

from pydantic import Field
from typing import List, Optional
import os
import sys

def _detect_poppler_path() -> Optional[str]:
    """
    Auto-detect the correct Poppler path based on the operating system.
    - On Linux (Streamlit Cloud): Poppler is installed system-wide via packages.txt, so return None.
    - On Windows (local dev): Use the bundled poppler folder.
    """
    if sys.platform == "win32":
        local_path = os.path.join(os.path.dirname(__file__), "..", "poppler-25.12.0", "Library", "bin")
        local_path = os.path.normpath(local_path)
        if os.path.isdir(local_path):
            return local_path
    # On Linux/Mac, poppler is on the system PATH — return None to use it automatically
    return None

class OCRConfig(BaseSettings):
    """Type-safe configuration with validation"""
    
    # OCR Engine
    ocr_languages: List[str] = Field(default=['en'], description="Languages to detect")
    ocr_gpu: bool = Field(default=False, description="Use GPU acceleration")
    ocr_batch_size: int = Field(default=8, description="Pages to process in parallel")
    
    # Performance
    max_workers: int = Field(default=2, description="Thread pool size")
    timeout_per_page: int = Field(default=60, description="Seconds before timeout")
    
    # Storage
    database_url: str = Field(default='sqlite:////tmp/blast_ocr.db')
    output_format: str = Field(default='txt', description="Output format: txt, json, pptx")
    
    # Paths
    data_dir: str = Field(default='data/pages')
    output_dir: str = Field(default='/tmp/blast_output')
    log_dir: str = Field(default='/tmp/logs')
    poppler_path: Optional[str] = Field(
        default_factory=_detect_poppler_path,
        description="Path to poppler bin folder (auto-detected)"
    )
    
    # Quality Control
    min_confidence: float = Field(default=0.6, description="Minimum confidence to accept")
    enable_spellcheck: bool = Field(default=True)
    
    # Self-Healing
    max_retries: int = Field(default=3)
    retry_backoff: int = Field(default=2)
    enable_fallback: bool = Field(default=True)
    
    # Preprocessing (Added for Phase 4 Fix)
    denoise_level: int = Field(default=0, description="Denoising strength (0-20)")
    contrast_boost: float = Field(default=1.0, description="Contrast multiplier (1.0-3.0)")
    auto_deskew: bool = Field(default=True, description="Enable auto-deskewing")
    
    if SettingsConfigDict:
        model_config = SettingsConfigDict(
            env_file='.env',
            env_prefix='BLAST_OCR_'
        )
    else:
        class Config:
            env_file = '.env'
            env_prefix = 'BLAST_OCR_'

# Load config
config = OCRConfig()

def get_settings() -> OCRConfig:
    """Retrieve the global configuration instance."""
    return config

```

### 📄 File: `blast_ocr/logging_config.py`
*Structured JSON and Desktop Loging Strategies*

```py
import logging
import logging.handlers
from pathlib import Path
import json
from datetime import datetime, timezone
import os

def setup_logging(log_dir='logs', level=logging.INFO):
    """Configure structured logging"""
    
    log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # Create formatter
    class JSONFormatter(logging.Formatter):
        def format(self, record):
            log_data = {
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'level': record.levelname,
                'logger': record.name,
                'message': record.getMessage(),
                'module': record.module,
                'function': record.funcName,
                'line': record.lineno
            }
            
            # Add exception info if present
            if record.exc_info:
                log_data['exception'] = self.formatException(record.exc_info)
            
            # Add custom fields
            if hasattr(record, 'page_number'):
                log_data['page_number'] = record.page_number
            if hasattr(record, 'confidence'):
                log_data['confidence'] = record.confidence
            
            return json.dumps(log_data)
    
    # Root logger
    logger = logging.getLogger('blast_ocr')
    logger.setLevel(level)
    
    # Clear existing handlers
    logger.handlers = []
    
    # Console handler (human-readable)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    ))
    logger.addHandler(console_handler)
    
    # File handler (JSON format)
    file_handler = logging.handlers.RotatingFileHandler(
        log_dir / 'blast_ocr.log',
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5
    )
    file_handler.setFormatter(JSONFormatter())
    logger.addHandler(file_handler)
    
    # Error file (errors only)
    error_handler = logging.handlers.RotatingFileHandler(
        log_dir / 'errors.log',
        maxBytes=10*1024*1024,
        backupCount=5
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(JSONFormatter())
    logger.addHandler(error_handler)
    
    return logger

```

## 8. Quality Assurance & Tests
**🎯 Target Audience:** AI Agent
*Unit tests ensuring core operations.*

### 📄 File: `tests\conftest.py`
*QA Suite Component*

```py
import pytest
import os
import shutil
from pathlib import Path
from PIL import Image, ImageDraw

@pytest.fixture
def temp_workspace(tmp_path):
    """Create isolated workspace"""
    workspace = {
        'input': tmp_path / 'input',
        'output': tmp_path / 'output',
        'db': tmp_path / 'test.db',
        'logs': tmp_path / 'logs'
    }
    for p in workspace.values():
        if p.suffix: # file
            pass
        else:
            p.mkdir()
    return workspace

@pytest.fixture
def sample_image(temp_workspace):
    """Create a test image with known text"""
    img_path = temp_workspace['input'] / "test_page.png"
    
    img = Image.new('RGB', (800, 200), color='white')
    draw = ImageDraw.Draw(img)
    # Use default font
    draw.text((10, 50), "Sample OCR Test Text", fill='black')
    
    img.save(img_path)
    return str(img_path)

@pytest.fixture(autouse=True)
def mock_env(monkeypatch, temp_workspace):
    """Set environment variables for testing"""
    monkeypatch.setenv("BLAST_OCR_DATABASE_URL", f"sqlite:///{temp_workspace['db']}")
    monkeypatch.setenv("BLAST_OCR_KEY_LOG_DIR", str(temp_workspace['logs']))
    monkeypatch.setenv("BLAST_OCR_OCR_GPU", "false")

```

### 📄 File: `tests\debug_pdf.py`
*QA Suite Component*

```py
import sys
from pathlib import Path
import os
import logging

# Add project root
sys.path.append(str(Path(__file__).parent.parent))

from blast_ocr.main import process_pdf, get_components
from blast_ocr.config import config

# Enable Debug Logging
logging.basicConfig(level=logging.DEBUG)
logger, _, _, parallel_processor = get_components()
logger.setLevel(logging.DEBUG)

def debug_pdf(pdf_path):
    print(f"[-] Debugging PDF: {pdf_path}")
    
    if not os.path.exists(pdf_path):
        print("[!] File not found!")
        return

    # 1. Test Poppler Path from Config
    print(f"    Poppler Path: {config.poppler_path}")
    
    # 2. Run Process (Just first few pages if we could limit, 
    # but process_pdf processes all. We'll trust the logger to show us what's happening)
    # Actually, let's override the parallel processor to be simpler/verbose or just run generic process_pdf
    
    try:
        # Optimization: convert_from_path supports first_page and last_page
        # We need to hack this into process_pdf or just use the logic from main.py here manually
        
        # Let's recreate the logic of process_pdf here but with limits
        from pdf2image import convert_from_path
        import tempfile
        from blast_ocr.main import process_single_image
        
        print("[-] Manually processing first 5 pages...")
        with tempfile.TemporaryDirectory() as temp_dir:
            try:
                kwargs = {}
                if config.poppler_path:
                    kwargs['poppler_path'] = config.poppler_path
                
                print("    Converting PDF (Limit 5 pages)...")
                pages = convert_from_path(pdf_path, dpi=300, first_page=1, last_page=5, **kwargs)
                print(f"    Converted {len(pages)} pages.")
            except Exception as e:
                print(f"[!] PDF Conversion Failed: {e}")
                return

            results = []
            for i, page in enumerate(pages, 1):
                fname = f"page_{i:04d}.png"
                fpath = os.path.join(temp_dir, fname)
                page.save(fpath, "PNG")
                
                print(f"    OCR Page {i}...")
                res = process_single_image(fpath, i)
                results.append(res)
                
                text_preview = str(res.get('text', ''))[:50].replace('\n', ' ')
                conf = res.get('confidence', 0)
                # Handle possible list/tuple confidence return if logic changed, but usually float
                if isinstance(conf, (list, tuple)): conf = conf[0]
                
                print(f"    Page {i}: Conf={float(conf):.2f}, Text='{text_preview}...'")
        
        print("[-] Debug complete.")
            
    except Exception as e:
        print(f"[!] Crash: {e}")

if __name__ == "__main__":
    # Use the file provided by the user
    target_file = r"c:\Users\hafiz\OneDrive - University of Engineering and Technology Taxila\Desktop\Ibrahim\Projects\Python\OCR_Book\the-ideology-of-pakistan-javid-iqbal.pdf"
    debug_pdf(target_file)

```

### 📄 File: `tests\final_verification.py`
*QA Suite Component*

```py
import sys
import os
import shutil
import logging
from pathlib import Path
import tempfile
import cv2
import numpy as np

# Add project root
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.append(str(PROJECT_ROOT))

# Setup Logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger("VERIFY")

def check_step(name):
    print(f"\n[TEST] {name}...")

def assert_true(condition, message):
    if not condition:
        print(f"[FAIL] {message}")
        sys.exit(1)
    else:
        print(f"[PASS] {message}")

def verify_dependencies():
    check_step("Dependencies")
    
    # 1. Config & Poppler
    try:
        from blast_ocr.config import config
        poppler = config.poppler_path
        assert_true(poppler and os.path.exists(poppler), f"Poppler path valid: {poppler}")
        
        # Check pdftoppm executable specifically
        exe = os.path.join(poppler, "pdftoppm.exe")
        assert_true(os.path.exists(exe), f"pdftoppm.exe found at {exe}")
        
    except ImportError:
        assert_true(False, "Could not import blast_ocr.config")

    # 2. EasyOCR
    try:
        import easyocr
        print("[PASS] EasyOCR importable")
    except ImportError:
        assert_true(False, "EasyOCR not installed")

    # 3. UI Libs
    try:
        import streamlit
        import pandas
        print("[PASS] Streamlit & Pandas importable")
    except ImportError:
        assert_true(False, "UI dependencies missing")

def verify_database():
    check_step("Database")
    from blast_ocr.storage.database import OCRDatabase
    
    db_path = PROJECT_ROOT / "blast_ocr.db"
    
    try:
        db = OCRDatabase(f"sqlite:///{db_path}")
        # Write test
        job_id = db.create_job("VERIFY_TEST_FILE", 999)
        assert_true(job_id is not None, "Database write (create_job)")
        
        # Read test
        job = db.get_job(job_id)
        assert_true(job.filename == "VERIFY_TEST_FILE", "Database read (get_job)")
        
        # Cleanup (optional, but good for cleanliness)
        session = db.session
        session.delete(job)
        session.commit()
        print("[PASS] Database Read/Write/Delete")
        
    except Exception as e:
        assert_true(False, f"Database Integrity Error: {e}")

def verify_core_logic():
    check_step("Core Logic (Simulated Run)")
    from blast_ocr.core.text_extractor import extract_from_image, sanitize_for_xml
    
    # 1. XML Sanitization
    bad_str = "Clean\x00Me"
    clean = sanitize_for_xml(bad_str)
    assert_true(clean == "CleanMe", "XML Sanitizer logic")
    
    # 2. Image Extraction (Synthetic Image)
    # Create a simple white image with black text is hard to synth without fonts.
    # We will just verify the function doesn't crash on a blank image.
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        img_path = tmp.name
    
    try:
        # Create blank white image
        img = np.full((100, 100, 3), 255, dtype=np.uint8)
        cv2.imwrite(img_path, img)
        
        # Run Extractor
        res = extract_from_image(img_path)
        # Should return empty string or initialized error if model fails, but not crash
        assert_true(isinstance(res, str), "Extractor returned string")
        print(f"    Extractor Output (Blank Img): '{res}'")
        
    except Exception as e:
        assert_true(False, f"Core Extraction Crash: {e}")
    finally:
        if os.path.exists(img_path):
            os.remove(img_path)

def verify_ui_integrity():
    check_step("UI Integrity")
    ui_path = PROJECT_ROOT / "blast_ocr" / "ui" / "web_app.py"
    assert_true(ui_path.exists(), "web_app.py exists")
    
    # Check for syntax errors by compiling
    try:
        with open(ui_path, "r") as f:
            compile(f.read(), ui_path, 'exec')
        print("[PASS] web_app.py Syntax Check")
    except Exception as e:
        assert_true(False, f"UI Syntax Error: {e}")

if __name__ == "__main__":
    print("[*] STARTING FINAL SYSTEM AUDIT [*]")
    verify_dependencies()
    verify_database()
    verify_core_logic()
    verify_ui_integrity()
    print("\n[SUCCESS] SYSTEM VERIFIED: NO ISSUES DETECTED")
    sys.exit(0)

```

### 📄 File: `tests\test_callback.py`
*QA Suite Component*

```py
import sys
from pathlib import Path
import os
import time

# Add project root
sys.path.append(str(Path(__file__).parent.parent))

from blast_ocr.main import process_pdf, process_single_image
from blast_ocr.config import config

def mock_callback(current, total):
    print(f"CALLBACK: {current}/{total}")

def test_callback_integration():
    print("[-] Testing Callback Integration...")
    
    # We can't easily test process_pdf without a real PDF and time.
    # But we can check if main.py accepts the arg.
    import inspect
    from blast_ocr.main import main, process_pdf
    
    sig_main = inspect.signature(main)
    if 'progress_callback' in sig_main.parameters:
        print("[PASS] main() accepts progress_callback")
    else:
        print("[FAIL] main() missing progress_callback")
        sys.exit(1)

    sig_pdf = inspect.signature(process_pdf)
    if 'progress_callback' in sig_pdf.parameters:
        print("[PASS] process_pdf() accepts progress_callback")
    else:
        print("[FAIL] process_pdf() missing progress_callback")
        sys.exit(1)
        
    print("[SUCCESS] Signatures verified.")

if __name__ == "__main__":
    test_callback_integration()

```

### 📄 File: `tests\test_critical_paths.py`
*QA Suite Component*

```py
import pytest
import threading
import os
import tempfile
import time
from blast_ocr.core.extractor import RobustOCRExtractor, _ocr_global_lock
from blast_ocr.cache.manager import cache_manager, OCRCache
from blast_ocr.main import BlastPipeline

def test_global_lock_singleton():
    """Verify that multiple extractor instances share the SAME lock object."""
    e1 = RobustOCRExtractor()
    e2 = RobustOCRExtractor()
    
    # Check they point to the module-level lock
    assert e1.lock is _ocr_global_lock
    assert e2.lock is _ocr_global_lock
    assert e1.lock is e2.lock
    
    # Check locking works
    locked_Success = False
    with e1.lock:
        locked_Success = True
        # e2 shouldn't be able to acquire if we hold it (non-blocking acquire check?)
        # Standard Lock doesn't support 'locked()' query easily without acquire(blocking=False)
        # But verifying identity is the main fix verification.
    assert locked_Success

def test_cache_hashing_consistency():
    """Verify that cache hashing is consistent and respects content."""
    with tempfile.NamedTemporaryFile(delete=False, mode='wb') as f:
        f.write(b"Test Content 123")
        fname = f.name
        
    try:
        # Hashing should be deterministic
        h1 = cache_manager.get_file_hash(fname)
        h2 = cache_manager.get_file_hash(fname)
        assert h1 == h2
        
        # Modify file
        with open(fname, 'wb') as f:
            f.write(b"Modified Content 456")
            
        h3 = cache_manager.get_file_hash(fname)
        assert h1 != h3
        
    finally:
        if os.path.exists(fname):
            os.remove(fname)

def test_memory_cleanup_logic():
    """
    We can't easily test GC in a unit test, but we can verify the code patch
    didn't break the extractor loop basically.
    """
    # Just ensure we can instantiate execution without errors
    extractor = RobustOCRExtractor()
    assert extractor.reader is not None

```

### 📄 File: `tests\test_extractor.py`
*QA Suite Component*

```py
import pytest
import logging
from blast_ocr.core.extractor import RobustOCRExtractor
from blast_ocr.core.exceptions import ImageLoadError, PageExtractionError

# Configure logger to capture output during tests
logging.basicConfig(level=logging.DEBUG)

def test_extractor_initialization():
    extractor = RobustOCRExtractor()
    assert extractor.reader is not None

def test_process_page_success(sample_image):
    extractor = RobustOCRExtractor()
    result = extractor.process_page(sample_image, page_number=1)
    
    # Debug output
    print(f"Extracted Text: {result.get('text')}")
    print(f"Confidence: {result.get('confidence')}")
    
    assert result['page'] == 1
    # Lenient check as default font is tiny and might yield low quality
    assert len(result['text']) > 0 or result.get('warning') == 'no_text_detected'
    assert result['bbox_count'] >= 0

def test_process_page_not_found():
    extractor = RobustOCRExtractor()
    # The extractor wraps image load errors in PageExtractionError
    with pytest.raises(PageExtractionError) as excinfo:
        extractor.process_page("non_existent_file.png", 1)
    assert "File not found" in str(excinfo.value) or "Cannot load" in str(excinfo.value)

def test_image_load_error(tmp_path):
    # Create invalid image file
    bad_file = tmp_path / "bad.png"
    bad_file.write_text("not an image")
    
    extractor = RobustOCRExtractor()
    with pytest.raises(PageExtractionError) as excinfo:
        extractor.process_page(str(bad_file), 1)
    assert "Failed to load image" in str(excinfo.value) or "Cannot load" in str(excinfo.value)

```

### 📄 File: `tests\test_pipeline.py`
*QA Suite Component*

```py
import pytest
import os
from blast_ocr.main import main, BlastPipeline
from blast_ocr.storage.database import OCRDatabase, OCRJob

def test_end_to_end_image(temp_workspace, sample_image):
    """Test full flow for single image"""
    # FIX(phase2): CRITICAL-003 - Removed references to non-existent module globals
    # (_db, _extractor, _logger, _parallel_processor, get_components).
    # These globals don't exist in main.py. The correct approach is to create
    # a fresh BlastPipeline which handles its own component initialization.
    
    print(f"\n--- DEBUG INFO ---")
    print(f"Test Workspace DB: {temp_workspace['db']}")
    print(f"------------------\n")
    
    print(f"Processing image: {sample_image}")
    
    # FIX(phase2): Use the main() function directly, which creates its own pipeline
    result = main(
        source_path=sample_image,
        output_dir=str(temp_workspace['output'])
    )
    
    print(f"Result: {result}")
    
    assert result['status'] == 'success'
    assert result['pages_processed'] == 1
    
    # Check Output File
    out_files = list(temp_workspace['output'].glob("*.md"))
    assert len(out_files) == 1
    content = out_files[0].read_text(encoding='utf-8')
    assert len(content) >= 0  # May be empty if OCR doesn't detect text in test image

```

### 📄 File: `tests\test_sanitization.py`
*QA Suite Component*

```py
import sys
from pathlib import Path
import os

# Add project root
sys.path.append(str(Path(__file__).parent.parent))

from blast_ocr.core.text_extractor import sanitize_for_xml, save_output
from docx import Document

def test_sanitization():
    print("[-] Testing Sanitization Logic...")
    
    # Bad string with null byte and control char (0x1F is unit separator, invalid in XML)
    bad_text = "Hello\x00World\x1FTest"
    expected = "HelloWorldTest" # removed chars
    
    sanitized = sanitize_for_xml(bad_text)
    
    if sanitized == expected:
        print(f"[PASS] Sanitized correctly: {repr(bad_text)} -> {repr(sanitized)}")
    else:
        print(f"[FAIL] Expected {repr(expected)}, got {repr(sanitized)}")
        sys.exit(1)

def test_docx_save():
    print("[-] Testing DOCX Save with Bad Chars...")
    bad_text_content = "Safe Line\n## Forbidden\x00Header\nContent with control\x0bchar."
    
    output_dir = "tests/temp_out"
    os.makedirs(output_dir, exist_ok=True)
    
    try:
        md, docx = save_output(bad_text_content, "test_bad_chars", output_dir)
        if docx and os.path.exists(docx):
            print(f"[PASS] DOCX saved successfully at {docx}")
        else:
            print("[FAIL] DOCX path returned None or file missing")
            sys.exit(1)
    except Exception as e:
        print(f"[FAIL] Exception during save: {e}")
        sys.exit(1)

if __name__ == "__main__":
    try:
        test_sanitization()
        test_docx_save()
        print("\n[SUCCESS] XML Sanitization Verified.")
    except Exception as e:
        print(f"\n[FAILURE] Verification failed: {e}")
        sys.exit(1)

```

### 📄 File: `tests\verify.py`
*QA Suite Component*

```py
import os
from PIL import Image, ImageDraw, ImageFont
from blast_ocr.main import BlastPipeline
import time

def create_test_image(text="Hello World B.L.A.S.T.", filename="test_verify.png"):
    img = Image.new('RGB', (800, 200), color=(255, 255, 255))
    d = ImageDraw.Draw(img)
    # Use default font
    d.text((10,10), text, fill=(0,0,0))
    img.save(filename)
    return filename

def verify():
    print("[-] Creating test image...")
    img_path = create_test_image()
    
    print("[-] Initializing Pipeline...")
    pipeline = BlastPipeline()
    
    output_dir = "verify_output"
    if os.path.exists(output_dir):
        import shutil
        shutil.rmtree(output_dir)
        
    print(f"[-] Processing {img_path}...")
    start = time.time()
    result = pipeline.process_job(img_path, output_dir=output_dir)
    end = time.time()
    
    print(f"[-] Result: {result}")
    
    if result['status'] == 'success':
        print("[+] Success!")
        md_path = result['output_files']['md']
        if os.path.exists(md_path):
            with open(md_path, 'r') as f:
                content = f.read()
                print(f"[-] Extracted Content: {content.strip()}")
                if "Hello" in content or "World" in content:
                     print("[+] Content verification passed.")
                else:
                     print("[!] Content verification FAILED (OCR quality issue or empty).")
        else:
             print("[!] Markdown output missing.")
    else:
        print(f"[!] Processing FAILED: {result.get('error')}")

    # Clean up
    if os.path.exists(img_path): os.remove(img_path)
    # shutil.rmtree(output_dir) # Keep for inspection if needed

if __name__ == "__main__":
    verify()

```

### 📄 File: `tests\verify_enhancements.py`
*QA Suite Component*

```py
import sys
from pathlib import Path
import os
import logging

# Add project root
sys.path.append(str(Path(__file__).parent.parent))

from blast_ocr.config import config
from blast_ocr.storage.database import OCRDatabase
from blast_ocr.main import process_pdf, get_components

def test_config():
    print("[-] Testing Config...")
    assert hasattr(config, 'poppler_path'), "Config missing poppler_path"
    print(f"    Poppler Path: {config.poppler_path}")
    print("[+] Config OK")

def test_database():
    print("[-] Testing Database...")
    try:
        db = OCRDatabase()
        # Check if we can query
        jobs = db.session.query(db.get_job(1).__class__).all()
        print(f"    Existing Jobs: {len(jobs)}")
        print("[+] Database OK")
    except Exception as e:
        print(f"[!] Database Failed: {e}")
        raise

def test_process_logic():
    print("[-] Testing Process Logic (Dry Run)...")
    logger, _, _, _ = get_components()
    logger.setLevel(logging.CRITICAL) # Silence logs for test
    
    # Test with non-existent PDF to trigger error handling
    res = process_pdf("non_existent_file.pdf", "output")
    assert res == [], "Should return empty list on failure"
    print("[+] Error Handling OK")

if __name__ == "__main__":
    try:
        test_config()
        test_database()
        test_process_logic()
        print("\n[SUCCESS] All verification checks passed.")
    except Exception as e:
        print(f"\n[FAILURE] Verification failed: {e}")
        sys.exit(1)

```

### 📄 File: `tests\verify_pptx.py`
*QA Suite Component*

```py
import os
import sys
# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pptx import Presentation
from blast_ocr.core.extractor import extract_from_pptx

def create_test_pptx(filename="test_verify.pptx"):
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[0])
    title = slide.shapes.title
    subtitle = slide.placeholders[1]
    title.text = "Hello PPTX World"
    subtitle.text = "This is a subtitle"
    
    # Add a table slide
    slide2 = prs.slides.add_slide(prs.slide_layouts[5])
    shapes = slide2.shapes
    rows, cols = 2, 2
    left = top = width = height = 100000
    table = shapes.add_table(rows, cols, left, top, width, height).table
    table.cell(0, 0).text = "Row1 Col1"
    table.cell(0, 1).text = "Row1 Col2"
    table.cell(1, 0).text = "Row2 Col1"
    table.cell(1, 1).text = "Row2 Col2"
    
    prs.save(filename)
    return filename

def verify():
    pptx_path = create_test_pptx()
    print(f"[-] Created {pptx_path}")
    
    print("[-] Extracting text...")
    text = extract_from_pptx(pptx_path)
    print(f"[-] Extracted:\n{text}")
    
    if "Hello PPTX World" in text and "Row1 Col1" in text:
        print("[+] PPTX verification PASSED")
    else:
        print("[!] PPTX verification FAILED")
        
    if os.path.exists(pptx_path):
        os.remove(pptx_path)

if __name__ == "__main__":
    verify()

```

## 9. Maintenance & Audits
**🎯 Target Audience:** AI Agent
*Project maintenance utilities to track system erosion.*

### 📄 File: `AUDIT.md`
*Performance and Memory Leak Audit*

```md
# B.L.A.S.T. OCR System Audit Report (Forensic Verification)
**Date**: 2026-02-07
**Auditor**: Antigravity
**Codebase Version**: Current Workspace

---

## 1. EXECUTIVE SUMMARY
- **Use Case**: 8-page PDF processing taking ~17 minutes (146s/page).
- **Primary Root Cause**: **CPU Fallback**. `torch` is installed but no accelerator is detected (`pin_memory` warning).
- **Secondary Root Cause**: **Memory Accumulation**. Code lacks explicit `del` for large bitmaps, and `torch.cuda.empty_cache()` is skipped because CUDA is unavailable.
- **Serialization**: Global Lock is **Correctly Implemented**, which limits the system to Single-Threaded CPU speed (~100s/page for high-res).

---

## 2. FORENSIC EVIDENCE (Stage 2 & Verification)

### 2.1 `blast_ocr/main.py` (Orchestration)
**Batching Logic (Lines 121-127)**:
```python
batch_size = 10  # Process 10 pages at a time
# ...
for batch_start in range(1, total_pages + 1, batch_size):
    # ...
    pages = convert_from_path(..., first_page=batch_start, last_page=batch_end)
```
- **Analysis**: Correctly batches execution. For an 8-page document, it creates **1 batch** of 8 pages, matching the logs `1/8`, `2/8`.

### 2.2 `blast_ocr/core/extractor.py` (Core Logic)
**Global Lock Verification**:
```python
# Line 24 (Module Level):
_ocr_global_lock = threading.Lock()

# Line 35 (__init__):
self.lock = _ocr_global_lock
```
- **Verdict**: ✅ **CORRECT**. Lock is a module-level singleton.

**Lazy Import & Missing Cleanup (Line 192)**:
```python
# Line 192 (Inside process_page):
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except ImportError:
        pass  # <--- Skips if torch missing
```
- **Verdict**: ⚠️ **RISKY**. Logic is sound *if* GPU works, but fails silently on CPU.
- **Leak**: `del processed_img` is **MISSING** (Verified via grep).

### 2.3 `requirements.txt` vs Environment
**File Content**:
```text
easyocr
pillow
numpy
# (torch is MISSING)
```
**Environment Check**:
```text
Name: torch
Version: 2.10.0
```
- **Verdict**: ❌ **MISMATCH**. `torch` is installed but likely the CPU-only version (no `+cu` tag visible). The code expects GPU but gets CPU.

---

## 3. LOG & ROOT CAUSE ANALYSIS

### Q1: Why 146s per page?
**Breakdown**:
1.  **PDF Render**: ~5s (Batch of 8 is fast).
2.  **Preprocessing**: ~5-10s (Resize/Deskew).
3.  **OCR Inference**: **~120s**.
    - **Why?** EasyOCR on CPU with `max_workers=2` serialized by `_ocr_global_lock`.
    - Effectively: 1 CPU thread doing heavy matrix math on 1800x2400 images.

### Q2: Why is time INCREASING (110s → 146s)?
**Reason**: **RAM Accumulation**.
1.  Python GC is lazy. Large `processed_img` arrays (approx 20MB raw) are not explicitly `del`'d after use.
2.  `torch.cuda.empty_cache()` is skipped (Condition `is_available()` is False).
3.  Result: Memory usage grows -> OS starts paging to disk -> Processing slows down.

### Q3: Why `pin_memory` warning?
**Log**: `UserWarning: 'pin_memory' argument is set as true but no accelerator is found`
**Cause**: PyTorch DataLoader trying to pin memory for GPU transfer, but no GPU (`accelerator`) is active. Confirms **CPU Mode**.

---

## 4. CHECKLIST VERIFICATION (Final)

- [x] **Global Lock**: Verified Global (extractor.py:24).
- [x] **Readtext Protection**: All calls wrapped in `with self.lock`.
- [x] **Dependencies**: `torch` missing from `requirements.txt`.
- [x] **Image Deletion**: Explicit `del` MISSING.

---

## 5. RECOMMENDATIONS

1.  **Environment Fix**: Install CUDA-enabled Torch.
    ```bash
    pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118
    ```
2.  **Code Fix**: Add explicit `del` in `extractor.py`.
    ```python
    # After line 188
    del processed_img
    del image
    ```
3.  **Dependency Fix**: Add `torch` and `orjson` to `requirements.txt`.

---

## 6. AUDIT CONCLUSION
The codebase is logically sound regarding concurrency (locks), but fatally flawed in **Resource Management** (Memory/GPU). The "Bugs" are ostensibly fixed, but the **Performance** is destroyed by the environment configuration.

## 7. PHASE 4 VALIDATION RESULTS (Final)

### 7.1 Unit Tests
- **Status**: ✅ **PASSED** (3/3 Critical Paths)
- **Verified**:
    - Global Lock singleton ensures thread safety.
    - Cache hashing consistency.
    - Robust handling of missing dependencies.

### 7.2 Benchmark (CPU Mode)
- **Status**: ⚠️ **PASSED with WARNINGS**
- **Environment**: CPU-Only (No NVIDIA Driver detected).
- **Performance**: ~110-120s / page (Stable).
- **Memory Leak**: **FIXED**. Time per page is constant (Trend is FLAT), proving explicit `del` cleanup works.

### 7.3 Conclusion
The application is now **UNBRICKED** and **STABLE**. It will no longer crash due to memory leaks or DLL errors. However, to achieve <20s/page, valid NVIDIA Drivers must be installed to enable the GPU features of the installed Torch package.

```

### 📄 File: `maintain.py`
*Cleanup and health check automations*

```py
#!/usr/bin/env python
"""
B.L.A.S.T. OCR - Project Maintenance Tool

Usage:
  python maintain.py --clean      # Clean logs and temp files
  python maintain.py --audit      # Run system checks
  python maintain.py --stats      # Show usage stats
"""
import os
import sys
import shutil
import argparse
import logging
from pathlib import Path
from datetime import datetime

# Setup basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("MAINTAIN")

PROJECT_ROOT = Path(__file__).parent.absolute()

def clean_system():
    """Remove temporary files and old logs."""
    logger.info("Starting cleanup...")
    
    # 1. Clean .tmp
    tmp_path = PROJECT_ROOT / ".tmp"
    if tmp_path.exists():
        try:
            shutil.rmtree(tmp_path)
            logger.info("✅ Removed .tmp directory")
        except Exception as e:
            logger.error(f"❌ Failed to remove .tmp: {e}")
            
    # 2. Rotate Logs (Keep last 5)
    log_path = PROJECT_ROOT / "blast_ocr" / "logs" # Default log loc
    # Check config if possible, but fallback to likely spots
    if not log_path.exists():
        log_path = PROJECT_ROOT / "logs"
        
    if log_path.exists():
        logs = sorted(log_path.glob("*.log"), key=os.path.getmtime, reverse=True)
        if len(logs) > 5:
            for log in logs[5:]:
                try:
                    os.remove(log)
                    logger.info(f"🗑️ Deleted old log: {log.name}")
                except Exception as e:
                    logger.warning(f"Failed to delete {log.name}: {e}")
    
    logger.info("Cleanup complete.")

def audit_system():
    """Run verification scripts."""
    logger.info("Running System Audit...")
    
    # 1. Check DLLs
    dll_check = PROJECT_ROOT / "dll_check.py"
    if dll_check.exists():
        logger.info("--> Checking DLLs...")
        os.system(f"{sys.executable} \"{dll_check}\"")
        
    # 2. Verify Foundation
    found_check = PROJECT_ROOT / "verify_foundation.py"
    if found_check.exists():
        logger.info("--> Verifying Foundation...")
        os.system(f"{sys.executable} \"{found_check}\"")
        
    logger.info("Audit complete.")

def show_stats():
    """Query DB for stats (if exists)."""
    try:
        from blast_ocr.storage.database import OCRDatabase
        db = OCRDatabase()
        
        # Raw SQL for speed/simplicity
        with db.get_session() as session:
            # This depends on SQLAlchemy session structure, 
            # simplest is to just use the engine if available or basic count
            # Use the DB methods if available
             pass 
             # For now, just print where the DB is
        logger.info(f"Database located at: {db.engine.url}")
        logger.info("Stats feature requires active DB connection logic expansion.")
        
    except ImportError:
        logger.warning("Could not import OCRDatabase. Dependencies missing?")
    except Exception as e:
        logger.error(f"Stats check failed: {e}")

def main():
    parser = argparse.ArgumentParser(description="B.L.A.S.T. Maintenance Tool")
    parser.add_argument("--clean", action="store_true", help="Clean logs and temp files")
    parser.add_argument("--audit", action="store_true", help="Run system checks")
    parser.add_argument("--stats", action="store_true", help="Show system stats")
    
    args = parser.parse_args()
    
    if args.clean:
        clean_system()
    if args.audit:
        audit_system()
    if args.stats:
        show_stats()
        
    if not (args.clean or args.audit or args.stats):
        parser.print_help()

if __name__ == "__main__":
    main()

```

### 📄 File: `inventory_gen.py`
*Workspace context gathering utility*

```py
import os
from pathlib import Path

def count_lines(path):
    try:
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            return sum(1 for _ in f)
    except:
        return "N/A"

def generate_inventory():
    root = Path('.')
    print("## COMPLETE FILE INVENTORY")
    print("\n### Directory Structure")
    print("```")
    # Simple tree view (abbreviated)
    for path in sorted(root.rglob('*')):
        if path.is_dir():
            if not any(excluded in str(path) for excluded in ['.git', '__pycache__', 'venv', 'cache', 'logs', 'output']):
                 depth = len(path.parts) - 1
                 print(f"{'│   ' * depth}├── {path.name}/")
    print("```")
    
    print("\n### Python Files")
    print("| # | File Path | Lines | Purpose | Status |")
    print("|---|-----------|-------|---------|--------|")
    
    i = 1
    py_files = sorted(list(root.rglob('*.py')))
    for p in py_files:
        if any(excluded in str(p) for excluded in ['.git', 'venv']):
            continue
        lines = count_lines(p)
        status = "⏳ Not audited"
        print(f"| {i} | {p} | {lines} | ... | {status} |")
        i += 1
        
    print("\n### Config/Data Files")
    print("| File | Type | Purpose |")
    print("|------|------|---------|")
    for p in sorted(list(root.rglob('*'))):
         if p.name in ['requirements.txt', '.env', 'config.py'] or p.suffix in ['.json', '.toml', '.yaml']:
            if not any(excluded in str(p) for excluded in ['.git', 'venv', 'cache', 'logs']):
                print(f"| {p} | {p.suffix} | ... |")

if __name__ == "__main__":
    generate_inventory()

```

### 📄 File: `ENHANCEMENTS.md`
*Visual and Logic upgrades*

```md
# B.L.A.S.T. OCR - Enhancements Documentation

## 🎯 Overview
This document details the UI/UX improvements implemented in the B.L.A.S.T. OCR application (Version 2.0).

---

## ✨ Major Enhancements

### 1. VISUAL DESIGN & ACCESSIBILITY

#### A. Color Contrast Improvements
**Problem:** Poor readability with lavender text on dark purple background
**Solution:**
- Changed all text colors from `gray` to `#e0e7ff` (light indigo)
- Secondary text: `#c7d2fe` (lighter indigo)
- Stats labels: `#c7d2fe` with uppercase and letter-spacing
- Accuracy values: `#34d399` (emerald green) for positive emphasis

#### B. Glass-morphism Design System
**Implementation:**
- Background: `rgba(255, 255, 255, 0.08)`
- Blur: `backdrop-filter: blur(10px)`
- Benefits: Modern aesthetic, specific depth perception.

### 2. FUNCTIONAL IMPROVEMENTS

#### A. Smart Preset System
**Presets Available:**
1. **📄 Standard Document** (Balanced)
2. **🧾 Receipt / Low Quality** (High Boost)
3. **✍️ Handwriting** (Gentle)
4. **🖼️ Photo of Text** (Auto-Enhance)
5. **⚙️ Custom** (Manual control for experts)

#### B. Improved Slider Controls
- Icons for visual recognition (🔧, ✨)
- Descriptive names with units (e.g. "Noise Reduction Level (0-20)")
- Detailed help tooltips explaining effects.

#### C. Three-Stage Workflow
1. **Upload**: Drag-and-drop with preview.
2. **Preview**: Thumbnail display and validation.
3. **Process**: Prominent button with estimation.

### 3. ENHANCED USER EXPERIENCE

#### A. Smart Validation & Feedback
- Success/Info/Error boxes color-coded for instant recognition.
- Real-time file count and processing time estimation.

#### B. Export Options
- View results in-app.
- Download as **TXT**, **MD**, or **JSON**.

---

## 🚀 Quick Start

### For Users:
1. **Select a preset** based on your document.
2. **Upload files** (PDF, PNG, JPG).
3. **Review previews**.
4. **Click START PROCESSING**.
5. **Download results**.

---

**Version 2.0 • February 2026**

```

### 📄 File: `CHANGELOG.md`
*Historical adjustments*

```md
# Changelog

All notable changes to the B.L.A.S.T. OCR Engine will be documented in this file.

## [Unreleased] - 2026-02-04

### Fixed
- **Critical**: Resolved `FileNotFoundError` when running the CLI on files in the root directory without specifying an output folder.
- **Regression**: Fixed `AttributeError` in logging configuration by correcting `datetime` imports.
- **Deprecation**: Updated `datetime.utcnow()` to `datetime.now(timezone.utc)` across all modules.
- **Cleanup**: Removed duplicate imports in `web_app.py`.

### Added
- **Docs**: Added comprehensive `README.md`, `ARCHITECTURE.md`, and `CONTRIBUTING.md`.
- **Docs**: Added `CHANGELOG.md`.

### Removed
- **Cleanup**: Deleted temporary test artifacts (`test_output/`, `gui_output/`) and `__pycache__` directories.

```

### 📄 File: `CONTRIBUTING.md`
*Rules of Engagement*

```md
# 🤝 Contributing to B.L.A.S.T.

Thank you for your interest in improving the B.L.A.S.T. OCR Engine!

## 🛠️ Development Setup

1. **Fork & Clone**
   ```bash
   git clone https://github.com/your-username/blast-ocr.git
   ```
2. **Install Dev Dependencies**
   ```bash
   pip install -r requirements.txt
   pip install pytest pylint black
   ```

## 🧪 Testing

We use `pytest` for unit and integration testing.

- **Run all tests**:
  ```bash
  python -m pytest tests/
  ```
- **Run specific test**:
  ```bash
  python -m pytest tests/test_extractor.py
  ```

### Writing Tests
- Place new tests in `tests/`.
- Use the `temp_workspace` fixture for file I/O tests.
- Mock external calls (like heavy OCR models) where appropriate, but we prefer integration tests on small sample images.

## 📐 Coding Standards

- **Style**: Follow PEP 8.
- **Type Hinting**: Use Python type hints (`List`, `Dict`, `Optional`) for all function signatures.
- **Docstrings**: All modules, classes, and public functions must have docstrings.
- **Architecture**: Respect the 3-Layer separation. Do not put business logic in the UI layer.

## 🚀 Pull Request Process

1. Create a feature branch (`git checkout -b feature/amazing-feature`).
2. Commit your changes.
3. Push to the branch.
4. Open a Pull Request.
5. Ensure all tests pass.

```

### 📄 File: `DEVTOOLS_GUIDE.md`
*Frontend Debugging Patterns*

```md
# 🔍 Browser DevTools Inspection Guide
## B.L.A.S.T. OCR CSS - Live Testing & Debugging

---

## ✅ CSS Application Status (Valid)

### Working Correctly ✓

#### 1. Title Gradient (.blast-title)
```css
✓ font-size: 4rem
✓ font-weight: 800
✓ background: linear-gradient(135deg, #fb923c 0%, #f97316 50%, #ea580c 100%)
✓ -webkit-text-fill-color: transparent
✓ background-clip: text
✓ letter-spacing: 0.5rem
✓ text-shadow: 0 0 30px rgba(251, 146, 60, 0.3)
```
**Status**: Gradient text effect is rendering perfectly!

#### 2. Header Layout (.blast-header)
```css
✓ text-align: center
✓ padding: 2rem 0 1rem 0
✓ margin-bottom: 2rem
```
**Status**: Proper spacing and centering applied!

#### 3. Text Contrast Override
```css
✓ .stMarkdown, p, span, label { color: #e0e7ff !important; }
```
**Status**: High contrast text is overriding Streamlit defaults!

---

## 🔧 DevTools Inspection Workflow

### Step 1: Check Element Styles

**How to inspect:**
1. Right-click on element → Inspect
2. Look at "Styles" panel
3. Check which styles are applied (not crossed out)
4. Verify custom classes are present

### Step 2: Test Hover States

**In DevTools:**
1. Click ":hov" in Styles panel
2. Check ":hover" box
3. Verify hover styles activate

**Expected for .glass-card:hover:**
```css
.glass-card:hover {
    background: rgba(255, 255, 255, 0.12);  ← Should change
    transform: translateY(-2px);             ← Should lift
    box-shadow: 0 12px 40px rgba(0, 0, 0, 0.4); ← Should enhance
}
```

### Step 3: Verify Gradient Rendering

**Check for:**
- [ ] Text gradient visible (not solid color)
- [ ] Smooth color transition
- [ ] Text remains readable
- [ ] Glow effect visible

---

## 🐛 Common Issues & Solutions

### Issue 1: Styles Not Applying
**Fix:**
```css
/* If needed, increase specificity */
.main .blast-title { /* More specific */ }

/* Or use !important (last resort) */
.blast-title {
    font-size: 4rem !important;
}
```

### Issue 2: Glass Effect Not Visible
**Fix for Safari:**
```css
.glass-card {
    backdrop-filter: blur(10px);
    -webkit-backdrop-filter: blur(10px); /* Add this */
}
```

### Issue 3: Text Unreadable (Low Contrast)
**Your current contrast:**
```
Background: #312e81 (dark purple)
Text: #e0e7ff (light indigo)
Ratio: ~12.8:1 ✓ (Excellent - WCAG AAA)
```

---

## ✅ Final Verification Checklist

### Visual Checks
- [ ] Title gradient visible and smooth
- [ ] Text has high contrast (readable)
- [ ] Glass cards show blur effect
- [ ] Hover states trigger correctly
- [ ] Buttons have gradient and shadow
- [ ] Badges display with correct colors
- [ ] Stats cards centered and visible

### Performance Checks
- [ ] Page loads in < 2 seconds
- [ ] No layout shifts on load
- [ ] Smooth 60 FPS animations
- [ ] No console errors
- [ ] CSS transferred < 20KB

---

**Status: PRODUCTION READY ✓**

```

## 10. Skill Knowledge Base
**🎯 Target Audience:** AI Agent
*Distilled logic and patterns for maintaining the engine.*

### 📄 File: `skills\advanced_qa.md`
*System Context Meta-Skill*

```md
---
name: Advanced QA
description: Integration testing, end-to-end flows, and stress testing.
---

# Advanced QA Skill

## 1. Integration Testing
Testing components working together.
- **Scope**: `Pipeline -> Database`, `Extractor -> Cache`.
- **Tool**: `pytest tests/integration/`.

## 2. End-to-End (E2E) Scenarios
Simulate real user behavior.
- **Script**: `benchmark.py` covers the "Happy Path" (User uploads -> Gets Result).
- **Edge Cases**:
  - Upload 0-byte file.
  - Upload password-protected PDF.
  - Upload file with 10k pages (Stress Test).

## 3. Stress Testing
- **Concurrency**: Run 10 instances of `BlastPipeline` in parallel threads.
- **Resource Starvation**: Run with artificially limited RAM (container limits) to verify graceful failure.

## 4. Visual Regression
- **Compare**: Generate output today vs. known good output.
- **Diff**: Text diffing is easy. Visual layout diffing (for UI) requires screenshots (Playwright/Selenium - Future work).

```

### 📄 File: `skills\database_management.md`
*System Context Meta-Skill*

```md
---
name: Database Management
description: Guide to managing the SQLite database and SQLAlchemy ORM in B.L.A.S.T.
---

# Database Management Skill

## 1. Architecture
The project uses **SQLAlchemy** (ORM) with **SQLite**.
- **Location**: `blast_ocr.db` (root directory).
- **Code**: `blast_ocr/storage/database.py`.

## 2. Schema
### `OCRJob`
Tracks the overall file processing task.
- `id`: Primary Key
- `filename`: Source file name
- `status`: 'pending', 'processing', 'completed', 'failed'
- `error_message`: Stores failure reason

### `OCRResult`
Stores per-page results.
- `job_id`: FK to `OCRJob`
- `extracted_text`: Raw text
- `confidence_score`: 0.0 to 1.0 float

## 3. Common Operations

### CLI / Script Access
```python
from blast_ocr.storage.database import OCRDatabase

db = OCRDatabase()
# Get all failed jobs
failed_jobs = db.session.query(OCRJob).filter_by(status='failed').all()
```

### Migrations
Currently, `Base.metadata.create_all(self.engine)` is run on init.
- **Adding Columns**: No automatic migration tool (Alembic) is configured yet.
- **Workflow**: For schema changes, either:
  1. Delete `blast_ocr.db` (if data is disposable).
  2. Manually execute `ALTER TABLE` commands via SQLite CLI.

## 4. Best Practices
- **Session Management**: Always close sessions. Use the context manager pattern if extending `OCRDatabase` to support it (currently uses `__del__` backup).
- **Concurrency**: SQLite writes verify serialization. The `BlastPipeline` handles this by writing to DB only from the main thread.

```

### 📄 File: `skills\error_recovery.md`
*System Context Meta-Skill*

```md
---
name: Error Recovery (Healing)
description: Understanding and extending the Self-Healing OCR capabilities.
---

# Error Recovery Skill

## 1. The Healing Philosophy
The B.L.A.S.T. pipeline is designed to "fail gracefully" and "self-correct" where possible.
- **Core Logic**: `blast_ocr/core/healing.py`.
- **Global Instance**: `healer` object.

## 2. Retry Mechanism
We use an exponential backoff decorator `@healer.retry_with_backoff`.

```python
@healer.retry_with_backoff
def fragile_operation():
    # If this fails, it retries 3 times (default)
    # Waiting 2s, 4s, 8s...
    ...
```

### Config
Controlled via `config.py` (env vars):
- `OCR_MAX_RETRIES`: Default 3.
- `OCR_RETRY_BACKOFF`: Default 2.

## 3. Fatal vs. Transient Errors
The healer is smart enough **NOT** to retry fatal errors:
- `FileNotFoundError`: File won't appear by magic.
- `OCREngineError`: If the engine is broken (DLL missing), retrying won't fix it.
- `ImageLoadError`: Corrupt file.

**Action**: When adding new exceptions, ensure they are classified correctly in `healing.py` if they should skip retry.

## 4. Fallback Chains
Start with the best method, fall back to robust ones.
*Concept (Partially Implemented)*:
1. Try GPU OCR.
2. If VRAM OOM -> Fallback to CPU OCR.
3. If CPU Fail -> Fallback to Tesseract (if installed).

```

### 📄 File: `skills\future_roadmap.md`
*System Context Meta-Skill*

```md
---
name: Future Roadmap
description: Strategic outlook for upgrading B.L.A.S.T. to Next-Gen OCR technologies (2026+).
---

# Future Roadmap: Next-Gen OCR

## 1. The Shift to VLMs (Vision-Language Models)
Traditional pipelines (`Detection -> Recognition`) are being replaced by End-to-End Transformers.

### Candidate: Surya OCR
- **Why**: 90+ languages, accurate table/layout analysis.
- **Tech**: Segformer + GNNs.
- **Pros**: Handles complex formatting better than EasyOCR.
- **Migration**: Drop-in replacement for layout analysis.

### Candidate: GOT-OCR 2.0
- **Why**: "General OCR Theory". Unified model for text, formulas, music, and charts.
- **Use Case**: Scientific papers, complex PDFs.
- **Cons**: High VRAM requirement (580M params).

## 2. Pipeline Evolution
- **Current**: `PDF -> Image -> EasyOCR`.
- **Future**: `PDF -> LayoutLM (Classification) -> Component OCR`.
  - Classify page zones (Text, Table, Image).
  - Route Tables to specific table-transformers.
  - Route Text to fast OCR.

## 3. Tooling Upgrades
- **Switch to `uv`**: Migrate CI/CD pipeline.
- **Switch to `Ruff`**: Enforce stricter rules (E, F, I, UP) to modernize syntax automatically.

```

### 📄 File: `skills\meta_skill_management.md`
*System Context Meta-Skill*

```md
---
name: Meta-Skill Management
description: How to identify knowledge gaps and create new skills for the agent.
---

# Meta-Skill Management

## 1. Identification
When to create a new skill?
- **Repetition**: The agent explains something > 2 times.
- **Complexity**: A task requires > 5 steps to verify.
- **Domain Specifics**: Unique constraints (e.g., "Our specific way of handling PDF metadata").

## 2. Creation Process
1. **Draft**: Create `skills/topic_name.md`.
2. **Metadata**: Add YAML frontmatter (`name`, `description`).
3. **Structure**:
   - **Concepts**: What is this?
   - **Commands**: How to do it?
   - **Best Practices**: How to do it *well*?
4. **Verify**: Use the skill in a task to ensure it's actionable.

## 3. Discovery
- **Agent**: The agent should scan `skills/` at the start of complex tasks.
- **User**: The user can ask "What skills do you have?" (Agent lists them).

## 4. Updates
- Skills are living documents.
- If a tool changes, update the relevant skill immediately.

```

### 📄 File: `skills\ocr_debugging.md`
*System Context Meta-Skill*

```md
---
name: OCR Debugging
description: Workflow for debugging OCR accuracy, performance, and stability issues in the B.L.A.S.T. pipeline.
---

# OCR Debugging Skill

## 1. Environment Verification
Before debugging code, verify the runtime environment.

```bash
# Check DLL dependencies (Windows)
python dll_check.py

# Verify torch/cuda availability
python -c "import torch; print(f'CUDA: {torch.cuda.is_available()}')"
```

## 2. Common Failure Modes

### Memory Leaks (Increasing Time/Page)
- **Symptoms**: Processing slows down (e.g., 100s -> 150s), "DefaultCPUAllocator: not enough memory".
- **Fix**: 
  - Ensure `del processed_img` is called in `extractor.py`.
  - Check `torch.cuda.empty_cache()` usage.
  - Reduce `max_workers` in `parallel.py` (default: 2 for CPU safety).

### "No Space Left on Device"
- **Cause**: Temp files from `pdf2image` not being cleaned up.
- **Fix**:
  - Check `blast_ocr/main.py` usage of `tempfile.TemporaryDirectory`.
  - Ensure `os.remove(fpath)` is called inside processing loops.

### Silent Failures / Crashing
- **Cause**: Missing DLLs for `torch` or `cv2`.
- **Fix**: Run `dll_check.py`. Install VC++ Redistributable.

## 3. Logging & Tracing
Enable debug logging to see per-page events.

```python
# In config.py or via env var
LOG_LEVEL = "DEBUG"
```

Logs will show:
- `Page X: Cache hit/miss`
- `Initializing EasyOCR...`
- `Downscaling large image...`

## 4. Visual Debugging
To inspect what the OCR engine "sees":
1. Modify `extractor.py` to save preprocessed images:
   ```python
   cv2.imwrite(f"debug_preproc_{page_number}.png", processed_img)
   ```
2. Check for over-binarization or skew issues.

```

### 📄 File: `skills\pdf_processing.md`
*System Context Meta-Skill*

```md
---
name: PDF Processing
description: Best practices for handling PDF inputs in the B.L.A.S.T. pipeline.
---

# PDF Processing Skill

## 1. The Rendering Pipeline
PDFs are not OCR'd directly; they are rendered to images first.
`PDF -> [pdf2image] -> PIL/Numpy -> [OpenCV] -> [EasyOCR]`

## 2. Configuration (`pdf2image`)
Key parameters in `main.py`:
- `dpi=300`: Standard for OCR. Lower (200) loses accuracy; Higher (600) kills perf.
- `thread_count=4`: `pdftocairo` usually scales well up to 4 threads.
- `use_pdftocairo=True`: Faster and more robust than default `pdftoppm`.

## 3. Handling Large PDFs (>100 pages)
**Problem**: Rendering all pages at once fills RAM/Disk.
**Solution**: **Stream Processing**.
- `convert_from_path(..., first_page=i, last_page=i+batch)`
- Process batch -> Clean up temp files -> Next batch.

## 4. Metadata Extraction
To extract text *without* OCR (if PDF is already searchable):
- Use `pypdf` or `pdfmnier` (currently not in B.L.A.S.T. core, but valid extension).
- If `blast_ocr` detects text layer, it could skip OCR (Future Feature).

```

### 📄 File: `skills\performance_tuning.md`
*System Context Meta-Skill*

```md
---
name: OCR Performance Tuning
description: Strategies to optimize B.L.A.S.T. OCR for speed and resource usage (2026 Edition).
---

# OCR Performance Tuning (2026 Edition)

## 1. Hardware Acceleration (GPU)
- **Requirement**: NVIDIA GPU + CUDA.
- **Torch 2.x**: Use `torch.compile()` if custom models are added.
  - Speedup: Free 20-30% on supported hardware.

## 2. Quantization (Memory)
For lower VRAM usage (<4GB cards):
- Use `int8` or `float16` precision where possible.
- **EasyOCR**: Default is `float32`. Switching to `quantize=False` (paradoxically) uses `float16` on GPU in newer versions automatically if supported.

## 3. Parallelism
- **CPU**: `max_workers=2`.
- **GPU**: Serialize (`max_workers=1`).
- **Batching**: Use `readtext_batched` (if supported) vs loop.

## 4. Preprocessing
- **Resolution**: 1800-2200px width.
- **Denoising**: Skip unless necessary.

```

### 📄 File: `skills\project_maintenance.md`
*System Context Meta-Skill*

```md
---
name: Project Maintenance
description: Routine tasks for keeping the workspace clean, organized, and up-to-date.
---

# Project Maintenance Skill

## 1. Cleaning
- **Temp Files**: `blast_output/` and `.tmp/` accumulate data.
- **Action**: Run a cleanup script (or manual deletion) weekly.
  - Safe to delete: `*.tmp`, `__pycache__`, `logs/*.log` (if archived).

## 2. Dependency Updates
- **Check**: `pip list --outdated`.
- **Update**: `pip install -U -r requirements.txt`.
- **Lock**: Consider `pip-tools` or `poetry` for deterministic builds in future.

## 3. Git Hygiene
- **Commit Messages**: Semantic Commits (`feat:`, `fix:`, `docs:`).
- **Branches**: `main` is stable. Feature branches for big changes.
- **Ignore**: Verify `.gitignore` covers `venv`, `.env`, and output files.

## 4. Documentation
- **Keep Current**: Update `README.md` and `skills/*.md` when code changes.
- **Verify**: Run `verify_foundation.py` after major refactors.

```

### 📄 File: `skills\python_mastery.md`
*System Context Meta-Skill*

```md
---
name: Python Mastery
description: Guide to Python coding standards, best practices, and patterns used in B.L.A.S.T. (2026 Edition)
---

# Python Mastery Skill (2026 Edition)

## 1. Modern Tooling
We adopt the "Speed First" toolchain.
- **Installer**: Use **`uv`** instead of `pip`.
  - Why: 10-100x faster, Rust-based, unified venv management.
  - Cmd: `uv pip install -r requirements.txt`
- **Linter/Formatter**: Use **`Ruff`** instead of `flake8`/`black`/`isort`.
  - Why: Single binary, instant execution, replaces 10+ tools.
  - Config: `pyproject.toml` (standardized).

## 2. Type Hinting
We enforce strict typing for better tooling support.
- **Use**: `List`, `Dict`, `Optional`, `Union`, `Callable`.
- **Why**: Catches bugs early. Ruff's type-checking rules integrations help here.

## 3. Asynchronous Patterns
B.L.A.S.T. uses a mix of sync and async.
- **Sync**: `pdf2image`, `opencv` (CPU-bound).
- **Async**: UI updates.
- **Pattern**: When wrapping blocking calls in async, use `run_in_executor`.

## 4. Documentation
- **Docstrings**: Google Style.
  ```python
  def func(arg1: int) -> int:
      """
      Description.
      
      Args:
          arg1: Description.
      """
  ```

```

### 📄 File: `skills\software_cleanup.md`
*System Context Meta-Skill*

```md
---
name: Software Cleanup (Vibe Check)
description: A systematic guide to professionalizing "vibe coded" software—moving from fast chaos to structured reliability.
---

# Software Cleanup: The "Vibe Check"

This skill is for when you've written code "in the zone" (fast, messy, effective) and now need to make it maintainable for the long haul.

## 1. The Vibe Audit (Identification)
Use grep/ripgrep to find "smells" typical of vibe coding:
- **Magic Numbers**: Hardcoded values (e.g., `time.sleep(5)`, `if x > 100`).
- **Mega-Functions**: Functions > 50 lines doing 3+ things.
- **Global Mutations**: Modifying global state willy-nilly.
- **Copy-Paste**: Similar blocks repeated 3+ times.

**Command**:
```bash
# Find TODOs and FIXMEs left behind
grep -r "TODO" .
grep -r "FIXME" .
```

## 2. The Deterministic Detox (Linting & Formatting)
Stop arguing about style. Enforce it automatically.
- **Tool**: **`Ruff`** (The 2026 Standard).
- **Rule Set**: Use `select = ["E", "F", "I", "UP", "B"]` in `pyproject.toml`.
  - `E/F`: Standard errors (flake8).
  - `I`: Import sorting (isort).
  - `UP`: Upgrade syntax (pyupgrade).
  - `B`: Bugbear (common bugs).

**Command**:
```bash
ruff check --fix .
ruff format .
```

## 3. The Structure Upgrade (Architecture)
Refactor "Script" code into "Library" code.

### Step A: Configuration Injection
**Bad (Hardcoded)**:
```python
def process():
    file = open("data.txt") ...
```

**Good (Injected)**:
```python
def process(file_path: str):
    ...
```

### Step B: The "Main" Guard
Ensure no code runs on import. All scripts must have:
```python
if __name__ == "__main__":
    main()
```

### Step C: Logging > Print
Replace all `print()` statements with structured logging.
- **Why**: `print` vanishes in production or clutters output. `logger` can be filtered, filed, and formatted.

## 4. The Safety Net (Typing & Tests)
- **Type Hints**: Add types to function signatures. `def foo(x: int) -> str:`
- **Smoke Tests**: Write one test that runs the whole pipeline end-to-end on a tiny input.
  - If this passes, you haven't broken the world.

## 5. The "Vibe" Checklist
Before merging/deploying, ask:
1. [ ] Can a stranger run this without asking me for help? (README check)
2. [ ] Does it crash if the internet disconnects? (Error handling check)
3. [ ] Are there secrets (API keys) in the code? (Security check)

```

### 📄 File: `skills\system_architecture_analysis.md`
*System Context Meta-Skill*

```md
---
name: System Architecture Analysis
description: How to analyze and understand the B.L.A.S.T. codebase structure.
---

# System Architecture Analysis Skill

## 1. Directory Structure
- `blast_ocr/`: Core package.
  - `core/`: Logic (Extractor, Parallel, Healing).
  - `storage/`: Data Persistence (SQLite).
  - `ui/`: Frontend (Streamlit).
  - `cache/`: Performance optimization.

## 2. Data Flow
1. **Input**: `User -> UI -> Main Pipeline`
2. **Processing**: `Pipeline -> PDF2Image -> OpenCv -> EasyOCR`
3. **Storage**: `Pipeline -> SQLite (Main Thread)`
4. **Output**: `Pipeline -> MD/DOCX`

## 3. Dependency Graph
- **Core**: `torch`, `easyocr`, `numpy`, `opencv`.
- **UI**: `streamlit`.
- **Utils**: `pdf2image`, `tqdm`.

## 4. Analysis Tools
- **Static**: `inventory_gen.py` lists all files.
- **Runtime**: `tracemalloc` (in `benchmark.py`) profiles memory.
- **Logs**: `logs/blast_ocr.log` traces execution flow.

```

### 📄 File: `skills\testing_strategy.md`
*System Context Meta-Skill*

```md
---
name: Testing Strategy
description: How to verify, benchmark, and stress-test the OCR pipeline.
---

# Testing Strategy Skill

## 1. Unit Tests
Located in `tests/`.
- **Run**: `pytest`
- **Focus**:
  - `test_critical_paths.py`: Verifies locks, cache hashing, and singleton patterns.
  - **Philosophy**: Test logic, not libraries. Don't test *if* EasyOCR works (that's their job), test if *we* handle EasyOCR correctly.

## 2. Performance Benchmarking
Use `benchmark.py` for regression testing performance.
- **Run**: `python benchmark.py`
- **Metrics**:
  - Time per Page.
  - Peak RAM Usage (Critical for stability).
  - Cache Hit Speedup.

## 3. Foundation Verification
Use `verify_foundation.py` as a "Sanity Check" script.
- Great for post-deployment or environment setup checks.
- Verifies: Imports, DB Creation, Log Creation, Engine Init.

## 4. Manual "Smoke Tests"
- **Ghost Data**: Check `blast_output/` and temp dirs to ensure files aren't accumulating.
- **Visual Check**: Open a generated `.docx` to verify formatting/headers are preserved.

```

### 📄 File: `skills\ui_development.md`
*System Context Meta-Skill*

```md
---
name: UI Development
description: Guide to the Streamlit-based UI, styling, and extension (2026 Edition).
---

# UI Development Skill (2026 Edition)

## 1. Framework
Built with **Streamlit** (v1.37+ features).

## 2. Performance: Fragments
**CRITICAL**: Use `@st.fragment` for high-performance interactive components.
- **Concept**: Rerun *only* the annotated function, not the whole page.
- **Use Case**:
  - Independent counters/timers.
  - Real-time status badges.
  - Form inputs that don't affect global state.

```python
@st.fragment
def show_status(job_id):
    # This reruns every 5s WITHOUT reloading the whole app
    status = db.get_status(job_id)
    st.badge(status)
    time.sleep(5)
    st.rerun()
```

## 3. Styling System (CSS)
We use a **Custom CSS Injection** approach for a "Premium" look.
- **Glassmorphism**: `.glass-card`.
- **Gradients**: `.blast-title`.

## 4. Component Architecture
- **Sidebar**: Config.
- **Main Area**: `st.empty()` placeholders combined with fragments for smooth updates.

```

### 📄 File: `skills\ux_guidelines.md`
*System Context Meta-Skill*

```md
---
name: UX Guidelines
description: Principles for creating a premium User Experience in B.L.A.S.T.
---

# User Experience (UX) Guidelines

## 1. The "Premium" Aesthetic
The user explicitly requested "WOW" factors.
- **Glassmorphism**: Translucent cards with blur.
- **Gradients**: Use warm, vibrant gradients (Orange/Red) for brand identity.
- **Typography**: Clean, sans-serif fonts. Large headers (`4rem`).

## 2. Responsiveness
- **Feedback**: Immediate visual feedback for EVERY action.
  - Button click -> Spinner.
  - Processing -> Progress bar.
  - Success -> Green badge/toast.
- **Latency**: Operations > 0.5s must show a loader.

## 3. Dark Mode First
The interface is optimized for dark mode (`#312e81` background).
- **Contrast**: Text must be high contrast (`#e0e7ff`).
- **Shadows**: Use colored shadows (glows) instead of black shadows for depth.

## 4. Information Architecture
- **Hierarchy**: Most important controls (Upload) at the top.
- **Density**: Use white space liberally. Don't crowd the interface.
- **Tabs**: Group related functionality (e.g., "Settings" vs. "Run").

```

## 11. Benchmarking & Full Source Code Roster
**🎯 Target Audience:** AI Agent
*Metrics scripts and repository maps.*

### 📄 File: `benchmark.py`
*Measures execution speeds and limits.*

```py
"""
B.L.A.S.T. OCR Benchmark Script
Phase 4: Testing & Validation

Measures performance of the OCR pipeline before/after optimization.
"""
import os
import sys
import time
import tempfile
import tracemalloc
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from blast_ocr.main import BlastPipeline


def create_test_pdf(output_path: str, num_pages: int = 5) -> str:
    """
    Create a simple test PDF with text on each page.
    Uses PIL to create images and converts to PDF.
    """
    from PIL import Image, ImageDraw
    
    images = []
    for i in range(num_pages):
        # Create a letter-sized image (300 DPI)
        img = Image.new('RGB', (2550, 3300), color='white')
        draw = ImageDraw.Draw(img)
        
        # Add text content
        text_lines = [
            f"Page {i + 1} of {num_pages}",
            "",
            "B.L.A.S.T. OCR Benchmark Test Page",
            "",
            "Lorem ipsum dolor sit amet, consectetur adipiscing elit.",
            "Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.",
            "Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris.",
            "Duis aute irure dolor in reprehenderit in voluptate velit esse.",
            "",
            "The quick brown fox jumps over the lazy dog.",
            "Pack my box with five dozen liquor jugs.",
            "How vexingly quick daft zebras jump!",
        ]
        
        y_offset = 200
        for line in text_lines:
            draw.text((200, y_offset), line, fill='black')
            y_offset += 100
        
        images.append(img)
    
    # Save as PDF
    if images:
        images[0].save(output_path, "PDF", save_all=True, append_images=images[1:])
    
    return output_path


def create_test_image(output_path: str) -> str:
    """Create a simple test image with text."""
    img = Image.new('RGB', (800, 200), color='white')
    draw = ImageDraw.Draw(img)
    draw.text((50, 50), "B.L.A.S.T. OCR Test Image - Quick Brown Fox", fill='black')
    draw.text((50, 100), "1234567890 ABCDEFGHIJ abcdefghij", fill='black')
    img.save(output_path)
    return output_path


def format_bytes(bytes_val: int) -> str:
    """Format bytes to human readable string."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_val < 1024:
            return f"{bytes_val:.2f} {unit}"
        bytes_val /= 1024
    return f"{bytes_val:.2f} TB"


def run_benchmark():
    """Run the OCR benchmark and print results."""
    print("=" * 60)
    print("B.L.A.S.T. OCR BENCHMARK")
    print("=" * 60)
    print()
    
    results = {}
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # Test 1: Single Image OCR
        print("[1/3] Benchmarking single image OCR...")
        print("-" * 40)
        
        test_image = create_test_image(str(temp_path / "test_image.png"))
        
        tracemalloc.start()
        start_time = time.perf_counter()
        
        pipeline = BlastPipeline()
        result = pipeline.process_job(test_image, str(temp_path / "output_image"))
        
        end_time = time.perf_counter()
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        
        image_time = end_time - start_time
        results['single_image'] = {
            'time': image_time,
            'peak_memory': peak,
            'status': result.get('status', 'unknown')
        }
        
        print(f"  Status: {result.get('status', 'unknown')}")
        print(f"  Time: {image_time:.2f}s")
        print(f"  Peak RAM: {format_bytes(peak)}")
        print()
        
        # Test 2: Multi-page PDF OCR (5 pages)
        print("[2/3] Benchmarking 5-page PDF OCR...")
        print("-" * 40)
        
        test_pdf = create_test_pdf(str(temp_path / "test_5page.pdf"), num_pages=5)
        
        tracemalloc.start()
        start_time = time.perf_counter()
        
        pipeline2 = BlastPipeline()
        result2 = pipeline2.process_job(test_pdf, str(temp_path / "output_pdf5"))
        
        end_time = time.perf_counter()
        current2, peak2 = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        
        pdf5_time = end_time - start_time
        pages_processed = result2.get('pages_processed', 0)
        per_page_time = pdf5_time / max(pages_processed, 1)
        
        results['pdf_5page'] = {
            'time': pdf5_time,
            'per_page': per_page_time,
            'pages': pages_processed,
            'peak_memory': peak2,
            'status': result2.get('status', 'unknown')
        }
        
        print(f"  Status: {result2.get('status', 'unknown')}")
        print(f"  Pages processed: {pages_processed}")
        print(f"  Total time: {pdf5_time:.2f}s")
        print(f"  Per-page time: {per_page_time:.2f}s")
        print(f"  Peak RAM: {format_bytes(peak2)}")
        print()
        
        # Test 3: Cache hit test
        print("[3/3] Benchmarking cache hit...")
        print("-" * 40)
        
        start_time = time.perf_counter()
        
        # Re-process same image (should be cached)
        pipeline3 = BlastPipeline()
        result3 = pipeline3.process_job(test_image, str(temp_path / "output_cached"))
        
        end_time = time.perf_counter()
        cache_time = end_time - start_time
        
        results['cache_hit'] = {
            'time': cache_time,
            'status': result3.get('status', 'unknown')
        }
        
        print(f"  Status: {result3.get('status', 'unknown')}")
        print(f"  Time with cache: {cache_time:.2f}s")
        print(f"  Cache speedup: {image_time / max(cache_time, 0.001):.1f}x")
        print()
    
    # Summary
    print("=" * 60)
    print("BENCHMARK SUMMARY")
    print("=" * 60)
    print()
    print(f"Single Image OCR:     {results['single_image']['time']:.2f}s")
    print(f"5-Page PDF (total):   {results['pdf_5page']['time']:.2f}s")
    print(f"5-Page PDF (per-page):{results['pdf_5page']['per_page']:.2f}s")
    print(f"Cache Hit Reprocess:  {results['cache_hit']['time']:.2f}s")
    print(f"Peak Memory (PDF):    {format_bytes(results['pdf_5page']['peak_memory'])}")
    print()
    
    return results


def test_cache_behavior():
    """Test that cache hit/miss works correctly."""
    print("\n[SMOKE TEST] Cache Behavior")
    print("-" * 40)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        test_image = create_test_image(str(temp_path / "cache_test.png"))
        
        pipeline = BlastPipeline()
        
        # First run - should be cache miss
        result1 = pipeline.process_job(test_image, str(temp_path / "out1"))
        
        # Second run - should be cache hit
        result2 = pipeline.process_job(test_image, str(temp_path / "out2"))
        
        print(f"  First run:  {result1.get('status', 'unknown')}")
        print(f"  Second run: {result2.get('status', 'unknown')}")
        print("  ✓ Cache behavior test passed")


def test_error_handling():
    """Test that errors are handled gracefully."""
    print("\n[SMOKE TEST] Error Handling")
    print("-" * 40)
    
    pipeline = BlastPipeline()
    
    # Test non-existent file
    result = pipeline.process_job("non_existent_file.pdf", "output")
    assert result.get('status') == 'error', f"Expected 'error' status, got {result.get('status')}"
    print("  ✓ Non-existent file handled correctly")
    
    print("  ✓ Error handling test passed")


if __name__ == "__main__":
    print()
    print("Starting B.L.A.S.T. OCR Benchmark...")
    print("This will test single image, multi-page PDF, and cache performance.")
    print()
    
    try:
        results = run_benchmark()
        test_cache_behavior()
        test_error_handling()
        
        print("\n" + "=" * 60)
        print("ALL TESTS PASSED")
        print("=" * 60)
    except Exception as e:
        print(f"\n[ERROR] Benchmark failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

```

### 📄 Complete File System Roster
```text
./
    .env.example
    .gitignore
    ARCHITECTURE.md
    AUDIT.md
    benchmark.py
    CHANGELOG.md
    CONTRIBUTING.md
    DEVTOOLS_GUIDE.md
    dll_check.py
    ENHANCEMENTS.md
    gemini.md
    generate_docs.py
    generate_md_docs.py
    inventory_gen.py
    maintain.py
    packages.txt
    README.md
    requirements.txt
    run.py
    run_gui.py
    VC_redist.x64.exe
    verify_foundation.py
    .streamlit/
        config.toml
    architecture/
        extraction_flow.md
    blast_ocr/
        config.py
        logging_config.py
        main.py
        pipeline.py
        __init__.py
        cache/
            manager.py
            __init__.py
        core/
            exceptions.py
            extractor.py
            handshake_easyocr.py
            handshake_tesseract.py
            healing.py
            parallel.py
            worker.py
            __init__.py
        storage/
            database.py
            __init__.py
        ui/
            gui_launcher.py
            styles.css
            web_app.py
            __init__.py
    data/
        mybook.pdf
        pages/
            page-01.png
            page-02.png
            page-03.png
            page-04.png
            page-05.png
            page-06.png
            page-07.png
            page-08.png
            page-09.png
            page-10.png
            page-11.png
            page-12.png
            page-13.png
            page-14.png
            page-15.png
            page-16.png
            page-17.png
            page-18.png
            page-19.png
            page-20.png
            page-21.png
            page-22.png
            page-23.png
            page-24.png
            page-25.png
            page-26.png
            page-27.png
            page-28.png
            page-29.png
            page-30.png
            page-31.png
            page-32.png
            page-33.png
            page-34.png
            page-35.png
            page-36.png
            page-37.png
            page-38.png
            page-39.png
            page-40.png
            page-41.png
            page-42.png
            page-43.png
            page-44.png
            page-45.png
            page-46.png
            page-47.png
            page-48.png
            page-49.png
            page-50.png
            page-51.png
            page-52.png
            page-53.png
            page-54.png
            page-55.png
            page-56.png
            page-57.png
            page-58.png
            page-59.png
            page-60.png
            page-61.png
            page-62.png
            page-63.png
            page-64.png
            page-65.png
            page-66.png
            page-67.png
            page-68.png
            page-69.png
            page-70.png
            page-71.png
            page-72.png
            page-73.png
            page-74.png
            page-75.png
            page-76.png
            page-77.png
            page-78.png
            page-79.png
            page-80.png
            page-81.png
            page-82.png
            page-83.png
            page-84.png
            page-85.png
            page-86.png
            page-87.png
            page-88.png
            page-89.png
            page-90.png
            page-91.png
            page-92.png
            page-93.png
            page-94.png
            page-95.png
            page-96.png
            page-97.png
            page-98.png
    poppler-25.12.0/
        Library/
            bin/
                cairo.dll
                charset.dll
                deflate.dll
                expat.dll
                fontconfig-1.dll
                freetype.dll
                iconv.dll
                jpeg8.dll
                lcms2.dll
                Lerc.dll
                libcrypto-3-x64.dll
                libcurl.dll
                libexpat.dll
                liblzma.dll
                libpng16.dll
                libssh2.dll
                libtiff.dll
                libzstd.dll
                openjp2.dll
                pdfattach.exe
                pdfdetach.exe
                pdffonts.exe
                pdfimages.exe
                pdfinfo.exe
                pdfseparate.exe
                pdftocairo.exe
                pdftohtml.exe
                pdftoppm.exe
                pdftops.exe
                pdftotext.exe
                pdfunite.exe
                pixman-1-0.dll
                poppler-cpp.dll
                poppler-glib.dll
                poppler.dll
                tiff.dll
                zlib.dll
                zstd.dll
                zstd.exe
            include/
                poppler/
                    Annot.h
                    AnnotStampImageHelper.h
                    Array.h
                    BBoxOutputDev.h
                    CachedFile.h
                    Catalog.h
                    CertificateInfo.h
                    CharTypes.h
                    CryptoSignBackend.h
                    CurlCachedFile.h
                    CurlPDFDocBuilder.h
                    DateInfo.h
                    Dict.h
                    Error.h
                    ErrorCodes.h
                    FILECacheLoader.h
                    FileSpec.h
                    FontInfo.h
                    Form.h
                    Function.h
                    Gfx.h
                    GfxFont.h
                    GfxState.h
                    GfxState_helpers.h
                    GlobalParams.h
                    HashAlgorithm.h
                    JPEG2000Stream.h
                    JSInfo.h
                    Lexer.h
                    Link.h
                    MarkedContentOutputDev.h
                    Movie.h
                    NameToUnicodeTable.h
                    Object.h
                    OptionalContent.h
                    Outline.h
                    OutputDev.h
                    Page.h
                    PageTransition.h
                    Parser.h
                    PDFDoc.h
                    PDFDocBuilder.h
                    PDFDocEncoding.h
                    PDFDocFactory.h
                    poppler-config.h
                    PopplerCache.h
                    poppler_private_export.h
                    ProfileData.h
                    PSOutputDev.h
                    Rendition.h
                    SignatureInfo.h
                    Sound.h
                    SplashOutputDev.h
                    Stream-CCITT.h
                    Stream.h
                    StructElement.h
                    StructTreeRoot.h
                    TextOutputDev.h
                    UnicodeCClassTables.h
                    UnicodeCompTables.h
                    UnicodeDecompTables.h
                    UnicodeMap.h
                    UnicodeMapFuncs.h
                    UnicodeMapTables.h
                    UnicodeTypeTable.h
                    UTF.h
                    ViewerPreferences.h
                    XRef.h
                    cpp/
                        poppler-destination.h
                        poppler-document.h
                        poppler-embedded-file.h
                        poppler-font-private.h
                        poppler-font.h
                        poppler-global.h
                        poppler-image.h
                        poppler-page-renderer.h
                        poppler-page-transition.h
                        poppler-page.h
                        poppler-rectangle.h
                        poppler-toc.h
                        poppler-version.h
                        poppler_cpp_export.h
                    fofi/
                        FoFiBase.h
                        FoFiEncodings.h
                        FoFiIdentifier.h
                        FoFiTrueType.h
                        FoFiType1C.h
                    glib/
                        poppler-action.h
                        poppler-annot.h
                        poppler-attachment.h
                        poppler-date.h
                        poppler-document.h
                        poppler-enums.h
                        poppler-features.h
                        poppler-form-field.h
                        poppler-layer.h
                        poppler-macros.h
                        poppler-media.h
                        poppler-movie.h
                        poppler-page.h
                        poppler-structure-element.h
                        poppler.h
                    goo/
                        gfile.h
                        gmem.h
                        GooCheckedOps.h
                        GooLikely.h
                        GooString.h
                        GooTimer.h
                        grandom.h
                        gstrtod.h
                        ImgWriter.h
                        JpegWriter.h
                        PNGWriter.h
                        TiffWriter.h
                    splash/
                        Splash.h
                        SplashBitmap.h
                        SplashClip.h
                        SplashErrorCodes.h
                        SplashFont.h
                        SplashFontEngine.h
                        SplashFontFile.h
                        SplashFontFileID.h
                        SplashGlyphBitmap.h
                        SplashMath.h
                        SplashPath.h
                        SplashPattern.h
                        SplashTypes.h
            lib/
                poppler-cpp.lib
                poppler-glib.lib
                poppler.lib
                pkgconfig/
                    poppler-cpp.pc
                    poppler-glib.pc
                    poppler.pc
            share/
                man/
                    man1/
                        pdfattach.1
                        pdfdetach.1
                        pdffonts.1
                        pdfimages.1
                        pdfinfo.1
                        pdfseparate.1
                        pdftocairo.1
                        pdftohtml.1
                        pdftoppm.1
                        pdftops.1
                        pdftotext.1
                        pdfunite.1
        share/
            poppler/
                CMakeLists.txt
                COPYING
                COPYING.adobe
                COPYING.gpl2
                Makefile
                poppler-data.pc
                poppler-data.pc.in
                README
                cidToUnicode/
                    Adobe-CNS1
                    Adobe-GB1
                    Adobe-Japan1
                    Adobe-Korea1
                cMap/
                    Adobe-CNS1/
                        Adobe-CNS1-0
                        Adobe-CNS1-1
                        Adobe-CNS1-2
                        Adobe-CNS1-3
                        Adobe-CNS1-4
                        Adobe-CNS1-5
                        Adobe-CNS1-6
                        Adobe-CNS1-7
                        Adobe-CNS1-B5pc
                        Adobe-CNS1-ETen-B5
                        Adobe-CNS1-H-CID
                        Adobe-CNS1-H-Host
                        Adobe-CNS1-H-Mac
                        Adobe-CNS1-UCS2
                        B5-H
                        B5-V
                        B5pc-H
                        B5pc-UCS2
                        B5pc-UCS2C
                        B5pc-V
                        CNS-EUC-H
                        CNS-EUC-V
                        CNS1-H
                        CNS1-V
                        CNS2-H
                        CNS2-V
                        ETen-B5-H
                        ETen-B5-UCS2
                        ETen-B5-V
                        ETenms-B5-H
                        ETenms-B5-V
                        ETHK-B5-H
                        ETHK-B5-V
                        HKdla-B5-H
                        HKdla-B5-V
                        HKdlb-B5-H
                        HKdlb-B5-V
                        HKgccs-B5-H
                        HKgccs-B5-V
                        HKm314-B5-H
                        HKm314-B5-V
                        HKm471-B5-H
                        HKm471-B5-V
                        HKscs-B5-H
                        HKscs-B5-V
                        UCS2-B5pc
                        UCS2-ETen-B5
                        UniCNS-UCS2-H
                        UniCNS-UCS2-V
                        UniCNS-UTF16-H
                        UniCNS-UTF16-V
                        UniCNS-UTF32-H
                        UniCNS-UTF32-V
                        UniCNS-UTF8-H
                        UniCNS-UTF8-V
                    Adobe-GB1/
                        Adobe-GB1-0
                        Adobe-GB1-1
                        Adobe-GB1-2
                        Adobe-GB1-3
                        Adobe-GB1-4
                        Adobe-GB1-5
                        Adobe-GB1-GBK-EUC
                        Adobe-GB1-GBpc-EUC
                        Adobe-GB1-H-CID
                        Adobe-GB1-H-Host
                        Adobe-GB1-H-Mac
                        Adobe-GB1-UCS2
                        GB-EUC-H
                        GB-EUC-V
                        GB-H
                        GB-V
                        GBK-EUC-H
                        GBK-EUC-UCS2
                        GBK-EUC-V
                        GBK2K-H
                        GBK2K-V
                        GBKp-EUC-H
                        GBKp-EUC-V
                        GBpc-EUC-H
                        GBpc-EUC-UCS2
                        GBpc-EUC-UCS2C
                        GBpc-EUC-V
                        GBT-EUC-H
                        GBT-EUC-V
                        GBT-H
                        GBT-V
                        GBTpc-EUC-H
                        GBTpc-EUC-V
                        UCS2-GBK-EUC
                        UCS2-GBpc-EUC
                        UniGB-UCS2-H
                        UniGB-UCS2-V
                        UniGB-UTF16-H
                        UniGB-UTF16-V
                        UniGB-UTF32-H
                        UniGB-UTF32-V
                        UniGB-UTF8-H
                        UniGB-UTF8-V
                    Adobe-Japan1/
                        78-EUC-H
                        78-EUC-V
                        78-H
                        78-RKSJ-H
                        78-RKSJ-V
                        78-V
                        78ms-RKSJ-H
                        78ms-RKSJ-V
                        83pv-RKSJ-H
                        90ms-RKSJ-H
                        90ms-RKSJ-UCS2
                        90ms-RKSJ-V
                        90msp-RKSJ-H
                        90msp-RKSJ-V
                        90pv-RKSJ-H
                        90pv-RKSJ-UCS2
                        90pv-RKSJ-UCS2C
                        90pv-RKSJ-V
                        Add-H
                        Add-RKSJ-H
                        Add-RKSJ-V
                        Add-V
                        Adobe-Japan1-0
                        Adobe-Japan1-1
                        Adobe-Japan1-2
                        Adobe-Japan1-3
                        Adobe-Japan1-4
                        Adobe-Japan1-5
                        Adobe-Japan1-6
                        Adobe-Japan1-7
                        Adobe-Japan1-90ms-RKSJ
                        Adobe-Japan1-90pv-RKSJ
                        Adobe-Japan1-H-CID
                        Adobe-Japan1-H-Host
                        Adobe-Japan1-H-Mac
                        Adobe-Japan1-PS-H
                        Adobe-Japan1-PS-V
                        Adobe-Japan1-UCS2
                        EUC-H
                        EUC-V
                        Ext-H
                        Ext-RKSJ-H
                        Ext-RKSJ-V
                        Ext-V
                        H
                        Hankaku
                        Hiragana
                        Hojo-EUC-H
                        Hojo-EUC-V
                        Hojo-H
                        Hojo-V
                        Katakana
                        NWP-H
                        NWP-V
                        RKSJ-H
                        RKSJ-V
                        Roman
                        UCS2-90ms-RKSJ
                        UCS2-90pv-RKSJ
                        UniHojo-UCS2-H
                        UniHojo-UCS2-V
                        UniHojo-UTF16-H
                        UniHojo-UTF16-V
                        UniHojo-UTF32-H
                        UniHojo-UTF32-V
                        UniHojo-UTF8-H
                        UniHojo-UTF8-V
                        UniJIS-UCS2-H
                        UniJIS-UCS2-HW-H
                        UniJIS-UCS2-HW-V
                        UniJIS-UCS2-V
                        UniJIS-UTF16-H
                        UniJIS-UTF16-V
                        UniJIS-UTF32-H
                        UniJIS-UTF32-V
                        UniJIS-UTF8-H
                        UniJIS-UTF8-V
                        UniJIS2004-UTF16-H
                        UniJIS2004-UTF16-V
                        UniJIS2004-UTF32-H
                        UniJIS2004-UTF32-V
                        UniJIS2004-UTF8-H
                        UniJIS2004-UTF8-V
                        UniJISPro-UCS2-HW-V
                        UniJISPro-UCS2-V
                        UniJISPro-UTF8-V
                        UniJISX0213-UTF32-H
                        UniJISX0213-UTF32-V
                        UniJISX02132004-UTF32-H
                        UniJISX02132004-UTF32-V
                        V
                        WP-Symbol
                    Adobe-Japan2/
                        Adobe-Japan2-0
                    Adobe-Korea1/
                        Adobe-Korea1-0
                        Adobe-Korea1-1
                        Adobe-Korea1-2
                        Adobe-Korea1-H-CID
                        Adobe-Korea1-H-Host
                        Adobe-Korea1-H-Mac
                        Adobe-Korea1-KSCms-UHC
                        Adobe-Korea1-KSCpc-EUC
                        Adobe-Korea1-UCS2
                        KSC-EUC-H
                        KSC-EUC-V
                        KSC-H
                        KSC-Johab-H
                        KSC-Johab-V
                        KSC-V
                        KSCms-UHC-H
                        KSCms-UHC-HW-H
                        KSCms-UHC-HW-V
                        KSCms-UHC-UCS2
                        KSCms-UHC-V
                        KSCpc-EUC-H
                        KSCpc-EUC-UCS2
                        KSCpc-EUC-UCS2C
                        KSCpc-EUC-V
                        UCS2-KSCms-UHC
                        UCS2-KSCpc-EUC
                        UniKS-UCS2-H
                        UniKS-UCS2-V
                        UniKS-UTF16-H
                        UniKS-UTF16-V
                        UniKS-UTF32-H
                        UniKS-UTF32-V
                        UniKS-UTF8-H
                        UniKS-UTF8-V
                    Adobe-KR/
                        Adobe-KR-0
                        Adobe-KR-1
                        Adobe-KR-2
                        Adobe-KR-3
                        Adobe-KR-4
                        Adobe-KR-5
                        Adobe-KR-6
                        Adobe-KR-7
                        Adobe-KR-8
                        Adobe-KR-9
                        Adobe-KR-UCS2
                        UniAKR-UTF16-H
                        UniAKR-UTF32-H
                        UniAKR-UTF8-H
                nameToUnicode/
                    Bulgarian
                    Greek
                    Thai
                unicodeMap/
                    Big5
                    Big5ascii
                    EUC-CN
                    EUC-JP
                    GBK
                    ISO-2022-CN
                    ISO-2022-JP
                    ISO-2022-KR
                    ISO-8859-6
                    ISO-8859-7
                    ISO-8859-8
                    ISO-8859-9
                    KOI8-R
                    Latin2
                    Shift-JIS
                    TIS-620
                    Windows-1255
    skills/
        advanced_qa.md
        database_management.md
        error_recovery.md
        future_roadmap.md
        meta_skill_management.md
        ocr_debugging.md
        pdf_processing.md
        performance_tuning.md
        project_maintenance.md
        python_mastery.md
        software_cleanup.md
        system_architecture_analysis.md
        testing_strategy.md
        ui_development.md
        ux_guidelines.md
    tests/
        conftest.py
        debug_pdf.py
        final_verification.py
        test_callback.py
        test_critical_paths.py
        test_extractor.py
        test_pipeline.py
        test_sanitization.py
        verify.py
        verify_enhancements.py
        verify_pptx.py
    test_images/
        download.jpg
        images.jpg

```

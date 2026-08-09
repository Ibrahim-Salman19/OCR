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
- **Role**: Pure functions and classes that do one thing well (e.g., `RobustOCRExtractor`, `SelfHealingOCR`). 
- **Thread Safety**: Uses a module-level global lock (`_ocr_global_lock`) to serialize thread-unsafe OCR engine calls while allowing concurrent preprocessing.
- **Session Isolation**: Utilizes `scoped_session` with `threading.get_ident` to ensure database transaction isolation across parallel workers.

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

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

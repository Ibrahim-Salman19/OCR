# ♊ gemini.md - Project Map

**Status**: 🟢 Verified & Production-Ready
**Last Updated**: 2026-03-26

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

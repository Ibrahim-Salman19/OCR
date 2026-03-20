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

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

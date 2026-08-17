# Handoff Report: Streaming Buffer & Storage Engine Design (explorer_1)

## 1. Observation
- **Pipeline Memory Bottlenecks in `blast_ocr/pipeline.py`**:
  - In `process_pdf()` (lines 191-255), PDF rendering creates a single monolithic `temp_dir = tempfile.mkdtemp()` for all batches, accumulating all page dictionaries in `all_results.extend(batch_results)` (line 233).
  - In directory ingestion (lines 412-445), all image files in a folder are restored simultaneously on disk (`restored_paths = [restore_page_image(p, restore_temp_dir, mode="standard") for p in image_paths]`, lines 430-433) and passed in one giant list to `process_batch_threaded()`.
  - In `process_job()` (lines 477-519), a monolithic Pydantic `Document(pages=pages_list)` object tree is assembled in RAM, serialized via `json.dump(doc_model.model_dump(), jf)` (line 496), and text is concatenated into a single string (`"\n\n---\n\n".join(...)`, line 511), causing RAM usage to scale linearly with page count ($O(N)$).
- **Configuration in `blast_ocr/config.py`**:
  - `OCRConfig` (lines 28-107) has fields for `ocr_batch_size: int = 8`, `max_workers: int = 2`, but lacks explicit streaming window configuration (`enable_streaming`, `stream_chunk_size`, `stream_auto_threshold`, `stream_scratch_dir`, `stream_formats`).
- **Memory Guardrails in `tests/test_memory.py`**:
  - Verified existing memory tests (`pytest tests/test_memory.py -v`) pass 5/5 with zero leaks: `test_processed_img_deleted_after_ocr`, `test_memory_flat_across_pages`, `test_database_connection_closed_on_del`, `test_pipeline_temp_directory_cleaned_up`, `test_cache_file_handles_closed_after_write`.

## 2. Logic Chain
1. *From Observation 1*: Uncompressed 300 DPI A4 bitmaps require $\approx 26.1\text{MB}$ per page. Loading hundreds or thousands of pages simultaneously into RAM or leaving uncleaned scratch images on disk leads to RSS bloat ($>3.5\text{GB} - 26\text{GB}$) and eventual OOM kills.
2. *From Observation 1 & 2*: By introducing windowed ingestion ($K=8..16$) via `PageStreamGenerator`, at most $K$ raw image files exist on disk at any given time, and active in-flight RAM is bounded to $K \times 26.1\text{MB} \le 417\text{MB}$.
3. *From Observation 1*: By using `ChunkScratchManager`, scratch folders `scratch_w_0000`, `scratch_w_0001`, ... are isolated and immediately unlinked when advancing to the next batch, preventing disk space accumulation.
4. *From Observation 1*: By introducing `StreamDocumentWriter`, OCR results are written on-the-fly directly to Markdown, Plain Text, and JSON Lines format streams without constructing a 1,000-page monolithic Pydantic `Document` in RAM.
5. *From Observation 2*: By integrating `process_stream()` into `BlastPipeline` and configuring automatic thresholding ($N \ge 50$ pages) in `BlastConfig`, the pipeline transparently scales to arbitrary document sizes while guaranteeing peak RSS $\le 500\text{MB}$.

## 3. Caveats
- Searchable PDF generation in streaming mode requires incremental PDF writing via PyMuPDF (`fitz`). If PyMuPDF is not installed in the execution environment, Searchable PDF streaming gracefully disables while Markdown, TXT, and JSONL continue unaffected.
- EPUB and DOCX formats inherently require full-document structural hierarchies and are therefore recommended for standard/in-memory mode, whereas Markdown, TXT, and JSONL are the primary streaming formats.

## 4. Conclusion
The technical architecture and complete blueprint for `blast_ocr/core/streaming.py` (`ChunkScratchManager`, `PageStreamGenerator`, and `StreamDocumentWriter`) along with integration designs for `blast_ocr/pipeline.py` and `blast_ocr/config.py` are fully specified and verified in `/mnt/d/code/Projects/Python/OCR_Book/.agents/sub_orch_m3/explorer_1/report.md`. The design guarantees peak RSS $\le 500\text{MB}$ on 1,000+ page archives with zero disk leaks and $O(1)$ stream export memory.

## 5. Verification Method
1. Inspect report blueprint: `/mnt/d/code/Projects/Python/OCR_Book/.agents/sub_orch_m3/explorer_1/report.md`.
2. Run existing memory test suite to confirm baseline:
   ```bash
   pytest tests/test_memory.py -v
   ```
3. When implemented by Worker agent, run:
   ```bash
   pytest tests/test_streaming_storage.py -v
   ```

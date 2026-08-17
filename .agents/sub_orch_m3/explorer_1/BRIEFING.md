# BRIEFING — 2026-08-15T15:04:10Z

## Mission
Investigate and design `blast_ocr/core/streaming.py` (PageStreamGenerator, StreamDocumentWriter, ChunkScratchManager, and integration into BlastPipeline and BlastConfig) for Milestone 3.

## 🔒 My Identity
- Archetype: explorer
- Roles: investigator, designer
- Working directory: /mnt/d/code/Projects/Python/OCR_Book/.agents/sub_orch_m3/explorer_1
- Original parent: a287c8be-a840-4c60-a2f4-ef8524105659
- Milestone: Milestone 3 (Streaming Buffer & Storage Engine)

## 🔒 Key Constraints
- Read-only investigation — do NOT implement
- Ephemeral scratch folders `scratch_w_i`, page batch yielding, immediate unlinking of scratch files after batch completion
- Peak RSS <= 500MB on 1,000+ page archives
- StreamDocumentWriter incremental exporter for Markdown, Plain Text, JSONL
- ChunkScratchManager robust context manager
- Clean integration points with BlastPipeline and BlastConfig

## Current Parent
- Conversation ID: a287c8be-a840-4c60-a2f4-ef8524105659
- Updated: 2026-08-15T15:04:10Z

## Investigation State
- **Explored paths**: `blast_ocr/pipeline.py`, `blast_ocr/config.py`, `blast_ocr/core/models.py`, `blast_ocr/core/document_model.py`, `blast_ocr/core/exporter.py`, `blast_ocr/core/searchable_pdf.py`, `blast_ocr/core/worker.py`, `blast_ocr/core/parallel.py`, `blast_ocr/cache/manager.py`, `blast_ocr/storage/object_store.py`, `tests/test_memory.py`.
- **Key findings**:
  - In existing pipeline, `process_pdf()` accumulates all result dictionaries into memory; `process_job()` builds a monolithic Pydantic `Document` and serializes the full JSON tree in RAM, causing peak memory to balloon on 1,000+ page files.
  - Image directory processing currently restores and queues all images at once instead of in windowed chunks.
  - `ChunkScratchManager`, `PageStreamGenerator`, and `StreamDocumentWriter` in `blast_ocr/core/streaming.py` provide a clean solution bounding in-flight page bitmaps to $K \in [8..16]$ and writing output streams directly to disk.
- **Unexplored areas**: None for streaming core design; cache and storage components explored in parallel by `explorer_2` and `explorer_3`.

## Key Decisions Made
- Designed `ChunkScratchManager` with isolated `scratch_w_xxxx` directories, Windows lock retries, and `atexit` safety hooks.
- Designed `PageStreamGenerator` supporting multi-page PDF, naturally sorted image directory, and single image sources with immediate unlinking of previous window scratch files upon batch advance.
- Designed `StreamDocumentWriter` streaming Markdown, TXT, JSONL, and Searchable PDF with $O(1)$ memory per page.
- Designed clean integration in `BlastPipeline` via `process_stream()` and auto-routing for documents $>50$ pages.
- Produced detailed technical report at `/mnt/d/code/Projects/Python/OCR_Book/.agents/sub_orch_m3/explorer_1/report.md`.

## Artifact Index
- `/mnt/d/code/Projects/Python/OCR_Book/.agents/sub_orch_m3/explorer_1/report.md` — Full technical design and implementation blueprint
- `/mnt/d/code/Projects/Python/OCR_Book/.agents/sub_orch_m3/explorer_1/handoff.md` — 5-component handoff report

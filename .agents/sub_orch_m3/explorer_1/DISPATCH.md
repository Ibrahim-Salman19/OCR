## 2026-08-15T15:00:11Z

You are explorer_1 for Milestone 3 (Streaming Buffer & Storage Engine).
Working directory: /mnt/d/code/Projects/Python/OCR_Book/.agents/sub_orch_m3/explorer_1
Scope document: /mnt/d/code/Projects/Python/OCR_Book/.agents/sub_orch_m3/SCOPE.md
Project document: /mnt/d/code/Projects/Python/OCR_Book/PROJECT.md
Original request: /mnt/d/code/Projects/Python/OCR_Book/.agents/ORIGINAL_REQUEST.md

Your Task:
Investigate and design `blast_ocr/core/streaming.py`:
1. `PageStreamGenerator`: Windowed ingestion ($K=8..16$ pages) for PDF and image directory ingestion. Ephemeral scratch folders `scratch_w_i`, page batch yielding, immediate unlinking of scratch files after batch completion to guarantee peak RSS <= 500MB on 1,000+ page archives.
2. `StreamDocumentWriter`: Incremental stream exporter for Markdown, Plain Text, and JSONL formats without assembling monolithic Document models in RAM.
3. `ChunkScratchManager`: Context manager for robust temporary scratch space creation and deterministic cleanup.
4. Review `blast_ocr/pipeline.py` and `blast_ocr/config.py` to design clean integration points with `BlastPipeline`.

Read the existing codebase (`blast_ocr/pipeline.py`, `blast_ocr/config.py`, `blast_ocr/core/`, `tests/test_memory.py`).
Produce your complete technical design and blueprint in `/mnt/d/code/Projects/Python/OCR_Book/.agents/sub_orch_m3/explorer_1/report.md`.
Report back when done via send_message.

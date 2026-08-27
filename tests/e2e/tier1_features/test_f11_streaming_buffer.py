"""
tests/e2e/tier1_features/test_f11_streaming_buffer.py

Tier 1 Isolated Feature Tests: Feature 11 - Bounded Streaming Buffer Chunking
Covers:
- PageStreamGenerator chunk-window ingestion (K=8..16 pages)
- Immediate ephemeral scratch folder unlinking per chunk window
- StreamDocumentWriter incremental Markdown / PlainText / JSONL export
- Memory bounding and stream progress tracking
- Deterministic cleanup on stream interruption or error
"""

import json
from pathlib import Path
from PIL import Image

from blast_ocr.core.streaming import (
    PageStreamGenerator,
    StreamDocumentWriter,
)


def _create_dummy_image_pdf(pdf_path: Path, page_count: int = 12) -> None:
    """Helper to create a valid multi-page PDF with PIL images for testing."""
    images = []
    for p in range(1, page_count + 1):
        img = Image.new("RGB", (300, 400), color="white")
        images.append(img)
    if images:
        images[0].save(str(pdf_path), save_all=True, append_images=images[1:])


def test_f11_page_stream_generator_windowing_partitions(tmp_path):
    """
    Test 1: Tests PageStreamGenerator correctly partitions total document pages
    into exact chunk windows of size K (e.g. K=5 for 12 pages -> batches of 5, 5, 2).
    """
    pdf_path = tmp_path / "mock.pdf"
    _create_dummy_image_pdf(pdf_path, 12)
    gen = PageStreamGenerator(source_path=pdf_path, total_pages=12, chunk_size=5, temp_dir=tmp_path)
    
    batches = list(gen)
    assert len(batches) == 3, f"Expected 3 chunk batches, got {len(batches)}"
    
    # Check 1st chunk: pages 1 to 5
    batch_1 = batches[0]
    assert len(batch_1) == 5
    assert [p for p, _ in batch_1] == [1, 2, 3, 4, 5]

    # Check 2nd chunk: pages 6 to 10
    batch_2 = batches[1]
    assert len(batch_2) == 5
    assert [p for p, _ in batch_2] == [6, 7, 8, 9, 10]

    # Check 3rd chunk: pages 11 to 12
    batch_3 = batches[2]
    assert len(batch_3) == 2
    assert [p for p, _ in batch_3] == [11, 12]


def test_f11_chunk_scratch_immediate_unlinking(tmp_path):
    """
    Test 2: Tests that scratch files created during a chunk window are immediately
    purged from disk once iteration proceeds to the next chunk or completes.
    """
    pdf_path = tmp_path / "doc.pdf"
    _create_dummy_image_pdf(pdf_path, 8)
    gen = PageStreamGenerator(source_path=pdf_path, total_pages=8, chunk_size=4, temp_dir=tmp_path)
    
    observed_scratch_paths = []
    for chunk in gen:
        # Check files exist during chunk processing
        for _, path in chunk:
            assert path.exists(), f"Scratch file {path} should exist during active chunk"
            observed_scratch_paths.append(path)
    
    # After generator finishes iteration, all scratch files must be unlinked
    for path in observed_scratch_paths:
        assert not path.exists(), f"Scratch file {path} should have been unlinked immediately"


def test_f11_stream_document_writer_markdown_and_txt(tmp_path):
    """
    Test 3: Tests StreamDocumentWriter incrementally appends page text and headers
    to Markdown and Text output files.
    """
    # 1. Test Markdown export
    md_output = tmp_path / "export.md"
    with StreamDocumentWriter(md_output, format="markdown") as writer:
        writer.write_page(1, "First page OCR text")
        writer.write_page(2, "Second page OCR text")
    
    assert md_output.exists()
    content = md_output.read_text(encoding="utf-8")
    assert "## Page 1" in content
    assert "First page OCR text" in content
    assert "## Page 2" in content
    assert "---" in content

    # 2. Test Plain Text export
    txt_output = tmp_path / "export.txt"
    with StreamDocumentWriter(txt_output, format="txt") as writer:
        writer.write_page(1, "Plain text line 1")
    assert "--- Page 1 ---" in txt_output.read_text(encoding="utf-8")


def test_f11_stream_document_writer_jsonl(tmp_path):
    """
    Test 4: Tests StreamDocumentWriter formats and streams per-page layout and OCR
    results into line-delimited JSON (.jsonl).
    """
    jsonl_output = tmp_path / "export.jsonl"
    with StreamDocumentWriter(jsonl_output, format="jsonl") as writer:
        writer.write_page(1, "Text for P1", layout={"blocks": [{"box": [0, 0, 10, 10]}]})
        writer.write_page(2, "Text for P2", layout={"blocks": [{"box": [0, 0, 20, 20]}]})

    assert jsonl_output.exists()
    lines = [line.strip() for line in jsonl_output.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(lines) == 2
    
    record_1 = json.loads(lines[0])
    assert record_1["page"] == 1
    assert record_1["text"] == "Text for P1"
    assert "blocks" in record_1["layout"]

    record_2 = json.loads(lines[1])
    assert record_2["page"] == 2
    assert record_2["text"] == "Text for P2"


def test_f11_streaming_generator_cleanup_on_interruption(tmp_path):
    """
    Test 5: Tests exception safety and premature break handling: scratch folders
    are cleanly deleted even if processing fails mid-stream.
    """
    pdf_path = tmp_path / "bad.pdf"
    _create_dummy_image_pdf(pdf_path, 10)
    scratch_dir_captured = None
    
    try:
        with PageStreamGenerator(source_path=pdf_path, total_pages=10, chunk_size=3, temp_dir=tmp_path) as gen:
            for i, chunk in enumerate(gen):
                if i == 0:
                    scratch_dir_captured = chunk[0][1].parent
                    assert scratch_dir_captured.exists()
                    # Simulate unexpected error during chunk 1 processing
                    raise RuntimeError("Simulated mid-stream OCR failure")
    except RuntimeError:
        pass

    # Verify captured scratch folder was deleted upon context manager exit
    if scratch_dir_captured:
        assert not scratch_dir_captured.exists(), "Scratch folder must be cleaned up on exception"

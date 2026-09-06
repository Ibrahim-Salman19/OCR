"""
tests/test_ui_deep_coverage.py

Comprehensive unit tests targeting uncovered branches in blast_ocr/ui/web_app.py:
- _InMemoryDB state machine, transactions, results, metrics, queries
- Data conversion & safety sanitization: _safe_float, _safe_int, _safe_status,
  _markdown_without_embeds, _spreadsheet_safe_value, _safe_download_filename,
  _human_duration, _call_with_supported_kwargs, _result_error_message
- File sandbox boundaries: _path_is_within, _normalise_output_files, _build_zip_bytes
- Layout Geometry SVG Renderer: render_layout_geometry_svg with filters and thresholds
- UI Helper logic: _preset_defaults, _signature_matches, _validate_upload_batch,
  _extract_document_groups, _discover_layout_jsons, _resource_snapshot
"""

import io
import zipfile
from unittest.mock import patch, MagicMock

from blast_ocr.ui.web_app import (
    _InMemoryDB,
    _safe_float,
    _safe_int,
    _safe_status,
    _markdown_without_embeds,
    _spreadsheet_safe_value,
    _safe_download_filename,
    _human_duration,
    _call_with_supported_kwargs,
    _result_error_message,
    _path_is_within,
    _normalise_output_files,
    _build_zip_bytes,
    render_layout_geometry_svg,
    _preset_defaults,
    _signature_matches,
    _validate_upload_batch,
    _stage_queued_upload,
    _extract_document_groups,
    _resource_snapshot,
    _to_table,
    _pad_columns,
    render_landing_page,
    render_loading_screen,
    _set_active_job_ids,
    _remove_active_job,
    _active_job_ids,
    _cleanup_queued_source,
    _clear_current_session_artifacts,
    _render_document_preview_multi,
)
from tests.test_ui_mock import MockSessionState


# ============================================================================
# 1. _InMemoryDB Unit Tests
# ============================================================================

def test_in_memory_db_full_lifecycle():
    db = _InMemoryDB()

    # Create jobs
    j1 = db.create_job("test1.pdf", page_count=5, priority="high")
    j2 = db.create_job("test2.png", page_count=1, priority="low")
    assert j1 == 1
    assert j2 == 2

    # Update job status
    db.update_job_status(j1, "processing")
    job1 = db.get_job(j1)
    assert job1.status == "processing"
    assert job1.priority == "high"

    db.update_job_status(j2, "failed", error_message="File corrupt")
    job2 = db.get_job(j2)
    assert job2.status == "failed"
    assert job2.error_message == "File corrupt"

    # Nonexistent job update
    db.update_job_status(999, "failed")

    # Update page count
    db.update_job_page_count(j1, 10)
    assert db.get_job(j1).page_count == 10

    # Save results
    db.save_result(j1, 1, "Page 1 extracted text", 0.95, 0.42)
    db.save_result(j1, 2, "Page 2 extracted text", 0.98, 0.38)
    results = db.get_results(j1)
    assert len(results) == 2
    assert results[0].extracted_text == "Page 1 extracted text"
    assert results[1].confidence_score == 0.98

    # Save metrics
    db.save_metric(j1, peak_mem=128.5, avg_time=0.4, fidelity=0.96, velocity=2.5)
    metrics = db.get_recent_metrics(limit=5)
    assert len(metrics) == 1
    assert metrics[0].peak_memory_mb == 128.5

    # Recent jobs
    recent = db.get_recent_jobs(limit=10)
    assert len(recent) == 2
    assert recent[0].id == 2  # Most recent first

    # Purge
    assert db.purge_old_data(days=7) is None


# ============================================================================
# 2. Data Safety & Formatting Functions
# ============================================================================

def test_safe_converters():
    assert _safe_float(3.14) == 3.14
    assert _safe_float("invalid", default=1.0) == 1.0
    assert _safe_float(float("nan"), default=0.0) == 0.0
    assert _safe_float(float("inf"), default=0.0) == 0.0

    assert _safe_int(42) == 42
    assert _safe_int("99") == 99
    assert _safe_int("xyz", default=7) == 7

    assert _safe_status(" Job Succeeded! ") == "job_succeeded"
    assert _safe_status("") == "unknown"


def test_markdown_without_embeds():
    md = "# Heading\n![Logo](http://malicious.com/tracker.png)\nSome text.\n![Alt][ref]"
    cleaned = _markdown_without_embeds(md)
    assert "http://malicious.com" not in cleaned
    assert "[image omitted: Logo]" in cleaned
    assert "[image omitted: Alt]" in cleaned


def test_spreadsheet_safe_value():
    assert _spreadsheet_safe_value("=1+2") == "'=1+2"
    assert _spreadsheet_safe_value("+cmd|") == "'+cmd|"
    assert _spreadsheet_safe_value("-cmd|") == "'-cmd|"
    assert _spreadsheet_safe_value("@SUM(A1)") == "'@SUM(A1)"
    assert _spreadsheet_safe_value("Safe string") == "Safe string"
    assert _spreadsheet_safe_value(123) == 123


def test_safe_download_filename():
    assert _safe_download_filename("../../etc/passwd.pdf") == "passwd.pdf"
    assert _safe_download_filename("document\x00\x1f_test.docx") == "document__test.docx"
    assert _safe_download_filename("") == "artifact"


def test_human_duration():
    assert _human_duration(45) == "45s"
    assert _human_duration(125) == "2m 05s"
    assert _human_duration(3665) == "1h 01m"


def test_call_with_supported_kwargs():
    def dummy_func(a, b, keyword_only=None):
        return (a, b, keyword_only)

    res = _call_with_supported_kwargs(dummy_func, 1, 2, keyword_only="yes", extra_ignored="no")
    assert res == (1, 2, "yes")


def test_result_error_message():
    assert _result_error_message({"error": "Corrupted header"}) == "Corrupted header"
    assert _result_error_message({"message": "File rejected"}) == "File rejected"
    assert _result_error_message({}) == "Unknown processing error"


# ============================================================================
# 3. Path & ZIP Packaging Helpers
# ============================================================================

def test_path_is_within(tmp_path):
    root = tmp_path / "sandbox"
    root.mkdir()
    child = root / "sub" / "file.txt"
    outside = tmp_path / "outside.txt"

    assert _path_is_within(child, root) is True
    assert _path_is_within(outside, root) is False


def test_normalise_output_files(tmp_path):
    out_dir = tmp_path / "job_out"
    out_dir.mkdir()
    md_file = out_dir / "doc.md"
    md_file.write_text("# Test doc")
    txt_file = out_dir / "doc.txt"
    txt_file.write_text("Test doc plain")

    res = {"output_files": {"md": str(md_file), "txt": str(txt_file)}}
    norm = _normalise_output_files(res, "doc.pdf", out_dir)
    assert len(norm) == 2
    assert ("md", str(md_file.resolve())) in norm

    # Fallback to candidates on disk when output_files is missing
    norm_disk = _normalise_output_files({}, "doc.pdf", out_dir)
    assert len(norm_disk) >= 1


def test_build_zip_bytes(tmp_path):
    f1 = tmp_path / "report.md"
    f1.write_text("# Report Markdown")
    f2 = tmp_path / "report.docx"
    f2.write_bytes(b"DOCX_FAKE_BYTES")

    output_files = [("md", str(f1)), ("docx", str(f2))]
    zip_bytes = _build_zip_bytes(output_files)

    assert zip_bytes is not None
    # Validate it is a genuine zip
    with zipfile.ZipFile(zip_bytes, "r") as zf:
        namelist = zf.namelist()
        assert "report.md" in namelist
        assert "report.docx" in namelist


# ============================================================================
# 4. Layout Geometry SVG Renderer
# ============================================================================

def test_render_layout_geometry_svg():
    page_data = {
        "width": 800,
        "height": 1000,
        "blocks": [
            {
                "block_type": "title",
                "confidence": 0.95,
                "reading_order_index": 0,
                "bbox": {"xmin": 50, "ymin": 50, "xmax": 750, "ymax": 120},
            },
            {
                "block_type": "text",
                "confidence": 0.88,
                "reading_order_index": 1,
                "bbox": {"xmin": 50, "ymin": 150, "xmax": 750, "ymax": 400},
            },
            {
                "block_type": "table",
                "confidence": 0.50,
                "reading_order_index": 2,
                "bbox": {"xmin": 50, "ymin": 420, "xmax": 750, "ymax": 700},
            },
        ],
    }

    # Render ALL
    svg_all = render_layout_geometry_svg(page_data, filter_type="ALL", min_confidence=0.0)
    assert "<svg" in svg_all
    assert "viewBox=\"0 0 800.0 1000.0\"" in svg_all
    assert "</svg>" in svg_all

    # Render with filter_type="TABLE"
    svg_table = render_layout_geometry_svg(page_data, filter_type="TABLE", min_confidence=0.0)
    assert "<svg" in svg_table

    # Render with confidence threshold filter
    svg_high_conf = render_layout_geometry_svg(page_data, min_confidence=0.90)
    assert "<svg" in svg_high_conf


# ============================================================================
# 5. UI Helper Functions
# ============================================================================

class DummyUploadedFile:
    def __init__(self, data: bytes, name: str = "doc.pdf"):
        self._bio = io.BytesIO(data)
        self.name = name
        self.size = len(data)

    def getbuffer(self):
        return self._bio.getbuffer()

    def getvalue(self):
        return self._bio.getvalue()


def test_preset_defaults():
    denoise, contrast, deskew, dewarp = _preset_defaults("RECEIPT / INVOICE")
    assert denoise == 12
    assert contrast == 1.4
    assert deskew is True
    assert dewarp is False

    denoise_raw, contrast_raw, deskew_raw, dewarp_raw = _preset_defaults("RAW PASSTHROUGH")
    assert denoise_raw == 0
    assert contrast_raw == 1.0
    assert deskew_raw is False
    assert dewarp_raw is False


def test_signature_matches():
    f_pdf = DummyUploadedFile(b"%PDF-1.7 header stream", "test.pdf")
    assert _signature_matches(f_pdf, ".pdf") is True

    f_png = DummyUploadedFile(b"\x89PNG\r\n\x1a\n binary", "test.png")
    assert _signature_matches(f_png, ".png") is True

    # Spoofed mismatch
    assert _signature_matches(f_pdf, ".png") is False


def test_validate_upload_batch():
    f_valid = DummyUploadedFile(b"%PDF-1.4 header content", "document.pdf")
    f_bad_ext = DummyUploadedFile(b"MZ executable content", "script.exe")

    errors = _validate_upload_batch([f_valid, f_bad_ext], allowed_extensions={".pdf", ".png"})
    assert len(errors) == 1
    assert "extension .exe is not allowed" in errors[0]


def test_stage_queued_upload(tmp_path):
    out_dir = tmp_path / "staged"
    out_dir.mkdir()

    f_up = DummyUploadedFile(b"%PDF-1.5 test file content", "upload.pdf")

    staged_path = _stage_queued_upload(f_up, out_dir)
    assert staged_path.exists()
    assert staged_path.suffix == ".pdf"
    assert staged_path.read_bytes() == b"%PDF-1.5 test file content"


def test_extract_document_groups(tmp_path):
    current = {
        "documents": [
            {
                "filename": "doc1.pdf",
                "status": "SUCCEEDED",
                "pages": 2,
                "duration": 1.2,
                "outputs": [("md", str(tmp_path / "doc1.md"))],
            }
        ]
    }
    groups = _extract_document_groups(current)
    assert len(groups) == 1
    assert groups[0]["filename"] == "doc1.pdf"
    assert groups[0]["status"] == "SUCCEEDED"


def test_resource_snapshot():
    # _resource_snapshot returns (memory_mb, cpu_percent), in that order -- matching
    # its only call site at web_app.py:2772. This test had the names backwards,
    # which silently swapped the assertions: it was really checking
    # `cpu_percent > 0.0`, which is not a safe invariant (a process can legitimately
    # read 0% CPU between two samples), while never checking that RSS is positive
    # (which, for a live process, always should be). Caught in CI (not locally) when
    # a quiet moment made cpu_percent read exactly 0.0.
    memory_mb, cpu_percent = _resource_snapshot()
    if memory_mb is not None:
        assert memory_mb > 0.0
    if cpu_percent is not None:
        assert cpu_percent >= 0.0


def test_ui_table_and_padding():
    table = _to_table([{"col1": 1, "col2": 2}])
    assert table is not None

    cols = _pad_columns(["a", "b"], count=4)
    assert len(cols) == 4


def test_render_landing_and_loading_screens():
    mock_btn_col = MagicMock()
    with patch("streamlit.markdown") as mock_md, \
         patch("streamlit.columns", return_value=[MagicMock(), mock_btn_col, MagicMock()]), \
         patch("streamlit.button", return_value=True), \
         patch("streamlit.session_state", {}), \
         patch("streamlit.rerun") as mock_rerun:
        render_landing_page()
        mock_md.assert_called()
        mock_rerun.assert_called_once()

    with patch("streamlit.markdown") as mock_md:
        render_loading_screen("Starting Engine", "Warming up ONNX")
        mock_md.assert_called()


def test_active_job_lifecycle():
    mock_state = MockSessionState({"active_job_ids": [], "active_job_id": None, "queued_job_meta": {"1": {"title": "Doc"}}})
    with patch("streamlit.session_state", mock_state):
        _set_active_job_ids([1, 2, 2, 3])
        assert _active_job_ids() == [1, 2, 3]
        assert mock_state.active_job_id == 1

        _remove_active_job(1)
        assert _active_job_ids() == [2, 3]
        assert "1" not in mock_state.queued_job_meta


def test_cleanup_queued_source(tmp_path):
    f = tmp_path / "queued.png"
    f.write_text("dummy")
    mock_state = MockSessionState({"queued_source_paths": {"job-1": str(f)}})
    with patch("streamlit.session_state", mock_state):
        _cleanup_queued_source("job-1")
        assert not f.exists()
        assert "job-1" not in mock_state.queued_source_paths


def test_clear_current_session_artifacts(tmp_path):
    sess_dir = tmp_path / "sess"
    sess_dir.mkdir()
    (sess_dir / "out.txt").write_text("data")

    mock_state = MockSessionState({
        "current_results": {"res": 1},
        "active_job_ids": [1],
        "active_job_id": 1,
        "queued_source_paths": {},
        "queued_job_meta": {},
    })
    with patch("blast_ocr.ui.web_app.get_session_output_dir", return_value=sess_dir), \
         patch("streamlit.session_state", mock_state):
        reclaimed = _clear_current_session_artifacts()
        assert reclaimed == 4
        assert not sess_dir.exists()
        assert mock_state.current_results is None
        assert mock_state.active_job_ids == []


def test_render_document_preview_multi(tmp_path):
    txt_file = tmp_path / "doc.txt"
    txt_file.write_text("Hello OCR Preview World!")
    doc_groups = [{
        "filename": "doc.txt",
        "outputs": [("txt", str(txt_file))],
    }]
    with patch("streamlit.expander") as mock_expander, \
         patch("streamlit.markdown"), \
         patch("streamlit.columns", return_value=[MagicMock(), MagicMock(), MagicMock()]):
        _render_document_preview_multi(doc_groups, [("txt", str(txt_file))])
        mock_expander.assert_called_once()

import pytest
from blast_ocr.core.exporter import sanitize_for_xml, save_output


def test_sanitization_removes_null_and_control_chars():
    input_str = "Hello\x00World\x08Test\nNewline\tTab"
    clean = sanitize_for_xml(input_str)
    assert "\x00" not in clean
    assert "\x08" not in clean
    assert "Hello" in clean
    assert "World" in clean
    assert "Newline" in clean
    assert "Tab" in clean


def test_sanitization_handles_none_and_empty():
    assert sanitize_for_xml(None) == ""
    assert sanitize_for_xml("") == ""


def test_docx_save(tmp_path):
    output_dir = str(tmp_path / "out")
    md_path, docx_path = save_output(
        "## Title Section\n\nParagraph text line.\n---\nNext page line.",
        "sample_doc",
        output_dir,
    )
    assert md_path is not None
    assert docx_path is not None
    assert (tmp_path / "out" / "sample_doc.md").exists()
    assert (tmp_path / "out" / "sample_doc.docx").exists()

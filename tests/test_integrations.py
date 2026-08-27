"""
tests/test_integrations.py

Unit tests for LangChain and LlamaIndex integration connectors.
"""

from unittest.mock import MagicMock, patch

from blast_ocr.integrations.langchain_loader import BlastOCRDocumentLoader
from blast_ocr.integrations.llamaindex_reader import BlastOCRReader


def test_langchain_loader(tmp_path):
    sample_file = tmp_path / "test_doc.pdf"
    sample_file.write_bytes(b"dummy pdf")

    mock_md = tmp_path / "test_doc.md"
    mock_md.write_text("# Chapter 1\nLangChain integration text.", encoding="utf-8")

    mock_result = {
        "status": "success",
        "pages_processed": 1,
        "output_files": {"md": str(mock_md)},
        "generated_files": {"md": str(mock_md)},
    }

    loader = BlastOCRDocumentLoader(
        file_path=sample_file,
        engine="rapidocr",
        secure_mode=True,
    )

    with patch("blast_ocr.integrations.langchain_loader.BlastPipeline") as mock_pipe_cls:
        mock_inst = MagicMock()
        mock_inst.process_job.return_value = mock_result
        mock_pipe_cls.return_value = mock_inst

        docs = loader.load()
        assert len(docs) == 1
        doc = docs[0]
        assert "LangChain integration text." in getattr(doc, "page_content", "")
        meta = getattr(doc, "metadata", {})
        assert meta["engine"] == "rapidocr"
        assert meta["secure_mode"] is True


def test_llamaindex_reader(tmp_path):
    sample_file = tmp_path / "test_report.png"
    sample_file.write_bytes(b"dummy img")

    mock_md = tmp_path / "test_report.md"
    mock_md.write_text("# Analysis Report\nLlamaIndex reader test.", encoding="utf-8")

    mock_result = {
        "status": "success",
        "pages_processed": 1,
        "output_files": {"md": str(mock_md)},
        "generated_files": {"md": str(mock_md)},
    }

    reader = BlastOCRReader(engine="rapidocr", secure_mode=False)

    with patch("blast_ocr.integrations.llamaindex_reader.BlastPipeline") as mock_pipe_cls:
        mock_inst = MagicMock()
        mock_inst.process_job.return_value = mock_result
        mock_pipe_cls.return_value = mock_inst

        docs = reader.load_data(sample_file, extra_info={"project": "BLAST"})
        assert len(docs) == 1
        doc = docs[0]
        assert "LlamaIndex reader test." in getattr(doc, "text", "")
        extra = getattr(doc, "extra_info", {})
        assert extra["project"] == "BLAST"
        assert extra["engine"] == "rapidocr"

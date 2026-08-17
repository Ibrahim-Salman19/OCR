"""
tests/test_cli_runner.py

Unit tests for B.L.A.S.T. CLI runner.
"""

import sys
from unittest.mock import patch, MagicMock
import pytest

from blast_ocr.cli import run_cli


def test_cli_help():
    with patch.object(sys, "argv", ["blast-ocr", "--help"]):
        with pytest.raises(SystemExit) as exc:
            run_cli()
        assert exc.value.code == 0


def test_cli_missing_source():
    with patch.object(sys, "argv", ["blast-ocr"]):
        code = run_cli()
        assert code == 1


def test_cli_nonexistent_source():
    with patch.object(sys, "argv", ["blast-ocr", "/nonexistent/path/doc.pdf"]):
        code = run_cli()
        assert code == 1


def test_cli_successful_run(tmp_path):
    img_path = str(tmp_path / "test.png")
    (tmp_path / "test.png").write_bytes(b"dummy")

    mock_result = {
        "status": "success",
        "generated_files": {"md": str(tmp_path / "test.md")},
        "metadata": {"page_count": 1},
    }

    with patch.object(sys, "argv", ["blast-ocr", img_path, "--engine", "rapidocr", "--json"]):
        with patch("blast_ocr.cli.BlastPipeline") as mock_pipeline_cls:
            mock_inst = MagicMock()
            mock_inst.process_job.return_value = mock_result
            mock_pipeline_cls.return_value = mock_inst

            code = run_cli()
            assert code == 0

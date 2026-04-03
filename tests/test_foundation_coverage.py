"""
Sprint 5: Foundation test coverage.
This covers __init__.py, config.py, exceptions.py, logging_config.py, and main.py
to achieve 100% coverage on core foundations.
"""

import sys
import pytest
import logging
import json
from unittest.mock import patch
from importlib import reload
from logging.handlers import RotatingFileHandler

from blast_ocr.core.exceptions import LowConfidenceError
import blast_ocr.logging_config as logging_config
import blast_ocr.main as main_module
import blast_ocr.config as config_module
import blast_ocr


class TestExceptionsCoverage:
    def test_low_confidence_error_init(self):
        """Covers missing lines in LowConfidenceError."""
        err = LowConfidenceError(0.45, 0.6)
        assert err.confidence == 0.45
        assert err.threshold == 0.6
        assert str(err) == "Confidence 0.45 < 0.60"


class TestLoggingConfigCoverage:
    def test_json_formatter_page_number_and_confidence(self):
        """Covers lines 33, 35 in logging_config.py JSONFormatter."""
        logger = logging_config.setup_logging("/tmp/test_logs")

        # We find the file handler that has the JSONFormatter
        json_handler = next(
            h
            for h in logger.handlers
            if isinstance(h, RotatingFileHandler) and h.level != logging.ERROR
        )
        formatter = json_handler.formatter
        assert formatter is not None

        record = logging.LogRecord("test", logging.INFO, "path.py", 10, "msg", (), None)
        record.page_number = 42
        record.confidence = 0.99

        output = formatter.format(record)
        parsed = json.loads(output)

        assert parsed["page_number"] == 42
        assert parsed["confidence"] == 0.99


class TestConfigCoverage:
    def test_detect_poppler_path_not_win32(self):
        """Covers line 25 where sys.platform is not win32."""
        with patch("sys.platform", "linux"):
            assert config_module._detect_poppler_path() is None

    def test_detect_poppler_path_win32_but_no_dir(self, tmp_path):
        """Covers win32 where directory doesn't exist."""
        with patch("sys.platform", "win32"), patch("os.path.isdir", return_value=False):
            assert config_module._detect_poppler_path() is None

    def test_get_settings(self):
        """Covers get_settings function."""
        s = config_module.get_settings()
        assert s is config_module.config

    def test_settings_config_dict_import_fallback(self):
        """Covers lines 3-5 and 97-99 where pydantic_settings fails to import."""
        import importlib

        # Save original sys.modules
        had_pydantic_settings = "pydantic_settings" in sys.modules
        orig_pydantic_settings = sys.modules.get("pydantic_settings")
        orig_config_module = sys.modules.pop("blast_ocr.config", None)

        try:
            real_import = __import__

            def mock_import(name, globals=None, locals=None, fromlist=(), level=0):
                if name == "pydantic_settings":
                    raise ImportError("simulated import error")
                # Make fallback deterministic across pydantic v1/v2.
                # If config falls back to `from pydantic import BaseSettings`, force it to fail.
                if name == "pydantic" and "BaseSettings" in (
                    fromlist or ()
                ):  # pragma: no cover - branch for import mechanics
                    raise ImportError("simulated BaseSettings import error")
                return real_import(name, globals, locals, fromlist, level)

            with patch("builtins.__import__", side_effect=mock_import):
                with pytest.raises(ImportError):
                    importlib.import_module("blast_ocr.config")

        finally:
            if had_pydantic_settings and orig_pydantic_settings is not None:
                sys.modules["pydantic_settings"] = orig_pydantic_settings
            elif "pydantic_settings" in sys.modules:
                del sys.modules["pydantic_settings"]

            if orig_config_module:
                sys.modules["blast_ocr.config"] = orig_config_module
            elif "blast_ocr.config" in sys.modules:
                del sys.modules["blast_ocr.config"]


class TestInitCoverage:
    def test_etree_import_error(self):
        """Covers lines 12-13 in __init__.py where lxml.etree raises ImportError."""
        real_import = builtins_import = __import__

        def mock_import(name, globals=None, locals=None, fromlist=(), level=0):
            if name == "lxml":
                raise ImportError("mocked no lxml")
            return builtins_import(name, globals, locals, fromlist, level)

        with patch("builtins.__import__", side_effect=mock_import):
            reload(blast_ocr)
        # Should complete without error due to pass block

        # Restore normal init state
        reload(blast_ocr)


class TestMainCoverage:
    def test_main_function(self):
        """Covers main.py lines 11-13."""
        with patch("blast_ocr.main.BlastPipeline") as mock_pipeline_cls:
            mock_pipeline = mock_pipeline_cls.return_value
            mock_pipeline.process_job.return_value = {"status": "success"}
            cb = lambda _cur, _tot: None

            result = main_module.main("dummy.png", "out_dir", cb, {"opt": 1})
            assert result["status"] == "success"
            mock_pipeline_cls.assert_called_once_with(config_overrides={"opt": 1})
            mock_pipeline.process_job.assert_called_once_with(
                "dummy.png", "out_dir", cb
            )

    def test_main_cli_entrypoint(self):
        """Covers the __name__ == '__main__' block in main.py."""
        import runpy

        with patch("sys.argv", ["main.py", "source.pdf", "--out", "out_dir"]):
            with patch("builtins.print"):
                with patch("blast_ocr.main.BlastPipeline") as mock_pipeline_cls:
                    mock_pipeline = mock_pipeline_cls.return_value
                    mock_pipeline.process_job.return_value = {"status": "success"}
                    original_main_mod = sys.modules.pop("blast_ocr.main", None)
                    try:
                        runpy.run_module("blast_ocr.main", run_name="__main__")
                    except SystemExit:
                        pass  # argparse can exit
                    finally:
                        if original_main_mod is not None:
                            sys.modules["blast_ocr.main"] = original_main_mod

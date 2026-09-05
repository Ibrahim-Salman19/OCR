"""
tests/test_api_dependencies_server.py

Tests for API security dependencies (API key verification) and
production FastAPI server runner (uvicorn launcher).
"""

import asyncio
from unittest.mock import patch
import pytest
from fastapi import HTTPException

from blast_ocr.api.dependencies import verify_api_key
from blast_ocr.api.server import start_server


def test_verify_api_key_anonymous_when_no_config(monkeypatch):
    from blast_ocr.config import config
    monkeypatch.setattr(config, "api_key", None)
    result = asyncio.run(verify_api_key(x_api_key=None, authorization=None))
    assert result == "anonymous-dev"


def test_verify_api_key_header_matching(monkeypatch):
    from blast_ocr.config import config
    monkeypatch.setattr(config, "api_key", "secret-token-123")
    result = asyncio.run(verify_api_key(x_api_key="secret-token-123", authorization=None))
    assert result == "secret-token-123"


def test_verify_api_key_bearer_matching(monkeypatch):
    from blast_ocr.config import config
    monkeypatch.setattr(config, "api_key", "bearer-token-456")
    result = asyncio.run(verify_api_key(x_api_key=None, authorization="Bearer bearer-token-456"))
    assert result == "bearer-token-456"

    # Also test apikey prefix
    result_apikey = asyncio.run(verify_api_key(x_api_key=None, authorization="ApiKey bearer-token-456"))
    assert result_apikey == "bearer-token-456"

    # Also test raw single token authorization header
    result_raw = asyncio.run(verify_api_key(x_api_key=None, authorization="bearer-token-456"))
    assert result_raw == "bearer-token-456"


def test_verify_api_key_unauthorized_missing_or_invalid(monkeypatch):
    from blast_ocr.config import config
    monkeypatch.setattr(config, "api_key", "secret-token-123")

    # Missing
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(verify_api_key(x_api_key=None, authorization=None))
    assert exc_info.value.status_code == 401

    # Invalid
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(verify_api_key(x_api_key="wrong-key", authorization=None))
    assert exc_info.value.status_code == 401


def test_start_server_launcher():
    with patch("uvicorn.run") as mock_run:
        start_server(host="127.0.0.1", port=9000, reload=True, workers=2)
        mock_run.assert_called_once_with(
            "blast_ocr.api.app:app",
            host="127.0.0.1",
            port=9000,
            reload=True,
            workers=2,
            log_level="info",
        )


def test_server_main_cli(monkeypatch):
    import runpy
    monkeypatch.setattr("sys.argv", ["blast_ocr.api.server", "--host", "127.0.0.1", "--port", "8080", "--reload", "--workers", "3"])
    with patch("uvicorn.run") as mock_run:
        runpy.run_module("blast_ocr.api.server", run_name="__main__")
        mock_run.assert_called_once_with(
            "blast_ocr.api.app:app",
            host="127.0.0.1",
            port=8080,
            reload=True,
            workers=3,
            log_level="info",
        )

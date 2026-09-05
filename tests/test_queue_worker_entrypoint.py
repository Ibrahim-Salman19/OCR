"""
tests/test_queue_worker_entrypoint.py

Unit test suite for blast_ocr.queue.worker entrypoint.
Covers worker startup, CLI argument parsing, Redis availability check,
heartbeat lifecycle, RQ worker orchestration, and fatal error cleanup.
"""

import sys
from unittest.mock import patch, MagicMock

from blast_ocr.queue.worker import main


def test_worker_redis_unavailable(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["blast_ocr.queue.worker"])
    with patch("blast_ocr.queue.client.is_queue_available", return_value=False):
        exit_code = main()
        assert exit_code == 1


def test_worker_success_lifecycle(monkeypatch):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "blast_ocr.queue.worker",
            "--worker-id",
            "test-worker-1",
            "--queues",
            "high,default",
            "--heartbeat-interval",
            "2.0",
        ],
    )
    mock_redis = MagicMock()
    mock_heartbeat = MagicMock()
    mock_queue = MagicMock()
    mock_queue.name = "high"
    mock_worker_instance = MagicMock()

    with patch("blast_ocr.queue.client.is_queue_available", return_value=True):
        with patch("blast_ocr.queue.client.get_redis_connection", return_value=mock_redis):
            with patch("blast_ocr.queue.heartbeat.HeartbeatDaemon", return_value=mock_heartbeat):
                with patch("blast_ocr.queue.client.get_queue", return_value=mock_queue):
                    with patch("rq.Worker", return_value=mock_worker_instance):
                        exit_code = main()
                        assert exit_code == 0
                        mock_heartbeat.start.assert_called_once()
                        mock_worker_instance.work.assert_called_once_with(with_scheduler=False)
                        mock_heartbeat.stop.assert_called_once()


def test_worker_fatal_error_stops_heartbeat(monkeypatch):
    monkeypatch.setattr(
        sys,
        "argv",
        ["blast_ocr.queue.worker", "--worker-id", "test-fatal"],
    )
    mock_redis = MagicMock()
    mock_heartbeat = MagicMock()
    mock_queue = MagicMock()
    mock_queue.name = "high"

    with patch("blast_ocr.queue.client.is_queue_available", return_value=True):
        with patch("blast_ocr.queue.client.get_redis_connection", return_value=mock_redis):
            with patch("blast_ocr.queue.heartbeat.HeartbeatDaemon", return_value=mock_heartbeat):
                with patch("blast_ocr.queue.client.get_queue", return_value=mock_queue):
                    with patch("rq.Worker", side_effect=RuntimeError("RQ failure")):
                        exit_code = main()
                        assert exit_code == 0
                        mock_heartbeat.start.assert_called_once()
                        mock_heartbeat.stop.assert_called_once()

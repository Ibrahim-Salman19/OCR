"""
PHASE 10: Streamlit UI Logic Mocking.
Boosts coverage for blast_ocr/ui/web_app.py.
"""

from unittest.mock import MagicMock, patch


class MockSessionState(dict):
    """A mock for Streamlit session state that allows attribute and item access."""

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)

    def __setattr__(self, name, value):
        self[name] = value


def test_ui_session_state_initialization():
    """Verify that session state is correctly initialized if missing."""
    mock_state = MockSessionState()
    with patch("streamlit.session_state", mock_state):
        from blast_ocr.ui.web_app import init_session_state

        init_session_state()
        assert "total_scans" in mock_state
        assert mock_state.total_scans == 142
        assert "pages_decoded" in mock_state
        assert "session_id" in mock_state


def test_ui_output_dir_isolation():
    """Verify that per-session UUID directories are used (BUG-DATA-BLEED-01)."""
    mock_state = MockSessionState({"session_id": "test-uuid-123", "output_dir": None})
    with patch("streamlit.session_state", mock_state):
        from blast_ocr.ui.web_app import get_session_output_dir

        out_dir = get_session_output_dir()
        assert "test-uuid-123" in str(out_dir)
        assert mock_state.output_dir == str(out_dir)


def test_ui_file_handler_error_grace():
    """Verify that the UI handles upload errors without crashing."""
    mock_file = MagicMock()
    mock_file.name = "corrupt.pdf"
    mock_file.getbuffer.side_effect = Exception("Disk failure")

    mock_pipeline = MagicMock()
    mock_db = MagicMock()
    mock_state = MockSessionState(
        {"session_id": "test-uuid", "output_dir": "test_out", "current_results": None}
    )

    with patch("streamlit.file_uploader", return_value=[mock_file]):
        with patch("streamlit.button", return_value=True):
            with patch("streamlit.session_state", mock_state):
                from blast_ocr.ui.web_app import handle_file_upload

                handle_file_upload(mock_pipeline, mock_db)
                assert mock_state.current_results["summary"][0]["STATUS"] == "FAILED"
                assert (
                    "Disk failure" in mock_state.current_results["summary"][0]["ERROR"]
                )

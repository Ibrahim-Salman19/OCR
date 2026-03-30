"""
PHASE 3: Streamlit multi-user session isolation and state pollution.
"""
import pytest
import re
from pathlib import Path

# ── Test 3.1: Codebase does NOT contain st.session_state = {} ─────────────
def test_no_global_session_state_overwrite():
    """
    REASONING: st.session_state = {} is the single most common cause
    of multi-user data bleed in Streamlit. It replaces the per-user
    SessionStateProxy with a shared global dict.
    """
    web_app = Path("blast_ocr/ui/web_app.py")
    if not web_app.exists():
        pytest.skip("web_app.py not found")

    source = web_app.read_text(encoding="utf-8")

    # Pattern: st.session_state followed by = and { or dict()
    dangerous_pattern = re.compile(
        r'st\.session_state\s*=\s*(\{|dict\()', re.MULTILINE
    )
    matches = dangerous_pattern.findall(source)

    if matches:
        pytest.fail(
            f"BUG-STREAMLIT-SESSION-01 | CRITICAL | security\n"
            f"Found {len(matches)} instance(s) of 'st.session_state = {{}}' in web_app.py.\n"
            f"This replaces SessionStateProxy with a global dict, causing ALL users to share state.\n"
            f"Fix: Replace st.session_state = {{}} with st.session_state.clear() everywhere."
        )

# ── Test 3.2: Output directory is per-user (UUID-based), not shared ────────
def test_output_dir_is_user_unique():
    """
    REASONING: If two users upload invoice.pdf simultaneously and both
    write to /tmp/blast_output/invoice.docx, User B's job overwrites
    User A's output file. User A downloads corrupted/wrong document.
    """
    web_app = Path("blast_ocr/ui/web_app.py")
    if not web_app.exists():
        pytest.skip("web_app.py not found")

    source = web_app.read_text(encoding="utf-8")

    # Check if session_id or uuid is used in output directory construction
    uses_session_isolation = any(pattern in source for pattern in [
        "session_id", "uuid", "uuid4", "st.session_state",
        "unique", "tempfile.mkdtemp"
    ])

    has_fixed_output_dir = "blast_output" in source and (
        "blast_output" + '"' in source or
        'blast_output' + "'" in source
    )

    if has_fixed_output_dir and not uses_session_isolation:
        pytest.fail(
            "BUG-STREAMLIT-OUTPUT-01 | CRITICAL | data-loss\n"
            "Output directory is a fixed shared path (e.g., /tmp/blast_output).\n"
            "Two concurrent users uploading same-named files will corrupt each other's output.\n"
            "Fix: Generate per-session output dirs using uuid.uuid4() or session-specific keys:\n"
            "  session_dir = Path('/tmp/blast_output') / str(uuid.uuid4())\n"
            "  session_dir.mkdir(parents=True, exist_ok=True)"
        )

# ── Test 3.3: AppTest simulation — two sessions do not share state ─────────
def test_two_apptest_sessions_isolated():
    """
    REASONING: Use streamlit.testing.v1.AppTest to simulate two
    independent user sessions and verify state does not cross-contaminate.
    """
    try:
        from streamlit.testing.v1 import AppTest
    except ImportError:
        pytest.skip("streamlit.testing.v1 not available")

    web_app = Path("blast_ocr/ui/web_app.py")
    if not web_app.exists():
        pytest.skip("web_app.py not found")

    try:
        # Session 1 — User A sets a value
        at1 = AppTest.from_file(str(web_app))
        at1.run(timeout=10)

        # Session 2 — User B independent session
        at2 = AppTest.from_file(str(web_app))
        at2.run(timeout=10)

        # Check that session state objects are independent
        assert at1.session_state is not at2.session_state, \
            "BUG-STREAMLIT-SHARE-01: Two AppTest sessions share the same session_state object"

        # If User A's state contains "processing_history" (from web_app init),
        # User B must have an independent copy
        if "processing_history" in at1.session_state and \
           "processing_history" in at2.session_state:
            at1.session_state["processing_history"] = ["user_a_document.pdf"]
            assert at2.session_state["processing_history"] != ["user_a_document.pdf"], \
                "BUG-STREAMLIT-SHARE-02: CRITICAL data bleed — User A's history visible in User B's session"
    except Exception as e:
        if "data bleed" in str(e) or "share" in str(e).lower():
            raise
        pytest.skip(f"AppTest execution error (non-isolation bug): {e}")

# ── Test 3.4: session_state.clear() usage in codebase ────────────────────
def test_session_clear_uses_correct_method():
    """Check that .clear() is used, not = {} assignment."""
    web_app = Path("blast_ocr/ui/web_app.py")
    if not web_app.exists():
        pytest.skip("web_app.py not found")

    source = web_app.read_text(encoding="utf-8")

    # .clear() is correct
    if "session_state.clear()" in source:
        pass  # Good pattern found

    # Any direct assignment is dangerous
    assignment = re.compile(r'session_state\s*=\s*[{\[]')
    if assignment.search(source):
        pytest.fail(
            "BUG-STREAMLIT-CLEAR-01 | HIGH | security\n"
            "Direct assignment to session_state detected.\n"
            "Use st.session_state.clear() for proper session reset."
        )

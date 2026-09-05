"""
tests/test_cleanup_manager.py

Unit test suite for blast_ocr.core.cleanup_manager.
Validates automated system stewardship, stale session purging,
disk statistics telemetry, and ghost data prevention.
"""

import os
import time
from blast_ocr.core.cleanup_manager import CleanupManager


def test_cleanup_stale_sessions_nonexistent_dir(tmp_path):
    nonexistent = str(tmp_path / "does_not_exist")
    saved = CleanupManager.cleanup_stale_sessions(nonexistent, max_age_hours=1)
    assert saved == 0


def test_cleanup_stale_sessions_purges_old_folders(tmp_path):
    base_dir = tmp_path / "sessions"
    base_dir.mkdir()

    # Fresh session folder (modified right now)
    fresh_dir = base_dir / "session_fresh"
    fresh_dir.mkdir()
    fresh_file = fresh_dir / "doc.txt"
    fresh_file.write_text("fresh document")

    # Stale session folder (modified 48 hours ago)
    stale_dir = base_dir / "session_stale"
    stale_dir.mkdir()
    stale_file = stale_dir / "stale.txt"
    stale_file.write_text("stale document content that should be purged")

    old_time = time.time() - (48 * 3600)
    os.utime(str(stale_dir), (old_time, old_time))

    saved_bytes = CleanupManager.cleanup_stale_sessions(str(base_dir), max_age_hours=24)

    assert saved_bytes > 0
    assert not stale_dir.exists()
    assert fresh_dir.exists()
    assert fresh_file.exists()


def test_cleanup_stale_sessions_error_handling(tmp_path, monkeypatch):
    base_dir = tmp_path / "sessions"
    base_dir.mkdir()

    stale_dir = base_dir / "stale_error"
    stale_dir.mkdir()
    old_time = time.time() - (48 * 3600)
    os.utime(str(stale_dir), (old_time, old_time))

    def mock_rmtree(path):
        raise PermissionError("Locked file simulation")

    monkeypatch.setattr("shutil.rmtree", mock_rmtree)
    saved = CleanupManager.cleanup_stale_sessions(str(base_dir), max_age_hours=24)
    # Failed deletion caught gracefully
    assert saved == 0


def test_get_system_disk_stats(tmp_path):
    base_dir = tmp_path / "outputs"
    # Nonexistent dir returns 0
    stats_empty = CleanupManager.get_system_disk_stats(str(base_dir))
    assert stats_empty["total_size_mb"] == 0.0
    assert stats_empty["session_count"] == 0

    # Create directories and files
    base_dir.mkdir()
    sub1 = base_dir / "job1"
    sub1.mkdir()
    f1 = sub1 / "test.bin"
    f1.write_bytes(b"A" * 1024 * 1024)  # 1 MB

    sub2 = base_dir / "job2"
    sub2.mkdir()
    f2 = sub2 / "test2.bin"
    f2.write_bytes(b"B" * 512 * 1024)   # 0.5 MB

    stats = CleanupManager.get_system_disk_stats(str(base_dir))
    assert stats["session_count"] >= 2
    assert 1.4 <= stats["total_size_mb"] <= 1.6

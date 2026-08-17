"""
tests/test_alembic_migration.py

Regression tests for the Alembic <-> create_all() coordination bug found and
fixed in ADR 0009. Two independent, previously-broken things are covered:

1. `alembic.ini` had a `[logging] default_level = INFO` key that is not valid
   `logging.fileConfig` format -- `alembic upgrade head` failed immediately
   with `KeyError: 'formatters'` before ever touching the database. Alembic
   was never actually runnable despite the migration files existing.
2. `OCRDatabase.__init__` bootstraps schema via `Base.metadata.create_all()`,
   which has no concept of Alembic migration history. A database created
   this way had no `alembic_version` row, so a later `alembic upgrade head`
   would try to re-create tables that already exist and fail outright.

These run real `alembic` commands against a real temp SQLite file -- not
mocks -- since the bug was specifically about the CLI/env.py wiring being
broken, which a unit test mocking alembic away would never have caught.
"""

import os
import sqlite3
import subprocess
import sys
import tempfile

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _run_alembic(db_url, *args):
    env = dict(os.environ)
    env["BLAST_OCR_DATABASE_URL"] = db_url
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )


@pytest.fixture
def temp_db_path():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    os.unlink(path)  # alembic/sqlite3 will create it fresh
    yield path
    if os.path.exists(path):
        os.unlink(path)


def test_alembic_ini_logging_config_is_valid(temp_db_path):
    """`alembic upgrade head` must not fail on fileConfig() parsing alembic.ini."""
    result = _run_alembic(f"sqlite:///{temp_db_path}", "upgrade", "head")
    assert result.returncode == 0, (
        f"alembic upgrade head failed (alembic.ini logging config regression?): "
        f"stdout={result.stdout}\nstderr={result.stderr}"
    )


def test_alembic_upgrade_head_creates_expected_tables(temp_db_path):
    result = _run_alembic(f"sqlite:///{temp_db_path}", "upgrade", "head")
    assert result.returncode == 0, result.stderr

    conn = sqlite3.connect(temp_db_path)
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    conn.close()
    assert {"ocr_jobs", "ocr_results", "ocr_metrics", "alembic_version"} <= tables


def test_create_all_bootstrap_is_stamped_and_future_upgrade_is_noop(temp_db_path):
    """
    Simulates the real app startup path (OCRDatabase.__init__ ->
    Base.metadata.create_all()), then verifies a subsequent
    `alembic upgrade head` is a clean no-op instead of erroring with
    "table already exists" -- the exact failure mode this fix closes.
    """
    from blast_ocr.storage.database import OCRDatabase

    db = OCRDatabase(f"sqlite:///{temp_db_path}")
    db.close()

    conn = sqlite3.connect(temp_db_path)
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    version_rows = conn.execute("SELECT version_num FROM alembic_version").fetchall()
    conn.close()

    assert "ocr_jobs" in tables
    assert "alembic_version" in tables, (
        "create_all()-bootstrapped database was not stamped with an Alembic "
        "baseline -- a later `alembic upgrade head` would fail on tables that "
        "already exist."
    )
    assert version_rows == [("001_initial_schema",)]

    result = _run_alembic(f"sqlite:///{temp_db_path}", "upgrade", "head")
    assert result.returncode == 0, (
        f"alembic upgrade head against a create_all()-bootstrapped DB must be "
        f"a no-op, not an error: stdout={result.stdout}\nstderr={result.stderr}"
    )

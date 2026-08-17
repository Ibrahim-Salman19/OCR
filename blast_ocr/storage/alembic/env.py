"""
blast_ocr.storage.alembic.env

Alembic environment configuration for database schema migrations.
"""

from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context

import sys
from pathlib import Path
REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

from blast_ocr.storage.database import Base, config

config_alembic = context.config

if config_alembic.config_file_name:
    # disable_existing_loggers=False: fileConfig() defaults to tearing down
    # every logger object that already exists in the process, which is
    # catastrophic when Alembic is invoked programmatically (e.g.
    # OCRDatabase._stamp_alembic_baseline_if_needed()) from inside a long-lived
    # process that already has its own loggers configured -- app logging (and,
    # in tests, pytest's caplog capture) would otherwise go silently dark for
    # any logger created before this line runs. This bit us for real: it
    # silenced unrelated tests' caplog assertions once any test in the same
    # pytest session had constructed an OCRDatabase().
    fileConfig(config_alembic.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


def _resolve_db_url() -> str:
    """
    Prefer a URL explicitly set on the Alembic Config object (e.g. via
    `cfg.set_main_option("sqlalchemy.url", ...)` from a programmatic caller
    such as OCRDatabase's baseline-stamping logic, or an `alembic -x` /
    `-o sqlalchemy.url=...` CLI override), falling back to the app's global
    config.database_url. Without this fallback-aware resolution, any
    programmatic Alembic invocation targeting a specific database silently
    operated on config.database_url instead -- see docs/adr/0009.
    """
    return config_alembic.get_main_option("sqlalchemy.url") or config.database_url


def run_migrations_offline() -> None:
    url = _resolve_db_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        {"sqlalchemy.url": _resolve_db_url()},
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

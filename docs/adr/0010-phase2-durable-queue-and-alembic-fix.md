Title: Phase 2 -- Durable Queue (Redis + RQ), and Fixing a Non-Functional Alembic Setup
Status: accepted
Date: 2026-08-13

Context:
- EXECUTION_PLAN.md Phase 5/8 calls for durable, out-of-process job execution: closing the
  browser or restarting the web process must not kill an in-flight OCR job. Prior to this
  change, `BlastPipeline.process_job()` only ran synchronously inside whatever process called
  it (the Streamlit script run, in the web UI's case). A `run_background_job()` function and a
  `render_mission_control()` polling UI already existed in `web_app.py` suggesting async
  processing was intended, but `run_background_job()` had zero callers and `handle_file_upload`
  called `pipeline.process_job()` inline and blocking -- the same "architecture built, never
  wired" pattern found throughout this codebase in ADR 0009.
- Separately, while building the queue's job-tracking integration, `alembic.ini` and
  `blast_ocr/storage/alembic/env.py` were found to be non-functional: `alembic upgrade head`
  failed immediately with `KeyError: 'formatters'` because `alembic.ini`'s `[logging]` section
  used `default_level = INFO`, which is not valid `logging.fileConfig()` format. Migration files
  existed and were unit-tested in isolation, but the Alembic CLI itself had never actually been
  run against them. `alembic` was also missing from `requirements.txt` entirely.
- Fixing that surfaced a second, independent bug: `env.py` resolved the database URL from the
  global `blast_ocr.config.config.database_url` singleton unconditionally, ignoring any URL set
  on the `alembic.config.Config` object passed to a programmatic caller. This meant any
  script-driven Alembic invocation (needed for the create_all()-vs-migrations reconciliation
  below, and for CI's planned "test upgrade/downgrade" gate) would silently operate against
  whatever database happened to be configured globally rather than its intended target.
- A third, related gap: `OCRDatabase.__init__` bootstraps schema via
  `Base.metadata.create_all()`, which has no concept of Alembic migration history. A database
  created this way has no `alembic_version` row, so a later `alembic upgrade head` (e.g. after a
  schema-changing release) would try to re-run `001_initial_schema` against tables that already
  exist and fail with "table already exists" -- meaning Alembic was unusable on every database
  the app itself had created, only on databases created purely by `alembic upgrade head` from
  scratch.

Decision:
- Added `blast_ocr/queue/` (client.py, tasks.py, worker.py): `enqueue_job()` creates the durable
  DB job record and pushes `run_ocr_job` (a plain, importable module-level function -- RQ
  serializes job references as a dotted import path, not a pickled closure) onto a Redis-backed
  RQ queue; `python -m blast_ocr.queue.worker` runs a worker process that executes queued jobs
  by calling the same `BlastPipeline.process_job()` used by the synchronous path -- the queue is
  a different way of invoking the pipeline, not a second implementation of it.
- `config.queue_backend` (`"sync"` default / `"redis"`) gates this: running BLAST requires no
  Redis server unless a deployment explicitly opts in.
- `web_app.py`'s `handle_file_upload` now checks `queue_backend` and, when set to `"redis"` and
  reachable, calls `enqueue_job()` and sets `active_job_id` instead of blocking on
  `pipeline.process_job()` -- which means `render_mission_control()`'s polling UI, previously
  unreachable dead code in the main upload path, now actually drives a live view for queued
  jobs. Falls back to the synchronous path automatically if Redis isn't reachable.
- Fixed `alembic.ini`'s `[logging]` section to be valid `logging.fileConfig` format, and added
  `alembic` to `requirements.txt`.
- Fixed `env.py` to resolve the database URL via
  `config_alembic.get_main_option("sqlalchemy.url") or config.database_url` instead of always
  reading the global singleton, so a programmatically-targeted database is actually the one
  Alembic operates on.
- Added `OCRDatabase._stamp_alembic_baseline_if_needed()`: after `create_all()`, if the schema's
  tables exist but no `alembic_version` row does, stamp the database at `head` using Alembic's
  own `command.stamp()` (via `alembic.config.Config` with the URL explicitly set, exercising the
  `env.py` fix above). This makes every database the app has ever bootstrapped agree with
  Alembic about its migration history, so future schema-changing releases can migrate it
  correctly instead of failing on first contact with an existing installation.
- `tests/test_queue.py`: integration tests run against a real local `redis-server` (installed
  via apt for this environment; auto-skipped if unreachable) and a real `rq.SimpleWorker`
  processing an actual queued job end-to-end -- not mocked, since the entire point of a queue
  backend is durability across real process boundaries.
- `tests/test_alembic_migration.py`: runs the real `alembic` CLI as a subprocess against a real
  temp SQLite file, covering both the `alembic.ini` parsing bug and the create_all()-vs-stamp
  reconciliation, since both were CLI/wiring bugs a pure-Python unit test mocking Alembic away
  would never have caught.

Consequences:
- Positive:
  - OCR jobs can now survive the web process restarting or a user closing their browser, when
    the operator opts into the Redis backend -- genuinely verified against a real worker
    process, not asserted from reading the code.
  - `alembic upgrade head` is, for the first time, an operation that actually works -- against
    both fresh databases and every database this app itself has ever created via `create_all()`.
  - The dead `render_mission_control` UI is now load-bearing rather than decorative.
- Negative / follow-up:
  - The queue path currently assumes the web process and the RQ worker process share a
    filesystem (the uploaded file's temp path is passed by path, not by content) -- true for a
    single-machine or Docker-Compose-with-shared-volume deployment (the target this plan
    describes), but not for workers on separate hosts without shared storage. Phase 3's object
    storage abstraction is the fix for that; until then, `queue_backend="redis"` should only be
    enabled when the worker can read the same temp directory as the web process.
  - `JobFingerprint`-based idempotency is computed at enqueue time but not yet consulted to
    deduplicate identical repeated submissions -- deferred, same as noted in ADR 0009.

Title: Phase 3 -- S3-Compatible Object Storage Abstraction
Status: accepted
Date: 2026-08-13

Context:
- EXECUTION_PLAN.md Phase 8 calls for keeping large blobs (source uploads, intermediate
  artifacts, final exports) out of the database and in object storage, with database rows
  limited to metadata/job state/audit records.
- BLAST has always written outputs directly to a local `output_dir` via `shutil`/`Path`
  operations. This is fine for a single-machine deployment but doesn't extend to a
  multi-worker or multi-host deployment (Phase 2's Redis queue can dispatch a job to a worker
  process that may not share a filesystem with the web process, once workers scale beyond one
  host) or provide the artifact durability/retention story production operation needs.

Decision:
- Added `blast_ocr/storage/object_store.py`: a small `ObjectStorage` protocol with two
  implementations -- `LocalFilesystemStorage` (default, `config.storage_backend="local"`, zero
  extra infra) and `S3ObjectStorage` (`boto3`, works against real AWS S3 or any S3-compatible
  endpoint including MinIO via `endpoint_url`). `boto3` is imported lazily so a `"local"`
  deployment never needs it installed.
- `get_object_storage(settings=None)` is the factory. It accepts an explicit settings object
  (falling back to the global config singleton only if omitted) -- this exists specifically
  because the first implementation read the global singleton unconditionally, which silently
  ignored a `BlastPipeline` instance's own `self._config.s3_bucket` override and wrote to the
  wrong bucket. This was caught by `tests/test_object_store.py::TestPipelineObjectStorageMirror`
  failing (the mirror step logged success, but the test's own client, reading the same global
  default bucket the code had used, still found the object -- the test only caught the bug
  because it asserted against the *intended* bucket a caller had configured, not whatever bucket
  the code actually used). It is the same class of "reads global mutable state instead of the
  caller's own config" defect fixed for OCR engine selection in ADR 0009, recurring in genuinely
  new code within this same session -- worth remembering as a standing hazard whenever a factory
  function defaults to a global singleton.
- `BlastPipeline.process_job()` mirrors every output artifact (plus the manifest) to object
  storage when `config.storage_backend == "s3"`, additive and non-blocking: mirror failure logs
  a warning but does not fail the job, since outputs remain available locally either way. This
  is deliberately scoped to the write-after-processing path rather than a full rewrite of the
  pipeline's internal temp-file handling during OCR (which stays local-filesystem-based) --
  lower blast radius for the actual production gap this closes (durable, retained exports) while
  leaving Phase 2's queue-worker shared-filesystem assumption for uploaded originals as a
  documented follow-up rather than pretending a full distributed-storage rewrite happened.
- Verification: `LocalFilesystemStorage` tested directly (including a path-traversal rejection
  test: a job_id/filename-derived key must not escape the storage root via `../`).
  `S3ObjectStorage` tested against `moto`'s in-process mocked S3 for pure logic correctness, AND
  against a real MinIO container (started via `docker run minio/minio`, torn down after) when
  Docker is reachable in the environment -- both passed, so both the mocked-logic path and a
  genuine network round trip against a real S3-compatible server are verified, not just one or
  the other.

Consequences:
- Positive:
  - A deployment that needs durable, centrally-retained artifact storage (rather than "whatever
    disk the worker happened to run on") can turn it on via one config value, with real
    verification (moto + real MinIO) that the backend actually works.
  - The bucket/endpoint-scoping bug this surfaced is a useful, concrete reminder that "add a
    settings parameter with a global-singleton default" is not automatically safe -- callers
    holding their own config object must be checked to actually pass it.
- Negative / follow-up:
  - The queue worker (Phase 2) still expects to read the uploaded source file from a shared
    local filesystem path, not from object storage -- a multi-host worker deployment needs that
    closed before `queue_backend="redis"` + `storage_backend="s3"` can be combined safely across
    separate hosts. Documented, not yet implemented.
  - No retention/lifecycle policy (Phase 8's "original upload: 7/30/90 days" configurable
    retention) is implemented yet -- mirroring is unconditional once enabled, with no automatic
    cleanup.

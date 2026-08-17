B.L.A.S.T. OCR — Production Architecture Plan v2

> **Implementation status (2026-08-13)**: A first implementation pass (see ADRs 0009-0013)
> found that several P0 items below had been built as isolated, unit-tested modules but never
> actually wired into the real request path -- including the exact cross-job engine-selection
> race this document's section 1.1 was written to prevent. That gap is now closed and
> regression-tested. Completed from the P0/P1 lists below: items 1-7, 9, 11-16 (benchmark
> corpus, correctness fixes, immutable JobConfig now actually used for engine selection, typed
> pipeline contracts, Tier-0 router, secure upload validation, durable job state model, database
> migrations, structured logs + metrics, dependency lock, CI security scanning), plus P1 items
> 17-19, 22 (durable queue, object storage, idempotency fingerprinting groundwork,
> OpenTelemetry). Explicitly NOT done: sandboxed per-job OCR execution (item 8 -- Docker
> isolation exists at the deployment level, not yet per-job), SLO dashboards/backup-restore
> testing/load testing/canary deployment (items 23-27), SBOM/artifact provenance (29-30), and
> all of P2. See `docs/adr/0009-*` through `docs/adr/0013-*` for what was actually verified and
> how, and `docs/COMPETITIVE_LANDSCAPE.md` for how the remaining gaps compare to the market.

1. First: change these parts of the existing plan
1.1 Do NOT implement _engine_name_override

The existing proposal fixes the UI → worker disconnect by introducing:

_engine_name_override: Optional[str] = None

and then changing that global before workers execute.

That solves one bug by creating another concurrency problem.

Imagine:

Job A -> RapidOCR
Job B -> EasyOCR

If both jobs overlap:

Job A sets global = rapidocr
Job B sets global = easyocr
Job A worker reads global -> easyocr
Production solution

Create an immutable per-job configuration:

@dataclass(frozen=True)
class JobConfig:
    ocr_engine: str
    enable_tier0: bool
    enable_book_intelligence: bool
    language: str | None
    secure_mode: bool
    ...

Then:

UI/API
  ↓
JobConfig
  ↓
BlastPipeline
  ↓
PageTask(job_config=...)
  ↓
OCR worker

Workers should never consult a mutable global configuration to decide job behavior.

If worker processes need expensive engine reuse, create a worker-local EngineRegistry, keyed by immutable engine/model configuration:

Worker Process
├── RapidOCR instance
├── EasyOCR instance
└── EngineRegistry

This gives engine reuse without cross-job state leakage.

1.2 Rewrite the environment-variable recovery logic

The existing plan proposes temporarily deleting environment variables and repeatedly constructing OCRConfig() to find the bad one.

I would not do that in production.

Environment configuration should be:

load
 ↓
validate
 ↓
fail fast

not:

load
 ↓
validation error
 ↓
mutate os.environ
 ↓
retry
 ↓
silently continue

Production startup should fail with something like:

ConfigurationError

BLAST_OCR_MAX_WORKERS:
    expected integer >= 1
    received: "abc"

Use Pydantic's structured ValidationError.errors() to identify invalid fields. Development mode may provide friendlier fallbacks, but production mode should not silently repair malformed operational configuration.

1.3 Do NOT make 0.90 a magic Tier-0 production threshold

The existing plan proposes:

if confidence >= 0.90:
    skip_ocr()

That is not sufficient.

Native PDF extraction is fundamentally different from OCR confidence. A PDF may technically contain text while producing:

garbled encoding
wrong reading order
missing characters
invisible OCR layer
duplicated text
broken ligatures
incorrect column order
empty spaces between glyphs

The Tier-0 router needs a quality classifier, not merely a confidence number.

Use something like:

NativeTextQuality(
    character_count,
    printable_ratio,
    unicode_replacement_ratio,
    alphanumeric_ratio,
    whitespace_sanity,
    duplicate_ratio,
    text_coverage,
    reading_order_score,
    extraction_error_count,
)

Then determine:

PASS_NATIVE
OCR_REQUIRED
HYBRID_REQUIRED
REJECT_PAGE

The threshold must be calibrated on the B.L.A.S.T. gold corpus rather than chosen manually.

1.4 Do NOT blindly pin rapidocr_onnxruntime==1.4.4

This is an important finding from the current web research.

The active RapidOCR upstream now documents installation using:

pip install rapidocr onnxruntime

rather than the old standalone integration described in your existing dependency plan. The active repository's v3.9.0 release also moved its defaults to PP-OCRv6 models.

Therefore I would add an engine modernization bake-off:

A. Existing rapidocr_onnxruntime 1.4.4
B. Current unified RapidOCR
C. EasyOCR

Benchmark all three against exactly the same gold set.

Only migrate if the unified version meets your regression gates.

Your current RapidOCR result—CER 0.1916, 100% fact-check pass, and ~7.7× CPU speed advantage over EasyOCR—is a valuable baseline and should remain the benchmark reference.

2. Target production architecture

I would evolve B.L.A.S.T. from:

Streamlit
    ↓
BlastPipeline
    ↓
OCR
    ↓
files

into:

                   ┌─────────────────┐
User ──HTTPS──────►│ Web UI          │
                   │ Streamlit       │
                   └────────┬────────┘
                            │
                            ▼
                   ┌─────────────────┐
                   │ Job/API Layer   │
                   └────────┬────────┘
                            │
             ┌──────────────┼──────────────┐
             ▼              ▼              ▼
       Object Storage   Job Database   Durable Queue
             │                             │
             │                             ▼
             │                    ┌─────────────────┐
             └───────────────────►│ OCR Workers     │
                                  │ sandboxed       │
                                  └────────┬────────┘
                                           │
                        ┌──────────────────┼──────────────┐
                        ▼                  ▼              ▼
                    Tier-0              OCR Engine      Layout
                                           │
                                           ▼
                                   Book Intelligence
                                           │
                                           ▼
                                      Exporter
                                           │
                                           ▼
                                      Artifacts

Streamlit can remain the user-facing control plane. But OCR execution should no longer depend on a Streamlit session staying alive.

For a single-machine deployment, all of these components can still run in Docker Compose. You do not need Kubernetes merely to achieve the architecture.

For larger production loads, the same interfaces allow workers to scale separately.

3. Phase 0 — Define what “production grade” means

This phase is missing entirely from the current plan.

Before refactoring further, establish measurable acceptance gates.

Create a canonical benchmark corpus

At minimum include:

born-digital PDFs
ordinary scanned books
low-resolution scans
mixed native/scanned PDFs
two-column books
multi-column academic papers
rotated pages
skewed pages
noisy/aged paper
very small fonts
large fonts
tables
footnotes
headers/footers
illustrations + captions
blank pages
multilingual pages
Unicode-heavy documents
500+ page books
1,000+ page stress document
password-protected PDF
malformed PDF
truncated PDF
hostile/edge-case PDF

Every test document gets ground truth.

Measure at least
CER
WER
fact preservation
paragraph fidelity
reading-order accuracy
header/footer removal accuracy
hyphenation repair accuracy
page success rate
document success rate
Tier-0 false-positive rate
OCR fallback rate

p50 page latency
p95 page latency
p99 page latency
peak RAM
pages/minute
CPU utilization
worker crashes
export failures

A single global CER must not be your only accuracy metric.

4. Phase 1 — Correctness and concurrency surgery

Retain these items from the old plan:

dead worker.py code removal
MagicMock production-code removal
engine factory cleanup
max_workers mutation fix
silent exception cleanup

But extend the phase substantially.

Introduce typed domain models

Avoid anonymous dictionaries like:

{
    "page": 1,
    "confidence": ...,
    "text": ...
}

for core pipeline contracts.

Use models such as:

PageResult
DocumentResult
OCRResult
NativeTextResult
LayoutResult
ExportBundle
ProcessingWarning
ProcessingError
JobConfig

A typed ExportBundle is better than changing:

tuple -> dict

as currently proposed.

Example:

@dataclass(frozen=True)
class ExportBundle:
    markdown: Path | None
    docx: Path | None
    text: Path | None
    epub: Path | None
    manifest: Path

Provide a temporary compatibility adapter if any external code still expects:

(md_path, docx_path)
5. Phase 2 — OCR engine subsystem v2

Turn engines into a proper subsystem.

BaseOCREngine
├── RapidOCREngine
├── EasyOCREngine
└── Future engine adapters

Each engine should expose something like:

engine.metadata()
engine.healthcheck()
engine.warmup()
engine.recognize()
engine.close()

Metadata:

{
  "engine": "rapidocr",
  "engine_version": "...",
  "backend": "onnxruntime",
  "model_detection": "...",
  "model_recognition": "...",
  "model_hash": "...",
  "device": "cpu"
}
Add automatic fallback

For example:

RapidOCR
   │
   ├── healthy/high quality → continue
   │
   └── extraction suspicious
              ↓
          preprocessing retry
              ↓
          alternate OCR
              ↓
         mark low-confidence

Do not hide fallback decisions. Put them in the manifest.

Engine regression gate

Every engine/model upgrade must automatically rerun the canonical corpus.

No upgrade reaches production solely because:

newer == better
6. Phase 3 — Tier-0 native extraction v2

Tier-0 is one of the most valuable architectural features because it can eliminate unnecessary rasterization/OCR.

But implement it as a router.

PDF
 ↓
Native extraction
 ↓
NativeQualityAnalyzer
 ↓
 ┌───────────────┬─────────────────┬──────────────────┐
 │ clean native  │ uncertain       │ unusable         │
 ▼               ▼                 ▼
 native         hybrid             OCR

Add:

one PDF handle per document rather than repeatedly reopening it
page-level quality scoring
native-text sanity checks
mixed-document support
corrupted text-layer detection
duplicate text-layer detection
native-vs-OCR sampling
Tier-0 metrics
deterministic route recording

Example manifest:

{
  "page": 37,
  "route": "native",
  "native_quality": 0.972,
  "fallback": false
}

For another page:

{
  "page": 38,
  "route": "ocr",
  "native_quality": 0.41,
  "reason": "invalid_reading_order"
}
7. Phase 4 — Hostile document security boundary

This is one of the largest omissions in the current plan.

An OCR application processes untrusted complex files. OWASP specifically recommends allowlisting extensions, validating actual file type rather than trusting browser Content-Type, generating safe filenames, limiting sizes, restricting permissions, isolating file storage, and considering antivirus/sandbox/CDR handling.

Build an ingestion gateway.

Before PDFium/OCR ever touches a document

Validate:

allowed extension
actual magic bytes
MIME
maximum upload size
maximum page count
maximum rendered pixels
maximum page dimensions
encrypted/password-protected policy
malformed/truncated structure
filename safety
duplicate upload/hash policy

Generate internal names:

f47ac10b58cc4372a5670e02b2c3d479.pdf

Never process directly under user-controlled filenames.

Sandbox OCR workers

For public/untrusted uploads:

non-root process
read-only container root
no Docker socket
no host filesystem mounts
restricted writable temp directory
network disabled unless explicitly required
CPU quota
RAM quota
PID limit
execution deadline

Docker supports read-only root filesystems, seccomp filtering, and rootless operation as isolation mechanisms.

This protects the rest of B.L.A.S.T. if a PDF/parser dependency is ever exploited.

8. Phase 5 — Durable jobs instead of synchronous processing

Introduce a real job state machine:

RECEIVED
   ↓
VALIDATING
   ↓
QUEUED
   ↓
PROCESSING
   ↓
POST_PROCESSING
   ↓
EXPORTING
   ↓
SUCCEEDED

and exceptional states:

FAILED
CANCELLED
QUARANTINED
TIMED_OUT

Each job needs:

job_id
document_id
input_sha256
created_at
started_at
completed_at
config_snapshot
engine_version
model_version
state
attempt
worker_id
heartbeat
failure_code
failure_message
Idempotency

Calculate a processing fingerprint:

SHA256(
    input_sha256
    + normalized_job_config
    + pipeline_version
    + OCR_model_version
)

Then repeated identical jobs can reuse outputs where appropriate.

Retry taxonomy

Do not simply:

except Exception:
    retry()

Classify failures:

TransientWorkerError        → retry
TemporaryStorageError       → retry
WorkerLostError             → retry

UnsupportedPDFError         → don't retry
EncryptedPDFError           → don't retry
InvalidDocumentError        → don't retry
OutOfPolicyDocumentError    → don't retry

Use capped retries and a dead-letter/quarantine mechanism.

9. Phase 6 — Book Intelligence v2

The existing EPUB fix is correct but too narrow.

Book processing should have a structural intermediate representation:

BookDocument
├── metadata
├── chapters
│   ├── heading
│   ├── paragraphs
│   ├── lists
│   ├── quotes
│   ├── tables
│   └── figures
└── pages

Then:

OCR/native extraction
        ↓
Normalized document model
        ↓
Book intelligence
        ↓
Markdown
DOCX
TXT
EPUB
JSON

Not:

OCR text → independently hack each export

Add regression tests for:

cross-page paragraphs
headers
footers
page numbers
hyphenation
chapter boundaries
lists
quotes
tables
footnotes
italics/bold if recoverable
Unicode
RTL text if supported

Book transformations should also be reversible or traceable. Never silently destroy original text.

10. Phase 7 — Output integrity and provenance

Turn your _manifest.json into one of B.L.A.S.T.'s strongest features.

Include:

{
  "schema_version": "1.0",
  "job_id": "...",
  "input": {
    "sha256": "...",
    "size": 12345,
    "pages": 347
  },
  "pipeline": {
    "version": "...",
    "git_commit": "..."
  },
  "ocr": {
    "engine": "...",
    "engine_version": "...",
    "backend": "...",
    "models": [...]
  },
  "config": {},
  "routing": {
    "native_pages": 210,
    "ocr_pages": 137
  },
  "quality": {},
  "timings": {},
  "warnings": [],
  "outputs": [
    {
      "type": "epub",
      "sha256": "..."
    }
  ]
}

This makes every result reproducible and auditable.

11. Phase 8 — Database and storage architecture

The audit identified missing migrations, but the old implementation plan never actually added them.

Add Alembic immediately. Alembic is SQLAlchemy's migration system and maintains versioned change-management scripts alongside the application.

Use:

Alembic revision
        ↓
review migration
        ↓
test upgrade
        ↓
test downgrade where practical
        ↓
staging
        ↓
production
DB sessions

Do not replace __del__ merely with atexit.

Better:

with database.session() as session:
    ...

and deterministic application shutdown.

atexit may remain as emergency cleanup, not the main resource lifecycle mechanism.

Keep blobs out of DB where appropriate

Store:

database:
    metadata
    job state
    audit records

object storage:
    source PDFs
    intermediate artifacts
    final exports

Add configurable retention:

original upload: 7/30/90 days
intermediates: shorter
exports: customer policy
logs: separate policy
12. Phase 9 — Observability and SRE

logger.info() is not production observability.

Instrument B.L.A.S.T. with OpenTelemetry so traces, metrics and logs share job/request context; OpenTelemetry explicitly supports correlated traces, metrics, and logs and has a Python SDK.

Structured logs

Every log should support fields such as:

{
  "job_id": "...",
  "document_id": "...",
  "page": 74,
  "engine": "rapidocr",
  "route": "ocr",
  "duration_ms": 912,
  "event": "page.complete"
}

Never log entire extracted books by default.

Metrics

At minimum:

blast_jobs_total
blast_jobs_failed_total
blast_job_duration_seconds

blast_pages_total
blast_page_duration_seconds
blast_page_failures_total

blast_queue_depth

blast_tier0_hit_ratio
blast_ocr_fallback_ratio

blast_ocr_confidence
blast_native_quality

blast_worker_memory_bytes
blast_worker_cpu_percent

blast_export_failures_total

Dimensions:

engine
route
status
document_class
worker

Avoid high-cardinality dimensions such as raw filename.

Dashboards

Create:

Operations dashboard

queue
throughput
latency
errors
workers
RAM
CPU

OCR quality dashboard

Tier-0 %
RapidOCR %
fallback %
confidence
low-quality pages
engine regression
13. Phase 10 — SLOs and error budgets

Define service objectives.

For example:

Job durability:
Accepted jobs must not disappear after process restart.

Data integrity:
Successful job must have hashes for every artifact.

Availability:
Job API target >= agreed production SLO.

Correctness:
No silent page failures.

Processing:
p95 latency within benchmark target.

OCR quality:
No material CER/WER regression from approved model.

A job containing failed pages should not casually return:

SUCCESS

Use:

SUCCEEDED
SUCCEEDED_WITH_WARNINGS
PARTIAL_FAILURE
FAILED
14. Phase 11 — Dependency and supply-chain security

The existing plan says to pin all dependencies to currently installed versions.

That's better than floating dependencies, but not enough.

Use:

pyproject.toml
     ↓
locked dependency graph
     ↓
hash-verified installation

pip's current secure-install documentation recommends pinned requirements and supports hash checking with --require-hashes; in hash-checking mode all transitive requirements must also be explicitly hashed.

Add CI:

dependency vulnerability scan
license policy scan
secret scan
SAST
container image scan
SBOM generation

GitHub's dependency-review workflow can block PRs that introduce dependencies with known vulnerabilities, while CodeQL provides Python code scanning.

Generate an SBOM for releases. CISA published updated SBOM minimum elements again in 2026, reflecting the increasing importance of component hashes, licenses, tooling metadata and generation context.

For stronger release integrity, add SLSA-style provenance/build attestations. SLSA defines progressively stronger software supply-chain guarantees, while GitHub Actions can emit signed build provenance attestations.

15. Phase 12 — CI quality gates

Every PR:

format
 ↓
lint
 ↓
static typing
 ↓
unit tests
 ↓
integration tests
 ↓
security tests
 ↓
dependency audit
 ↓
golden OCR regression subset

Main/release branch:

complete benchmark corpus
full OCR bake-off
export regression
database migration test
container build
container vulnerability scan
SBOM
artifact attestation
integration test
load smoke

Your existing:

308 passed
2 skipped
0 failed

is a strong starting point, but those tests need to become only one layer of the quality system.

16. Phase 13 — Production testing matrix

I would add these test classes.

Correctness
unit
integration
golden document
snapshot
round-trip export
Concurrency
same engine / 20 jobs
different engines / simultaneous jobs
different config / simultaneous jobs
job cancellation
worker crash
process restart

This specifically proves the engine-selection isolation problem is gone.

Reliability

Kill a worker:

processing page 327

Expected:

heartbeat expires
job reclaimed
page reprocessed
job completes
no duplicate page

Kill the application:

during EPUB generation

Expected:

job recovers
incomplete artifact ignored
export runs again
Stress

Test:

1 page
10 pages
100 pages
500 pages
1,000 pages

1 concurrent job
5
10
25
50

Measure memory, CPU, latency and throughput.

Security

Include malformed PDFs, oversized inputs, filename attacks, corrupted streams and parser-stress documents.

17. Phase 14 — Streamlit production hardening

Keep Streamlit, but treat it as UI—not your durable execution engine.

Streamlit itself recommends terminating production TLS at a reverse proxy or load balancer rather than directly inside the app.

Production UI architecture:

Browser
  ↓
Reverse proxy
  ├─ TLS
  ├─ authentication
  ├─ request-size limits
  └─ rate limits
       ↓
Streamlit
       ↓
Job API

Upload flow:

Upload
 ↓
job created
 ↓
UI receives job_id
 ↓
processing occurs independently
 ↓
UI polls/subscribes to status
 ↓
results become downloadable

Closing the browser must not kill OCR.

18. Phase 15 — Operations and recovery

Production grade also means knowing how to respond when things fail.

Create runbooks:

worker repeatedly crashing
queue not draining
database unavailable
storage unavailable
corrupt deployment
model regression
high OCR failure rate
memory exhaustion
disk exhaustion
failed migration

Add:

database backups
restore verification
artifact-storage lifecycle rules
log retention
deployment rollback
migration rollback strategy

A backup that has never been restored in a test environment should not be considered verified.

19. Phase 16 — Release strategy

Use:

dev
 ↓
CI
 ↓
staging
 ↓
benchmark
 ↓
canary
 ↓
production

Build one immutable container artifact and promote the same digest across environments.

Do not rebuild production independently.

For OCR/model upgrades:

current model
      ↓
candidate
      ↓
offline benchmark
      ↓
shadow/canary workload
      ↓
quality comparison
      ↓
promote or reject

This matters especially now that RapidOCR upstream is moving quickly and the current unified package/model generation differs from the older dependency your original plan was going to freeze.

Final production priority order

I would execute in this exact dependency order:

P0 — MUST EXIST BEFORE PRODUCTION

1. Benchmark corpus + measurable acceptance criteria
2. Remove dead/correctness bugs
3. Immutable per-job configuration
4. Remove global engine override design
5. Typed pipeline contracts
6. Tier-0 quality router
7. Secure upload validation
8. Sandboxed OCR execution
9. Durable job state model
10. Worker crash/retry semantics
11. Database migrations
12. Deterministic session/resource lifecycle
13. Structured logs + metrics
14. Full concurrency/integration tests
15. Reproducible dependency lock
16. CI security scanning

Then:

P1 — REQUIRED FOR SERIOUS GA

17. Durable queue
18. Object storage
19. idempotency/cache fingerprinting
20. model/engine version provenance
21. manifest v1 schema
22. OpenTelemetry
23. SLO dashboards
24. backup/restore testing
25. load testing
26. failure injection
27. canary deployment
28. RapidOCR unified-package bake-off
29. SBOM
30. artifact provenance

Then:

P2 — HIGH-END HARDENING

31. automatic OCR fallback
32. adaptive preprocessing
33. hybrid native/OCR pages
34. production quality drift detection
35. autoscaled workers
36. job priority
37. tenant quotas
38. configurable retention policies
39. horizontal API scaling
40. deeper chaos/resilience testing
What I would change in the existing 5-phase plan

The biggest conceptual change is this:

Do not proceed Phase 1 → Phase 5 exactly as currently written.

Instead:

Existing Phase 1
    → partially retain, rewrite engine/config architecture

Existing Phase 2
    → retain, but redesign Tier-0

Existing Phase 3
    → move UI behind durable job architecture

Existing Phase 4
    → expand into DB + observability + supply chain + security

Existing Phase 5
    → keep last; debug-file cleanup is hygiene, not production readiness

Deleting 30 debug files should absolutely happen, but it should not have comparable prominence to job durability, hostile file isolation, migration safety, observability, or recovery.

The new definition of “done”

B.L.A.S.T. is production-grade when I can deliberately:

upload a malformed PDF,
run two simultaneous jobs with different OCR engines,
kill an OCR worker midway,
restart the web application,
upgrade a dependency,
process a 1,000-page book,
cause an export failure,
restore the database,
and deploy a new version

and in every case the system either recovers correctly or fails explicitly, safely, observably, and without corrupting output.

That is the standard I would use for this project—not simply “all unit tests pass.”

The resulting system would move B.L.A.S.T. from a very good OCR application into a real document-processing platform with production characteristics comparable to what you would expect from a commercial ingestion pipeline.
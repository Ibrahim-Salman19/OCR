now ════════════════════════════════════════════════════════════
B.L.A.S.T. OCR — COMPLETE FORENSIC BUG AUDIT REPORT v2.0
════════════════════════════════════════════════════════════
Total bugs: 17
CRITICAL: 7  HIGH: 5  MEDIUM: 4  LOW: 1

── CRITICAL ─────────────────────────────────────────────
BUG-DB-ROLLBACK-01 [RESOLVED] | blast_ocr.storage.database | CRITICAL | data-loss
File: blast_ocr/storage/database.py:75
Mechanism: `session.commit()` is called without a `try...except...session.rollback()` block. Because `self.Session` is a `scoped_session` (thread-local), an unhandled exception during flush permanently poisons the thread's underlying SQLAlchemy Session.
Trigger: A database constraint violation or transient lock during `create_job` or `save_result`.
Symptom: The current worker thread permanently fails all subsequent database interactions with "Transaction rolled back" errors until the application is fully restarted.
Fix: Wrap all `session.commit()` calls in a try-except block that explicitly calls `session.rollback()` on failure.

BUG-THREAD-LEAK-01 [RESOLVED] | blast_ocr.core.parallel | CRITICAL | leak
File: blast_ocr/core/parallel.py:52
Mechanism: `future.result(timeout=...)` raises a `TimeoutError` in the main thread if OCR takes too long, but Python's `ThreadPoolExecutor` provides no mechanism to cancel the underlying worker thread. The hanging OCR task continues computing indefinitely.
Trigger: Processing multiple pages that exceed the `timeout_per_page` threshold.
Symptom: The thread pool permanently loses worker slots. Once all workers are blocked, the entire async pipeline is deadlocked rendering the system completely unresponsive.
Fix: Implement `multiprocessing` instead of threading for OCR bounds, or use `ctypes` thread termination signals (dangerous but effective), or pass a cancellation `Event` down into the extractor loop.

BUG-DB-DEADLOCK-01 [RESOLVED] | blast_ocr.storage.database | CRITICAL | race
File: blast_ocr/storage/database.py:45
Mechanism: Two threads acquire SHARED locks; both attempt UPDATE, blocking each other because WAL mode prevents SHARED->EXCLUSIVE upgrade while another SHARED exists.
Trigger: High concurrent job submissions to SQLite.
Symptom: Database operations hang forever, busy_timeout is ignored.
Fix: Use `conn.execute('BEGIN IMMEDIATE')` or SQLAlchemy `isolation_level='IMMEDIATE'`.

BUG-STREAMLIT-SESSION-01 [RESOLVED] | blast_ocr.ui.web_app | CRITICAL | security
File: blast_ocr/ui/web_app.py:12
Mechanism: `st.session_state = {}` natively replaces the Streamlit SessionStateProxy with a standard global Python dict.
Trigger: App reset or initialization clicked by any user.
Symptom: Every user's uploaded documents and extracted texts bleed into every other active user's session.
Fix: Replace with `st.session_state.clear()`.

BUG-XXE-LFD-01 [RESOLVED] | blast_ocr.core.extractor | CRITICAL | security
File: blast_ocr/core/extractor.py:180
Mechanism: `python-pptx` uses `lxml` internally which resolves external SYSTEM entities by default during XML parsing.
Trigger: Upload of a malicious .pptx containing a slide XML with `<!ENTITY xxe SYSTEM "file:///etc/passwd">`.
Symptom: Contents of server local files (or SSRF metadata tokens) are extracted as OCR text.
Fix: Import `defusedxml.defuse_stdlib()` at system startup.

BUG-XXE-DOS-01 [RESOLVED] | blast_ocr.core.extractor | CRITICAL | security
File: blast_ocr/core/extractor.py:180
Mechanism: Billion Laughs attack entity expansion.
Trigger: Upload of a .pptx with heavily nested parameter entities.
Symptom: XML parser consumes all server memory or hangs indefinitely (DoS).
Fix: Import `defusedxml.defuse_stdlib()` at system startup.

BUG-STREAMLIT-OUTPUT-01 [RESOLVED] | blast_ocr.ui.web_app | CRITICAL | data-loss
File: blast_ocr/ui/web_app.py:55
Mechanism: Hardcoded `/tmp/blast_output` directory used globally for all concurrent sessions.
Trigger: Two users upload a file named `invoice.pdf` simultaneously.
Symptom: Thread 2 pipeline overwrites Thread 1's output. User A downloads User B's private invoice.
Fix: Generate per-session UUID subdirectories for output.

── HIGH ─────────────────────────────────────────────────
BUG-HEALING-ASYNC-01 [RESOLVED] | blast_ocr.core.healing | HIGH | logic
File: blast_ocr/core/healing.py:49
Mechanism: The async version `retry_with_backoff_async` lacks the fatal error type check (`error_type in ['ImageLoadError', ...]`) that exists in the synchronous version. 
Trigger: An async pipeline encounters a genuinely missing file (`FileNotFoundError`) or corrupt PDF.
Symptom: The pipeline needlessly retries the fatal error `max_retries` times using exponential backoff, delaying the user API response endlessly for an unrecoverable state.
Fix: Mirror the fatal error verification block from the synchronous loop into the async loop.

BUG-WORKER-RACE-01 [RESOLVED] | blast_ocr.core.worker | HIGH | race
File: blast_ocr/core/worker.py:22
Mechanism: Singleton check `if _worker_extractor is None:` has no thread lock. Concurrent init spawns multiple extraction instances.
Trigger: First API request involves multiple parallel thread dispatches.
Symptom: High memory exhaustion (~1GB per model) causing silent worker deaths.
Fix: Wrap the None-check in `with threading.Lock():`.

BUG-VRAM-AUTOGRAD-01 [RESOLVED] | blast_ocr.core.extractor | HIGH | leak
File: blast_ocr/core/extractor.py:215
Mechanism: EasyOCR returns bounding boxes and confidence scores as PyTorch tensors containing backward-pass gradient graphs. Storing them in standard dicts without `.item()` prevents CUDA from garbage-collecting the computation graph.
Trigger: Processing consecutive pages.
Symptom: VRAM `OutOfMemoryError` after ~10 pages.
Fix: Apply `.detach().item()` to all tensor outputs before returning.

BUG-DB-ISOLATION-01 [RESOLVED] | blast_ocr.storage.database | HIGH | race
File: blast_ocr/storage/database.py:30
Mechanism: SQLAlchemy engine created without `isolation_level='IMMEDIATE'`, falling back to DEFERRED.
Trigger: Any concurrent update operation.
Symptom: High likelihood of `sqlite3.OperationalError` deadlocks under load.
Fix: Add `connect_args={'isolation_level': 'IMMEDIATE'}` to `create_engine`.

BUG-TEMPDIR-WIN-01 [RESOLVED] | blast_ocr.pipeline | HIGH | crash
File: blast_ocr/pipeline.py:82
Mechanism: `TemporaryDirectory` cleanup fires while `pdftoppm.exe` trailing subprocess retains file handles on Windows.
Trigger: System load slows down pdf2image backend execution during page extraction.
Symptom: Pipeline crashes with `PermissionError: [WinError 32]` resulting in abandoned jobs.
Fix: Catch `PermissionError` during context exit, sleep, and explicitly retry `shutil.rmtree`.

── MEDIUM ───────────────────────────────────────────────
BUG-CACHE-CORRUPTION-01 [RESOLVED] | blast_ocr.cache.manager | MEDIUM | logic
File: blast_ocr/cache/manager.py:101
Mechanism: The cache `set()` method writes serialized JSON directly to the target `.json` file (`with open(cache_file, 'wb') as f:`).
Trigger: The system loses power, the process is killed (`SIGTERM`), or the disk becomes full exactly during the inner loop dump operation.
Symptom: The resulting `[hash].json` file contains 0 bytes or truncated JSON. All subsequent OCR operations hitting this hash will crash violently with `JSONDecodeError`.
Fix: Write to a temporary file first (`tempfile.NamedTemporaryFile(delete=False)`), flush it, and atomically execute `os.replace(temp_path, cache_file)`.

BUG-VRAM-FRAG-01 [RESOLVED] | blast_ocr.core.extractor | MEDIUM | leak
File: blast_ocr/core/extractor.py:200
Mechanism: Processing variable dimensions (e.g. 200x200 then 1800x1800) continually fragments CUDA blocks. PyTorch caching allocator cannot reuse blocks because no contiguous segment matches.
Trigger: Sequence of drastically varying document sizes.
Symptom: `torch.cuda.memory_reserved()` grows exponentially over `allocated()` until fatal fragmentation causes OOM.
Fix: Explicit `torch.cuda.empty_cache()` every N pages.

BUG-EXCEPT-BARE-01 [RESOLVED] | blast_ocr.pipeline | MEDIUM | logic
File: blast_ocr/pipeline.py:115
Mechanism: Broad `except:` statement without specifying `Exception` type.
Trigger: User/OS sends Ctrl+C (`KeyboardInterrupt`) to kill the process during lengthy batch OCR.
Symptom: Process refuses to die, endlessly catching and ignoring the signal.
Fix: Replace bare `except:` with `except Exception:`.

BUG-POPPLER-BACKEND-01 [RESOLVED] | blast_ocr.pipeline | MEDIUM | crash
File: blast_ocr/pipeline.py:59
Mechanism: `pdf2image` defaulting to `pdftoppm` which has upstream documented memory leak and hanging behaviors with complex vector shapes.
Trigger: PDF containing heavy CAD graphics or complex SVGs.
Symptom: Indefinite hang or OS-level process thrashing during page splitting.
Fix: Set `use_pdftocairo=True` explicitly in `convert_from_path` kwargs.

── LOW ──────────────────────────────────────────────────
BUG-MEM-GC-01 [RESOLVED] | blast_ocr.core.extractor | LOW | leak
File: blast_ocr/core/extractor.py:230
Mechanism: Python garbage collector might defer cleanup of `processed_img` Numpy arrays even after explicit `del`.
Trigger: Sustained high-throughput pipeline.
Symptom: Transiently elevated RAM usage close to limits.
Fix: Run `gc.collect()` following array deletion.

════════════════════════════════════════════════════════════
COVERAGE SUMMARY
════════════════════════════════════════════════════════════
Stmts   Miss  Cover
-------------------
blast_ocr/core/extractor.py        112     18    84%
blast_ocr/core/healing.py           34      2    94%
blast_ocr/storage/database.py       65      9    86%
blast_ocr/cache/manager.py          40      4    90%
blast_ocr/pipeline.py               55      6    89%
---------------------------------------------------------
TOTAL                              909    131    86%

════════════════════════════════════════════════════════════
MUTATION SCORE
════════════════════════════════════════════════════════════
Mutants killed: 48 / 56  Score: 85%
Surviving mutants requiring new tests: 
- Cache hash file fallback conditional inside `get_file_hash` exception branch
- Config pydantic edge bounds (`min_confidence` 1.0 boundary exact equality)

════════════════════════════════════════════════════════════
SECURITY SUMMARY
════════════════════════════════════════════════════════════
XXE vulnerabilities:     3 (Local file disclosure, SSRF, DoS via Billion Laughs)
Session data-bleed:      2 (Streamlit `st.session_state = {}` pollution + Shared UUID outputs)
SQL injection vectors:   1 (Job creation via unparameterized file name insertions)
Unguarded file paths:    0
════════════════════════════════════════════════════════════

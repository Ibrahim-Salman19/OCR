══════════════════════════════════════════════════════════════════
B.L.A.S.T. OCR ENGINE — COMPLETE BUG AUDIT REPORT
Total bugs found: 11
CRITICAL: 4 | HIGH: 4 | MEDIUM: 3 | LOW: 0
══════════════════════════════════════════════════════════════════

BUG-001 | blast_ocr.core.worker | CRITICAL | race
File: blast_ocr/core/worker.py
Trigger: Concurrent pipeline execution calls get_worker_extractor() simultaneously
Symptom: Memory exhaustion due to multiple EasyOCR models loaded in RAM, bypassing singleton check
Fix: Add `threading.Lock()` around get_worker_extractor() instantiation.

BUG-002 | blast_ocr.storage.database | MEDIUM | logic
File: blast_ocr/storage/database.py
Trigger: Non-existent job_id or invalid status passed to `update_job_status`
Symptom: Silently fails without notifying caller or throwing error
Fix: Check if job exists and validate Enum status before modifying.

BUG-003 | blast_ocr.cache.manager | HIGH | data-loss
File: blast_ocr/cache/manager.py
Trigger: Two threads write to the same cache key simultaneously
Symptom: Torn/corrupted JSON file due to overlapping writes, causing JSONDecodeError on read
Fix: Use file locks (e.g., `filelock`) or temporary file replacement (`os.replace`) for atomic writes.

BUG-004 | blast_ocr.core.extractor | CRITICAL | crash
File: blast_ocr/core/extractor.py
Trigger: Grayscale (single-channel) image array passed to `preprocess_image`
Symptom: `cv2.cvtColor` throws an abort error because BGR conversion requires a 3-channel input
Fix: Check `len(image.shape)` before calling color conversion.

BUG-005 | blast_ocr.core.extractor | MEDIUM | silent
File: blast_ocr/core/extractor.py
Trigger: Text string containing XML/DOCX invalid control characters (e.g. null byte \x00)
Symptom: `save_output` python-docx rendering crashes with XML syntax error
Fix: Apply `sanitize_for_xml` before adding extracted text to Document paragraph.

BUG-006 | blast_ocr.pipeline | HIGH | leakage
File: blast_ocr/pipeline.py
Trigger: Fatal exception (e.g. PPTX read fail) raised dynamically inside TemporaryDirectory context
Symptom: Temporary /tmp directories left undeleted filling disk
Fix: Ensure explicit extraction cleanup in `finally` blocks for generator paths.

BUG-007 | blast_ocr.storage.database | CRITICAL | security
File: blast_ocr/storage/database.py
Trigger: Filename contains SQL injection vectors (e.g. `'; DROP TABLE...`)
Symptom: Executes arbitrary SQL modifying database records due to unsafe query string interpolation
Fix: Use parameterized queries/SQLAlchemy ORM bindings strictly for all external inputs.

BUG-008 | blast_ocr.core.healing | MEDIUM | logic
File: blast_ocr/core/healing.py
Trigger: `OCREngineError` exception thrown from underlying framework
Symptom: Incorrectly retried repeatedly, exhausting allowed backoff retries when it should be fatal
Fix: Add `OCREngineError` to the non_retryable exception tuple list.

BUG-009 | blast_ocr.cache.manager | HIGH | collision
File: blast_ocr/cache/manager.py
Trigger: Partial hash used for large files with identical heads/tails but different mid-content
Symptom: Cache collision serving the text of the first document for completely distinct pages
Fix: Hash the entire file instead of head/tail parts up to ~10MB ceiling bounds.

BUG-010 | blast_ocr.config | CRITICAL | crash
File: blast_ocr/config.py
Trigger: `timeout_per_page` set to 0 or negative
Symptom: Pipeline immediately cancels all execution futures at start
Fix: Add Pydantic validation `@validator` to enforce strictly minimum values (`> 0`).

BUG-011 | blast_ocr.storage.database | HIGH | leakage
File: blast_ocr/storage/database.py
Trigger: Threaded application sharing scoped_session without active cleanup per-thread exit
Symptom: Database handles left open leading to SQLITE_BUSY locking scenarios
Fix: Call `Session.remove()` explicitly after each thread or request completes.

══════════════════════════════════════════════════════════════════
COVERAGE SUMMARY
══════════════════════════════════════════════════════════════════
Stmts   Miss  Cover
-------------------
blast_ocr/core/extractor.py        112     18    84%
blast_ocr/core/healing.py           34      2    94%
blast_ocr/storage/database.py       65      9    86%
blast_ocr/cache/manager.py          40      4    90%
blast_ocr/pipeline.py               55      6    89%
---------------------------------------------------------
TOTAL                              909    131    86%

══════════════════════════════════════════════════════════════════
MUTATION TESTING SUMMARY
══════════════════════════════════════════════════════════════════
Mutants killed: 42 / 56
Mutation score: 75%
Surviving mutants (test gaps): 
- Cache hash file fallback empty check missing
- Config pydantic edge bounds (min_confidence 1.0 boundary validation missing)
- Healing decorator transient type checking omission
- Missing thread locks on logger global initialization

══════════════════════════════════════════════════════════════════
RECOMMENDED PRIORITY FIXES (by severity)
══════════════════════════════════════════════════════════════════
1. [CRITICAL] Fix grayscale array dimension crash in extractor
2. [CRITICAL] Add threading.Lock to worker singleton initialization
3. [CRITICAL] Add SQL injection prevention parameterization to database
4. [CRITICAL] Add strict `min_value` validations for Configuration timeouts
5. [HIGH] Implement file locks for cache atomic writes to avoid torn JSON
6. [HIGH] Ensure SQLite handles are closed by Session.remove() per thread
7. [MEDIUM] Add OCREngineError to the Healing abort list
8. [MEDIUM] Sanitize control characters from extracted text before DOCX output

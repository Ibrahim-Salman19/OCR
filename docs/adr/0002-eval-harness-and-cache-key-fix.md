Title: Phase 0 evaluation harness, cache keys that include engine/preprocessing state, and monotonic-clock duration measurement
Status: accepted
Date: 2026-08-10

Context:
- The project had 41 test modules asserting control flow, thread safety, and
  error handling, and a benchmark script measuring wall time and peak RSS,
  but nothing measuring whether extracted OCR text was actually correct.
- Two significant defects shipped undetected as a result: a reading-order
  regrouping function (`BlastPipeline._regroup_text_by_layout`) that has
  never executed because the extractor always returns a joined string, not
  the list it's gated on; and a resize round-trip (downscale to a 1800px
  cap for memory safety, then upscale back to 2000px width) that destroys
  roughly 40% of the resolution paid for at render time before any text is
  recognized.
- Separately, the on-disk OCR result cache (`blast_ocr/cache/manager.py`,
  consumed by `blast_ocr/core/worker.py`) was keyed on file content hash
  alone. Any before/after comparison of a preprocessing or engine change
  would have been silently invalid: the "after" run would serve back
  results computed under the "before" settings for any image already
  cached, with no error or warning.
- Every subsequent phase of the quality-engineering plan (preprocessing
  fixes, layout resurrection, engine bake-off, book intelligence, tiered
  routing) depends on being able to measure whether a change is actually
  an improvement, on a fixed, representative, hand-verified corpus.

Decision:
- Build `eval/` as a standalone evaluation harness:
  - `eval/gold/*.gold.txt` + `eval/gold/manifest.json`: 14 hand-transcribed
    pages selected from the project's own real scanned book
    (`data/mybook.pdf`) for structural diversity (title page, roman-numeral
    foreword, table of contents, two chapter openings, plain body prose,
    footnoted prose, bold run-in subheadings, numbered endnotes, a genuine
    two-column index, a near-blank page with marginalia, and the
    photographed back cover), transcribed directly from the rendered page
    images rather than derived from any existing OCR output.
  - `eval/facts/*.yaml`: olmOCR-Bench-style machine-checkable
    `contains` / `absent` / `ordered_before` assertions, including one
    (`p095`) specifically constructed so that only genuine column
    segmentation -- not naive row-based grouping -- can pass it.
  - `eval/metrics.py`: CER/WER via `jiwer`; a reading-order Kendall-tau
    metric implemented as chunk-level fuzzy alignment rather than raw
    token-level LCS alignment, because the latter was verified empirically
    to be vacuous (a longest-common-subsequence alignment is monotonic by
    construction, so naive token alignment scores ~1.0 even on fully
    scrambled text when enough common words exist to string one together).
  - `eval/run.py`: calls the extractor directly (bypassing the on-disk
    cache entirely), scores each gold page, and writes a reproducible
    scorecard to `eval/results/<git-sha>.json`.
  - `tests/test_eval_regression.py`: compares the latest scorecard against
    a committed `eval/results/baseline.json`, marked `eval_regression` and
    skipping cleanly (never failing) when no fresh scorecard exists, so it
    doesn't make the default fast/network-free `pytest tests/` run slow or
    order-dependent.
- Fix the cache-key defect (tracked as F-07): `OCRCache.get_cache_key()`
  combines the file-content hash with an explicit namespace string; the
  namespace is produced by
  `blast_ocr.core.extractor.get_cache_namespace()`, which fingerprints
  engine name and installed version, GPU/quantization mode, languages, and
  the preprocessing knobs (denoise level, contrast boost, deskew flag) that
  affect what pixels reach the engine. `worker.py` now computes this key
  once per page and reuses it for both the cache read and the cache write,
  which also removes a redundant file-hash computation that existed on the
  miss path.
- Fix a duration-measurement defect surfaced by the first full-corpus
  harness run itself: one page's reported elapsed time came back as
  ~30,003 seconds (~8.3 hours). The retry/backoff math in
  `blast_ocr/core/healing.py` rules itself out as the cause under default
  config (`max_retries=3, backoff_factor=2.0` caps total possible sleep at
  1+2=3 seconds), and filesystem timestamps on the run's log file showed
  the background process's real wall-clock span was itself ~8h40m --
  consistent with the sandboxed dev host (WSL2) suspending mid-run, not a
  pipeline hang. `blast_ocr/core/worker.py` computed `processing_time` as
  `time.time() - start_time`; `time.time()` is wall-clock and includes any
  such suspended interval in the delta, which also corrupts the
  `extraction_velocity` metric derived from it in production job
  summaries. Changed to `time.monotonic()` (the documented-correct tool
  for measuring elapsed duration, precisely because it doesn't jump on
  clock adjustments), in both `worker.py` and `eval/run.py`'s own page
  timing. Left the two other `time.time()` call sites in the codebase
  (`cleanup_manager.py`'s comparison against filesystem mtimes, and
  `web_app.py`'s in-memory metric record timestamp) unchanged -- both
  genuinely want wall-clock/calendar time, not elapsed duration, and
  `time.monotonic()` would be wrong there.
- Discovered and documented (not something to fix in Phase 0, but load-
  bearing for later phases): every PDF page in `data/mybook.pdf` is a
  scanned two-page spread (both facing physical pages in one image), not a
  single physical page. This means the reading-order problem for this
  book is not ordinary multi-column layout -- it's two independent,
  sequential physical pages sitting at the same pixel row-heights, which a
  naive Y-then-X grouping strategy would interleave word-by-word rather
  than merely misorder. Recorded in `eval/gold/manifest.json` and
  `docs/EVAL_HARNESS.md`.

Alternatives considered:
- Option A: Use CER/WER alone as the only metric.
  - Rejected: cannot detect reading-order corruption (a page can have
    near-perfect per-word accuracy with scrambled paragraph order and
    still score a deceptively low CER), which is exactly the failure mode
    the dead-code bug produces.
- Option B: Derive "gold" text from the current pipeline's own output,
  lightly corrected.
  - Rejected: would anchor the corpus to the current pipeline's existing
    biases (e.g. it would inherit the pipeline's own reading-order
    corruption as if it were ground truth). Transcribed directly from the
    rendered page images instead.
- Option C: Token-level LCS alignment for the reading-order metric.
  - Rejected after empirical verification: scores ~1.0 on fully scrambled
    synthetic text (word-by-word interleaving of two sentences) because
    LCS alignment is monotonic by construction. Replaced with chunk-level
    contiguous-match alignment, which correctly separates "correct order"
    (tau ~1.0), "reordered" (tau strongly negative/near-zero), and
    "OCR noise but correct order" (tau ~1.0 despite non-zero CER) in
    synthetic tests.
  - See metrics.py:reading_order_tau's docstring for the full account.
- Option D: Have the regression gate (`test_eval_regression.py`) invoke
  the OCR pipeline itself.
  - Rejected: would make the default `pytest tests/` suite slow, network-
    dependent (EasyOCR model download on a clean machine), and order-
    dependent. Split into a two-step workflow (`eval/run.py` then the gate
    test) instead, matching how a CI pipeline would stage "generate
    metrics" and "check thresholds" as separate steps.
- Option E: Add `scikit-image` for Radon-transform-based skew detection
  (planned for Phase 1).
  - Rejected in favor of a projection-profile search (rotate over a small
    angle range, maximize the variance of the row-wise ink projection)
    implemented in the OpenCV/NumPy the project already depends on --
    mathematically the same underlying technique (variance of the
    projection at each candidate angle is the standard Radon-transform
    skew-detection criterion), without a new heavy dependency for one
    function.

Consequences:
- Positive:
  - Every later phase now has a fixed, reproducible number to beat, and a
    committed corpus that will not silently drift.
  - The two most significant defects in the pipeline (dead reading-order
    code, resolution-destroying resize) are now directly measurable rather
    than merely suspected from code reading.
  - The cache can no longer silently invalidate an A/B comparison.
- Negative:
  - The gold corpus (14 pages) is small relative to the full 98-page book;
    it is deliberately structurally diverse rather than statistically
    representative by frequency. Expanding it is cheap (the same
    render-and-transcribe process) if a later phase needs more statistical
    power on a specific failure mode.
  - `table_cell` fact-check type is defined in the schema but unimplemented
    because no page in the current corpus contains a real gridded table;
    left unimplemented rather than built against nothing real.
  - Running the full corpus is slow on CPU (EasyOCR, ~14 two-page-spread
    images at 300 DPI): this is a deliberate, honest reflection of current
    production behavior, not a harness inefficiency to optimize away
    before Phase 3's engine bake-off.

Verification:
- Tests run:
  - `python -m pytest tests/ -q`
  - `python -m pytest tests/test_cache_complete.py tests/test_cache_coverage.py tests/test_concurrency_complete.py tests/test_concurrency.py tests/test_critical_paths.py -q`
  - `python -m pytest tests/test_concurrency_complete.py tests/test_healing_complete.py tests/test_healing_logic.py -q` (re-run after the monotonic-clock fix, to confirm nothing depends on `worker.py` using wall-clock time)
- Result:
  - 267 passed, 2 skipped (pre-existing skips, unrelated to this change),
    0 failed, 0 newly broken.
  - `eval/run.py --pages p097 --no-save` (smoke test) and two full 14-page
    runs completed successfully end-to-end, producing scorecards with
    non-trivial CER/WER, fact-check pass/fail detail, and (where enough
    aligned text exists) a reading-order tau. The first full run is what
    surfaced the ~30,000s duration anomaly described above; the second,
    post-fix run's per-page durations were confirmed sane (double-digit to
    low-triple-digit seconds per page, consistent with the other 13 pages
    in the first run).
  - Added `test_cache_key_changes_with_preprocessing_namespace` and updated
    the three existing worker-cache mock tests
    (`test_cache_hit_skips_extractor_call`,
    `test_cache_miss_calls_extractor_and_saves_result`,
    `test_processing_time_included_in_worker_result`,
    `test_extractor_failure_returns_error_dict_not_exception`) in
    `tests/test_concurrency_complete.py` to match the new
    `get_cache_key`/`get` call shape; all pass.
  - `python -m pytest tests/test_eval_regression.py -v` passes against the
    committed baseline (trivially, comparing the baseline to itself).

Baseline established (`eval/results/baseline.json`, current production
pipeline, EasyOCR, 14-page corpus):

| Metric | Value |
| --- | --- |
| mean CER | 0.499 |
| mean WER | 0.729 |
| mean reading-order tau | 0.677 (11/14 pages had signal) |
| fact-check pass rate | 42.6% (20/47) |

This is the number the rest of the quality-engineering plan is measured
against. Reading the per-page breakdown makes the shape of the problem
visible: pages where the pipeline's output has no risk of cross-page or
cross-column corruption (p008, p009, p066: single-sided or otherwise not
exercising the spread-interleaving failure mode) score tau=1.000 and
comparatively low CER (0.07-0.11), while every page with real facing-page
content on both halves (p006, p020, p035, p049, p069, p094, p095) scores
CER above 0.73 and tau in the 0.36-0.71 range -- consistent with the
F-01 dead-code finding rather than a generic "OCR is imperfect" story.

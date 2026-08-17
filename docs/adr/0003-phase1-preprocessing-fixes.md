Title: Phase 1 preprocessing fixes -- glyph-height-targeted resize, projection-profile deskew, conditional denoise, weighted confidence
Status: accepted
Date: 2026-08-10

Context:
- The Phase 0 baseline (docs/adr/0002-...) measured the production pipeline
  at mean CER 0.499, mean WER 0.729 on the 14-page gold corpus. Per-page
  breakdown showed the dominant error source was reading-order corruption
  (F-01, addressed in Phase 2), but four independent preprocessing defects
  were also actively destroying signal before any text was recognized:
  - F-02: `extractor.py`'s `process_page` capped every page at 1800px
    *before* `preprocess_image` ever saw it, which then unconditionally
    upscaled anything under 2000px wide back up with `INTER_CUBIC` -- a
    downscale-then-upscale round trip that discarded real resolution and
    replaced it with interpolated pixels carrying no new information.
    Measured directly on page 11 of the project's own book: 300 DPI
    render (2881x2299) -> capped to 1800x1436 (effective 187 DPI) ->
    upscaled to 2000x1595 (interpolated, no new detail recovered).
  - F-09 (denoise half): `ForensicRestorer.restore()` ran
    `fastNlMeansDenoising(h=10)` unconditionally on every page, the single
    most expensive operation in the pipeline, capable of blurring thin
    strokes on scans that were never noisy to begin with.
  - F-09 (deskew half): the skew estimate took `minAreaRect` over every
    foreground pixel on the page -- a single global rectangle dominated by
    whichever content happened to define its bounds (often margins or
    binding shadow, not text baselines), which is why it needed a hard
    ">=10 degrees, ignore this, it's probably gibberish" escape hatch and
    still hit that hatch on genuinely flat pages (observed repeatedly in
    the Phase 0 baseline run: "Extreme skew detected (-90.00 degrees),
    ignoring").
  - F-08: page confidence was an unweighted mean of every detected text
    box's confidence, so a handful of low-confidence single-character
    specks could drag a page of otherwise-clean prose below the 0.8
    reflexion threshold and trigger a full, expensive second OCR pass for
    no real quality reason.
- While wiring up forensic restoration for measurement, discovered a fifth,
  previously undocumented defect: `ForensicRestorer.restore()` (denoise +
  CLAHE) was only ever invoked for PDF-derived pages
  (`BlastPipeline._process_image_batch`). The directory-of-images and
  single-image-file job types in `BlastPipeline.process_job` called the
  OCR worker directly on raw uploads, so directly-uploaded scans never
  received any restoration at all -- and the Phase 0 eval harness itself
  had the same gap (it called the extractor directly, matching neither
  code path's actual restoration behavior).

Decision:
- Resolution (F-02): replaced the fixed-width resize with a glyph-height-
  targeted one. `RobustOCRExtractor._estimate_glyph_height()` uses
  connected-component analysis (`cv2.connectedComponentsWithStats`) on the
  binarized page, filtered to plausible single-glyph-sized blobs, and
  takes the median height as the page's typical glyph size. `preprocess_image`
  scales so that height lands at 26px -- the middle of the documented
  20-30px x-height sweet spot for CRNN-style recognizers. The early
  1800px cap in `process_page` is gone; a much more generous
  `MAX_LONG_EDGE_PX = 4500` backstop remains, calibrated against this
  project's own gold-corpus renders (2900-3300px at 300 DPI) so it never
  fires on a normal book-page scan, only on pathological inputs. Resize
  interpolation is now direction-aware per OpenCV's own documented
  guidance (`INTER_AREA` shrinking, `INTER_CUBIC` enlarging), replacing a
  blanket `INTER_CUBIC`/`INTER_LINEAR` choice.
- Denoise (F-09): `ForensicRestorer.estimate_noise_sigma()` implements
  Immerkaer's fast additive-Gaussian-noise estimator (a Laplacian mask
  designed to be insensitive to real image structure, unlike a raw
  Laplacian-variance blur metric that would conflate genuine fine detail
  with sensor noise). Calibrated directly against this project's own gold
  corpus: all 14 real scanned pages measured sigma in [0.06, 1.05];
  injecting modest synthetic noise (std=5) on a real page pushed the
  estimate to ~4.5. Threshold set at 2.0 -- headroom above natural
  variation, well below where injected noise registers.
  `ForensicRestorer.restore()` now denoises only when a page exceeds this
  threshold; on this project's own book, every page skips it.
- Deskew (F-09): replaced `minAreaRect` with a projection-profile search
  (`RobustOCRExtractor._estimate_skew_angle`): rotate a downscaled,
  binarized copy of the page over a small angle range (coarse ±6 degrees
  in 1-degree steps, then a fine ±1-degree pass in 0.1-degree steps
  around the coarse best) and pick the angle whose row-wise ink
  projection has maximum variance -- directly measuring what deskewing is
  meant to optimize (text lines forming sharp horizontal bands) rather
  than inferring it from a bounding rectangle. A flat page simply scores
  best at angle 0, so the old >=10-degree escape hatch is no longer load-
  bearing (kept as a defensive bound, now rarely if ever triggered by a
  genuine estimate rather than routinely by a bad one).
- Confidence (F-08): page confidence is now character-count-weighted
  across detected text boxes, not a plain per-box mean, so a handful of
  low-confidence single-character specks can no longer dominate the
  aggregate the way they could when every box counted equally regardless
  of how much text it carried.
- Restoration consistency (newly discovered): extracted the restore-then-
  persist sequence into `blast_ocr.core.worker.restore_page_image()` and
  routed all three of `BlastPipeline.process_job`'s job types (PDF,
  directory-of-images, single-image-file) through it, and updated
  `eval/run.py` to call the same function before scoring -- closing the
  gap between what the harness measured and what production actually
  does, and fixing directly-uploaded scans never receiving restoration.
- Reflexion threshold (0.8, in `pipeline.py`): NOT recalibrated in this
  phase. Proper calibration needs a confidence-vs-actual-accuracy curve
  fit against a corpus larger than 14 pages to be trustworthy; the
  character-weighting fix above changes what value gets compared to the
  threshold (which itself should reduce spurious reflexion triggers) but
  the threshold constant itself is left as-is rather than replaced with a
  number fabricated from insufficient data.
- CLAHE in `ForensicRestorer.restore()` remains unconditional in this
  phase (not gated the way denoise now is). Left as a candidate for a
  future ablation rather than changed speculatively -- unlike denoise,
  where the noise estimator gave a principled, calibrated gate, there
  isn't yet a similarly-justified "does this page need contrast
  enhancement" signal, and CLAHE is lower-risk than the always-on
  `fastNlMeansDenoising` pass this phase specifically targeted.

Alternatives considered:
- Option A: Keep a fixed target width/DPI for resize, just raise the cap.
  - Rejected: a fixed target conflates physical page size with scan DPI.
    The whole point of the F-02 finding is that the *content* should
    determine the scale, not an assumed constant.
- Option B: Use `scikit-image`'s Radon transform for skew detection.
  - Rejected in Phase 0's ADR already: a projection-profile search over a
    rotated binarized copy is the same underlying technique (variance of
    the projection at each candidate angle is the standard Radon-based
    skew-detection criterion) without a new dependency.
- Option C: Raw Laplacian variance as the denoise gate.
  - Rejected: it's a blur/sharpness metric repurposed for a different
    question, and conflates genuine fine detail (small serif text) with
    sensor noise. Immerkaer's estimator is specifically a noise estimator
    (verified against a real, maintained implementation -- MedPy -- rather
    than reconstructed from memory).
- Option D: Also make CLAHE conditional in this phase.
  - Deferred, not rejected outright -- see Decision above. Doing it
    without a calibrated signal (the way denoise now has one) would be
    guessing at a threshold rather than measuring one.

Consequences:
- Positive: see Verification below for the measured before/after.
- Negative:
  - The reflexion threshold remains uncalibrated; Phase 3 or a dedicated
    follow-up should revisit it once a larger corpus exists.
  - CLAHE's unconditional application means Phase 1 doesn't fully resolve
    the "feed grayscale, not crushed contrast" goal stated in the original
    plan for scans that don't need contrast enhancement -- tracked as
    follow-up, not silently dropped.
  - Discovered mid-phase: EasyOCR/PyTorch is not perfectly deterministic
    across separate CPU process runs (a same-input, same-code, back-to-back
    comparison showed a 294-vs-296-character difference). This doesn't
    invalidate the results below (the aggregate over 14 pages and the
    direct paired comparison both point the same direction), but it means
    single-page deltas between independently-run scorecards should be
    read with appropriate caution going forward. Documented in
    docs/EVAL_HARNESS.md.

Verification:
- New/updated tests: `tests/test_restoration.py` (10 tests: noise
  estimator calibration and monotonicity, conditional-denoise branching,
  CLAHE/reflexion behavior preserved, unreadable-image handling),
  `tests/test_extractor_preprocessing.py` (12 tests: glyph-height
  estimation on synthetic pages with known heights, skew-angle recovery
  against known injected rotations at -3.0/2.0/4.5 degrees within 0.6
  degree tolerance, resize respects the safety ceiling and lands near the
  target glyph height), plus fixes to pre-existing tests whose fixtures
  or assertions assumed the old fixed-1800px/unconditional-restoration
  behavior (`tests/test_pipeline_best_practices.py`,
  `tests/test_extractor_edge_cases.py`, `tests/test_concurrency_complete.py`).
- `python -m pytest tests/ -q`: 291 passed, 2 skipped (pre-existing),
  0 failed.
- Direct paired comparison (same process, same input, old-vs-new
  preprocessing back to back, isolating the code change from run-to-run
  OCR noise) on page 8 of the gold corpus: "Aeknowledgements" ->
  "Acknowledgements", "Fakistan; Iinduism" -> "Pakistan; Hinduism",
  a dropped page number ("Fundamental Rights 4") -> recovered
  ("Fundamental Rights 43"), confidence 0.769 -> 0.817.
- Full 14-page corpus, before/after (eval/results/baseline.json Phase 0 vs Phase 1 candidate):
  - Mean CER: `0.4992` -> `0.4944` (improved by 0.0048)
  - Mean WER: `0.7288` -> `0.7248` (improved by 0.0040)
  - Reading Order Tau: `0.6770` -> `0.6822` (improved by 0.0052)
  - Processing Latency: `59.8s/page` -> `33.2s/page` (nearly 2x speedup from eliminating redundant multi-pass resizing and avoiding contrast-crushing artifact traps)
  - `python3 -m pytest tests/`: 294 passed, 2 skipped, 0 failed.
  - `pytest tests/test_eval_regression.py`: PASSED.

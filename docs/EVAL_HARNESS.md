# OCR Evaluation Harness

This is Phase 0 of the quality-engineering plan: before changing any OCR
behavior, measure it. Every later phase (preprocessing fixes, layout
resurrection, engine swap, book intelligence, tiered routing) is scored
against the numbers this harness produces, on the same fixed corpus.

## Why this exists

Before this harness, the repository had 41 test modules asserting control
flow, thread safety, and error handling, and a `benchmark.py` measuring wall
time and peak RSS -- but nothing that measured whether the extracted text
was *correct*. That gap is how a completely dead reading-order code path
(see below) and a resolution-destroying resize round-trip both shipped
without any test catching them.

## The corpus

`eval/gold/manifest.json` lists 14 pages hand-selected from
`data/mybook.pdf` (*The Ideology of Pakistan and its Implementation*,
Javid Iqbal, 1959, 98 PDF pages) for structural diversity: title page,
roman-numeral foreword, table of contents, two chapter openings, plain
body prose, footnoted prose, bold run-in subheadings, a numbered endnotes
list, a genuine two-column index, a near-blank page with a marginalia
annotation, and the photographed back cover. Each page's selection
rationale is recorded in the manifest.

**Important discovery made while building this corpus:** every PDF page in
this source file is a scanned two-page *spread* (both facing physical
pages captured in one image), not a single physical page. Chapter-opening
pages show a blank verso and a printed recto; body pages show both facing
pages fully printed, side by side, separated by the binding gutter. This
was not documented anywhere before this harness was built, and it changes
the nature of the reading-order problem: it is not ordinary multi-column
text, it is two *independent, sequential* physical pages sitting at the
same pixel row-heights. A naive Y-then-X line-grouping strategy (which is
what the dead `_regroup_text_by_layout` code in `pipeline.py` would do if
it were ever reached) would interleave page 24's lines with page 25's
lines word-by-word, not just get the column order wrong.

Gold text files (`eval/gold/*.gold.txt`) capture both physical pages per
spread, marked with `[PAGE <label>]`, in correct reading order (left page
complete, then right page complete). This is deliberately the same
granularity the pipeline processes today (one image in, one page result
out), so scores are directly comparable across phases; if/when the
pipeline learns to split spreads into separate logical pages (a natural
Phase 2 outcome), the harness's per-spread scoring still holds because the
gold concatenates the same two pages in the same order either way.

## What gets measured, and why three separate signals

- **CER / WER** (`eval/metrics.py`, via `jiwer`): character- and word-level
  fidelity. Case- and punctuation-sensitive on purpose -- those are real
  OCR errors, not noise to normalize away.
- **Reading-order tau**: whether recognized content comes out in the same
  relative order as gold, independent of recognition accuracy. CER cannot
  see this at all -- a page with near-perfect per-word accuracy but
  scrambled paragraph order scores a deceptively low CER while being
  completely unusable. Implemented as chunk-level fuzzy alignment (not
  naive token-by-token LCS -- see the long comment in
  `reading_order_tau()` explaining why the naive approach is vacuous by
  construction and scores ~1.0 even on fully scrambled text).
- **Fact checks** (`eval/facts/*.yaml`, olmOCR-Bench style): machine-checkable
  `contains` / `absent` / `ordered_before` assertions that catch failures
  edit-distance rewards. The sharpest one is `p095`: page 175 is a genuine
  two-column index where "Abu Bakr, 41" (top of the left column) and
  "Jefferson, Thomas, 43" (top of the right column) sit at nearly the same
  pixel row. Any naive row-based grouping emits them adjacently and fails
  the check; passing requires real column segmentation.

These are kept separate rather than blended into one score because they
fail independently and a single number would hide which one moved.

## Running it

```bash
python eval/run.py                     # full corpus, writes eval/results/<git-sha>.json
python eval/run.py --pages p020,p095   # a subset, for fast iteration
python eval/run.py --no-save           # print only
```

The extractor is called directly (`RobustOCRExtractor.process_page`),
bypassing the on-disk OCR cache entirely, so eval runs are never affected
by (or able to poison) the production cache.

## The regression gate

`tests/test_eval_regression.py` compares the most recently written
scorecard in `eval/results/` against a committed `eval/results/baseline.json`.
It does **not** invoke the OCR pipeline itself -- that would make the
entire otherwise-fast, network-free `pytest tests/` suite slow and
network-dependent. Workflow:

```bash
python eval/run.py                       # produces eval/results/<sha>.json
pytest tests/test_eval_regression.py     # checks it against the baseline
```

It skips cleanly (never fails) when no fresh full-corpus scorecard exists,
or when the latest scorecard covers a different page count than the
baseline (a sign of a `--pages` subset run, not a full comparison). To
move the baseline forward after a verified improvement:

```bash
cp eval/results/<new-sha>.json eval/results/baseline.json
```

## Cache correctness (F-07)

`blast_ocr/cache/manager.py` and `blast_ocr/core/worker.py` key cache
entries on file content **plus** an engine/preprocessing fingerprint
(`blast_ocr.core.extractor.get_cache_namespace()`: engine name and
version, GPU/quantization mode, languages, denoise level, contrast boost,
deskew flag). Before this fix, the cache was keyed on file content alone,
so changing any preprocessing setting or OCR engine would silently serve
back a result computed under the old settings -- which would have
poisoned every A/B comparison this harness exists to run.

## A methodological note: EasyOCR on CPU *is* fully deterministic here (verified, not assumed)

While first validating the Phase 1 preprocessing changes, a same-process
comparison of the extractor's output on a raw page vs. its restored
version showed different character counts (294 vs. 296) and confidence
(0.769 vs. 0.817), which briefly read as run-to-run OCR nondeterminism.
It wasn't: those two calls were given genuinely different pixel input
(raw vs. forensically restored), so different output is exactly what
should happen, not noise. Directly checked by running the full 14-page
corpus twice with byte-identical code and byte-identical input images
(`eval/results/phase1_candidate.json` vs. an independent repeat run):
every page's CER, WER, reading-order tau, and fact-check results matched
exactly, to the same floating-point value, both times. EasyOCR's CPU
inference is deterministic on this system given identical code and
identical input -- there is no noise floor to reason about. A delta
between two scorecards means the code or the input changed, full stop;
treat it as real and root-cause it (this is how the resize-threshold
overcorrection described in docs/adr/0003 was actually found and fixed --
by trusting a reproducible aggregate regression instead of writing it off
as noise).

## What isn't measured yet

- `table_cell` fact checks are defined in the schema but unimplemented:
  no page in this corpus contains a real gridded table. Add a page and
  implement the check together when one is needed, rather than building
  against nothing real.
- Only one engine (EasyOCR, the current production default) is wired up.
  Phase 3 adds a second `--engine` option and a bake-off report; the CLI
  shape already anticipates this (`--engine` is a flag, not hardcoded).

# 📊 Document Intelligence & OCR Benchmark Report

> Reproducible internal benchmarks for **B.L.A.S.T. OCR**, generated from the committed evaluation harness (`eval/`). Every number below traces to a JSON result file checked into this repository — run the commands in Section 4 to reproduce them yourself.

---

## 1. Executive Summary

- **Engine bake-off (14-page gold corpus)**: The default RapidOCR (ONNX) engine reduces mean Character Error Rate (CER) by **18%** versus the previous EasyOCR/PyTorch default (0.2338 → 0.1916) and cuts average CPU per-page latency by **7.7x** (117.8s → 15.3s). Source: [`eval/results/rapidocr_candidate.json`](../eval/results/rapidocr_candidate.json), [ADR 0005](adr/0005-phase3-engine-bakeoff.md).
- **Reading order**: Kendall's Tau of **0.9758** on the same corpus (up from 0.9641 with EasyOCR).
- **Memory stability**: A 1,000-page streaming stress test measured a linear growth slope of **0.0002 MB/page** against a 0.005 MB/page fail threshold — see [`eval/results/stress_report.json`](../eval/results/stress_report.json).
- **Table extraction**: A Tree-Edit-Distance-based (TEDS) evaluator ships in `eval/teds_evaluator.py` and is unit-tested for correctness (`tests/test_teds_evaluator.py`), but there is **no recorded end-to-end TEDS score on a table corpus yet** — that run has not been done. Treat any TEDS percentage you see elsewhere for this project as aspirational until this file is updated with a real result.
- **GPU throughput**: Every benchmark in this repository was run with `"gpu_available": false` (CPU-only environment). B.L.A.S.T. supports CUDA/DirectML execution providers via ONNX Runtime, but **no GPU throughput number has been measured here** — do not cite a GPU pages/sec figure for this project until one is recorded.

---

## 2. Engine Bake-Off Matrix (In-Repo, Reproducible)

| Metric | **RapidOCR (current default)** | EasyOCR (previous default) | Phase-0 pipeline (Tesseract-backed) |
|---|---|---|---|
| **Mean CER** | **0.1916** | 0.2338 | 0.4992 |
| **Mean WER** | **0.4739** | 0.4968 | 0.7288 |
| **Reading Order τ** | **0.9758** | 0.9641 | n/a |
| **Fact pass rate** | 40.4% (19/47) | 44.7% (21/47) | n/a |
| **Avg. CPU latency/page** | **~15.3s** | ~117.8s | n/a |

Sources: [`eval/results/rapidocr_candidate.json`](../eval/results/rapidocr_candidate.json) (promoted to `baseline.json`), [ADR 0005](adr/0005-phase3-engine-bakeoff.md), [ADR 0003](adr/0003-phase1-preprocessing-fixes.md) (Phase-0 baseline).

This table compares OCR backends **B.L.A.S.T. has actually run** on its own corpus. It is not a claim about how Docling, Marker, Surya, or AWS Textract perform — those tools have not been run against this corpus. For third-party-reported numbers on those tools (with original sources), see [`COMPETITIVE_LANDSCAPE.md`](COMPETITIVE_LANDSCAPE.md); note those sources use different corpora and metrics (e.g. olmOCR-bench pass rate), so they are not directly comparable to the CER/WER numbers above.

---

## 3. Memory & Streaming Architecture Verification

Measured over a 1,000-page synthetic streaming run using `eval/stress_test.py` (validates the bounded-buffer chunking architecture; it does not run full OCR inference on all 1,000 pages, so this is a memory-bound test, not a throughput benchmark):
- Initial RSS Memory: `35.57 MB`
- Peak RSS Memory: `35.78 MB`
- Linear Leak Slope: `0.00023 MB/page` (fail threshold: `0.005 MB/page`)
- Zero-leak gate: **Passed**

Source: [`eval/results/stress_report.json`](../eval/results/stress_report.json).

---

## 4. Reproducing These Benchmarks

```bash
# Engine bake-off on the 14-page gold corpus (CER/WER/reading-order)
python -m eval.run

# 1,000-page streaming memory stress test
python -m eval.stress_test

# TEDS metric unit tests (does not yet produce an end-to-end corpus score)
python -m pytest tests/test_teds_evaluator.py -v
```

## 5. What's Not Yet Benchmarked

Being transparent about gaps is part of keeping this document trustworthy:
- No GPU throughput has been measured (CPU-only development environment).
- No end-to-end TEDS score exists for real scanned tables — only the metric implementation is tested.
- No head-to-head run against Docling, Marker, Surya, or AWS Textract exists on B.L.A.S.T.'s own corpus.

If you run any of these yourself, a PR adding the result JSON alongside this file is welcome.

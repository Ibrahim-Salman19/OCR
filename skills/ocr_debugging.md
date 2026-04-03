---
name: ocr-debugging
description: End-to-end debugging workflow for the B.L.A.S.T OCR pipeline. Use for failing tests, OCR quality regressions, memory/VRAM growth, threading/database instability, Streamlit UI state bugs, and doc-vs-code mismatch triage.
compatibility: Requires Python 3.12+, pytest, OpenCV, EasyOCR/Torch, and project-local test fixtures.
metadata:
  scope: blast-ocr
  focus: reliability-and-debuggability
---

# OCR Debugging Skill

## When To Use

Use this skill when any of these happen:

- OCR output quality degrades (missing text, low confidence spikes, gibberish).
- Test suite starts failing or becomes flaky.
- Memory/VRAM increases across long documents.
- Streamlit UI flow fails in tests or background threads.
- Pipeline behavior diverges from docs.

## Core Method

Follow this sequence strictly:

1. **Reproduce** with the smallest failing command first.
2. **Localize** to module/function and identify exact failing path.
3. **Patch minimally** while preserving existing architecture.
4. **Verify narrowly** (targeted tests), then **verify broadly** (full suite).
5. **Document risk** (what remains warning-only vs. fully fixed).

Do not skip from symptom directly to broad refactor.

## Project-Specific Debug Checklist

### 1) Test Triage

Run fast triage first:

```bash
python -m pytest tests -q -x
```

Then isolate failing scope:

```bash
python -m pytest tests/path/to/test_file.py::test_name -q
```

Rules:

- Fix deterministic failures before addressing warnings.
- Prefer production-code fixes over weakening assertions unless the test is non-deterministic by design.
- If changing test tolerance, justify with platform/runtime behavior and keep guardrails meaningful.

### 2) OCR Extractor Failures (`blast_ocr/core/extractor.py`)

Primary invariants:

- `process_page` always returns consistent schema on success.
- OCR inference path must not leak autograd references.
- Cleanup (`del`, `gc.collect`, and optional `torch.cuda.empty_cache`) runs on both success and failure paths.

Typical fixes:

- Wrap OCR call in `torch.inference_mode()` when torch exists.
- Use `finally` for cleanup of large arrays.
- Convert confidence values safely (`detach()`/`item()`/`float()`) before storage.

### 3) Pipeline/Batch Failures (`blast_ocr/pipeline.py`)

Primary invariants:

- Accept both path-based and image-object page inputs where tests mock either.
- Clean temporary raw/restored images deterministically.
- Avoid bare `except:`; catch `Exception` at minimum.

When dealing with `pdf2image`:

- Prefer `paths_only=True` + `output_folder` for memory stability in large batches.
- Ensure fallback path (`unknown page count`) follows same contract as batched path.

### 4) UI/Session Failures (`blast_ocr/ui/web_app.py`)

Primary invariants:

- `st.session_state` keys are initialized before read.
- Unit tests running without full Streamlit runtime must not spawn unsafe background behavior.
- Upload path handles extension validation and file-buffer failures gracefully.

When tests patch `streamlit.session_state` or `pipeline`:

- Add compatibility handling that preserves production behavior.
- Keep asynchronous mission-control flow for real runtime; use safe synchronous fallback for mocked pipeline contexts.

### 5) Memory/VRAM Debugging

Use two layers:

- **Functional memory guard**: tests that detect runaway growth trends.
- **Runtime profiling**: `tracemalloc` snapshots and RSS checks (`psutil`) for deeper analysis.

References:

- Python tracemalloc docs: use `start()`, `take_snapshot()`, and `compare_to()`.
- PyTorch inference-mode docs: ensure no autograd graph retention during inference.

## Failure Pattern Playbook

### Pattern: "Works alone, fails in full suite"

Likely causes:

- Shared state leakage (session/thread globals).
- Background thread still active at interpreter shutdown.
- Test assuming order or implicit initialization.

Actions:

- Initialize missing state keys explicitly.
- Guard thread launch on runtime context.
- Use per-test isolated fixtures and deterministic mocks.

### Pattern: "Memory test unstable across OS/CI"

Likely causes:

- Allocator variance (EasyOCR/Torch/OpenCV).
- One-time model load skewing ratio assertions.

Actions:

- Compare growth after warm-up snapshot.
- Keep threshold as leak guard, not exact allocator model.

### Pattern: "UI tests fail with missing ScriptRunContext"

Cause:

- Streamlit bare mode has no active script context.

Actions:

- Detect runtime context before launching background jobs.
- Provide deterministic failure/report path in tests.

## Verification Protocol

After each patch set:

1. Re-run only affected tests.
2. Re-run a broader cluster related to module boundaries.
3. Re-run full suite.

Suggested commands:

```bash
python -m pytest tests/test_foundation_coverage.py tests/test_extractor_edge_cases.py tests/test_pipeline_coverage.py tests/test_ui_mock.py tests/test_ui_coverage.py -q
python -m pytest tests -q
```

## Guardrails

- Do not weaken behavior silently (no broad exception swallowing beyond explicit safe fallbacks).
- Prefer small, auditable patches.
- Preserve API contracts and result schema expected by UI and DB layers.
- Avoid introducing hidden background side effects in test mode.

## Output Requirements For Debug Sessions

When completing a debug cycle, report:

1. Root cause by file and function.
2. Minimal patch summary.
3. Targeted and full-suite test outcomes.
4. Remaining warnings and whether they are product-risking or test-noise.

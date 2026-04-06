# OCR Engine Transition Playbook

This playbook defines a safe, reversible transition from EasyOCR to an alternative engine (target: PaddleOCR) for CPU-only deployments.

## Goals

- Preserve runtime reliability.
- Avoid output schema regressions.
- Keep rollback immediate and low-risk.

## Current Engine Contract (Must Be Preserved)

The extractor currently returns a page result dictionary with fields used downstream:

- `page` (int)
- `text` (str)
- `confidence` (float)
- `bbox_count` (int)
- `details` (list[dict]) where each detail includes:
  - `text` (str)
  - `conf` (float)
  - `bbox` (flattened list of ints)

This contract is consumed by:

- `blast_ocr/core/worker.py`
- `blast_ocr/pipeline.py`
- `blast_ocr/ui/web_app.py`

## Transition Phases

### Phase 0: No-Behavior-Change Refactor

- Introduce backend abstraction around OCR engine calls.
- Keep EasyOCR as default backend.
- Add feature flag:
  - `BLAST_OCR_ENGINE=easyocr|paddle`
  - default: `easyocr`.

### Phase 1: Paddle Backend Adapter (Opt-In)

- Implement Paddle backend as an adapter that normalizes output to existing contract.
- Keep all pipeline/UI/database behavior unchanged.
- Ensure adapter maps Paddle output fields (`rec_texts`, `rec_scores`, polygons) into existing detail format.

### Phase 2: Shadow Validation

- Run both engines on the same inputs in non-blocking validation mode.
- Compare:
  - success/failure rate
  - extraction latency
  - confidence distribution
  - text drift (string similarity and critical-field checks)

### Phase 3: Canary Rollout

- Route a small controlled percentage of jobs to Paddle backend.
- Maintain immediate rollback via env var.
- Monitor errors and latency.

### Phase 4: Cutover

- Make Paddle default only after canary acceptance criteria pass.
- Keep EasyOCR backend available for fallback/rollback.

## Rollback Strategy

Rollback must not require code deployment.

- Set `BLAST_OCR_ENGINE=easyocr`.
- Reboot app.
- Confirm health endpoint and smoke OCR path.

## Acceptance Gates

Promotion to next phase requires all of:

1. No increase in fatal job failure rate.
2. No contract/schema regressions in outputs.
3. Cloud startup remains stable.
4. Full test suite passes.
5. Representative document benchmark passes pre-defined thresholds.

## CPU-Only Baseline Controls

Keep these during migration:

- `BLAST_OCR_OCR_GPU=false`
- `BLAST_OCR_MAX_WORKERS=1` (cloud), low worker count locally
- deterministic model/cache directories
- avoid runtime model downloads in steady-state production

## Test Plan Requirements

### Contract Tests

- Verify backend output schema and types.
- Verify confidence values are numeric floats.
- Verify bbox flattening format.

### Regression Tests

- Existing extractor tests continue passing with default backend.
- Pipeline end-to-end tests unchanged.
- UI upload and mission-control flows unchanged.

### Deployment Tests

- Streamlit startup health checks.
- cloud runtime with CPU-only config.
- first-run model bootstrap and post-bootstrap steady-state.

## Risks and Controls

- Risk: backend output format mismatch.
  - Control: explicit adapter + contract tests.
- Risk: runtime incompatibility on hosted Python versions.
  - Control: version gate and runtime validation before enabling backend.
- Risk: startup stalls due to model initialization/download.
  - Control: prewarm/bootstrap stage and health-safe UI gating.

## Operational Checklist

Before enabling non-default backend in production:

- [ ] Feature flag is implemented and documented.
- [ ] Adapter contract tests pass.
- [ ] Full suite passes.
- [ ] Shadow run comparison report generated.
- [ ] Canary error/latency dashboards ready.
- [ ] Rollback runbook tested.

# Challenger 1 Dispatch Instructions

## Working Directory
`/mnt/d/code/Projects/Python/OCR_Book/.agents/challenger_1`

## Scope
Adversarial Verification & Full-Suite Stress Test:
1. Run the entire test suite across the repository (`pytest`):
   - All legacy & regression tests in `tests/`
   - All M1-M4 unit tests (`test_batched_engine.py`, `test_streaming_storage.py`, `test_benchmark_eval.py`, etc.)
   - All 190 E2E tests across Tiers 1-4 (`tests/e2e/`)
2. Stress test boundary conditions:
   - Zero-length inputs, corrupt images, invalid PDF streams
   - Concurrency bursts with Redis mock / in-memory queues
   - High volume stream iteration memory consumption
3. Verify that 100% of tests pass with 0 failures and 0 regressions.

## Reference Files
- `/mnt/d/code/Projects/Python/OCR_Book/.agents/ORIGINAL_REQUEST.md` (MANDATORY TO READ)
- `/mnt/d/code/Projects/Python/OCR_Book/PROJECT.md`
- `/mnt/d/code/Projects/Python/OCR_Book/TEST_READY.md`

## Instructions
1. Read `ORIGINAL_REQUEST.md`, `PROJECT.md`, `TEST_READY.md`.
2. Execute full test suite runs and stress verification.
3. Record exact counts, durations, and pass rates.
4. Write `handoff.md` with structured verdict: `APPROVE` or `REQUEST_CHANGES` (with exact failure logs if any).
5. Notify orchestrator via `send_message`.

## 2026-08-16T06:39:34Z
You are challenger_1 assigned to perform full-suite adversarial verification and regression testing.

Working Directory: /mnt/d/code/Projects/Python/OCR_Book/.agents/challenger_1
Project Root: /mnt/d/code/Projects/Python/OCR_Book
Original Request: /mnt/d/code/Projects/Python/OCR_Book/.agents/ORIGINAL_REQUEST.md
Scope Document: /mnt/d/code/Projects/Python/OCR_Book/PROJECT.md
Dispatch: /mnt/d/code/Projects/Python/OCR_Book/.agents/challenger_1/DISPATCH.md

Tasks:
1. Read ORIGINAL_REQUEST.md, PROJECT.md, and TEST_READY.md.
2. Initialize BRIEFING.md and progress.md in your working directory.
3. Execute the entire test suite (`pytest`) across all unit tests, regression tests, and all 190 E2E tests across Tiers 1-4.
4. Assert that 100% of all tests pass with 0 failures and 0 regressions.
5. Record exact test counts, pass rates, and durations.
6. Write `handoff.md` with explicit structured verdict: `APPROVE` or `REQUEST_CHANGES`.
7. Notify orchestrator via `send_message`.


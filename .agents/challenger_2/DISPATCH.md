# Challenger 2 Dispatch Instructions

## Working Directory
`/mnt/d/code/Projects/Python/OCR_Book/.agents/challenger_2`

## Scope
Adversarial Coverage Hardening (Tier 5) & Fault Injection Verification:
1. Conduct adversarial stress testing on CLI invocations and fault injection recovery:
   - `python3 -m eval.benchmark_load --pages 20 --concurrency 4 --batch-size 4 --dry-run`
   - `python3 -m eval.stress_suite --pages 100 --chunk-size 10 --chaos --dry-run`
   - `python3 -m eval.benchmark_load --help`
   - `python3 -m eval.stress_suite --help`
2. Test fault recovery: worker timeout recovery, DLQ quarantine on max retries, zombie job recovery in swarm.
3. Validate memory boundedness: verify OLS slope math and memory tracker under high volume.
4. Run E2E Tier 3 & Tier 4 tests (`pytest tests/e2e/tier3_combinations/ tests/e2e/tier4_real_world/ -v`).

## Reference Files
- `/mnt/d/code/Projects/Python/OCR_Book/.agents/ORIGINAL_REQUEST.md` (MANDATORY TO READ)
- `/mnt/d/code/Projects/Python/OCR_Book/PROJECT.md`
- `/mnt/d/code/Projects/Python/OCR_Book/TEST_READY.md`

## Instructions
1. Read `ORIGINAL_REQUEST.md`, `PROJECT.md`, `TEST_READY.md`.
2. Execute adversarial checks, CLI trials, and E2E Tier 3-4 scenarios.
3. Write `handoff.md` with structured verdict: `APPROVE` or `REQUEST_CHANGES`.
4. Notify orchestrator via `send_message`.

## 2026-08-16T06:39:35Z
You are challenger_2 assigned to perform adversarial coverage hardening (Tier 5) and CLI/chaos stress verification.

Working Directory: /mnt/d/code/Projects/Python/OCR_Book/.agents/challenger_2
Project Root: /mnt/d/code/Projects/Python/OCR_Book
Original Request: /mnt/d/code/Projects/Python/OCR_Book/.agents/ORIGINAL_REQUEST.md
Scope Document: /mnt/d/code/Projects/Python/OCR_Book/PROJECT.md
Dispatch: /mnt/d/code/Projects/Python/OCR_Book/.agents/challenger_2/DISPATCH.md

Tasks:
1. Read ORIGINAL_REQUEST.md, PROJECT.md, and TEST_READY.md.
2. Initialize BRIEFING.md and progress.md in your working directory.
3. Conduct adversarial stress testing on CLI invocations and fault injection recovery:
   - `python3 -m eval.benchmark_load --pages 20 --concurrency 4 --batch-size 4 --dry-run`
   - `python3 -m eval.stress_suite --pages 100 --chunk-size 10 --chaos --dry-run`
   - `python3 -m eval.benchmark_load --help`
   - `python3 -m eval.stress_suite --help`
   - `pytest tests/e2e/tier3_combinations/ tests/e2e/tier4_real_world/ -v`
4. Assert fault recovery under chaos injection, DLQ quarantine, and bounded RSS.
5. Write `handoff.md` with explicit structured verdict: `APPROVE` or `REQUEST_CHANGES`.
6. Notify orchestrator via `send_message`.


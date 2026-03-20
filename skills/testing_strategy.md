---
name: Testing Strategy
description: How to verify, benchmark, and stress-test the OCR pipeline.
---

# Testing Strategy Skill

## 1. Unit Tests
Located in `tests/`.
- **Run**: `pytest`
- **Focus**:
  - `test_critical_paths.py`: Verifies locks, cache hashing, and singleton patterns.
  - **Philosophy**: Test logic, not libraries. Don't test *if* EasyOCR works (that's their job), test if *we* handle EasyOCR correctly.

## 2. Performance Benchmarking
Use `benchmark.py` for regression testing performance.
- **Run**: `python benchmark.py`
- **Metrics**:
  - Time per Page.
  - Peak RAM Usage (Critical for stability).
  - Cache Hit Speedup.

## 3. Foundation Verification
Use `verify_foundation.py` as a "Sanity Check" script.
- Great for post-deployment or environment setup checks.
- Verifies: Imports, DB Creation, Log Creation, Engine Init.

## 4. Manual "Smoke Tests"
- **Ghost Data**: Check `blast_output/` and temp dirs to ensure files aren't accumulating.
- **Visual Check**: Open a generated `.docx` to verify formatting/headers are preserved.

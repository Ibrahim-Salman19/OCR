---
name: Advanced QA
description: Integration testing, end-to-end flows, and stress testing.
---

# Advanced QA Skill

## 1. Integration Testing
Testing components working together.
- **Scope**: `Pipeline -> Database`, `Extractor -> Cache`.
- **Tool**: `pytest tests/integration/`.

## 2. End-to-End (E2E) Scenarios
Simulate real user behavior.
- **Script**: `benchmark.py` covers the "Happy Path" (User uploads -> Gets Result).
- **Edge Cases**:
  - Upload 0-byte file.
  - Upload password-protected PDF.
  - Upload file with 10k pages (Stress Test).

## 3. Stress Testing
- **Concurrency**: Run 10 instances of `BlastPipeline` in parallel threads.
- **Resource Starvation**: Run with artificially limited RAM (container limits) to verify graceful failure.

## 4. Visual Regression
- **Compare**: Generate output today vs. known good output.
- **Diff**: Text diffing is easy. Visual layout diffing (for UI) requires screenshots (Playwright/Selenium - Future work).

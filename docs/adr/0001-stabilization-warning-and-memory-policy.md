Title: Stabilization policy for warnings, resource cleanup, and memory-test robustness
Status: accepted
Date: 2026-04-04

Context:
- The OCR test suite had intermittent instability from warning escalation, unclosed logging handlers, and host-dependent memory checks.
- Reliability work required balancing strictness (catch regressions) with practical cross-host stability.

Decision:
- Enforce warnings-as-errors with explicit third-party suppressions in pytest config.
- Close existing logger handlers before replacement to prevent file descriptor leaks.
- Keep memory leak tests as coarse regression guards with host-tolerant thresholds and safe skip behavior for low-memory/inspection-limited environments.
- Register custom pytest markers and disable doctest plugin in this repo to avoid unrelated collection noise from text artifacts.

Alternatives considered:
- Option A: Keep warnings permissive and avoid strict policy.
  - Rejected due to hidden regressions and reduced signal quality.
- Option B: Keep strict policy but silence all warning classes broadly.
  - Rejected due to over-suppression and reduced value of warning gate.

Consequences:
- Positive:
  - Better reliability signal in CI/local runs.
  - Resource leak failures become deterministic and actionable.
  - Reduced flakiness for memory and property-based tests.
- Negative:
  - Requires ongoing maintenance of explicit warning filters as dependencies evolve.
  - Memory tests remain heuristic by design (not exact allocator model validation).

Verification:
- Tests run:
  - `python -m pytest -q`
  - `python -m pytest -q` (repeated 3x)
- Result:
  - Stable passing runs across repetition after policy and test hardening updates.

---
name: Decision Engineering
description: This skill should be used when the user asks to prioritize fixes, make architecture tradeoffs, choose what to debug first, or create a reliability decision log for OCR and pipeline stability work.
version: 0.1.0
---

# Decision Engineering Skill

## Purpose

Use a repeatable decision system so debugging and feature work stay fast, auditable, and low-risk.

## Decision Stack

Apply these frameworks in order:

1. **Mitigation-First (SRE)**
   - Stop user-visible failure first.
   - Delay deep root-cause exploration until impact is contained.

2. **OODA Loop (Observe, Orient, Decide, Act)**
   - Observe: gather failing tests, logs, warnings, crash signals.
   - Orient: isolate module ownership and blast radius.
   - Decide: pick smallest safe patch with highest reliability gain.
   - Act: patch, run narrow tests, then broad suite, then stress loop.

3. **RICE Prioritization for Backlog**
   - Reach: how many flows/users/tests affected.
   - Impact: severity on correctness, uptime, or security.
   - Confidence: certainty of diagnosis and fix.
   - Effort: estimated engineering cost.
   - Formula: `RICE = (Reach * Impact * Confidence) / Effort`.

4. **ADR Logging for Lasting Choices**
   - Record major decisions with context, options, tradeoffs, and consequences.
   - Keep one decision per record.

## OCR Project Playbook

### A) Incident / Red Build

1. Run targeted failing tests first.
2. Classify issue:
   - `Correctness` (wrong results)
   - `Reliability` (flaky, race, resource leak)
   - `Performance` (memory/latency growth)
   - `Tooling` (config/collection/runtime)
3. Apply mitigation-first patch.
4. Verify in three layers:
   - Narrow test(s)
   - Related module cluster
   - Full suite
5. Run repeat loop (`3x`) for anti-flake confidence.

### B) Architecture Decision Trigger

Create an ADR when any condition is true:

- Change affects cross-module contract.
- Change introduces new runtime mode or fallback path.
- Warning policy / test policy is tightened globally.
- Tradeoff is non-obvious and likely to be revisited.

### C) Priority Heuristics (Tie-Breakers)

If two options have similar RICE score, choose in this order:

1. Lower blast radius.
2. Better observability after change.
3. Simpler rollback.
4. Lower long-term maintenance cost.

## Reliability Gates

Before considering a stabilization cycle complete:

- `pytest -q` passes.
- `pytest -q` repeated 3 times passes.
- New warnings are either fixed or explicitly justified in config.
- Resource cleanup paths are verified on both success and failure branches.

## ADR Template (Short)

Use this when logging a major decision:

```text
Title:
Status: proposed | accepted | superseded
Date:

Context:
-

Decision:
-

Alternatives considered:
- Option A:
- Option B:

Consequences:
- Positive:
- Negative:

Verification:
- Tests run:
- Monitoring signal:
```

## Output Format for Decision Reviews

When reporting a decision cycle, include:

1. Problem statement (1-2 lines)
2. Chosen framework path (Mitigation -> OODA -> RICE -> ADR)
3. Patch scope (files/functions)
4. Validation evidence (targeted, related, full, repeat runs)
5. Remaining risk and next action

"""
tests.adversarial

B.L.A.S.T. OCR Programmatic Adversarial Test Harness (Tier 4).

Organizes the hostile/malformed-input regression suites specified in
docs/HARDENING_BLUEPRINT_AND_TEST_SPECS.md §4 by threat domain, mirroring the
already-shipped GAP-01..12 hardening fixes (docs §5.3) against the real
`blast_ocr` entry points -- not the illustrative module paths named in the
blueprint's own example code, which don't exist in this codebase under those
names (e.g. there is no `security.pdf_validator` or `core.text_sanitizer`;
the equivalent real logic lives in `security.gateway` and `core.exporter`).
"""

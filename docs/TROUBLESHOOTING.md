# 🛠️ Troubleshooting Guide

This guide covers common issues encountered during OCR operations and how B.L.A.S.T. automatically resolves or reports them.

## 🪟 Windows File Hub Problems

### Error: `PermissionError: [WinError 32]` or `WinError 5`
-   **Cause**: This happens when the B.L.A.S.T. `TemporaryDirectory` cleanup fires while a trailing `pdftoppm.exe` or `pdftocairo.exe` process still holds a lock on an image file.
-   **Remediation**: B.L.A.S.T. has a built-in **Windows Cleanup Hardener**. It catches this error, sleeps for 500ms, and explicitly retries the deletion up to 5 times.
-   **Manual Fix**: If persistent, ensure no other instance of the app is running and manually delete the `.tmp` or `pages/` directory.

---

## 🗄️ Database Failures

### Error: `OperationalError: database is locked`
-   **Cause**: Concurrent writes in SQLite during heavy multi-threading.
-   **Remediation**: B.L.A.S.T. uses **WAL Mode** and **IMMEDIATE** isolation. It will automatically wait up to the `busy_timeout` (5s) for the lock to release.
-   **Manual Fix**: Increase `busy_timeout` in `blast_ocr/storage/database.py` or reduce `max_workers`.

### Error: `Transaction rolled back` or `Session poisoned`
-   **Cause**: A previous unhandled exception left a thread-local session in an unusable state.
-   **Remediation**: Each core method is wrapped in a `try...except...rollback` block, ensuring the session is reset immediately upon failure.

---

## 📄 OCR Engine Glitches

### Error: `ImageLoadError: Page 1 extraction failed`
-   **Cause**: The source file is corrupt, or OpenCV cannot decode the rendered image.
-   **Remediation**: B.L.A.S.T. marks the page as failed and continues with subsequent pages to prevent a total job crash. Check the `PAGE_RESULTS` table for specific error messages.

### Symptom: OCR Text is "Garbage" or Gibberish
-   **Cause**: Low image resolution (DPI < 200) or high noise.
-   **Manual Fix**: Enhance the scan quality. Ensure Poppler is used via `use_pdftocairo=True` (default in v2.0).

---

## 🏥 The Self-Healing System

B.L.A.S.T. employs a **Tiered Recovery Logic**:

1.  **Transient Failure**: Network glich or GPU spike? -> **Retry** with exponential backoff.
2.  **Logic Failure**: Missing file or invalid path? -> **Fatal** (Immediate stop for that page).
3.  **Concurrency Failure**: DB lock? -> **Wait** (Busy timeout).

## 🔗 Next Steps
-   [API Reference](API_REFERENCE.md)
-   [Introduction](INTRODUCTION.md)

---

## 🔄 OCR Engine Migration Troubleshooting

### Symptom: New backend runs but pipeline output is malformed
- Cause: backend result schema does not match current extractor contract.
- Fix: enforce adapter normalization to `{page, text, confidence, bbox_count, details}` before returning from extractor path.

### Symptom: Cloud startup fails after backend swap
- Cause: model bootstrap/download path or runtime dependency mismatch.
- Fix: keep EasyOCR default and enable new backend with feature flag only after runtime compatibility validation.

### Symptom: CPU inference slower than expected after migration
- Cause: default backend tuning not aligned with cloud CPU limits.
- Fix: cap workers, set backend-specific CPU thread controls, benchmark representative documents before cutover.

### Symptom: Canary failures after enabling new backend
- Cause: hidden edge cases in document layouts.
- Fix: rollback immediately via engine feature flag and continue shadow comparison until acceptance criteria pass.

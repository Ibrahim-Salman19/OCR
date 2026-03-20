---
name: Error Recovery (Healing)
description: Understanding and extending the Self-Healing OCR capabilities.
---

# Error Recovery Skill

## 1. The Healing Philosophy
The B.L.A.S.T. pipeline is designed to "fail gracefully" and "self-correct" where possible.
- **Core Logic**: `blast_ocr/core/healing.py`.
- **Global Instance**: `healer` object.

## 2. Retry Mechanism
We use an exponential backoff decorator `@healer.retry_with_backoff`.

```python
@healer.retry_with_backoff
def fragile_operation():
    # If this fails, it retries 3 times (default)
    # Waiting 2s, 4s, 8s...
    ...
```

### Config
Controlled via `config.py` (env vars):
- `OCR_MAX_RETRIES`: Default 3.
- `OCR_RETRY_BACKOFF`: Default 2.

## 3. Fatal vs. Transient Errors
The healer is smart enough **NOT** to retry fatal errors:
- `FileNotFoundError`: File won't appear by magic.
- `OCREngineError`: If the engine is broken (DLL missing), retrying won't fix it.
- `ImageLoadError`: Corrupt file.

**Action**: When adding new exceptions, ensure they are classified correctly in `healing.py` if they should skip retry.

## 4. Fallback Chains
Start with the best method, fall back to robust ones.
*Concept (Partially Implemented)*:
1. Try GPU OCR.
2. If VRAM OOM -> Fallback to CPU OCR.
3. If CPU Fail -> Fallback to Tesseract (if installed).

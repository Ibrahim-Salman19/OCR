---
name: OCR Debugging
description: Workflow for debugging OCR accuracy, performance, and stability issues in the B.L.A.S.T. pipeline.
---

# OCR Debugging Skill

## 1. Environment Verification
Before debugging code, verify the runtime environment.

```bash
# Check DLL dependencies (Windows)
python dll_check.py

# Verify torch/cuda availability
python -c "import torch; print(f'CUDA: {torch.cuda.is_available()}')"
```

## 2. Common Failure Modes

### Memory Leaks (Increasing Time/Page)
- **Symptoms**: Processing slows down (e.g., 100s -> 150s), "DefaultCPUAllocator: not enough memory".
- **Fix**: 
  - Ensure `del processed_img` is called in `extractor.py`.
  - Check `torch.cuda.empty_cache()` usage.
  - Reduce `max_workers` in `parallel.py` (default: 2 for CPU safety).

### "No Space Left on Device"
- **Cause**: Temp files from `pdf2image` not being cleaned up.
- **Fix**:
  - Check `blast_ocr/main.py` usage of `tempfile.TemporaryDirectory`.
  - Ensure `os.remove(fpath)` is called inside processing loops.

### Silent Failures / Crashing
- **Cause**: Missing DLLs for `torch` or `cv2`.
- **Fix**: Run `dll_check.py`. Install VC++ Redistributable.

## 3. Logging & Tracing
Enable debug logging to see per-page events.

```python
# In config.py or via env var
LOG_LEVEL = "DEBUG"
```

Logs will show:
- `Page X: Cache hit/miss`
- `Initializing EasyOCR...`
- `Downscaling large image...`

## 4. Visual Debugging
To inspect what the OCR engine "sees":
1. Modify `extractor.py` to save preprocessed images:
   ```python
   cv2.imwrite(f"debug_preproc_{page_number}.png", processed_img)
   ```
2. Check for over-binarization or skew issues.

---
name: OCR Performance Tuning
description: Strategies to optimize B.L.A.S.T. OCR for speed and resource usage (2026 Edition).
---

# OCR Performance Tuning (2026 Edition)

## 1. Hardware Acceleration (GPU)
- **Requirement**: NVIDIA GPU + CUDA.
- **Torch 2.x**: Use `torch.compile()` if custom models are added.
  - Speedup: Free 20-30% on supported hardware.

## 2. Quantization (Memory)
For lower VRAM usage (<4GB cards):
- Use `int8` or `float16` precision where possible.
- **EasyOCR**: Default is `float32`. Switching to `quantize=False` (paradoxically) uses `float16` on GPU in newer versions automatically if supported.

## 3. Parallelism
- **CPU**: `max_workers=2`.
- **GPU**: Serialize (`max_workers=1`).
- **Batching**: Use `readtext_batched` (if supported) vs loop.

## 4. Preprocessing
- **Resolution**: 1800-2200px width.
- **Denoising**: Skip unless necessary.

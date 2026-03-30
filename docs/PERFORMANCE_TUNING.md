# ⚡ Performance Tuning & Resource Management

Operating deep learning models (EasyOCR) on local hardware requires precise resource orchestration to prevent OOM (Out of Memory) crashes and VRAM fragmentation.

## 🧠 Memory Optimization (CUDA/VRAM)

Large-scale PDF processing can quickly exhaust GPU memory if not managed correctly.

### 1. Autograd Graph Breakage
By default, PyTorch tensors retain a computation graph for backpropagation. Storing these in a result dictionary prevents the GC from freeing VRAM.
-   **Solution**: All OCR outputs are detached and cast to scalars/strings immediately (e.g., `confidence.detach().item()`).

### 2. Fragmentation Prevention
Repeatedly processing images of different sizes (e.g., a small landscape slide vs. a tall vertical scan) fragments CUDA memory blocks.
-   **Solution**: We trigger `torch.cuda.empty_cache()` every 5 pages to force the allocator to coalesce free blocks.

### 3. Explicit RAM Garbage Collection
Python's internal GC may delay cleanup of large NumPy image arrays.
-   **Solution**: After processing a page, we call `del img_array` followed by `gc.collect()` to ensure RAM is reclaimed before the next page load.

---

## ⚙️ Parallelism Strategy

B.L.A.S.T. uses a **Worker-Limited Threading Model**.

| Environment | Optimization | Logic |
| :--- | :--- | :--- |
| **Windows CPU** | `max_workers=2` | Prevents RAM exhaustion when loading multiple EasyOCR instances into RAM. |
| **NVIDIA GPU** | `max_workers=1` | Deep-learning inference is serial by nature on a single GPU. Serialization prevents VRAM race conditions. |

### The Global Lock (`_ocr_global_lock`)
Because EasyOCR is not natively thread-safe, all calls to `reader.readtext()` are serialized via a module-level lock. This allows **Preprocessing** (CPU-bound) to overlap with **Inference** (GPU-bound), maximizing throughput.

---

## 📉 Benchmarking

Typical performance on a mid-range CPU (i7 / 16GB RAM):
-   **PDF Splitting**: ~0.2s / page
-   **OCR Inference**: ~1.5s - 3.0s / page
-   **DOCX Generation**: ~0.1s / doc

## 🔗 Next Steps
-   [Troubleshooting](TROUBLESHOOTING.md)
-   [API Reference](API_REFERENCE.md)

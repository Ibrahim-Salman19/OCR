"""
PHASE 2: PyTorch VRAM management, autograd graph leaks, and fragmentation.
"""

import pytest
import numpy as np
import tempfile
import os
import cv2
from unittest.mock import patch
import threading


# ── Test 2.1: Autograd graph not attached to stored confidence scores ──────
def test_no_autograd_graph_in_stored_results():
    """
    REASONING: If EasyOCR returns raw tensors and the pipeline stores
    them in result["confidence"] without .item() or .detach(),
    the entire backward computation graph stays alive in VRAM,
    growing with every page processed.
    """
    try:
        import torch
    except ImportError:
        pytest.skip("PyTorch not available")

    from blast_ocr.core.extractor import RobustOCRExtractor

    # Create a fake EasyOCR result with a gradient-tracked tensor
    mock_tensor_conf = torch.tensor(0.95, requires_grad=True)
    mock_readtext_output = [
        ([[0, 0], [100, 0], [100, 50], [0, 50]], "TEST TEXT", mock_tensor_conf)
    ]

    extractor = RobustOCRExtractor()
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        img = np.full((100, 100, 3), 255, dtype=np.uint8)
        cv2.imwrite(f.name, img)
        img_path = f.name

    try:
        with patch.object(
            extractor.reader, "readtext", return_value=mock_readtext_output
        ):
            with extractor.lock:
                pass  # Lock is held by patch context
            result = extractor.process_page(img_path, 1)

        confidence = result.get("confidence", 0)

        # If confidence is a tensor with grad, the graph is leaking
        if hasattr(confidence, "requires_grad") and confidence.requires_grad:
            pytest.fail(
                "BUG-VRAM-AUTOGRAD-01 | HIGH | leak\n"
                "Confidence score stored with autograd graph attached.\n"
                "Every page keeps its computation graph in VRAM.\n"
                "Fix: Apply .item() to all tensor outputs before storing in result dict."
            )

        if hasattr(confidence, "grad_fn") and confidence.grad_fn is not None:
            pytest.fail(
                "BUG-VRAM-AUTOGRAD-02 | HIGH | leak\n"
                "Tensor with grad_fn stored in result — computational graph not severed.\n"
                "Fix: Use tensor.detach().item() on all EasyOCR tensor outputs."
            )
    finally:
        os.unlink(img_path)


# ── Test 2.2: VRAM fragmentation over variable-size image batches ──────────
def test_vram_fragmentation_variable_sizes():
    """
    REASONING: Processing images of sizes 200x200, then 1800x1800, then 50x50
    creates a Swiss-cheese pattern in VRAM. reserved - allocated grows unboundedly.
    Calling empty_cache() periodically defragments and releases unused blocks.
    """
    try:
        import torch

        if not torch.cuda.is_available():
            pytest.skip("CUDA not available — fragmentation test requires GPU")
    except ImportError:
        pytest.skip("PyTorch not available")

    from blast_ocr.core.extractor import RobustOCRExtractor

    extractor = RobustOCRExtractor()

    # Variable dimensions that cause fragmentation
    sizes = [(200, 200), (1800, 1800), (50, 50), (1200, 800), (100, 1600)] * 5

    fragmentation_ratios = []

    for w, h in sizes:
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            img = np.full((h, w, 3), 200, dtype=np.uint8)
            cv2.imwrite(f.name, img)
            path = f.name
        try:
            extractor.process_page(path, 1)
            allocated = torch.cuda.memory_allocated()
            reserved = torch.cuda.memory_reserved()
            if reserved > 0:
                frag_ratio = (reserved - allocated) / reserved
                fragmentation_ratios.append(frag_ratio)
        finally:
            os.unlink(path)

    if fragmentation_ratios:
        max_frag = max(fragmentation_ratios)
        if max_frag > 0.5:
            pytest.fail(
                f"BUG-VRAM-FRAG-01 | MEDIUM | leak\n"
                f"VRAM fragmentation ratio reached {max_frag:.1%}.\n"
                f"reserved={torch.cuda.memory_reserved() // 1024 // 1024}MB "
                f"allocated={torch.cuda.memory_allocated() // 1024 // 1024}MB\n"
                f"Fix: Call torch.cuda.empty_cache() after every batch or every N pages "
                f"to release fragmented blocks back to OS."
            )


# ── Test 2.3: del processed_img actually executes (not in dead code path) ─
def test_explicit_del_in_process_page():
    """
    REASONING: If 'del processed_img' is inside an if-block or try-block
    that doesn't always execute, memory leaks on the code paths that skip it.
    """
    import inspect
    from blast_ocr.core.extractor import RobustOCRExtractor

    source = inspect.getsource(RobustOCRExtractor.process_page)

    assert "del processed_img" in source, (
        "BUG-MEM-DEL-01 | MEDIUM | leak\n"
        "del processed_img not found in process_page source.\n"
        "Large numpy arrays (~20MB each) will accumulate across all pages."
    )

    assert "gc.collect()" in source, (
        "BUG-MEM-GC-01 | LOW | leak\n"
        "gc.collect() not called after del — Python GC may defer cleanup."
    )


# ── Test 2.4: Thread-local inference state does not bleed across threads ──
def test_inference_thread_local_state_no_bleed():
    """
    REASONING: PyTorch multithreaded inference within a web server can
    retain memory allocations in thread-local storage even after thread
    execution completes. tracemalloc detects this.
    """
    from blast_ocr.core.extractor import RobustOCRExtractor

    extractor = RobustOCRExtractor()

    # Warm-up inference once so one-time backend initialization does not skew thread metrics
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        warmup_path = f.name
    try:
        cv2.imwrite(warmup_path, np.full((100, 100, 3), 200, dtype=np.uint8))
        extractor.process_page(warmup_path, 0)
    finally:
        if os.path.exists(warmup_path):
            os.unlink(warmup_path)

    thread_memory = {}
    lock = threading.Lock()

    def run_inference(tid):
        import tracemalloc as tm

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            img_path = f.name

        try:
            cv2.imwrite(img_path, np.full((100, 100, 3), 200, dtype=np.uint8))
            tm.start()

            try:
                extractor.process_page(img_path, tid)
            except Exception:
                pass

            snap = tm.take_snapshot()
            total = sum(s.size for s in snap.statistics("lineno"))
            with lock:
                thread_memory[tid] = total
        finally:
            tm.stop()
            if os.path.exists(img_path):
                os.unlink(img_path)

    for i in range(3):
        t = threading.Thread(target=run_inference, args=(i,))
        t.start()
        t.join()

    # Memory per thread should be roughly equal — large divergence = leak
    if len(thread_memory) > 1:
        vals = list(thread_memory.values())
        ratio = max(vals) / max(min(vals), 1)
        if ratio > 10:
            pytest.fail(
                f"BUG-THREAD-MEM-01 | MEDIUM | leak\n"
                f"Thread memory divergence ratio={ratio:.1f}x: {thread_memory}\n"
                f"One thread retained significantly more memory — thread-local state pollution."
            )

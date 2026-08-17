# DISPATCH — worker_m1

**Task**: Implement Milestone 1 (High-Throughput Batch Pipeline & GPU Acceleration)
**Working Directory**: `/mnt/d/code/Projects/Python/OCR_Book/.agents/worker_m1`
**Scope Document**: `/mnt/d/code/Projects/Python/OCR_Book/PROJECT.md`
**Original Request**: `/mnt/d/code/Projects/Python/OCR_Book/.agents/ORIGINAL_REQUEST.md`
**Survey Blueprint**: `/mnt/d/code/Projects/Python/OCR_Book/.agents/survey_explorer_1/report.md`

### Mandatory Integrity Warning
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

### Implementation Checklist
1. `blast_ocr/core/batch_preprocessor.py`:
   - `BatchPreprocessor` class: zero-disk in-memory PDF/image rasterization with PyMuPDF/pdf2image fallback, SIMD tensor normalization (ImageNet mean/std, scale 1/255), dynamic aspect-ratio crop bucketing to minimize padding.
2. `blast_ocr/core/onnx_session.py`:
   - `ONNXSessionManager` class: multi-provider execution hierarchy (`TensorrtExecutionProvider` -> `CUDAExecutionProvider` -> `DmlExecutionProvider` -> `CPUExecutionProvider`).
   - Session options tuning: `intra_op_num_threads`, `inter_op_num_threads`, `graph_optimization_level`.
3. `blast_ocr/core/tensor_decoder.py`:
   - `VectorizedTensorDecoder`: Vectorized CTC greedy decoding (NumPy vectorized argmax + label mapping) and concurrent DBNet polygon segmentation/binarization.
4. `blast_ocr/core/engines/base.py`:
   - Extend `BaseOCREngine` with `process_batch(self, images: List[Union[str, np.ndarray]], page_numbers: Optional[List[int]] = None, **kwargs) -> List[Dict[str, Any]]`.
5. `blast_ocr/core/engines/batched_rapidocr.py`:
   - `BatchedRapidOCREngine` class implementing dynamic batch detection ($B \ge 1$) and recognition batching ($\text{rec\_batch}=32..64$).
6. `blast_ocr/core/engines/__init__.py`:
   - Export `BatchedRapidOCREngine`.
7. `tests/test_batched_engine.py`:
   - Comprehensive unit and integration test suite testing all components, batching, GPU provider hierarchy fallback to CPU, latency SLA validation, and zero regression across existing 378+ tests.
8. Run `pytest tests/test_batched_engine.py -v` and full `pytest`.
9. Write `handoff.md` and report completion.

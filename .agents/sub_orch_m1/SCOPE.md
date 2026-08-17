# Scope: Milestone 1 — High-Throughput Batch Pipeline & GPU Acceleration

## Architecture
- **Zero-Disk In-Memory Batch Preprocessor (`blast_ocr/core/batch_preprocessor.py`)**:
  - Direct PDF/image rasterization into NumPy arrays in RAM (no temp disk files).
  - SIMD/vectorized image normalization and color conversion.
  - Aspect-ratio bucketer to group crops of similar aspect ratios into uniform batches for batch recognition inference, minimizing zero-padding overhead.
- **Hardware-Accelerated ONNX Runtime Session Manager (`blast_ocr/core/onnx_session.py`)**:
  - Dynamic Execution Provider fallback cascade: `TensorrtExecutionProvider` -> `CUDAExecutionProvider` -> `DmlExecutionProvider` (DirectML on Windows/WSL) -> `CPUExecutionProvider`.
  - Configurable ONNX SessionOptions: graph optimization level, intra/inter thread tuning, arena memory allocation.
- **Concurrent & Vectorized Tensor Decoders (`blast_ocr/core/tensor_decoder.py`)**:
  - Concurrent DBNet polygon extraction from segmentation probability maps and binary maps (using cv2 / polygon dilation / contour tracing).
  - Vectorized CTC greedy decoder for recognition logits batch output (argmax, duplicate collapsing, blank token filtering).
- **Batched Engine Interfaces & Implementations (`blast_ocr/core/engines/base.py`, `blast_ocr/core/engines/batched_rapidocr.py`)**:
  - Updates to `BaseOCREngine` / interfaces for batched processing contracts (`process_batch`, `predict_batch`, async/sync hooks).
  - `BatchedRapidOCREngine`: dynamic batching pipeline integrating preprocessor -> batched detection -> bucketing & batched recognition -> decoding, returning structured `OCRResult` or dict outputs matching existing schemas.
- **Verification & Test Suite (`tests/test_batched_engine.py`)**:
  - Exhaustive unit & integration test coverage for all preprocessor routines, provider fallbacks, CTC decoder edge cases, bucketing, and batched engine throughput / accuracy parity.

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | Zero-disk PDF & Image Rasterizer | In-memory stream rasterization directly into NumPy buffers without disk I/O | M1 | ORIGINAL_REQUEST |
| 2 | Aspect-Ratio Bucketer | Groups bounding box crops by aspect ratio for padded batch recognition | M1 | ORIGINAL_REQUEST |
| 3 | ONNX Provider Cascade | Automatic fallback TensorRT -> CUDA -> DirectML -> CPU with log diagnostics | M1 | ORIGINAL_REQUEST |
| 4 | Vectorized CTC Decoder | Batched CTC greedy decoding with blank filtering and score computation | M1 | ORIGINAL_REQUEST |
| 5 | DBNet Postprocessor | High-throughput polygon box extractor from DBNet detection probability maps | M1 | ORIGINAL_REQUEST |
| 6 | Batched RapidOCR Engine | Full pipeline dynamic batching engine inheriting from base engine | M1 | ORIGINAL_REQUEST |
| 7 | Full Milestone 1 Test Suite | Comprehensive pytest suite in `tests/test_batched_engine.py` | M1 | ORIGINAL_REQUEST |

## Code Layout
- `blast_ocr/core/batch_preprocessor.py`
- `blast_ocr/core/onnx_session.py`
- `blast_ocr/core/tensor_decoder.py`
- `blast_ocr/core/engines/base.py`
- `blast_ocr/core/engines/batched_rapidocr.py`
- `tests/test_batched_engine.py`

## Interface Contracts
- `BatchPreprocessor.rasterize_pdf(pdf_bytes: bytes, dpi: int = 200) -> List[np.ndarray]`
- `BatchPreprocessor.bucket_by_aspect_ratio(images: List[np.ndarray], target_height: int = 48) -> Dict[int, List[Tuple[int, np.ndarray]]]`
- `create_onnx_session(model_path: str, providers: Optional[List[str]] = None, session_options = None) -> ort.InferenceSession`
- `CTCDecoder.decode_greedy(logits: np.ndarray, vocab: List[str], blank_idx: int = 0) -> List[Tuple[str, float]]`
- `DBNetDecoder.extract_polygons(prob_map: np.ndarray, thresh: float = 0.3, box_thresh: float = 0.6, unclip_ratio: float = 1.5) -> List[np.ndarray]`
- `BatchedRapidOCREngine(BaseOCREngine).process_batch(images: List[Union[str, np.ndarray, bytes]], batch_size: int = 16) -> List[Any]`

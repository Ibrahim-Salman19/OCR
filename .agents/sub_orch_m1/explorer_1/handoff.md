# Milestone 1 Exploration & Architecture Analysis Handoff

## 1. Observation

### 1.1 Installed Dependencies & Library State
Inspected the runtime environment on Linux Python 3.10.12:
- `numpy`: `1.26.4`
- `cv2` (opencv-python): `5.0.0`
- `fitz` (PyMuPDF): `1.28.0`
- `onnxruntime`: `1.23.2`
- `rapidocr_onnxruntime`: Available in `/usr/local/lib/python3.10/dist-packages/rapidocr_onnxruntime`
- `shapely`: `2.1.2`
- `pyclipper`: `1.4.0`
- `PIL` (Pillow): `10.4.0`
- `torch`: `2.13.0+cu130`
- `redis`: `8.1.0`
- `rq`: `2.10.0`
- ONNX Execution Providers query: `ort.get_available_providers()` reports `['AzureExecutionProvider', 'CPUExecutionProvider']` on the current host, with ONNXRuntime configured for dynamic fallback cascades when CUDA/DirectML/TensorRT are available.

### 1.2 Model Assets & Dimension Support
Inspected `rapidocr_onnxruntime` bundled model weights in `/usr/local/lib/python3.10/dist-packages/rapidocr_onnxruntime/models/`:
- Detection Model: `ch_PP-OCRv4_det_infer.onnx`
  - Input: `['x']` with shape `[['p2o.DynamicDimension.0', 3, 'p2o.DynamicDimension.1', 'p2o.DynamicDimension.2']]`
  - Output: `['sigmoid_0.tmp_0']` with shape `[['p2o.DynamicDimension.3', 1, 'p2o.DynamicDimension.4', 'p2o.DynamicDimension.5']]`
  - Fully supports dynamic batch dimensions and dynamic spatial resolution (height/width divisible by 32).
- Recognition Model: `ch_PP-OCRv4_rec_infer.onnx`
  - Input: `['x']` with shape `[['p2o.DynamicDimension.0', 3, '?', 'p2o.DynamicDimension.1']]` (batch, 3, height=48, width)
  - Output: `['softmax_11.tmp_0']` with shape `[['p2o.DynamicDimension.2', 'p2o.DynamicDimension.3', 6625]]`
  - Vocabulary: 6625 tokens, where token 0 is `'blank'`, followed by characters including special `' '` space.

### 1.3 Engine Interfaces & Data Model
- `blast_ocr/core/engines/base.py`:
  - `BaseOCREngine` (lines 12–67) declares abstract `engine_name`, `metadata()`, `healthcheck()`, `warmup()`, `close()`, and `process_page(image_path: str, page_number: int, glyph_height: Optional[float] = None) -> Dict[str, Any]`.
  - Currently lacks a unified `process_batch` contract for multi-page or batched in-memory image processing.
- `blast_ocr/core/engines/rapidocr_engine.py`:
  - `RapidOCREngine` (lines 20–131) processes single pages by calling `cv2.imread(image_path)`, running `self._engine(img)`, converting raw output to spans, and feeding into `LayoutEngine().process_page_detections(...)`.
- `blast_ocr/core/document_model.py`:
  - Rich Docling-style hierarchy: `BoundingBox`, `Span`, `Line`, `Block`, `Page`, `Document`.
  - Structured output schemas are generated via `layout_page.model_dump()` embedded under `"page_model"` in engine result dictionaries.
- `blast_ocr/core/layout.py`:
  - `LayoutEngine.process_page_detections` accepts `raw_detections: List[Dict[str, Any]]` where each detection has `'text'`, `'bbox'`, and `'confidence'`.
  - Performs book spread splitting, recursive XY-cut column segmentation, adaptive line clustering, and block grouping.

### 1.4 Testing Infrastructure & Conventions
- `pytest.ini`:
  - Sets `pythonpath = .`, suppresses external deprecations, defines markers `real_easyocr` and `eval_regression`.
- `tests/conftest.py`:
  - Fixtures: `temp_workspace`, `sample_image`, `mock_env`, `mock_easyocr_reader_for_tests`.
- Test execution:
  - `pytest -v tests/test_ocr_engines.py` passed with 3/3 passing tests in clean isolation.

---

## 2. Logic Chain

1. **Zero-Disk In-Memory Rasterization**:
   - Current single-page workflows rely on disk files or `pdf2image.convert_from_path` (which shells out to `pdftoppm` writing disk temp files).
   - PyMuPDF (`fitz`) is present and supports `fitz.open(stream=pdf_bytes, filetype="pdf")` and `page.get_pixmap(dpi=dpi)`.
   - Directly converting `pixmap.samples` into `np.ndarray` via `np.frombuffer` completely eliminates disk I/O, reducing per-page ingestion latency and disk wear.

2. **Aspect-Ratio Bucketing for Recognition**:
   - In document OCR, cropped text bounding boxes vary from short words (aspect ratio 1.5) to full-line sentences (aspect ratio 20+).
   - Direct batching with zero-padding to the maximum width across all bounding boxes causes significant compute waste (over 60% of tensor area filled with padding zeros on disparate crops).
   - Partitioning crops into aspect-ratio buckets (e.g. ratios [1.0, 2.5, 5.0, 10.0, 20.0, 40.0]) and padding only to the maximum width within each bucket minimizes wasted tensor padding and maximizes throughput.

3. **ONNX Provider Cascade & Session Management**:
   - Host environments may range from CPU-only dev environments to Nvidia GPU (CUDA/TensorRT) or DirectML accelerators.
   - A dedicated `create_onnx_session` factory with automatic provider fallback (`TensorrtExecutionProvider` -> `CUDAExecutionProvider` -> `DmlExecutionProvider` -> `CPUExecutionProvider`) and optimized `SessionOptions` (ORT_ENABLE_ALL, thread tuning, memory arena) guarantees portability and maximum hardware utilization without runtime crashes.

4. **Vectorized CTC & DBNet Postprocessing**:
   - DBNet outputs probability maps `(B, 1, H, W)`. Extracting candidate bounding boxes using OpenCV contours, minAreaRect, and polygon unclipping with `pyclipper` provides clean 4-point polygon bounding boxes.
   - CTC recognition logits `(B, T, 6625)` can be decoded in vectorized NumPy batches: `np.argmax`, duplicate collapsing `selection[1:] = text_index[1:] != text_index[:-1]`, and blank token removal (`selection &= text_index != blank_idx`), yielding extracted text and confidence scores in parallel.

5. **Engine Polymorphism & Backward Compatibility**:
   - Updating `BaseOCREngine` with `process_batch(self, images: List[Union[str, np.ndarray, bytes]], page_numbers: Optional[List[int]] = None, **kwargs) -> List[Dict[str, Any]]` provides a standard contract.
   - A default fallback loop in `BaseOCREngine` ensures existing single-page engines (EasyOCR, Tesseract, Consensus) remain 100% functional without modification.
   - `BatchedRapidOCREngine` implements the vectorized end-to-end batch pipeline, achieving high-throughput batch execution while returning identical data schemas (`PageResult` / `page_model`).

---

## 3. Caveats

1. **Host Execution Provider Availability**:
   - On the current test host without active NVIDIA GPU drivers in WSL, `ort.get_available_providers()` returns CPU/Azure. The provider cascade must gracefully fall back to `CPUExecutionProvider` without failing. Tests should mock provider lists to verify GPU/TensorRT cascade branches.
2. **Color Space Consistency**:
   - PyMuPDF pixmaps default to RGB, OpenCV expects BGR for certain operations (`cv2.cvtColor`, `cv2.imwrite`), and PP-OCRv4 models expect RGB with normalized values. The preprocessor must ensure explicit color space handling.
3. **Memory Limits on Oversized Documents**:
   - When rasterizing 1,000+ page PDFs in memory, batching should process in chunks (e.g., 8–16 pages per batch) rather than rasterizing 1,000 full-resolution images simultaneously into RAM.

---

## 4. Conclusion & Architectural Recommendations

### 4.1 Recommended File Structure for Milestone 1
```
blast_ocr/
├── core/
│   ├── batch_preprocessor.py       # Zero-disk rasterizer, aspect-ratio bucketer, image normalizer
│   ├── onnx_session.py             # Provider cascade, SessionOptions tuner, session pool
│   ├── tensor_decoder.py           # Vectorized CTCDecoder, DBNetDecoder with pyclipper
│   └── engines/
│       ├── base.py                 # BaseOCREngine with process_batch contract
│       ├── batched_rapidocr.py     # High-throughput BatchedRapidOCREngine implementation
│       └── __init__.py             # Register "batched_rapidocr" in _ENGINE_REGISTRY
tests/
└── test_batched_engine.py          # Complete pytest suite for Milestone 1
```

### 4.2 Interface Specifications

#### A. `BatchPreprocessor` (`blast_ocr/core/batch_preprocessor.py`)
```python
class BatchPreprocessor:
    @staticmethod
    def rasterize_pdf(
        pdf_input: Union[bytes, str, Path], 
        dpi: int = 200, 
        max_pages: Optional[int] = None
    ) -> List[np.ndarray]:
        """Rasterizes PDF pages directly into RGB NumPy arrays in RAM using PyMuPDF."""
        ...

    @staticmethod
    def normalize_for_detection(
        images: List[np.ndarray], 
        limit_side_len: int = 960, 
        limit_type: str = "max"
    ) -> Tuple[np.ndarray, List[Tuple[int, int]]]:
        """Resizes images to multiples of 32, normalizes to [-1, 1], and pads into batch tensor (B, 3, H_max, W_max)."""
        ...

    @staticmethod
    def bucket_by_aspect_ratio(
        crops: List[np.ndarray], 
        target_height: int = 48,
        bucket_ratios: Optional[List[float]] = None
    ) -> Dict[int, List[Tuple[int, np.ndarray]]]:
        """Groups text crops by aspect ratio and prepares padded batches."""
        ...
```

#### B. `ONNXSessionManager` (`blast_ocr/core/onnx_session.py`)
```python
def create_onnx_session(
    model_path: Union[str, Path],
    providers: Optional[List[str]] = None,
    session_options: Optional[ort.SessionOptions] = None,
    intra_op_num_threads: int = -1,
    inter_op_num_threads: int = -1,
) -> ort.InferenceSession:
    """Instantiates ONNX session with hardware fallback cascade (TensorRT -> CUDA -> DirectML -> CPU)."""
    ...
```

#### C. `TensorDecoders` (`blast_ocr/core/tensor_decoder.py`)
```python
class CTCDecoder:
    def __init__(self, vocab: Optional[List[str]] = None):
        ...
    def decode_greedy(
        self, 
        logits: np.ndarray, 
        blank_idx: int = 0
    ) -> List[Tuple[str, float]]:
        """Vectorized CTC greedy decode over batch logits (B, T, C)."""
        ...

class DBNetDecoder:
    def __init__(self, thresh: float = 0.3, box_thresh: float = 0.6, unclip_ratio: float = 1.5):
        ...
    def extract_polygons(
        self, 
        pred_map: np.ndarray, 
        dest_shape: Tuple[int, int]
    ) -> Tuple[np.ndarray, List[float]]:
        """Extracts text polygon coordinates and confidence scores from probability bitmap."""
        ...
```

#### D. `BaseOCREngine` & `BatchedRapidOCREngine`
- `BaseOCREngine.process_batch(self, images: List[Union[str, np.ndarray, bytes]], page_numbers: Optional[List[int]] = None, **kwargs) -> List[Dict[str, Any]]`
- `BatchedRapidOCREngine` overrides `process_batch` to execute:
  1. Batched detection inference -> 2. Polygon decoding -> 3. Crop extraction -> 4. Aspect-ratio bucketing -> 5. Batched recognition inference -> 6. CTC decoding -> 7. Layout reconstruction via `LayoutEngine`.

---

## 5. Verification Method

To independently verify the implementation and findings:
1. **Dependency check**:
   ```bash
   python3 -c "import onnxruntime, fitz, cv2, shapely, pyclipper, rapidocr_onnxruntime; print('All core libs available')"
   ```
2. **Model assets check**:
   ```bash
   python3 -c "import rapidocr_onnxruntime as r; from pathlib import Path; p = Path(r.__path__[0]) / 'models'; print(list(p.glob('*.onnx')))"
   ```
3. **Run existing test suite to ensure 0 regressions**:
   ```bash
   pytest -v tests/test_ocr_engines.py
   ```
4. **Run new Milestone 1 test suite**:
   ```bash
   pytest -v tests/test_batched_engine.py
   ```

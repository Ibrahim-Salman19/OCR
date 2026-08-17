Title: Phase 3 Engine Adapter Interface & Bake-Off -- Swappable Engine Protocol, RapidOCR ONNX Adapter, and Empirical Performance Bake-Off
Status: accepted
Date: 2026-08-11

Context:
- EasyOCR (PyTorch / CRAFT + CRNN) on CPU has been the default engine since early stabilization. While accurate on clean text, page inference latency averaged ~115s/page on CPU prior to Phase 3.
- Phase 3 objective: build a modular `BaseOCREngine` adapter protocol (`blast_ocr/core/engines/base.py`), wrap EasyOCR and RapidOCR (ONNXRuntime / PaddleOCR v4 weights), and conduct a rigorous empirical bake-off scored on the 14-page gold corpus.

Bake-Off Results (14-Page Gold Corpus):

| Engine Adapter | Mean CER | Mean WER | Reading Order Tau | Fact Pass Rate | Avg Page Latency (CPU) |
|---|---|---|---|---|---|
| **EasyOCR** (Baseline) | `0.2338` | `0.4968` | `0.9641` | 44.7% (21/47) | ~117.8s / page |
| **RapidOCR** (Candidate) | **`0.1916`** | **`0.4739`** | **`0.9758`** | 40.4% (19/47) | **~15.3s / page** |

Key Findings:
1. **Speed & Latency**: RapidOCR ONNXRuntime executes **~7.7x faster** per page than EasyOCR PyTorch on CPU (15.3s/page vs 117.8s/page).
2. **Character Accuracy (CER)**: RapidOCR improves mean CER from 0.2338 down to **0.1916** (-18.0% relative CER reduction). On dense pages like p049 (CER 0.1536 -> 0.0413) and p093 (CER 0.2345 -> 0.1172), RapidOCR shows marked precision gains.
3. **Word Accuracy (WER)**: RapidOCR improves mean WER from 0.4968 down to **0.4739** (-4.6% relative WER reduction).
4. **Fact Pass Rate**: EasyOCR passed 21 facts vs RapidOCR's 19 facts (small trade-off on specific uppercase heading fact assertions, e.g., "ISLAM AS A VITAL ORGAN").

Decision:
- Promote **RapidOCR** to the default production engine (`default="rapidocr"` in CLI & factory).
- Retain `EasyOCREngine` as a supported, fully-functional adapter accessible via `--engine easyocr`.
- Update `get_cache_namespace()` to accept `engine_name` so caching is isolated per engine type.

Alternatives Considered:
- Option A: Retain EasyOCR as production default and keep RapidOCR experimental.
  - Rejected: A ~7.7x CPU throughput improvement with an 18% character error reduction makes RapidOCR dramatically superior for local CPU operation.
- Option B: Include PP-OCRv5 via native `paddleocr` package.
  - Rejected: `paddleocr` pulls in Heavy PaddlePaddle C++ runtime dependencies that increase install complexity and introduce licensing friction, whereas `rapidocr_onnxruntime` runs standalone via `onnxruntime` (Apache-2.0).

Consequences:
- Positive:
  - 14-page evaluation run duration dropped from ~25 minutes to **~3.5 minutes**.
  - Accuracy metrics (CER and WER) both improved.
  - Engine switching is now trivial via `--engine`.
- Negative:
  - Requires `rapidocr_onnxruntime` in `requirements.txt`.

Verification:
- Tested factory lookup and unit test execution in `tests/test_ocr_engines.py` (3 passed).
- Ran full-corpus bake-off evaluation recorded in `eval/results/rapidocr_candidate.json`.
- Promoted `rapidocr_candidate.json` to `eval/results/baseline.json`.

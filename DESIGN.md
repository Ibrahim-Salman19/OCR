# B.L.A.S.T. Protocol Design Document
# Version: 3.0 (Mastery Edition)

## 🏗️ Architectural Overview

The B.L.A.S.T. (Batch Large-Scale Automated Scanned Text) system is designed for **deterministic, high-fidelity OCR automation**. It prioritizes stability and observability over raw speed, ensuring that large-scale digitization tasks (1000+ pages) are handled with zero data loss.

### Core Pillars
1. **Sovereignty**: Self-correcting logic (Reflexion) that minimizes human intervention.
2. **Forensics**: Advanced image restoration (Denoising/CLAHE) to recover text from low-quality scans.
3. **Observability**: Real-time telemetry tracking memory, fidelity, and throughput.
4. **Security**: Integrated PII redaction and secure temporary directory management.

## 🛠️ System Components

### 1. Forensic Restoration Layer (`restoration.py`)
- **Gaussian-Adaptive Denoising**: Cleans sensor noise from digital captures.
- **CLAHE (Contrast Limited Adaptive Histogram Equalization)**: Normalizes contrast per-tile to handle uneven lighting.
- **Reflexion Mode**: Ultra-high contrast sharpening triggered by low-confidence OCR results.

### 2. The Agentic Pipeline (`pipeline.py`)
- **Reflexion Loop**: A recursive "Double-Pass" retry mechanism.
- **Intermediate Checkpointing**: Row-level database persistence after every page.
- **Memory Guardrails**: Aggressive `gc.collect()` and batch-chunking to stay within 2GB RAM limits.

### 3. Intelligent Script Router (`router.py`)
- **Script Detection**: Uses `langdetect` to identify document language before engine initialization.
- **Dynamic Swapping**: Adjusts OCR model languages on-the-fly.

### 4. Mission Control Dashboard (`web_app.py`)
- **Async Execution**: Non-blocking background threads for long-running jobs.
- **Live Intelligence Stream**: Real-time polling of processed text.
- **System Health**: Telemetry visualizations via Streamlit metrics and charts.

## 📈 Performance Targets
- **Accuracy**: >98.5% on standard typeset documents.
- **Stability**: 100% success rate on 1000+ page PDF streams.
- **Response**: <2s UI polling latency.

--
*Validated by the Agentic Mastery Protocol.*

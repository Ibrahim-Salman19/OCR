# 🚀 Deployment Guide

B.L.A.S.T. is designed to be portable across Windows, Linux, and Cloud environments. Follow these guides to move from development to production.

## 💻 Windows Production Setup

1.  **Dependencies**:
    -   Install [Poppler](https://github.com/oschwartz10612/poppler-windows/releases/). Ensure the `bin/` folder is in your System Path.
    -   Install [Visual C++ Redistributable 2015-2022](https://aka.ms/vs/17/release/vc_redist.x64.exe).

2.  **GPU Acceleration**:
    -   Update PyTorch for CUDA support:
        ```bash
        pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118
        ```
    -   Verify with `dll_check.py` or `python -c "import torch; print(torch.cuda.is_available())"`.

3.  **Process Management**:
    -   Use `nssm` (Non-Sucking Service Manager) to run the Streamlit dashboard as a background Windows service.

---

## 🐳 Docker Deployment (Linux)

For cloud/linux deployment, use the provided Docker integration (or build your own).

### 1. The Base Image
We recommend `python:3.9-slim-bullseye`.

For Streamlit Community Cloud, pin Python with a root-level `runtime.txt`:

```text
python-3.11
```

This avoids Python 3.14 build-toolchain issues for packages that may not yet publish cp314 wheels in all environments.

### 2. Runtime Dependencies
```dockerfile
RUN apt-get update && apt-get install -y \
    libgl1 \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*
```

Notes:
- Avoid pinning `libglib2.0-0` explicitly on mixed Debian images (bullseye/trixie) to prevent `libglib2.0-0` vs `libglib2.0-0t64` conflicts.
- Tesseract is optional in this project and is not required for the default EasyOCR pipeline.

### 3. Execution
```bash
docker build -t blast-ocr .
docker run -p 8501:8501 -v /data:/app/data blast-ocr
```

---

## 🗺️ Environment Variables

Configure these in a `.env` file for production safety.

| Variable | Recommendation | Description |
| :--- | :--- | :--- |
| `BLAST_OCR_MAX_WORKERS` | `2` (CPU) or `1` (GPU) | Limit concurrency to balance RAM vs Speed. |
| `BLAST_OCR_OCR_GPU` | `True` | Set to `True` only if CUDA is verified. |
| `BLAST_OCR_EASYOCR_DOWNLOAD_ENABLED` | `0` after first successful bootstrap | Set `0/false/off` to disable runtime model downloads once models are preloaded. |
| `BLAST_OCR_EASYOCR_MODEL_DIR` | `/tmp/.EasyOCR/model` on cloud Linux | Explicit EasyOCR model directory override for writable, deterministic model cache location. |
| `DATABASE_URL` | `sqlite:///data/blast.db` | Persistent database path. |
| `LOG_LEVEL` | `INFO` | Use `DEBUG` only for forensic troubleshooting. |

## ☁️ Streamlit Community Cloud App Settings

- Main file path: `streamlit_app.py`
- Python version: root `runtime.txt` (`python-3.11`)
- Pip dependencies: root `requirements.txt`
- System packages: root `packages.txt`

Using `streamlit_app.py` as the main file avoids startup redirect/entrypoint misconfiguration and delegates cleanly into `run_gui.py`.

Reliability defaults for cloud:
- Set `BLAST_OCR_MAX_WORKERS=1`
- Set `BLAST_OCR_DATABASE_URL=sqlite:////tmp/blast_ocr.db`
- Keep `BLAST_OCR_EASYOCR_MODEL_DIR=/tmp/.EasyOCR/model`
- For first deployment use `BLAST_OCR_EASYOCR_DOWNLOAD_ENABLED=1`, then switch to `0`

## 🔗 Next Steps
-   [Troubleshooting](TROUBLESHOOTING.md)
-   [Introduction](INTRODUCTION.md)

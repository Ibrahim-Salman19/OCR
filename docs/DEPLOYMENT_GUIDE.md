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

### 2. Runtime Dependencies
```dockerfile
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 \
    poppler-utils \
    tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*
```

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
| `DATABASE_URL` | `sqlite:///data/blast.db` | Persistent database path. |
| `LOG_LEVEL` | `INFO` | Use `DEBUG` only for forensic troubleshooting. |

## 🔗 Next Steps
-   [Troubleshooting](TROUBLESHOOTING.md)
-   [Introduction](INTRODUCTION.md)

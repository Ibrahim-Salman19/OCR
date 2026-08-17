# syntax=docker/dockerfile:1
#
# B.L.A.S.T. OCR -- production container image.
#
# Multi-stage: build wheels in a full build environment, install into a slim
# runtime image so the final image doesn't carry compilers/dev headers.
# Runs as a non-root user with a read-only-friendly layout (writable state
# confined to /data, mounted as a volume) per EXECUTION_PLAN.md Phase 4
# ("Hostile document security boundary" -> sandboxed OCR workers: non-root
# process, minimal writable surface).

FROM python:3.11-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libxml2-dev \
        libxslt-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build
COPY requirements.txt requirements-production.txt pyproject.toml ./
# requirements.txt first (the CRITICAL STABILITY CORE pins, including the
# streamlit==1.32.0 protobuf<5 constraint), then requirements-production.txt
# (queue/storage/observability) -- deliberately excludes
# opentelemetry-exporter-otlp to avoid the protobuf conflict documented in
# both files and docs/adr/0013. The container image runs the full
# docker-compose profile (Redis queue, MinIO storage, Prometheus metrics), so
# it needs the production extras installed, unlike the minimal
# `pip install -r requirements.txt` path Streamlit Community Cloud uses.
# CPU-only torch FIRST, via PyTorch's own CPU wheel index: easyocr depends on
# torch without pinning a CPU/GPU variant, so a plain `pip install` on Linux
# resolves the default CUDA-enabled build -- multiple gigabytes of nvidia_*
# wheels (nvidia_cublas alone is 423MB) pulled into a container image that
# defaults to CPU-only RapidOCR and only uses EasyOCR as a fallback engine.
# Installing the CPU wheel first satisfies easyocr's torch dependency without
# pip ever resolving the CUDA variant.
ENV PIP_DEFAULT_TIMEOUT=100 \
    PIP_RETRIES=5
RUN pip install --no-cache-dir --prefix=/install \
        --index-url https://download.pytorch.org/whl/cpu \
        torch \
    && pip install --no-cache-dir --prefix=/install \
        -r requirements.txt \
        -r requirements-production.txt


FROM python:3.11-slim AS runtime

# Runtime-only system dependencies: poppler-utils (pdf2image), libgl1 (opencv
# needs libGL even in "headless" builds for some codec paths), fonts for
# DOCX/EPUB rendering correctness.
RUN apt-get update && apt-get install -y --no-install-recommends \
        poppler-utils \
        libgl1 \
        libglib2.0-0 \
        libgomp1 \
        tesseract-ocr \
        libxml2 \
        libxslt1.1 \
        curl \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 1000 blast \
    && useradd --uid 1000 --gid blast --shell /bin/bash --create-home blast

COPY --from=builder /install /usr/local

WORKDIR /app
COPY --chown=blast:blast . .

# Writable state lives entirely under /data -- everything else in the image
# can be mounted read-only in a hardened deployment (`docker run --read-only
# -v blast-data:/data ...`).
ENV BLAST_OCR_OUTPUT_DIR=/data/output \
    BLAST_OCR_LOG_DIR=/data/logs \
    BLAST_OCR_DATABASE_URL=sqlite:////data/blast_ocr.db \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

RUN mkdir -p /data/output /data/logs && chown -R blast:blast /data

USER blast

EXPOSE 8501 9464

HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8501/_stcore/health || exit 1

ENTRYPOINT ["streamlit", "run", "blast_ocr/ui/web_app.py", \
            "--server.address=0.0.0.0", "--server.port=8501", \
            "--server.headless=true"]

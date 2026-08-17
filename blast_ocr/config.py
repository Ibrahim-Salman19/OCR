import logging
import os
import sys
import tempfile
from typing import List, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _detect_poppler_path() -> Optional[str]:
    """
    Auto-detect the correct Poppler path based on the operating system.
    - On Linux (Streamlit Cloud): Poppler is installed system-wide via packages.txt, so return None.
    - On Windows (local dev): Use the bundled poppler folder.
    """
    if sys.platform == "win32":
        local_path = os.path.join(
            os.path.dirname(__file__), "..", "poppler-25.12.0", "Library", "bin"
        )
        local_path = os.path.normpath(local_path)
        if os.path.isdir(local_path):
            return local_path
    # On Linux/Mac, poppler is on the system PATH — return None to use it automatically
    return None


class OCRConfig(BaseSettings):
    """Type-safe configuration with validation"""

    # OCR Engine
    ocr_engine: str = Field(default="rapidocr", description="Engine choice: rapidocr, batched_rapidocr, or easyocr")
    ocr_languages: List[str] = Field(
        default_factory=lambda: ["en"], description="Languages to detect"
    )
    ocr_gpu: bool = Field(default=False, description="Use GPU acceleration")
    ocr_batch_size: int = Field(default=8, description="Pages to process in parallel")
    ocr_execution_provider: str = Field(
        default="auto",
        description="Execution provider: auto, cuda, tensorrt, directml, cpu",
    )
    ocr_gpu_device_id: int = Field(default=0, description="GPU device ID")
    ocr_det_batch_size: int = Field(default=4, description="Detection batch size")
    ocr_rec_batch_size: int = Field(default=32, description="Recognition batch size")
    ocr_det_limit_side_len: int = Field(default=960, description="Detection max side length")
    ocr_det_limit_type: str = Field(default="max", description="Detection limit type: max or min")
    ocr_enable_fp16: bool = Field(default=True, description="Enable FP16 optimization for GPU")
    enable_tier0_routing: bool = Field(default=True, description="Enable native text extraction for born-digital PDFs")
    enable_book_intelligence: bool = Field(default=True, description="Enable header/footer stripping and dehyphenation")

    # Performance
    max_workers: int = Field(default=2, description="Thread pool size")
    timeout_per_page: int = Field(default=60, description="Seconds before timeout")

    # Storage
    database_url: str = Field(
        default_factory=lambda: (
            f"sqlite:///{os.path.join(tempfile.gettempdir(), 'blast_ocr.db')}"
        )
    )
    output_format: str = Field(
        default="txt", description="Output format: txt, json, pptx"
    )

    # Paths
    data_dir: str = Field(default="data/pages")
    output_dir: str = Field(
        default_factory=lambda: os.path.join(tempfile.gettempdir(), "blast_output")
    )
    log_dir: str = Field(
        default_factory=lambda: os.path.join(tempfile.gettempdir(), "logs")
    )
    poppler_path: Optional[str] = Field(
        default_factory=_detect_poppler_path,
        description="Path to poppler bin folder (auto-detected)",
    )

    # Quality Control
    min_confidence: float = Field(
        default=0.6, description="Minimum confidence to accept"
    )
    enable_spellcheck: bool = Field(default=True)

    # Self-Healing
    max_retries: int = Field(default=3)
    retry_backoff: int = Field(default=2)
    enable_fallback: bool = Field(default=True)
    secure_mode: bool = Field(default=False, description="Enable PII redaction")

    # Preprocessing (Added for Phase 4 Fix)
    denoise_level: int = Field(default=0, description="Denoising strength (0-20)")
    contrast_boost: float = Field(
        default=1.0, description="Contrast multiplier (1.0-3.0)"
    )
    auto_deskew: bool = Field(default=True, description="Enable auto-deskewing")
    enable_dewarp: bool = Field(default=False, description="Enable book spine curvature dewarping")

    # Durable Queue (Execution Plan v2, Phase 5/8) -- "sync" (default) requires no
    # extra infra and matches all prior behavior; "redis" enables out-of-process,
    # durable job execution via blast_ocr.queue (RQ), see docs/adr/0010.
    queue_backend: str = Field(default="sync", description="Job execution backend: sync or redis")
    redis_url: str = Field(default="redis://localhost:6379/0", description="Redis connection URL for the queue backend")
    queue_job_timeout: int = Field(default=1800, description="Max seconds an RQ job may run before being killed")

    # Object Storage (Execution Plan v2, Phase 8) -- "local" (default) requires no
    # extra infra; "s3" enables MinIO/S3-compatible artifact storage via
    # blast_ocr.storage.object_store.
    storage_backend: str = Field(default="local", description="Artifact storage backend: local or s3")
    s3_endpoint_url: Optional[str] = Field(default=None, description="S3/MinIO endpoint URL (None = real AWS)")
    s3_bucket: str = Field(default="blast-ocr-artifacts", description="Bucket for job outputs/originals")
    s3_access_key: Optional[str] = Field(default=None, description="S3/MinIO access key")
    s3_secret_key: Optional[str] = Field(default=None, description="S3/MinIO secret key")

    # Streaming & Caching (Milestone 3 / R3)
    streaming_chunk_size: int = Field(default=8, description="Pages per streaming window chunk (K=8..16)")
    cache_l1_capacity: int = Field(default=100, description="L1 in-memory LRU cache capacity")
    storage_concurrency: int = Field(default=4, description="Concurrency for background object uploader")
    s3_multipart_threshold_mb: int = Field(default=8, description="Multipart upload threshold in MB")

    # Observability (Execution Plan v2, Phase 9)
    otel_exporter: str = Field(default="console", description="OpenTelemetry exporter: console or otlp")
    otel_otlp_endpoint: Optional[str] = Field(default=None, description="OTLP collector endpoint (required if otel_exporter=otlp)")
    prometheus_port: int = Field(default=9464, description="Port for the /metrics Prometheus endpoint")

    @field_validator("queue_backend")
    @classmethod
    def check_queue_backend(cls, v):
        name = v.lower().strip()
        if name not in ("sync", "redis"):
            raise ValueError(f"queue_backend must be 'sync' or 'redis', got '{v}'")
        return name

    @field_validator("storage_backend")
    @classmethod
    def check_storage_backend(cls, v):
        name = v.lower().strip()
        if name not in ("local", "s3"):
            raise ValueError(f"storage_backend must be 'local' or 's3', got '{v}'")
        return name

    @field_validator("otel_exporter")
    @classmethod
    def check_otel_exporter(cls, v):
        name = v.lower().strip()
        if name not in ("console", "otlp", "none"):
            raise ValueError(f"otel_exporter must be 'console', 'otlp', or 'none', got '{v}'")
        return name

    @field_validator("max_workers", "timeout_per_page")
    @classmethod
    def check_positive(cls, v):
        if v <= 0:
            raise ValueError("Must be > 0")
        return v

    @field_validator("min_confidence")
    @classmethod
    def check_conf(cls, v):
        if not (0.0 <= v <= 1.0):
            raise ValueError("Must be 0-1")
        return v

    @field_validator("contrast_boost")
    @classmethod
    def check_contrast(cls, v):
        if not (1.0 <= v <= 3.0):
            raise ValueError("Must be 1-3")
        return v

    @field_validator("ocr_engine")
    @classmethod
    def check_engine(cls, v):
        name = v.lower().strip()
        allowed = ("rapidocr", "batched_rapidocr", "easyocr", "tesseract", "ensemble")
        if name not in allowed:
            raise ValueError(f"ocr_engine must be one of {allowed}, got '{v}'")
        return name

    @field_validator("ocr_languages")
    @classmethod
    def check_langs(cls, v):
        if not v:
            raise ValueError("Cannot be empty")
        return v

    model_config = SettingsConfigDict(
        env_file=".env", env_prefix="BLAST_OCR_", extra="allow"
    )


def _load_config() -> OCRConfig:
    """Load configuration with safe individual key recovery for malformed env overrides."""
    try:
        return OCRConfig()
    except Exception as err:
        blast_keys = sorted([k for k in os.environ if k.startswith("BLAST_OCR_")])
        if not blast_keys:
            raise

        bad_keys = []
        for key in blast_keys:
            saved_val = os.environ.pop(key)
            try:
                OCRConfig()
                bad_keys.append(key)
            except Exception:
                os.environ[key] = saved_val

        if bad_keys:
            logging.getLogger(__name__).warning(
                "Removed invalid environment variable overrides: %s (error: %s)",
                ", ".join(bad_keys),
                err,
            )
            return OCRConfig()
        raise err


# Load config
config = _load_config()


def get_settings() -> OCRConfig:
    """Retrieve the global configuration instance."""
    return config

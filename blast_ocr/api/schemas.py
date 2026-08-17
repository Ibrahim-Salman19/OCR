"""
blast_ocr.api.schemas

Pydantic V2 request and response schemas for B.L.A.S.T. Production REST API,
including priority job dispatch, multi-worker swarm fleet metrics, and DLQ inspection.
"""

from typing import List, Dict, Optional, Any, Union
from pydantic import BaseModel, Field
from datetime import datetime


class JobCreateRequest(BaseModel):
    source_path: Optional[str] = Field(None, description="Path to input document (PDF, PPTX, image, directory)")
    output_dir: Optional[str] = Field(None, description="Directory where output artifacts will be saved")
    ocr_engine: str = Field("rapidocr", description="Target OCR engine: rapidocr, easyocr, tesseract, ensemble")
    priority: str = Field("default", description="Priority tier: high, default, low")
    max_retries: int = Field(3, ge=0, le=10, description="Max retry attempts for transient failures")
    auto_deskew: bool = Field(True, description="Enable automatic image deskewing")
    denoise_level: int = Field(0, description="Denoising filter level (0-20)")
    contrast_boost: float = Field(1.0, description="Contrast enhancement boost factor")
    enable_dewarp: bool = Field(False, description="Enable book spine curvature dewarping")
    enable_tier0_routing: bool = Field(True, description="Enable native PDF vector text fast-path routing")
    enable_book_intelligence: bool = Field(True, description="Enable running header/footer strip & dehyphenation")
    secure_mode: bool = Field(False, description="Enable enterprise PII redaction")
    max_workers: int = Field(2, description="Number of parallel OCR worker threads")
    formats: List[str] = Field(default_factory=lambda: ["markdown", "docx", "pdf", "txt", "epub", "json"])


class JobResponse(BaseModel):
    job_id: int
    status: str
    source_path: str
    priority: Optional[str] = "default"
    retry_count: Optional[int] = 0
    rq_job_id: Optional[str] = None
    total_pages: Optional[int] = None
    created_at: Optional[datetime] = None
    message: Optional[str] = None


class JobStatusResponse(BaseModel):
    job_id: int
    status: str
    source_file: str
    total_pages: int
    processed_pages: int
    progress_percentage: float
    average_confidence: float
    processing_time_sec: float
    priority: Optional[str] = "default"
    retry_count: Optional[int] = 0
    max_retries: Optional[int] = 3
    worker_id: Optional[str] = None
    queue_name: Optional[str] = None
    error_message: Optional[str] = None


class JobResultsResponse(BaseModel):
    job_id: int
    status: str
    source_file: str
    total_pages: int
    generated_files: Dict[str, Optional[str]]
    metadata: Dict[str, Any]
    summary_text: Optional[str] = None


class PageDetailResponse(BaseModel):
    page_number: int
    text: str
    confidence: float
    bbox_count: int
    processing_time: float
    engine_used: str
    details: List[Dict[str, Any]] = Field(default_factory=list)


class SystemHealthResponse(BaseModel):
    status: str
    database: str
    storage_backend: str
    queue_backend: str
    registered_engines: List[str]
    memory_used_mb: float
    timestamp: datetime


class SystemConfigResponse(BaseModel):
    app_version: str = "3.0.0"
    ocr_engine_default: str
    available_engines: List[str]
    max_workers: int
    log_dir: str
    storage_backend: str
    queue_backend: str


class WorkerInfoResponse(BaseModel):
    worker_id: str
    hostname: Optional[str] = "localhost"
    pid: Optional[int] = None
    status: str = "idle"  # idle, busy, draining, offline
    current_job_id: Optional[Union[int, str]] = None
    current_page: Optional[int] = None
    total_pages: Optional[int] = None
    memory_rss_mb: float = 0.0
    cpu_percent: float = 0.0
    last_heartbeat: Optional[float] = None
    uptime_sec: Optional[int] = None
    queues: Optional[List[str]] = Field(default_factory=list)
    jobs_processed_total: Optional[int] = 0
    jobs_failed_total: Optional[int] = 0


class SwarmWorkersResponse(BaseModel):
    workers: List[WorkerInfoResponse]
    total_active_workers: int
    timestamp: str


class QueueDepthResponse(BaseModel):
    queues: Dict[str, int]
    total_pending_jobs: int
    timestamp: str


class DLQJobResponse(BaseModel):
    job_id: Union[int, str]
    source_file: Optional[str] = None
    priority: Optional[str] = "default"
    retry_count: int = 0
    max_retries: int = 3
    dlq_at: Optional[str] = None
    dlq_reason: Optional[str] = None


class DLQInspectionResponse(BaseModel):
    dlq_jobs: List[DLQJobResponse]
    total_dlq_count: int


class JobRetryResponse(BaseModel):
    job_id: int
    status: str
    priority: str
    retry_count: int = 0
    message: str

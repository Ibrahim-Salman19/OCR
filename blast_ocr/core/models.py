"""
blast_ocr.core.models

Typed domain models for B.L.A.S.T. OCR production pipeline architecture.
Implements frozen dataclasses and Pydantic models for thread safety,
explicit configuration isolation, and auditable data flow.
"""

from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Dict, List, Optional, Any
from enum import Enum


class RouteDecision(str, Enum):
    PASS_NATIVE = "pass_native"
    OCR_REQUIRED = "ocr_required"
    HYBRID_REQUIRED = "hybrid_required"
    REJECT_PAGE = "reject_page"


class JobState(str, Enum):
    RECEIVED = "received"
    VALIDATING = "validating"
    QUEUED = "queued"
    PROCESSING = "processing"
    POST_PROCESSING = "post_processing"
    EXPORTING = "exporting"
    SUCCEEDED = "succeeded"
    SUCCEEDED_WITH_WARNINGS = "succeeded_with_warnings"
    PARTIAL_FAILURE = "partial_failure"
    FAILED = "failed"
    CANCELLED = "cancelled"
    QUARANTINED = "quarantined"
    TIMED_OUT = "timed_out"


@dataclass(frozen=True)
class JobConfig:
    """Immutable per-job configuration preventing cross-job state leakage."""
    ocr_engine: str = "rapidocr"
    enable_tier0_routing: bool = True
    enable_book_intelligence: bool = True
    language: str = "en"
    ocr_languages: List[str] = field(default_factory=lambda: ["en"])
    secure_mode: bool = False
    denoise_level: int = 0
    contrast_boost: float = 1.0
    auto_deskew: bool = True
    enable_dewarp: bool = False
    max_workers: int = 2
    timeout_per_page: int = 60
    min_confidence: float = 0.6
    ocr_gpu: bool = False
    ocr_batch_size: int = 8
    output_dir: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "JobConfig":
        valid_keys = {f.name for f in fields(cls)}
        filtered = {k: v for k, v in data.items() if k in valid_keys}
        return cls(**filtered)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ocr_engine": self.ocr_engine,
            "enable_tier0_routing": self.enable_tier0_routing,
            "enable_book_intelligence": self.enable_book_intelligence,
            "language": self.language,
            "ocr_languages": self.ocr_languages,
            "secure_mode": self.secure_mode,
            "denoise_level": self.denoise_level,
            "contrast_boost": self.contrast_boost,
            "auto_deskew": self.auto_deskew,
            "max_workers": self.max_workers,
            "timeout_per_page": self.timeout_per_page,
            "min_confidence": self.min_confidence,
            "ocr_gpu": self.ocr_gpu,
            "ocr_batch_size": self.ocr_batch_size,
            "output_dir": self.output_dir,
        }


@dataclass(frozen=True)
class NativeTextQuality:
    """Detailed quality classifier for native text layer extraction."""
    character_count: int
    printable_ratio: float
    unicode_replacement_ratio: float
    alphanumeric_ratio: float
    whitespace_sanity: float
    duplicate_ratio: float
    quality_score: float
    decision: RouteDecision


@dataclass
class PageResult:
    """Page extraction result payload."""
    page_number: int
    extracted_text: str
    confidence_score: float
    processing_time_sec: float
    engine_used: str
    route_used: str = "ocr"
    error_message: Optional[str] = None
    page_model_dict: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "page": self.page_number,
            "text": self.extracted_text,
            "confidence": self.confidence_score,
            "processing_time": self.processing_time_sec,
            "engine": self.engine_used,
            "route": self.route_used,
            "error": self.error_message,
            "page_model": self.page_model_dict,
        }


@dataclass(frozen=True)
class ExportBundle:
    """Typed container for generated output artifacts."""
    markdown_path: Optional[Path] = None
    docx_path: Optional[Path] = None
    txt_path: Optional[Path] = None
    epub_path: Optional[Path] = None
    pdf_path: Optional[Path] = None
    manifest_path: Optional[Path] = None

    def to_dict(self) -> Dict[str, Optional[str]]:
        return {
            "md": str(self.markdown_path) if self.markdown_path else None,
            "docx": str(self.docx_path) if self.docx_path else None,
            "txt": str(self.txt_path) if self.txt_path else None,
            "epub": str(self.epub_path) if self.epub_path else None,
            "pdf": str(self.pdf_path) if self.pdf_path else None,
            "manifest": str(self.manifest_path) if self.manifest_path else None,
        }

    def __iter__(self):
        yield str(self.markdown_path) if self.markdown_path else ""
        yield str(self.docx_path) if self.docx_path else None

    def __len__(self):
        return 2

    def __getitem__(self, idx: int):
        if idx == 0:
            return str(self.markdown_path) if self.markdown_path else ""
        elif idx == 1:
            return str(self.docx_path) if self.docx_path else None
        elif idx == 2:
            return str(self.pdf_path) if self.pdf_path else None
        elif idx == 3:
            return str(self.epub_path) if self.epub_path else None
        elif idx == 4:
            return str(self.txt_path) if self.txt_path else None
        raise IndexError("ExportBundle tuple indexing supports 0 (md), 1 (docx), 2 (pdf), 3 (epub), 4 (txt)")


@dataclass
class ProcessingWarning:
    page_number: int
    code: str
    message: str


class ProcessingError(Exception):
    """Base domain exception for job processing failures."""
    def __init__(self, message: str, code: str = "PROCESSING_ERROR", retryable: bool = False):
        super().__init__(message)
        self.code = code
        self.retryable = retryable

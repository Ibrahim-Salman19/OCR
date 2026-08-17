"""
blast_ocr.core.manifest

Auditable Provenance & Manifest Schema v1 (Phase 7 of Execution Plan v2).
Generates structured JSON manifest containing input hashes, pipeline git commit,
OCR engine metadata, routing metrics, timings, and output artifact hashes.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
import json
import os
from datetime import datetime, timezone


@dataclass
class ManifestOutputArtifact:
    artifact_type: str
    filepath: str
    sha256_hash: str
    size_bytes: int


@dataclass
class RunManifest:
    schema_version: str = "1.0"
    job_id: Optional[int] = None
    input_filename: str = ""
    input_sha256: str = ""
    input_size_bytes: int = 0
    input_page_count: int = 0
    pipeline_version: str = "1.0.0-SOVEREIGN"
    git_commit: str = "unknown"
    ocr_engine: str = "rapidocr"
    ocr_backend: str = "onnxruntime"
    ocr_models: List[str] = field(default_factory=lambda: ["ch_PP-OCRv3_det", "ch_PP-OCRv3_rec"])
    native_pages_count: int = 0
    ocr_pages_count: int = 0
    peak_memory_mb: float = 0.0
    avg_page_time_sec: float = 0.0
    avg_confidence: float = 0.0
    velocity_pages_per_sec: float = 0.0
    timestamp_utc: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    warnings: List[str] = field(default_factory=list)
    outputs: List[ManifestOutputArtifact] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "job_id": self.job_id,
            "input": {
                "filename": self.input_filename,
                "sha256": self.input_sha256,
                "size_bytes": self.input_size_bytes,
                "page_count": self.input_page_count,
            },
            "pipeline": {
                "version": self.pipeline_version,
                "git_commit": self.git_commit,
            },
            "ocr": {
                "engine": self.ocr_engine,
                "backend": self.ocr_backend,
                "models": self.ocr_models,
            },
            "routing": {
                "native_pages": self.native_pages_count,
                "ocr_pages": self.ocr_pages_count,
            },
            "metrics": {
                "peak_memory_mb": round(self.peak_memory_mb, 2),
                "avg_page_time_sec": round(self.avg_page_time_sec, 3),
                "avg_confidence": round(self.avg_confidence, 4),
                "velocity_pages_per_sec": round(self.velocity_pages_per_sec, 2),
            },
            "timestamp_utc": self.timestamp_utc,
            "warnings": self.warnings,
            "outputs": [
                {
                    "type": o.artifact_type,
                    "filepath": o.filepath,
                    "sha256": o.sha256_hash,
                    "size_bytes": o.size_bytes,
                }
                for o in self.outputs
            ],
        }

    def save(self, output_path: str) -> str:
        data = self.to_dict()
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        return output_path

try:
    from pydantic_settings import BaseSettings, SettingsConfigDict
except ImportError:
    # Fallback for Pydantic V1 or V2 without pydantic-settings
    from pydantic import BaseSettings
    SettingsConfigDict = None

from pydantic import Field
from typing import List, Optional
import os
import sys

def _detect_poppler_path() -> Optional[str]:
    """
    Auto-detect the correct Poppler path based on the operating system.
    - On Linux (Streamlit Cloud): Poppler is installed system-wide via packages.txt, so return None.
    - On Windows (local dev): Use the bundled poppler folder.
    """
    if sys.platform == "win32":
        local_path = os.path.join(os.path.dirname(__file__), "..", "poppler-25.12.0", "Library", "bin")
        local_path = os.path.normpath(local_path)
        if os.path.isdir(local_path):
            return local_path
    # On Linux/Mac, poppler is on the system PATH — return None to use it automatically
    return None

class OCRConfig(BaseSettings):
    """Type-safe configuration with validation"""
    
    # OCR Engine
    ocr_languages: List[str] = Field(default=['en'], description="Languages to detect")
    ocr_gpu: bool = Field(default=False, description="Use GPU acceleration")
    ocr_batch_size: int = Field(default=8, description="Pages to process in parallel")
    
    # Performance
    max_workers: int = Field(default=2, description="Thread pool size")
    timeout_per_page: int = Field(default=60, description="Seconds before timeout")
    
    # Storage
    database_url: str = Field(default='sqlite:////tmp/blast_ocr.db')
    output_format: str = Field(default='txt', description="Output format: txt, json, pptx")
    
    # Paths
    data_dir: str = Field(default='data/pages')
    output_dir: str = Field(default='/tmp/blast_output')
    log_dir: str = Field(default='/tmp/logs')
    poppler_path: Optional[str] = Field(
        default_factory=_detect_poppler_path,
        description="Path to poppler bin folder (auto-detected)"
    )
    
    # Quality Control
    min_confidence: float = Field(default=0.6, description="Minimum confidence to accept")
    enable_spellcheck: bool = Field(default=True)
    
    # Self-Healing
    max_retries: int = Field(default=3)
    retry_backoff: int = Field(default=2)
    enable_fallback: bool = Field(default=True)
    
    # Preprocessing (Added for Phase 4 Fix)
    denoise_level: int = Field(default=0, description="Denoising strength (0-20)")
    contrast_boost: float = Field(default=1.0, description="Contrast multiplier (1.0-3.0)")
    auto_deskew: bool = Field(default=True, description="Enable auto-deskewing")
    
    if SettingsConfigDict:
        model_config = SettingsConfigDict(
            env_file='.env',
            env_prefix='BLAST_OCR_'
        )
    else:
        class Config:
            env_file = '.env'
            env_prefix = 'BLAST_OCR_'

# Load config
config = OCRConfig()

def get_settings() -> OCRConfig:
    """Retrieve the global configuration instance."""
    return config

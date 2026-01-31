from pydantic_settings import BaseSettings
from pydantic import Field
from typing import List, Optional
import os

class OCRConfig(BaseSettings):
    """Type-safe configuration with validation"""
    
    # OCR Engine
    ocr_languages: List[str] = Field(default=['en', 'ur'], description="Languages to detect")
    ocr_gpu: bool = Field(default=False, description="Use GPU acceleration")
    ocr_batch_size: int = Field(default=8, description="Pages to process in parallel")
    
    # Performance
    max_workers: int = Field(default=4, description="Thread pool size")
    timeout_per_page: int = Field(default=30, description="Seconds before timeout")
    
    # Storage
    database_url: str = Field(default='sqlite:///blast_ocr.db')
    output_format: str = Field(default='txt', description="Output format: txt, json, pptx")
    
    # Paths
    data_dir: str = Field(default='data/pages')
    output_dir: str = Field(default='output')
    log_dir: str = Field(default='logs')
    
    # Quality Control
    min_confidence: float = Field(default=0.6, description="Minimum confidence to accept")
    enable_spellcheck: bool = Field(default=True)
    
    # Self-Healing
    max_retries: int = Field(default=3)
    retry_backoff: int = Field(default=2)
    enable_fallback: bool = Field(default=True)
    
    class Config:
        env_file = '.env'
        env_prefix = 'BLAST_OCR_'

# Load config
config = OCRConfig()

"""
blast_ocr.api package

Enterprise REST API service powered by FastAPI and Uvicorn.
"""

from blast_ocr.api.app import app
from blast_ocr.api.server import start_server

__all__ = ["app", "start_server"]

"""
blast_ocr.api.server

CLI runner for the B.L.A.S.T. FastAPI production server.
"""

import argparse
import uvicorn
import logging

from blast_ocr.logging_config import setup_logging
from blast_ocr.config import config

logger = logging.getLogger(__name__)


# 0.0.0.0 default is required for container port binding & Docker ingress
def start_server(
    host: str = "0.0.0.0",  # nosec B104
    port: int = 8000,
    reload: bool = False,
    workers: int = 1,
):
    """Launches the Uvicorn ASGI server hosting the B.L.A.S.T. REST API."""
    setup_logging(config.log_dir)
    logger.info(f"Starting B.L.A.S.T. OCR REST API on http://{host}:{port}")
    uvicorn.run(
        "blast_ocr.api.app:app",
        host=host,
        port=port,
        reload=reload,
        workers=workers,
        log_level="info",
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="B.L.A.S.T. OCR REST API Server")
    # 0.0.0.0 default is required for container port binding & Docker ingress
    parser.add_argument("--host", default="0.0.0.0", help="Binding IP address (default: 0.0.0.0)")  # nosec B104
    parser.add_argument("--port", type=int, default=8000, help="Port to listen on (default: 8000)")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload on code changes")
    parser.add_argument("--workers", type=int, default=1, help="Number of worker processes")
    args = parser.parse_args()

    start_server(host=args.host, port=args.port, reload=args.reload, workers=args.workers)

import logging
import logging.handlers
from pathlib import Path
import json
from datetime import datetime, timezone
from typing import Union, Dict, Any


class JSONFormatter(logging.Formatter):
    """Structured JSON Formatter for log records."""

    def format(self, record: logging.LogRecord) -> str:
        log_data: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Add custom fields
        if hasattr(record, "page_number"):
            log_data["page_number"] = getattr(record, "page_number")
        if hasattr(record, "confidence"):
            log_data["confidence"] = getattr(record, "confidence")

        return json.dumps(log_data)


def setup_logging(
    log_dir: Union[str, Path] = "logs", level: int = logging.INFO
) -> logging.Logger:
    """Configure structured logging with console and rotating JSON file handlers."""

    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)

    # Root logger
    logger = logging.getLogger("blast_ocr")
    logger.setLevel(level)

    # Clear existing handlers and close file descriptors to avoid leaks
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        try:
            handler.close()
        except Exception:
            pass

    # Console handler (human-readable)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(
        logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    )
    logger.addHandler(console_handler)

    # File handler (JSON format)
    file_handler = logging.handlers.RotatingFileHandler(
        log_path / "blast_ocr.log",
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
    )
    file_handler.setFormatter(JSONFormatter())
    logger.addHandler(file_handler)

    # Error file (errors only)
    error_handler = logging.handlers.RotatingFileHandler(
        log_path / "errors.log", maxBytes=10 * 1024 * 1024, backupCount=5
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(JSONFormatter())
    logger.addHandler(error_handler)

    return logger

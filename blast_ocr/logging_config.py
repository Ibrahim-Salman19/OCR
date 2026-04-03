import logging
import logging.handlers
from pathlib import Path
import json
from datetime import datetime, timezone


def setup_logging(log_dir="logs", level=logging.INFO):
    """Configure structured logging"""

    log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)

    # Create formatter
    class JSONFormatter(logging.Formatter):
        def format(self, record):
            log_data = {
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
                log_data["page_number"] = record.page_number
            if hasattr(record, "confidence"):
                log_data["confidence"] = record.confidence

            return json.dumps(log_data)

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
        log_dir / "blast_ocr.log",
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
    )
    file_handler.setFormatter(JSONFormatter())
    logger.addHandler(file_handler)

    # Error file (errors only)
    error_handler = logging.handlers.RotatingFileHandler(
        log_dir / "errors.log", maxBytes=10 * 1024 * 1024, backupCount=5
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(JSONFormatter())
    logger.addHandler(error_handler)

    return logger

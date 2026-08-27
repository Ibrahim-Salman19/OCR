#!/usr/bin/env python
"""
B.L.A.S.T. OCR - Project Maintenance Tool

Usage:
  python maintain.py --clean      # Clean logs and temp files
  python maintain.py --audit      # Run system checks
  python maintain.py --stats      # Show usage stats
"""

import os
import sys
import shutil
import argparse
import logging
from pathlib import Path

# Setup basic logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("MAINTAIN")

PROJECT_ROOT = Path(__file__).parent.absolute()


def clean_system():
    """Remove temporary files and old logs."""
    logger.info("Starting cleanup...")

    # 1. Clean .tmp
    tmp_path = PROJECT_ROOT / ".tmp"
    if tmp_path.exists():
        try:
            shutil.rmtree(tmp_path)
            logger.info("✅ Removed .tmp directory")
        except Exception as e:
            logger.error(f"❌ Failed to remove .tmp: {e}")

    # 2. Rotate Logs (Keep last 5)
    log_path = PROJECT_ROOT / "blast_ocr" / "logs"  # Default log loc
    # Check config if possible, but fallback to likely spots
    if not log_path.exists():
        log_path = PROJECT_ROOT / "logs"

    if log_path.exists():
        logs = sorted(log_path.glob("*.log"), key=os.path.getmtime, reverse=True)
        if len(logs) > 5:
            for log in logs[5:]:
                try:
                    os.remove(log)
                    logger.info(f"🗑️ Deleted old log: {log.name}")
                except Exception as e:
                    logger.warning(f"Failed to delete {log.name}: {e}")

    logger.info("Cleanup complete.")


def audit_system():
    """Run verification scripts."""
    logger.info("Running System Audit...")

    # 1. Check DLLs
    dll_check = PROJECT_ROOT / "dll_check.py"
    if dll_check.exists():
        logger.info("--> Checking DLLs...")
        os.system(f'{sys.executable} "{dll_check}"')

    # 2. Verify Foundation
    found_check = PROJECT_ROOT / "verify_foundation.py"
    if found_check.exists():
        logger.info("--> Verifying Foundation...")
        os.system(f'{sys.executable} "{found_check}"')

    logger.info("Audit complete.")


def show_stats():
    """Query DB for stats (if exists)."""
    try:
        from blast_ocr.storage.database import OCRDatabase

        db = OCRDatabase()

        # Raw SQL for speed/simplicity
        with db.get_session():
            pass
            # For now, just print where the DB is
        logger.info(f"Database located at: {db.engine.url}")
        logger.info("Stats feature requires active DB connection logic expansion.")

    except ImportError:
        logger.warning("Could not import OCRDatabase. Dependencies missing?")
    except Exception as e:
        logger.error(f"Stats check failed: {e}")


def main():
    parser = argparse.ArgumentParser(description="B.L.A.S.T. Maintenance Tool")
    parser.add_argument(
        "--clean", action="store_true", help="Clean logs and temp files"
    )
    parser.add_argument("--audit", action="store_true", help="Run system checks")
    parser.add_argument("--stats", action="store_true", help="Show system stats")

    args = parser.parse_args()

    if args.clean:
        clean_system()
    if args.audit:
        audit_system()
    if args.stats:
        show_stats()

    if not (args.clean or args.audit or args.stats):
        parser.print_help()


if __name__ == "__main__":
    main()

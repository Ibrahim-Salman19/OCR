import os
import shutil
import time
import logging

logger = logging.getLogger(__name__)


class CleanupManager:
    """
    Automated System Stewardship for B.L.A.S.T.
    Inspired by 'deanpeters/business-health-diagnostic' and 'garrytan/qa'.
    """

    @staticmethod
    def cleanup_stale_sessions(base_dir: str, max_age_hours: int = 24) -> int:
        """
        Scans and purges temporary session folders older than max_age_hours.
        Returns the number of bytes saved.
        """
        bytes_saved = 0
        now = time.time()
        max_age_seconds = max_age_hours * 3600

        if not os.path.exists(base_dir):
            return 0

        for folder_name in os.listdir(base_dir):
            folder_path = os.path.join(base_dir, folder_name)
            if os.path.isdir(folder_path):
                # Check modification time
                folder_mtime = os.path.getmtime(folder_path)
                if (now - folder_mtime) > max_age_seconds:
                    logger.info(f"Purging stale session: {folder_name}")
                    try:
                        # Estimate size before deletion
                        for root, dirs, files in os.walk(folder_path):
                            for f in files:
                                bytes_saved += os.path.getsize(os.path.join(root, f))

                        shutil.rmtree(folder_path)
                    except Exception as e:
                        logger.error(f"Failed to purge folder {folder_name}: {e}")

        return bytes_saved

    @staticmethod
    def get_system_disk_stats(base_dir: str) -> dict:
        """
        Returns basic usage telemetry for the project's output directory.
        """
        total_size = 0
        count = 0
        if os.path.exists(base_dir):
            for root, dirs, files in os.walk(base_dir):
                for f in files:
                    total_size += os.path.getsize(os.path.join(root, f))
                count += len(dirs)

        return {"total_size_mb": total_size / (1024 * 1024), "session_count": count}

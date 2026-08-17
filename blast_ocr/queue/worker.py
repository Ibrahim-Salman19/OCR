"""
blast_ocr.queue.worker

RQ & Swarm worker entrypoint with multi-queue priority listening and heartbeat integration. Run with:

    python -m blast_ocr.queue.worker --worker-id node-1 --queues high,default,low
"""

import argparse
import logging
import os
import sys
import uuid


def main() -> int:
    from blast_ocr.config import config
    from blast_ocr.logging_config import setup_logging
    from blast_ocr.queue.client import get_queue, get_redis_connection, is_queue_available
    from blast_ocr.queue.heartbeat import HeartbeatDaemon

    parser = argparse.ArgumentParser(description="B.L.A.S.T. OCR Swarm Worker")
    parser.add_argument("--worker-id", type=str, default=None, help="Custom unique worker ID")
    parser.add_argument("--queues", type=str, default="high,default,low", help="Comma-separated queue tiers")
    parser.add_argument("--heartbeat-interval", type=float, default=5.0, help="Heartbeat interval in seconds")
    args = parser.parse_args()

    setup_logging(config.log_dir)
    logger = logging.getLogger("blast_ocr.queue.worker")

    if not is_queue_available():
        logger.error(
            f"Cannot reach Redis at {config.redis_url}. "
            f"Start redis-server or set BLAST_OCR_REDIS_URL, then retry."
        )
        return 1

    worker_id = args.worker_id or f"worker:{os.uname().nodename if hasattr(os, 'uname') else 'local'}:{os.getpid()}:{uuid.uuid4().hex[:6]}"
    queue_names = [q.strip() for q in args.queues.split(",") if q.strip()]

    redis_conn = get_redis_connection()
    heartbeat = HeartbeatDaemon(
        redis_client=redis_conn,
        worker_id=worker_id,
        interval_seconds=args.heartbeat_interval,
        queues=queue_names,
    )
    heartbeat.start()

    try:
        from rq import Worker
        rq_queues = [get_queue(qn) for qn in queue_names]
        logger.info(f"Starting worker '{worker_id}' listening on {[q.name for q in rq_queues]}")
        worker = Worker(rq_queues, connection=redis_conn, name=worker_id)
        worker.work(with_scheduler=False)
    except Exception as e:
        logger.error(f"Worker encountered fatal error: {e}", exc_info=True)
    finally:
        heartbeat.stop()

    return 0


if __name__ == "__main__":
    sys.exit(main())

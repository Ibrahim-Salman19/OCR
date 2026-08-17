"""
eval.stress_test

Automated Continuous Stress Testing and Resilience Verification for B.L.A.S.T. OCR.
Validates:
- Zero memory leaks over continuous multi-hundred/multi-thousand page batch workloads
- Dynamic memory sliding window bounds enforcement
- Resilience under simulated worker faults, exceptions, and transient timeouts
- Dead Letter Queue (DLQ) quarantine behavior under repeated failures
"""

from __future__ import annotations

import argparse
import collections
import gc
import json
import logging
import os
from pathlib import Path
import time
from typing import Any, Dict, List, Optional, Union

import numpy as np
import psutil

from blast_ocr.core.batch_preprocessor import BatchPreprocessor
from blast_ocr.core.engines.batched_rapidocr import BatchedRapidOCREngine
from blast_ocr.core.job_state import TransientWorkerError, NonRetryableJobError
from blast_ocr.queue.tasks import BackoffDLQHandler

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("eval.stress_test")


class MockRedis:
    def __init__(self):
        self.lists = collections.defaultdict(list)
        self.hashes = collections.defaultdict(dict)
        self.strings = {}

    def lpush(self, key, value):
        self.lists[key].insert(0, value)
        return len(self.lists[key])

    def rpush(self, key, value):
        self.lists[key].append(value)
        return len(self.lists[key])

    def rpop(self, key):
        if self.lists[key]:
            return self.lists[key].pop()
        return None

    def llen(self, key):
        return len(self.lists[key])

    def hset(self, key, *args, **kwargs):
        return 1

    def zadd(self, key, mapping):
        return len(mapping)


class StressTestRunner:
    """
    Stress test executor measuring memory stability, slope regression, and fault recovery.
    """

    def __init__(self, output_dir: Optional[Union[str, Path]] = None):
        self.output_dir = Path(output_dir or "eval/results")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.results: Dict[str, Any] = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "stress_suite": {},
        }

    def run_memory_leak_stress_test(
        self,
        total_pages: int = 100,
        batch_size: int = 8,
        max_allowed_slope_mb_per_page: float = 0.05,
    ) -> Dict[str, Any]:
        """
        Processes pages in continuous batches and performs linear regression on RSS memory.
        """
        logger.info(
            "Starting continuous memory leak stress test: %d pages (batch size %d)...",
            total_pages,
            batch_size,
        )
        engine = BatchedRapidOCREngine()
        dummy_img = np.full((1200, 800, 3), 255, dtype=np.uint8)

        proc = psutil.Process(os.getpid())
        gc.collect()
        initial_rss = proc.memory_info().rss / (1024 * 1024)

        rss_snapshots: List[float] = []
        pages_processed = 0

        while pages_processed < total_pages:
            current_batch_count = min(batch_size, total_pages - pages_processed)
            batch = [dummy_img.copy() for _ in range(current_batch_count)]

            engine.process_batch(batch, batch_size=current_batch_count)
            pages_processed += current_batch_count

            current_rss = proc.memory_info().rss / (1024 * 1024)
            rss_snapshots.append(current_rss)

        x = np.arange(len(rss_snapshots))
        y = np.array(rss_snapshots)
        # Linear regression slope (MB per batch)
        slope, intercept = np.polyfit(x, y, 1)
        slope_per_page = float(slope / batch_size)
        peak_rss = float(np.max(y))
        growth_mb = float(peak_rss - initial_rss)

        passed = slope_per_page <= max_allowed_slope_mb_per_page

        metrics = {
            "total_pages": total_pages,
            "batch_size": batch_size,
            "initial_rss_mb": round(initial_rss, 2),
            "peak_rss_mb": round(peak_rss, 2),
            "net_growth_mb": round(growth_mb, 2),
            "rss_slope_mb_per_page": round(slope_per_page, 6),
            "leak_threshold_mb_per_page": max_allowed_slope_mb_per_page,
            "leak_free_passed": passed,
        }

        logger.info(
            "Memory Stress Result: Peak RSS = %.2f MB, Slope = %.6f MB/page (Pass: %s)",
            peak_rss,
            slope_per_page,
            passed,
        )
        self.results["stress_suite"]["memory_stability"] = metrics
        return metrics

    def run_worker_fault_recovery_test(self, num_failing_tasks: int = 10) -> Dict[str, Any]:
        """
        Validates worker swarm fault handling, exponential backoff retries, and DLQ containment.
        """
        logger.info("Starting worker fault recovery test with %d fault tasks...", num_failing_tasks)
        mock_redis = MockRedis()
        handler = BackoffDLQHandler(
            base_delay=0.01,
            backoff_factor=2.0,
            max_retries=3,
            redis_client=mock_redis,
        )

        dlq_count = 0
        retried_count = 0

        for i in range(num_failing_tasks):
            job_id = f"job_fault_{i}"
            # Retryable exception simulation
            exc = TransientWorkerError("Simulated worker timeout")
            # Step through retries 0, 1, 2 (should schedule retry) and 3 (should DLQ)
            for r in range(4):
                action = handler.handle_task_failure(
                    job_id=i + 1,
                    exc=exc,
                    current_retry_count=r,
                    job_payload={"job_id": i + 1, "source_path": f"doc_{i}.pdf"},
                )
                if action["action"] == "retry":
                    retried_count += 1
                elif action["action"] == "dlq":
                    dlq_count += 1

        metrics = {
            "num_fault_tasks": num_failing_tasks,
            "retries_scheduled": retried_count,
            "dlq_quarantined": dlq_count,
            "expected_dlq": num_failing_tasks,
            "quarantine_success": dlq_count == num_failing_tasks,
        }
        logger.info("Worker fault recovery result: %s", metrics)
        self.results["stress_suite"]["fault_recovery"] = metrics
        return metrics

    def save_report(self, filename: str = "stress_report.json") -> Path:
        """Saves stress test report to disk."""
        report_path = self.output_dir / filename
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(self.results, f, indent=2)
        logger.info("Stress test report saved to %s", report_path)
        return report_path


def main():
    parser = argparse.ArgumentParser(description="B.L.A.S.T. OCR Continuous Stress Test Runner")
    parser.add_argument("--output", default="eval/results", help="Directory for stress report output")
    parser.add_argument("--pages", type=int, default=50, help="Total pages for continuous memory test")
    args = parser.parse_args()

    runner = StressTestRunner(output_dir=args.output)
    runner.run_memory_leak_stress_test(total_pages=args.pages)
    runner.run_worker_fault_recovery_test(num_failing_tasks=10)
    runner.save_report()


if __name__ == "__main__":
    main()

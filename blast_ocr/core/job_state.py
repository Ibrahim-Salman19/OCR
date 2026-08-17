"""
blast_ocr.core.job_state

Durable Job State Machine, Idempotency Fingerprinting, and Categorized Retry Taxonomy (Phase 5 of Execution Plan v2).
"""

import hashlib
import json
from blast_ocr.core.models import JobState, JobConfig


class RetryableJobError(Exception):
    """Base exception for transient errors that warrant retries."""
    pass


class NonRetryableJobError(Exception):
    """Base exception for deterministic errors that should not be retried."""
    pass


class TransientWorkerError(RetryableJobError): pass
class TemporaryStorageError(RetryableJobError): pass
class WorkerLostError(RetryableJobError): pass

class UnsupportedPDFError(NonRetryableJobError): pass
class EncryptedPDFError(NonRetryableJobError): pass
class InvalidDocumentError(NonRetryableJobError): pass
class OutOfPolicyDocumentError(NonRetryableJobError): pass


def classify_exception(exc: BaseException) -> bool:
    """
    Classify an exception raised during job processing as retryable or not.

    Bridges blast_ocr.core.exceptions' domain hierarchy (raised by the
    extractor/engines) and blast_ocr.security.gateway.SecurityValidationError
    with this module's retry taxonomy, so callers -- currently the job-level
    except block in BlastPipeline.process_job, eventually the queue worker's
    retry policy -- have one place to ask "is this worth retrying?" rather than
    defaulting every failure to a blanket retry-or-not.

    Returns True if the failure is plausibly transient and worth retrying,
    False if it is a deterministic property of the input that a retry cannot fix.
    """
    if isinstance(exc, (RetryableJobError,)):
        return True
    if isinstance(exc, (NonRetryableJobError,)):
        return False

    # Deterministic, input-shape failures: retrying with the same bytes changes nothing.
    non_retryable_names = {
        "SecurityValidationError",
        "ValueError",
        "FileNotFoundError",
        "UnsupportedPDFError",
        "EncryptedPDFError",
        "InvalidDocumentError",
    }
    # Transient, environment/resource failures: a retry (possibly after backoff
    # or on a different worker) has a real chance of succeeding.
    retryable_names = {
        "OCREngineError",
        "TimeoutError",
        "ConnectionError",
        "OSError",
        "MemoryError",
    }

    exc_type_names = {t.__name__ for t in type(exc).__mro__}
    if exc_type_names & non_retryable_names:
        return False
    if exc_type_names & retryable_names:
        return True

    # Unknown failure shape: default to non-retryable. A blanket retry-on-unknown
    # policy is how transient-looking bugs silently become infinite retry loops;
    # an operator can reclassify a specific exception type once its behavior is
    # understood, rather than every unclassified error being retried by default.
    return False


class JobFingerprint:
    """Computes deterministic execution fingerprints for job idempotency."""

    @staticmethod
    def compute(
        input_sha256: str,
        job_config: JobConfig,
        pipeline_version: str = "1.0.0-SOVEREIGN",
        ocr_model_version: str = "1.0.0",
    ) -> str:
        """
        SHA256(input_sha256 + normalized_job_config + pipeline_version + ocr_model_version)
        """
        config_json = json.dumps(job_config.to_dict(), sort_keys=True)
        raw_string = f"{input_sha256}:{config_json}:{pipeline_version}:{ocr_model_version}"
        return hashlib.sha256(raw_string.encode("utf-8")).hexdigest()


class JobStateMachine:
    """Validates state transitions across the processing lifecycle."""

    ALLOWED_TRANSITIONS = {
        # RECEIVED -> PROCESSING is a direct fast-path for synchronous callers that
        # don't need separately durable VALIDATING/QUEUED states (no queue backend
        # in front of them yet). A queue-backed caller should still walk
        # RECEIVED -> VALIDATING -> QUEUED -> PROCESSING for full lifecycle auditability.
        JobState.RECEIVED: {JobState.VALIDATING, JobState.QUEUED, JobState.PROCESSING, JobState.FAILED, JobState.CANCELLED},
        JobState.VALIDATING: {JobState.QUEUED, JobState.QUARANTINED, JobState.FAILED},
        JobState.QUEUED: {JobState.PROCESSING, JobState.CANCELLED, JobState.TIMED_OUT},
        JobState.PROCESSING: {
            JobState.POST_PROCESSING,
            JobState.EXPORTING,
            JobState.SUCCEEDED,
            JobState.PARTIAL_FAILURE,
            JobState.FAILED,
            JobState.TIMED_OUT,
        },
        JobState.POST_PROCESSING: {JobState.EXPORTING, JobState.FAILED},
        JobState.EXPORTING: {
            JobState.SUCCEEDED,
            JobState.SUCCEEDED_WITH_WARNINGS,
            JobState.PARTIAL_FAILURE,
            JobState.FAILED,
        },
        JobState.SUCCEEDED: set(),
        JobState.SUCCEEDED_WITH_WARNINGS: set(),
        JobState.PARTIAL_FAILURE: set(),
        JobState.FAILED: {JobState.QUEUED},  # Allow retry from FAILED
        JobState.CANCELLED: set(),
        JobState.QUARANTINED: set(),
        JobState.TIMED_OUT: {JobState.QUEUED},
    }

    @classmethod
    def can_transition(cls, current: JobState, target: JobState) -> bool:
        return target in cls.ALLOWED_TRANSITIONS.get(current, set())

    @classmethod
    def validate_transition(cls, current: JobState, target: JobState) -> None:
        if not cls.can_transition(current, target):
            raise ValueError(
                f"Invalid job state transition: '{current}' -> '{target}'. Allowed targets: {sorted(cls.ALLOWED_TRANSITIONS.get(current, []))}"
            )

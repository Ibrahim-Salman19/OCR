from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    Text,
    DateTime,
    Float,
    ForeignKey,
    text,
)
from sqlalchemy.orm import declarative_base, scoped_session, sessionmaker
from sqlalchemy import event  # Added for FK enforcement
from contextlib import contextmanager
from pathlib import Path
import datetime
import threading
import logging
from blast_ocr.config import config
from blast_ocr.core.models import JobState
from blast_ocr.core.job_state import JobStateMachine

logger = logging.getLogger(__name__)

# completed_at is specifically a *success* completion timestamp (existing contract,
# BUG-DB-DATE-01): callers use "is completed_at set?" as a success proxy, so it must
# stay unset for failed/cancelled/quarantined jobs even though those are terminal too.
_TERMINAL_SUCCESS_STATES = {
    JobState.SUCCEEDED.value,
    JobState.SUCCEEDED_WITH_WARNINGS.value,
}

Base = declarative_base()


class OCRJob(Base):
    __tablename__ = "ocr_jobs"

    id = Column(Integer, primary_key=True)
    filename = Column(String(255), nullable=False)
    page_count = Column(Integer)
    status = Column(String(50))  # pending, processing, completed, failed
    created_at = Column(
        DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc)
    )
    completed_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)

    # Swarm & Priority Queue extensions
    priority = Column(String(20), default="default", nullable=False)
    retry_count = Column(Integer, default=0, nullable=False)
    max_retries = Column(Integer, default=3, nullable=False)
    worker_id = Column(String(100), nullable=True)
    queue_name = Column(String(50), nullable=True)
    started_at = Column(DateTime, nullable=True)
    dlq_at = Column(DateTime, nullable=True)
    dlq_reason = Column(Text, nullable=True)


class OCRResult(Base):
    __tablename__ = "ocr_results"

    id = Column(Integer, primary_key=True)
    job_id = Column(Integer, ForeignKey("ocr_jobs.id"))
    page_number = Column(Integer)
    extracted_text = Column(Text)
    confidence_score = Column(Float)
    processing_time = Column(Float)  # seconds
    created_at = Column(
        DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc)
    )


class OCRMetric(Base):
    __tablename__ = "ocr_metrics"

    id = Column(Integer, primary_key=True)
    job_id = Column(Integer, ForeignKey("ocr_jobs.id"))
    peak_memory_mb = Column(Float)
    avg_page_time = Column(Float)
    fidelity_score = Column(Float)  # Based on confidence
    extraction_velocity = Column(Float)  # Pages/sec
    timestamp = Column(
        DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc)
    )


import atexit

# Database manager
class OCRDatabase:
    _local = threading.local()

    def __init__(self, db_path=None):
        # Use config if no path provided
        self.db_url = db_path or config.database_url
        engine_kwargs = {
            "pool_size": 5,
            "max_overflow": 10,
            "pool_pre_ping": True,
        }

        connect_args = {}
        if str(self.db_url).startswith("sqlite"):
            connect_args = {
                "isolation_level": "IMMEDIATE",
                "timeout": 30,
                "check_same_thread": False,
            }

        self.engine = create_engine(
            self.db_url,
            connect_args=connect_args,
            **engine_kwargs,
        )

        @event.listens_for(self.engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        Base.metadata.create_all(self.engine)
        self._reconcile_sqlite_columns()
        self._stamp_alembic_baseline_if_needed()
        session_factory = sessionmaker(bind=self.engine)
        self.Session = scoped_session(session_factory, scopefunc=threading.get_ident)

        # Register deterministic process exit cleanup
        atexit.register(self.close)

    def _reconcile_sqlite_columns(self) -> None:
        """Ensures all model columns exist on existing SQLite databases."""
        if "sqlite" not in self.db_url:
            return
        try:
            with self.engine.connect() as conn:
                res = conn.execute(text("PRAGMA table_info(ocr_jobs)"))
                existing_cols = {row[1] for row in res.fetchall()}
                new_cols = {
                    "priority": "VARCHAR(20) DEFAULT 'default'",
                    "retry_count": "INTEGER DEFAULT 0",
                    "max_retries": "INTEGER DEFAULT 3",
                    "worker_id": "VARCHAR(100)",
                    "queue_name": "VARCHAR(50)",
                    "started_at": "DATETIME",
                    "dlq_at": "DATETIME",
                    "dlq_reason": "TEXT",
                }
                for col_name, col_type in new_cols.items():
                    if col_name not in existing_cols:
                        conn.execute(text(f"ALTER TABLE ocr_jobs ADD COLUMN {col_name} {col_type}"))
                conn.commit()
        except Exception:
            pass

    def _stamp_alembic_baseline_if_needed(self) -> None:
        """
        Reconcile create_all()'s schema bootstrap with Alembic's version
        tracking. create_all() creates tables idempotently but knows nothing
        about migration history; without this, a fresh database created by
        create_all() has no `alembic_version` row, so a later
        `alembic upgrade head` (e.g. after a schema-changing release) would
        try to re-run 001_initial_schema against tables that already exist
        and fail. Stamping the current head as the baseline the first time we
        see a database with our tables but no alembic_version row makes the
        two mechanisms agree on where migration history starts.
        """
        try:
            from sqlalchemy import inspect as sa_inspect
            inspector = sa_inspect(self.engine)
            existing_tables = set(inspector.get_table_names())
            if "ocr_jobs" not in existing_tables or "alembic_version" in existing_tables:
                return  # either a brand-new DB with nothing to stamp yet, or already tracked

            from alembic.config import Config as AlembicConfig
            from alembic import command as alembic_command

            repo_root = Path(__file__).resolve().parent.parent.parent
            ini_path = repo_root / "alembic.ini"
            if not ini_path.exists():
                return
            cfg = AlembicConfig(str(ini_path))
            cfg.set_main_option("sqlalchemy.url", str(self.db_url))
            alembic_command.stamp(cfg, "head")
            logger.info("Stamped Alembic baseline 'head' on pre-existing create_all() schema.")
        except ImportError:
            logger.debug("Alembic not installed; skipping baseline stamp (create_all() schema still valid).")
        except Exception as e:
            logger.warning(f"Could not stamp Alembic baseline: {e}")

    @property
    def session(self):
        """Thread-local session property"""
        return self.Session()

    @contextmanager
    def session_scope(self):
        """Transactional context manager for thread-safe database sessions."""
        session = self.Session()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            self.Session.remove()

    def create_job(self, filename, page_count=0, priority="default", max_retries=3, queue_name=None):
        session = self.session
        job = OCRJob(
            filename=filename,
            page_count=page_count,
            status=JobState.RECEIVED.value,
            priority=priority or "default",
            max_retries=max_retries if max_retries is not None else 3,
            queue_name=queue_name,
            retry_count=0,
        )
        session.add(job)
        try:
            session.commit()
            return job.id
        except Exception as e:
            session.rollback()
            raise e

    def update_job_status(self, job_id, status, error_message=None):
        """
        Transition a job's status, validated against JobStateMachine.

        `status` accepts a JobState enum member or its string value. Legacy string
        aliases ("pending"/"processing"/"completed"/"failed") are mapped onto their
        JobState equivalents for backward compatibility with older callers.
        """
        legacy_aliases = {
            "pending": JobState.RECEIVED,
            "processing": JobState.PROCESSING,
            "completed": JobState.SUCCEEDED,
            "failed": JobState.FAILED,
        }
        if isinstance(status, JobState):
            target_state = status
        elif status in legacy_aliases:
            target_state = legacy_aliases[status]
        else:
            try:
                target_state = JobState(status)
            except ValueError:
                raise ValueError(
                    f"Invalid status: {status!r}. Must be a JobState value: "
                    f"{sorted(s.value for s in JobState)}"
                )

        session = self.session
        try:
            job = session.query(OCRJob).filter_by(id=job_id).first()
            if not job:
                # BUG-DB-NOTFOUND-01 Fix: Raise error if job doesn't exist
                raise ValueError(f"Job ID {job_id} not found")

            current_state = JobState(job.status) if job.status in {s.value for s in JobState} else JobState.RECEIVED
            JobStateMachine.validate_transition(current_state, target_state)

            job.status = target_state.value
            if target_state.value in _TERMINAL_SUCCESS_STATES:
                job.completed_at = datetime.datetime.now(datetime.timezone.utc)
            else:
                # BUG-DB-DATE-01 Fix: Ensure completed_at is NULL if not successfully completed
                job.completed_at = None

            if error_message:
                job.error_message = error_message
            session.commit()
        except Exception as e:
            session.rollback()
            raise e

    def save_result(self, job_id, page_number, text, confidence, processing_time):
        session = self.session
        result = OCRResult(
            job_id=job_id,
            page_number=page_number,
            extracted_text=text,
            confidence_score=confidence,
            processing_time=processing_time,
            created_at=datetime.datetime.now(datetime.timezone.utc),
        )
        session.add(result)
        try:
            session.commit()
        except Exception as e:
            session.rollback()
            raise e

    def update_job_page_count(self, job_id, page_count):
        session = self.session
        try:
            job = session.query(OCRJob).filter_by(id=job_id).first()
            if job:
                job.page_count = page_count
                session.commit()
        except Exception as e:
            session.rollback()
            raise e

    def save_metric(self, job_id, peak_mem, avg_time, fidelity, velocity):
        session = self.session
        metric = OCRMetric(
            job_id=job_id,
            peak_memory_mb=peak_mem,
            avg_page_time=avg_time,
            fidelity_score=fidelity,
            extraction_velocity=velocity,
        )
        session.add(metric)
        try:
            session.commit()
        except Exception as e:
            session.rollback()
            raise e

    def purge_old_data(self, days=7):
        """
        Lifecycle management: Prune metrics and job results older than X days.
        Inspired by 'deanpeters/business-health-diagnostic'.
        """
        session = self.session
        cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(
            days=days
        )
        try:
            # 1. Prune metrics
            session.query(OCRMetric).filter(OCRMetric.timestamp < cutoff).delete()
            # 2. Prune old job results (keep the job entry itself for history)
            # Find jobs completed before cutoff
            old_jobs = (
                session.query(OCRJob.id).filter(OCRJob.completed_at < cutoff).all()
            )
            old_job_ids = [j[0] for j in old_jobs]
            if old_job_ids:
                session.query(OCRResult).filter(
                    OCRResult.job_id.in_(old_job_ids)
                ).delete()

            session.commit()
            logger.info(f"Purged data older than {days} days.")
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to purge old data: {e}")

    def get_recent_metrics(self, limit=10):
        session = self.session
        return (
            session.query(OCRMetric)
            .order_by(OCRMetric.timestamp.desc())
            .limit(limit)
            .all()
        )

    def get_job(self, job_id):
        session = self.session
        return session.query(OCRJob).filter_by(id=job_id).first()

    def get_results(self, job_id):
        session = self.session
        return (
            session.query(OCRResult)
            .filter_by(job_id=job_id)
            .order_by(OCRResult.page_number)
            .all()
        )

    def get_recent_jobs(self, limit=50):
        """Retrieves list of most recent OCR jobs as dictionaries."""
        session = self.session
        jobs = (
            session.query(OCRJob)
            .order_by(OCRJob.created_at.desc())
            .limit(limit)
            .all()
        )
        return [
            {
                "id": j.id,
                "source_file": j.filename,
                "filename": j.filename,
                "page_count": j.page_count,
                "total_pages": j.page_count,
                "status": j.status,
                "created_at": j.created_at,
                "completed_at": j.completed_at,
                "error_message": j.error_message,
                "priority": getattr(j, "priority", "default") or "default",
                "retry_count": getattr(j, "retry_count", 0) or 0,
                "max_retries": getattr(j, "max_retries", 3) or 3,
                "worker_id": getattr(j, "worker_id", None),
                "queue_name": getattr(j, "queue_name", None),
                "started_at": getattr(j, "started_at", None),
                "dlq_at": getattr(j, "dlq_at", None),
                "dlq_reason": getattr(j, "dlq_reason", None),
            }
            for j in jobs
        ]

    def update_job_execution(self, job_id, worker_id=None, started_at=None, queue_name=None):
        """Updates worker identity and execution start timestamp."""
        session = self.session
        try:
            job = session.query(OCRJob).filter_by(id=job_id).first()
            if job:
                if worker_id is not None:
                    job.worker_id = worker_id
                if started_at is not None:
                    job.started_at = started_at
                if queue_name is not None:
                    job.queue_name = queue_name
                session.commit()
        except Exception as e:
            session.rollback()
            raise e

    def update_job_retry(self, job_id, retry_count, error_message=None):
        """Updates job retry count and records last error."""
        session = self.session
        try:
            job = session.query(OCRJob).filter_by(id=job_id).first()
            if job:
                job.retry_count = retry_count
                if error_message:
                    job.error_message = error_message
                session.commit()
        except Exception as e:
            session.rollback()
            raise e

    def mark_job_dlq(self, job_id, dlq_reason):
        """Marks a job as dead-lettered with quarantine timestamp and reason."""
        session = self.session
        try:
            job = session.query(OCRJob).filter_by(id=job_id).first()
            if job:
                job.status = JobState.FAILED.value
                job.dlq_at = datetime.datetime.now(datetime.timezone.utc)
                job.dlq_reason = str(dlq_reason)
                job.error_message = f"Exhausted retries: {dlq_reason}"
                session.commit()
        except Exception as e:
            session.rollback()
            raise e

    def get_job_pages(self, job_id):
        """Retrieves list of OCR page results for a specific job."""
        results = self.get_results(job_id)
        return [
            {
                "page": r.page_number,
                "page_number": r.page_number,
                "text": r.extracted_text,
                "confidence": r.confidence_score,
                "processing_time": r.processing_time,
                "created_at": r.created_at,
            }
            for r in results
        ]

    # FIX(phase2): BUG-03 - Add close method to prevent session leaks
    def close(self):
        """Close database session and dispose of the engine to prevent resource leaks."""
        if hasattr(self, "Session"):
            self.Session.remove()
        if hasattr(self, "engine"):
            self.engine.dispose()

    def __del__(self):
        """Cleanup on garbage collection."""
        try:
            self.close()
        except Exception:
            pass

from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    Text,
    DateTime,
    Float,
    ForeignKey,
)
from sqlalchemy.orm import declarative_base, scoped_session, sessionmaker
from sqlalchemy import event  # Added for FK enforcement
import datetime
import threading
import logging
from blast_ocr.config import config

logger = logging.getLogger(__name__)

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


# Database manager
class OCRDatabase:
    _local = threading.local()

    def __init__(self, db_path=None):
        # Use config if no path provided
        self.db_url = db_path or config.database_url
        # FIX #4: Add connection pool settings for thread safety
        # BUG-DB-ISOLATION-01 Fix: Add IMMEDIATE isolation level to prevent SQLite WAL deadlocks
        self.engine = create_engine(
            self.db_url,
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,
            connect_args={"isolation_level": "IMMEDIATE", "timeout": 15},
        )

        # FIX: Ensure SQLite enforces Foreign Key constraints
        @event.listens_for(self.engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        Base.metadata.create_all(self.engine)
        # FIX #4: Use scoped_session for thread-safe session management
        session_factory = sessionmaker(bind=self.engine)
        # Use get_ident explicitly to bypass any threading.local pollution
        self.Session = scoped_session(session_factory, scopefunc=threading.get_ident)

    @property
    def session(self):
        """Thread-local session property"""
        return self.Session()

    def create_job(self, filename, page_count=0):
        session = self.session
        job = OCRJob(filename=filename, page_count=page_count, status="pending")
        session.add(job)
        try:
            session.commit()
            return job.id
        except Exception as e:
            session.rollback()
            raise e

    def update_job_status(self, job_id, status, error_message=None):
        # BUG-DB-VALIDATION-01 Fix: Explicit status validation
        allowed_statuses = ["pending", "processing", "completed", "failed"]
        if status not in allowed_statuses:
            raise ValueError(
                f"Invalid status: {status}. Must be one of {allowed_statuses}"
            )

        session = self.session
        try:
            job = session.query(OCRJob).filter_by(id=job_id).first()
            if not job:
                # BUG-DB-NOTFOUND-01 Fix: Raise error if job doesn't exist
                raise ValueError(f"Job ID {job_id} not found")

            job.status = status
            if status == "completed":
                job.completed_at = datetime.datetime.now(datetime.timezone.utc)
            else:
                # BUG-DB-DATE-01 Fix: Ensure completed_at is NULL if not completed
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

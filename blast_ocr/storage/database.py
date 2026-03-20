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
import datetime
import threading
from blast_ocr.config import config

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


# Database manager
class OCRDatabase:
    _local = threading.local()

    def __init__(self, db_path=None):
        # Use config if no path provided
        self.db_url = db_path or config.database_url
        # FIX #4: Add connection pool settings for thread safety
        self.engine = create_engine(
            self.db_url, pool_size=5, max_overflow=10, pool_pre_ping=True
        )
        Base.metadata.create_all(self.engine)
        # FIX #4: Use scoped_session for thread-safe session management
        session_factory = sessionmaker(bind=self.engine)
        self.Session = scoped_session(session_factory)

    @property
    def session(self):
        """Thread-local session property"""
        return self.Session()

    def create_job(self, filename, page_count):
        session = self.Session
        job = OCRJob(filename=filename, page_count=page_count, status="pending")
        session.add(job)
        session.commit()
        return job.id

    def update_job_status(self, job_id, status, error_message=None):
        session = self.Session
        job = session.query(OCRJob).filter_by(id=job_id).first()
        if job:
            job.status = status
            if status == "completed":
                job.completed_at = datetime.datetime.now(datetime.timezone.utc)
            if error_message:
                job.error_message = error_message
            session.commit()

    def save_result(self, job_id, page_number, text, confidence, processing_time):
        session = self.Session
        result = OCRResult(
            job_id=job_id,
            page_number=page_number,
            extracted_text=text,
            confidence_score=confidence,
            processing_time=processing_time,
        )
        session.add(result)
        session.commit()

    def get_job(self, job_id):
        session = self.Session
        return session.query(OCRJob).filter_by(id=job_id).first()

    def get_results(self, job_id):
        session = self.Session
        return (
            session.query(OCRResult)
            .filter_by(job_id=job_id)
            .order_by(OCRResult.page_number)
            .all()
        )

    # FIX(phase2): BUG-03 - Add close method to prevent session leaks
    def close(self):
        """Close database session to prevent resource leaks."""
        if hasattr(self, "Session"):
            self.Session.remove()

    def __del__(self):
        """Cleanup on garbage collection."""
        try:
            self.close()
        except Exception:
            pass

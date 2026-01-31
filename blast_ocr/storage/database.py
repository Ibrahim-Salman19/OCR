from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, Float, ForeignKey
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker
import datetime
from blast_ocr.config import config

Base = declarative_base()

class OCRJob(Base):
    __tablename__ = 'ocr_jobs'
    
    id = Column(Integer, primary_key=True)
    filename = Column(String(255), nullable=False)
    page_count = Column(Integer)
    status = Column(String(50))  # pending, processing, completed, failed
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)
    
class OCRResult(Base):
    __tablename__ = 'ocr_results'
    
    id = Column(Integer, primary_key=True)
    job_id = Column(Integer, ForeignKey('ocr_jobs.id'))
    page_number = Column(Integer)
    extracted_text = Column(Text)
    confidence_score = Column(Float)
    processing_time = Column(Float)  # seconds
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

# Database manager
class OCRDatabase:
    def __init__(self, db_path=None):
        # Use config if no path provided
        self.db_url = db_path or config.database_url
        self.engine = create_engine(self.db_url)
        Base.metadata.create_all(self.engine)
        Session = sessionmaker(bind=self.engine)
        self.session = Session()
    
    def create_job(self, filename, page_count):
        job = OCRJob(filename=filename, page_count=page_count, status='pending')
        self.session.add(job)
        self.session.commit()
        return job.id
    
    def update_job_status(self, job_id, status, error_message=None):
        job = self.session.query(OCRJob).filter_by(id=job_id).first()
        if job:
            job.status = status
            if status == 'completed':
                job.completed_at = datetime.datetime.utcnow()
            if error_message:
                job.error_message = error_message
            self.session.commit()
    
    def save_result(self, job_id, page_number, text, confidence, processing_time):
        result = OCRResult(
            job_id=job_id,
            page_number=page_number,
            extracted_text=text,
            confidence_score=confidence,
            processing_time=processing_time
        )
        self.session.add(result)
        self.session.commit()

    def get_job(self, job_id):
        return self.session.query(OCRJob).filter_by(id=job_id).first()

    def get_results(self, job_id):
        return self.session.query(OCRResult).filter_by(job_id=job_id).order_by(OCRResult.page_number).all()

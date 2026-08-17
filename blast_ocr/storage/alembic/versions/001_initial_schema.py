"""Initial Database Schema Revision

Revision ID: 001_initial_schema
Revises: 
Create Date: 2026-08-12
"""

from alembic import op
import sqlalchemy as sa

revision = '001_initial_schema'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'ocr_jobs',
        sa.Column('id', sa.Integer(), nullable=False, primary_key=True),
        sa.Column('filename', sa.String(length=255), nullable=False),
        sa.Column('page_count', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
    )

    op.create_table(
        'ocr_results',
        sa.Column('id', sa.Integer(), nullable=False, primary_key=True),
        sa.Column('job_id', sa.Integer(), sa.ForeignKey('ocr_jobs.id'), nullable=True),
        sa.Column('page_number', sa.Integer(), nullable=True),
        sa.Column('extracted_text', sa.Text(), nullable=True),
        sa.Column('confidence_score', sa.Float(), nullable=True),
        sa.Column('processing_time', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )

    op.create_table(
        'ocr_metrics',
        sa.Column('id', sa.Integer(), nullable=False, primary_key=True),
        sa.Column('job_id', sa.Integer(), sa.ForeignKey('ocr_jobs.id'), nullable=True),
        sa.Column('peak_memory_mb', sa.Float(), nullable=True),
        sa.Column('avg_page_time', sa.Float(), nullable=True),
        sa.Column('fidelity_score', sa.Float(), nullable=True),
        sa.Column('extraction_velocity', sa.Float(), nullable=True),
        sa.Column('timestamp', sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table('ocr_metrics')
    op.drop_table('ocr_results')
    op.drop_table('ocr_jobs')

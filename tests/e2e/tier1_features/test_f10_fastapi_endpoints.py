"""
tests/e2e/tier1_features/test_f10_fastapi_endpoints.py

Tier 1 Isolated Feature Tests: Feature 10 - FastAPI Priority & Swarm Endpoints
Covers:
- Priority & retries job dispatch via POST /v1/ocr/jobs
- Live job status and progress tracking via GET /v1/ocr/jobs/{job_id}
- Swarm worker fleet inspection via GET /v1/workers
- Multi-tier queue depth monitoring via GET /v1/queues
- Dead-Letter Queue (DLQ) inspection and replay via POST /v1/ocr/jobs/{job_id}/retry
"""

from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient

from blast_ocr.api.app import app as main_app
from blast_ocr.core.models import JobState
from blast_ocr.storage.database import OCRDatabase


@pytest.fixture(scope="module")
def full_api_client():
    """Test client equipped with real FastAPI routes."""
    return TestClient(main_app)


def test_f10_post_ocr_job_submission(full_api_client, sample_multipage_pdf):
    """
    Test 1: Tests POST /v1/ocr/jobs accepts job parameters (priority, engine, source_path),
    returning HTTP 202 Accepted with a valid job ID and queued status.
    """
    with patch("blast_ocr.api.routes._execute_pipeline_task"):
        response = full_api_client.post(
            "/v1/ocr/jobs",
            data={
                "source_path": str(sample_multipage_pdf),
                "ocr_engine": "rapidocr",
                "priority": "high",
                "max_workers": 2,
                "auto_deskew": True,
            },
        )
        assert response.status_code == 202, f"Expected 202, got {response.status_code}: {response.text}"
        data = response.json()
        assert "job_id" in data
        assert data["job_id"] > 0
        assert data["status"] == "queued"
        assert str(sample_multipage_pdf) in data["source_path"]


def test_f10_get_job_status_and_progress(full_api_client, sample_multipage_pdf):
    """
    Test 2: Tests GET /v1/ocr/jobs/{job_id} returns live job status, progress percentage,
    page counts, and average confidence metrics.
    """
    db = OCRDatabase()
    job_id = db.create_job("status_test.pdf", 4)
    db.save_result(job_id, 1, "Page 1 content", 0.95, 0.2)
    db.save_result(job_id, 2, "Page 2 content", 0.98, 0.25)
    db.close()

    response = full_api_client.get(f"/v1/ocr/jobs/{job_id}")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    
    data = response.json()
    assert data["job_id"] == job_id
    assert data["total_pages"] == 4
    assert data["processed_pages"] == 2
    assert data["progress_percentage"] == 50.0
    assert data["average_confidence"] == round((0.95 + 0.98) / 2, 4)


def test_f10_get_workers_fleet_monitoring(full_api_client):
    """
    Test 3: Tests GET /v1/workers returns active swarm worker registry,
    monitoring status ('idle', 'busy', 'draining'), CPU, memory RSS, and active task info.
    """
    response = full_api_client.get("/v1/workers")
    assert response.status_code == 200
    data = response.json()
    
    assert "workers" in data
    assert "total_active_workers" in data
    assert len(data["workers"]) == data["total_active_workers"]


def test_f10_get_queues_depth_and_dlq_inspection(full_api_client):
    """
    Test 4: Tests GET /v1/queues returns multi-tier queue depths (high, default, low, dlq),
    and GET /v1/queues/dlq returns quarantined jobs with failure reasons.
    """
    # 1. Queue depth summary
    resp_queues = full_api_client.get("/v1/queues")
    assert resp_queues.status_code == 200
    q_data = resp_queues.json()
    assert "queues" in q_data
    assert "blast_ocr:queue:high" in q_data["queues"]
    assert "blast_ocr:queue:default" in q_data["queues"]
    assert "blast_ocr:queue:low" in q_data["queues"]
    assert "blast_ocr:queue:dlq" in q_data["queues"]
    assert q_data["total_pending_jobs"] >= 0

    # 2. DLQ inspection
    resp_dlq = full_api_client.get("/v1/queues/dlq")
    assert resp_dlq.status_code == 200
    dlq_data = resp_dlq.json()
    assert "dlq_jobs" in dlq_data
    assert dlq_data["total_dlq_count"] >= 0


def test_f10_post_job_retry_replays_failed_job(full_api_client):
    """
    Test 5: Tests POST /v1/ocr/jobs/{job_id}/retry resets a failed job's state
    to QUEUED and re-enqueues it with specified priority.
    """
    db = OCRDatabase()
    job_id = db.create_job("failed_job.pdf", 1)
    db.update_job_status(job_id, JobState.FAILED)
    db.close()

    response = full_api_client.post(f"/v1/ocr/jobs/{job_id}/retry?priority=high")
    assert response.status_code == 200
    data = response.json()
    
    assert data["job_id"] == job_id
    assert data["status"] == JobState.QUEUED.value
    assert data["priority"] == "high"
    assert data["retry_count"] == 0

    # Verify database was updated
    db_verify = OCRDatabase()
    job = db_verify.get_job(job_id)
    db_verify.close()
    assert job.status == JobState.QUEUED.value

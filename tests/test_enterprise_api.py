"""
tests/test_enterprise_api.py

Integration tests for FastAPI REST API endpoints.
"""

from fastapi.testclient import TestClient
import pytest
import numpy as np
import cv2
import io

from blast_ocr.api.app import app

client = TestClient(app)


def test_api_root():
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "B.L.A.S.T. OCR Engine"
    assert data["status"] == "operational"
    assert "documentation" in data


def test_api_health():
    response = client.get("/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ("healthy", "degraded")
    assert "registered_engines" in data
    assert "memory_used_mb" in data


def test_api_config():
    response = client.get("/v1/config")
    assert response.status_code == 200
    data = response.json()
    assert data["app_version"] == "3.0.0"
    assert "rapidocr" in data["available_engines"]
    assert "tesseract" in data["available_engines"]
    assert "ensemble" in data["available_engines"]


def test_api_metrics():
    response = client.get("/v1/metrics")
    assert response.status_code == 200


def test_api_job_creation_with_file_upload(tmp_path):
    img = np.full((100, 200, 3), 255, dtype=np.uint8)
    cv2.putText(img, "API Test", (20, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)
    _, enc = cv2.imencode(".png", img)

    file_bytes = io.BytesIO(enc.tobytes())
    files = {"file": ("test_doc.png", file_bytes, "image/png")}
    data = {
        "ocr_engine": "rapidocr",
        "secure_mode": "true",
        "enable_tier0_routing": "true",
        "enable_book_intelligence": "true",
    }

    response = client.post("/v1/ocr/jobs", files=files, data=data)
    assert response.status_code == 202
    res_data = response.json()
    assert "job_id" in res_data
    assert res_data["status"] == "queued"
    job_id = res_data["job_id"]

    # Status check
    st_resp = client.get(f"/v1/ocr/jobs/{job_id}")
    assert st_resp.status_code == 200
    assert st_resp.json()["job_id"] == job_id


def test_api_job_creation_missing_source():
    response = client.post("/v1/ocr/jobs", data={"ocr_engine": "rapidocr"})
    assert response.status_code == 400


def test_api_job_toc_and_chunks(tmp_path):
    img = np.full((100, 200, 3), 255, dtype=np.uint8)
    cv2.putText(img, "CHAPTER 1: Math", (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
    _, enc = cv2.imencode(".png", img)

    file_bytes = io.BytesIO(enc.tobytes())
    files = {"file": ("chapter1.png", file_bytes, "image/png")}
    response = client.post("/v1/ocr/jobs", files=files, data={"ocr_engine": "rapidocr"})
    assert response.status_code == 202
    job_id = response.json()["job_id"]

    # Test TOC endpoint
    toc_resp = client.get(f"/v1/ocr/jobs/{job_id}/toc")
    assert toc_resp.status_code == 200
    assert "toc" in toc_resp.json()

    # Test Chunks endpoint
    chunk_resp = client.get(f"/v1/ocr/jobs/{job_id}/chunks")
    assert chunk_resp.status_code == 200
    assert "chunks" in chunk_resp.json()

    # Test Stream endpoint
    with client.stream("GET", f"/v1/ocr/jobs/{job_id}/stream") as stream_resp:
        assert stream_resp.status_code == 200
        assert stream_resp.headers["content-type"].startswith("text/event-stream")
        first_line = next(stream_resp.iter_lines())
        assert first_line is not None


def test_api_discovery_endpoints():
    # Test llms.txt
    resp_llms = client.get("/llms.txt")
    assert resp_llms.status_code == 200
    assert "B.L.A.S.T. OCR Engine" in resp_llms.text
    assert resp_llms.headers["X-Agent-Discoverable"] == "true"

    # Test llms-full.txt
    resp_full = client.get("/llms-full.txt")
    assert resp_full.status_code == 200
    assert "Complete Technical Specification" in resp_full.text

    # Test robots.txt
    resp_robots = client.get("/robots.txt")
    assert resp_robots.status_code == 200
    assert "GPTBot" in resp_robots.text

    # Test sitemap.xml
    resp_sitemap = client.get("/sitemap.xml")
    assert resp_sitemap.status_code == 200
    assert "urlset" in resp_sitemap.text

    # Test .well-known/ai-plugin.json
    resp_plugin = client.get("/.well-known/ai-plugin.json")
    assert resp_plugin.status_code == 200
    assert resp_plugin.json()["name_for_model"] == "blast_ocr"


import os
import pytest
from fastapi.testclient import TestClient
from main import app
from core.auth import GET_API_KEY

client = TestClient(app)

def test_health_check():
    """
    Test the health endpoint.
    """
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
    # Verify security headers are appended
    assert "Content-Security-Policy" in response.headers
    assert response.headers["X-Frame-Options"] == "DENY"

def test_extract_endpoint_missing_api_key():
    """
    Verify endpoint rejects requests with missing API Key header.
    """
    response = client.post("/api/v1/extract", files={"file": ("dummy.pdf", b"dummy content", "application/pdf")})
    assert response.status_code in (401, 403)  # FastAPI returns 401 or 403 when missing depending on version

def test_extract_endpoint_invalid_api_key():
    """
    Verify endpoint rejects invalid API Key credentials.
    """
    headers = {"X-API-Key": "wrong-key"}
    response = client.post(
        "/api/v1/extract", 
        headers=headers,
        files={"file": ("dummy.pdf", b"dummy content", "application/pdf")}
    )
    assert response.status_code == 401
    assert "Invalid API Key" in response.json()["detail"]

def test_extract_endpoint_invalid_file_extension():
    """
    Verify endpoint rejects non-PDF file uploads.
    """
    headers = {"X-API-Key": GET_API_KEY}
    response = client.post(
        "/api/v1/extract",
        headers=headers,
        files={"file": ("dummy.txt", b"dummy content", "text/plain")}
    )
    assert response.status_code == 400
    assert "Only PDF files are supported" in response.json()["detail"]

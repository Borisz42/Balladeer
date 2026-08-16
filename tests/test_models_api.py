import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_models_status_api():
    res = client.get("/api/models/status")
    assert res.status_code == 200
    data = res.json()
    assert "models" in data
    assert "hardware" in data
    assert "demucs" in data["models"]
    assert "clip-vit" in data["models"]
    assert "mms-fa" in data["models"]
    assert data["models"]["demucs"]["is_cached"] is True
    assert data["models"]["clip-vit"]["is_cached"] is True
    assert data["models"]["mms-fa"]["is_cached"] is True

def test_model_download_trigger_api():
    res = client.post("/api/models/download", json={"model_name": "clip-vit"})
    assert res.status_code == 200
    assert res.json()["status"] == "started"

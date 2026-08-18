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
    assert "siglip2" in data["models"]
    assert "mms-fa" in data["models"]

def test_model_download_trigger_api(monkeypatch):
    import app.api.models
    monkeypatch.setattr(app.api.models, "download_model", lambda *args, **kwargs: None)
    res = client.post("/api/models/download", json={"model_name": "siglip2"})
    assert res.status_code == 200
    assert res.json()["status"] == "started"


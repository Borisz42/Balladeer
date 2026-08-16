import pytest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_shutdown_endpoint():
    with patch("app.api.system.async_shutdown_process", new_callable=AsyncMock):
        res = client.post("/api/system/shutdown")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "shutting_down"
        assert "shutting down cleanly" in data["message"]

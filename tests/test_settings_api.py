import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.config import get_settings

client = TestClient(app)

def test_settings_api_lifecycle():
    settings = get_settings()
    initial_slug = settings.indexing.local_slug
    initial_model = settings.indexing.local_model

    # 1. Get settings
    res = client.get("/api/system/settings")
    assert res.status_code == 200
    data = res.json()
    assert "has_gemini_api_key" in data
    assert "only_local_ai" in data
    assert "local_model" in data
    assert "quotas" in data
    assert "gemini-3.5-flash-lite" in data["quotas"]
    assert initial_slug in data["quotas"]

    # 2. Update settings (only_local_ai = True, local_model = "custom-vlm-4b")
    update_res = client.post(
        "/api/system/settings",
        json={"only_local_ai": True, "local_model": "custom-vlm-4b"}
    )
    assert update_res.status_code == 200
    updated_data = update_res.json()
    assert updated_data["only_local_ai"] is True
    assert updated_data["local_model"] == "custom-vlm-4b"
    assert "local-custom-vlm-4b" in updated_data["quotas"]

    # 3. Restore defaults
    restore_res = client.post(
        "/api/system/settings",
        json={"only_local_ai": False, "local_model": initial_model}
    )
    assert restore_res.status_code == 200
    assert restore_res.json()["only_local_ai"] is False
    assert restore_res.json()["local_model"] == initial_model
    assert initial_slug in restore_res.json()["quotas"]

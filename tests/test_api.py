import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health_endpoint():
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "healthy"
    assert "vram_stats" in data
    assert data["config"]["default_bg_mode"] == "blurred_fill"

def test_project_api_lifecycle():
    # 1. Create project
    create_res = client.post(
        "/api/projects",
        json={
            "title": "Tokyo Journey",
            "narrative_text": "Day 1: Shibuya crossing. Day 2: Mount Fuji."
        }
    )
    assert create_res.status_code == 200
    proj_data = create_res.json()
    project_id = proj_data["id"]
    assert proj_data["title"] == "Tokyo Journey"

    # 2. Get project detail
    get_res = client.get(f"/api/projects/{project_id}")
    assert get_res.status_code == 200
    detail = get_res.json()
    assert detail["project"]["id"] == project_id
    assert len(detail["assets"]) == 0

    # 3. List projects
    list_res = client.get("/api/projects")
    assert list_res.status_code == 200
    assert any(p["id"] == project_id for p in list_res.json())

    # 4. Delete project
    del_res = client.delete(f"/api/projects/{project_id}")
    assert del_res.status_code == 200

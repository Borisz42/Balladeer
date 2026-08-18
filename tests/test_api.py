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

    # 4. Rename project via PUT
    rename_res = client.put(
        f"/api/projects/{project_id}",
        json={"title": "Tokyo Journey Remastered"}
    )
    assert rename_res.status_code == 200
    renamed_detail = rename_res.json()
    assert renamed_detail["project"]["title"] == "Tokyo Journey Remastered"

    # 5. Rename project via PATCH
    patch_res = client.patch(
        f"/api/projects/{project_id}",
        json={"title": "Tokyo Journey Final"}
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["project"]["title"] == "Tokyo Journey Final"

    # 6. Delete project
    del_res = client.delete(f"/api/projects/{project_id}")
    assert del_res.status_code == 200

    # Verify deleted
    verify_res = client.get(f"/api/projects/{project_id}")
    assert verify_res.status_code == 404

def test_project_batch_delete():
    # Create 2 test projects
    p1 = client.post("/api/projects", json={"title": "Batch Test 1", "narrative_text": "text 1"}).json()
    p2 = client.post("/api/projects", json={"title": "Batch Test 2", "narrative_text": "text 2"}).json()

    # Batch delete both
    batch_res = client.post(
        "/api/projects/batch-delete",
        json={"project_ids": [p1["id"], p2["id"]]}
    )
    assert batch_res.status_code == 200
    assert p1["id"] in batch_res.json()["deleted_ids"]
    assert p2["id"] in batch_res.json()["deleted_ids"]

    assert client.get(f"/api/projects/{p1['id']}").status_code == 404
    assert client.get(f"/api/projects/{p2['id']}").status_code == 404


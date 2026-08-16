import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_split_and_reorder_api():
    # 1. Create project
    p = client.post("/api/projects", json={"title": "Split Test", "narrative_text": "Day 1: Test."}).json()
    pid = p["id"]

    # Index sample media
    client.post(f"/api/projects/{pid}/index-directory", json={"directory_path": "sample_media"})

    # Generate music & solve
    client.post(f"/api/projects/{pid}/generate-music", json={"duration_sec": 10.0})
    client.post(f"/api/projects/{pid}/solve-timeline")

    # Get slices
    slices_res = client.get(f"/api/timeline/{pid}/slices")
    slices = slices_res.json()
    assert len(slices) > 0

    first_slice = next((s for s in slices if s["beat_count"] >= 2), None)
    if first_slice:
        split_beat = first_slice["start_beat"] + 1
        split_res = client.post(
            f"/api/timeline/{pid}/slices/{first_slice['id']}/split",
            json={"split_at_beat": split_beat}
        )
        assert split_res.status_code == 200
        new_slices = split_res.json()
        assert len(new_slices) == len(slices) + 1

    # Cleanup
    client.delete(f"/api/projects/{pid}")

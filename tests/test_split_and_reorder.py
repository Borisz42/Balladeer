import pytest
from pathlib import Path
from unittest.mock import MagicMock
from fastapi.testclient import TestClient
from app.main import app
from app.models.demucs_separator import demucs_separator
from app.models.local_vlm import local_vlm

client = TestClient(app)

@pytest.fixture(autouse=True)
def mock_demucs_separation(monkeypatch):
    def fake_separate(master_path, output_dir):
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        voc = out / "vocals.wav"
        acc = out / "accompaniment.wav"
        voc.write_bytes(Path(master_path).read_bytes() if Path(master_path).exists() else b"RIFFfake")
        acc.write_bytes(Path(master_path).read_bytes() if Path(master_path).exists() else b"RIFFfake")
        return {"vocals": voc, "accompaniment": acc}

    monkeypatch.setattr(demucs_separator, "separate", fake_separate)
    monkeypatch.setattr(local_vlm, "generate_story_and_lyrics", lambda acts, narrative_text="", is_instrumental=False: ("[Verse 1]\nSplit test line", "Upbeat travel pop"))

def test_split_and_reorder_api():
    # 1. Create project
    p = client.post("/api/projects", json={"title": "Split Test", "narrative_text": "Day 1: Test."}).json()
    pid = p["id"]

    try:
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
    finally:
        # Cleanup
        client.delete(f"/api/projects/{pid}")

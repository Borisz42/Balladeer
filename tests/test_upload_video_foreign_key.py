import pytest
import uuid
import numpy as np
from pathlib import Path
from app.database import db, ProjectModel
from app.pipeline.indexer import indexer
from app.models.qwen_vlm import qwen_vlm

class MockChatLlama:
    def create_chat_completion(self, messages, max_tokens=256):
        return {
            "choices": [
                {
                    "message": {
                        "content": '{"caption": "A scenic video clip of a journey", "tags": ["video", "scenic"], "quality_score": 8.0}'
                    }
                }
            ]
        }

@pytest.fixture(autouse=True)
def mock_qwen_llm(monkeypatch):
    monkeypatch.setattr(qwen_vlm, "_get_llm", lambda: MockChatLlama())
    monkeypatch.setattr(qwen_vlm, "_loaded_model_name", "local-qwen3.5-4b")

def test_video_indexing_foreign_key_integrity(tmp_path):

    proj_id = f"proj_test_fk_video_{uuid.uuid4().hex[:8]}"
    # 1. Create project
    proj = db.create_project(ProjectModel(
        id=proj_id,
        title="Test Video FK Project",
        narrative_text="A scenic roadtrip"
    ))
    assert proj.id == proj_id

    try:
        # 2. Create a dummy video file
        dummy_video = tmp_path / "sample_action.mp4"
        dummy_video.write_bytes(b"dummy video binary content")

        # 3. Index the video file - should succeed without foreign key constraint errors
        asset = indexer.index_media_file(proj_id, dummy_video)
        assert asset.id.startswith("ast_")
        assert asset.media_type == "video"

        # 4. Verify asset and video segments exist in DB
        with db.get_connection() as conn:
            asset_row = conn.execute("SELECT * FROM media_assets WHERE id = ?", (asset.id,)).fetchone()
            assert asset_row is not None
            segments = conn.execute("SELECT * FROM video_segments WHERE asset_id = ?", (asset.id,)).fetchall()
            assert len(segments) >= 1
    finally:
        db.delete_project(proj_id)

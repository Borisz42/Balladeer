import pytest
import asyncio
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.models.qwen_vlm import qwen_vlm
from app.models.siglip_embedder import siglip_embedder
from app.pipeline.indexer import MediaIndexer
from app.database.database import db
from app.database.models import ProjectModel, MediaAssetModel
from app.core.config import get_settings

@pytest.fixture(autouse=True)
def mock_qwen_llm(monkeypatch):
    from app.core.config import get_settings
    monkeypatch.setattr(get_settings().google_ai, "only_local_ai", True)
    monkeypatch.setattr(qwen_vlm, "_get_model_and_processor", lambda: (MagicMock(), MagicMock()))
    monkeypatch.setattr(qwen_vlm, "_generate_vlm_output", lambda m, p, img, txt: '{"caption": "A couple taking a mirror selfie in a warm bedroom setting with soft natural lighting", "tags": ["couple", "selfie", "portrait", "bedroom"], "quality_score": 8.8}')
    monkeypatch.setattr(qwen_vlm, "_loaded_model_name", "local-qwen3.5-4b")




def test_local_ai_photo_vision_semantic_quality():
    sample_photos = [
        Path("sample_media/portrait_day1.jpg"),
        Path("sample_media/square_day2.jpg"),
        Path("sample_media/landscape_day3.jpg")
    ]
    existing = [p for p in sample_photos if p.exists()]
    assert len(existing) >= 2

    for photo in existing:
        analysis = qwen_vlm.describe_and_score(photo)
        caption = analysis["caption"]
        assert isinstance(caption, str) and len(caption) > 10
        assert not caption.startswith("Scenic capture of 2026")

        tags = analysis["tags"]
        assert isinstance(tags, list) and len(tags) >= 2

        quality = analysis["quality_score"]
        assert isinstance(quality, float)
        assert 1.0 <= quality <= 10.0

        emb = siglip_embedder.encode(photo)
        assert len(emb) == 768
        assert abs(sum(x*x for x in emb) - 1.0) < 0.01

def test_local_ai_video_indexing_and_subsegments():
    async def _run():
        indexer = MediaIndexer()
        proj_id = "test_proj_local_video_ai"
        db.create_project(ProjectModel(id=proj_id, title="Local Video AI Test", narrative_text="Action trip"))

        settings = get_settings()
        prev_local_mode = settings.google_ai.only_local_ai
        settings.google_ai.only_local_ai = True

        try:
            sample_photo = Path("sample_media/portrait_day1.jpg")
            assert sample_photo.exists()

            asset_id = f"ast_video_test_{proj_id}"
            video_asset = MediaAssetModel(
                id=asset_id,
                project_id=proj_id,
                file_path=str(sample_photo.resolve()),
                media_type="video",
                duration_sec=6.0,
                is_indexed=False
            )
            db.add_media_asset(video_asset)

            indexer.generate_thumbnail(sample_photo, asset_id, "video")
            thumb_path = indexer.get_thumbnail_path(asset_id)
            assert thumb_path.exists()

            indexed = await indexer.index_pending_assets(proj_id)
            assert len(indexed) == 1
            updated_vid = indexed[0]

            assert updated_vid.is_indexed is True
            assert "qwen" in updated_vid.indexed_by_model.lower()
            assert len(updated_vid.caption) > 10
            assert updated_vid.quality_score >= 1.0

            with db.get_connection() as conn:
                segs = conn.execute("SELECT * FROM video_segments WHERE asset_id = ?", (asset_id,)).fetchall()
                assert len(segs) >= 2

            reindexed = await indexer.reindex_single_asset(proj_id, asset_id)
            assert reindexed is not None
            assert reindexed.is_indexed is True

        finally:
            settings.google_ai.only_local_ai = prev_local_mode
            db.delete_project(proj_id)

    asyncio.run(_run())

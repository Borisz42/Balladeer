import pytest
import asyncio
from pathlib import Path
from app.pipeline.indexer import MediaIndexer
from app.database.database import db
from app.database.models import ProjectModel
from app.models.qwen_vlm import qwen_vlm


class MockChatLlama:
    def create_chat_completion(self, messages, max_tokens=256):
        return {
            "choices": [
                {
                    "message": {
                        "content": '{"caption": "A scenic landscape during golden hour", "tags": ["landscape", "scenic"], "quality_score": 8.5}'
                    }
                }
            ]
        }

@pytest.fixture(autouse=True)
def mock_qwen_llm(monkeypatch):
    monkeypatch.setattr(qwen_vlm, "_get_llm", lambda: MockChatLlama())
    monkeypatch.setattr(qwen_vlm, "_loaded_model_name", "local-qwen3.5-4b")

def test_parallel_batch_indexing():
    async def _run():
        indexer = MediaIndexer()
        proj_id = "test_proj_batch_idx"
        db.create_project(ProjectModel(id=proj_id, title="Batch Test", narrative_text="Day 1 in Kyoto."))


        try:
            sample_files = [
                Path("sample_media/portrait_day1.jpg"),
                Path("sample_media/square_day2.jpg"),
                Path("sample_media/landscape_day3.jpg")
            ]
            existing_files = [f for f in sample_files if f.exists()]
            assert len(existing_files) >= 2

            progress_msgs = []
            async def on_progress(msg, pct):
                progress_msgs.append((msg, pct))

            assets = await indexer.index_media_batch(
                project_id=proj_id,
                file_paths=existing_files,
                batch_size=2,
                progress_callback=on_progress
            )

            assert len(assets) == len(existing_files)
            for a in assets:
                assert a.project_id == proj_id
                assert len(a.embedding) == 512
                assert a.quality_score >= 1.0
                assert a.is_indexed is True
                assert a.indexed_by_model is not None

            assert len(progress_msgs) > 0
        finally:
            db.delete_project(proj_id)

    asyncio.run(_run())

def test_two_step_media_indexing_and_user_editing():
    async def _run():
        indexer = MediaIndexer()
        proj_id = "test_proj_two_step"
        db.create_project(ProjectModel(id=proj_id, title="Two Step Test", narrative_text="Tokyo trip."))

        try:
            sample_files = [
                Path("sample_media/portrait_day1.jpg"),
                Path("sample_media/square_day2.jpg")
            ]
            existing_files = [f for f in sample_files if f.exists()]

            # Step 1: Rapid Staging
            staged = indexer.stage_media_files(proj_id, existing_files)
            assert len(staged) == len(existing_files)
            for s in staged:
                assert s.is_indexed is False
                assert s.indexed_by_model is None
                assert s.width is not None

            # Verify thumbnail generation
            for s in staged:
                thumb_path = indexer.get_thumbnail_path(s.id)
                assert thumb_path.exists()

            # Step 2: Batch indexing of pending files
            indexed = await indexer.index_pending_assets(proj_id)
            assert len(indexed) == len(existing_files)
            for item in indexed:
                assert item.is_indexed is True
                assert item.indexed_by_model is not None
                assert item.embedding is not None

            # Step 3: User Editing of Asset
            target_asset = indexed[0]
            updated = db.update_media_asset(target_asset.id, {
                "caption": "Custom user description of cherry blossoms",
                "quality_score": 9.5,
                "tags": ["sakura", "kyoto", "spring"]
            })
            assert updated.caption == "Custom user description of cherry blossoms"
            assert updated.quality_score == 9.5
            assert "sakura" in updated.tags

        finally:
            db.delete_project(proj_id)

    asyncio.run(_run())

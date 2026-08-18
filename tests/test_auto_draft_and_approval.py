import pytest
import asyncio
import os
from pathlib import Path
from PIL import Image
from unittest.mock import MagicMock

from app.database.database import db
from app.database.models import ProjectModel, MediaAssetModel
from app.pipeline.indexer import media_indexer as indexer
from app.pipeline.rephraser import diary_rephraser
from app.api.projects import draft_travel_log, approve_travel_log, ApproveTravelLogRequest
from app.models.qwen_vlm import qwen_vlm

from app.models.siglip_embedder import siglip_embedder

@pytest.fixture(autouse=True)
def mock_qwen_llm(monkeypatch):
    from app.core.config import get_settings
    monkeypatch.setattr(get_settings().google_ai, "only_local_ai", True)
    monkeypatch.setattr(qwen_vlm, "_get_model_and_processor", lambda: (MagicMock(), MagicMock()))
    monkeypatch.setattr(qwen_vlm, "_generate_vlm_output", lambda m, p, img, txt: '{"caption": "A scenic landscape during golden hour", "tags": ["landscape", "scenic"], "quality_score": 8.5}')
    monkeypatch.setattr(qwen_vlm, "_loaded_model_name", "local-qwen3.5-4b")
    
    # Fast mock for SigLIP 2 embeddings
    dummy_vec = [0.05] * 768
    monkeypatch.setattr(siglip_embedder, "encode_text", lambda text: dummy_vec)
    monkeypatch.setattr(siglip_embedder, "encode", lambda path: dummy_vec)
    monkeypatch.setattr(siglip_embedder, "encode_images_batch", lambda imgs: [dummy_vec for _ in imgs])
    monkeypatch.setattr(siglip_embedder, "compute_aesthetic_score", lambda p: 8.0)
    monkeypatch.setattr(siglip_embedder, "get_aesthetic_anchors", lambda: (dummy_vec, [-0.05] * 768))

def test_auto_draft_and_deferred_relevance(tmp_path):
    async def _run():
        # 1. Create temporary sample photos with different dates/captions
        img1_path = tmp_path / "day1_tokyo.jpg"
        img2_path = tmp_path / "day2_kyoto.jpg"
        
        img = Image.new("RGB", (100, 100), color=(100, 150, 200))
        img.save(img1_path)
        img.save(img2_path)

        # 2. Create project in auto_draft mode (unapproved)
        proj_id = "proj_test_auto_draft_1"
        proj = ProjectModel(
            id=proj_id,
            title="Japan Winter Tour",
            narrative_text="",
            status="created",
            config_override={
                "travel_log_mode": "auto_draft",
                "travel_log_approved": False
            }
        )
        db.create_project(proj)

        # 3. Stage and index assets
        staged = indexer.stage_media_files(proj_id, [img1_path, img2_path])
        assert len(staged) == 2

        # Set mock capture times and captions
        db.update_media_asset(staged[0].id, {
            "capture_time": "2026-02-10T10:00:00",
            "caption": "Shinjuku neon lights and street ramen",
            "tags": ["tokyo", "night", "city"]
        })
        db.update_media_asset(staged[1].id, {
            "capture_time": "2026-02-11T14:30:00",
            "caption": "Fushimi Inari golden shrine gates and tranquil forest",
            "tags": ["kyoto", "temple", "nature"]
        })

        # Index pending assets in auto_draft mode
        indexed = await indexer.index_pending_assets(proj_id)
        assert len(indexed) == 2

        # Verify that relevance scores are NOT calculated (remain 0.0) during initial indexing
        for asset in indexed:
            db_asset = db.get_asset(asset.id)
            assert db_asset.is_indexed is True
            assert db_asset.relevance_score_daily == 0.0
            assert db_asset.relevance_score_overall == 0.0

        # 4. Draft Travel Log from Media
        draft_res = await draft_travel_log(proj_id)
        assert draft_res["status"] == "drafted"
        draft = draft_res["draft"]
        assert len(draft["diary_days"]) >= 1
        assert "narrative_text" in draft
        assert len(draft["narrative_text"]) > 0

        # Verify project was updated with drafted diary days
        updated_proj = db.get_project(proj_id)
        assert len(updated_proj.narrative_text) > 0
        assert len(updated_proj.config_override["diary_days"]) >= 1
        assert updated_proj.config_override.get("travel_log_approved") is False

        # 5. User Reviews and Approves Travel Log
        approve_req = ApproveTravelLogRequest(
            title="Japan Winter Tour (Approved)",
            narrative_text=updated_proj.narrative_text,
            config_override=updated_proj.config_override
        )
        approved_detail = await approve_travel_log(proj_id, approve_req)
        
        # 6. Verify relevance scores are now calculated and non-zero
        assert approved_detail.project.config_override["travel_log_approved"] is True
        
        scored_assets = db.get_project_assets(proj_id)
        for asset in scored_assets:
            assert asset.relevance_score_overall > 0.0
            assert asset.relevance_score_daily > 0.0
            assert any(tag.startswith("day:") for tag in asset.tags)

    asyncio.run(_run())

def test_manual_mode_calculates_relevance_immediately(tmp_path):
    async def _run():
        img_path = tmp_path / "manual_test.jpg"
        img = Image.new("RGB", (80, 80), color=(120, 80, 200))
        img.save(img_path)

        proj_id = "proj_test_manual_mode_1"
        proj = ProjectModel(
            id=proj_id,
            title="Kyoto Traditional Exploration",
            narrative_text="Day 1: Explored ancient temples and serene gardens in Kyoto.",
            status="created",
            config_override={
                "travel_log_mode": "manual",
                "travel_log_approved": True,
                "diary_days": [
                    {
                        "day_number": 1,
                        "date": "2026-03-01",
                        "title": "Ancient Kyoto",
                        "events": "Explored ancient temples and serene gardens in Kyoto."
                    }
                ]
            }
        )
        db.create_project(proj)

        staged = indexer.stage_media_files(proj_id, [img_path])
        db.update_media_asset(staged[0].id, {
            "capture_time": "2026-03-01T09:00:00",
            "caption": "Golden Pavilion reflecting on quiet waters"
        })

        indexed = await indexer.index_pending_assets(proj_id)
        assert len(indexed) == 1
        # In manual mode with approved log, relevance is calculated immediately
        assert indexed[0].relevance_score_overall > 0.0
        assert indexed[0].relevance_score_daily > 0.0

    asyncio.run(_run())

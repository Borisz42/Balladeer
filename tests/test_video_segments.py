import json
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

from app.main import app
from app.database.database import db
from app.database.models import ProjectModel, MediaAssetModel, VideoSegmentModel
from app.pipeline.indexer import MediaIndexer

client = TestClient(app)

def test_video_subsegments_extraction(tmp_path):
    indexer = MediaIndexer()
    dummy_video = tmp_path / "trip_clip.mp4"
    dummy_video.touch()

    # Test subsegments for a 9.0 second video
    segs = indexer.extract_video_subsegments(dummy_video, "asset_test_vid", 9.0)
    assert len(segs) == 3
    assert segs[0].start_time == 0.0
    assert segs[0].end_time == 3.0
    assert 0.0 <= segs[0].motion_score <= 1.0
    assert segs[1].start_time == 3.0
    assert segs[2].end_time == 9.0

def test_video_segments_and_frame_scores_api():
    proj_id = "test_proj_segments_api"
    asset_id = "ast_video_seg_test_1"
    
    db.create_project(ProjectModel(id=proj_id, title="Segments API Test", narrative_text="Trip to Kyoto"))
    try:
        sample_img = Path("sample_media/portrait_day1.jpg")
        asset = MediaAssetModel(
            id=asset_id,
            project_id=proj_id,
            file_path=str(sample_img.resolve()),
            media_type="video",
            duration_sec=6.0,
            quality_score=8.5,
            relevance_score_daily=0.88,
            relevance_score_overall=0.79,
            is_indexed=True
        )
        db.add_media_asset(asset)

        # Create mock segments with frame scores
        frame_points_1 = [
            {"t": 0.0, "s_rel": 0.85, "s_aes": 0.70, "s_comp": 0.80},
            {"t": 1.0, "s_rel": 0.88, "s_aes": 0.75, "s_comp": 0.84},
            {"t": 2.0, "s_rel": 0.90, "s_aes": 0.80, "s_comp": 0.87}
        ]
        frame_points_2 = [
            {"t": 3.0, "s_rel": 0.82, "s_aes": 0.72, "s_comp": 0.79},
            {"t": 4.0, "s_rel": 0.86, "s_aes": 0.78, "s_comp": 0.84},
            {"t": 5.0, "s_rel": 0.89, "s_aes": 0.82, "s_comp": 0.87}
        ]

        seg1 = VideoSegmentModel(
            id="seg_test_1_0",
            asset_id=asset_id,
            start_time=0.0,
            end_time=3.0,
            motion_score=0.84,
            relevance_score=0.88,
            best_shot_start=1.0,
            best_shot_end=3.0,
            description="Bamboo grove entrance",
            frame_scores=json.dumps(frame_points_1)
        )
        seg2 = VideoSegmentModel(
            id="seg_test_1_1",
            asset_id=asset_id,
            start_time=3.0,
            end_time=6.0,
            motion_score=0.87,
            relevance_score=0.86,
            best_shot_start=3.5,
            best_shot_end=5.5,
            description="Shrine pathway",
            frame_scores=json.dumps(frame_points_2)
        )
        db.save_video_segments([seg1, seg2])

        # Test Segments API
        res_segs = client.get(f"/api/projects/{proj_id}/assets/{asset_id}/segments")
        assert res_segs.status_code == 200
        segs_data = res_segs.json()
        assert len(segs_data) == 2
        assert segs_data[0]["best_shot_start"] == 1.0
        assert segs_data[0]["relevance_score"] == 0.88
        assert segs_data[1]["best_shot_end"] == 5.5

        # Test Frame Scores API
        res_scores = client.get(f"/api/projects/{proj_id}/assets/{asset_id}/frame-scores")
        assert res_scores.status_code == 200
        scores_data = res_scores.json()
        assert scores_data["asset_id"] == asset_id
        assert len(scores_data["frame_scores"]) == 6
        assert scores_data["frame_scores"][0]["s_comp"] == 0.80
        assert len(scores_data["segments"]) == 2

        # Verify dual relevance scores on Project Asset Model API
        res_proj = client.get(f"/api/projects/{proj_id}")
        assert res_proj.status_code == 200
        assets_data = res_proj.json()["assets"]
        assert len(assets_data) == 1
        assert assets_data[0]["relevance_score_daily"] == 0.88
        assert assets_data[0]["relevance_score_overall"] == 0.79

    finally:
        db.delete_project(proj_id)

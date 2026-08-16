import pytest
import numpy as np
from pathlib import Path
from app.database.database import Database
from app.database.models import ProjectModel, MediaAssetModel, TimelineSliceModel, AudioTrackModel

def test_database_lifecycle(tmp_path):
    test_db_path = tmp_path / "test_balladeer.db"
    db = Database(db_path=test_db_path)

    # 1. Create project
    proj = ProjectModel(
        id="test_proj_1",
        title="Kyoto Trip",
        narrative_text="Day 1: Arrived in Kyoto. Day 2: Bamboo forest."
    )
    db.create_project(proj)
    fetched = db.get_project("test_proj_1")
    assert fetched is not None
    assert fetched.title == "Kyoto Trip"

    # 2. Add media asset with embeddings
    emb1 = [0.1] * 512
    emb2 = [0.9] * 512
    asset1 = MediaAssetModel(
        id="asset_1",
        project_id="test_proj_1",
        file_path="kyoto_morning.jpg",
        media_type="image",
        quality_score=8.5,
        caption="Morning in Kyoto",
        embedding=emb1
    )
    asset2 = MediaAssetModel(
        id="asset_2",
        project_id="test_proj_1",
        file_path="bamboo.jpg",
        media_type="image",
        quality_score=9.0,
        caption="Arashiyama Bamboo",
        embedding=emb2
    )
    db.add_media_asset(asset1)
    db.add_media_asset(asset2)

    assets = db.get_project_assets("test_proj_1")
    assert len(assets) == 2

    # 3. Vector similarity search
    results = db.search_similar_assets(
        project_id="test_proj_1",
        target_embedding=[0.85] * 512,
        top_k=2
    )
    assert len(results) == 2
    assert results[0][0].id == "asset_2" # asset2 is closest to [0.85]*512
    assert results[0][1] > 0.99

    # 4. Save and fetch timeline slices
    track = AudioTrackModel(
        id="trk_1",
        project_id="test_proj_1",
        master_path="test_master.wav",
        bpm=120.0
    )
    db.save_audio_track(track)

    slice1 = TimelineSliceModel(
        id="sl_1",
        project_id="test_proj_1",
        audio_track_id="trk_1",
        asset_id="asset_1",
        start_beat=0,
        beat_count=2,
        timeline_start_sec=0.0,
        timeline_end_sec=1.0,
        clip_order=0,
        bg_mode="blurred_fill",
        enable_ken_burns=False
    )
    db.save_timeline_slices("test_proj_1", [slice1])
    slices = db.get_timeline_slices("test_proj_1")
    assert len(slices) == 1
    assert slices[0].bg_mode == "blurred_fill"
    assert slices[0].asset is not None
    assert slices[0].asset.caption == "Morning in Kyoto"

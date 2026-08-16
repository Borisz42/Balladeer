import pytest
from pathlib import Path
from app.pipeline.indexer import MediaIndexer

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

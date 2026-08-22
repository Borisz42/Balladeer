import pytest
from app.pipeline.beat_solver import BeatSolver
from app.database.models import MediaAssetModel, AudioTrackModel, AlignedWordModel
from app.core.config import get_settings

def test_beat_solver_config_ranges():
    settings = get_settings()
    solver = BeatSolver(settings)

    # 120 BPM = 0.5s per beat, 10 beats total (5.0s)
    beat_grid = [round(i * 0.5, 4) for i in range(10)]
    downbeats = [0.0, 2.0, 4.0]
    
    track = AudioTrackModel(
        id="trk_test",
        project_id="proj_test",
        master_path="dummy.wav",
        bpm=120.0,
        beat_grid=beat_grid,
        downbeats=downbeats,
        aligned_lyrics=[
            AlignedWordModel(word="Hello", start=0.0, end=0.4, snapped_start=0.0, snapped_end=0.5, beat_index=0)
        ]
    )

    assets = [
        MediaAssetModel(
            id="p1",
            project_id="proj_test",
            file_path="photo1.jpg",
            media_type="image",
            quality_score=8.0,
            caption="Sunrise"
        ),
        MediaAssetModel(
            id="v1",
            project_id="proj_test",
            file_path="video1.mp4",
            media_type="video",
            quality_score=9.0,
            caption="Action walk"
        ),
        MediaAssetModel(
            id="p2",
            project_id="proj_test",
            file_path="photo2.jpg",
            media_type="image",
            quality_score=7.5,
            caption="Sunset"
        )
    ]

    slices = solver.solve_timeline(
        project_id="proj_test",
        audio_track=track,
        assets=assets
    )

    assert len(slices) > 0
    total_allocated_beats = sum(s.beat_count for s in slices)
    assert total_allocated_beats == len(beat_grid)

    # Verify each photo slice satisfies photo_beat_range [1, 3]
    # and video satisfies video_beat_range [2, 5]
    photo_min, photo_max = settings.video.photo_beat_range
    vid_min, vid_max = settings.video.video_beat_range

    for s in slices:
        matched_asset = next(a for a in assets if a.id == s.asset_id)
        if matched_asset.media_type == "image":
            assert photo_min <= s.beat_count <= photo_max
        elif matched_asset.media_type == "video":
            assert vid_min <= s.beat_count <= vid_max
        assert s.bg_mode == "blurred_fill"

def test_beat_solver_strict_chronological_order_and_single_shot():
    solver = BeatSolver()

    # 120 BPM = 0.5s per beat, 16 beats = 8.0s (fits ~4 photos of 2 beats each)
    beat_grid = [round(i * 0.5, 4) for i in range(16)]
    track = AudioTrackModel(
        id="trk_chrono",
        project_id="proj_chrono",
        master_path="dummy.wav",
        bpm=120.0,
        beat_grid=beat_grid,
        downbeats=[0.0, 2.0, 4.0, 6.0]
    )

    # Assets across Day 1 and Day 2 with timestamps
    assets = [
        MediaAssetModel(id="d2_p1", project_id="proj_chrono", file_path="d2_1.jpg", media_type="image", capture_time="2026-06-02T10:00:00Z", tags=["day:Day 2"]),
        MediaAssetModel(id="d1_p2", project_id="proj_chrono", file_path="d1_2.jpg", media_type="image", capture_time="2026-06-01T14:00:00Z", tags=["day:Day 1"]),
        MediaAssetModel(id="d1_p1", project_id="proj_chrono", file_path="d1_1.jpg", media_type="image", capture_time="2026-06-01T09:00:00Z", tags=["day:Day 1"]),
        MediaAssetModel(id="d2_p2", project_id="proj_chrono", file_path="d2_2.jpg", media_type="image", capture_time="2026-06-02T16:00:00Z", tags=["day:Day 2"]),
    ]

    slices = solver.solve_timeline(
        project_id="proj_chrono",
        audio_track=track,
        assets=assets
    )

    assert len(slices) >= 4
    placed_ids = [s.asset_id for s in slices[:4]]

    # Must be placed in strict chronological order: Day 1 (09:00 -> 14:00), then Day 2 (10:00 -> 16:00)
    assert placed_ids == ["d1_p1", "d1_p2", "d2_p1", "d2_p2"]

    # Must use each shot only once (0 duplicates in first 4 slices)
    assert len(set(placed_ids)) == 4

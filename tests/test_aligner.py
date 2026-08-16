import pytest
from pathlib import Path
from app.pipeline.aligner import AudioAligner
from app.pipeline.music_gen import MusicGenerator

def test_beat_snapping():
    aligner = AudioAligner()
    beat_grid = [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0]

    # Timestamp within tolerance (0.25s) of 1.0s -> snaps to 1.0
    snapped, beat_idx = aligner.snap_to_beat(1.08, beat_grid, tolerance_sec=0.25)
    assert snapped == 1.0
    assert beat_idx == 2

    # Timestamp outside tolerance (e.g. 1.25s is 0.25s away from 1.0 and 1.5)
    snapped2, beat_idx2 = aligner.snap_to_beat(1.24, beat_grid, tolerance_sec=0.20)
    # If not within 0.20s of nearest beat (0.24 away from 1.0, 0.26 away from 1.5)
    assert snapped2 == 1.24

def test_music_synthesis_and_beat_extraction(tmp_path):
    music_gen = MusicGenerator()
    aligner = AudioAligner()

    # Generate a short 4-second audio track
    res = music_gen.synthesize_music_track(
        project_id="test_audio",
        lyrics="Walking in the sun\nHaving lots of fun",
        prompt="Acoustic pop",
        bpm=120.0,
        target_duration_sec=4.0
    )

    assert Path(res["master_path"]).exists()
    assert Path(res["vocal_path"]).exists()
    assert Path(res["accompaniment_path"]).exists()

    bpm, beat_grid, downbeats = aligner.extract_beat_grid(res["master_path"])
    assert bpm > 0
    assert len(beat_grid) >= 4
    assert len(downbeats) >= 1

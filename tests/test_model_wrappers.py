import pytest
from pathlib import Path
from app.models.qwen_vlm import qwen_vlm
from app.models.minimax_music import minimax_music
from app.models.demucs_wrapper import demucs_separator
from app.models.mms_aligner import mms_aligner

def test_qwen_vlm_heuristic():
    res = qwen_vlm.describe_and_score(Path("sample_media/portrait_day1.jpg"), "portrait_day1.jpg")
    assert "caption" in res
    assert "tags" in res
    assert 1.0 <= res["quality_score"] <= 10.0

def test_minimax_music_engine():
    stems = minimax_music.generate(
        lyrics="Day 1 in the city\nDay 2 in the wild",
        prompt="Acoustic pop",
        bpm=120.0,
        target_duration_sec=3.0,
        is_instrumental=False
    )
    assert "master" in stems
    assert "vocals" in stems
    assert "accompaniment" in stems
    assert len(stems["master"]) > 0

def test_mms_aligner():
    beat_grid = [0.0, 0.5, 1.0, 1.5, 2.0]
    words = mms_aligner.align(
        vocal_path=Path("data/output/test/vocals.wav"),
        lyrics="Walking under golden sunrise",
        beat_grid=beat_grid
    )
    assert len(words) >= 4
    for w in words:
        assert w.snapped_start in beat_grid or w.snapped_start >= 0.0

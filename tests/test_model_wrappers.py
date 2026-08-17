import pytest
from pathlib import Path
from unittest.mock import MagicMock
from app.models.qwen_vlm import qwen_vlm
from app.models.minimax_music import minimax_music
from app.models.demucs_wrapper import demucs_separator
from app.models.mms_aligner import mms_aligner

class MockChatLlama:
    def create_chat_completion(self, messages, max_tokens=256):
        return {
            "choices": [
                {
                    "message": {
                        "content": '{"caption": "A scenic portrait photo with vivid colors", "tags": ["portrait", "scenic"], "quality_score": 8.0}'
                    }
                }
            ]
        }

def test_qwen_vlm_heuristic(monkeypatch):
    monkeypatch.setattr(qwen_vlm, "_get_llm", lambda: MockChatLlama())
    monkeypatch.setattr(qwen_vlm, "_loaded_model_name", "local-qwen3.5-4b")
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

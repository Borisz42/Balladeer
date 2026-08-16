import pytest
import os
import numpy as np
from unittest.mock import patch, MagicMock
from app.models.comfy_music_worker import ComfyUIHeadlessWorker, comfy_music_worker
from app.models.minimax_music import MiniMaxMusicEngine
from app.models.cmf_runner import CMFNativeRunner

def test_comfy_worker_build_prompt_graph():
    worker = ComfyUIHeadlessWorker()
    graph = worker.build_prompt_graph(
        lyrics="[Verse 1]\nMemories alive in the sunshine",
        prompt="Cinematic indie folk acoustic guitar",
        bpm=120.0,
        target_duration_sec=30.0,
        is_instrumental=False
    )
    assert "1" in graph
    assert "3" in graph
    assert graph["3"]["inputs"]["bpm"] == 120
    assert graph["3"]["inputs"]["is_instrumental"] is False
    assert "Memories alive" in graph["3"]["inputs"]["lyrics"]

def test_comfy_worker_fallback_when_offline():
    worker = ComfyUIHeadlessWorker()
    with patch.object(worker, "is_available", return_value=False):
        res = worker.generate(
            lyrics="Hello world",
            prompt="Electronic beat",
            bpm=128.0,
            target_duration_sec=10.0
        )
        assert res is None

def test_minimax_engine_with_comfy_audio():
    engine = MiniMaxMusicEngine()
    fake_audio = np.zeros(32000 * 5, dtype=np.float32)
    with patch("app.models.minimax_music.comfy_music_worker.generate", return_value=fake_audio):
        stems = engine.generate(
            lyrics="[Chorus]\nSing along",
            prompt="Pop upbeat",
            bpm=120.0,
            target_duration_sec=5.0,
            is_instrumental=False
        )
        assert "master" in stems
        assert "vocals" in stems
        assert "accompaniment" in stems
        assert len(stems["master"]) == 32000 * 5

def test_minimax_engine_with_cmf_runner_audio():
    engine = MiniMaxMusicEngine()
    fake_audio = np.zeros(32000 * 4, dtype=np.float32)
    with patch("app.models.minimax_music.comfy_music_worker.generate", return_value=None), \
         patch("app.models.minimax_music.cmf_runner.generate_music", return_value=fake_audio):
        stems = engine.generate(
            lyrics="[Verse 1]\nWalking down the road",
            prompt="Acoustic guitar",
            bpm=110.0,
            target_duration_sec=4.0
        )
        assert len(stems["master"]) == 32000 * 4

def test_minimax_engine_strict_error_when_all_offline():
    engine = MiniMaxMusicEngine()
    # Temporarily unset PYTEST_CURRENT_TEST to verify strict exception behavior
    with patch.dict(os.environ, {"PYTEST_CURRENT_TEST": ""}), \
         patch("app.models.minimax_music.comfy_music_worker.generate", return_value=None), \
         patch("app.models.minimax_music.cmf_runner.generate_music", return_value=None):
        with pytest.raises(RuntimeError) as exc_info:
            engine.generate(
                lyrics="Test lyrics",
                prompt="Test prompt",
                bpm=120.0,
                target_duration_sec=5.0
            )
        assert "MiniMax Music 3 Error" in str(exc_info.value)

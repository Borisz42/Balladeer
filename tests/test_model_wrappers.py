import pytest
from pathlib import Path
from unittest.mock import MagicMock
from app.models.local_vlm import local_vlm
from app.models.siglip_embedder import siglip_embedder
from app.models.demucs_wrapper import demucs_separator
from app.models.mms_aligner import mms_aligner

def test_local_vlm_heuristic(monkeypatch):
    monkeypatch.setattr(local_vlm, "_get_model_and_processor", lambda: (MagicMock(), MagicMock()))
    monkeypatch.setattr(local_vlm, "_generate_vlm_output", lambda m, p, img, txt: '{"caption": "A scenic portrait photo with vivid colors", "tags": ["portrait", "scenic"], "quality_score": 8.0}')
    res = local_vlm.describe_and_score(Path("sample_media/portrait_day1.jpg"), "portrait_day1.jpg")
    assert "caption" in res
    assert "tags" in res
    assert 1.0 <= res["quality_score"] <= 10.0
    assert "embedding" not in res  # Embedding must only be computed once in the indexer

def test_local_vlm_markdown_fenced_json(monkeypatch):
    monkeypatch.setattr(local_vlm, "_get_model_and_processor", lambda: (MagicMock(), MagicMock()))
    monkeypatch.setattr(local_vlm, "_generate_vlm_output", lambda m, p, img, txt: '```json\n{\n  "caption": "A couple poses together in a sunny art gallery with paintings.",\n  "tags": ["couple", "gallery", "art"],\n  "quality_score": 8.7\n}\n```')
    res = local_vlm.describe_and_score(Path("sample_media/portrait_day1.jpg"), "portrait_day1.jpg")
    assert res["caption"] == "A couple poses together in a sunny art gallery with paintings."
    assert "gallery" in res["tags"]
    assert res["quality_score"] == 8.7

def test_local_vlm_malformed_fence_fallback(monkeypatch):
    monkeypatch.setattr(local_vlm, "_get_model_and_processor", lambda: (MagicMock(), MagicMock()))
    monkeypatch.setattr(local_vlm, "_generate_vlm_output", lambda m, p, img, txt: "```json\n")
    res = local_vlm.describe_and_score(Path("sample_media/portrait_day1.jpg"), "portrait_day1.jpg")
    assert res["caption"].startswith("Travel scene:")
    assert not res["caption"].startswith("```")
    assert len(res["caption"]) > 8

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

def test_siglip_prewarm_and_clear_cache(monkeypatch):
    import asyncio
    called = []
    monkeypatch.setattr(siglip_embedder, "_get_processor_and_model", lambda: called.append(True) or (MagicMock(), MagicMock()))
    asyncio.run(siglip_embedder.prewarm_async())
    assert len(called) == 1
    siglip_embedder.clear_cache()
    assert siglip_embedder._model is None

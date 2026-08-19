import pytest
from pathlib import Path
from fastapi.testclient import TestClient
from app.main import app
from app.database.database import db
from app.database.models import AlignedWordModel, AudioTrackModel
from app.pipeline.aligner import aligner
from app.pipeline.compositor import VideoCompositor
from app.models.demucs_separator import demucs_separator
from app.models.local_vlm import local_vlm

client = TestClient(app)

@pytest.fixture(autouse=True)
def mock_demucs_separation(monkeypatch):
    def fake_separate(master_path, output_dir):
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        voc = out / "vocals.wav"
        acc = out / "accompaniment.wav"
        voc.write_bytes(Path(master_path).read_bytes() if Path(master_path).exists() else b"RIFFfake")
        acc.write_bytes(Path(master_path).read_bytes() if Path(master_path).exists() else b"RIFFfake")
        return {"vocals": voc, "accompaniment": acc}

    monkeypatch.setattr(demucs_separator, "separate", fake_separate)
    monkeypatch.setattr(
        local_vlm,
        "generate_story_and_lyrics",
        lambda acts, narrative_text="", is_instrumental=False: (
            "[Verse 1]\nWalking down the cobblestone street\nSunlight dancing at our feet\n\n[Chorus]\nMemories carved in stone\nNever walking all alone",
            "Uplifting acoustic travel indie pop"
        )
    )

def test_mms_aligner_line_index():
    """Verify MMS aligner accurately groups words by lyric line and assigns line_index."""
    lyrics = "[Verse 1]\nGolden morning sun\nWalking on the shore\n\n[Chorus]\nEndless blue horizons"
    aligned = aligner.align_lyrics_mms_fa(
        vocal_path=Path("sample_media"),
        lyrics_text=lyrics,
        beat_grid=[0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0]
    )

    assert len(aligned) > 0
    # First 3 words belong to line 0 ("Golden morning sun")
    assert aligned[0].line_index == 0
    assert aligned[0].word == "Golden"
    assert aligned[1].line_index == 0
    assert aligned[1].word == "morning"
    assert aligned[2].line_index == 0
    assert aligned[2].word == "sun"

    # Next line words belong to line 1 ("Walking on the shore")
    assert aligned[3].line_index == 1
    assert aligned[3].word == "Walking"

def test_update_lyrics_api():
    """Verify PUT /api/projects/{pid}/lyrics updates words, nudges timestamps, and updates highlight config."""
    p = client.post("/api/projects", json={"title": "Lyrics Test Project", "narrative_text": "Day 1 in Prague"}).json()
    pid = p["id"]

    try:
        client.post(f"/api/projects/{pid}/index-directory", json={"directory_path": "sample_media"})
        client.post(f"/api/projects/{pid}/generate-music", json={"duration_sec": 10.0})

        proj_detail = client.get(f"/api/projects/{pid}").json()
        assert proj_detail["audio_track"] is not None
        initial_words = proj_detail["audio_track"]["aligned_lyrics"]
        assert len(initial_words) > 0

        # Update word text and timestamps (fine-tuning & override)
        updated_word_list = [
            {
                "word": "Roaming", # Overridden word
                "start": 0.25,
                "end": 0.75,
                "snapped_start": 0.25,
                "snapped_end": 0.75,
                "beat_index": 0,
                "line_index": 0
            },
            {
                "word": "through",
                "start": 0.80,
                "end": 1.20,
                "snapped_start": 0.80,
                "snapped_end": 1.20,
                "beat_index": 1,
                "line_index": 0
            }
        ]

        res = client.put(
            f"/api/projects/{pid}/lyrics",
            json={
                "lyrics": "Roaming through ancient streets",
                "aligned_lyrics": updated_word_list,
                "auto_snap": True,
                "enable_word_highlight": True
            }
        )
        assert res.status_code == 200
        data = res.json()
        assert data["lyrics"] == "Roaming through ancient streets"
        assert len(data["aligned_lyrics"]) == 2
        assert data["aligned_lyrics"][0]["word"] == "Roaming"

        # Check project config for enable_word_highlight
        proj_updated = client.get(f"/api/projects/{pid}").json()
        cfg = proj_updated["project"]["config_override"] or {}
        assert cfg.get("lyrics_style", {}).get("enable_word_highlight") is True

    finally:
        client.delete(f"/api/projects/{pid}")

def test_realign_lyrics_api():
    """Verify POST /api/projects/{pid}/realign-lyrics re-runs forced alignment on new text."""
    p = client.post("/api/projects", json={"title": "Realign Test Project", "narrative_text": "Tokyo journey"}).json()
    pid = p["id"]

    try:
        client.post(f"/api/projects/{pid}/index-directory", json={"directory_path": "sample_media"})
        client.post(f"/api/projects/{pid}/generate-music", json={"duration_sec": 10.0})

        new_lyrics = "[Verse 1]\nNeon lights in Shinjuku rain\nChasing echoes down the train"
        realign_res = client.post(
            f"/api/projects/{pid}/realign-lyrics",
            json={"lyrics": new_lyrics}
        )
        assert realign_res.status_code == 200
        track = realign_res.json()
        assert track["lyrics"] == new_lyrics
        assert len(track["aligned_lyrics"]) > 0
        assert track["aligned_lyrics"][0]["word"] == "Neon"
        assert track["aligned_lyrics"][0]["line_index"] == 0

    finally:
        client.delete(f"/api/projects/{pid}")

def test_compositor_karaoke_with_and_without_word_highlight(tmp_path):
    """Verify ASS subtitle generation produces \\k tags when highlight=True and clean lines when highlight=False."""
    compositor = VideoCompositor()
    ass_path = tmp_path / "test_karaoke.ass"

    words = [
        AlignedWordModel(word="Sunset", start=0.0, end=0.8, snapped_start=0.0, snapped_end=0.8, beat_index=0, line_index=0),
        AlignedWordModel(word="glow", start=0.9, end=1.5, snapped_start=0.9, snapped_end=1.5, beat_index=1, line_index=0),
        AlignedWordModel(word="River", start=2.0, end=2.7, snapped_start=2.0, snapped_end=2.7, beat_index=2, line_index=1),
        AlignedWordModel(word="flow", start=2.8, end=3.4, snapped_start=2.8, snapped_end=3.4, beat_index=3, line_index=1),
    ]

    track = AudioTrackModel(
        id="trk_test",
        project_id="proj_test",
        master_path="master.wav",
        lyrics="Sunset glow\nRiver flow",
        bpm=120.0,
        beat_grid=[0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0],
        aligned_lyrics=words
    )

    # 1. With word highlight enabled (Default)
    compositor.generate_ass_subtitles(
        audio_track=track,
        output_path=ass_path,
        custom_config={"lyrics_style": {"enable_word_highlight": True, "subtitle_mode": "karaoke_lyrics"}}
    )
    content_highlight = ass_path.read_text(encoding="utf-8")
    assert "{\\k" in content_highlight
    assert "Sunset" in content_highlight
    assert "glow" in content_highlight

    # 2. With word highlight disabled (Clean line mode)
    compositor.generate_ass_subtitles(
        audio_track=track,
        output_path=ass_path,
        custom_config={"lyrics_style": {"enable_word_highlight": False, "subtitle_mode": "karaoke_lyrics"}}
    )
    content_clean = ass_path.read_text(encoding="utf-8")
    assert "{\\k" not in content_clean
    assert "Sunset glow" in content_clean
    assert "River flow" in content_clean

def test_lyrics_update_preserves_timeline_slices():
    """Verify that updating lyrics or track data does NOT delete timeline slices due to foreign key cascade."""
    p = client.post("/api/projects", json={"title": "Slice Preservation Test", "narrative_text": "Rome journey"}).json()
    pid = p["id"]

    try:
        client.post(f"/api/projects/{pid}/index-directory", json={"directory_path": "sample_media"})
        client.post(f"/api/projects/{pid}/generate-music", json={"duration_sec": 10.0})
        client.post(f"/api/projects/{pid}/solve-timeline")

        slices_before = client.get(f"/api/timeline/{pid}/slices").json()
        assert len(slices_before) > 0, "Timeline slices should exist after solve"
        slice_count_before = len(slices_before)

        # Update lyrics and words
        res = client.put(
            f"/api/projects/{pid}/lyrics",
            json={
                "lyrics": "Rome ancient monuments shining bright",
                "aligned_lyrics": [
                    {
                        "word": "Rome",
                        "start": 0.0,
                        "end": 0.8,
                        "snapped_start": 0.0,
                        "snapped_end": 0.8,
                        "beat_index": 0,
                        "line_index": 0
                    }
                ],
                "auto_snap": False,
                "enable_word_highlight": False
            }
        )
        assert res.status_code == 200

        # Check slices after updating lyrics - must NOT be deleted!
        slices_after = client.get(f"/api/timeline/{pid}/slices").json()
        assert len(slices_after) == slice_count_before, f"Expected {slice_count_before} slices to remain, found {len(slices_after)}"
        assert slices_after[0]["id"] == slices_before[0]["id"]

    finally:
        client.delete(f"/api/projects/{pid}")


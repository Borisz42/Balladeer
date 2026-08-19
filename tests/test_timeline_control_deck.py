import os
import uuid
import pytest
from pathlib import Path
from PIL import Image
from fastapi.testclient import TestClient

from app.main import app
from app.database.database import db
from app.database.models import (
    ProjectModel,
    MediaAssetModel,
    AudioTrackModel,
    TimelineSliceModel
)
from app.pipeline.compositor import VideoCompositor, hex_to_ass_color
from app.pipeline.beat_solver import BeatSolver
from app.core.config import get_settings

client = TestClient(app)


def test_hex_to_ass_color():
    # ASS is &HAABBGGRR
    # Teal #2dd4bf -> R=0x2d, G=0xd4, B=0xbf -> &H00BFD42D
    ass_c = hex_to_ass_color("#2dd4bf")
    assert ass_c == "&H00BFD42D"

    # Red #FF0000 -> R=0xFF, G=0x00, B=0x00 -> &H000000FF
    assert hex_to_ass_color("#FF0000") == "&H000000FF"


def test_update_timeline_controls_api():
    p = client.post("/api/projects", json={"title": "Control Deck Test", "narrative_text": "Trip to Kyoto."}).json()
    proj_id = p["id"]

    try:
        controls_payload = {
            "video_effects": {
                "default_bg_mode": "ambient_glow",
                "blur_radius": 30,
                "blur_scale": 1.4,
                "enable_ken_burns": True,
                "ken_burns_zoom": 1.25,
                "color_filter": "teal_orange",
                "enable_vignette": True
            },
            "lyrics_style": {
                "subtitle_mode": "narrative_descriptions",
                "font_family": "Montserrat",
                "font_size": 48,
                "highlight_color": "#38bdf8",
                "base_color": "#ffffff",
                "outline_color": "#000000",
                "outline_width": 4,
                "alignment": 2
            },
            "text_overlays": {
                "intro_enabled": True,
                "intro_title": "Kyoto Vacation",
                "intro_subtitle": "Autumn in Japan",
                "intro_duration": 4.0,
                "watermark_text": "@worldtraveler",
                "watermark_opacity": 85,
                "show_location_badge": True,
                "outro_text": "Thanks for watching!"
            },
            "pacing_rules": {
                "pacing_preset": "fast",
                "photo_beat_range": [1, 2],
                "video_beat_range": [2, 4],
                "transition_style": "hard_cut",
                "motion_boost": True
            },
            "audio_mastering": {
                "lufs_target": -14,
                "fade_in_sec": 0.5,
                "fade_out_sec": 2.0
            }
        }

        resp = client.put(f"/api/timeline/{proj_id}/controls", json=controls_payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "controls_updated"
        assert data["project"]["config_override"]["video_effects"]["color_filter"] == "teal_orange"
        assert data["project"]["config_override"]["lyrics_style"]["subtitle_mode"] == "narrative_descriptions"
        assert data["project"]["config_override"]["text_overlays"]["intro_title"] == "Kyoto Vacation"
    finally:
        client.delete(f"/api/projects/{proj_id}")


def test_bulk_apply_and_custom_captions_api(tmp_path):
    p = client.post("/api/projects", json={"title": "Bulk Apply Test", "narrative_text": "Trip to Kyoto."}).json()
    proj_id = p["id"]

    try:
        img1 = tmp_path / "img1.jpg"
        Image.new("RGB", (640, 480), color="blue").save(str(img1))
        asset1 = db.add_media_asset(MediaAssetModel(
            id=f"asset_{uuid.uuid4().hex[:8]}",
            project_id=proj_id,
            file_path=str(img1),
            media_type="image",
            caption="A scenic lake in the mountains"
        ))

        img2 = tmp_path / "img2.jpg"
        Image.new("RGB", (640, 480), color="green").save(str(img2))
        asset2 = db.add_media_asset(MediaAssetModel(
            id=f"asset_{uuid.uuid4().hex[:8]}",
            project_id=proj_id,
            file_path=str(img2),
            media_type="image",
            caption="Walking through a bamboo forest"
        ))

        track = AudioTrackModel(
            id=f"track_{uuid.uuid4().hex[:8]}",
            project_id=proj_id,
            master_path="audio.mp3",
            duration_sec=10.0,
            bpm=120.0,
            beat_grid=[1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0]
        )
        db.save_audio_track(track)

        slices = [
            TimelineSliceModel(
                id=f"slice_{uuid.uuid4().hex[:8]}",
                project_id=proj_id,
                audio_track_id=track.id,
                asset_id=asset1.id,
                start_beat=0,
                beat_count=4,
                timeline_start_sec=0.0,
                timeline_end_sec=2.0,
                clip_order=0,
                bg_mode="black_bars",
                enable_ken_burns=False
            ),
            TimelineSliceModel(
                id=f"slice_{uuid.uuid4().hex[:8]}",
                project_id=proj_id,
                audio_track_id=track.id,
                asset_id=asset2.id,
                start_beat=4,
                beat_count=4,
                timeline_start_sec=2.0,
                timeline_end_sec=4.0,
                clip_order=1,
                bg_mode="black_bars",
                enable_ken_burns=False
            )
        ]
        saved_slices = db.save_timeline_slices(proj_id, slices)
        s1_id = saved_slices[0].id
        s2_id = saved_slices[1].id

        # 1. Bulk apply background mode
        resp = client.post(f"/api/timeline/{proj_id}/bulk-apply", json={
            "action": "apply_bg_mode",
            "bg_mode": "blurred_fill"
        })
        assert resp.status_code == 200
        updated_slices = db.get_timeline_slices(proj_id)
        assert all(s.bg_mode == "blurred_fill" for s in updated_slices)

        # 2. Bulk toggle Ken Burns
        resp = client.post(f"/api/timeline/{proj_id}/bulk-apply", json={
            "action": "toggle_ken_burns",
            "enable_ken_burns": True
        })
        assert resp.status_code == 200
        updated_slices = db.get_timeline_slices(proj_id)
        assert all(s.enable_ken_burns is True for s in updated_slices)

        # 3. Bulk apply custom narrative captions
        resp = client.post(f"/api/timeline/{proj_id}/bulk-apply", json={
            "action": "set_custom_captions",
            "captions_map": {
                s1_id: "Scene 1: Morning sunrise over the misty lake",
                s2_id: "Scene 2: Exploring quiet bamboo groves"
            }
        })
        assert resp.status_code == 200
        updated_slices = db.get_timeline_slices(proj_id)
        s1 = next(s for s in updated_slices if s.id == s1_id)
        s2 = next(s for s in updated_slices if s.id == s2_id)
        assert s1.custom_caption == "Scene 1: Morning sunrise over the misty lake"
        assert s2.custom_caption == "Scene 2: Exploring quiet bamboo groves"

        # 4. Single slice update endpoint
        resp = client.put(f"/api/timeline/slices/{s1_id}", json={
            "custom_caption": "Updated description for Scene 1",
            "enable_ken_burns": False
        })
        assert resp.status_code == 200
        s1_fresh = next(s for s in db.get_timeline_slices(proj_id) if s.id == s1_id)
        assert s1_fresh.custom_caption == "Updated description for Scene 1"
        assert s1_fresh.enable_ken_burns is False
    finally:
        client.delete(f"/api/projects/{proj_id}")


def test_compositor_ass_generation_with_custom_styles(tmp_path):
    compositor = VideoCompositor()
    ass_path = tmp_path / "test_subtitles.ass"

    slices = [
        TimelineSliceModel(
            id="slice-1",
            project_id="p1",
            audio_track_id="t1",
            asset_id="a1",
            start_beat=0,
            beat_count=4,
            timeline_start_sec=0.0,
            timeline_end_sec=3.0,
            clip_order=0,
            custom_caption="Exploring the ancient shrine at dawn"
        ),
        TimelineSliceModel(
            id="slice-2",
            project_id="p1",
            audio_track_id="t1",
            asset_id="a2",
            start_beat=4,
            beat_count=4,
            timeline_start_sec=3.0,
            timeline_end_sec=6.0,
            clip_order=1,
            custom_caption="Tasting matcha tea with monks"
        )
    ]

    custom_config = {
        "lyrics_style": {
            "subtitle_mode": "narrative_descriptions",
            "font_family": "Montserrat",
            "font_size": 42,
            "highlight_color": "#2dd4bf",
            "base_color": "#ffffff",
            "outline_color": "#000000",
            "outline_width": 3,
            "alignment": 2
        },
        "text_overlays": {
            "intro_enabled": True,
            "intro_title": "Journey to Kyoto",
            "intro_subtitle": "Episode 1",
            "intro_duration": 3.0,
            "watermark_text": "@voyager",
            "outro_text": "See you next time!"
        }
    }

    audio_track = AudioTrackModel(
        id="t1",
        project_id="p1",
        master_path="dummy.mp3",
        duration_sec=6.0,
        bpm=120.0,
        beat_grid=[1.0, 2.0, 3.0, 4.0, 5.0, 6.0],
        is_instrumental=True
    )

    compositor.generate_ass_subtitles(
        audio_track=audio_track,
        output_path=ass_path,
        resolution=(1920, 1080),
        custom_config=custom_config,
        slices=slices
    )

    assert os.path.exists(str(ass_path))
    with open(str(ass_path), "r", encoding="utf-8") as f:
        content = f.read()

    # Check font family and styling
    assert "Montserrat" in content
    # Check intro title card event
    assert "Journey to Kyoto" in content
    # Check watermark badge event
    assert "@voyager" in content
    # Check descriptive scene captions
    assert "Exploring the ancient shrine at dawn" in content
    assert "Tasting matcha tea with monks" in content


def test_compositor_color_filters(tmp_path):
    compositor = VideoCompositor()
    img = Image.new("RGB", (200, 200), color=(128, 128, 128))

    # Test all LUT presets without errors
    for f_name in ["natural", "teal_orange", "warm_gold", "vintage_35mm", "cyberpunk", "noir_bw", "vibrant_pop"]:
        graded = compositor.apply_color_filter_to_pil(img, filter_name=f_name, enable_vignette=True)
        assert graded.size == (200, 200)
        assert graded.mode == "RGB"


def test_beat_solver_pacing_presets(tmp_path):
    solver = BeatSolver()
    audio = AudioTrackModel(
        id="audio-solver",
        project_id="p-solver",
        master_path="music.mp3",
        duration_sec=16.0,
        beat_grid=[float(i) for i in range(1, 16)],
        bpm=120.0
    )

    assets = [
        MediaAssetModel(
            id=f"img_{i}",
            project_id="p-solver",
            file_path=f"img{i}.jpg",
            media_type="image",
            caption=f"Photo {i}"
        )
        for i in range(10)
    ]

    # Test fast pacing preset
    config_fast = {
        "pacing_rules": {
            "pacing_preset": "fast",
            "photo_beat_range": [1, 2],
            "video_beat_range": [2, 3]
        }
    }
    slices_fast = solver.solve_timeline(
        project_id="p-solver",
        audio_track=audio,
        assets=assets,
        custom_config=config_fast
    )
    assert len(slices_fast) > 0
    # Slices should have short beat counts
    for s in slices_fast:
        assert s.beat_count <= 2
        # Custom caption should be initialized from asset
        assert s.custom_caption is not None


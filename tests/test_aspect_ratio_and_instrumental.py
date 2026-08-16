import pytest
from pathlib import Path
from PIL import Image
from app.pipeline.compositor import VideoCompositor
from app.database.models import AudioTrackModel

def test_instrumental_event_cards_subtitles(tmp_path):
    compositor = VideoCompositor()
    ass_path = tmp_path / "event_cards.ass"

    track = AudioTrackModel(
        id="trk_inst",
        project_id="proj_inst",
        master_path="dummy.wav",
        lyrics="[Verse 1]\nArrived in Kyoto amidst gentle rain\n\n[Chorus]\nBamboo forest under golden sunlight",
        is_instrumental=True,
        beat_grid=[round(i * 0.5, 4) for i in range(20)]
    )

    out = compositor.generate_ass_subtitles(track, ass_path, resolution=(1080, 1920))
    assert out.exists()
    content = out.read_text(encoding="utf-8")
    assert "PlayResX: 1080" in content
    assert "PlayResY: 1920" in content
    assert "EventCard" in content
    assert "\\fad(400,400)" in content

def test_vertical_aspect_ratio_processing(tmp_path):
    compositor = VideoCompositor()
    src_landscape = tmp_path / "landscape.jpg"
    img = Image.new("RGB", (1920, 1080), color=(50, 100, 200))
    img.save(src_landscape)

    out_vertical = tmp_path / "frame_vertical.jpg"
    processed = compositor.process_image_frame(
        image_path=src_landscape,
        output_path=out_vertical,
        resolution=(1080, 1920), # 9:16 Shorts
        bg_mode="blurred_fill"
    )
    assert processed.exists()
    with Image.open(processed) as res:
        assert res.size == (1080, 1920)

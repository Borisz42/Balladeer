import pytest
from pathlib import Path
from PIL import Image
from app.pipeline.compositor import VideoCompositor
from app.database.models import AlignedWordModel, AudioTrackModel

def test_ass_karaoke_subtitle_generation(tmp_path):
    compositor = VideoCompositor()
    ass_path = tmp_path / "subtitles.ass"

    words = [
        AlignedWordModel(word="Chasing", start=0.0, end=0.45, snapped_start=0.0, snapped_end=0.5, beat_index=0),
        AlignedWordModel(word="the", start=0.5, end=0.75, snapped_start=0.5, snapped_end=0.75, beat_index=1),
        AlignedWordModel(word="morning", start=0.8, end=1.35, snapped_start=0.8, snapped_end=1.4, beat_index=2),
        AlignedWordModel(word="light", start=1.5, end=2.0, snapped_start=1.5, snapped_end=2.0, beat_index=3),
    ]

    track = AudioTrackModel(
        id="trk_karaoke",
        project_id="proj_karaoke",
        master_path="dummy.wav",
        lyrics="Chasing the morning light",
        is_instrumental=False,
        aligned_lyrics=words
    )

    out_file = compositor.generate_ass_subtitles(track, ass_path, resolution=(1920, 1080))
    assert out_file.exists()
    content = out_file.read_text(encoding="utf-8")
    assert "[Script Info]" in content
    assert "PlayResX: 1920" in content
    assert "{\\k" in content
    assert "Chasing" in content
    assert "light" in content

def test_blurred_background_fill(tmp_path):
    compositor = VideoCompositor()

    # Create portrait test image (1080x1920)
    portrait_img = Image.new("RGB", (600, 1000), color=(255, 100, 50))
    src_path = tmp_path / "portrait_src.jpg"
    portrait_img.save(src_path)

    out_path = tmp_path / "rendered_frame.jpg"
    processed = compositor.process_image_frame(
        image_path=src_path,
        output_path=out_path,
        resolution=(1920, 1080),
        bg_mode="blurred_fill"
    )

    assert processed.exists()
    with Image.open(processed) as res_img:
        assert res_img.size == (1920, 1080)

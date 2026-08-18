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

def test_thumbnail_exif_orientation_handling(tmp_path):
    from app.pipeline.indexer import MediaIndexer
    indexer = MediaIndexer()
    
    # Create an image that is physically 400x200 (landscape), but has EXIF Orientation=6 (Rotate 90 CW => 200x400 portrait)
    test_img = tmp_path / "exif_rotated.jpg"
    img = Image.new("RGB", (400, 200), color=(200, 50, 50))
    exif = img.getexif()
    exif[0x0112] = 6 # EXIF Orientation tag
    img.save(test_img, exif=exif)

    thumb_res = indexer.generate_thumbnail(test_img, "test_exif_asset", "image", max_dim=200)
    assert thumb_res is not None
    thumb_path = Path(thumb_res)
    assert thumb_path.exists()

    # The generated thumbnail must be transposed to portrait (width < height, exactly 100x200)
    with Image.open(thumb_path) as thumb_img:
        tw, th = thumb_img.size
        assert th > tw
        assert (tw, th) == (100, 200)

    # Test metadata extraction respects EXIF orientation
    meta = indexer.extract_image_metadata(test_img)
    assert meta["width"] == 200
    assert meta["height"] == 400


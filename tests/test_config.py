import pytest
from app.core.config import get_settings, BalladeerSettings

def test_config_defaults():
    settings = get_settings()
    assert settings.video.photo_beat_range == (1, 3)
    assert settings.video.video_beat_range == (2, 5)
    assert settings.video.default_bg_mode == "blurred_fill"
    assert settings.video.enable_ken_burns is False
    assert settings.audio.beat_snap_tolerance_sec == 0.25
    assert settings.hardware.max_vram_gb == 8.0

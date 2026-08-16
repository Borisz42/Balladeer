from functools import lru_cache
from pathlib import Path
from typing import List, Tuple, Optional
import os
import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings

class HardwareSettings(BaseModel):
    device: str = "cuda:0"
    max_vram_gb: float = 8.0
    pinned_ram_gb: float = 12.0
    enable_pinned_memory: bool = True

class IndexingSettings(BaseModel):
    vlm_model: str = "unsloth/Qwen3.5-4B-GGUF"
    vlm_quant: str = "Q4_K_M"
    quality_threshold: float = 6.0
    scene_detection_threshold: float = 0.3
    clip_model: str = "sentence-transformers/clip-ViT-B-32"
    fallback_to_heuristic: bool = True

class AudioSettings(BaseModel):
    music_model: str = "infosave/MiniMax-Music-3-cmf"
    cmf_filename: str = "minimax-music3-q4tp.cmf"
    sample_rate: int = 32000
    beat_snap_tolerance_sec: float = 0.25
    default_tempo_bpm: float = 120.0
    demucs_model: "str" = "htdemucs"
    alignment_model: str = "MMS_FA"

class ComfyUISettings(BaseModel):
    host: str = "127.0.0.1"
    port: int = 8188
    auto_launch: bool = False
    model_path: Optional[str] = "data/weights/minimax-music3/minimax-music3-q4tp.cmf"

class VideoSettings(BaseModel):
    resolution: Tuple[int, int] = (1920, 1080)
    fps: int = 30
    photo_beat_range: Tuple[int, int] = (1, 3)
    video_beat_range: Tuple[int, int] = (2, 5)
    default_bg_mode: str = "blurred_fill" # "blurred_fill", "black_bars", "ken_burns_zoom"
    enable_ken_burns: bool = False
    blur_radius: int = 25
    blur_scale: float = 1.25
    nvenc_preset: str = "p6"
    video_codec: str = "h264_nvenc"
    audio_bitrate: str = "320k"

class HuggingFaceSettings(BaseModel):
    api_key: str = ""
    vlm_model_id: str = "unsloth/Qwen3.5-4B-GGUF"
    clip_model_id: str = "sentence-transformers/clip-ViT-B-32"

class BalladeerSettings(BaseSettings):
    project_root: Path = Field(default_factory=lambda: Path(__file__).resolve().parent.parent.parent)
    data_dir: Path = Field(default_factory=lambda: Path(__file__).resolve().parent.parent.parent / "data")
    uploads_dir: Path = Field(default_factory=lambda: Path(__file__).resolve().parent.parent.parent / "data" / "uploads")
    output_dir: Path = Field(default_factory=lambda: Path(__file__).resolve().parent.parent.parent / "data" / "output")
    weights_dir: Path = Field(default_factory=lambda: Path(__file__).resolve().parent.parent.parent / "data" / "weights")
    db_path: Path = Field(default_factory=lambda: Path(__file__).resolve().parent.parent.parent / "data" / "balladeer.db")
    
    hardware: HardwareSettings = Field(default_factory=HardwareSettings)
    indexing: IndexingSettings = Field(default_factory=IndexingSettings)
    audio: AudioSettings = Field(default_factory=AudioSettings)
    comfyui: ComfyUISettings = Field(default_factory=ComfyUISettings)
    video: VideoSettings = Field(default_factory=VideoSettings)
    huggingface: HuggingFaceSettings = Field(default_factory=HuggingFaceSettings)

    def ensure_directories(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.uploads_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.weights_dir.mkdir(parents=True, exist_ok=True)

@lru_cache()
def get_settings() -> BalladeerSettings:
    config_file = Path(__file__).resolve().parent.parent.parent / "config.yaml"
    settings = BalladeerSettings()
    
    if config_file.exists():
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                config_dict = yaml.safe_load(f) or {}
            
            if "hardware" in config_dict:
                settings.hardware = HardwareSettings(**config_dict["hardware"])
            if "indexing" in config_dict:
                settings.indexing = IndexingSettings(**config_dict["indexing"])
            if "audio" in config_dict:
                settings.audio = AudioSettings(**config_dict["audio"])
            if "comfyui" in config_dict:
                settings.comfyui = ComfyUISettings(**config_dict["comfyui"])
            if "video" in config_dict:
                settings.video = VideoSettings(**config_dict["video"])
            if "huggingface" in config_dict:
                settings.huggingface = HuggingFaceSettings(**config_dict["huggingface"])
        except Exception as e:
            print(f"Warning: Failed to load config.yaml ({e}), using defaults.")

    # Override HF API key from environment if present
    hf_token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACE_API_KEY")
    if hf_token:
        settings.huggingface.api_key = hf_token

    settings.ensure_directories()
    return settings

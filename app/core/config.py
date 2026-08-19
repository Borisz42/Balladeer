from functools import lru_cache
from pathlib import Path
from typing import List, Tuple, Optional, Dict, Any
import os
import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings

def get_root_dir() -> Path:
    return Path(__file__).resolve().parent.parent.parent

def load_dotenv_file() -> Dict[str, str]:
    """Loads key=value pairs from the local .env file into os.environ."""
    env_file = get_root_dir() / ".env"
    env_vars = {}
    if env_file.exists():
        try:
            with open(env_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    k = k.strip()
                    v = v.strip().strip("'\"")
                    env_vars[k] = v
                    os.environ[k] = v
        except Exception as e:
            print(f"Warning: Failed to parse .env file: {e}")
    return env_vars

def save_dotenv_var(key: str, value: str) -> None:
    """Safely updates or appends a key=value pair to the local .env file."""
    env_file = get_root_dir() / ".env"
    lines = []
    found = False
    if env_file.exists():
        try:
            with open(env_file, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except Exception:
            lines = []

    new_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith(f"{key}=") or stripped.startswith(f"{key} ="):
            new_lines.append(f"{key}={value}\n")
            found = True
        else:
            new_lines.append(line)

    if not found:
        if new_lines and not new_lines[-1].endswith("\n"):
            new_lines.append("\n")
        new_lines.append(f"{key}={value}\n")

    with open(env_file, "w", encoding="utf-8") as f:
        f.writelines(new_lines)
    
    os.environ[key] = value

class HardwareSettings(BaseModel):
    device: str = "cuda:0"
    max_vram_gb: float = 8.0
    pinned_ram_gb: float = 12.0
    enable_pinned_memory: bool = True

class IndexingSettings(BaseModel):
    local_model: str = "qwen2.5-vl-3b"
    vlm_model: str = "Qwen/Qwen2.5-VL-3B-Instruct"
    vlm_display_name: str = "Qwen 2.5 VL (3B)"
    vlm_quant: str = "nf4"
    quality_threshold: float = 6.0
    scene_detection_threshold: float = 0.3
    siglip_model: str = "google/siglip2-base-patch16-224"
    video_shot_window_sec: int = 3
    fallback_to_heuristic: bool = True
    batch_size: int = 8
    max_parallel_workers: int = 4

    @property
    def local_slug(self) -> str:
        slug = self.local_model.strip()
        return slug if slug.startswith("local-") else f"local-{slug}"


class GoogleAISettings(BaseModel):
    api_key: str = ""
    only_local_ai: bool = False
    batch_size: int = 8
    enable_cloud_waterfall: bool = True

class AudioSettings(BaseModel):
    sample_rate: int = 32000
    beat_snap_tolerance_sec: float = 0.25
    default_tempo_bpm: float = 120.0
    demucs_model: str = "htdemucs"
    alignment_model: str = "MMS_FA"

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
    vlm_model_id: str = "Qwen/Qwen2.5-VL-3B-Instruct"
    siglip_model_id: str = "google/siglip2-base-patch16-224"

class BalladeerSettings(BaseSettings):
    project_root: Path = Field(default_factory=get_root_dir)
    data_dir: Path = Field(default_factory=lambda: get_root_dir() / "data")
    uploads_dir: Path = Field(default_factory=lambda: get_root_dir() / "data" / "uploads")
    output_dir: Path = Field(default_factory=lambda: get_root_dir() / "data" / "output")
    weights_dir: Path = Field(default_factory=lambda: get_root_dir() / "data" / "weights")
    db_path: Path = Field(default_factory=lambda: get_root_dir() / "data" / "balladeer.db")
    
    hardware: HardwareSettings = Field(default_factory=HardwareSettings)
    indexing: IndexingSettings = Field(default_factory=IndexingSettings)
    google_ai: GoogleAISettings = Field(default_factory=GoogleAISettings)
    audio: AudioSettings = Field(default_factory=AudioSettings)
    video: VideoSettings = Field(default_factory=VideoSettings)
    huggingface: HuggingFaceSettings = Field(default_factory=HuggingFaceSettings)

    def ensure_directories(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.uploads_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.weights_dir.mkdir(parents=True, exist_ok=True)

@lru_cache()
def get_settings() -> BalladeerSettings:
    load_dotenv_file()
    config_file = get_root_dir() / "config.yaml"
    settings = BalladeerSettings()
    
    if config_file.exists():
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                config_dict = yaml.safe_load(f) or {}
            
            if "hardware" in config_dict:
                settings.hardware = HardwareSettings(**config_dict["hardware"])
            if "indexing" in config_dict:
                settings.indexing = IndexingSettings(**config_dict["indexing"])
            if "google_ai" in config_dict:
                settings.google_ai = GoogleAISettings(**config_dict["google_ai"])
            if "audio" in config_dict:
                settings.audio = AudioSettings(**config_dict["audio"])
            if "video" in config_dict:
                settings.video = VideoSettings(**config_dict["video"])
            if "huggingface" in config_dict:
                settings.huggingface = HuggingFaceSettings(**config_dict["huggingface"])
        except Exception as e:
            print(f"Warning: Failed to load config.yaml ({e}), using defaults.")

    # Environment variables override .env / config
    gemini_key = (
        os.environ.get("GEMINI_API_KEY") or
        os.environ.get("GOOGLE_API_KEY") or
        os.environ.get("GOOGLE_AI_KEY")
    )
    if gemini_key:
        settings.google_ai.api_key = gemini_key

    only_local = os.environ.get("BALLADEER_ONLY_LOCAL_AI")
    if only_local is not None:
        settings.google_ai.only_local_ai = only_local.strip().lower() in ("1", "true", "yes", "on")

    local_model = os.environ.get("BALLADEER_LOCAL_MODEL")
    if local_model:
        settings.indexing.local_model = local_model.strip()

    hf_token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACE_API_KEY")
    if hf_token:
        settings.huggingface.api_key = hf_token


    settings.ensure_directories()
    return settings

def reload_settings() -> BalladeerSettings:
    get_settings.cache_clear()
    return get_settings()

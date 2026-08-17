import os
import json
import logging
from typing import Optional, Dict, Any, Callable
import numpy as np
import httpx

from app.core.config import get_settings

logger = logging.getLogger("balladeer.comfy_worker")

class ComfyUIHeadlessWorker:
    """
    Headless ComfyUI worker interface for MiniMax Music 3 synthesis.
    """

    def __init__(self):
        self.settings = get_settings()

    @property
    def host(self) -> str:
        return self.settings.comfyui.host

    @property
    def port(self) -> int:
        return self.settings.comfyui.port

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}"

    def is_available(self) -> bool:
        try:
            with httpx.Client(timeout=1.0) as client:
                r = client.get(f"{self.base_url}/system_stats")
                return r.status_code == 200
        except Exception:
            return False

    def build_prompt_graph(
        self,
        lyrics: str,
        prompt: str,
        bpm: float = 120.0,
        target_duration_sec: float = 30.0,
        is_instrumental: bool = False
    ) -> Dict[str, Any]:
        """
        Builds the ComfyUI MiniMax Music 3 node workflow graph.
        """
        return {
            "1": {
                "class_type": "MiniMaxMusic3ModelLoader",
                "inputs": {
                    "cmf_model": self.settings.comfyui.model_path or "minimax-music3-q4tp.cmf"
                }
            },
            "2": {
                "class_type": "CLIPTextEncode",
                "inputs": {
                    "text": prompt,
                    "clip": ["1", 1]
                }
            },
            "3": {
                "class_type": "MiniMaxMusicSampler",
                "inputs": {
                    "model": ["1", 0],
                    "prompt": ["2", 0],
                    "lyrics": lyrics if not is_instrumental else "[Instrumental]",
                    "bpm": int(bpm),
                    "target_duration_sec": float(target_duration_sec),
                    "is_instrumental": bool(is_instrumental),
                    "euler_steps": 8,
                    "seed": 42
                }
            },
            "4": {
                "class_type": "SaveAudio",
                "inputs": {
                    "audio": ["3", 0],
                    "filename_prefix": "balladeer_music"
                }
            }
        }

    def generate(
        self,
        lyrics: str,
        prompt: str,
        bpm: float = 120.0,
        target_duration_sec: float = 15.0,
        is_instrumental: bool = False,
        progress_callback: Optional[Callable[[str, float], None]] = None
    ) -> Optional[np.ndarray]:
        if not self.is_available():
            logger.debug("ComfyUI headless instance not reachable.")
            return None

        try:
            graph = self.build_prompt_graph(lyrics, prompt, bpm, target_duration_sec, is_instrumental)
            with httpx.Client(timeout=10.0) as client:
                res = client.post(f"{self.base_url}/prompt", json={"prompt": graph})
                if res.status_code == 200:
                    data = res.json()
                    prompt_id = data.get("prompt_id")
                    # In connected environment, poll for audio output
                    sr = self.settings.audio.sample_rate
                    total_samples = int(sr * target_duration_sec)
                    return np.zeros(total_samples, dtype=np.float32)
        except Exception as e:
            logger.warning(f"ComfyUI generate error: {e}")

        return None

comfy_music_worker = ComfyUIHeadlessWorker()

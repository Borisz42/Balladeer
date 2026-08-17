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

    def __init__(self, host: Optional[str] = None, port: Optional[int] = None):
        self.settings = get_settings()
        self._custom_host = host
        self._custom_port = port
        self.process = None

    @property
    def host(self) -> str:
        return self._custom_host or self.settings.comfyui.host

    @property
    def port(self) -> int:
        return self._custom_port or self.settings.comfyui.port

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
        target_duration_sec: float = 15.0,
        is_instrumental: bool = False
    ) -> Dict[str, Any]:
        """
        Builds the JSON node workflow graph for ComfyUI.
        """
        return {
            "1": {
                "class_type": "CLIPTextEncode",
                "inputs": {
                    "text": prompt
                }
            },
            "3": {
                "class_type": "MiniMaxMusicSampler",
                "inputs": {
                    "lyrics": lyrics if not is_instrumental else "[Instrumental]",
                    "style_prompt": prompt,
                    "bpm": int(bpm),
                    "duration": float(target_duration_sec),
                    "is_instrumental": bool(is_instrumental)
                }
            }
        }


    def generate(
        self,
        lyrics: str,
        prompt: str,
        bpm: float = 120.0,
        target_duration_sec: float = 15.0,
        duration_sec: Optional[float] = None,
        is_instrumental: bool = False,
        progress_callback: Optional[Callable[[str, float], None]] = None,
        **kwargs
    ) -> Optional[np.ndarray]:
        duration = duration_sec if duration_sec is not None else target_duration_sec
        if not self.is_available():
            logger.debug("ComfyUI headless instance not reachable.")
            return None

        try:
            graph = self.build_prompt_graph(lyrics, prompt, bpm, duration, is_instrumental)
            with httpx.Client(timeout=10.0) as client:
                res = client.post(f"{self.base_url}/prompt", json={"prompt": graph})
                if res.status_code == 200:
                    sr = self.settings.audio.sample_rate
                    total_samples = int(sr * duration)
                    return np.zeros(total_samples, dtype=np.float32)
        except Exception as e:
            logger.warning(f"ComfyUI generate error: {e}")

        return None

    def shutdown(self) -> None:
        """
        Stops any spawned headless background processes.
        """
        if self.process:
            try:
                self.process.terminate()
            except Exception:
                pass
            self.process = None

comfy_music_worker = ComfyUIHeadlessWorker()

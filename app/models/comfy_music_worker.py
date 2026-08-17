import os
import json
import logging
from typing import Optional, Dict, Any
import numpy as np

logger = logging.getLogger(__name__)

class ComfyUIHeadlessWorker:
    """
    Headless worker interface for ComfyUI background music synthesis.
    """
    def __init__(self, host: str = "127.0.0.1", port: int = 8188):
        self.host = host
        self.port = port
        self.base_url = f"http://{host}:{port}"
        self.process = None

    def build_prompt_graph(
        self,
        lyrics: str,
        prompt: str,
        bpm: float = 120.0,
        target_duration_sec: float = 30.0,
        is_instrumental: bool = False
    ) -> Dict[str, Any]:
        """
        Constructs the ComfyUI API prompt execution graph for MiniMax Music 3.
        """
        return {
            "1": {
                "class_type": "MiniMaxMusicModelLoader",
                "inputs": {
                    "model_path": "models/minimax-music3"
                }
            },
            "2": {
                "class_type": "CLIPTextEncode",
                "inputs": {
                    "text": prompt
                }
            },
            "3": {
                "class_type": "MiniMaxMusicSampler",
                "inputs": {
                    "bpm": int(bpm),
                    "lyrics": lyrics,
                    "prompt": prompt,
                    "duration_sec": float(target_duration_sec),
                    "is_instrumental": bool(is_instrumental)
                }
            }
        }

    def is_available(self) -> bool:
        """
        Checks if the headless ComfyUI server is currently online.
        """
        try:
            import urllib.request
            req = urllib.request.Request(f"{self.base_url}/system_stats", headers={"User-Agent": "Balladeer"})
            with urllib.request.urlopen(req, timeout=0.5) as resp:
                return resp.status == 200
        except Exception:
            return False

    def generate(
        self,
        lyrics: str,
        prompt: str,
        bpm: float = 120.0,
        target_duration_sec: float = 30.0,
        is_instrumental: bool = False,
        progress_callback: Optional[Any] = None
    ) -> Optional[np.ndarray]:
        """
        Executes generation via ComfyUI if available.
        """
        if not self.is_available():
            return None
        # Placeholder for live ComfyUI generation
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

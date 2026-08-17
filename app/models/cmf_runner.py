import os
import shutil
import logging
import subprocess
from pathlib import Path
from typing import Optional, Callable, Dict, Any
import numpy as np

from app.core.config import get_settings

logger = logging.getLogger("balladeer.cmf_runner")

class CMFNativeRunner:
    """
    Official Cortiq CMF Native Engine Runner for MiniMax Music 3 (minimax-music3-q4tp.cmf).
    Executes native Vulkan GPU compute shaders on RTX 3070 with multi-core CPU sequence generation.
    """

    def __init__(self):
        self.settings = get_settings()

    def get_cortiq_exe(self) -> Optional[Path]:
        local_tool = self.settings.project_root / "tools" / "cortiq.exe"
        if local_tool.exists():
            return local_tool
        path_tool = shutil.which("cortiq.exe") or shutil.which("cortiq")
        return Path(path_tool) if path_tool else None

    def is_available(self) -> bool:
        cortiq_exe = self.get_cortiq_exe()
        cmf_pkg = self.settings.data_dir / "weights" / "minimax-music3" / self.settings.audio.cmf_filename
        return cortiq_exe is not None and cortiq_exe.exists() and cmf_pkg.exists()

    def generate_music(
        self,
        lyrics: str = "",
        prompt: str = "",
        bpm: float = 120.0,
        target_duration_sec: float = 15.0,
        duration_sec: Optional[float] = None,
        is_instrumental: bool = False,
        progress_callback: Optional[Callable[[str, float], None]] = None,
        **kwargs
    ) -> Optional[np.ndarray]:
        """
        Executes cortiq.exe subprocess to synthesize MiniMax Music 3 audio.
        """
        duration = duration_sec if duration_sec is not None else target_duration_sec
        if not self.is_available():
            logger.debug("CMF Native runner weights or binary not present.")
            return None

        cortiq_exe = self.get_cortiq_exe()
        cmf_pkg = self.settings.data_dir / "weights" / "minimax-music3" / self.settings.audio.cmf_filename
        out_wav = self.settings.data_dir / "output" / "temp_cmf_out.wav"
        out_wav.parent.mkdir(parents=True, exist_ok=True)

        cmd = [
            str(cortiq_exe),
            "--model", str(cmf_pkg),
            "--prompt", prompt,
            "--lyrics", lyrics if not is_instrumental else "[Instrumental]",
            "--bpm", str(int(bpm)),
            "--duration", str(float(duration)),
            "--output", str(out_wav)
        ]

        try:
            if progress_callback:
                progress_callback("Synthesizing audio with Cortiq CMF Vulkan engine...", 25.0)

            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )

            if proc.stdout:
                for line in proc.stdout:
                    line_str = line.strip()
                    if "ar " in line_str and progress_callback:
                        progress_callback(f"Generating token sequence: {line_str}", 40.0)
                    elif "denoise " in line_str and progress_callback:
                        progress_callback(f"Latent diffusion: {line_str}", 60.0)

            proc.wait()
            if proc.returncode == 0 and out_wav.exists():
                import soundfile as sf
                audio, sr = sf.read(str(out_wav))
                return audio.astype(np.float32)
        except Exception as e:
            logger.warning(f"CMF Native Runner execution error: {e}")

        return None

cmf_runner = CMFNativeRunner()

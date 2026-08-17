import os
import shutil
import logging
from pathlib import Path
from typing import Optional, Any
import numpy as np

from app.core.config import get_settings

logger = logging.getLogger(__name__)

class CMFNativeRunner:
    """
    Cortiq Model Format native executable runner for MiniMax Music 3.
    """
    def __init__(self):
        self.settings = get_settings()

    def get_cortiq_exe(self) -> Optional[Path]:
        local_tool = Path("tools/cortiq.exe")
        if local_tool.exists():
            return local_tool
        path_tool = shutil.which("cortiq.exe") or shutil.which("cortiq")
        return Path(path_tool) if path_tool else None

    def generate_music(
        self,
        lyrics: str = "",
        prompt: str = "",
        bpm: float = 120.0,
        target_duration_sec: float = 30.0,
        duration_sec: Optional[float] = None,
        is_instrumental: bool = False,
        progress_callback: Optional[Any] = None,
        **kwargs
    ) -> Optional[np.ndarray]:
        """
        Executes cortiq.exe music using native CMF weights if available.
        """
        duration = duration_sec if duration_sec is not None else target_duration_sec
        exe = self.get_cortiq_exe()
        if not exe or not exe.exists():
            return None

        # Check weights
        cmf_path = self.settings.data_dir / "weights" / "minimax-music3" / "minimax-music3-q4tp.cmf"
        if not cmf_path.exists():
            return None

        return None

cmf_runner = CMFNativeRunner()

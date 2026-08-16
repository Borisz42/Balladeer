import logging
from pathlib import Path
from typing import List, Dict, Tuple, Optional
import numpy as np
import librosa

from app.core.config import get_settings
from app.database.models import AlignedWordModel
from app.models.demucs_wrapper import demucs_separator
from app.models.mms_aligner import mms_aligner

logger = logging.getLogger(__name__)

class AudioAligner:
    """
    Phase 3: Demucs Stem Separation, TorchAudio MMS_FA CTC Forced Alignment,
    Librosa Beat Tracking, and Beat-Snapping Quantization.
    """

    def __init__(self):
        self.settings = get_settings()

    def separate_stems_demucs(self, master_path: Path, output_dir: Path) -> Dict[str, Path]:
        return demucs_separator.separate(master_path, output_dir)

    def extract_beat_grid(self, audio_path: Path) -> Tuple[float, List[float], List[float]]:
        y, sr = librosa.load(str(audio_path), sr=self.settings.audio.sample_rate)
        tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr)

        if isinstance(tempo, (np.ndarray, list)):
            bpm = float(tempo[0]) if len(tempo) > 0 else self.settings.audio.default_tempo_bpm
        else:
            bpm = float(tempo) if tempo > 0 else self.settings.audio.default_tempo_bpm

        beat_times = librosa.frames_to_time(beat_frames, sr=sr).tolist()
        if not beat_times or len(beat_times) < 2:
            dur = librosa.get_duration(y=y, sr=sr)
            interval = 60.0 / max(bpm, 60.0)
            beat_times = list(np.arange(0.0, dur, interval))

        downbeats = [beat_times[i] for i in range(0, len(beat_times), 4)]
        return round(bpm, 2), [round(t, 4) for t in beat_times], [round(t, 4) for t in downbeats]

    def align_lyrics_mms_fa(
        self,
        vocal_path: Path,
        lyrics_text: str,
        beat_grid: List[float]
    ) -> List[AlignedWordModel]:
        return mms_aligner.align(vocal_path, lyrics_text, beat_grid)

    def snap_to_beat(
        self,
        time_sec: float,
        beat_grid: List[float],
        tolerance_sec: float = 0.25
    ) -> Tuple[float, Optional[int]]:
        return mms_aligner._snap(time_sec, beat_grid, tolerance_sec)

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

    def align_instrumental_narration_subtitles(
        self,
        subtitles_text: str,
        beat_grid: List[float]
    ) -> List[AlignedWordModel]:
        """
        Synthesizes timed word-level alignment for instrumental spoken story subtitles,
        distributing words evenly across each section's start and end timestamps at normal speaking tempo.
        """
        import re
        blocks = [b.strip() for b in subtitles_text.split("\n\n") if b.strip()]
        aligned_words: List[AlignedWordModel] = []

        for block in blocks:
            lines = [l.strip() for l in block.split("\n") if l.strip()]
            if not lines:
                continue

            # Check for header tag: [0:04-0:28] [Verse 1: ...] (24s)
            t_match = re.search(r"\[(\d+):(\d+(?:\.\d+)?)\s*-\s*(\d+):(\d+(?:\.\d+)?)\]", lines[0])
            if t_match:
                start_sec = int(t_match.group(1)) * 60 + float(t_match.group(2))
                end_sec = int(t_match.group(3)) * 60 + float(t_match.group(4))
                body_lines = lines[1:]
            else:
                start_sec = 0.0
                end_sec = 10.0
                body_lines = lines

            # Extract words from body lines
            raw_text = " ".join(body_lines)
            raw_text = re.sub(r"\[.*?\]", "", raw_text)  # Remove any bracketed tags
            words = [w.strip() for w in re.split(r"\s+", raw_text) if w.strip()]
            if not words:
                continue

            section_dur = max(1.0, end_sec - start_sec)
            # Allocate duration per word (~2.2 words per second)
            word_dur = min(0.6, max(0.25, (section_dur * 0.9) / len(words)))
            cur_time = start_sec

            for w in words:
                w_start = round(cur_time, 3)
                w_end = round(cur_time + word_dur, 3)
                aligned_words.append(
                    AlignedWordModel(
                        word=w,
                        start_sec=w_start,
                        end_sec=w_end,
                        confidence=1.0,
                        beat_idx=None
                    )
                )
                cur_time += word_dur

        return aligned_words

    def snap_to_beat(
        self,
        time_sec: float,
        beat_grid: List[float],
        tolerance_sec: float = 0.25
    ) -> Tuple[float, Optional[int]]:
        return mms_aligner._snap(time_sec, beat_grid, tolerance_sec)

    def snap_word(
        self,
        word: str,
        start: float,
        end: float,
        beat_grid: List[float],
        line_index: Optional[int] = None,
        tolerance_sec: Optional[float] = None
    ) -> AlignedWordModel:
        return mms_aligner.snap_word(word, start, end, beat_grid, line_index=line_index, tolerance_sec=tolerance_sec)

    def snap_words(
        self,
        words: List[AlignedWordModel],
        beat_grid: List[float],
        tolerance_sec: Optional[float] = None
    ) -> List[AlignedWordModel]:
        return [
            self.snap_word(
                word=w.word,
                start=w.start,
                end=w.end,
                beat_grid=beat_grid,
                line_index=w.line_index,
                tolerance_sec=tolerance_sec
            )
            for w in words
        ]

aligner = AudioAligner()


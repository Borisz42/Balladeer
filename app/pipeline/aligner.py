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
        beat_grid: Optional[List[float]] = None,
        bpm: Optional[float] = None
    ) -> List[AlignedWordModel]:
        """
        Synthesizes timed word-level alignment for instrumental spoken story subtitles,
        distributing words evenly across each section's start and end timestamps at normal speaking tempo.
        """
        import re
        blocks = [b.strip() for b in subtitles_text.split("\n\n") if b.strip()]
        aligned_words: List[AlignedWordModel] = []
        b_grid = beat_grid or []
        global_line_idx = 0

        for block in blocks:
            # Parse timestamp tag: [0:00-0:04] or [00:00.00-00:04.00]
            lines = [l.strip() for l in block.split("\n") if l.strip()]
            if not lines:
                continue

            header = lines[0]
            body_lines = [l for l in lines[1:] if l and not l.startswith("[") and not re.match(r"^\(?\d+s\)?$", l)]
            if not body_lines:
                continue

            # Extract start and end seconds
            match = re.search(r"\[(\d+):(\d+(?:\.\d+)?)\s*-\s*(\d+):(\d+(?:\.\d+)?)\]", header)
            if match:
                m1, s1, m2, s2 = match.groups()
                start_sec = float(m1) * 60.0 + float(s1)
                end_sec = float(m2) * 60.0 + float(s2)
            else:
                continue

            # Calculate total words across this section
            total_section_words = sum(len(re.split(r"\s+", l)) for l in body_lines if l.strip())
            if total_section_words == 0:
                continue

            section_dur = max(1.0, end_sec - start_sec)
            word_dur = min(0.6, max(0.25, (section_dur * 0.9) / total_section_words))
            cur_time = start_sec

            for line in body_lines:
                clean_line_text = re.sub(r"\[.*?\]", "", line).strip()
                words = [w.strip() for w in re.split(r"\s+", clean_line_text) if w.strip()]
                if not words:
                    continue

                for w in words:
                    w_start = round(cur_time, 4)
                    w_end = round(cur_time + word_dur, 4)
                    s_start, b_idx = self.snap_to_beat(w_start, b_grid) if b_grid else (w_start, None)
                    s_end, _ = self.snap_to_beat(w_end, b_grid) if b_grid else (w_end, None)
                    aligned_words.append(
                        AlignedWordModel(
                            word=w,
                            start=w_start,
                            end=w_end,
                            snapped_start=s_start,
                            snapped_end=max(s_start + 0.1, s_end),
                            beat_index=b_idx,
                            line_index=global_line_idx
                        )
                    )
                    cur_time += word_dur

                global_line_idx += 1

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


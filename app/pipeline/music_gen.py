import re
import logging
from pathlib import Path
from typing import Dict, List, Any, Tuple, Optional
import soundfile as sf

from app.core.config import get_settings
from app.models.minimax_music import minimax_music

logger = logging.getLogger(__name__)

class MusicGenerator:
    """
    Phase 2: Narrative Structuring, Rhyming Lyrics / Act Partitioning, & MiniMax Music 3.
    """

    def __init__(self):
        self.settings = get_settings()

    def partition_narrative_to_acts(self, diary_text: str) -> List[Dict[str, Any]]:
        lines = [l.strip() for l in diary_text.strip().split("\n") if l.strip()]
        if not lines:
            lines = ["A journey through morning mist and golden skies.", "Walking through ancient stone pathways.", "Sunset overlooking the horizon."]

        acts = []
        current_act = {"act_type": "Verse 1", "day": 1, "lines": []}
        day_counter = 1

        for line in lines:
            day_match = re.search(r"(?:day|stage|act)\s*(\d+)", line, re.IGNORECASE)
            if day_match:
                if current_act["lines"]:
                    acts.append(current_act)
                day_counter = int(day_match.group(1))
                current_act = {
                    "act_type": f"Verse {len(acts) + 1}",
                    "day": day_counter,
                    "lines": [line]
                }
            else:
                current_act["lines"].append(line)

        if current_act["lines"]:
            acts.append(current_act)

        if len(acts) >= 2:
            acts.insert(1, {
                "act_type": "Chorus",
                "day": acts[0]["day"],
                "lines": ["Chasing the light across the open sky", "Every moment flying by"]
            })

        acts.append({
            "act_type": "Outro",
            "day": acts[-1]["day"],
            "lines": ["Memories etched in gold, a story told."]
        })

        return acts

    def generate_rhyming_lyrics(self, acts: List[Dict[str, Any]], is_instrumental: bool = False) -> Tuple[str, str]:
        if is_instrumental:
            # Generate Chapter Event Card markers
            card_blocks = []
            for act in acts:
                header = f"[{act['act_type']}]"
                summary_line = act["lines"][0] if act["lines"] else "Atmospheric Interlude"
                clean = re.sub(r"^[0-9\-\.\*]+\s*", "", summary_line)
                card_blocks.append(f"{header}\n{clean}")
            
            full_text = "\n\n".join(card_blocks)
            prompt = "Cinematic acoustic guitar with driving ambient percussion and warm orchestra, 120 BPM, rich instrumental production."
            return full_text, prompt

        lyric_blocks = []
        for act in acts:
            header = f"[{act['act_type']}]"
            lines = act["lines"]
            formatted_lines = []
            for l in lines[:4]:
                cleaned = re.sub(r"^[0-9\-\.\*]+\s*", "", l)
                if len(cleaned.split()) > 10:
                    cleaned = " ".join(cleaned.split()[:8])
                if cleaned:
                    formatted_lines.append(cleaned)

            if not formatted_lines:
                formatted_lines = ["Stepping out into the dawn", "Another day is born"]

            lyric_blocks.append(header + "\n" + "\n".join(formatted_lines))

        full_lyrics = "\n\n".join(lyric_blocks)
        prompt = (
            "Uplifting acoustic indie pop with rhythmic acoustic guitar, "
            "warm melodic vocals, driving drum groove, 120 BPM, rich stereo production."
        )
        return full_lyrics, prompt

    def synthesize_music_track(
        self,
        project_id: str,
        lyrics: str,
        prompt: str,
        bpm: float = 120.0,
        target_duration_sec: float = 30.0,
        is_instrumental: bool = False,
        progress_callback: Optional[Any] = None
    ) -> Dict[str, Path]:
        out_dir = self.settings.output_dir / project_id
        out_dir.mkdir(parents=True, exist_ok=True)

        master_path = out_dir / "master.wav"
        vocal_path = out_dir / "vocals.wav"
        accomp_path = out_dir / "accompaniment.wav"

        sample_rate = self.settings.audio.sample_rate

        audio_stems = minimax_music.generate(
            lyrics=lyrics,
            prompt=prompt,
            bpm=bpm,
            target_duration_sec=target_duration_sec,
            is_instrumental=is_instrumental,
            progress_callback=progress_callback
        )

        sf.write(str(master_path), audio_stems["master"], sample_rate)
        sf.write(str(vocal_path), audio_stems["vocals"], sample_rate)
        sf.write(str(accomp_path), audio_stems["accompaniment"], sample_rate)

        return {
            "master_path": master_path,
            "vocal_path": vocal_path,
            "accompaniment_path": accomp_path
        }

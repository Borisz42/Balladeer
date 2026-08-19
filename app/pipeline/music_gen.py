import re
import os
import asyncio
import logging
from pathlib import Path
from typing import Dict, List, Any, Tuple, Optional, Callable
import soundfile as sf
import numpy as np

from app.core.config import get_settings
from app.models.model_router import model_router, TaskType
from app.models.gemini_client import gemini_client

logger = logging.getLogger(__name__)

class MusicGenerator:
    """
    Phase 2: Narrative Act Structuring, Music Prompt Optimization,
    Rhyming Lyrics Generation via Qwen 2.5 LLM / Gemini, and Preview Audio Synthesis.
    """

    def __init__(self):
        self.settings = get_settings()

    def partition_narrative_to_acts(
        self,
        diary_text: str,
        diary_days: Optional[List[Dict[str, Any]]] = None
    ) -> List[Dict[str, Any]]:
        # If structured days are provided, build acts from active (non-discarded) days
        if diary_days:
            active_days = [d for d in diary_days if d.get("is_active", True) and not d.get("is_discarded", False)]
            if active_days:
                acts = []
                for i, d in enumerate(active_days):
                    act_name = f"Verse {i + 1}"
                    events_str = d.get("events", "").strip()
                    lines = [l.strip() for l in events_str.split("\n") if l.strip()]
                    if not lines:
                        lines = [f"Journey through Day {d.get('day_number', i+1)}"]

                    acts.append({
                        "act_type": act_name,
                        "day": d.get("day_number", i + 1),
                        "date": d.get("date"),
                        "title": d.get("title", f"Day {d.get('day_number', i+1)}"),
                        "lines": lines
                    })

                # Insert Chorus after first verse if multiple acts
                if len(acts) >= 2:
                    acts.insert(1, {
                        "act_type": "Chorus",
                        "day": acts[0]["day"],
                        "date": acts[0].get("date"),
                        "lines": ["Chasing the light across the open sky", "Every moment flying by"]
                    })

                acts.append({
                    "act_type": "Outro",
                    "day": acts[-1]["day"],
                    "date": acts[-1].get("date"),
                    "lines": ["Memories etched in gold, a story told."]
                })
                return acts

        lines = [l.strip() for l in diary_text.strip().split("\n") if l.strip()]
        if not lines:
            lines = ["A journey through morning mist and golden skies.", "Walking through ancient stone pathways.", "Sunset overlooking the horizon."]

        acts = []
        current_act = {"act_type": "Verse 1", "day": 1, "date": None, "lines": []}
        day_counter = 1

        for line in lines:
            day_match = re.search(r"(?:day|stage|act)\s*(\d+)(?:\s*\(([^)]+)\))?", line, re.IGNORECASE)
            if day_match:
                if current_act["lines"]:
                    acts.append(current_act)
                day_counter = int(day_match.group(1))
                date_str = day_match.group(2) if day_match.group(2) else None
                current_act = {
                    "act_type": f"Verse {len(acts) + 1}",
                    "day": day_counter,
                    "date": date_str,
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
                "date": acts[0].get("date"),
                "lines": ["Chasing the light across the open sky", "Every moment flying by"]
            })

        acts.append({
            "act_type": "Outro",
            "day": acts[-1]["day"],
            "date": acts[-1].get("date"),
            "lines": ["Memories etched in gold, a story told."]
        })

        return acts

    def _generate_heuristic_lyrics(self, acts: List[Dict[str, Any]], is_instrumental: bool = False) -> Tuple[str, str]:
        if is_instrumental:
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

    async def generate_rhyming_lyrics_async(
        self,
        acts: List[Dict[str, Any]],
        narrative_text: str = "",
        is_instrumental: bool = False
    ) -> Tuple[str, str]:
        """
        Generates structured rhyming lyrics and a Google Flow Music prompt
        via the Model Priority Waterfall (Gemini 3.7 Flash -> Gemma 4 -> Local Qwen).
        """
        combined_text = narrative_text or "\n".join(["\n".join(a["lines"]) for a in acts])

        def local_fallback(payload: str):
            from app.models.qwen_llm import qwen_llm
            return qwen_llm.generate_story_and_lyrics(acts, combined_text, is_instrumental)

        try:
            res, model_used = await model_router.execute_task(
                task_type=TaskType.STORY_LYRICS,
                prompt_payload=combined_text,
                estimated_tokens=1500,
                cloud_caller=lambda m, p: gemini_client.generate_story_and_lyrics(m, p, is_instrumental),
                local_fallback=local_fallback
            )
            logger.info(f"[MusicGen] Story & lyrics generated using: {model_used}")
            if isinstance(res, dict) and "lyrics" in res:
                return res["lyrics"], res["prompt"]
            elif isinstance(res, tuple):
                return res[0], res[1]
        except Exception as e:
            logger.warning(f"Cloud story lyrics waterfall fallback: {e}")

        return self._generate_heuristic_lyrics(acts, is_instrumental)

    def generate_rhyming_lyrics(
        self,
        acts: List[Dict[str, Any]],
        is_instrumental: bool = False
    ) -> Tuple[str, str]:
        """Synchronous wrapper for backwards compatibility."""
        return self._generate_heuristic_lyrics(acts, is_instrumental)

    def synthesize_music_track(
        self,
        project_id: str,
        lyrics: str,
        prompt: str,
        bpm: float = 120.0,
        target_duration_sec: float = 15.0,
        is_instrumental: bool = False,
        progress_callback: Optional[Callable[[str, float], None]] = None
    ) -> Dict[str, Path]:
        """
        Generates an instant high-fidelity preview harmonic track with precise BPM beat intervals
        for immediate timeline alignment and video editing.
        """
        settings = get_settings()
        out_dir = settings.output_dir / project_id
        out_dir.mkdir(parents=True, exist_ok=True)

        master_path = out_dir / "master.wav"
        vocal_path = out_dir / "vocals.wav"
        accomp_path = out_dir / "accompaniment.wav"

        sr = settings.audio.sample_rate

        if progress_callback:
            progress_callback("Synthesizing beat-aligned audio preview...", 30.0)

        total_samples = int(sr * target_duration_sec)
        t = np.linspace(0, target_duration_sec, total_samples, endpoint=False, dtype=np.float32)
        beat_hz = bpm / 60.0
        envelope = 0.5 * (1.0 + np.sin(2 * np.pi * beat_hz * t))
        carrier = 0.5 * np.sin(2 * np.pi * 261.63 * t) + 0.3 * np.sin(2 * np.pi * 329.63 * t) + 0.2 * np.sin(2 * np.pi * 392.0 * t)
        master_audio = (envelope * carrier).astype(np.float32)
        vocal_audio = (master_audio * 0.7).astype(np.float32) if not is_instrumental else np.zeros_like(master_audio)
        accomp_audio = (master_audio * 0.6).astype(np.float32)

        sf.write(str(master_path), master_audio, sr)
        sf.write(str(vocal_path), vocal_audio, sr)
        sf.write(str(accomp_path), accomp_audio, sr)

        return {
            "master_path": master_path,
            "vocal_path": vocal_path,
            "accompaniment_path": accomp_path
        }

music_gen = MusicGenerator()

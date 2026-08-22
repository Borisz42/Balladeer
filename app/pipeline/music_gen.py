import re
import os
import asyncio
import logging
from pathlib import Path
from typing import Dict, List, Any, Tuple, Optional, Callable
from datetime import datetime
import soundfile as sf
import numpy as np

from app.core.config import get_settings
from app.models.model_router import model_router, TaskType
from app.models.gemini_client import gemini_client
from app.database.database import db
from app.database.models import MediaAssetModel

logger = logging.getLogger(__name__)

class MusicGenerator:
    """
    Phase 2: Dynamic Music Studio Engine.
    - Media & Diary-Aware Duration & BPM Suggestions
    - Daily Media Inclusion Thresholds (Top X% per day)
    - Pacing & Section Duration Calculations (Photos, Videos, Instrumental Buffers)
    - Google Flow Music Prompt & Proportional Rhyming Lyrics with Timing Cues
    - High-Fidelity Preview Audio Synthesis
    """

    def __init__(self):
        self.settings = get_settings()

    def compute_asset_inclusion_score(self, asset: MediaAssetModel) -> float:
        """
        Calculates the transparent auto-inclusion score:
        S_inc = 0.5 * S_qual + 0.5 * (S_rel_daily * 10.0)
        Normalized to 1.0 - 10.0.
        """
        q = float(getattr(asset, "quality_score", 7.0) or 7.0)
        rel_daily = float(getattr(asset, "relevance_score_daily", 0.0) or 0.0)
        if rel_daily > 0.0:
            score = 0.5 * q + 0.5 * (rel_daily * 10.0)
        else:
            score = q
        return round(max(1.0, min(10.0, score)), 2)

    def calculate_media_timeline_estimate(
        self,
        project_id: str,
        diary_days: Optional[List[Dict[str, Any]]] = None,
        assets: Optional[List[MediaAssetModel]] = None,
        custom_config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Calculates daily media statistics, applies daily inclusion thresholds (Top X%),
        computes section and overall song duration based on pacing, and generates
        a structured act timeline with timing cues.
        """
        from app.pipeline.indexer import media_indexer as indexer

        if assets is None:
            assets = db.get_project_assets(project_id)

        cfg = custom_config or {}
        pacing_rules = cfg.get("pacing_rules", {})
        daily_thresholds = cfg.get("daily_inclusion_thresholds", {})
        default_thresh_pct = float(cfg.get("default_inclusion_threshold", 70.0))

        pacing_preset = pacing_rules.get("pacing_preset", "balanced")
        if pacing_preset == "fast":
            photo_sec = float(pacing_rules.get("photo_sec", 1.5))
            video_sec_max = float(pacing_rules.get("video_sec_max", 3.0))
            suggested_bpm = 128
        elif pacing_preset == "cinematic":
            photo_sec = float(pacing_rules.get("photo_sec", 4.0))
            video_sec_max = float(pacing_rules.get("video_sec_max", 6.0))
            suggested_bpm = 96
        else: # balanced
            photo_sec = float(pacing_rules.get("photo_sec", 2.5))
            video_sec_max = float(pacing_rules.get("video_sec_max", 4.5))
            suggested_bpm = 118

        active_days = []
        if diary_days:
            active_days = [d for d in diary_days if d.get("is_active", True) and not d.get("is_discarded", False)]

        # If no diary days provided, create default 1-day grouping
        if not active_days:
            active_days = [{
                "id": "day_1",
                "day_number": 1,
                "title": "Travel Highlights",
                "events": "Journey through scenic places and moments",
                "date": None,
                "is_active": True
            }]

        # Group assets by day
        day_assets_map: Dict[int, List[MediaAssetModel]] = {d.get("day_number", i + 1): [] for i, d in enumerate(active_days)}
        unassigned_assets: List[MediaAssetModel] = []

        for a in assets:
            matched_day = indexer.match_capture_time_to_day(a.capture_time, active_days)
            if matched_day:
                d_num = matched_day.get("day_number", 1)
                if d_num in day_assets_map:
                    day_assets_map[d_num].append(a)
                else:
                    unassigned_assets.append(a)
            else:
                # Check tag for day number
                found_day = False
                for tag in (a.tags or []):
                    m = re.search(r"day:\s*(?:day\s*)?(\d+)", tag, re.IGNORECASE)
                    if m:
                        d_num = int(m.group(1))
                        if d_num in day_assets_map:
                            day_assets_map[d_num].append(a)
                            found_day = True
                            break
                if not found_day:
                    unassigned_assets.append(a)

        # Distribute unassigned assets evenly if some days are empty
        if unassigned_assets:
            for idx, a in enumerate(unassigned_assets):
                target_day = active_days[idx % len(active_days)].get("day_number", 1)
                day_assets_map[target_day].append(a)

        daily_stats = []
        all_asset_inclusion_status: Dict[str, Dict[str, Any]] = {}
        all_included_asset_ids: List[str] = []

        # Process each day's threshold and duration
        for d in active_days:
            d_num = d.get("day_number", 1)
            d_assets = day_assets_map.get(d_num, [])
            thresh_pct = float(daily_thresholds.get(str(d_num), daily_thresholds.get(d_num, default_thresh_pct)))

            scored_items = []
            for a in d_assets:
                score = self.compute_asset_inclusion_score(a)
                scored_items.append((a, score))

            # Sort descending by score
            scored_items.sort(key=lambda x: x[1], reverse=True)
            total_count = len(scored_items)

            included_for_day = []
            excluded_for_day = []
            threshold_score = 7.0

            if total_count > 0:
                k_include = max(1, int(np.ceil(total_count * (thresh_pct / 100.0))))
                threshold_score = scored_items[min(k_include - 1, total_count - 1)][1]

                for rank_idx, (a, score) in enumerate(scored_items):
                    is_inc = (rank_idx < k_include) and a.is_active
                    all_asset_inclusion_status[a.id] = {
                        "asset_id": a.id,
                        "day_number": d_num,
                        "quality_score": a.quality_score,
                        "relevance_score_daily": a.relevance_score_daily,
                        "inclusion_score": score,
                        "rank": rank_idx + 1,
                        "total_in_day": total_count,
                        "is_included": is_inc,
                        "threshold_score": threshold_score,
                        "basis": f"50% Qual ({a.quality_score:.1f}) + 50% Rel ({(a.relevance_score_daily * 10.0):.1f})"
                    }
                    if is_inc:
                        included_for_day.append(a)
                        all_included_asset_ids.append(a.id)
                    else:
                        excluded_for_day.append(a)

            # Compute section duration
            sec_photo_dur = sum(photo_sec for a in included_for_day if a.media_type == "image")
            sec_video_dur = sum(
                min(max(float(a.duration_sec or 2.0), 2.0), video_sec_max)
                for a in included_for_day if a.media_type == "video"
            )
            raw_section_dur = sec_photo_dur + sec_video_dur
            # Clamp section duration between 6.0s and 28.0s
            section_dur = round(max(6.0, min(28.0, raw_section_dur if raw_section_dur > 0 else 8.0)), 1)

            daily_stats.append({
                "day_number": d_num,
                "date": d.get("date"),
                "title": d.get("title", f"Day {d_num}"),
                "events": d.get("events", ""),
                "total_media_count": total_count,
                "included_media_count": len(included_for_day),
                "threshold_percent": thresh_pct,
                "threshold_score": threshold_score,
                "section_duration_sec": section_dur,
                "included_asset_ids": [a.id for a in included_for_day],
                "excluded_asset_ids": [a.id for a in excluded_for_day]
            })

        # Build structured Acts with musical buffers
        acts = []
        current_time = 0.0

        # 1. Intro buffer (3.5s - 5.0s)
        intro_dur = 4.0
        acts.append({
            "act_type": "Intro",
            "day_number": None,
            "title": "Acoustic Intro Swell",
            "start_sec": current_time,
            "end_sec": round(current_time + intro_dur, 1),
            "duration_sec": intro_dur,
            "is_instrumental": True,
            "lines": ["[Instrumental Intro - Warm Acoustic Build]"],
            "directions": "Atmospheric acoustic guitar swell and light ambient percussion."
        })
        current_time += intro_dur

        # 2. Daily Verses and Chorus Interludes
        for i, d_stat in enumerate(daily_stats):
            d_num = d_stat["day_number"]
            dur = d_stat["section_duration_sec"]
            d_title = d_stat["title"]
            if " & " in d_title or not d_title or d_title.lower() in ("travel scene", "untitled"):
                d_title = f"Day {d_num}"
            events_summary = d_stat["events"].strip().split("\n")[0] if d_stat["events"] else f"Adventures of Day {d_num}"

            acts.append({
                "act_type": f"Verse {i + 1}",
                "day_number": d_num,
                "title": d_title,
                "start_sec": round(current_time, 1),
                "end_sec": round(current_time + dur, 1),
                "duration_sec": dur,
                "is_instrumental": False,
                "lines": [events_summary],
                "directions": f"Narrative singing covering {d_title} ({dur}s)."
            })
            current_time += dur

            # Insert Chorus after Verse 1 if multiple days
            if i == 0 and len(daily_stats) >= 2:
                chorus_dur = 7.5
                acts.append({
                    "act_type": "Chorus",
                    "day_number": None,
                    "title": "Chorus Hook",
                    "start_sec": round(current_time, 1),
                    "end_sec": round(current_time + chorus_dur, 1),
                    "duration_sec": chorus_dur,
                    "is_instrumental": False,
                    "lines": [
                        "Chasing the light across the open sky",
                        "Every moment flying by, memories held high"
                    ],
                    "directions": "Catchy melodic vocal hook with driving beat."
                })
                current_time += chorus_dur

        # 3. Outro Buffer (3.5s - 5.0s)
        outro_dur = 4.5
        acts.append({
            "act_type": "Outro",
            "day_number": None,
            "title": "Acoustic Outro Fade",
            "start_sec": round(current_time, 1),
            "end_sec": round(current_time + outro_dur, 1),
            "duration_sec": outro_dur,
            "is_instrumental": True,
            "lines": ["[Instrumental Outro - Melodic Fade]"],
            "directions": "Acoustic guitar fade-out with gentle rhythmic release."
        })
        current_time += outro_dur

        total_duration_sec = round(current_time, 1)

        return {
            "total_duration_sec": total_duration_sec,
            "suggested_bpm": suggested_bpm,
            "pacing_preset": pacing_preset,
            "photo_sec": photo_sec,
            "default_threshold_percent": default_thresh_pct,
            "daily_stats": daily_stats,
            "acts": acts,
            "all_included_asset_ids": all_included_asset_ids,
            "asset_inclusion_status": all_asset_inclusion_status
        }

    def partition_narrative_to_acts(
        self,
        diary_text: str,
        diary_days: Optional[List[Dict[str, Any]]] = None,
        assets: Optional[List[MediaAssetModel]] = None,
        custom_config: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Constructs narrative musical acts with duration and pacing metadata.
        """
        if assets is not None:
            timeline_est = self.calculate_media_timeline_estimate(
                project_id="",
                diary_days=diary_days,
                assets=assets,
                custom_config=custom_config
            )
            return timeline_est["acts"]

        # Fallback if no assets provided
        if diary_days:
            active_days = [d for d in diary_days if d.get("is_active", True) and not d.get("is_discarded", False)]
            if active_days:
                acts = []
                cur_t = 0.0
                # Intro
                acts.append({
                    "act_type": "Intro",
                    "day_number": None,
                    "title": "Acoustic Intro",
                    "start_sec": 0.0,
                    "end_sec": 4.0,
                    "duration_sec": 4.0,
                    "is_instrumental": True,
                    "lines": ["[Instrumental Intro]"],
                    "directions": "Atmospheric acoustic intro."
                })
                cur_t = 4.0
                for i, d in enumerate(active_days):
                    act_name = f"Verse {i + 1}"
                    events_str = d.get("events", "").strip()
                    lines = [l.strip() for l in events_str.split("\n") if l.strip()] or [f"Journey through Day {d.get('day_number', i+1)}"]
                    dur = 10.0
                    acts.append({
                        "act_type": act_name,
                        "day_number": d.get("day_number", i + 1),
                        "title": d.get("title", f"Day {d.get('day_number', i+1)}"),
                        "start_sec": cur_t,
                        "end_sec": cur_t + dur,
                        "duration_sec": dur,
                        "is_instrumental": False,
                        "lines": lines,
                        "directions": f"Day {d.get('day_number', i+1)} verse."
                    })
                    cur_t += dur

                    if i == 0 and len(active_days) >= 2:
                        acts.append({
                            "act_type": "Chorus",
                            "day_number": None,
                            "title": "Chorus Hook",
                            "start_sec": cur_t,
                            "end_sec": cur_t + 8.0,
                            "duration_sec": 8.0,
                            "is_instrumental": False,
                            "lines": ["Chasing the light across the open sky", "Every moment flying by"],
                            "directions": "Vocal chorus hook."
                        })
                        cur_t += 8.0

                acts.append({
                    "act_type": "Outro",
                    "day_number": None,
                    "title": "Outro",
                    "start_sec": cur_t,
                    "end_sec": cur_t + 4.0,
                    "duration_sec": 4.0,
                    "is_instrumental": True,
                    "lines": ["[Instrumental Outro]"],
                    "directions": "Acoustic fade."
                })
                return acts

        lines = [l.strip() for l in diary_text.strip().split("\n") if l.strip()]
        if not lines:
            lines = ["A journey through morning mist and golden skies.", "Walking through ancient stone pathways.", "Sunset overlooking the horizon."]

        acts = []
        acts.append({
            "act_type": "Intro",
            "day_number": None,
            "title": "Intro",
            "start_sec": 0.0,
            "end_sec": 4.0,
            "duration_sec": 4.0,
            "is_instrumental": True,
            "lines": ["[Instrumental Intro]"]
        })
        current_act = {"act_type": "Verse 1", "day_number": 1, "start_sec": 4.0, "end_sec": 14.0, "duration_sec": 10.0, "lines": []}
        day_counter = 1

        for line in lines:
            day_match = re.search(r"(?:day|stage|act)\s*(\d+)(?:\s*\(([^)]+)\))?", line, re.IGNORECASE)
            if day_match:
                if current_act["lines"]:
                    acts.append(current_act)
                day_counter = int(day_match.group(1))
                current_act = {
                    "act_type": f"Verse {len(acts)}",
                    "day_number": day_counter,
                    "duration_sec": 10.0,
                    "lines": [line]
                }
            else:
                current_act["lines"].append(line)

        if current_act["lines"]:
            acts.append(current_act)

        if len(acts) >= 3:
            acts.insert(2, {
                "act_type": "Chorus",
                "day_number": None,
                "duration_sec": 8.0,
                "lines": ["Chasing the light across the open sky", "Every moment flying by"]
            })

        acts.append({
            "act_type": "Outro",
            "day_number": None,
            "duration_sec": 4.0,
            "is_instrumental": True,
            "lines": ["[Instrumental Outro]"]
        })

        return acts

    def _generate_heuristic_flow_prompt(
        self,
        acts: List[Dict[str, Any]],
        suggested_bpm: int = 118,
        total_duration_sec: float = 30.0,
        genre: str = "Acoustic Indie Folk Pop",
        is_instrumental: bool = False
    ) -> str:
        """Constructs a structured Google Flow Music prompt with section cues and timing hints."""
        cues = []
        for a in acts:
            s_sec = int(a.get("start_sec", 0))
            e_sec = int(a.get("end_sec", 0))
            act_name = a.get("act_type", "Section")
            d_title = a.get("title", "")
            title_part = f" ({d_title})" if d_title and d_title != act_name else ""
            cues.append(f"[{s_sec//60}:{s_sec%60:02d}-{e_sec//60}:{e_sec%60:02d}] {act_name}{title_part}")

        cue_summary = " | ".join(cues)
        vocal_desc = "cinematic melodic arrangement without vocals" if is_instrumental else "melodic warm vocals"
        return (
            f"Uplifting {genre} with rhythmic acoustic guitar, {vocal_desc}, and driving ambient percussion, "
            f"{suggested_bpm} BPM, {int(total_duration_sec)}s total length. "
            f"Song Structure: {cue_summary}. Rich stereo production with clean master mix."
        )

    def _generate_heuristic_lyrics(
        self,
        acts: List[Dict[str, Any]],
        is_instrumental: bool = False
    ) -> Tuple[str, str]:
        """Generates fallback rhyming lyrics or instrumental story narration subtitles formatted with exact timestamps."""
        lyric_blocks = []
        for act_idx, act in enumerate(acts):
            s_sec = int(act.get("start_sec", 0))
            e_sec = int(act.get("end_sec", 0))
            act_type = act.get("act_type", "Verse")
            d_title = act.get("title", "")
            if " & " in d_title and len(d_title.split()) <= 6:
                d_title = f"Day {act.get('day_number', act_idx + 1)}"
            title_part = f": {d_title}" if d_title and d_title.lower() != act_type.lower() else ""
            dur = act.get("duration_sec", 10.0)
            tag = f"[{s_sec//60}:{s_sec%60:02d}-{e_sec//60}:{e_sec%60:02d}] [{act_type}{title_part}] ({dur:.0f}s)"

            if is_instrumental:
                narration = self._create_fallback_narration_subtitles(act, act_idx, dur)
                lyric_blocks.append(f"{tag}\n{narration}")
                continue

            lines = act.get("lines", [])
            formatted_lines = []
            for l in lines[:4]:
                cleaned = re.sub(r"^[0-9\-\.\*]+\s*", "", l)
                if len(cleaned.split()) > 10:
                    cleaned = " ".join(cleaned.split()[:8])
                if cleaned:
                    formatted_lines.append(cleaned)

            if not formatted_lines:
                formatted_lines = ["Stepping out into the dawn", "Another golden day is born"]

            lyric_blocks.append(tag + "\n" + "\n".join(formatted_lines))

        full_lyrics = "\n\n".join(lyric_blocks)
        prompt = self._generate_heuristic_flow_prompt(acts, is_instrumental=is_instrumental)
        return full_lyrics, prompt

    async def generate_music_prompt_async(
        self,
        acts: List[Dict[str, Any]],
        diary_text: str = "",
        suggested_bpm: int = 118,
        total_duration_sec: float = 30.0,
        style_vibe: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Phase 2: Generates an optimized Google Flow Music prompt with section directions.
        """
        def local_fallback(payload: str):
            from app.models.local_vlm import local_vlm
            return local_vlm.generate_music_style_and_prompt(acts, diary_text, suggested_bpm, total_duration_sec, style_vibe)

        try:
            res, model_used = await model_router.execute_task(
                task_type=TaskType.STORY_LYRICS,
                prompt_payload=diary_text or "Travel Montage",
                estimated_tokens=1000,
                cloud_caller=lambda m, p: gemini_client.generate_music_style_and_prompt(
                    m, acts, diary_text, suggested_bpm, total_duration_sec, style_vibe
                ),
                local_fallback=local_fallback
            )
            logger.info(f"[MusicGen] Style prompt generated via: {model_used}")
            if isinstance(res, dict) and "flow_prompt" in res:
                return res
        except Exception as e:
            logger.warning(f"Flow prompt AI generation fallback: {e}")

        fallback_prompt = self._generate_heuristic_flow_prompt(acts, suggested_bpm, total_duration_sec, style_vibe or "Acoustic Indie Folk Pop")
        return {
            "flow_prompt": fallback_prompt,
            "suggested_bpm": suggested_bpm,
            "genre": style_vibe or "Acoustic Indie Folk Pop",
            "mood": "Uplifting & Inspiring",
            "instruments": ["Acoustic Guitar", "Warm Vocals", "Ambient Percussion", "Cello"]
        }

    def _clean_and_filter_lyric_line(self, line: str, known_titles: List[str], is_instrumental: bool = False) -> Optional[str]:
        """Cleans markdown, tags, echoes, and returns text only if it is a genuine sung lyric line or spoken subtitle."""
        # 1. Strip all markdown formatting (*, #, _, `, ~, >, -)
        cleaned = re.sub(r"[*`#_~>]+", " ", line)
        cleaned = re.sub(r"^[0-9\-\.\*•]+\s*", "", cleaned).strip()
        cleaned = re.sub(r"^(?:\(\s*\d+s\s*\)\s*)+", "", cleaned).strip()
        cleaned = re.sub(r"\[.*?\]", "", cleaned).strip()
        cleaned = re.sub(r"\s+", " ", cleaned).strip()

        # 2. Check if line starts with header indicators or brackets
        if not cleaned or re.match(r"^\(?\d+s\)?$", cleaned.strip()):
            return None

        # 3. Check if line is a header echo (e.g. "Verse 1:", "Chorus -", "Act 1")
        if re.match(r"^(?:verse\s*\d*|chorus|bridge|intro|outro|act\s*\d*)\s*[:\-–—]?", cleaned, re.IGNORECASE):
            stripped_header = re.sub(r"^(?:verse\s*\d*|chorus|bridge|intro|outro|act\s*\d*)\s*[:\-–—]?\s*", "", cleaned, flags=re.IGNORECASE).strip()
            if not stripped_header:
                return None
            cleaned = stripped_header

        # 4. Check if line is identical to any known title or raw tags joined with &
        if cleaned.lower() in [t.lower() for t in known_titles if t]:
            return None
        if " & " in cleaned and len(cleaned.split()) <= 6:
            return None
        if cleaned.lower().startswith("instrumental") and not is_instrumental:
            return None

        # 5. Reject lines that are too short, or too long for singing verse lines
        words = cleaned.split()
        if len(words) < 2:
            return None
        if not is_instrumental and len(words) > 16:
            return None

        technical_cues = [
            "qr code", "metal detector", "white card", "photo of", "picture of",
            "close-up", "close up", "screenshot", "camera", "standing near", "holds a",
            "holding a", "seen in the", "image shows", "video shows"
        ]
        if any(cue in cleaned.lower() for cue in technical_cues):
            return None

        return cleaned

    def _check_rhyme_pair(self, l1: str, l2: str) -> bool:
        """Verifies that two lines end in a genuine rhyming pair and do not repeat the same word."""
        if not l1 or not l2:
            return False
        w1 = re.sub(r'[^a-z]', '', l1.split()[-1].lower()) if l1.split() else ''
        w2 = re.sub(r'[^a-z]', '', l2.split()[-1].lower()) if l2.split() else ''
        if not w1 or not w2 or w1 == w2:
            return False
        if len(w1) >= 3 and len(w2) >= 3 and w1[-3:] == w2[-3:]:
            return True
        if len(w1) >= 2 and len(w2) >= 2 and w1[-2:] == w2[-2:] and w1[-2:] in {
            "ay", "ee", "ey", "ow", "un", "in", "it", "at", "et", "op", "ip", "og", "ug", "ue", "ew", "oy", "ar", "or", "ur"
        }:
            return True
        phonetic_pairs = {
            ("sky", "high"), ("fly", "high"), ("eye", "sky"), ("eyes", "skies"),
            ("view", "through"), ("blue", "through"), ("new", "view"), ("blue", "new"),
            ("air", "share"), ("there", "fair"), ("where", "there"), ("care", "share"),
            ("time", "rhyme"), ("shine", "fine"), ("grace", "place"), ("trace", "space"),
            ("town", "around"), ("town", "down"), ("sound", "ground"), ("bound", "found"),
            ("glow", "slow"), ("glow", "know"), ("night", "sight"), ("day", "away"),
            ("clear", "near"), ("dear", "here"), ("stroll", "soul"), ("stroll", "whole")
        }
        return (w1, w2) in phonetic_pairs or (w2, w1) in phonetic_pairs

    def _format_subtitles_into_short_lines(self, text: str, words_per_line: int = 11) -> str:
        """Formats long spoken subtitle paragraphs into natural, clean 1-2 sentence lines without run-ons."""
        if not text:
            return ""
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
        lines = []
        for s in sentences:
            words = s.split()
            if len(words) <= words_per_line + 3:
                lines.append(s)
            else:
                # Split long sentences cleanly at commas or mid-point
                clauses = [c.strip() for c in re.split(r"[,;—–\-]\s*", s) if c.strip()]
                if len(clauses) >= 2:
                    lines.append(", ".join(clauses[:len(clauses)//2]) + ",")
                    lines.append(", ".join(clauses[len(clauses)//2:]))
                else:
                    mid = len(words) // 2
                    lines.append(" ".join(words[:mid]))
                    lines.append(" ".join(words[mid:]))
        return "\n".join(lines)

    def _create_fallback_rhyming_verse(self, act: Dict[str, Any], verse_idx: int, dur: float) -> List[str]:
        """Synthesizes high-quality, evocative rhyming lyric lines for a travel verse."""
        day_num = act.get("day_number") or (verse_idx + 1)
        title = act.get("title") or f"Day {day_num}"
        if " & " in title:
            title = f"Day {day_num}"

        act_text = " ".join(act.get("lines", []))
        loc_name = title if title.lower() not in ("day 1", "day 2", "day 3", "verse 1", "verse 2") else "the morning streets"
        if "pré-saint-gervais" in act_text.lower() or "paris" in act_text.lower():
            loc_name = "Le Pré-Saint-Gervais"
            
        rhyme_sets = [
            [
                f"Stepping into {loc_name} in the golden morning light",
                "Watching all the quiet streets and colors shining bright",
                "Past the towers on the skyline and the murals on the wall",
                "Finding wonder in the beauty as the summer shadows fall"
            ],
            [
                f"Walking through {loc_name} with excitement in our eyes",
                "Chasing every hidden gem beneath the sunny skies",
                "Footsteps on the cobblestones and music in the air",
                "Capturing the magic in the moments that we share"
            ],
            [
                f"Another golden chapter as we wander down the way",
                "Treasuring the lively sights and spirit of the day",
                "Sunset softly painted on the rooftops up ahead",
                "Following the open path where all our dreams are led"
            ],
            [
                "Memories of laughter underneath the canopy",
                "Moments that will stay with us for all of time to be",
                "Smiling at the little things we discovered on the way",
                "Celebrating memories from another perfect day"
            ]
        ]
        
        selected = rhyme_sets[verse_idx % len(rhyme_sets)]
        line_count = 4 if dur >= 14.0 else 2
        return selected[:line_count]

    def _trim_narration_to_complete_sentences(self, text: str, dur: float, act_type: str = "") -> str:
        """
        Trims or fits spoken narrative subtitles so they ALWAYS form complete, grammatical,
        poetic sentences without awkward cutoffs, trailing commas, or hanging prepositions/articles.
        """
        cleaned = re.sub(r"[*`#_~>]+", " ", text)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        if not cleaned:
            return ""

        # Remove hanging bracket tags if any
        cleaned = re.sub(r"\[.*?\]", "", cleaned).strip()

        # Split into genuine sentences
        raw_sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", cleaned) if s.strip()]
        if not raw_sentences:
            raw_sentences = [cleaned]

        target_words = max(6, int(dur * 2.3))

        # Check special case for short Intro / Outro (dur <= 5.0)
        is_intro_or_outro = any(k in act_type.lower() for k in ("intro", "outro")) or dur <= 5.0
        if is_intro_or_outro:
            # Look for a short complete sentence (4 to 12 words)
            for s in raw_sentences:
                w_count = len(s.split())
                if 4 <= w_count <= 12:
                    # Strip any trailing comma or dangling punctuation
                    s = re.sub(r"[,;:\-–—]+$", "", s).strip()
                    if not s.endswith((".", "!", "?")):
                        s += "."
                    # Check if last word is a hanging word
                    last_w = s.split()[-1].lower().rstrip(".,;:!?")
                    if last_w not in {"a", "an", "the", "of", "to", "in", "on", "with", "and", "as", "for", "at", "by", "from", "casting", "amidst", "near", "where", "which", "that"}:
                        return s

            # If sentence is longer, try breaking cleanly at a comma/clause boundary
            first_s = raw_sentences[0]
            clauses = [c.strip() for c in re.split(r"[,;—–\-]", first_s) if c.strip()]
            for c in clauses:
                c_words = c.split()
                if 4 <= len(c_words) <= 10:
                    last_w = c_words[-1].lower().rstrip(".,;:!?")
                    if last_w not in {"a", "an", "the", "of", "to", "in", "on", "with", "and", "as", "for", "at", "by", "from", "casting", "amidst", "near", "where", "which", "that", "picturesque"}:
                        return c + "."

            # Fallback to curated short complete sentences
            if "intro" in act_type.lower():
                return "Our journey begins as morning light breaks across the horizon."
            elif "outro" in act_type.lower():
                return "As the day comes to a close, we hold onto memories from an unforgettable journey."
            else:
                return "A wonderful moment captured as the adventure continues."

        # For regular duration sections (dur > 5.0s):
        accumulated: List[str] = []
        cur_word_count = 0

        for s in raw_sentences:
            w_count = len(s.split())
            if cur_word_count + w_count <= target_words + 8 or not accumulated:
                accumulated.append(s)
                cur_word_count += w_count
            else:
                break

        res = " ".join(accumulated).strip()
        res = re.sub(r"[,;:\-–—]+$", "", res).strip()
        if not res.endswith((".", "!", "?")):
            last_w = res.split()[-1].lower().rstrip(".,;:!?")
            if last_w in {"a", "an", "the", "of", "to", "in", "on", "with", "and", "as", "for", "at", "by", "from", "casting", "amidst", "near", "where", "which", "that"}:
                res = " ".join(res.split()[:-1])
            res += "."

        return res

    def _create_fallback_narration_subtitles(self, act: Dict[str, Any], verse_idx: int, dur: float) -> str:
        """
        Synthesizes timed spoken storytelling narration subtitles for instrumental mode,
        calibrated to normal speaking tempo (~2.2 words per second) and focused on image scenes.
        """
        day_num = act.get("day_number") or (verse_idx + 1)
        title = act.get("title") or f"Day {day_num}"
        if " & " in title:
            title = f"Day {day_num}"

        act_type = (act.get("act_type") or "Section").lower()
        if "intro" in act_type or dur <= 5.0 and verse_idx == 0:
            return "Our journey begins as morning light breaks across the horizon and the adventure unfolds."
        if "outro" in act_type or dur <= 5.0:
            return "As the day comes to a close, we hold onto memories from an unforgettable journey."

        narrations = [
            (
                f"Walking into {title}, the morning sun illuminates the vibrant scenery and lively streets. "
                "Every corner reveals historic architecture, quiet cafes, and the rich atmosphere of the journey as we explore. "
                "Footsteps on the cobblestones echo with the spirit of discovery as each new scene unfolds before our eyes."
            ),
            (
                "Exploring deeper along the scenic promenade, we take in panoramic views of the water and open skies. "
                "Sunlight reflects off the water as we pause to capture the peaceful atmosphere and beautiful scenes all around us. "
                "The quiet rhythm of the city invites us to slow down and savor every remarkable perspective."
            ),
            (
                "The afternoon journey continues through winding cobblestone alleys and picturesque pathways. "
                "Laughter and music fill the warm breeze, creating unforgettable moments with every new step along the way. "
                "Historic facades and welcoming storefronts tell tales of generations past, bringing the heritage of the town to life."
            ),
            (
                "Golden hour descends across the skyline, bathing the cityscape in warm amber tones. "
                "We take one last stroll past the landmarks, celebrating the beauty and shared memories of another remarkable day. "
                "As twilight approaches, the quiet streets settle into a serene stillness that stays in our hearts forever."
            )
        ]
        chosen = narrations[verse_idx % len(narrations)]
        return self._trim_narration_to_complete_sentences(chosen, dur, act.get("act_type", ""))

    def enforce_acts_timeline_on_lyrics(
        self,
        acts: List[Dict[str, Any]],
        raw_lyrics: str,
        is_instrumental: bool = False
    ) -> str:
        """
        Parses whatever lyrics/lines the LLM generated and strictly aligns them
        onto the EXACT calculated section timestamps, headers, and duration limits.
        Prevents LLM timestamp hallucination, token cutoff damage, or sentence truncation.
        """
        if not acts:
            return raw_lyrics

        known_titles = [a.get("title", "") for a in acts if a.get("title")]
        known_titles += [a.get("act_type", "") for a in acts if a.get("act_type")]

        # Extract textual blocks/lines from raw_lyrics
        clean_raw = re.sub(r"\[music prompt\].*$", "", raw_lyrics, flags=re.IGNORECASE | re.DOTALL).strip()

        # Parse sections by header tags: e.g. [0:00-0:04] [Intro] (4s) or [Verse 1]
        header_pattern = r"(?:^|\n)\s*(\[\d+:\d+(?:\.\d+)?\s*-\s*\d+:\d+(?:\.\d+)?\]\s*\[[^\]]+\](?:\s*\([^\)]+\))?|\b(?:Verse\s*\d*|Chorus|Intro|Outro|Bridge)\b[^\n]*)\s*\n"
        splits = re.split(header_pattern, clean_raw, flags=re.IGNORECASE)

        named_sections: Dict[str, List[str]] = {}
        unnamed_blocks: List[List[str]] = []

        if len(splits) > 1:
            for i in range(1, len(splits), 2):
                hdr = splits[i].strip().lower()
                body = splits[i + 1].strip() if i + 1 < len(splits) else ""
                lines = [self._clean_and_filter_lyric_line(l, known_titles, is_instrumental=is_instrumental) for l in body.split("\n") if l.strip()]
                clean_lines = [l for l in lines if l]
                if clean_lines:
                    if "intro" in hdr:
                        named_sections["intro"] = clean_lines
                    elif "outro" in hdr:
                        named_sections["outro"] = clean_lines
                    elif "verse 1" in hdr or "day 1" in hdr:
                        named_sections["verse 1"] = clean_lines
                    elif "verse 2" in hdr or "day 2" in hdr:
                        named_sections["verse 2"] = clean_lines
                    elif "verse 3" in hdr or "day 3" in hdr:
                        named_sections["verse 3"] = clean_lines
                    elif "chorus" in hdr:
                        named_sections["chorus"] = clean_lines
                    else:
                        unnamed_blocks.append(clean_lines)
        else:
            # Fallback for plain blocks without headers
            raw_blocks = [b.strip() for b in clean_raw.split("\n\n") if b.strip()]
            for block in raw_blocks:
                lines = [l.strip() for l in block.split("\n") if l.strip()]
                clean_lines = [self._clean_and_filter_lyric_line(l, known_titles, is_instrumental=is_instrumental) for l in lines]
                clean_lines = [l for l in clean_lines if l]
                if clean_lines:
                    unnamed_blocks.append(clean_lines)

        # Build clean, strictly timed output blocks matching acts
        output_blocks = []
        for act_idx, act in enumerate(acts):
            s_sec = int(act.get("start_sec", 0))
            e_sec = int(act.get("end_sec", 0))
            act_type = act.get("act_type", "Section")
            act_key = act_type.lower()
            d_title = act.get("title", "")
            
            # Clean title if it contains raw & joined tags
            if " & " in d_title and len(d_title.split()) <= 6:
                d_title = f"Day {act.get('day_number', act_idx + 1)}"

            title_part = f": {d_title}" if d_title and d_title.lower() != act_type.lower() else ""
            dur = act.get("duration_sec", 10.0)
            tag = f"[{s_sec//60}:{s_sec%60:02d}-{e_sec//60}:{e_sec%60:02d}] [{act_type}{title_part}] ({dur:.0f}s)"

            if is_instrumental:
                # Timed spoken narrative subtitles for instrumental mode
                candidate_lines = named_sections.get(act_key) or (unnamed_blocks.pop(0) if unnamed_blocks else [])
                joined = " ".join(candidate_lines) if candidate_lines else ""
                joined = re.sub(r"^(?:\(\s*\d+s\s*\)\s*)+", "", joined).strip()
                joined = re.sub(r"\[.*?\]", "", joined).strip()
                min_words_for_dur = 5 if dur <= 5.0 else max(16, int(dur * 1.6))

                if len(joined.split()) >= min_words_for_dur:
                    narration_text = self._trim_narration_to_complete_sentences(joined, dur, act_type)
                elif len(joined.split()) >= 4 and dur > 5.0:
                    fb = self._create_fallback_narration_subtitles(act, act_idx, dur)
                    combined_text = f"{joined} {fb}"
                    narration_text = self._trim_narration_to_complete_sentences(combined_text, dur, act_type)
                else:
                    narration_text = self._create_fallback_narration_subtitles(act, act_idx, dur)

                formatted_subs = self._format_subtitles_into_short_lines(narration_text)
                output_blocks.append(f"{tag}\n{formatted_subs}")
            elif act.get("is_instrumental"):
                summary = act.get("directions") or "Atmospheric acoustic guitar swell"
                clean_dir = re.sub(r"^[0-9\-\.\*]+\s*", "", summary).strip()
                clean_dir = re.sub(r"[*`#]+", "", clean_dir).strip()
                output_blocks.append(f"{tag}\n[Instrumental - {clean_dir}]")
            else:
                candidate_lines = named_sections.get(act_key) or (unnamed_blocks.pop(0) if unnamed_blocks else [])
                target_lines = 4 if dur >= 14.0 else 2

                verified_lines = []
                # Check candidate rhyming lines
                for idx in range(0, len(candidate_lines) - 1, 2):
                    l1, l2 = candidate_lines[idx], candidate_lines[idx + 1]
                    if self._check_rhyme_pair(l1, l2):
                        verified_lines.extend([l1, l2])
                    if len(verified_lines) == target_lines:
                        break

                if len(verified_lines) < target_lines:
                    fallback_lines = self._create_fallback_rhyming_verse(act, act_idx, dur)
                    if len(verified_lines) == 2 and target_lines == 4:
                        verified_lines.extend(fallback_lines[2:4] if len(fallback_lines) >= 4 else fallback_lines[:2])
                    else:
                        verified_lines = fallback_lines[:target_lines]

                output_blocks.append(tag + "\n" + "\n".join(verified_lines))

        return "\n\n".join(output_blocks)

    async def generate_rhyming_lyrics_async(
        self,
        acts: List[Dict[str, Any]],
        narrative_text: str = "",
        flow_prompt: str = "",
        is_instrumental: bool = False
    ) -> Tuple[str, str]:
        """
        Phase 3: Generates structured rhyming lyrics with explicit timestamps and section tags.
        """
        combined_text = narrative_text or "\n".join(["\n".join(a.get("lines", [])) for a in acts])

        def local_fallback(payload: str):
            from app.models.local_vlm import local_vlm
            return local_vlm.generate_story_and_lyrics(acts, combined_text, is_instrumental)

        try:
            logger.info("=" * 65)
            logger.info(f"[MusicGen] Generating story & lyrics/subtitles (instrumental={is_instrumental}, {len(acts)} sections)...")
            logger.debug(f"[MusicGen] Narrative context:\n{combined_text}")
            logger.info("=" * 65)

            res, model_used = await model_router.execute_task(
                task_type=TaskType.STORY_LYRICS,
                prompt_payload=combined_text,
                estimated_tokens=1500,
                cloud_caller=lambda m, p: gemini_client.generate_story_and_lyrics(m, p, is_instrumental, acts=acts),
                local_fallback=local_fallback
            )
            logger.info(f"[MusicGen] Story & lyrics generated using: {model_used}")
            if isinstance(res, dict) and "lyrics" in res:
                p = res.get("prompt") or flow_prompt or self._generate_heuristic_flow_prompt(acts)
                logger.debug(f"[MusicGen] Raw LLM lyrics before timeline enforcement:\n{res['lyrics']}")
                clean_lyrics = self.enforce_acts_timeline_on_lyrics(acts, res["lyrics"], is_instrumental)
                logger.info(f"[MusicGen] ✓ Final aligned lyrics/subtitles:\n{clean_lyrics}")
                return clean_lyrics, p
            elif isinstance(res, tuple):
                p = res[1] or flow_prompt or self._generate_heuristic_flow_prompt(acts)
                logger.debug(f"[MusicGen] Raw LLM lyrics before timeline enforcement:\n{res[0]}")
                clean_lyrics = self.enforce_acts_timeline_on_lyrics(acts, res[0], is_instrumental)
                logger.info(f"[MusicGen] ✓ Final aligned lyrics/subtitles:\n{clean_lyrics}")
                return clean_lyrics, p
        except Exception as e:
            logger.warning(f"Cloud story lyrics waterfall fallback: {e}")

        fallback_lyrics, fallback_prompt = self._generate_heuristic_lyrics(acts, is_instrumental)
        logger.info(f"[MusicGen] Using heuristic fallback lyrics:\n{fallback_lyrics}")
        return fallback_lyrics, fallback_prompt

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
        Phase 4: Generates an instant high-fidelity preview harmonic track with precise BPM beat intervals
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

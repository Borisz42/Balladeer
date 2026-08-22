import os
import re
import json
import base64
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
import httpx
from PIL import Image, ImageOps

from app.core.config import get_settings

logger = logging.getLogger("balladeer.gemini_client")

# Model aliases to map waterfall IDs to exact, active Google AI Studio API model slugs
MODEL_API_MAP = {
    "gemini-3.5-flash-lite": ["gemini-3.5-flash-lite", "gemini-3.1-flash-lite", "gemini-flash-lite-latest"],
    "gemini-3.1-flash-lite": ["gemini-3.1-flash-lite", "gemini-3.5-flash-lite", "gemini-flash-lite-latest"],
    "gemini-2.5-flash-lite": ["gemini-3.5-flash-lite", "gemini-3.1-flash-lite"],
    "gemini-3.7-flash":      ["gemini-3.7-flash", "gemini-3.6-flash", "gemini-3.5-flash", "gemini-flash-latest"],
    "gemini-3.6-flash":      ["gemini-3.6-flash", "gemini-3.5-flash", "gemini-flash-latest"],
    "gemini-3.5-flash":      ["gemini-3.5-flash", "gemini-3.6-flash", "gemini-flash-latest"],
    "gemini-2.5-flash":      ["gemini-3.5-flash", "gemini-3.6-flash"],
    "gemma-4-31b":           ["gemma-4-31b-it", "gemma-4-26b-a4b-it", "gemini-3.5-flash-lite"],
    "gemma-4-26b":           ["gemma-4-26b-a4b-it", "gemma-4-31b-it", "gemini-3.5-flash-lite"],
}


class GoogleAIStudioClient:
    """
    Asynchronous client for Google AI Studio Free Tier API calls (Gemini & Gemma).
    Handles multimodal batch image analysis and Google Flow Music prompt optimization.
    """

    def __init__(self):
        self.base_url = "https://generativelanguage.googleapis.com/v1beta/models"

    def _get_api_key(self) -> str:
        settings = get_settings()
        return (
            settings.google_ai.api_key.strip() or
            os.environ.get("GEMINI_API_KEY", "").strip() or
            os.environ.get("GOOGLE_API_KEY", "").strip()
        )

    def _encode_image_to_part(self, image_path: Path, max_dim: int = 1024) -> Dict[str, Any]:
        """Resizes large images to conserve tokens & bandwidth, returning an inline base64 part."""
        with Image.open(image_path) as img:
            img = ImageOps.exif_transpose(img) or img
            img = img.convert("RGB")
            if max(img.size) > max_dim:
                img.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)
            
            import io
            buffer = io.BytesIO()
            img.save(buffer, format="JPEG", quality=85)
            b64_data = base64.b64encode(buffer.getvalue()).decode("utf-8")

        return {
            "inline_data": {
                "mime_type": "image/jpeg",
                "data": b64_data
            }
        }

    async def analyze_image_batch(
        self,
        model_name: str,
        images: List[Any]
    ) -> List[Dict[str, Any]]:
        """
        Submits a batch of images to Gemini / Gemma for parallel multimodal indexing.
        Accepts List[Path], List[Dict[str, Any]], or List[Tuple[Path, Any]].
        Returns a list of structured analysis dicts matching the input order.
        """
        api_key = self._get_api_key()
        if not api_key:
            raise ValueError("No Google AI Studio / Gemini API key configured.")

        candidate_slugs = MODEL_API_MAP.get(model_name, [model_name, "gemini-3.5-flash-lite"])

        parsed_items: List[Tuple[Path, str]] = []
        for it in images:
            if isinstance(it, dict):
                p = Path(it.get("path") or it.get("file_path"))
                meta = it.get("metadata")
                meta_str = ""
                if isinstance(meta, dict):
                    parts = []
                    if meta.get("gps_lat") and meta.get("gps_lon"):
                        parts.append(f"GPS: {meta['gps_lat']}°, {meta['gps_lon']}°")
                    if meta.get("capture_time"):
                        parts.append(f"Time: {meta['capture_time']}")
                    if meta.get("camera_make") or meta.get("camera_model"):
                        cam = f"{meta.get('camera_make', '')} {meta.get('camera_model', '')}".strip()
                        parts.append(f"Camera: {cam}")
                    if meta.get("width") and meta.get("height"):
                        parts.append(f"Resolution: {meta['width']}x{meta['height']}")
                    if parts:
                        meta_str = f" [Metadata: {' | '.join(parts)}]"
                elif isinstance(meta, str) and meta.strip():
                    meta_str = f" [Metadata: {meta.strip()}]"
                parsed_items.append((p, meta_str))
            elif isinstance(it, tuple) and len(it) >= 2:
                p = Path(it[0])
                meta_str = f" [Metadata: {str(it[1])}]" if str(it[1]).strip() else ""
                parsed_items.append((p, meta_str))
            else:
                p = Path(it)
                parsed_items.append((p, ""))

        parts: List[Dict[str, Any]] = []
        parts.append({
            "text": (
                "You are an expert cinematic video editor and photographer. "
                "Analyze the following batch of numbered vacation/travel photos. Picture metadata (GPS coordinates, camera, time, dimensions) is provided where available. "
                "For EACH photo in order, provide:\n"
                "1. index (integer starting at 0)\n"
                "2. caption (concise descriptive sentence for song lyrics matching)\n"
                "3. tags (array of 3 to 6 descriptive lowercase keywords like 'nature', 'sunset', 'city', 'portrait')\n"
                "4. quality_score (float from 1.0 to 10.0 reflecting photographic composition, sharpness, lighting balance, and visual appeal; e.g. 5.5 for blurry/poor exposure, 7.5 for good shots, 8.8+ for pro/cinematic shots)\n\n"
                "Return ONLY a valid JSON array of objects with schema:\n"
                "[{\"index\": 0, \"caption\": \"...\", \"tags\": [\"...\"], \"quality_score\": 7.8}]"
            )
        })

        for idx, (p, meta_str) in enumerate(parsed_items):
            parts.append({"text": f"--- Photo #{idx}: {p.name}{meta_str} ---"})
            parts.append(self._encode_image_to_part(p))

        payload = {
            "contents": [{"parts": parts}],
            "generationConfig": {
                "temperature": 0.2,
                "maxOutputTokens": 4096,
                "responseMimeType": "application/json"
            }
        }

        last_error = None
        for slug in candidate_slugs:
            url = f"{self.base_url}/{slug}:generateContent?key={api_key}"
            logger.info(f"[Google-AI] Dispatching batch vision request to '{slug}' for {len(parsed_items)} media item(s): {[p.name for p, _ in parsed_items]}")
            logger.info(f"[Google-AI] Vision Prompt: \"{parts[0]['text'][:100]}...\"")
            try:
                async with httpx.AsyncClient(timeout=35.0) as client:
                    resp = await client.post(url, json=payload)
                    if resp.status_code != 200:
                        last_error = f"Google AI Studio Error {resp.status_code} on {slug}: {resp.text[:200]}"
                        logger.warning(f"[Google-AI] {last_error}")
                        continue

                    data = resp.json()
                    candidates = data.get("candidates", [])
                    if not candidates:
                        last_error = f"No candidates returned from {slug}"
                        logger.warning(f"[Google-AI] {last_error}")
                        continue

                    raw_text = candidates[0]["content"]["parts"][0]["text"].strip()
                    cleaned_text = re.sub(r"^```json\s*", "", raw_text, flags=re.IGNORECASE)
                    cleaned_text = re.sub(r"^```\s*", "", cleaned_text)
                    cleaned_text = re.sub(r"\s*```$", "", cleaned_text).strip()

                    parsed = json.loads(cleaned_text)
                    if not isinstance(parsed, list):
                        if isinstance(parsed, dict) and "photos" in parsed:
                            parsed = parsed["photos"]
                        else:
                            parsed = [parsed]

                    results = []
                    for i, (p, _) in enumerate(parsed_items):
                        match = next((item for item in parsed if item.get("index") == i), None)
                        if not match and i < len(parsed):
                            match = parsed[i]
                        
                        if match:
                            results.append({
                                "caption": str(match.get("caption", f"Travel scene: {p.stem}")),
                                "tags": list(match.get("tags", ["travel", "scenic"])),
                                "quality_score": float(max(1.0, min(10.0, float(match.get("quality_score", 7.5)))))
                            })
                        else:
                            results.append({
                                "caption": f"Travel scene: {p.stem.replace('_', ' ')}",
                                "tags": ["travel", "scenic"],
                                "quality_score": 7.0
                            })

                    logger.info(f"[Google-AI] ✓ Model '{slug}' successfully indexed {len(results)} items. Sample caption: \"{results[0]['caption']}\"")
                    return results
            except Exception as e:
                last_error = str(e)
                logger.warning(f"[Google-AI] Exception on '{slug}': {e}")
                continue



        raise RuntimeError(last_error or f"Failed to call Google AI Studio API for {model_name}")

    async def generate_music_style_and_prompt(
        self,
        model_name: str,
        acts: List[Dict[str, Any]],
        narrative_text: str = "",
        suggested_bpm: int = 118,
        total_duration_sec: float = 30.0,
        style_vibe: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Phase 2: Generates an optimized Google Flow Music prompt with section cues and duration hints.
        """
        api_key = self._get_api_key()
        if not api_key:
            raise ValueError("No Google AI Studio / Gemini API key configured.")

        candidate_slugs = MODEL_API_MAP.get(model_name, [model_name, "gemini-3.7-flash", "gemini-3.6-flash"])

        structure_summary = []
        for a in acts:
            s_sec = int(a.get("start_sec", 0))
            e_sec = int(a.get("end_sec", 0))
            dur = a.get("duration_sec", 10.0)
            structure_summary.append(
                f"- [{s_sec//60}:{s_sec%60:02d}-{e_sec//60}:{e_sec%60:02d}] {a.get('act_type', 'Section')}: {a.get('title', '')} ({dur:.0f}s duration)"
            )
        struct_str = "\n".join(structure_summary)

        vibe_hint = f"Desired Style/Genre: {style_vibe}\n" if style_vibe else ""

        prompt_instruction = (
            f"You are an expert music producer and Google Flow Music prompt engineer. "
            f"Generate an optimized musical style prompt tailored for Google Flow Music (MusicFX / Lyria) "
            f"for a travel montage video with exact target duration {int(total_duration_sec)} seconds and tempo {suggested_bpm} BPM.\n\n"
            f"{vibe_hint}"
            f"DIARY CONTEXT:\n{narrative_text.strip()}\n\n"
            f"SONG SECTION TIMELINE:\n{struct_str}\n\n"
            f"REQUIREMENTS:\n"
            f"1. Generate a single-paragraph 'flow_prompt' specifying genre, key instruments (e.g. acoustic guitar, cello, percussion), "
            f"tempo ({suggested_bpm} BPM), dynamic energy arc, and section breakdown with timestamp clues.\n"
            f"2. Suggest 'genre', 'mood', and 'instruments' (array of 3-5 strings).\n"
            f"3. Return ONLY a valid JSON object with schema:\n"
            f"{{\n"
            f"  \"flow_prompt\": \"...\",\n"
            f"  \"suggested_bpm\": {suggested_bpm},\n"
            f"  \"genre\": \"...\",\n"
            f"  \"mood\": \"...\",\n"
            f"  \"instruments\": [\"...\"]\n"
            f"}}"
        )

        payload = {
            "contents": [{"parts": [{"text": prompt_instruction}]}],
            "generationConfig": {
                "temperature": 0.5,
                "maxOutputTokens": 1024,
                "responseMimeType": "application/json"
            }
        }

        last_error = None
        for slug in candidate_slugs:
            url = f"{self.base_url}/{slug}:generateContent?key={api_key}"
            try:
                async with httpx.AsyncClient(timeout=25.0) as client:
                    resp = await client.post(url, json=payload)
                    if resp.status_code != 200:
                        last_error = f"Error {resp.status_code} on {slug}: {resp.text[:200]}"
                        continue
                    data = resp.json()
                    candidates = data.get("candidates", [])
                    if not candidates:
                        continue
                    raw_text = candidates[0]["content"]["parts"][0]["text"].strip()
                    cleaned = re.sub(r"^```json\s*", "", raw_text, flags=re.IGNORECASE)
                    cleaned = re.sub(r"^```\s*", "", cleaned)
                    cleaned = re.sub(r"\s*```$", "", cleaned).strip()
                    parsed = json.loads(cleaned)
                    return {
                        "flow_prompt": str(parsed.get("flow_prompt", "")),
                        "suggested_bpm": int(parsed.get("suggested_bpm", suggested_bpm)),
                        "genre": str(parsed.get("genre", "Acoustic Indie Folk")),
                        "mood": str(parsed.get("mood", "Uplifting & Atmospheric")),
                        "instruments": list(parsed.get("instruments", ["Acoustic Guitar", "Vocals", "Percussion"]))
                    }
            except Exception as e:
                last_error = str(e)
                continue

        raise RuntimeError(last_error or f"Failed to generate music style prompt for {model_name}")

    async def generate_story_and_lyrics(
        self,
        model_name: str,
        narrative_text: str,
        is_instrumental: bool = False,
        acts: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Structures a travel diary into musical acts with proportional rhyming lyrics
        and timestamp cues optimized for Google Flow Music.
        """
        api_key = self._get_api_key()
        if not api_key:
            raise ValueError("No Google AI Studio / Gemini API key configured.")

        candidate_slugs = MODEL_API_MAP.get(model_name, [model_name, "gemini-3.7-flash", "gemini-3.6-flash"])

        acts_context = ""
        if acts:
            lines = []
            for a in acts:
                s_sec = int(a.get("start_sec", 0))
                e_sec = int(a.get("end_sec", 0))
                dur = a.get("duration_sec", 10.0)
                lines.append(
                    f"[{s_sec//60}:{s_sec%60:02d}-{e_sec//60}:{e_sec%60:02d}] [{a.get('act_type', 'Section')}] ({dur:.0f}s): {a.get('title', '')} - {a.get('directions', '')}"
                )
            acts_context = "PLANNED SECTION TIMELINE:\n" + "\n".join(lines) + "\n\n"

        if is_instrumental:
            prompt_instruction = (
                f"You are a cinematic documentary narrator and music producer. "
                f"Transform this travel log/diary and scene descriptions into timed spoken narrative voiceover subtitles "
                f"for a travel video with background instrumental music.\n\n"
                f"{acts_context}"
                f"DIARY LOG & SCENE CAPTIONS:\n{narrative_text}\n\n"
                f"REQUIREMENTS:\n"
                f"1. Generate timed spoken narrative subtitles for each section matching normal speaking tempo (~2.2 words per second). "
                f"Describe the travel story with specific focus on what is seen in the photos and video scenes. Use timestamp headers like [0:04-0:15] [Verse 1: Day 1 - Paris].\n"
                f"   - For 4s Intro and Outro sections, write EXACTLY ONE short, complete grammatical sentence of 6 to 9 words (e.g. 'Our journey begins as morning light breaks across the horizon.'). Never leave partial or cut-off sentences.\n"
                f"2. Generate an 'optimized_flow_music_prompt' tailored specifically for Google Flow Music (MusicFX / Lyria) "
                f"for background instrumental music (e.g. Acoustic Indie Folk, Warm Lo-Fi, Cinematic Ambient) with tempo (BPM) and section breakdown.\n"
                f"3. Return ONLY a valid JSON object with keys: 'lyrics' (full formatted timed narrative subtitles string with timestamp headers), "
                f"'flow_prompt' (the Google Flow Music prompt), and 'suggested_bpm' (integer 90-140)."
            )
        else:
            prompt_instruction = (
                f"You are an award-winning music composer and songwriter. "
                f"Transform this travel log/diary into evocative rhyming song lyrics proportional to section durations.\n\n"
                f"{acts_context}"
                f"DIARY LOG:\n{narrative_text}\n\n"
                f"REQUIREMENTS:\n"
                f"1. Generate structured rhyming lyrics with explicit timestamps matching each section, e.g. [0:04-0:15] [Verse 1: Day 1 - Paris]. "
                f"Scale the lines to the section length (e.g. 2 lines for 8-10s, 4 lines for 15s+). "
                f"For instrumental sections (Intro, Outro, Interludes), include a descriptive cue in brackets like [Instrumental - Acoustic Guitar Build].\n"
                f"2. Generate an 'optimized_flow_music_prompt' tailored specifically for Google Flow Music (MusicFX / Lyria) "
                f"including genre, acoustic/electric instruments, tempo (BPM), vocal mood, and atmospheric texture with section breakdown.\n"
                f"3. Return ONLY a valid JSON object with keys: 'lyrics' (full formatted lyric string with headers and timestamps), "
                f"'flow_prompt' (the Google Flow Music prompt), and 'suggested_bpm' (integer 90-140)."
            )

        payload = {
            "contents": [{"parts": [{"text": prompt_instruction}]}],
            "generationConfig": {
                "temperature": 0.7,
                "maxOutputTokens": 2048,
                "responseMimeType": "application/json"
            }
        }

        last_error = None
        for slug in candidate_slugs:
            url = f"{self.base_url}/{slug}:generateContent?key={api_key}"
            logger.info("=" * 65)
            logger.info(f"[Google-AI] Calling '{slug}' for story structure & Google Flow Music prompt generation...")
            logger.info(f"[Google-AI] [Prompt-Instruction]:\n{prompt_instruction}")
            logger.info("=" * 65)
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    resp = await client.post(url, json=payload)
                    if resp.status_code != 200:
                        last_error = f"Google AI Studio Error {resp.status_code} on {slug}: {resp.text[:200]}"
                        logger.warning(f"[Google-AI] {last_error}")
                        continue

                    data = resp.json()
                    candidates = data.get("candidates", [])
                    if not candidates:
                        continue

                    raw_text = candidates[0]["content"]["parts"][0]["text"].strip()
                    logger.info(f"[Google-AI] [LLM-Response] Raw response from '{slug}':\n{raw_text}")
                    logger.debug(f"[Google-AI] [LLM-Debug] Full candidate metadata: {candidates[0].get('finishReason', 'UNKNOWN')}")

                    cleaned_text = re.sub(r"^```json\s*", "", raw_text, flags=re.IGNORECASE)
                    cleaned_text = re.sub(r"^```\s*", "", cleaned_text)
                    cleaned_text = re.sub(r"\s*```$", "", cleaned_text).strip()

                    parsed = json.loads(cleaned_text)
                    flow_prompt = str(parsed.get("flow_prompt", "Cinematic acoustic folk pop with warm guitars and inspiring melodic vocals, 120 BPM."))
                    lyrics_str = str(parsed.get("lyrics", ""))
                    suggested_bpm = int(parsed.get("suggested_bpm", 120))

                    logger.info(f"[Google-AI] ✓ Model '{slug}' generated lyrics ({len(lyrics_str.splitlines())} lines) & Flow Music Prompt (BPM: {suggested_bpm})")

                    return {
                        "lyrics": lyrics_str,
                        "prompt": flow_prompt,
                        "suggested_bpm": suggested_bpm
                    }
            except Exception as e:
                last_error = str(e)
                logger.warning(f"[Google-AI] Exception on '{slug}': {e}")
                continue

        raise RuntimeError(last_error or f"Failed to call Google AI Studio API for {model_name}")

    async def draft_travel_log(
        self,
        model_name: str,
        media_items: List[Dict[str, Any]],
        project_title: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Drafts a rich, comprehensive day-by-day travel diary/itinerary from ALL indexed media items,
        organizing full day timelines and synthesizing detailed multi-sentence narrative summaries.
        """
        api_key = self._get_api_key()
        if not api_key:
            raise ValueError("No Google AI Studio / Gemini API key configured.")

        candidate_slugs = MODEL_API_MAP.get(model_name, [model_name, "gemini-3.7-flash", "gemini-3.6-flash", "gemini-3.5-flash-lite"])

        title_header = f"Trip Title: {project_title}\n" if project_title else ""

        # Chronologically sort all media items
        sorted_items = sorted(
            media_items,
            key=lambda x: str(x.get("capture_time") or "9999-99-99T99:99:99")
        )

        # Group items by date for clear prompt structure
        grouped_by_date: Dict[str, List[Dict[str, Any]]] = {}
        for it in sorted_items:
            ts = str(it.get("capture_time") or "").strip()
            date_key = ts.split("T")[0] if "T" in ts else (ts[:10] if len(ts) >= 10 else "Undated")
            if date_key not in grouped_by_date:
                grouped_by_date[date_key] = []
            grouped_by_date[date_key].append(it)

        # Format full media timeline grouped by date
        media_sections = []
        item_counter = 1
        for date_key, items in grouped_by_date.items():
            date_label = f"DATE: {date_key}" if date_key != "Undated" else "DATE: Sequence Bucket"
            lines = [f"=== {date_label} ({len(items)} items recorded) ==="]
            for it in items[:150]:  # Support up to 150 items per day without truncating the rest of the trip
                ts = it.get("capture_time") or "Time unknown"
                m_type = it.get("media_type") or "media"
                caption = it.get("caption") or "Travel scene"
                tags = ", ".join(it.get("tags") or [])
                lines.append(f"  [{item_counter}] [{m_type.upper()}] Time: {ts} | Description: {caption} | Tags: {tags}")
                item_counter += 1
            media_sections.append("\n".join(lines))

        media_context = "\n\n".join(media_sections)

        prompt_instruction = (
            f"You are an expert travel writer and montage story director.\n"
            f"Below is a complete, chronological list of indexed photos and videos from a travel expedition, organized by day.\n\n"
            f"{title_header}"
            f"TOTAL MEDIA ITEMS: {len(sorted_items)}\n\n"
            f"MEDIA TIMELINE & DESCRIPTIONS BY DAY:\n"
            f"{media_context}\n\n"
            f"TASK & WRITING INSTRUCTIONS:\n"
            f"1. Structure the entire trip into sequential days (day_number 1, 2, 3...).\n"
            f"2. For EVERY day, examine ALL media descriptions in that day's section (from morning start, midday explorations, afternoon discoveries, to evening/night activities).\n"
            f"3. Write an evocative, specific 'title' for each day capturing the day's main destinations and experiences.\n"
            f"4. Write a comprehensive, cohesive 'events' summary (3 to 6 vivid narrative sentences) for each day that incorporates ALL the sights, activities, culinary stops, landmarks, and atmospheres described across the day's media. DO NOT only summarize the first couple of items; synthesize the full arc of the day.\n"
            f"5. Return ONLY a valid JSON object matching this schema:\n"
            f"   - 'start_date': string (YYYY-MM-DD)\n"
            f"   - 'finish_date': string (YYYY-MM-DD)\n"
            f"   - 'diary_days': array of day objects: [\n"
            f"       {{\n"
            f"         'day_number': int,\n"
            f"         'date': 'YYYY-MM-DD',\n"
            f"         'title': 'Day Title',\n"
            f"         'events': 'Comprehensive multi-sentence narrative summary of all media in this day',\n"
            f"         'is_active': true,\n"
            f"         'is_discarded': false\n"
            f"       }}\n"
            f"     ]\n"
            f"   - 'narrative_text': string (cohesive full story combining each Day N (YYYY-MM-DD): [events] separated by newlines)"
        )

        payload = {
            "contents": [{"parts": [{"text": prompt_instruction}]}],
            "generationConfig": {
                "temperature": 0.7,
                "maxOutputTokens": 8192,
                "responseMimeType": "application/json"
            }
        }

        last_error = None
        for slug in candidate_slugs:
            url = f"{self.base_url}/{slug}:generateContent?key={api_key}"
            logger.info("=" * 65)
            logger.info(f"[Google-AI] Calling '{slug}' to draft comprehensive travel log from {len(media_items)} media items...")
            logger.info(f"[Google-AI] [Prompt-Instruction]:\n{prompt_instruction}")
            logger.info("=" * 65)
            try:
                async with httpx.AsyncClient(timeout=60.0) as client:
                    resp = await client.post(url, json=payload)
                    if resp.status_code != 200:
                        last_error = f"Google AI Studio Error {resp.status_code} on {slug}: {resp.text[:200]}"
                        logger.warning(f"[Google-AI] {last_error}")
                        continue

                    data = resp.json()
                    candidates = data.get("candidates", [])
                    if not candidates:
                        last_error = f"No candidates returned from {slug}"
                        continue

                    raw_text = candidates[0]["content"]["parts"][0]["text"].strip()
                    logger.info(f"[Google-AI] [LLM-Response] Raw response from '{slug}':\n{raw_text}")
                    logger.debug(f"[Google-AI] [LLM-Debug] Finish reason: {candidates[0].get('finishReason', 'UNKNOWN')}")

                    cleaned_text = re.sub(r"^```json\s*", "", raw_text, flags=re.IGNORECASE)
                    cleaned_text = re.sub(r"^```\s*", "", cleaned_text)
                    cleaned_text = re.sub(r"\s*```$", "", cleaned_text).strip()

                    parsed = json.loads(cleaned_text)
                    diary_days = parsed.get("diary_days", [])
                    start_date = str(parsed.get("start_date", ""))
                    finish_date = str(parsed.get("finish_date", ""))
                    narrative_text = str(parsed.get("narrative_text", ""))

                    if not narrative_text and diary_days:
                        lines = []
                        for d in diary_days:
                            d_num = d.get("day_number", 1)
                            d_date = f" ({d['date']})" if d.get("date") else ""
                            lines.append(f"Day {d_num}{d_date}: {d.get('events', '')}")
                        narrative_text = "\n".join(lines)

                    logger.info(f"[Google-AI] ✓ Model '{slug}' successfully drafted comprehensive travel log ({len(diary_days)} days).")
                    return {
                        "start_date": start_date,
                        "finish_date": finish_date,
                        "diary_days": diary_days,
                        "narrative_text": narrative_text
                    }
            except Exception as e:
                last_error = str(e)
                logger.warning(f"[Google-AI] Exception on '{slug}': {e}")
                continue

        raise RuntimeError(last_error or f"Failed to draft travel log via Google AI Studio for {model_name}")

gemini_client = GoogleAIStudioClient()


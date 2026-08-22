import os
import re
import json
import logging
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple, Callable
from PIL import Image, ImageFilter, ImageOps, ImageEnhance

from app.core.config import get_settings
from app.database.models import (
    TimelineSliceModel,
    AudioTrackModel,
    AlignedWordModel,
    MediaAssetModel
)

logger = logging.getLogger(__name__)

ASPECT_RATIO_RESOLUTIONS = {
    "16:9": (1920, 1080),
    "9:16": (1080, 1920),
    "1:1": (1080, 1080),
    "4:5": (1080, 1350),
    "21:9": (2560, 1080),
}

def hex_to_ass_color(hex_str: str, default: str = "&H00FFFFFF", alpha_hex: str = "00") -> str:
    """Converts #RRGGBB hex color to ASS &HAABBGGRR format."""
    if not hex_str:
        return default
    clean = hex_str.strip().lstrip("#")
    if len(clean) == 6:
        r, g, b = clean[0:2], clean[2:4], clean[4:6]
        return f"&H{alpha_hex}{b.upper()}{g.upper()}{r.upper()}"
    return default


class VideoCompositor:
    """
    Phase 5: Multi-Aspect Ratio Media Transformation (Blurred BG Fill, Ken Burns, Ambient Glow),
    Synchronized Karaoke, Narrative Scene Descriptions & Event Card Subtitles,
    Cinematic Color Grading, EBU R128 Audio Mastering, and FFmpeg Hardware Compositing.
    """

    def __init__(self):
        self.settings = get_settings()

    def generate_ass_subtitles(
        self,
        audio_track: AudioTrackModel,
        output_path: Path,
        resolution: Tuple[int, int] = (1920, 1080),
        custom_config: Optional[Dict[str, Any]] = None,
        slices: Optional[List[TimelineSliceModel]] = None
    ) -> Path:
        width, height = resolution
        cfg = custom_config or {}
        sub_cfg = cfg.get("lyrics_style", {})
        overlays_cfg = cfg.get("text_overlays", {})

        font_name = sub_cfg.get("font_family", "Arial")
        font_size = int(sub_cfg.get("font_size", 48))
        mode = sub_cfg.get("subtitle_mode", "auto")
        primary_color = hex_to_ass_color(sub_cfg.get("highlight_color", "#2dd4bf"), default="&H00BFD42D")
        secondary_color = hex_to_ass_color(sub_cfg.get("base_color", "#ffffff"), default="&H00FFFFFF")
        outline_color = hex_to_ass_color(sub_cfg.get("outline_color", "#000000"), default="&H00000000")
        back_color = hex_to_ass_color(sub_cfg.get("backdrop_color", "#000000"), default="&H80000000", alpha_hex="80")
        outline_width = int(sub_cfg.get("outline_width", 3))
        shadow_depth = int(sub_cfg.get("shadow_depth", 2))
        margin_v = int(sub_cfg.get("margin_v", 70))
        alignment = int(sub_cfg.get("alignment", 2))

        header = f"""[Script Info]
Title: Balladeer Subtitles
ScriptType: v4.00+
WrapStyle: 0
ScaledBorderAndShadow: yes
PlayResX: {width}
PlayResY: {height}

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Karaoke,{font_name},{font_size},{secondary_color},{primary_color},{outline_color},{back_color},-1,0,0,0,100,100,1,0,1,{outline_width},{shadow_depth},{alignment},40,40,{margin_v},1
Style: NarrativeSub,{font_name},{max(32, font_size - 4)},{secondary_color},{primary_color},{outline_color},{back_color},-1,0,0,0,100,100,1,0,1,{outline_width},{shadow_depth},{alignment},50,50,{margin_v},1
Style: EventCard,{font_name},{max(34, font_size - 6)},&H00E0E0E0,&H00FFFFFF,&H00000000,&H90000000,-1,0,0,0,100,100,1,0,1,2,2,2,40,40,65,1
Style: IntroTitle,{font_name},56,&H00FFFFFF,&H002DD4BF,&H00000000,&HA0000000,-1,0,0,0,100,100,2,0,1,3,2,5,60,60,80,1
Style: Watermark,{font_name},24,&H80E0E0E0,&H80FFFFFF,&H80000000,&H00000000,-1,0,0,0,100,100,1,0,1,1,1,9,30,30,30,1
Style: OutroCard,{font_name},46,&H00F8FAFC,&H002DD4BF,&H00000000,&H90000000,-1,0,0,0,100,100,1,0,1,2,2,5,60,60,80,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
        events = []
        total_duration = audio_track.beat_grid[-1] if audio_track.beat_grid else 30.0

        # 1. Overlay: Intro Title Card
        intro_enabled = overlays_cfg.get("intro_enabled", True)
        intro_title = overlays_cfg.get("intro_title")
        intro_subtitle = overlays_cfg.get("intro_subtitle")
        intro_duration = float(overlays_cfg.get("intro_duration", 3.5))

        if intro_enabled and intro_title:
            s_str = self._sec_to_ass_time(0.0)
            e_str = self._sec_to_ass_time(min(intro_duration, total_duration))
            sub_text = f"\\N{{\\fs32\\c&H00CBD5E1&}}{intro_subtitle}" if intro_subtitle else ""
            events.append(f"Dialogue: 2,{s_str},{e_str},IntroTitle,,0,0,0,,{{\\fad(600,600)}}{intro_title}{sub_text}")

        # 2. Overlay: Creator Watermark Badge
        watermark_text = overlays_cfg.get("watermark_text")
        if watermark_text:
            s_str = self._sec_to_ass_time(0.0)
            e_str = self._sec_to_ass_time(total_duration)
            events.append(f"Dialogue: 1,{s_str},{e_str},Watermark,,0,0,0,,{watermark_text}")

        # 3. Subtitles / Lyrics / Narrative Mode Content
        is_instrumental = audio_track.is_instrumental

        if mode == "hidden":
            pass
        elif mode == "narrative_descriptions":
            if slices:
                for s in slices:
                    caption = (s.custom_caption or "").strip()
                    if not caption and s.asset:
                        caption = (s.asset.caption or "").strip()
                    if not caption:
                        caption = f"Scene #{s.clip_order + 1}"

                    t_start = max(0.0, s.timeline_start_sec)
                    t_end = max(t_start + 0.5, s.timeline_end_sec)
                    s_str = self._sec_to_ass_time(t_start)
                    e_str = self._sec_to_ass_time(t_end)
                    events.append(f"Dialogue: 0,{s_str},{e_str},NarrativeSub,,0,0,0,,{{\\fad(300,300)}}{caption}")
            else:
                lines = [l.strip() for l in audio_track.lyrics.split("\n") if l.strip()]
                card_interval = max(4.0, total_duration / max(len(lines), 1))
                for i, line in enumerate(lines):
                    t_start = i * card_interval
                    t_end = min(t_start + card_interval - 0.5, total_duration)
                    s_str = self._sec_to_ass_time(t_start)
                    e_str = self._sec_to_ass_time(t_end)
                    events.append(f"Dialogue: 0,{s_str},{e_str},NarrativeSub,,0,0,0,,{{\\fad(400,400)}}{line}")

        elif mode == "chapter_event_cards":
            lines = [l.strip() for l in audio_track.lyrics.split("\n") if l.strip()]
            card_interval = max(4.0, total_duration / max(len(lines), 1))
            for i, line in enumerate(lines):
                t_start = i * card_interval
                t_end = min(t_start + card_interval - 0.5, total_duration)
                s_str = self._sec_to_ass_time(t_start)
                e_str = self._sec_to_ass_time(t_end)
                events.append(f"Dialogue: 0,{s_str},{e_str},EventCard,,0,0,0,,{{\\fad(400,400)}}{line}")
        else:
            # "karaoke_lyrics" or "auto" default: renders timed word-for-word synced lyrics or spoken narration subtitles
            aligned = audio_track.aligned_lyrics
            if not aligned:
                events.append("Dialogue: 0,0:00:00.00,0:00:10.00,Karaoke,,0,0,0,,Balladeer Montage")
            else:
                enable_word_highlight = sub_cfg.get("enable_word_highlight", True)
                
                # Group words by line_index if defined, otherwise by 5-word chunks
                lines_chunks: List[List[AlignedWordModel]] = []
                current_line_idx = None
                current_chunk: List[AlignedWordModel] = []

                for w in aligned:
                    w_line = w.line_index
                    if w_line is not None:
                        if current_line_idx is None or w_line == current_line_idx:
                            current_chunk.append(w)
                            current_line_idx = w_line
                        else:
                            if current_chunk:
                                lines_chunks.append(current_chunk)
                            current_chunk = [w]
                            current_line_idx = w_line
                    else:
                        current_chunk.append(w)
                        if len(current_chunk) >= 5:
                            lines_chunks.append(current_chunk)
                            current_chunk = []

                if current_chunk:
                    lines_chunks.append(current_chunk)

                for chunk in lines_chunks:
                    if not chunk:
                        continue
                    line_start = chunk[0].snapped_start
                    line_end = chunk[-1].snapped_end + 0.3
                    start_str = self._sec_to_ass_time(line_start)
                    end_str = self._sec_to_ass_time(line_end)

                    if enable_word_highlight:
                        karaoke_tokens = []
                        for w in chunk:
                            dur_cs = max(10, int((w.snapped_end - w.snapped_start) * 100))
                            karaoke_tokens.append(f"{{\\k{dur_cs}}}{w.word}")
                        line_text = " ".join(karaoke_tokens)
                        events.append(f"Dialogue: 0,{start_str},{end_str},Karaoke,,0,0,0,,{line_text}")
                    else:
                        line_text = " ".join([w.word for w in chunk])
                        events.append(f"Dialogue: 0,{start_str},{end_str},Karaoke,,0,0,0,,{{\\fad(200,200)}}{line_text}")

        # 4. Overlay: Outro End Card
        outro_text = overlays_cfg.get("outro_text")
        if outro_text and total_duration > 4.0:
            outro_dur = float(overlays_cfg.get("outro_duration", 3.0))
            t_start = max(0.0, total_duration - outro_dur)
            s_str = self._sec_to_ass_time(t_start)
            e_str = self._sec_to_ass_time(total_duration)
            events.append(f"Dialogue: 2,{s_str},{e_str},OutroCard,,0,0,0,,{{\\fad(600,600)}}{outro_text}")

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(header + "\n".join(events))

        return output_path

    def _sec_to_ass_time(self, seconds: float) -> str:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        centisecs = int(round((seconds - int(seconds)) * 100))
        if centisecs >= 100:
            centisecs = 99
        return f"{hours}:{minutes:02d}:{secs:02d}.{centisecs:02d}"

    def apply_color_filter_to_pil(
        self,
        img: Image.Image,
        filter_preset: str = "natural",
        vignette: bool = False,
        filter_name: Optional[str] = None,
        enable_vignette: Optional[bool] = None
    ) -> Image.Image:
        """Applies cinematic color grading LUT preset and optional vignette to a PIL Image."""
        chosen_filter = filter_name or filter_preset or "natural"
        is_vignette = enable_vignette if enable_vignette is not None else vignette

        if chosen_filter == "teal_orange":
            r, g, b = img.split()
            r = ImageEnhance.Brightness(r).enhance(1.08)
            b = ImageEnhance.Brightness(b).enhance(1.05)
            img = Image.merge("RGB", (r, g, b))
            img = ImageEnhance.Color(img).enhance(1.2)
        elif chosen_filter == "warm_gold":
            r, g, b = img.split()
            r = ImageEnhance.Brightness(r).enhance(1.12)
            g = ImageEnhance.Brightness(g).enhance(1.04)
            b = ImageEnhance.Brightness(b).enhance(0.92)
            img = Image.merge("RGB", (r, g, b))
            img = ImageEnhance.Color(img).enhance(1.15)
        elif filter_preset == "vintage_35mm":
            img = ImageEnhance.Contrast(img).enhance(0.92)
            img = ImageEnhance.Color(img).enhance(0.85)
            r, g, b = img.split()
            r = ImageEnhance.Brightness(r).enhance(1.06)
            b = ImageEnhance.Brightness(b).enhance(0.94)
            img = Image.merge("RGB", (r, g, b))
        elif filter_preset == "cyberpunk":
            img = ImageEnhance.Contrast(img).enhance(1.25)
            img = ImageEnhance.Color(img).enhance(1.4)
            r, g, b = img.split()
            r = ImageEnhance.Brightness(r).enhance(1.1)
            b = ImageEnhance.Brightness(b).enhance(1.15)
            img = Image.merge("RGB", (r, g, b))
        elif filter_preset == "noir_bw":
            img = img.convert("L").convert("RGB")
            img = ImageEnhance.Contrast(img).enhance(1.35)
        elif filter_preset == "vibrant_pop":
            img = ImageEnhance.Color(img).enhance(1.35)
            img = ImageEnhance.Contrast(img).enhance(1.1)

        return img

    def process_image_frame(
        self,
        image_path: Path,
        output_path: Path,
        resolution: Tuple[int, int] = (1920, 1080),
        bg_mode: str = "blurred_fill",
        blur_radius: Optional[int] = None,
        blur_scale: Optional[float] = None,
        color_filter: str = "natural",
        vignette: bool = False
    ) -> Path:
        target_w, target_h = resolution
        output_path.parent.mkdir(parents=True, exist_ok=True)
        b_radius = blur_radius or self.settings.video.blur_radius
        b_scale = blur_scale or self.settings.video.blur_scale

        try:
            with Image.open(image_path) as src_img:
                src_img = ImageOps.exif_transpose(src_img) or src_img
                src_img = src_img.convert("RGB")
                src_img = self.apply_color_filter_to_pil(src_img, filter_preset=color_filter, vignette=vignette)
                src_w, src_h = src_img.size

                target_aspect = target_w / target_h
                src_aspect = src_w / src_h
                canvas = Image.new("RGB", (target_w, target_h), (0, 0, 0))

                if bg_mode == "blurred_fill" and abs(target_aspect - src_aspect) > 0.02:
                    scale_bg = max(target_w / src_w, target_h / src_h) * b_scale
                    bg_w, bg_h = int(src_w * scale_bg), int(src_h * scale_bg)
                    bg_img = src_img.resize((bg_w, bg_h), Image.Resampling.BILINEAR)

                    left = (bg_w - target_w) // 2
                    top = (bg_h - target_h) // 2
                    bg_crop = bg_img.crop((left, top, left + target_w, top + target_h))
                    blurred_bg = bg_crop.filter(ImageFilter.GaussianBlur(radius=b_radius))
                    canvas.paste(blurred_bg, (0, 0))
                elif bg_mode == "ambient_glow" and abs(target_aspect - src_aspect) > 0.02:
                    scale_bg = max(target_w / src_w, target_h / src_h) * 1.5
                    bg_w, bg_h = int(src_w * scale_bg), int(src_h * scale_bg)
                    bg_img = src_img.resize((bg_w, bg_h), Image.Resampling.BILINEAR)
                    left = (bg_w - target_w) // 2
                    top = (bg_h - target_h) // 2
                    bg_crop = bg_img.crop((left, top, left + target_w, top + target_h))
                    blurred_bg = bg_crop.filter(ImageFilter.GaussianBlur(radius=40))
                    canvas.paste(blurred_bg, (0, 0))

                # Scale foreground image preserving aspect ratio
                scale_fg = min(target_w / src_w, target_h / src_h)
                fg_w, fg_h = int(src_w * scale_fg), int(src_h * scale_fg)
                fg_resized = src_img.resize((fg_w, fg_h), Image.Resampling.LANCZOS)

                fg_x = (target_w - fg_w) // 2
                fg_y = (target_h - fg_h) // 2
                canvas.paste(fg_resized, (fg_x, fg_y))

                canvas.save(output_path, "JPEG", quality=95)
                return output_path
        except Exception as e:
            logger.debug(f"Image frame processing notice: {e}")
            return image_path

    def render_slice_video(
        self,
        slice_model: TimelineSliceModel,
        output_path: Path,
        resolution: Tuple[int, int] = (1920, 1080),
        fps: int = 30,
        custom_config: Optional[Dict[str, Any]] = None
    ) -> Path:
        duration = slice_model.timeline_end_sec - slice_model.timeline_start_sec
        if duration <= 0.05:
            duration = 1.0

        target_w, target_h = resolution
        asset = slice_model.asset
        asset_path = Path(asset.file_path) if asset else None

        cfg = custom_config or {}
        v_fx = cfg.get("video_effects", {})
        color_filter = v_fx.get("color_filter", "natural")
        vignette = v_fx.get("enable_vignette", False)
        blur_radius = v_fx.get("blur_radius", self.settings.video.blur_radius)
        blur_scale = v_fx.get("blur_scale", self.settings.video.blur_scale)
        ken_burns_scale = float(v_fx.get("ken_burns_zoom", 1.25))

        output_path.parent.mkdir(parents=True, exist_ok=True)
        if not asset_path or not asset_path.exists():
            cmd = [
                "ffmpeg", "-y",
                "-f", "lavfi", "-i", f"color=c=0x1e293b:s={target_w}x{target_h}:d={duration}",
                "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(fps),
                str(output_path)
            ]
            subprocess.run(cmd, capture_output=True, check=True)
            return output_path

        is_video = asset.media_type == "video"

        if is_video:
            cmd = [
                "ffmpeg", "-y",
                "-ss", "0.0", "-t", str(duration),
                "-i", str(asset_path),
                "-vf", (
                    f"split[fg][bg];"
                    f"[bg]scale={target_w}*{blur_scale}:{target_h}*{blur_scale}:force_original_aspect_ratio=increase,crop={target_w}:{target_h},boxblur={blur_radius}[bgblur];"
                    f"[fg]scale={target_w}:{target_h}:force_original_aspect_ratio=decrease[fgscale];"
                    f"[bgblur][fgscale]overlay=(W-w)/2:(H-h)/2"
                ),
                "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", "-r", str(fps),
                "-an", str(output_path)
            ]
            try:
                subprocess.run(cmd, capture_output=True, check=True)
                return output_path
            except Exception:
                cmd_fallback = [
                    "ffmpeg", "-y",
                    "-ss", "0.0", "-t", str(duration),
                    "-i", str(asset_path),
                    "-vf", f"scale={target_w}:{target_h}:force_original_aspect_ratio=decrease,pad={target_w}:{target_h}:(ow-iw)/2:(oh-ih)/2",
                    "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", "-r", str(fps),
                    "-an", str(output_path)
                ]
                subprocess.run(cmd_fallback, capture_output=True, check=True)
                return output_path
        else:
            temp_frame_path = output_path.parent / f"frame_{slice_model.id}.jpg"
            self.process_image_frame(
                image_path=asset_path,
                output_path=temp_frame_path,
                resolution=resolution,
                bg_mode=slice_model.bg_mode,
                blur_radius=blur_radius,
                blur_scale=blur_scale,
                color_filter=color_filter,
                vignette=vignette
            )

            if slice_model.enable_ken_burns:
                total_frames = int(duration * fps)
                zoom_rate = max(0.0005, (ken_burns_scale - 1.0) / max(total_frames, 1))
                cmd = [
                    "ffmpeg", "-y",
                    "-loop", "1", "-i", str(temp_frame_path),
                    "-vf", f"zoompan=z='min(zoom+{zoom_rate:.5f},{ken_burns_scale})':d={total_frames}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={target_w}x{target_h}",
                    "-t", str(duration),
                    "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", "-r", str(fps),
                    str(output_path)
                ]
            else:
                cmd = [
                    "ffmpeg", "-y",
                    "-loop", "1", "-i", str(temp_frame_path),
                    "-t", str(duration),
                    "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", "-r", str(fps),
                    str(output_path)
                ]

            subprocess.run(cmd, capture_output=True, check=True)
            return output_path

    def assemble_final_video(
        self,
        project_id: str,
        slices: List[TimelineSliceModel],
        audio_track: AudioTrackModel,
        output_filename: str = "montage.mp4",
        aspect_ratio: str = "16:9",
        custom_config: Optional[Dict[str, Any]] = None,
        progress_callback: Optional[Callable[[str, float], None]] = None
    ) -> Path:
        return self.render_timeline(
            project_id=project_id,
            slices=slices,
            audio_track=audio_track,
            output_path=self.settings.output_dir / project_id / output_filename,
            custom_config=custom_config,
            progress_callback=progress_callback,
            aspect_ratio=aspect_ratio
        )

    def render_timeline(
        self,
        project_id: str,
        slices: List[TimelineSliceModel],
        audio_track: AudioTrackModel,
        output_path: Optional[Path] = None,
        custom_config: Optional[Dict[str, Any]] = None,
        progress_callback: Optional[Callable[[str, float], None]] = None,
        aspect_ratio: Optional[str] = None
    ) -> Path:
        cfg = custom_config or {}
        v_cfg = cfg.get("video", {})
        asp = aspect_ratio or v_cfg.get("aspect_ratio") or cfg.get("aspect_ratio", "16:9")

        out_dir = self.settings.output_dir / project_id
        out_dir.mkdir(parents=True, exist_ok=True)
        final_mp4 = output_path or (out_dir / "montage.mp4")
        final_mp4.parent.mkdir(parents=True, exist_ok=True)

        temp_dir = out_dir / "render_tmp"
        temp_dir.mkdir(parents=True, exist_ok=True)

        resolution = ASPECT_RATIO_RESOLUTIONS.get(asp, self.settings.video.resolution)
        fps = self.settings.video.fps

        if progress_callback:
            progress_callback("Rendering video slices...", 15.0)

        # 1. Render all slice video clips
        clip_paths: List[Path] = []
        total_slices = len(slices)
        for idx, s in enumerate(slices):
            clip_file = temp_dir / f"slice_{s.clip_order:03d}.mp4"
            self.render_slice_video(
                slice_model=s,
                output_path=clip_file,
                resolution=resolution,
                fps=fps,
                custom_config=custom_config
            )
            clip_paths.append(clip_file)
            if progress_callback and total_slices > 0:
                pct = 15.0 + ((idx + 1) / total_slices) * 50.0
                progress_callback(f"Rendered slice {idx + 1}/{total_slices}", round(pct, 1))

        # 2. Concat playlist
        concat_list_path = temp_dir / "concat_list.txt"
        with open(concat_list_path, "w", encoding="utf-8") as f:
            for p in clip_paths:
                esc_path = str(p.resolve()).replace("\\", "/")
                f.write(f"file '{esc_path}'\n")

        # 3. Concatenate video stream
        concat_video_path = temp_dir / "video_concat.mp4"
        cmd_concat = [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0",
            "-i", str(concat_list_path),
            "-c", "copy",
            str(concat_video_path)
        ]
        subprocess.run(cmd_concat, capture_output=True, check=True)

        if progress_callback:
            progress_callback("Generating animated subtitles & overlays...", 75.0)

        # 4. Generate Subtitles & Overlays
        ass_path = temp_dir / "subtitles.ass"
        self.generate_ass_subtitles(
            audio_track=audio_track,
            output_path=ass_path,
            resolution=resolution,
            custom_config=custom_config,
            slices=slices
        )

        if progress_callback:
            progress_callback("Final hardware video mastering...", 85.0)

        # 5. Audio Mastering & Final Encoding
        master_audio = Path(audio_track.master_path)
        encoder = self.settings.video.video_codec
        ass_filter_path = str(ass_path.resolve()).replace("\\", "/").replace(":", "\\:")

        audio_mastering = cfg.get("audio_mastering", {})
        lufs_target = audio_mastering.get("lufs_target", -14)
        fade_in_sec = float(audio_mastering.get("fade_in_sec", 0.5))
        fade_out_sec = float(audio_mastering.get("fade_out_sec", 1.5))
        total_duration = audio_track.beat_grid[-1] if audio_track.beat_grid else 30.0
        fade_out_start = max(0.0, total_duration - fade_out_sec)

        audio_filter = f"loudnorm=I={lufs_target}:LRA=11:TP=-1.5,afade=t=in:ss=0:d={fade_in_sec},afade=t=out:st={fade_out_start:.2f}:d={fade_out_sec}"

        cmd_final = [
            "ffmpeg", "-y",
            "-i", str(concat_video_path),
            "-i", str(master_audio),
            "-vf", f"subtitles='{ass_filter_path}'",
            "-af", audio_filter,
            "-c:v", encoder,
            "-preset", self.settings.video.nvenc_preset,
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-b:a", self.settings.video.audio_bitrate,
            "-shortest",
            str(final_mp4)
        ]

        try:
            res = subprocess.run(cmd_final, capture_output=True, text=True)
            if res.returncode != 0:
                raise RuntimeError(f"NVENC render notice: {res.stderr}")
        except Exception:
            cmd_fallback = [
                "ffmpeg", "-y",
                "-i", str(concat_video_path),
                "-i", str(master_audio),
                "-vf", f"subtitles='{ass_filter_path}'",
                "-af", audio_filter,
                "-c:v", "libx264",
                "-preset", "veryfast",
                "-pix_fmt", "yuv420p",
                "-c:a", "aac",
                "-b:a", self.settings.video.audio_bitrate,
                "-shortest",
                str(final_mp4)
            ]
            subprocess.run(cmd_fallback, capture_output=True, check=True)

        if progress_callback:
            progress_callback("Video render complete!", 100.0)

        return final_mp4


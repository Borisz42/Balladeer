import os
import re
import json
import logging
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from PIL import Image, ImageFilter, ImageOps

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
}

class VideoCompositor:
    """
    Phase 5: Multi-Aspect Ratio Media Transformation (Blurred BG Fill, Ken Burns),
    Synchronized Karaoke & Event Card Subtitles, EBU R128 Audio Mastering,
    and FFmpeg NVENC Hardware Compositing.
    """

    def __init__(self):
        self.settings = get_settings()

    def generate_ass_subtitles(
        self,
        audio_track: AudioTrackModel,
        output_path: Path,
        resolution: Tuple[int, int] = (1920, 1080)
    ) -> Path:
        width, height = resolution
        header = f"""[Script Info]
Title: Balladeer Subtitles
ScriptType: v4.00+
WrapStyle: 0
ScaledBorderAndShadow: yes
PlayResX: {width}
PlayResY: {height}

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Karaoke,Arial,48,&H00FFFFFF,&H0000FFFF,&H00000000,&H80000000,-1,0,0,0,100,100,1,0,1,3,2,2,40,40,70,1
Style: EventCard,Arial,42,&H00E0E0E0,&H00FFFFFF,&H00000000,&H90000000,-1,0,0,0,100,100,1,0,1,2,2,2,40,40,65,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
        events = []
        is_instrumental = audio_track.is_instrumental

        if is_instrumental:
            # Generate Chapter Event Card overlays
            lines = [l.strip() for l in audio_track.lyrics.split("\n") if l.strip()]
            total_duration = audio_track.beat_grid[-1] if audio_track.beat_grid else 30.0
            card_interval = max(4.0, total_duration / max(len(lines), 1))

            for i, line in enumerate(lines):
                t_start = i * card_interval
                t_end = min(t_start + card_interval - 0.5, total_duration)
                s_str = self._sec_to_ass_time(t_start)
                e_str = self._sec_to_ass_time(t_end)
                events.append(f"Dialogue: 0,{s_str},{e_str},EventCard,,0,0,0,,{{\\fad(400,400)}}{line}")
        else:
            # Karaoke word highlights
            aligned = audio_track.aligned_lyrics
            if not aligned:
                events.append("Dialogue: 0,0:00:00.00,0:00:10.00,Karaoke,,0,0,0,,Balladeer Montage")
            else:
                words_per_line = 5
                for i in range(0, len(aligned), words_per_line):
                    chunk = aligned[i : i + words_per_line]
                    line_start = chunk[0].snapped_start
                    line_end = chunk[-1].snapped_end + 0.3
                    start_str = self._sec_to_ass_time(line_start)
                    end_str = self._sec_to_ass_time(line_end)

                    karaoke_tokens = []
                    for w in chunk:
                        dur_cs = max(10, int((w.snapped_end - w.snapped_start) * 100))
                        karaoke_tokens.append(f"{{\\k{dur_cs}}}{w.word}")

                    line_text = " ".join(karaoke_tokens)
                    events.append(f"Dialogue: 0,{start_str},{end_str},Karaoke,,0,0,0,,{line_text}")

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

    def process_image_frame(
        self,
        image_path: Path,
        output_path: Path,
        resolution: Tuple[int, int] = (1920, 1080),
        bg_mode: str = "blurred_fill"
    ) -> Path:
        target_w, target_h = resolution
        output_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            with Image.open(image_path) as src_img:
                src_img = ImageOps.exif_transpose(src_img) or src_img
                src_img = src_img.convert("RGB")
                src_w, src_h = src_img.size

                target_aspect = target_w / target_h
                src_aspect = src_w / src_h
                canvas = Image.new("RGB", (target_w, target_h), (0, 0, 0))

                if bg_mode == "blurred_fill" and abs(target_aspect - src_aspect) > 0.02:
                    scale_bg = max(target_w / src_w, target_h / src_h) * self.settings.video.blur_scale
                    bg_w, bg_h = int(src_w * scale_bg), int(src_h * scale_bg)
                    bg_img = src_img.resize((bg_w, bg_h), Image.Resampling.BILINEAR)

                    left = (bg_w - target_w) // 2
                    top = (bg_h - target_h) // 2
                    bg_crop = bg_img.crop((left, top, left + target_w, top + target_h))
                    blurred_bg = bg_crop.filter(ImageFilter.GaussianBlur(radius=self.settings.video.blur_radius))
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
        fps: int = 30
    ) -> Path:
        duration = slice_model.timeline_end_sec - slice_model.timeline_start_sec
        if duration <= 0.05:
            duration = 1.0

        target_w, target_h = resolution
        asset = slice_model.asset
        asset_path = Path(asset.file_path) if asset else None

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
                    f"[bg]scale={target_w}*{self.settings.video.blur_scale}:{target_h}*{self.settings.video.blur_scale}:force_original_aspect_ratio=increase,crop={target_w}:{target_h},boxblur={self.settings.video.blur_radius}[bgblur];"
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
                # Fallback simple pad
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
                bg_mode=slice_model.bg_mode
            )

            if slice_model.enable_ken_burns:
                total_frames = int(duration * fps)
                cmd = [
                    "ffmpeg", "-y",
                    "-loop", "1", "-i", str(temp_frame_path),
                    "-vf", f"zoompan=z='min(zoom+0.0015,1.25)':d={total_frames}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={target_w}x{target_h}",
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
        aspect_ratio: str = "16:9"
    ) -> Path:
        out_dir = self.settings.output_dir / project_id
        out_dir.mkdir(parents=True, exist_ok=True)
        final_mp4 = out_dir / output_filename

        temp_dir = out_dir / "render_tmp"
        temp_dir.mkdir(parents=True, exist_ok=True)

        resolution = ASPECT_RATIO_RESOLUTIONS.get(aspect_ratio, self.settings.video.resolution)
        fps = self.settings.video.fps

        # 1. Render all slice video clips
        clip_paths: List[Path] = []
        for s in slices:
            clip_file = temp_dir / f"slice_{s.clip_order:03d}.mp4"
            self.render_slice_video(
                slice_model=s,
                output_path=clip_file,
                resolution=resolution,
                fps=fps
            )
            clip_paths.append(clip_file)

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

        # 4. Generate Subtitles
        ass_path = temp_dir / "subtitles.ass"
        self.generate_ass_subtitles(
            audio_track=audio_track,
            output_path=ass_path,
            resolution=resolution
        )

        # 5. Final Hardware-Accelerated NVENC Encoding with EBU R128 Loudness Mastering
        master_audio = Path(audio_track.master_path)
        encoder = self.settings.video.video_codec
        ass_filter_path = str(ass_path.resolve()).replace("\\", "/").replace(":", "\\:")

        # Audio filter: EBU R128 loudness normalization (-14 LUFS) and fade in/out
        audio_filter = "loudnorm=I=-14:LRA=11:TP=-1.5,afade=t=in:ss=0:d=0.5,afade=t=out:st=28:d=1.5"

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
            # Software fallback
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

        return final_mp4

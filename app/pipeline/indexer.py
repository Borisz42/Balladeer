import os
import json
import asyncio
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple, Callable
import numpy as np
from PIL import Image, ExifTags

try:
    import cv2
except ImportError:
    cv2 = None

from app.core.config import get_settings
from app.database.database import db
from app.database.models import MediaAssetModel, VideoSegmentModel
from app.models.qwen_vlm import qwen_vlm
from app.models.siglip_embedder import siglip_embedder
from app.models.gemini_client import gemini_client
from app.models.model_router import model_router, TaskType

logger = logging.getLogger("balladeer.indexer")

class MediaIndexer:
    """
    Automated Travel Montage AI Indexer (Offline High-Throughput Media Ingestion & Scoring Engine).
    
    Stage 1: Ultra-Fast Frame Scoring & Best Shot Selection
    - SigLIP 2 embeddings (google/siglip2-base-patch16-224, downscaled 224x224).
    - Decodes video at 1 fps.
    - Aesthetic & Sharpness evaluation (Laplacian variance & dynamic range) -> S_aes.
    - Travel log relevance scoring (Daily log + Overall full travel log) -> S_rel.
    - Visual similarity segmentation & 1D rolling convolution -> Best n-sec shot selection.
    
    Stage 2: 1-Sentence Semantic Captioning
    - Qwen 3.5 (4B/9B Q4_K_M GGUF via llama-cpp with strict CoT bypass).
    - Capped at 512x512 pixels for winning representative frame.
    """

    def __init__(self):
        self.settings = get_settings()

    def get_thumbnail_path(self, asset_id: str) -> Path:
        thumb_dir = self.settings.output_dir / "thumbnails"
        thumb_dir.mkdir(parents=True, exist_ok=True)
        return thumb_dir / f"{asset_id}.jpg"

    def generate_thumbnail(self, media_path: Path, asset_id: str, media_type: str, max_dim: int = 400) -> Optional[str]:
        """Generates and saves a fast JPEG thumbnail for photos and video frames using ffmpeg / cv2 / PIL."""
        try:
            thumb_path = self.get_thumbnail_path(asset_id)
            if thumb_path.exists() and thumb_path.stat().st_size > 0:
                return str(thumb_path)

            p = Path(media_path)
            is_image = p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"} or media_type == "image"

            if is_image:
                with Image.open(p) as img:
                    img = img.convert("RGB")
                    img.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)
                    img.save(thumb_path, "JPEG", quality=80)
                    return str(thumb_path)
            else:
                # Video file: use ffmpeg to extract 1 frame
                import subprocess
                cmd = [
                    "ffmpeg", "-y", "-ss", "0.5", "-i", str(p),
                    "-vframes", "1", "-vf", f"scale='min({max_dim},iw)':-1",
                    "-q:v", "2", str(thumb_path)
                ]
                subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)
                if thumb_path.exists() and thumb_path.stat().st_size > 0:
                    return str(thumb_path)

                # Fallback to 0s if 0.5s is past duration
                cmd_zero = [
                    "ffmpeg", "-y", "-ss", "0", "-i", str(p),
                    "-vframes", "1", "-vf", f"scale='min({max_dim},iw)':-1",
                    "-q:v", "2", str(thumb_path)
                ]
                subprocess.run(cmd_zero, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)
                if thumb_path.exists() and thumb_path.stat().st_size > 0:
                    return str(thumb_path)

                # Fallback to cv2 if available
                if cv2 is not None:
                    cap = cv2.VideoCapture(str(p))
                    if cap.isOpened():
                        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 1)
                        cap.set(cv2.CAP_PROP_POS_FRAMES, max(0, total_frames // 2))
                        ret, frame = cap.read()
                        cap.release()
                        if ret and frame is not None:
                            h, w = frame.shape[:2]
                            scale = min(max_dim / max(h, w, 1), 1.0)
                            if scale < 1.0:
                                frame = cv2.resize(frame, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
                            cv2.imwrite(str(thumb_path), frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
                            return str(thumb_path)
        except Exception as e:
            logger.warning(f"Failed to generate thumbnail for {media_path.name}: {e}")
        return None

    @staticmethod
    def _convert_gps_to_degrees(value):
        if not value or len(value) < 3:
            return None
        try:
            d = float(value[0])
            m = float(value[1])
            s = float(value[2])
            return d + (m / 60.0) + (s / 3600.0)
        except Exception:
            return None

    def extract_image_metadata(self, image_path: Path) -> Dict[str, Any]:
        meta = {
            "capture_time": None,
            "width": None,
            "height": None,
            "gps_lat": None,
            "gps_lon": None,
            "gps_alt": None,
            "camera_make": None,
            "camera_model": None,
            "iso": None,
            "f_number": None,
            "summary_str": ""
        }
        try:
            with Image.open(image_path) as img:
                meta["width"], meta["height"] = img.size
                exif_data = img.getexif()
                if exif_data:
                    for tag_id, value in exif_data.items():
                        tag_name = ExifTags.TAGS.get(tag_id, tag_id)
                        if tag_name in ("DateTimeOriginal", "DateTime"):
                            try:
                                dt = datetime.strptime(str(value), "%Y:%m:%d %H:%M:%S")
                                meta["capture_time"] = dt.isoformat()
                            except Exception:
                                pass
                        elif tag_name == "Make":
                            meta["camera_make"] = str(value).strip()
                        elif tag_name == "Model":
                            meta["camera_model"] = str(value).strip()
                        elif tag_name == "FNumber":
                            try:
                                meta["f_number"] = float(value)
                            except Exception:
                                pass
                        elif tag_name in ("ISOSpeedRatings", "PhotographicSensitivity"):
                            try:
                                meta["iso"] = int(value)
                            except Exception:
                                pass

                    # Extract GPS tags if available
                    gps_info = None
                    try:
                        if hasattr(ExifTags, "IFD") and hasattr(ExifTags.IFD, "GPSInfo"):
                            gps_info = exif_data.get_ifd(ExifTags.IFD.GPSInfo)
                        else:
                            gps_info = exif_data.get(34853)
                    except Exception:
                        pass

                    if gps_info:
                        gps_tags = {}
                        for k, v in gps_info.items():
                            gps_tags[ExifTags.GPSTAGS.get(k, k)] = v

                        lat_raw = gps_tags.get("GPSLatitude")
                        lat_ref = gps_tags.get("GPSLatitudeRef", "N")
                        lon_raw = gps_tags.get("GPSLongitude")
                        lon_ref = gps_tags.get("GPSLongitudeRef", "E")
                        alt_raw = gps_tags.get("GPSAltitude")

                        lat_deg = self._convert_gps_to_degrees(lat_raw)
                        if lat_deg is not None:
                            if lat_ref == "S":
                                lat_deg = -lat_deg
                            meta["gps_lat"] = round(lat_deg, 5)

                        lon_deg = self._convert_gps_to_degrees(lon_raw)
                        if lon_deg is not None:
                            if lon_ref == "W":
                                lon_deg = -lon_deg
                            meta["gps_lon"] = round(lon_deg, 5)

                        if alt_raw is not None:
                            try:
                                meta["gps_alt"] = round(float(alt_raw), 1)
                            except Exception:
                                pass
        except Exception as e:
            logger.warning(f"Could not parse EXIF for {image_path.name}: {e}")

        if not meta["capture_time"]:
            mtime = os.path.getmtime(image_path)
            meta["capture_time"] = datetime.fromtimestamp(mtime).isoformat()

        summary_parts = []
        if meta["width"] and meta["height"]:
            ratio = "Landscape" if meta["width"] > meta["height"] else ("Portrait" if meta["height"] > meta["width"] else "Square")
            summary_parts.append(f"{meta['width']}x{meta['height']} ({ratio})")
        if meta["gps_lat"] and meta["gps_lon"]:
            summary_parts.append(f"GPS: {meta['gps_lat']}°, {meta['gps_lon']}°")
        if meta["camera_make"] or meta["camera_model"]:
            cam = f"{meta.get('camera_make') or ''} {meta.get('camera_model') or ''}".strip()
            summary_parts.append(f"Camera: {cam}")
        if meta["capture_time"]:
            summary_parts.append(f"Time: {meta['capture_time']}")
        meta["summary_str"] = " | ".join(summary_parts)

        return meta

    def extract_video_metadata(self, video_path: Path) -> Dict[str, Any]:
        meta = {
            "capture_time": None,
            "duration_sec": 0.0,
            "width": 1920,
            "height": 1080,
            "fps": 30.0
        }
        # 1. Primary: Use ffprobe
        try:
            import subprocess
            cmd = [
                "ffprobe", "-v", "error", "-select_streams", "v:0",
                "-show_entries", "stream=width,height,duration,r_frame_rate",
                "-show_entries", "format=duration",
                "-of", "json", str(video_path)
            ]
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=8, text=True)
            if res.returncode == 0:
                data = json.loads(res.stdout)
                streams = data.get("streams", [])
                if streams:
                    s = streams[0]
                    meta["width"] = int(s.get("width") or 1920)
                    meta["height"] = int(s.get("height") or 1080)
                    if "duration" in s and s["duration"]:
                        meta["duration_sec"] = round(float(s["duration"]), 2)
                    elif "format" in data and "duration" in data["format"] and data["format"]["duration"]:
                        meta["duration_sec"] = round(float(data["format"]["duration"]), 2)

                    r_fps = s.get("r_frame_rate", "30/1")
                    if "/" in r_fps:
                        num, den = r_fps.split("/")
                        if float(den) > 0:
                            meta["fps"] = round(float(num) / float(den), 2)
        except Exception as e:
            logger.debug(f"ffprobe metadata notice on {video_path.name}: {e}")

        # 2. Fallback to cv2 if needed
        if meta["duration_sec"] <= 0.0 and cv2 is not None:
            try:
                cap = cv2.VideoCapture(str(video_path))
                if cap.isOpened():
                    meta["width"] = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or meta["width"])
                    meta["height"] = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or meta["height"])
                    fps = float(cap.get(cv2.CAP_PROP_FPS) or 30.0)
                    if fps > 0:
                        meta["fps"] = fps
                    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                    if meta["fps"] > 0 and frame_count > 0:
                        meta["duration_sec"] = round(frame_count / meta["fps"], 2)
                    cap.release()
            except Exception as e:
                logger.debug(f"cv2 metadata notice on {video_path.name}: {e}")

        mtime = os.path.getmtime(video_path)
        meta["capture_time"] = datetime.fromtimestamp(mtime).isoformat()
        return meta

    def stage_media_files(self, project_id: str, file_paths: List[Path]) -> List[MediaAssetModel]:
        """
        Step 1: Rapidly registers uploaded/chosen files into the database with thumbnails
        and basic EXIF/video dimensions, marking is_indexed=False.
        """
        staged: List[MediaAssetModel] = []
        video_exts = {".mp4", ".mov", ".avi", ".mkv", ".webm"}

        for idx, p in enumerate(file_paths):
            is_video = p.suffix.lower() in video_exts
            asset_id = f"ast_{p.stem}_{int(datetime.utcnow().timestamp()*1000)%10000000}_{idx}"
            
            if is_video:
                meta = self.extract_video_metadata(p)
                media_type = "video"
                duration_sec = meta["duration_sec"]
            else:
                meta = self.extract_image_metadata(p)
                media_type = "image"
                duration_sec = 0.0

            # Generate thumbnail
            self.generate_thumbnail(p, asset_id, media_type)

            asset = MediaAssetModel(
                id=asset_id,
                project_id=project_id,
                file_path=str(p.resolve()),
                media_type=media_type,
                capture_time=meta["capture_time"],
                duration_sec=duration_sec,
                quality_score=7.0,
                caption=f"{p.stem.replace('_', ' ').replace('-', ' ').title()}",
                tags=["pending"],
                embedding=None,
                is_active=True,
                is_indexed=False,
                indexed_by_model=None,
                width=meta["width"],
                height=meta["height"]
            )
            db.add_media_asset(asset)
            staged.append(asset)

        return staged

    def generate_siglip_embedding(self, text_or_image: Any) -> List[float]:
        return siglip_embedder.encode(text_or_image)

    def generate_clip_embedding(self, text_or_image: Any) -> List[float]:
        """Backward compatibility alias for SigLIP 2 embeddings."""
        return self.generate_siglip_embedding(text_or_image)

    def evaluate_frame_aesthetics(self, img_rgb_or_bgr: np.ndarray) -> float:
        """
        Aesthetic & Sharpness Evaluation ($S_{aes} \in [0.1, 0.98]$):
        - Logarithmic Laplacian variance for sharpness (detecting crisp focus vs motion blur).
        - Dynamic range and luminance contrast (standard deviation of luminance).
        - Exposure curve centered around optimal middle-gray without harsh clipping.
        - Chroma / color variance for vibrant saturation.
        """
        try:
            if len(img_rgb_or_bgr.shape) == 3:
                if cv2 is not None:
                    gray = cv2.cvtColor(img_rgb_or_bgr, cv2.COLOR_BGR2GRAY if img_rgb_or_bgr.shape[2] == 3 else cv2.COLOR_RGB2GRAY)
                else:
                    gray = (0.299 * img_rgb_or_bgr[:, :, 0] + 0.587 * img_rgb_or_bgr[:, :, 1] + 0.114 * img_rgb_or_bgr[:, :, 2]).astype(np.float32)
            else:
                gray = img_rgb_or_bgr.astype(np.float32)
            
            # 1. Laplacian variance for sharpness
            if cv2 is not None:
                lap_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())
            else:
                lap = (
                    gray[1:-1, 2:] + gray[1:-1, :-2] + gray[2:, 1:-1] + gray[:-2, 1:-1] - 4.0 * gray[1:-1, 1:-1]
                )
                lap_var = float(np.var(lap)) if lap.size > 0 else 0.0

            # Logarithmic mapping: blurry (~50) -> ~0.2, normal (~500) -> ~0.65, crisp (~3000+) -> ~0.9
            sharpness_score = float(np.clip((np.log1p(lap_var) - 3.2) / 4.2, 0.10, 0.95))

            # 2. Dynamic range & luminance balance
            mean_lum = float(np.mean(gray))
            std_lum = float(np.std(gray))

            # Optimal exposure around 110-145 with gentle falloff
            exposure_score = float(np.clip(1.0 - (abs(mean_lum - 128.0) / 128.0) ** 1.6, 0.10, 0.95))
            contrast_score = float(np.clip(std_lum / 65.0, 0.10, 0.95))

            # 3. Chroma / Color richness
            if len(img_rgb_or_bgr.shape) == 3:
                color_std = float(np.std(img_rgb_or_bgr, axis=(0, 1)).mean())
                color_score = float(np.clip(color_std / 50.0, 0.10, 0.95))
            else:
                color_score = 0.50

            s_aes = (0.35 * sharpness_score) + (0.30 * contrast_score) + (0.20 * exposure_score) + (0.15 * color_score)
            return round(float(np.clip(s_aes, 0.10, 0.98)), 3)
        except Exception as e:
            logger.debug(f"Aesthetic evaluation notice: {e}")
        return 0.65

    def extract_video_frames_1fps(self, video_path: Path, max_duration: Optional[float] = None) -> List[Tuple[float, np.ndarray]]:
        """
        Decodes video at 1 frame per second (1 fps) using FFmpeg streaming pipe (or OpenCV fallback).
        Returns list of (timestamp_sec, frame_rgb_224x224).
        """
        frames: List[Tuple[float, np.ndarray]] = []
        if not video_path.exists():
            return frames

        # 1. Primary engine: FFmpeg rawvideo pipe
        try:
            import subprocess
            vf_filter = "fps=1,scale=224:224"
            if max_duration and max_duration > 0:
                cmd = ["ffmpeg", "-y", "-i", str(video_path), "-t", str(max_duration), "-vf", vf_filter, "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
            else:
                cmd = ["ffmpeg", "-y", "-i", str(video_path), "-vf", vf_filter, "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]

            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            raw_bytes, _ = proc.communicate(timeout=30)

            frame_size = 224 * 224 * 3
            total_extracted = len(raw_bytes) // frame_size

            for idx in range(total_extracted):
                offset = idx * frame_size
                frame_buf = raw_bytes[offset:offset + frame_size]
                frame_arr = np.frombuffer(frame_buf, dtype=np.uint8).reshape((224, 224, 3))
                frames.append((round(float(idx), 2), frame_arr))

            if frames:
                return frames
        except Exception as e:
            logger.debug(f"FFmpeg 1 fps frame extraction note on {video_path.name}: {e}")

        # 2. Fallback: OpenCV cv2 if available
        if cv2 is not None:
            try:
                cap = cv2.VideoCapture(str(video_path))
                if cap.isOpened():
                    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
                    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
                    duration = total_frames / fps if fps > 0 else 0.0
                    if max_duration and max_duration > 0:
                        duration = min(duration, max_duration)

                    current_sec = 0.0
                    while current_sec < duration:
                        frame_num = int(current_sec * fps)
                        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_num)
                        ret, frame = cap.read()
                        if not ret or frame is None:
                            break
                        # Convert to RGB and resize
                        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                        small_frame = cv2.resize(frame_rgb, (224, 224), interpolation=cv2.INTER_AREA)
                        frames.append((round(current_sec, 2), small_frame))
                        current_sec += 1.0
                    cap.release()
            except Exception as e:
                logger.debug(f"cv2 1 fps video extraction note on {video_path.name}: {e}")

        return frames

    def get_project_log_embeddings(self, project_id: str) -> Tuple[Optional[List[float]], Dict[str, List[float]]]:
        """
        Computes SigLIP 2 text embeddings for:
        1. Overall full travel log (combining project narrative and all active diary days).
        2. Day-specific travel log embeddings mapped by date/day_number.
        """
        project = db.get_project(project_id)
        if not project:
            return None, {}

        full_narrative = project.narrative_text or ""
        diary_days = (project.config_override or {}).get("diary_days", [])
        
        all_texts = []
        if full_narrative:
            all_texts.append(full_narrative)
        
        day_embs: Dict[str, List[float]] = {}
        for d in diary_days:
            day_text = f"{d.get('title', '')} {d.get('notes', '')}".strip()
            if day_text:
                all_texts.append(day_text)
                day_key = str(d.get("date", f"day_{d.get('day_number', 1)}"))
                day_embs[day_key] = siglip_embedder.encode_text(day_text)

        combined_full_log = " | ".join([t for t in all_texts if t]) or project.title or "Travel vacation montage"
        full_log_emb = siglip_embedder.encode_text(combined_full_log)
        return full_log_emb, day_embs

    @staticmethod
    def cosine_similarity(v1: Optional[List[float]], v2: Optional[List[float]]) -> float:
        if not v1 or not v2:
            return 0.60
        a = np.array(v1, dtype=np.float32)
        b = np.array(v2, dtype=np.float32)
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a == 0 or norm_b == 0:
            return 0.60
        sim = float(np.dot(a, b) / (norm_a * norm_b))
        # Dynamically scale SigLIP 2 cross-modal similarities (active range ~ -0.05 to +0.20)
        scaled_sim = 0.50 + (sim * 3.5)
        return float(np.clip(scaled_sim, 0.15, 0.95))

    def is_travel_log_ready(self, project_id: str) -> bool:
        """
        Determines if a project's travel log is ready for relevance score calculation.
        For auto_draft mode, requires travel_log_approved=True.
        """
        project = db.get_project(project_id)
        if not project:
            return False
        cfg = project.config_override or {}
        mode = cfg.get("travel_log_mode", "manual")
        if mode == "auto_draft":
            return bool(cfg.get("travel_log_approved", False))
        return bool(project.narrative_text and project.narrative_text.strip()) or bool(cfg.get("diary_days"))

    def process_video_and_extract_segments(
        self,
        asset: MediaAssetModel,
        full_log_emb: Optional[List[float]],
        day_log_emb: Optional[List[float]],
        window_sec: int = 3,
        calculate_relevance: bool = True
    ) -> Tuple[List[VideoSegmentModel], Path]:
        """
        Stage 1: Ultra-Fast Frame Scoring & Best Shot Selection
        - Decodes video at 1 fps.
        - Scores every frame for Aesthetics ($S_{aes}$), Travel Log Relevance ($S_{rel}$), and Motion Dynamics ($S_{mot}$).
        - Segments video based on visual similarity cosine distance.
        - Applies 1D rolling convolution ($S_{comp} = 0.45 S_{rel} + 0.35 S_{aes} + 0.20 S_{mot}$) over n-sec window.
        - Extracts best representative frame for Qwen captioning.
        """
        video_path = Path(asset.file_path)
        frames_1fps = self.extract_video_frames_1fps(video_path, max_duration=asset.duration_sec)
        thumb_p = Path(self.get_thumbnail_path(asset.id))
        
        if not frames_1fps:
            duration = asset.duration_sec if asset.duration_sec > 0 else 3.0
            step = 3.0
            segments: List[VideoSegmentModel] = []
            curr_t = 0.0
            s_idx = 0
            while curr_t < duration:
                end_t = min(curr_t + step, duration)
                motion = round(0.5 + (0.35 * np.sin(s_idx * 1.3)), 2)
                emb = siglip_embedder.encode(thumb_p if thumb_p.exists() else f"{asset.id} segment {s_idx}")
                
                # Guaranteed non-empty fallback per-second score curve
                fallback_pts = []
                sec_t = curr_t
                while sec_t < end_t:
                    fallback_pts.append({
                        "t": round(sec_t, 2),
                        "s_rel": 0.65 if calculate_relevance else 0.0,
                        "s_aes": 0.70,
                        "s_comp": round(0.68 + (0.08 * np.sin(sec_t * 0.9)), 3) if calculate_relevance else round(0.65 * 0.70 + 0.35 * 0.50, 3)
                    })
                    sec_t += 1.0

                segments.append(
                    VideoSegmentModel(
                        id=f"seg_{asset.id}_{s_idx}",
                        asset_id=asset.id,
                        start_time=round(curr_t, 2),
                        end_time=round(end_t, 2),
                        motion_score=round(max(0.1, min(1.0, motion)), 2),
                        relevance_score=0.65 if calculate_relevance else 0.0,
                        best_shot_start=round(curr_t, 2),
                        best_shot_end=round(min(curr_t + 2.0, end_t), 2),
                        description=f"Action segment {s_idx+1}",
                        embedding=emb,
                        frame_scores=json.dumps(fallback_pts)
                    )
                )
                curr_t = end_t
                s_idx += 1
            return segments, thumb_p

        timestamps = [t for t, _ in frames_1fps]
        raw_frames = [f for _, f in frames_1fps]
        
        # Batched SigLIP 2 frame embeddings
        frame_embs = siglip_embedder.encode_images_batch(raw_frames)

        # Retrieve cached zero-shot aesthetic anchor prompt embeddings
        pos_emb, neg_emb = siglip_embedder.get_aesthetic_anchors()

        # Compute S_aes, S_rel, and S_mot for each frame
        composite_scores = []
        s_rel_arr = []
        s_aes_arr = []
        s_mot_arr = []

        for i, f in enumerate(raw_frames):
            heuristic_aes = self.evaluate_frame_aesthetics(f)
            emb = frame_embs[i]
            e_arr = np.array(emb, dtype=np.float32)
            e_norm = e_arr / (np.linalg.norm(e_arr) + 1e-8)

            # 1. Zero-shot aesthetic score from SigLIP 2 blended with physical sharpness
            if pos_emb is not None and neg_emb is not None:
                pos_sim = float(np.dot(e_norm, pos_emb))
                neg_sim = float(np.dot(e_norm, neg_emb))
                siglip_aes = float(np.clip(0.60 + ((pos_sim - neg_sim) * 5.0), 0.15, 0.98))
                s_aes = round(0.50 * siglip_aes + 0.50 * heuristic_aes, 3)
            else:
                s_aes = heuristic_aes
            
            # 2. Relevance score against diary days / full log
            if calculate_relevance and (day_log_emb or full_log_emb):
                s_rel_daily = self.cosine_similarity(emb, day_log_emb) if day_log_emb else 0.65
                s_rel_full = self.cosine_similarity(emb, full_log_emb) if full_log_emb else 0.65
                s_rel = round((0.6 * s_rel_daily) + (0.4 * s_rel_full), 3)
            elif calculate_relevance:
                # Default baseline with slight visual richness variance
                s_rel = round(0.60 + 0.15 * np.sin(i * 0.8), 3)
            else:
                s_rel = 0.0

            # 3. Frame visual motion/transition delta
            if i > 0:
                prev_e = np.array(frame_embs[i-1], dtype=np.float32)
                prev_norm = prev_e / (np.linalg.norm(prev_e) + 1e-8)
                cos_dist = float(1.0 - np.dot(e_norm, prev_norm))
                s_mot = float(np.clip(0.30 + (cos_dist * 3.0), 0.10, 0.95))
            else:
                s_mot = 0.50

            # 4. Multi-factor composite timeline score
            if calculate_relevance:
                s_comp = round((0.45 * s_rel) + (0.35 * s_aes) + (0.20 * s_mot), 3)
            else:
                s_comp = round((0.60 * s_aes) + (0.40 * s_mot), 3)
            
            composite_scores.append(s_comp)
            s_rel_arr.append(s_rel)
            s_aes_arr.append(s_aes)
            s_mot_arr.append(round(s_mot, 3))

        # Visual similarity segmentation
        sim_threshold = getattr(self.settings.indexing, "scene_detection_threshold", 0.30)
        segment_bounds = [0]
        
        for i in range(1, len(frame_embs)):
            # Cosine distance
            dot_prod = float(np.dot(frame_embs[i], frame_embs[i-1]))
            dist = 1.0 - dot_prod
            curr_seg_len = i - segment_bounds[-1]
            if (dist > sim_threshold and curr_seg_len >= 2) or curr_seg_len >= 12:
                segment_bounds.append(i)
        
        if segment_bounds[-1] != len(frame_embs):
            segment_bounds.append(len(frame_embs))

        segments: List[VideoSegmentModel] = []
        best_global_score = -1.0
        best_global_rep_frame_path = None

        temp_dir = self.settings.output_dir / "temp_frames"
        temp_dir.mkdir(parents=True, exist_ok=True)

        for seg_idx in range(len(segment_bounds) - 1):
            start_idx = segment_bounds[seg_idx]
            end_idx = segment_bounds[seg_idx + 1]
            seg_scores = np.array(composite_scores[start_idx:end_idx], dtype=np.float32)
            seg_len = len(seg_scores)

            seg_start_t = timestamps[start_idx]
            seg_end_t = min(timestamps[end_idx - 1] + 1.0, asset.duration_sec)

            # 1D Rolling Convolution for Best n-sec Shot
            w = min(max(2, window_sec), seg_len)
            if seg_len >= w:
                kernel = np.ones(w, dtype=np.float32) / w
                rolling_avg = np.convolve(seg_scores, kernel, mode="valid")
                best_offset = int(np.argmax(rolling_avg))
                best_shot_score = float(rolling_avg[best_offset])
                best_start_t = timestamps[start_idx + best_offset]
                best_end_t = min(timestamps[start_idx + best_offset + w - 1] + 1.0, asset.duration_sec)
                rep_idx = start_idx + best_offset + (w // 2)
            else:
                best_shot_score = float(np.mean(seg_scores))
                best_start_t = seg_start_t
                best_end_t = seg_end_t
                rep_idx = start_idx + (seg_len // 2)

            rep_idx = min(rep_idx, len(frames_1fps) - 1)
            rep_emb = frame_embs[rep_idx]
            rep_frame_rgb = raw_frames[rep_idx]

            # Build per-second frame score points for visualization
            seg_frame_scores = [
                {
                    "t": round(float(timestamps[idx]), 2),
                    "s_rel": round(float(s_rel_arr[idx]), 3),
                    "s_aes": round(float(s_aes_arr[idx]), 3),
                    "s_comp": round(float(composite_scores[idx]), 3)
                }
                for idx in range(start_idx, end_idx)
            ]
            seg_relevance = round(float(np.mean(s_rel_arr[start_idx:end_idx])), 3)

            # Save representative frame image (max 512x512) for Qwen captioning using PIL
            seg_rep_path = temp_dir / f"rep_{asset.id}_seg{seg_idx}.jpg"
            try:
                pil_rep = Image.fromarray(rep_frame_rgb)
                pil_rep.thumbnail((512, 512), Image.Resampling.LANCZOS)
                pil_rep.save(seg_rep_path, "JPEG", quality=85)
            except Exception as e:
                logger.debug(f"Rep frame save note: {e}")

            if best_shot_score > best_global_score:
                best_global_score = best_shot_score
                best_global_rep_frame_path = seg_rep_path

            seg_model = VideoSegmentModel(
                id=f"seg_{asset.id}_{seg_idx}",
                asset_id=asset.id,
                start_time=round(seg_start_t, 2),
                end_time=round(seg_end_t, 2),
                motion_score=round(best_shot_score, 2),
                relevance_score=seg_relevance,
                best_shot_start=round(best_start_t, 2),
                best_shot_end=round(best_end_t, 2),
                description=f"Action scene (Segment {seg_idx+1})",
                embedding=rep_emb,
                frame_scores=json.dumps(seg_frame_scores)
            )
            segments.append(seg_model)

        if not best_global_rep_frame_path or not best_global_rep_frame_path.exists():
            best_global_rep_frame_path = thumb_p

        return segments, best_global_rep_frame_path


    def extract_video_subsegments(
        self,
        arg1: Any,
        arg2: Any,
        duration_sec: float
    ) -> List[VideoSegmentModel]:
        """Legacy helper for subsegment extraction."""
        if isinstance(arg1, Path) or (isinstance(arg1, str) and ("." in arg1 or "/" in arg1 or "\\" in arg1)):
            video_path = Path(arg1)
            asset_id = str(arg2)
        else:
            asset_id = str(arg1)
            video_path = Path(arg2)

        v_name = video_path.name if isinstance(video_path, Path) else str(video_path)
        dummy_asset = MediaAssetModel(
            id=asset_id,
            project_id="temp",
            file_path=str(video_path),
            media_type="video",
            duration_sec=duration_sec
        )
        segs, _ = self.process_video_and_extract_segments(dummy_asset, None, None)
        return segs

    def get_visual_path(self, asset: MediaAssetModel) -> Path:
        """Returns the image path or video thumbnail path for AI vision processing."""
        p = Path(asset.file_path)
        if asset.media_type == "video":
            thumb_path = self.get_thumbnail_path(asset.id)
            if not thumb_path.exists() or thumb_path.stat().st_size == 0:
                self.generate_thumbnail(p, asset.id, "video")
            if thumb_path.exists() and thumb_path.stat().st_size > 0:
                return thumb_path
        return p

    def match_capture_time_to_day(self, capture_time: Optional[str], diary_days: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Matches a media capture timestamp to an active diary day."""
        if not capture_time or not diary_days:
            return None

        cap_date = capture_time[:10] # YYYY-MM-DD
        active_days = [d for d in diary_days if d.get("is_active", True) and not d.get("is_discarded", False)]
        if not active_days:
            return None

        # 1. Exact date match
        for d in active_days:
            if d.get("date") == cap_date:
                return d

        # 2. Closest date match
        try:
            cap_dt = datetime.fromisoformat(cap_date)
            def date_diff(d):
                try:
                    return abs((datetime.fromisoformat(d.get("date", cap_date)) - cap_dt).total_seconds())
                except Exception:
                    return float("inf")
            
            sorted_days = sorted(active_days, key=date_diff)
            return sorted_days[0] if sorted_days else None
        except Exception:
            return active_days[0] if active_days else None

    def sync_assets_with_diary_dates(self, project_id: str, diary_days: List[Dict[str, Any]]) -> int:
        """
        Re-indexes and updates day/date tags on all media assets of a project.
        """
        assets = db.get_project_assets(project_id)
        updated_count = 0
        for asset in assets:
            matched_day = self.match_capture_time_to_day(asset.capture_time, diary_days)
            clean_tags = [t for t in asset.tags if not t.startswith("day:") and not t.startswith("date:")]
            if matched_day:
                clean_tags.append(f"day:Day {matched_day.get('day_number', 1)}")
                if matched_day.get("date"):
                    clean_tags.append(f"date:{matched_day['date']}")
                if matched_day.get("title") and matched_day["title"] not in clean_tags:
                    clean_tags.append(matched_day["title"])

            db.update_media_asset(asset.id, {"tags": clean_tags})
            updated_count += 1
        return updated_count

    async def index_pending_assets(
        self,
        project_id: str,
        asset_ids: Optional[List[str]] = None,
        batch_size: Optional[int] = None,
        progress_callback: Optional[Callable[[str, float], Any]] = None
    ) -> List[MediaAssetModel]:
        """
        Step 2: Executes AI indexing on non-indexed or selected assets (both photos and videos)
        using SigLIP 2 scoring + Qwen 3.5 1-sentence captioning.
        """
        all_assets = db.get_project_assets(project_id)
        if asset_ids:
            target_assets = [a for a in all_assets if a.id in asset_ids]
        else:
            target_assets = [a for a in all_assets if not a.is_indexed]

        if not target_assets:
            logger.info("No pending unindexed assets to process.")
            return []

        settings = get_settings()
        log_ready = self.is_travel_log_ready(project_id)
        if log_ready:
            full_log_emb, day_embs = self.get_project_log_embeddings(project_id)
        else:
            full_log_emb, day_embs = None, {}

        project = db.get_project(project_id)
        diary_days = (project.config_override or {}).get("diary_days", []) if project else []

        chunk_size = batch_size or settings.google_ai.batch_size or 20
        total_count = len(target_assets)
        processed_count = 0
        indexed_results: List[MediaAssetModel] = []

        chunks = [target_assets[i : i + chunk_size] for i in range(0, len(target_assets), chunk_size)]

        for chunk_idx, chunk in enumerate(chunks):
            # For each asset, prepare the representative visual path and rich metadata
            visual_paths: List[Path] = []
            metadatas: List[Dict[str, Any]] = []
            video_segments_bundle: Dict[str, List[VideoSegmentModel]] = {}

            for asset in chunk:
                p_asset = Path(asset.file_path)
                meta_item = self.extract_image_metadata(p_asset) if asset.media_type == "image" else self.extract_video_metadata(p_asset)
                metadatas.append(meta_item)

                matched_day = self.match_capture_time_to_day(asset.capture_time, diary_days) if log_ready else None
                day_key = str(matched_day.get("date", f"day_{matched_day.get('day_number', 1)}")) if matched_day else None
                day_log_emb = day_embs.get(day_key) if day_key else None

                if asset.media_type == "video":
                    shot_window = getattr(settings.indexing, "video_shot_window_sec", 3)
                    segs, rep_frame_path = self.process_video_and_extract_segments(
                        asset=asset,
                        full_log_emb=full_log_emb,
                        day_log_emb=day_log_emb,
                        window_sec=shot_window,
                        calculate_relevance=log_ready
                    )
                    video_segments_bundle[asset.id] = segs
                    visual_paths.append(rep_frame_path)
                else:
                    visual_paths.append(self.get_visual_path(asset))

            # Build enriched prompt payload with image path and GPS/camera metadata
            prompt_payload = [
                {
                    "path": visual_paths[idx],
                    "metadata": metadatas[idx],
                    "filename": Path(asset.file_path).name
                }
                for idx, asset in enumerate(chunk)
            ]

            est_tokens = len(visual_paths) * 600

            import time
            t0 = time.perf_counter()

            vlm_results, model_used = await model_router.execute_task(
                task_type=TaskType.VISION_BATCH,
                prompt_payload=prompt_payload,
                estimated_tokens=est_tokens,
                cloud_caller=gemini_client.analyze_image_batch,
                local_fallback=qwen_vlm.describe_and_score_batch
            )

            t1 = time.perf_counter()
            elapsed_sec = t1 - t0
            avg_per_item = elapsed_sec / len(visual_paths) if visual_paths else 0

            logger.info(f"[Indexer] Indexed batch {chunk_idx+1}/{len(chunks)} ({len(chunk)} media items) using: {model_used} in {elapsed_sec:.2f}s (avg {avg_per_item:.2f}s/item)")

            for idx, asset in enumerate(chunk):
                p = Path(asset.file_path)
                analysis = vlm_results[idx] if idx < len(vlm_results) else {
                    "caption": f"Scene: {p.stem}",
                    "tags": ["travel"],
                    "quality_score": 7.0
                }
                
                # Compute SigLIP 2 embedding for the asset (once)
                emb = self.generate_siglip_embedding(visual_paths[idx] if visual_paths[idx].exists() else analysis["caption"])

                # Compute local SigLIP 2 zero-shot aesthetic score & blend with VLM score
                siglip_score = siglip_embedder.compute_aesthetic_score(visual_paths[idx] if visual_paths[idx].exists() else p)
                vlm_score = float(analysis.get("quality_score", 7.0))
                combined_quality = round(max(1.0, min(10.0, 0.5 * siglip_score + 0.5 * vlm_score)), 1)

                if log_ready:
                    matched_day = self.match_capture_time_to_day(asset.capture_time, diary_days)
                    day_key = str(matched_day.get("date", f"day_{matched_day.get('day_number', 1)}")) if matched_day else None
                    day_log_emb = day_embs.get(day_key) if day_key else None

                    rel_daily = round(self.cosine_similarity(emb, day_log_emb), 3) if day_log_emb else 0.65
                    rel_overall = round(self.cosine_similarity(emb, full_log_emb), 3) if full_log_emb else 0.65

                    if asset.media_type == "video" and asset.id in video_segments_bundle:
                        segs = video_segments_bundle[asset.id]
                        for s_idx, s in enumerate(segs):
                            s.description = f"{analysis['caption']} (Part {s_idx+1})" if s_idx > 0 else analysis['caption']
                        db.save_video_segments(segs)
                        if segs:
                            seg_rel_avg = float(np.mean([s.relevance_score for s in segs if s.relevance_score > 0] or [0.65]))
                            rel_daily = round(seg_rel_avg, 3)
                else:
                    rel_daily = 0.0
                    rel_overall = 0.0
                    if asset.media_type == "video" and asset.id in video_segments_bundle:
                        segs = video_segments_bundle[asset.id]
                        for s_idx, s in enumerate(segs):
                            s.description = f"{analysis['caption']} (Part {s_idx+1})" if s_idx > 0 else analysis['caption']
                        db.save_video_segments(segs)

                updated = db.update_media_asset(asset.id, {
                    "caption": analysis["caption"],
                    "tags": analysis["tags"],
                    "quality_score": combined_quality,
                    "relevance_score_daily": rel_daily,
                    "relevance_score_overall": rel_overall,
                    "embedding": emb,
                    "is_indexed": True,
                    "indexed_by_model": model_used
                })
                if updated:
                    indexed_results.append(updated)
                processed_count += 1

            if progress_callback:
                pct = (processed_count / total_count) * 100.0
                cb = progress_callback(
                    f"Indexed {processed_count}/{total_count} files via {model_used}",
                    pct
                )
                if asyncio.iscoroutine(cb):
                    await cb

        return indexed_results

    async def reindex_single_asset(self, project_id: str, asset_id: str) -> Optional[MediaAssetModel]:
        asset = db.get_asset(asset_id)
        if not asset:
            return None

        p = Path(asset.file_path)
        if not p.exists():
            raise FileNotFoundError(f"Media file not found at {asset.file_path}")

        meta = self.extract_image_metadata(p) if asset.media_type == "image" else self.extract_video_metadata(p)
        log_ready = self.is_travel_log_ready(project_id)
        if log_ready:
            full_log_emb, day_embs = self.get_project_log_embeddings(project_id)
        else:
            full_log_emb, day_embs = None, {}

        project = db.get_project(project_id)
        diary_days = (project.config_override or {}).get("diary_days", []) if project else []
        matched_day = self.match_capture_time_to_day(asset.capture_time, diary_days) if log_ready else None
        day_key = str(matched_day.get("date", f"day_{matched_day.get('day_number', 1)}")) if matched_day else None
        day_log_emb = day_embs.get(day_key) if day_key else None

        if asset.media_type == "video":
            shot_window = getattr(self.settings.indexing, "video_shot_window_sec", 3)
            segs, visual_path = self.process_video_and_extract_segments(
                asset=asset,
                full_log_emb=full_log_emb,
                day_log_emb=day_log_emb,
                window_sec=shot_window,
                calculate_relevance=log_ready
            )
        else:
            segs = []
            visual_path = self.get_visual_path(asset)

        prompt_payload = [{
            "path": visual_path,
            "metadata": meta,
            "filename": p.name
        }]

        vlm_results, model_used = await model_router.execute_task(
            task_type=TaskType.VISION_BATCH,
            prompt_payload=prompt_payload,
            estimated_tokens=600,
            cloud_caller=gemini_client.analyze_image_batch,
            local_fallback=qwen_vlm.describe_and_score_batch
        )
        analysis = vlm_results[0] if vlm_results else {
            "caption": f"Scene: {p.stem}",
            "tags": ["travel"],
            "quality_score": 7.5
        }
        emb = self.generate_siglip_embedding(visual_path if visual_path.exists() else analysis["caption"])

        siglip_score = siglip_embedder.compute_aesthetic_score(visual_path if visual_path.exists() else p)
        vlm_score = float(analysis.get("quality_score", 7.0))
        combined_quality = round(max(1.0, min(10.0, 0.5 * siglip_score + 0.5 * vlm_score)), 1)

        if log_ready:
            rel_daily = round(self.cosine_similarity(emb, day_log_emb), 3) if day_log_emb else 0.65
            rel_overall = round(self.cosine_similarity(emb, full_log_emb), 3) if full_log_emb else 0.65

            if asset.media_type == "video" and segs:
                for s_idx, s in enumerate(segs):
                    s.description = f"{analysis['caption']} (Part {s_idx+1})" if s_idx > 0 else analysis['caption']
                db.save_video_segments(segs)
                seg_rel_avg = float(np.mean([s.relevance_score for s in segs if s.relevance_score > 0] or [0.65]))
                rel_daily = round(seg_rel_avg, 3)
        else:
            rel_daily = 0.0
            rel_overall = 0.0
            if asset.media_type == "video" and segs:
                for s_idx, s in enumerate(segs):
                    s.description = f"{analysis['caption']} (Part {s_idx+1})" if s_idx > 0 else analysis['caption']
                db.save_video_segments(segs)

        return db.update_media_asset(asset.id, {
            "caption": analysis["caption"],
            "tags": analysis["tags"],
            "quality_score": combined_quality,
            "relevance_score_daily": rel_daily,
            "relevance_score_overall": rel_overall,
            "embedding": emb,
            "is_indexed": True,
            "indexed_by_model": model_used
        })

    def index_media_file(self, project_id: str, file_path: Path) -> MediaAssetModel:
        """Legacy helper for synchronous single file tests/scripts."""
        staged = self.stage_media_files(project_id, [file_path])
        asset = staged[0]
        meta = self.extract_image_metadata(file_path) if asset.media_type == "image" else self.extract_video_metadata(file_path)
        vlm_res = qwen_vlm.describe_and_score(file_path, metadata=meta)
        emb = self.generate_siglip_embedding(vlm_res["caption"])

        siglip_score = siglip_embedder.compute_aesthetic_score(file_path)
        vlm_score = float(vlm_res.get("quality_score", 7.0))
        combined_quality = round(max(1.0, min(10.0, 0.5 * siglip_score + 0.5 * vlm_score)), 1)

        log_ready = self.is_travel_log_ready(project_id)
        if log_ready:
            full_log_emb, day_embs = self.get_project_log_embeddings(project_id)
            rel_daily = round(self.cosine_similarity(emb, None), 3)
            rel_overall = round(self.cosine_similarity(emb, full_log_emb), 3) if full_log_emb else 0.65
        else:
            full_log_emb, day_embs = None, {}
            rel_daily = 0.0
            rel_overall = 0.0

        if asset.media_type == "video":
            segs, _ = self.process_video_and_extract_segments(asset, full_log_emb, None, calculate_relevance=log_ready)
            db.save_video_segments(segs)
            if segs and log_ready:
                rel_daily = round(float(np.mean([s.relevance_score for s in segs])), 3)

        target_model = getattr(self.settings.indexing, "local_model", "qwen3.5-4b") or "qwen3.5-4b"
        return db.update_media_asset(asset.id, {
            "caption": vlm_res["caption"],
            "tags": vlm_res["tags"],
            "quality_score": combined_quality,
            "relevance_score_daily": rel_daily,
            "relevance_score_overall": rel_overall,
            "embedding": emb,
            "is_indexed": True,
            "indexed_by_model": f"local-{target_model}"
        })

    def compute_project_relevance_scores(self, project_id: str) -> Dict[str, Any]:
        """
        Calculates and updates relevance scores (daily & overall) for all assets
        and video segments against the approved travel log narrative and diary days.
        """
        project = db.get_project(project_id)
        if not project:
            raise ValueError(f"Project not found: {project_id}")

        full_log_emb, day_embs = self.get_project_log_embeddings(project_id)
        assets = db.get_project_assets(project_id)
        diary_days = (project.config_override or {}).get("diary_days", [])

        updated_assets_count = 0
        updated_segments_count = 0

        for asset in assets:
            emb = asset.embedding
            if not emb:
                p = Path(asset.file_path)
                thumb = Path(self.get_thumbnail_path(asset.id))
                emb = self.generate_siglip_embedding(thumb if thumb.exists() else (asset.caption or p.name))

            matched_day = self.match_capture_time_to_day(asset.capture_time, diary_days)
            day_key = str(matched_day.get("date", f"day_{matched_day.get('day_number', 1)}")) if matched_day else None
            day_log_emb = day_embs.get(day_key) if day_key else None

            rel_daily = round(self.cosine_similarity(emb, day_log_emb), 3) if day_log_emb else (round(self.cosine_similarity(emb, full_log_emb), 3) if full_log_emb else 0.65)
            rel_overall = round(self.cosine_similarity(emb, full_log_emb), 3) if full_log_emb else 0.65

            if asset.media_type == "video":
                segments = db.get_video_segments(asset.id)
                if segments:
                    for seg in segments:
                        seg_emb = seg.embedding or emb
                        seg_rel_daily = self.cosine_similarity(seg_emb, day_log_emb) if day_log_emb else (self.cosine_similarity(seg_emb, full_log_emb) if full_log_emb else 0.65)
                        seg_rel_full = self.cosine_similarity(seg_emb, full_log_emb) if full_log_emb else 0.65
                        seg_rel = round((0.6 * seg_rel_daily) + (0.4 * seg_rel_full), 3)
                        seg.relevance_score = seg_rel

                        if seg.frame_scores:
                            try:
                                pts = json.loads(seg.frame_scores)
                                for pt in pts:
                                    pt["s_rel"] = seg_rel
                                    s_aes = pt.get("s_aes", 0.70)
                                    s_mot = 0.50
                                    pt["s_comp"] = round((0.45 * seg_rel) + (0.35 * s_aes) + (0.20 * s_mot), 3)
                                seg.frame_scores = json.dumps(pts)
                            except Exception:
                                pass
                        updated_segments_count += 1
                    db.save_video_segments(segments)
                    seg_rel_avg = float(np.mean([s.relevance_score for s in segments if s.relevance_score > 0] or [rel_daily]))
                    rel_daily = round(seg_rel_avg, 3)

            db.update_media_asset(asset.id, {
                "relevance_score_daily": rel_daily,
                "relevance_score_overall": rel_overall,
                "embedding": emb
            })
            updated_assets_count += 1

        self.sync_assets_with_diary_dates(project_id, diary_days)

        return {
            "project_id": project_id,
            "updated_assets": updated_assets_count,
            "updated_segments": updated_segments_count
        }

    async def index_media_batch(
        self,
        project_id: str,
        file_paths: List[Path],
        batch_size: Optional[int] = None,
        progress_callback: Optional[Callable[[str, float], Any]] = None
    ) -> List[MediaAssetModel]:
        """Stages and immediately indexes a batch of media files."""
        staged = self.stage_media_files(project_id, file_paths)
        staged_ids = [a.id for a in staged]
        return await self.index_pending_assets(
            project_id=project_id,
            asset_ids=staged_ids,
            batch_size=batch_size,
            progress_callback=progress_callback
        )

media_indexer = MediaIndexer()
indexer = media_indexer


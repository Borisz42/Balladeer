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
from app.models.clip_embedder import clip_embedder
from app.models.gemini_client import gemini_client
from app.models.model_router import model_router, TaskType

logger = logging.getLogger("balladeer.indexer")

class MediaIndexer:
    """
    Phase 1: 2-Step Parallel Media Ingestion & Multi-Modal Indexing Engine.
    
    Step 1: Rapid Media Staging (Fast EXIF, dimensions, video duration, and thumbnail generation).
    Step 2: Batch AI Vision Indexing via Intelligent Multi-Tier Model Waterfall (Gemini -> Gemma -> Local Qwen).
    """

    def __init__(self):
        self.settings = get_settings()

    def get_thumbnail_path(self, asset_id: str) -> Path:
        thumb_dir = self.settings.output_dir / "thumbnails"
        thumb_dir.mkdir(parents=True, exist_ok=True)
        return thumb_dir / f"{asset_id}.jpg"

    def generate_thumbnail(self, media_path: Path, asset_id: str, media_type: str, max_dim: int = 400) -> Optional[str]:
        """Generates and saves a fast JPEG thumbnail for photos and video frames using ffmpeg / PIL."""
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

    def extract_image_metadata(self, image_path: Path) -> Dict[str, Any]:
        meta = {
            "capture_time": None,
            "width": None,
            "height": None,
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
                                break
                            except Exception:
                                pass
        except Exception as e:
            logger.warning(f"Could not parse EXIF for {image_path.name}: {e}")

        if not meta["capture_time"]:
            mtime = os.path.getmtime(image_path)
            meta["capture_time"] = datetime.fromtimestamp(mtime).isoformat()

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

    def generate_clip_embedding(self, text_or_image: Any) -> List[float]:
        return clip_embedder.encode(text_or_image)

    def extract_video_subsegments(
        self,
        arg1: Any,
        arg2: Any,
        duration_sec: float
    ) -> List[VideoSegmentModel]:
        if isinstance(arg1, Path) or (isinstance(arg1, str) and ("." in arg1 or "/" in arg1 or "\\" in arg1)):
            video_path = Path(arg1)
            asset_id = str(arg2)
        else:
            asset_id = str(arg1)
            video_path = Path(arg2)

        v_name = video_path.name if isinstance(video_path, Path) else str(video_path)

        segments: List[VideoSegmentModel] = []
        if duration_sec <= 3.0:
            emb = self.generate_clip_embedding(v_name)
            return [
                VideoSegmentModel(
                    id=f"seg_{asset_id}_0",
                    asset_id=asset_id,
                    start_time=0.0,
                    end_time=duration_sec,
                    motion_score=0.7,
                    description="Action scene",
                    embedding=emb
                )
            ]

        step = 3.0
        current_t = 0.0
        idx = 0
        while current_t < duration_sec:
            end_t = min(current_t + step, duration_sec)
            motion = 0.5 + (0.35 * np.sin(idx * 1.3))
            emb = self.generate_clip_embedding(f"{v_name} subclip {idx}")

            segments.append(
                VideoSegmentModel(
                    id=f"seg_{asset_id}_{idx}",
                    asset_id=asset_id,
                    start_time=round(current_t, 2),
                    end_time=round(end_t, 2),
                    motion_score=round(max(0.1, min(1.0, motion)), 2),
                    description=f"Action segment {idx+1}",
                    embedding=emb
                )
            )
            current_t = end_t
            idx += 1

        return segments

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

    async def index_pending_assets(
        self,
        project_id: str,
        asset_ids: Optional[List[str]] = None,
        batch_size: Optional[int] = None,
        progress_callback: Optional[Callable[[str, float], Any]] = None
    ) -> List[MediaAssetModel]:
        """
        Step 2: Executes AI indexing on non-indexed or selected assets (both photos and videos)
        using the Model Priority Waterfall.
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
        chunk_size = batch_size or settings.google_ai.batch_size or 20
        total_count = len(target_assets)
        processed_count = 0
        indexed_results: List[MediaAssetModel] = []

        chunks = [target_assets[i : i + chunk_size] for i in range(0, len(target_assets), chunk_size)]

        for chunk_idx, chunk in enumerate(chunks):
            visual_paths = [self.get_visual_path(a) for a in chunk]
            est_tokens = len(visual_paths) * 800

            vlm_results, model_used = await model_router.execute_task(
                task_type=TaskType.VISION_BATCH,
                prompt_payload=visual_paths,
                estimated_tokens=est_tokens,
                cloud_caller=gemini_client.analyze_image_batch,
                local_fallback=qwen_vlm.describe_and_score_batch
            )

            logger.info(f"[Indexer] Indexed batch {chunk_idx+1}/{len(chunks)} ({len(chunk)} media items) using: {model_used}")

            for idx, asset in enumerate(chunk):
                p = Path(asset.file_path)
                analysis = vlm_results[idx] if idx < len(vlm_results) else {
                    "caption": f"Scene: {p.stem}",
                    "tags": ["travel"],
                    "quality_score": 7.0
                }
                emb = self.generate_clip_embedding(analysis["caption"])

                if asset.media_type == "video":
                    segs = self.extract_video_subsegments(asset.id, p, asset.duration_sec)
                    with db.get_connection() as conn:
                        for s in segs:
                            conn.execute(
                                """
                                INSERT OR REPLACE INTO video_segments (id, asset_id, start_time, end_time, motion_score, description, embedding)
                                VALUES (?, ?, ?, ?, ?, ?, ?)
                                """,
                                (s.id, s.asset_id, s.start_time, s.end_time, s.motion_score, s.description,
                                 np.array(s.embedding, dtype=np.float32).tobytes() if s.embedding else None)
                            )

                updated = db.update_media_asset(asset.id, {
                    "caption": analysis["caption"],
                    "tags": analysis["tags"],
                    "quality_score": analysis["quality_score"],
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

        visual_path = self.get_visual_path(asset)
        vlm_results, model_used = await model_router.execute_task(
            task_type=TaskType.VISION_BATCH,
            prompt_payload=[visual_path],
            estimated_tokens=800,
            cloud_caller=gemini_client.analyze_image_batch,
            local_fallback=qwen_vlm.describe_and_score_batch
        )
        analysis = vlm_results[0] if vlm_results else {
            "caption": f"Scene: {p.stem}",
            "tags": ["travel"],
            "quality_score": 7.5
        }
        emb = self.generate_clip_embedding(analysis["caption"])

        if asset.media_type == "video":
            segs = self.extract_video_subsegments(asset.id, p, asset.duration_sec)
            with db.get_connection() as conn:
                for s in segs:
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO video_segments (id, asset_id, start_time, end_time, motion_score, description, embedding)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (s.id, s.asset_id, s.start_time, s.end_time, s.motion_score, s.description,
                         np.array(s.embedding, dtype=np.float32).tobytes() if s.embedding else None)
                    )

        return db.update_media_asset(asset.id, {
            "caption": analysis["caption"],
            "tags": analysis["tags"],
            "quality_score": analysis["quality_score"],
            "embedding": emb,
            "is_indexed": True,
            "indexed_by_model": model_used
        })

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
            # Retain non-day/date tags
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


    def index_media_file(self, project_id: str, file_path: Path) -> MediaAssetModel:
        """Legacy synchronous helper for single file tests/scripts."""
        staged = self.stage_media_files(project_id, [file_path])
        asset = staged[0]
        vlm_res = qwen_vlm.describe_and_score(file_path)
        emb = self.generate_clip_embedding(vlm_res["caption"])

        if asset.media_type == "video":
            segs = self.extract_video_subsegments(asset.id, file_path, asset.duration_sec)
            with db.get_connection() as conn:
                for s in segs:
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO video_segments (id, asset_id, start_time, end_time, motion_score, description, embedding)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (s.id, s.asset_id, s.start_time, s.end_time, s.motion_score, s.description,
                         np.array(s.embedding, dtype=np.float32).tobytes() if s.embedding else None)
                    )

        target_model = getattr(self.settings.indexing, "local_model", "qwen3.5-4b") or "qwen3.5-4b"
        return db.update_media_asset(asset.id, {
            "caption": vlm_res["caption"],
            "tags": vlm_res["tags"],
            "quality_score": vlm_res["quality_score"],
            "embedding": emb,
            "is_indexed": True,
            "indexed_by_model": f"local-{target_model}"
        })

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


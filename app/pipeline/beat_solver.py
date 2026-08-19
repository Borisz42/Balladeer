import logging
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
import numpy as np

from app.core.config import get_settings, BalladeerSettings
from app.database.database import db
from app.database.models import (
    MediaAssetModel,
    AudioTrackModel,
    TimelineSliceModel,
    AlignedWordModel,
    VideoSegmentModel
)

logger = logging.getLogger(__name__)

class BeatSolver:
    """
    Phase 4: Constraint-Based Media Placement Solver.
    Allocates photos & videos to musical beats based on chronological acts,
    semantic similarity, quality scores, recency penalties, and config-driven beat ranges.
    """

    def __init__(self, settings: Optional[BalladeerSettings] = None):
        self.settings = settings or get_settings()

    def solve_timeline(
        self,
        project_id: str,
        audio_track: AudioTrackModel,
        assets: List[MediaAssetModel],
        custom_config: Optional[Dict[str, Any]] = None
    ) -> List[TimelineSliceModel]:
        if not assets:
            logger.warning("No media assets provided to solver.")
            return []

        video_cfg = self.settings.video
        cfg = custom_config or {}
        pacing_cfg = cfg.get("pacing_rules", {})
        video_effects_cfg = cfg.get("video_effects", {})
        video_sub_cfg = cfg.get("video", {})

        # Pacing presets
        preset = pacing_cfg.get("pacing_preset", "balanced")
        if preset == "fast":
            default_photo_range = [1, 2]
            default_vid_range = [2, 4]
        elif preset == "cinematic":
            default_photo_range = [3, 6]
            default_vid_range = [4, 8]
        else:
            default_photo_range = video_cfg.photo_beat_range
            default_vid_range = video_cfg.video_beat_range

        photo_min, photo_max = pacing_cfg.get(
            "photo_beat_range",
            video_sub_cfg.get("photo_beat_range", default_photo_range)
        )
        vid_min, vid_max = pacing_cfg.get(
            "video_beat_range",
            video_sub_cfg.get("video_beat_range", default_vid_range)
        )

        default_bg_mode = video_effects_cfg.get(
            "default_bg_mode",
            video_sub_cfg.get("default_bg_mode", video_cfg.default_bg_mode)
        )
        enable_ken_burns = video_effects_cfg.get(
            "enable_ken_burns",
            video_sub_cfg.get("enable_ken_burns", video_cfg.enable_ken_burns)
        )

        quality_threshold = self.settings.indexing.quality_threshold
        active_assets = [a for a in assets if a.is_active] or assets

        def parse_time(a: MediaAssetModel) -> float:
            if a.capture_time:
                try:
                    return datetime.fromisoformat(a.capture_time.replace("Z", "+00:00")).timestamp()
                except Exception:
                    pass
            return 0.0

        active_assets.sort(key=parse_time)
        high_quality_assets = [a for a in active_assets if a.quality_score >= quality_threshold]
        pool = high_quality_assets if len(high_quality_assets) >= 3 else active_assets

        beat_grid = audio_track.beat_grid
        total_beats = len(beat_grid)
        if total_beats < 2:
            beat_interval = 60.0 / audio_track.bpm
            beat_grid = [round(i * beat_interval, 4) for i in range(int(30.0 / beat_interval))]
            total_beats = len(beat_grid)

        # Retrieve video segments if available
        video_segments_map: Dict[str, List[Dict[str, Any]]] = {}
        try:
            with db.get_connection() as conn:
                rows = conn.execute("SELECT * FROM video_segments").fetchall()
                for r in rows:
                    aid = r["asset_id"]
                    if aid not in video_segments_map:
                        video_segments_map[aid] = []
                    video_segments_map[aid].append(dict(r))
        except Exception:
            pass

        slices: List[TimelineSliceModel] = []
        current_beat = 0
        clip_order = 0
        asset_usage_history: List[str] = []

        while current_beat < total_beats:
            beats_left = total_beats - current_beat

            best_asset, best_score = self._select_best_asset(
                pool=pool,
                current_beat=current_beat,
                total_beats=total_beats,
                asset_usage_history=asset_usage_history,
                is_instrumental=audio_track.is_instrumental
            )

            # Determine beat duration based on media type & instrumental phrasing
            if audio_track.is_instrumental:
                # Phrasing: snap to 4-beat or 8-beat musical bar boundaries if possible
                if best_asset.media_type == "video":
                    target_beats = min(vid_max, max(vid_min, 4))
                else:
                    target_beats = min(photo_max, max(photo_min, 2))
            else:
                if best_asset.media_type == "video":
                    target_beats = min(vid_max, max(vid_min, 3))
                else:
                    target_beats = min(photo_max, max(photo_min, 2))

            allocated_beats = min(target_beats, beats_left)
            if allocated_beats <= 0:
                allocated_beats = 1

            start_beat_idx = current_beat
            end_beat_idx = min(current_beat + allocated_beats, total_beats - 1)

            t_start = beat_grid[start_beat_idx]
            if end_beat_idx < total_beats - 1:
                t_end = beat_grid[end_beat_idx]
            else:
                t_end = t_start + (allocated_beats * (60.0 / audio_track.bpm))

            # Pick matching video segment ID if video
            matched_seg_id = None
            if best_asset.media_type == "video" and best_asset.id in video_segments_map:
                segs = video_segments_map[best_asset.id]
                if segs:
                    # Pick highest motion score
                    segs.sort(key=lambda s: s.get("motion_score", 0.5), reverse=True)
                    matched_seg_id = segs[0]["id"]

            slice_id = f"slice_{project_id}_{clip_order}_{start_beat_idx}"

            slices.append(
                TimelineSliceModel(
                    id=slice_id,
                    project_id=project_id,
                    audio_track_id=audio_track.id,
                    asset_id=best_asset.id,
                    video_segment_id=matched_seg_id,
                    start_beat=start_beat_idx,
                    beat_count=allocated_beats,
                    timeline_start_sec=round(t_start, 4),
                    timeline_end_sec=round(t_end, 4),
                    clip_order=clip_order,
                    bg_mode=default_bg_mode,
                    enable_ken_burns=enable_ken_burns,
                    custom_caption=best_asset.caption or "",
                    asset=best_asset
                )
            )

            asset_usage_history.append(best_asset.id)
            current_beat += allocated_beats
            clip_order += 1

        return slices

    def _select_best_asset(
        self,
        pool: List[MediaAssetModel],
        current_beat: int,
        total_beats: int,
        asset_usage_history: List[str],
        is_instrumental: bool = False
    ) -> Tuple[MediaAssetModel, float]:
        alpha = 0.45
        beta = 0.35
        gamma = 0.30

        song_progress = current_beat / max(total_beats, 1)
        best_score = -float("inf")
        best_asset = pool[0]
        n_assets = len(pool)

        for i, asset in enumerate(pool):
            asset_progress = i / max(n_assets, 1)
            chrono_alignment = 1.0 - abs(song_progress - asset_progress)
            quality_term = (asset.quality_score or 7.0) / 10.0

            recency_penalty = 0.0
            if asset_usage_history:
                try:
                    last_idx = len(asset_usage_history) - 1 - asset_usage_history[::-1].index(asset.id)
                    dist = len(asset_usage_history) - last_idx
                    if dist <= 3:
                        recency_penalty = 1.0 / dist
                except ValueError:
                    pass

            date_affinity = 0.0
            if asset.tags:
                for tag in asset.tags:
                    if tag.startswith("day:Day "):
                        try:
                            d_num = int(tag.replace("day:Day ", ""))
                            # Estimate which day the song progress corresponds to
                            target_day = max(1, int(round(song_progress * 5)) + 1)
                            if d_num == target_day:
                                date_affinity = 0.25
                        except Exception:
                            pass

            score = (alpha * chrono_alignment) + (beta * quality_term) + date_affinity - (gamma * recency_penalty)
            if score > best_score:
                best_score = score
                best_asset = asset

        return best_asset, best_score

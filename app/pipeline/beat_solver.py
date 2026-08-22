import logging
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple, Set
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

        def parse_day_and_time(a: MediaAssetModel) -> Tuple[int, float]:
            day_num = 1
            if a.tags:
                for tag in a.tags:
                    if tag.startswith("day:Day "):
                        try:
                            day_num = int(tag.replace("day:Day ", ""))
                            break
                        except Exception:
                            pass

            t_val = 0.0
            if a.capture_time:
                try:
                    t_val = datetime.fromisoformat(a.capture_time.replace("Z", "+00:00")).timestamp()
                except Exception:
                    pass
            return day_num, t_val

        # Build discrete Shot Candidates (1 per photo, multiple distinct non-overlapping segments per video)
        class ShotCandidate:
            def __init__(
                self,
                shot_id: str,
                asset: MediaAssetModel,
                segment_id: Optional[str] = None,
                segment_data: Optional[Dict[str, Any]] = None,
                day_num: int = 1,
                timestamp: float = 0.0,
                sub_order: int = 0
            ):
                self.shot_id = shot_id
                self.asset = asset
                self.segment_id = segment_id
                self.segment_data = segment_data
                self.day_num = day_num
                self.timestamp = timestamp
                self.sub_order = sub_order

        shot_candidates: List[ShotCandidate] = []
        for a in active_assets:
            d_num, t_val = parse_day_and_time(a)
            if a.media_type == "video":
                segs = video_segments_map.get(a.id, [])
                if segs:
                    # Sort segments by start time
                    segs.sort(key=lambda s: s.get("start_time", 0.0))
                    for s_idx, seg in enumerate(segs):
                        shot_candidates.append(
                            ShotCandidate(
                                shot_id=f"{a.id}_seg_{seg['id']}",
                                asset=a,
                                segment_id=seg["id"],
                                segment_data=seg,
                                day_num=d_num,
                                timestamp=t_val + (seg.get("start_time", 0.0)),
                                sub_order=s_idx
                            )
                        )
                else:
                    # If video has duration > 4s, allow up to 2-3 non-overlapping cuts
                    v_dur = float(a.duration_sec or 3.0)
                    if v_dur >= 7.0:
                        n_cuts = min(3, int(v_dur // 3.5))
                        cut_len = v_dur / n_cuts
                        for c_idx in range(n_cuts):
                            shot_candidates.append(
                                ShotCandidate(
                                    shot_id=f"{a.id}_part_{c_idx}",
                                    asset=a,
                                    segment_id=None,
                                    segment_data={"start_time": c_idx * cut_len, "end_time": (c_idx + 1) * cut_len},
                                    day_num=d_num,
                                    timestamp=t_val + (c_idx * cut_len),
                                    sub_order=c_idx
                                )
                            )
                    else:
                        shot_candidates.append(
                            ShotCandidate(
                                shot_id=f"{a.id}_full",
                                asset=a,
                                segment_id=None,
                                segment_data=None,
                                day_num=d_num,
                                timestamp=t_val,
                                sub_order=0
                            )
                        )
            else:
                shot_candidates.append(
                    ShotCandidate(
                        shot_id=f"{a.id}_photo",
                        asset=a,
                        segment_id=None,
                        segment_data=None,
                        day_num=d_num,
                        timestamp=t_val,
                        sub_order=0
                    )
                )

        # STRICT CHRONOLOGICAL SORTING:
        # 1. Day number (Day 1 -> Day 2 -> Day 3...)
        # 2. Timestamp (EXIF capture_time)
        # 3. Subsegment order
        shot_candidates.sort(key=lambda s: (s.day_num, s.timestamp, s.sub_order))

        if not shot_candidates:
            return []

        beat_grid = audio_track.beat_grid
        total_beats = len(beat_grid)
        if total_beats < 2:
            beat_interval = 60.0 / audio_track.bpm
            beat_grid = [round(i * beat_interval, 4) for i in range(int(30.0 / beat_interval))]
            total_beats = len(beat_grid)

        slices: List[TimelineSliceModel] = []
        current_beat = 0
        clip_order = 0
        used_shot_ids: Set[str] = set()

        # Track sequential index through chronological pool
        chrono_idx = 0

        while current_beat < total_beats:
            beats_left = total_beats - current_beat

            # Find next unused shot in chronological order
            chosen_shot: Optional[ShotCandidate] = None
            for idx in range(len(shot_candidates)):
                cand = shot_candidates[(chrono_idx + idx) % len(shot_candidates)]
                if cand.shot_id not in used_shot_ids:
                    chosen_shot = cand
                    chrono_idx = (chrono_idx + idx + 1) % len(shot_candidates)
                    break

            # If all shots in project have been used once, reset usage tracker to cycle
            if not chosen_shot:
                used_shot_ids.clear()
                chosen_shot = shot_candidates[chrono_idx % len(shot_candidates)]
                chrono_idx = (chrono_idx + 1) % len(shot_candidates)

            used_shot_ids.add(chosen_shot.shot_id)
            best_asset = chosen_shot.asset

            # Determine beat duration based on media type & instrumental phrasing
            if audio_track.is_instrumental:
                if best_asset.media_type == "video":
                    target_beats = min(vid_max, max(vid_min, 4))
                else:
                    target_beats = min(photo_max, max(photo_min, 2))
            else:
                if best_asset.media_type == "video":
                    target_beats = min(vid_max, max(vid_min, 3))
                else:
                    target_beats = min(photo_max, max(photo_min, 2))

            # If remaining beats are less than min allowed and we already have slices, absorb into previous slice
            min_allowed = vid_min if best_asset.media_type == "video" else photo_min
            if slices and beats_left < min_allowed:
                prev = slices[-1]
                prev.beat_count += beats_left
                prev.timeline_end_sec = round(beat_grid[-1] if beat_grid else (prev.timeline_start_sec + prev.beat_count * (60.0 / audio_track.bpm)), 4)
                break

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

            slice_id = f"slice_{project_id}_{clip_order}_{start_beat_idx}"

            slices.append(
                TimelineSliceModel(
                    id=slice_id,
                    project_id=project_id,
                    audio_track_id=audio_track.id,
                    asset_id=best_asset.id,
                    video_segment_id=chosen_shot.segment_id,
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

            current_beat += allocated_beats
            clip_order += 1

        return slices

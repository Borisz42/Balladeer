import os
import shutil
import asyncio
import logging
from pathlib import Path
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Depends
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.core.config import get_settings
from app.database.database import db
from app.database.models import (
    ProjectModel,
    MediaAssetModel,
    VideoSegmentModel,
    AudioTrackModel,
    TimelineSliceModel,
    AlignedWordModel,
    ProjectDetailResponse
)
from app.pipeline.indexer import media_indexer as indexer
from app.pipeline.music_gen import music_gen
from app.pipeline.aligner import aligner
from app.pipeline.beat_solver import BeatSolver
from app.pipeline.compositor import VideoCompositor
from app.api.progress import progress_tracker

router = APIRouter(prefix="/api/projects", tags=["projects"])
logger = logging.getLogger("balladeer.api.projects")

beat_solver = BeatSolver()
compositor = VideoCompositor()

from app.pipeline.rephraser import diary_rephraser
from app.models.model_router import model_router, TaskType
from app.models.gemini_client import gemini_client

class CreateProjectRequest(BaseModel):
    title: str
    narrative_text: Optional[str] = ""
    config_override: Optional[Dict[str, Any]] = None

class UpdateProjectRequest(BaseModel):
    title: Optional[str] = None
    narrative_text: Optional[str] = None
    config_override: Optional[Dict[str, Any]] = None

class ApproveTravelLogRequest(BaseModel):
    title: Optional[str] = None
    narrative_text: Optional[str] = None
    config_override: Optional[Dict[str, Any]] = None

class RephraseRequest(BaseModel):
    text: Optional[str] = None
    day_number: Optional[int] = None
    date: Optional[str] = None
    days: Optional[List[Dict[str, Any]]] = None
    mode: Optional[str] = "single_day" # "single_day" | "full_diary" | "structured_days"

class IndexDirRequest(BaseModel):
    directory_path: str

class GenerateMusicRequest(BaseModel):
    prompt: Optional[str] = None
    bpm: Optional[float] = 120.0
    duration_sec: Optional[float] = 30.0
    is_instrumental: Optional[bool] = False

class AnalyzeMusicTimelineRequest(BaseModel):
    pacing_preset: Optional[str] = "balanced" # "fast" | "balanced" | "cinematic"
    photo_sec: Optional[float] = None
    video_sec_max: Optional[float] = None
    default_inclusion_threshold: Optional[float] = 70.0
    daily_inclusion_thresholds: Optional[Dict[str, float]] = None

class GenerateMusicPromptRequest(BaseModel):
    style_vibe: Optional[str] = None
    suggested_bpm: Optional[int] = 118
    total_duration_sec: Optional[float] = 30.0
    acts: Optional[List[Dict[str, Any]]] = None

class GenerateMusicLyricsRequest(BaseModel):
    flow_prompt: Optional[str] = None
    is_instrumental: Optional[bool] = False
    acts: Optional[List[Dict[str, Any]]] = None

class SynthesizeMusicAudioRequest(BaseModel):
    prompt: Optional[str] = None
    lyrics: Optional[str] = None
    bpm: Optional[float] = 118.0
    duration_sec: Optional[float] = 30.0
    is_instrumental: Optional[bool] = False

class ToggleAssetInclusionRequest(BaseModel):
    include: bool
    threshold_score: Optional[float] = None
    delta: Optional[float] = 0.15

class UpdateAssetRequest(BaseModel):
    caption: Optional[str] = None
    tags: Optional[List[str]] = None
    quality_score: Optional[float] = None
    is_active: Optional[bool] = None

class UpdateLyricsRequest(BaseModel):
    lyrics: Optional[str] = None
    aligned_lyrics: Optional[List[AlignedWordModel]] = None
    auto_snap: Optional[bool] = True
    enable_word_highlight: Optional[bool] = None

class RealignLyricsRequest(BaseModel):
    lyrics: Optional[str] = None

@router.get("", response_model=List[ProjectModel])
@router.get("/", response_model=List[ProjectModel], include_in_schema=False)
def list_all_projects():
    return db.list_projects()

@router.post("", response_model=ProjectModel)
@router.post("/", response_model=ProjectModel, include_in_schema=False)
def create_new_project(req: CreateProjectRequest):
    import uuid
    project_id = f"proj_{uuid.uuid4().hex[:12]}"
    project = ProjectModel(
        id=project_id,
        title=req.title,
        narrative_text=req.narrative_text,
        status="created",
        config_override=req.config_override
    )
    db.create_project(project)
    return project

class BatchDeleteRequest(BaseModel):
    project_ids: List[str]

@router.put("/{project_id}", response_model=ProjectDetailResponse)
@router.patch("/{project_id}", response_model=ProjectDetailResponse)
@router.put("/{project_id}/diary", response_model=ProjectDetailResponse)
@router.put("/{project_id}/rename", response_model=ProjectDetailResponse)
def update_project_diary(project_id: str, req: UpdateProjectRequest):
    proj = db.get_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")

    updated_proj = db.update_project(
        project_id=project_id,
        title=req.title,
        narrative_text=req.narrative_text,
        config_override=req.config_override
    )

    # Sync assets with updated diary days if available
    if req.config_override and "diary_days" in req.config_override:
        indexer.sync_assets_with_diary_dates(project_id, req.config_override["diary_days"])

    return get_project_detail(project_id)

@router.post("/rephrase")
@router.post("/{project_id}/rephrase")
def rephrase_diary_text(req: RephraseRequest, project_id: Optional[str] = None):
    """
    AI re-phraser & spell correction for individual day events or full diary schedules.
    """
    if req.days is not None:
        rephrased_days = diary_rephraser.rephrase_structured_days(req.days)
        active_lines = []
        for d in rephrased_days:
            if d.get("is_active", True) and not d.get("is_discarded", False):
                date_part = f" ({d['date']})" if d.get("date") else ""
                active_lines.append(f"Day {d.get('day_number', 1)}{date_part}: {d.get('events', '')}")
        
        full_text = "\n".join(active_lines)
        return {
            "rephrased_days": rephrased_days,
            "rephrased_text": full_text
        }
    elif req.mode == "full_diary" or "\n" in (req.text or ""):
        full_rephrased = diary_rephraser.rephrase_full_diary(req.text or "")
        return {
            "rephrased_text": full_rephrased
        }
    else:
        single_rephrased = diary_rephraser.rephrase_single_day(
            req.text or "",
            day_number=req.day_number,
            date_str=req.date
        )
        return {
            "rephrased_text": single_rephrased
        }

@router.post("/{project_id}/sync-diary-dates")
def sync_diary_dates(project_id: str):
    proj = db.get_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")

    diary_days = (proj.config_override or {}).get("diary_days", [])
    updated = indexer.sync_assets_with_diary_dates(project_id, diary_days)
    return {"status": "synced", "project_id": project_id, "updated_assets": updated}

@router.post("/{project_id}/draft-travel-log")
async def draft_travel_log(project_id: str):
    """
    Synthesizes a structured day-by-day travel diary/itinerary from indexed media
    items and their metadata (captions, tags, timestamps/dates, locations).
    """
    proj = db.get_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")

    assets = db.get_project_assets(project_id)
    if not assets:
        raise HTTPException(status_code=400, detail="No media assets imported to draft travel log from")

    media_items = [
        {
            "id": a.id,
            "file_path": a.file_path,
            "media_type": a.media_type,
            "capture_time": a.capture_time,
            "caption": a.caption,
            "tags": a.tags,
            "quality_score": a.quality_score
        }
        for a in assets
    ]

    draft = None
    try:
        from app.models.local_vlm import local_vlm
        est_tokens = max(1200, len(media_items) * 35)
        draft, model_used = await model_router.execute_task(
            task_type=TaskType.STORY_LYRICS,
            prompt_payload=proj.title or "Travel Montage",
            estimated_tokens=est_tokens,
            cloud_caller=lambda m, p: gemini_client.draft_travel_log(m, media_items, proj.title),
            local_fallback=lambda p: local_vlm.draft_travel_log(media_items, proj.title)
        )
    except Exception as e:
        logger.warning(f"AI travel log draft fallback: {e}")
        from app.models.local_vlm import local_vlm
        draft = local_vlm.draft_travel_log(media_items, proj.title)

    existing_cfg = proj.config_override or {}
    updated_cfg = {
        **existing_cfg,
        "start_date": draft.get("start_date", existing_cfg.get("start_date", "")),
        "finish_date": draft.get("finish_date", existing_cfg.get("finish_date", "")),
        "diary_days": draft.get("diary_days", [])
    }

    db.update_project(
        project_id=project_id,
        narrative_text=draft.get("narrative_text", ""),
        config_override=updated_cfg
    )

    return {
        "status": "drafted",
        "project_id": project_id,
        "draft": draft
    }

@router.post("/{project_id}/approve-travel-log", response_model=ProjectDetailResponse)
async def approve_travel_log(project_id: str, req: Optional[ApproveTravelLogRequest] = None):
    """
    Approves the travel log/itinerary, marks travel_log_approved=True,
    and calculates all relevance scores (daily & overall) for media assets and video segments.
    """
    proj = db.get_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")

    cfg = proj.config_override or {}
    if req and req.config_override:
        cfg = {**cfg, **req.config_override}
    cfg["travel_log_approved"] = True

    updated_title = req.title if req and req.title is not None else proj.title
    updated_narrative = req.narrative_text if req and req.narrative_text is not None else proj.narrative_text

    db.update_project(
        project_id=project_id,
        title=updated_title,
        narrative_text=updated_narrative,
        config_override=cfg
    )

    # Compute relevance scores for all assets against approved travel log
    res = indexer.compute_project_relevance_scores(project_id)

    await progress_tracker.emit(
        project_id=project_id,
        phase="ready",
        progress=100.0,
        message=f"Travel log approved! Generated relevance scores for {res.get('updated_assets', 0)} assets."
    )

    return get_project_detail(project_id)


@router.get("/{project_id}", response_model=ProjectDetailResponse)
def get_project_detail(project_id: str):
    proj = db.get_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")

    assets = db.get_project_assets(project_id)
    audio = db.get_audio_track(project_id)
    slices = db.get_timeline_slices(project_id)

    video_url = None
    settings = get_settings()
    out_video = settings.output_dir / project_id / "montage.mp4"
    if out_video.exists():
        video_url = f"/api/projects/{project_id}/video"

    return ProjectDetailResponse(
        project=proj,
        assets=assets,
        audio_track=audio,
        timeline_slices=slices,
        rendered_video_url=video_url
    )

def cleanup_project_files(project_id: str):
    try:
        settings = get_settings()
        uploads = settings.uploads_dir / project_id
        output = settings.output_dir / project_id
        if uploads.exists():
            shutil.rmtree(uploads, ignore_errors=True)
        if output.exists():
            shutil.rmtree(output, ignore_errors=True)
        assets = db.get_project_assets(project_id)
        for a in assets:
            try:
                thumb = indexer.get_thumbnail_path(a.id)
                if thumb.exists():
                    thumb.unlink()
            except Exception:
                pass
    except Exception as e:
        logger.warning(f"Error cleaning up disk files for project {project_id}: {e}")

@router.delete("/{project_id}")
def delete_project(project_id: str):
    proj = db.get_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")
    cleanup_project_files(project_id)
    db.delete_project(project_id)
    return {"status": "deleted", "id": project_id}

@router.post("/batch-delete")
def batch_delete_projects(req: BatchDeleteRequest):
    deleted = []
    for pid in req.project_ids:
        proj = db.get_project(pid)
        if proj:
            cleanup_project_files(pid)
            db.delete_project(pid)
            deleted.append(pid)
    return {"status": "deleted", "deleted_ids": deleted}

@router.post("/{project_id}/upload", response_model=List[MediaAssetModel])
async def upload_media(project_id: str, files: List[UploadFile] = File(...)):
    """Step 1: Rapidly upload and stage media files with thumbnails and basic EXIF/duration."""
    proj = db.get_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")

    settings = get_settings()
    project_upload_dir = settings.uploads_dir / project_id
    project_upload_dir.mkdir(parents=True, exist_ok=True)

    saved_paths = []
    for file in files:
        file_path = project_upload_dir / file.filename
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        saved_paths.append(file_path)

    staged_assets = indexer.stage_media_files(
        project_id=project_id,
        file_paths=saved_paths
    )

    await progress_tracker.emit(
        project_id=project_id,
        phase="staged",
        progress=100.0,
        message=f"Staged {len(staged_assets)} files. Click 'Index Media' to run AI vision analysis."
    )

    return staged_assets

@router.post("/{project_id}/index-directory", response_model=List[MediaAssetModel])
async def index_directory(project_id: str, req: IndexDirRequest):
    """Step 1: Rapidly stage files from a local directory."""
    proj = db.get_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")

    dir_path = Path(req.directory_path)
    if not dir_path.exists() or not dir_path.is_dir():
        raise HTTPException(status_code=400, detail="Invalid directory path")

    supported_exts = {".jpg", ".jpeg", ".png", ".webp", ".mp4", ".mov", ".mkv", ".avi"}
    files = [f for f in dir_path.glob("*") if f.suffix.lower() in supported_exts]

    staged_assets = indexer.stage_media_files(
        project_id=project_id,
        file_paths=files
    )

    await progress_tracker.emit(
        project_id=project_id,
        phase="staged",
        progress=100.0,
        message=f"Staged {len(staged_assets)} files from directory. Click 'Index Media' to run AI vision analysis."
    )

    return staged_assets

@router.post("/{project_id}/index-pending", response_model=List[MediaAssetModel])
async def index_pending_media(project_id: str):
    """Step 2: Executes parallel batch AI vision indexing on all unindexed media files."""
    proj = db.get_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")

    async def on_progress(msg: str, pct: float):
        await progress_tracker.emit(
            project_id=project_id,
            phase="indexing",
            progress=pct,
            message=msg
        )

    indexed = await indexer.index_pending_assets(
        project_id=project_id,
        progress_callback=on_progress
    )

    await progress_tracker.emit(
        project_id=project_id,
        phase="ready",
        progress=100.0,
        message=f"Completed AI vision indexing for {len(indexed)} files."
    )

    return indexed

@router.get("/{project_id}/assets/{asset_id}/thumbnail")
def get_asset_thumbnail(project_id: str, asset_id: str):
    """Returns the cached thumbnail image for an asset."""
    thumb_path = indexer.get_thumbnail_path(asset_id)
    if thumb_path.exists():
        return FileResponse(thumb_path, media_type="image/jpeg", headers={"Cache-Control": "public, max-age=86400"})

    asset = db.get_asset(asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    p = Path(asset.file_path)
    if not p.exists():
        raise HTTPException(status_code=404, detail="File on disk not found")

    # Generate and serve
    indexer.generate_thumbnail(p, asset_id, asset.media_type)
    if thumb_path.exists():
        return FileResponse(thumb_path, media_type="image/jpeg")

    # Fallback to direct file if image
    if asset.media_type == "image":
        return FileResponse(p)

    raise HTTPException(status_code=404, detail="Thumbnail not available")

@router.get("/{project_id}/assets/{asset_id}/file")
def get_asset_raw_file(project_id: str, asset_id: str):
    """Serves the raw full-resolution photo or video file."""
    asset = db.get_asset(asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    p = Path(asset.file_path)
    if not p.exists():
        raise HTTPException(status_code=404, detail="File on disk not found")

    media_type = "video/mp4" if asset.media_type == "video" else "image/jpeg"
    return FileResponse(p, media_type=media_type)

@router.put("/{project_id}/assets/{asset_id}", response_model=MediaAssetModel)
def update_asset(project_id: str, asset_id: str, req: UpdateAssetRequest):
    """Allows user to inspect and edit what the AI thinks about any media asset."""
    asset = db.get_asset(asset_id)
    if not asset or asset.project_id != project_id:
        raise HTTPException(status_code=404, detail="Asset not found")

    updates = {}
    if req.caption is not None:
        updates["caption"] = req.caption.strip()
        # Re-compute SigLIP 2 embedding for user's updated caption
        if req.caption.strip():
            updates["embedding"] = indexer.generate_siglip_embedding(req.caption.strip())
        updates["indexed_by_model"] = "user-edited"

    if req.tags is not None:
        updates["tags"] = req.tags
    if req.quality_score is not None:
        updates["quality_score"] = float(max(1.0, min(10.0, req.quality_score)))
    if req.is_active is not None:
        updates["is_active"] = bool(req.is_active)

    updated = db.update_media_asset(asset_id, updates)
    return updated

@router.post("/{project_id}/assets/{asset_id}/reindex", response_model=MediaAssetModel)
async def reindex_asset(project_id: str, asset_id: str):
    """Re-indexes an individual asset with the AI model waterfall."""
    updated = await indexer.reindex_single_asset(project_id, asset_id)
    if not updated:
        raise HTTPException(status_code=404, detail="Asset not found or failed to reindex")
    return updated

@router.get("/{project_id}/assets/{asset_id}/segments", response_model=List[VideoSegmentModel])
def get_asset_segments(project_id: str, asset_id: str):
    """Returns the visual subsegments and best n-sec timestamps for a video asset."""
    asset = db.get_asset(asset_id)
    if not asset or asset.project_id != project_id:
        raise HTTPException(status_code=404, detail="Asset not found")
    return db.get_video_segments(asset_id)

@router.get("/{project_id}/assets/{asset_id}/frame-scores")
def get_asset_frame_scores(project_id: str, asset_id: str):
    """Returns the time-series frame aesthetic, relevance, and composite scores for charting."""
    asset = db.get_asset(asset_id)
    if not asset or asset.project_id != project_id:
        raise HTTPException(status_code=404, detail="Asset not found")

    segments = db.get_video_segments(asset_id)
    all_points = []
    import json
    for s in segments:
        if s.frame_scores:
            try:
                pts = json.loads(s.frame_scores)
                if isinstance(pts, list):
                    all_points.extend(pts)
            except Exception:
                pass

    all_points.sort(key=lambda x: x.get("t", 0.0))
    return {
        "asset_id": asset_id,
        "duration_sec": asset.duration_sec,
        "segments": [
            {
                "id": s.id,
                "start_time": s.start_time,
                "end_time": s.end_time,
                "best_shot_start": s.best_shot_start,
                "best_shot_end": s.best_shot_end,
                "motion_score": s.motion_score,
                "relevance_score": s.relevance_score,
                "description": s.description
            }
            for s in segments
        ],
        "frame_scores": all_points
    }

@router.post("/{project_id}/assets/{asset_id}/toggle-inclusion")
def toggle_asset_inclusion(project_id: str, asset_id: str, req: ToggleAssetInclusionRequest):
    """
    Manually overrides asset inclusion for the music timeline by automatically
    adjusting its quality/composite score to (threshold_score ± delta) and setting is_active.
    """
    asset = db.get_asset(asset_id)
    if not asset or asset.project_id != project_id:
        raise HTTPException(status_code=404, detail="Asset not found")

    delta = float(req.delta or 0.15)
    rel_daily = float(asset.relevance_score_daily or 0.0)

    # S_inc = 0.5 * S_qual + 0.5 * (S_rel_daily * 10.0)
    # Target S_qual = 2.0 * target_inc - (rel_daily * 10.0)
    if req.include:
        if req.threshold_score is not None:
            target_inc = req.threshold_score + delta
            needed_qual = 2.0 * target_inc - (rel_daily * 10.0)
            if needed_qual > 10.0:
                new_qual = 10.0
                new_rel = min(1.0, max(0.0, (target_inc - 0.5 * 10.0) / 5.0))
                updates = {"quality_score": 10.0, "relevance_score_daily": round(new_rel, 2), "is_active": True}
            else:
                new_qual = max(1.0, min(10.0, needed_qual))
                updates = {"quality_score": round(new_qual, 2), "is_active": True}
        else:
            new_qual = min(10.0, max(1.0, asset.quality_score + 0.6))
            updates = {"quality_score": round(new_qual, 2), "is_active": True}
        
        updated = db.update_media_asset(asset_id, updates)
    else:
        if req.threshold_score is not None:
            target_inc = max(1.0, req.threshold_score - delta)
            needed_qual = 2.0 * target_inc - (rel_daily * 10.0)
            if needed_qual < 1.0:
                new_qual = 1.0
                new_rel = max(0.0, (target_inc - 0.5 * 1.0) / 5.0)
                updates = {"quality_score": 1.0, "relevance_score_daily": round(new_rel, 2)}
            else:
                new_qual = max(1.0, min(10.0, needed_qual))
                updates = {"quality_score": round(new_qual, 2)}
        else:
            new_qual = max(1.0, min(10.0, asset.quality_score - 0.6))
            updates = {"quality_score": round(new_qual, 2)}
        
        updated = db.update_media_asset(asset_id, updates)

    return {
        "status": "updated",
        "asset": updated,
        "new_score": music_gen.compute_asset_inclusion_score(updated)
    }

@router.post("/{project_id}/music/analyze-timeline")
def analyze_music_timeline(project_id: str, req: Optional[AnalyzeMusicTimelineRequest] = None):
    """
    Phase 1: Calculates daily media stats, applies inclusion thresholds,
    and returns section timing and suggested total duration and BPM.
    """
    proj = db.get_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")

    assets = db.get_project_assets(project_id)
    diary_days = (proj.config_override or {}).get("diary_days")

    custom_cfg = proj.config_override or {}
    if req:
        if req.pacing_preset:
            custom_cfg.setdefault("pacing_rules", {})["pacing_preset"] = req.pacing_preset
        if req.photo_sec is not None:
            custom_cfg.setdefault("pacing_rules", {})["photo_sec"] = req.photo_sec
        if req.video_sec_max is not None:
            custom_cfg.setdefault("pacing_rules", {})["video_sec_max"] = req.video_sec_max
        if req.default_inclusion_threshold is not None:
            custom_cfg["default_inclusion_threshold"] = req.default_inclusion_threshold
        if req.daily_inclusion_thresholds is not None:
            custom_cfg["daily_inclusion_thresholds"] = req.daily_inclusion_thresholds

        # Persist updated threshold config into project
        db.update_project(project_id, config_override=custom_cfg)

    logger.info(f"[MusicStudio] [Phase 1: Timeline Analysis] Project: {project_id}, Pacing: {req.pacing_preset if req else 'balanced'}, Default Threshold: {req.default_inclusion_threshold if req else 70.0}%")
    analysis = music_gen.calculate_media_timeline_estimate(
        project_id=project_id,
        diary_days=diary_days,
        assets=assets,
        custom_config=custom_cfg
    )
    logger.debug(f"[MusicStudio] [Phase 1: Results] Total Dur: {analysis.get('total_duration_sec')}s, Suggested BPM: {analysis.get('suggested_bpm')}, Acts Count: {len(analysis.get('acts', []))}")
    return analysis

@router.post("/{project_id}/music/generate-prompt")
async def generate_music_prompt_endpoint(project_id: str, req: Optional[GenerateMusicPromptRequest] = None):
    """
    Phase 2: Generates an optimized Google Flow Music prompt with section cues.
    """
    proj = db.get_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")

    assets = db.get_project_assets(project_id)
    diary_days = (proj.config_override or {}).get("diary_days")

    acts = req.acts if req and req.acts else None
    if not acts:
        est = music_gen.calculate_media_timeline_estimate(
            project_id=project_id,
            diary_days=diary_days,
            assets=assets,
            custom_config=proj.config_override
        )
        acts = est["acts"]
        suggested_bpm = est["suggested_bpm"]
        total_dur = est["total_duration_sec"]
    else:
        suggested_bpm = req.suggested_bpm or 118
        total_dur = req.total_duration_sec or 30.0

    style_vibe = req.style_vibe if req else None
    logger.info(f"[MusicStudio] [Phase 2: Prompt Generation] Project: {project_id}, Vibe: {style_vibe or 'default'}, BPM: {suggested_bpm}, Dur: {total_dur}s, Acts: {len(acts)}")

    prompt_data = await music_gen.generate_music_prompt_async(
        acts=acts,
        diary_text=proj.narrative_text,
        suggested_bpm=suggested_bpm,
        total_duration_sec=total_dur,
        style_vibe=style_vibe
    )
    logger.debug(f"[MusicStudio] [Phase 2: Generated Prompt]: {prompt_data.get('flow_prompt')}")
    return prompt_data

@router.post("/{project_id}/music/generate-lyrics")
async def generate_music_lyrics_endpoint(project_id: str, req: Optional[GenerateMusicLyricsRequest] = None):
    """
    Phase 3: Generates proportional rhyming lyrics with explicit section timestamp cues.
    """
    proj = db.get_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")

    assets = db.get_project_assets(project_id)
    diary_days = (proj.config_override or {}).get("diary_days")

    acts = req.acts if req and req.acts else None
    if not acts:
        est = music_gen.calculate_media_timeline_estimate(
            project_id=project_id,
            diary_days=diary_days,
            assets=assets,
            custom_config=proj.config_override
        )
        acts = est["acts"]

    flow_p = req.flow_prompt if req and req.flow_prompt else ""
    is_inst = req.is_instrumental if req and req.is_instrumental is not None else False
    logger.info(f"[MusicStudio] [Phase 3: Lyrics / Subtitles Generation] Project: {project_id}, Instrumental: {is_inst}, Acts: {len(acts)}")

    lyrics, out_prompt = await music_gen.generate_rhyming_lyrics_async(
        acts=acts,
        narrative_text=proj.narrative_text,
        flow_prompt=flow_p,
        is_instrumental=is_inst
    )
    logger.debug(f"[MusicStudio] [Phase 3: Output Lyrics / Subtitles]:\n{lyrics}")

    return {
        "lyrics": lyrics,
        "prompt": out_prompt,
        "is_instrumental": is_inst
    }

@router.post("/{project_id}/music/synthesize-and-align", response_model=AudioTrackModel)
@router.post("/{project_id}/music/analyze-and-align", response_model=AudioTrackModel)
@router.post("/{project_id}/generate-music", response_model=AudioTrackModel)
async def generate_music_and_align(project_id: str, req: Optional[SynthesizeMusicAudioRequest] = None):
    """
    Phase 4 / Analyze & Align: Previews audio track, separates vocal/accompaniment stems
    with Demucs, extracts Librosa beat grid, and aligns lyrics/subtitles with MMS-FA CTC forced alignment.
    """
    proj = db.get_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")

    db.update_project_status(project_id, "generating_music")
    try:
        assets = db.get_project_assets(project_id)
        diary_days = (proj.config_override or {}).get("diary_days")

        # Run timeline estimate to determine exact duration & acts if not provided
        est = music_gen.calculate_media_timeline_estimate(
            project_id=project_id,
            diary_days=diary_days,
            assets=assets,
            custom_config=proj.config_override
        )

        acts = est["acts"]
        bpm = float(req.bpm if req and req.bpm else est["suggested_bpm"])
        duration = float(req.duration_sec if req and req.duration_sec else est["total_duration_sec"])
        is_inst = bool(req.is_instrumental if req and req.is_instrumental is not None else False)

        prompt = req.prompt if req and req.prompt else None
        lyrics = req.lyrics if req and req.lyrics else None
        logger.info(f"[MusicStudio] [Phase 4: Analyze & Align] Project: {project_id}, BPM: {bpm}, Dur: {duration}s, Instrumental: {is_inst}, Lyrics Len: {len(lyrics or '')} chars")

        if not prompt or not lyrics:
            await progress_tracker.emit(project_id, "music_gen", 15.0, "Structuring narrative acts and optimizing Google Flow Music prompt...")
            gen_lyrics, gen_prompt = await music_gen.generate_rhyming_lyrics_async(
                acts=acts,
                narrative_text=proj.narrative_text,
                flow_prompt=prompt or "",
                is_instrumental=is_inst
            )
            lyrics = lyrics or gen_lyrics
            prompt = prompt or gen_prompt
        else:
            lyrics = music_gen.enforce_acts_timeline_on_lyrics(acts, lyrics, is_instrumental=is_inst)

        loop = asyncio.get_running_loop()
        def on_synth_progress(msg: str, pct: float):
            try:
                asyncio.run_coroutine_threadsafe(
                    progress_tracker.emit(project_id, "music_gen", pct, msg),
                    loop
                )
            except Exception:
                pass

        audio_files = music_gen.synthesize_music_track(
            project_id=project_id,
            lyrics=lyrics,
            prompt=prompt,
            bpm=bpm,
            target_duration_sec=duration,
            is_instrumental=is_inst,
            progress_callback=on_synth_progress
        )

        db.update_project_status(project_id, "aligning")
        await progress_tracker.emit(project_id, "aligning", 65.0, "Demixing vocal and backing stems with Demucs...")
        stems = aligner.separate_stems_demucs(
            master_path=audio_files["master_path"],
            output_dir=audio_files["master_path"].parent
        )

        await progress_tracker.emit(project_id, "aligning", 80.0, "Extracting Librosa beat grid and downbeats...")
        track_bpm, beat_grid, downbeats = aligner.extract_beat_grid(audio_files["master_path"])

        await progress_tracker.emit(project_id, "aligning", 95.0, "Aligning lyrics with MMS_FA CTC trellis...")
        aligned_words = []
        if lyrics:
            if not is_inst:
                aligned_words = aligner.align_lyrics_mms_fa(
                    vocal_path=stems["vocals"],
                    lyrics_text=lyrics,
                    beat_grid=beat_grid
                )
            else:
                aligned_words = aligner.align_instrumental_narration_subtitles(
                    subtitles_text=lyrics,
                    beat_grid=beat_grid
                )

        track_id = f"trk_{project_id}"
        track = AudioTrackModel(
            id=track_id,
            project_id=project_id,
            master_path=str(audio_files["master_path"].resolve()),
            vocal_stem_path=str(stems["vocals"].resolve()),
            accompaniment_stem_path=str(stems["accompaniment"].resolve()),
            prompt=prompt,
            lyrics=lyrics,
            is_instrumental=is_inst,
            bpm=track_bpm,
            beat_grid=beat_grid,
            downbeats=downbeats,
            aligned_lyrics=aligned_words
        )
        db.save_audio_track(track)
        db.update_project_status(project_id, "ready")
        await progress_tracker.emit(project_id, "ready", 100.0, "Audio generation & beat alignment complete!")

        return track
    except Exception as e:
        logger.exception("Music generation failed")
        db.update_project_status(project_id, "error", str(e))
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{project_id}/upload-custom-audio", response_model=AudioTrackModel)
async def upload_custom_audio_and_align(
    project_id: str,
    file: UploadFile = File(...),
    bpm: Optional[float] = Form(None),
    is_instrumental: bool = Form(False)
):
    """
    Accepts user-uploaded audio, runs Demucs stem separation, Librosa beat tracking,
    and MMS-FA lyric alignment (or instrumental narration subtitle timing).
    """
    proj = db.get_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")

    settings = get_settings()
    out_dir = settings.output_dir / project_id
    out_dir.mkdir(parents=True, exist_ok=True)

    master_path = out_dir / "master.wav"
    with open(master_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    db.update_project_status(project_id, "separating_stems")
    try:
        await progress_tracker.emit(project_id, "separating_stems", 40.0, "Separating audio stems with Demucs HTDemucs...")
        stems = aligner.separate_stems_demucs(master_path, out_dir)

        await progress_tracker.emit(project_id, "beat_tracking", 70.0, "Tracking Librosa beat grid...")
        detected_bpm, beat_grid, downbeats = aligner.extract_beat_grid(master_path)
        final_bpm = float(bpm) if bpm and bpm > 0 else detected_bpm

        existing_track = db.get_audio_track(project_id)
        lyrics = existing_track.lyrics if existing_track else ""

        await progress_tracker.emit(project_id, "aligning", 90.0, "Aligning lyrics & subtitles...")
        aligned_words = []
        if lyrics:
            if not is_instrumental:
                aligned_words = aligner.align_lyrics_mms_fa(
                    vocal_path=stems["vocals"],
                    lyrics_text=lyrics,
                    beat_grid=beat_grid
                )
            else:
                aligned_words = aligner.align_instrumental_narration_subtitles(
                    subtitles_text=lyrics,
                    beat_grid=beat_grid
                )

        track_id = f"trk_{project_id}"
        track = AudioTrackModel(
            id=track_id,
            project_id=project_id,
            master_path=str(master_path.resolve()),
            vocal_stem_path=str(stems["vocals"].resolve()),
            accompaniment_stem_path=str(stems["accompaniment"].resolve()),
            prompt=prompt,
            lyrics=lyrics,
            is_instrumental=is_instrumental or False,
            bpm=final_bpm,
            beat_grid=beat_grid,
            downbeats=downbeats,
            aligned_lyrics=aligned_words
        )
        db.save_audio_track(track)
        db.update_project_status(project_id, "ready")
        await progress_tracker.emit(project_id, "ready", 100.0, "Custom audio stems and beat alignment ready!")
        return track
    except Exception as e:
        logger.exception("Upload audio processing failed")
        db.update_project_status(project_id, "error", str(e))
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{project_id}/audio/{stem_type}")
def stream_audio_stem(project_id: str, stem_type: str):
    track = db.get_audio_track(project_id)
    if not track:
        raise HTTPException(status_code=404, detail="Audio track not found")

    path_map = {
        "master": track.master_path,
        "vocals": track.vocal_stem_path,
        "accompaniment": track.accompaniment_stem_path
    }

    target = path_map.get(stem_type)
    if not target or not Path(target).exists():
        raise HTTPException(status_code=404, detail=f"Audio stem '{stem_type}' not found on disk")

    return FileResponse(target, media_type="audio/wav")

@router.put("/{project_id}/lyrics", response_model=AudioTrackModel)
def update_project_lyrics(project_id: str, req: UpdateLyricsRequest):
    """
    Updates audio track lyrics and/or word-level aligned timestamps.
    Supports in-browser fine-tuning, fixing misheard lyrics, and nudging word timestamps.
    """
    track = db.get_audio_track(project_id)
    if not track:
        raise HTTPException(status_code=404, detail="Audio track not found")

    new_lyrics = req.lyrics if req.lyrics is not None else track.lyrics
    new_aligned = track.aligned_lyrics

    if req.aligned_lyrics is not None:
        if req.auto_snap:
            new_aligned = aligner.snap_words(req.aligned_lyrics, track.beat_grid)
        else:
            new_aligned = req.aligned_lyrics

    # If enable_word_highlight flag is provided, persist it in project config_override
    if req.enable_word_highlight is not None:
        proj = db.get_project(project_id)
        if proj:
            cfg = proj.config_override or {}
            lyr_style = cfg.get("lyrics_style", {})
            lyr_style["enable_word_highlight"] = req.enable_word_highlight
            cfg["lyrics_style"] = lyr_style
            db.update_project(project_id, config_override=cfg)

    updated_track = db.update_audio_track_lyrics(
        project_id=project_id,
        lyrics=new_lyrics,
        aligned_lyrics=new_aligned
    )
    if not updated_track:
        raise HTTPException(status_code=500, detail="Failed to update audio track lyrics")

    return updated_track

@router.post("/{project_id}/realign-lyrics", response_model=AudioTrackModel)
async def realign_project_lyrics(project_id: str, req: Optional[RealignLyricsRequest] = None):
    """
    Re-runs TorchAudio MMS_FA CTC forced alignment on updated lyrics against project vocal stem and beat grid.
    """
    track = db.get_audio_track(project_id)
    if not track:
        raise HTTPException(status_code=404, detail="Audio track not found")

    lyrics_text = (req.lyrics if req and req.lyrics is not None else track.lyrics) or ""
    if not lyrics_text.strip():
        raise HTTPException(status_code=400, detail="Lyrics text cannot be empty for alignment")

    vocal_target = track.vocal_stem_path if track.vocal_stem_path and Path(track.vocal_stem_path).exists() else track.master_path
    if not vocal_target or not Path(vocal_target).exists():
        raise HTTPException(status_code=400, detail="Audio stem file not found on disk")

    try:
        if track.is_instrumental:
            aligned_words = aligner.align_instrumental_narration_subtitles(
                subtitles_text=lyrics_text,
                beat_grid=track.beat_grid,
                bpm=track.bpm
            )
        else:
            aligned_words = aligner.align_lyrics_mms_fa(
                vocal_path=Path(vocal_target),
                lyrics_text=lyrics_text,
                beat_grid=track.beat_grid
            )

        updated_track = db.update_audio_track_lyrics(
            project_id=project_id,
            lyrics=lyrics_text,
            aligned_lyrics=aligned_words
        )
        return updated_track
    except Exception as e:
        logger.exception("Lyric re-alignment failed")
        raise HTTPException(status_code=500, detail=f"Alignment failed: {str(e)}")

@router.post("/{project_id}/solve-timeline")
async def solve_timeline(project_id: str):
    proj = db.get_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")

    audio = db.get_audio_track(project_id)
    if not audio:
        raise HTTPException(status_code=400, detail="Audio track must be generated or uploaded first")

    assets = db.get_project_assets(project_id)
    if not assets:
        raise HTTPException(status_code=400, detail="No media assets found. Please upload or index photos and videos first.")

    db.update_project_status(project_id, "solving")
    try:
        await progress_tracker.emit(project_id, "solving", 50.0, "Optimizing constraint-based media placement...")
        slices = beat_solver.solve_timeline(
            project_id=project_id,
            audio_track=audio,
            assets=assets,
            custom_config=proj.config_override
        )
        saved_slices = db.save_timeline_slices(project_id, slices) or []
        db.update_project_status(project_id, "ready")
        await progress_tracker.emit(project_id, "ready", 100.0, f"Solved timeline with {len(saved_slices)} clips!")
        return {"status": "solved", "slices_count": len(saved_slices), "slices": saved_slices}
    except Exception as e:
        logger.exception("Beat solver failed")
        db.update_project_status(project_id, "error", str(e))
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{project_id}/render-video")
async def render_montage_video(project_id: str):
    proj = db.get_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")

    audio = db.get_audio_track(project_id)
    slices = db.get_timeline_slices(project_id)
    assets = db.get_project_assets(project_id)

    if not audio or not slices or not assets:
        raise HTTPException(status_code=400, detail="Audio, slices, and assets must all be present before rendering")

    db.update_project_status(project_id, "rendering")
    try:
        settings = get_settings()
        out_dir = settings.output_dir / project_id
        out_video = out_dir / "montage.mp4"

        loop = asyncio.get_running_loop()
        def on_render_progress(msg: str, pct: float):
            try:
                asyncio.run_coroutine_threadsafe(
                    progress_tracker.emit(project_id, "rendering", pct, msg),
                    loop
                )
            except Exception:
                pass

        final_path = compositor.render_timeline(
            project_id=project_id,
            slices=slices,
            audio_track=audio,
            output_path=out_video,
            custom_config=proj.config_override,
            progress_callback=on_render_progress
        )

        db.update_project_status(project_id, "completed")
        await progress_tracker.emit(project_id, "ready", 100.0, "Video render complete!")
        return {"status": "completed", "video_url": f"/api/projects/{project_id}/video"}
    except Exception as e:
        logger.exception("Video render failed")
        db.update_project_status(project_id, "error", str(e))
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{project_id}/video")
def stream_rendered_video(project_id: str):
    settings = get_settings()
    out_video = settings.output_dir / project_id / "montage.mp4"
    if not out_video.exists():
        raise HTTPException(status_code=404, detail="Rendered video not found")
    return FileResponse(out_video, media_type="video/mp4")

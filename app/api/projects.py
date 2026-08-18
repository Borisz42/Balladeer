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

class CreateProjectRequest(BaseModel):
    title: str
    narrative_text: str
    config_override: Optional[Dict[str, Any]] = None

class UpdateProjectRequest(BaseModel):
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
    enable_local_synthesis: Optional[bool] = False

class UpdateAssetRequest(BaseModel):
    caption: Optional[str] = None
    tags: Optional[List[str]] = None
    quality_score: Optional[float] = None
    is_active: Optional[bool] = None

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

@router.post("/{project_id}/generate-music", response_model=AudioTrackModel)
async def generate_music_and_align(project_id: str, req: GenerateMusicRequest):
    proj = db.get_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")

    db.update_project_status(project_id, "generating_music")
    try:
        await progress_tracker.emit(project_id, "music_gen", 15.0, "Structuring narrative acts and optimizing Google Flow Music prompt...")
        diary_days = proj.config_override.get("diary_days") if proj.config_override else None
        acts = music_gen.partition_narrative_to_acts(proj.narrative_text, diary_days=diary_days)
        lyrics, gen_prompt = await music_gen.generate_rhyming_lyrics_async(
            acts=acts,
            narrative_text=proj.narrative_text,
            is_instrumental=bool(req.is_instrumental)
        )

        prompt = req.prompt or gen_prompt

        bpm = req.bpm or 120.0
        duration = req.duration_sec or 30.0

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
            is_instrumental=req.is_instrumental,
            enable_local_synthesis=bool(req.enable_local_synthesis),
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
        aligned_words = aligner.align_lyrics_mms_fa(
            vocal_path=stems["vocals"],
            lyrics_text=lyrics,
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
            is_instrumental=req.is_instrumental or False,
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

@router.post("/{project_id}/upload-audio", response_model=AudioTrackModel)
async def upload_custom_audio(
    project_id: str,
    file: UploadFile = File(...),
    bpm: Optional[float] = Form(None),
    is_instrumental: Optional[bool] = Form(False)
):
    """Uploads external audio track (e.g. from Google Flow Music / Lyria) and processes stems & alignment."""
    proj = db.get_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")

    settings = get_settings()
    proj_out_dir = settings.output_dir / project_id
    proj_out_dir.mkdir(parents=True, exist_ok=True)

    master_path = proj_out_dir / f"master{Path(file.filename).suffix}"
    with open(master_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    db.update_project_status(project_id, "aligning")
    try:
        await progress_tracker.emit(project_id, "aligning", 30.0, "Demixing stems with Demucs from uploaded audio...")
        stems = aligner.separate_stems_demucs(master_path=master_path, output_dir=proj_out_dir)

        await progress_tracker.emit(project_id, "aligning", 60.0, "Detecting beats and tempo from custom audio...")
        detected_bpm, beat_grid, downbeats = aligner.extract_beat_grid(master_path)
        final_bpm = bpm if bpm and bpm > 0 else detected_bpm

        existing_track = db.get_audio_track(project_id)
        lyrics = existing_track.lyrics if existing_track else ""
        prompt = existing_track.prompt if existing_track else "Custom uploaded audio"

        await progress_tracker.emit(project_id, "aligning", 85.0, "Running phonetic MMS_FA forced alignment...")
        aligned_words = []
        if lyrics and not is_instrumental:
            aligned_words = aligner.align_lyrics_mms_fa(
                vocal_path=stems["vocals"],
                lyrics_text=lyrics,
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

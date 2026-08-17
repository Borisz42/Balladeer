import os
import shutil
import logging
import asyncio
from pathlib import Path
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.core.config import get_settings
from app.database.database import db
from app.database.models import (
    ProjectModel,
    MediaAssetModel,
    AudioTrackModel,
    ProjectDetailResponse
)
from app.pipeline.indexer import MediaIndexer
from app.pipeline.music_gen import MusicGenerator
from app.pipeline.aligner import AudioAligner
from app.pipeline.beat_solver import BeatSolver
from app.pipeline.compositor import VideoCompositor
from app.api.progress import progress_tracker

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/projects", tags=["projects"])

indexer = MediaIndexer()
music_gen = MusicGenerator()
aligner = AudioAligner()
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

@router.post("", response_model=ProjectModel)
def create_project(req: CreateProjectRequest):
    project_id = f"proj_{int(Path('.').stat().st_mtime * 1000) % 1000000}_{os.urandom(3).hex()}"
    proj = ProjectModel(
        id=project_id,
        title=req.title,
        narrative_text=req.narrative_text,
        config_override=req.config_override
    )
    return db.create_project(proj)

@router.put("/{project_id}", response_model=ProjectDetailResponse)
@router.put("/{project_id}/diary", response_model=ProjectDetailResponse)
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

@router.get("", response_model=List[ProjectModel])
def list_projects():
    return db.list_projects()

@router.get("/{project_id}", response_model=ProjectDetailResponse)
def get_project_detail(project_id: str):
    proj = db.get_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")

    assets = db.get_project_assets(project_id)
    audio = db.get_audio_track(project_id)
    slices = db.get_timeline_slices(project_id)

    settings = get_settings()
    video_path = settings.output_dir / project_id / "montage.mp4"
    video_url = f"/api/projects/{project_id}/video" if video_path.exists() else None

    return ProjectDetailResponse(
        project=proj,
        assets=assets,
        audio_track=audio,
        timeline_slices=slices,
        rendered_video_url=video_url
    )

@router.delete("/{project_id}")
def delete_project(project_id: str):
    proj = db.get_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")
    db.delete_project(project_id)
    return {"status": "deleted", "id": project_id}

@router.post("/{project_id}/upload", response_model=List[MediaAssetModel])
async def upload_media(project_id: str, files: List[UploadFile] = File(...)):
    proj = db.get_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")

    settings = get_settings()
    project_upload_dir = settings.uploads_dir / project_id
    project_upload_dir.mkdir(parents=True, exist_ok=True)

    added_assets = []
    total = len(files)
    for idx, file in enumerate(files):
        file_path = project_upload_dir / file.filename
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        asset = indexer.index_media_file(project_id, file_path)
        db.add_media_asset(asset)
        added_assets.append(asset)

        await progress_tracker.emit(
            project_id=project_id,
            phase="indexing",
            progress=((idx + 1) / total) * 100,
            message=f"Indexed asset {idx + 1}/{total}: {file.filename}"
        )

    return added_assets

@router.post("/{project_id}/index-directory", response_model=List[MediaAssetModel])
async def index_directory(project_id: str, req: IndexDirRequest):
    proj = db.get_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")

    dir_path = Path(req.directory_path)
    if not dir_path.exists() or not dir_path.is_dir():
        raise HTTPException(status_code=400, detail="Invalid directory path")

    added_assets = []
    supported_exts = {".jpg", ".jpeg", ".png", ".webp", ".mp4", ".mov", ".mkv", ".avi"}
    files = [f for f in dir_path.glob("*") if f.suffix.lower() in supported_exts]
    total = len(files)

    for idx, f in enumerate(files):
        asset = indexer.index_media_file(project_id, f)
        db.add_media_asset(asset)
        added_assets.append(asset)

        await progress_tracker.emit(
            project_id=project_id,
            phase="indexing",
            progress=((idx + 1) / max(total, 1)) * 100,
            message=f"Indexed asset {idx + 1}/{total}: {f.name}"
        )

    return added_assets

@router.post("/{project_id}/generate-music", response_model=AudioTrackModel)
async def generate_music_and_align(project_id: str, req: GenerateMusicRequest):
    proj = db.get_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")

    db.update_project_status(project_id, "generating_music")
    try:
        diary_days = proj.config_override.get("diary_days") if proj.config_override else None
        acts = music_gen.partition_narrative_to_acts(proj.narrative_text, diary_days=diary_days)
        lyrics, gen_prompt = music_gen.generate_rhyming_lyrics(acts, is_instrumental=req.is_instrumental)
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
            is_instrumental=bool(req.is_instrumental),
            bpm=track_bpm,
            beat_grid=beat_grid,
            downbeats=downbeats,
            aligned_lyrics=aligned_words
        )
        saved_track = db.save_audio_track(track)
        db.update_project_status(project_id, "ready")
        await progress_tracker.emit(project_id, "ready", 100.0, "Audio track and alignment ready!")
        return saved_track
    except Exception as e:
        logger.exception("Music generation failed")
        db.update_project_status(project_id, "error", str(e))
        await progress_tracker.emit(project_id, "error", 0.0, f"Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{project_id}/solve-timeline")
async def solve_timeline(project_id: str):
    proj = db.get_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")

    audio = db.get_audio_track(project_id)
    if not audio:
        raise HTTPException(status_code=400, detail="Audio track must be generated first")

    assets = db.get_project_assets(project_id)
    if not assets:
        raise HTTPException(status_code=400, detail="No media assets found")

    db.update_project_status(project_id, "solving")
    try:
        await progress_tracker.emit(project_id, "solving", 50.0, "Optimizing constraint-based media placement...")
        slices = beat_solver.solve_timeline(
            project_id=project_id,
            audio_track=audio,
            assets=assets,
            custom_config=proj.config_override
        )
        db.save_timeline_slices(project_id, slices)
        db.update_project_status(project_id, "ready")
        await progress_tracker.emit(project_id, "ready", 100.0, f"Generated {len(slices)} beat-aligned video cuts.")
        return db.get_timeline_slices(project_id)
    except Exception as e:
        logger.exception("Timeline solve failed")
        db.update_project_status(project_id, "error", str(e))
        await progress_tracker.emit(project_id, "error", 0.0, f"Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{project_id}/render")
def render_project_video(project_id: str, background_tasks: BackgroundTasks):
    proj = db.get_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")

    audio = db.get_audio_track(project_id)
    slices = db.get_timeline_slices(project_id)
    if not audio or not slices:
        raise HTTPException(status_code=400, detail="Audio track and timeline slices required")

    db.update_project_status(project_id, "rendering")

    def run_render():
        try:
            aspect = "16:9"
            if proj.config_override and "video" in proj.config_override:
                aspect = proj.config_override["video"].get("aspect_ratio", "16:9")

            compositor.assemble_final_video(
                project_id=project_id,
                slices=slices,
                audio_track=audio,
                aspect_ratio=aspect
            )
            db.update_project_status(project_id, "completed")
        except Exception as e:
            logger.exception("Render failed")
            db.update_project_status(project_id, "error", str(e))

    background_tasks.add_task(run_render)
    return {"status": "rendering", "project_id": project_id}

@router.get("/{project_id}/video")
def get_rendered_video(project_id: str):
    settings = get_settings()
    video_path = settings.output_dir / project_id / "montage.mp4"
    if not video_path.exists():
        raise HTTPException(status_code=404, detail="Rendered video not found")
    return FileResponse(str(video_path), media_type="video/mp4", filename=f"{project_id}_montage.mp4")

@router.get("/{project_id}/audio/{stem_type}")
def get_audio_file(project_id: str, stem_type: str):
    audio = db.get_audio_track(project_id)
    if not audio:
        raise HTTPException(status_code=404, detail="Audio track not found")

    path_map = {
        "master": audio.master_path,
        "vocals": audio.vocal_stem_path,
        "accompaniment": audio.accompaniment_stem_path
    }
    p = path_map.get(stem_type)
    if not p or not Path(p).exists():
        raise HTTPException(status_code=404, detail="Audio stem file not found")
    return FileResponse(p, media_type="audio/wav")

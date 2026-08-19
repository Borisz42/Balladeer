import logging
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.database.database import db
from app.database.models import TimelineSliceModel, MediaAssetModel

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/timeline", tags=["timeline"])

class UpdateSliceRequest(BaseModel):
    asset_id: Optional[str] = None
    bg_mode: Optional[str] = None
    enable_ken_burns: Optional[bool] = None
    beat_count: Optional[int] = None
    custom_caption: Optional[str] = None
    audio_muted: Optional[bool] = None
    audio_volume: Optional[float] = None

class BulkApplyRequest(BaseModel):
    action: str # "apply_bg_mode", "toggle_ken_burns", "set_custom_captions", "set_audio_mute", "set_audio_volume"
    bg_mode: Optional[str] = None
    enable_ken_burns: Optional[bool] = None
    captions_map: Optional[Dict[str, str]] = None # slice_id -> caption
    audio_muted: Optional[bool] = None
    audio_volume: Optional[float] = None

class UpdateControlsRequest(BaseModel):
    video_effects: Optional[Dict[str, Any]] = None
    lyrics_style: Optional[Dict[str, Any]] = None
    text_overlays: Optional[Dict[str, Any]] = None
    pacing_rules: Optional[Dict[str, Any]] = None
    audio_mastering: Optional[Dict[str, Any]] = None
    video: Optional[Dict[str, Any]] = None

class SwapAssetRequest(BaseModel):
    new_asset_id: str

class SplitSliceRequest(BaseModel):
    split_at_beat: int

class ReorderSlicesRequest(BaseModel):
    ordered_slice_ids: List[str]

class RecommendationResponse(BaseModel):
    asset: MediaAssetModel
    similarity_score: float

@router.get("/{project_id}/slices", response_model=List[TimelineSliceModel])
def get_slices(project_id: str):
    return db.get_timeline_slices(project_id)

@router.put("/slices/{slice_id}")
def update_slice(slice_id: str, req: UpdateSliceRequest):
    updates = {}
    if req.asset_id is not None:
        updates["asset_id"] = req.asset_id
    if req.bg_mode is not None:
        updates["bg_mode"] = req.bg_mode
    if req.enable_ken_burns is not None:
        updates["enable_ken_burns"] = 1 if req.enable_ken_burns else 0
    if req.beat_count is not None:
        updates["beat_count"] = req.beat_count
    if req.custom_caption is not None:
        updates["custom_caption"] = req.custom_caption
    if req.audio_muted is not None:
        updates["audio_muted"] = 1 if req.audio_muted else 0
    if req.audio_volume is not None:
        updates["audio_volume"] = req.audio_volume

    db.update_timeline_slice(slice_id, updates)
    return {"status": "updated", "slice_id": slice_id}

@router.post("/{project_id}/bulk-apply")
def bulk_apply_slice_effects(project_id: str, req: BulkApplyRequest):
    slices = db.get_timeline_slices(project_id)
    if not slices:
        return {"status": "no_slices", "updated_count": 0}

    for s in slices:
        if req.action == "apply_bg_mode" and req.bg_mode:
            s.bg_mode = req.bg_mode
        elif req.action == "toggle_ken_burns" and req.enable_ken_burns is not None:
            if not s.asset or s.asset.media_type != "video":
                s.enable_ken_burns = req.enable_ken_burns
        elif req.action == "set_custom_captions" and req.captions_map:
            if s.id in req.captions_map:
                s.custom_caption = req.captions_map[s.id]
        elif req.action == "set_audio_mute" and req.audio_muted is not None:
            s.audio_muted = req.audio_muted
        elif req.action == "set_audio_volume" and req.audio_volume is not None:
            s.audio_volume = req.audio_volume

    db.save_timeline_slices(project_id, slices)
    return {"status": "bulk_applied", "updated_count": len(slices), "slices": db.get_timeline_slices(project_id)}

@router.put("/{project_id}/controls")
def update_timeline_controls(project_id: str, req: UpdateControlsRequest):
    proj = db.get_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")

    cfg = proj.config_override or {}
    if req.video_effects is not None:
        cfg["video_effects"] = {**cfg.get("video_effects", {}), **req.video_effects}
    if req.lyrics_style is not None:
        cfg["lyrics_style"] = {**cfg.get("lyrics_style", {}), **req.lyrics_style}
    if req.text_overlays is not None:
        cfg["text_overlays"] = {**cfg.get("text_overlays", {}), **req.text_overlays}
    if req.pacing_rules is not None:
        cfg["pacing_rules"] = {**cfg.get("pacing_rules", {}), **req.pacing_rules}
    if req.audio_mastering is not None:
        cfg["audio_mastering"] = {**cfg.get("audio_mastering", {}), **req.audio_mastering}
    if req.video is not None:
        cfg["video"] = {**cfg.get("video", {}), **req.video}

    db.update_project(project_id=project_id, config_override=cfg)
    updated_proj = db.get_project(project_id)
    return {"status": "controls_updated", "config_override": cfg, "project": updated_proj}

@router.post("/{project_id}/slices/{slice_id}/split")
def split_slice(project_id: str, slice_id: str, req: SplitSliceRequest):
    slices = db.get_timeline_slices(project_id)
    target_idx = next((i for i, s in enumerate(slices) if s.id == slice_id), None)
    if target_idx is None:
        raise HTTPException(status_code=404, detail="Slice not found")

    target = slices[target_idx]
    if target.beat_count <= 1:
        raise HTTPException(status_code=400, detail="Cannot split a 1-beat slice")

    split_point = max(1, min(target.beat_count - 1, req.split_at_beat - target.start_beat))
    first_beats = split_point
    second_beats = target.beat_count - split_point

    # Calculate timestamps
    audio = db.get_audio_track(project_id)
    beat_grid = audio.beat_grid if audio else []
    
    # Update first slice
    target.beat_count = first_beats
    if target.start_beat + first_beats < len(beat_grid):
        target.timeline_end_sec = beat_grid[target.start_beat + first_beats]

    # Create second slice
    new_start_beat = target.start_beat + first_beats
    t_start = beat_grid[new_start_beat] if new_start_beat < len(beat_grid) else target.timeline_end_sec
    new_end_beat = new_start_beat + second_beats
    t_end = beat_grid[new_end_beat] if new_end_beat < len(beat_grid) else t_start + second_beats * 0.5

    new_slice = TimelineSliceModel(
        id=f"slice_{project_id}_{len(slices)}_{new_start_beat}",
        project_id=project_id,
        audio_track_id=target.audio_track_id,
        asset_id=target.asset_id,
        start_beat=new_start_beat,
        beat_count=second_beats,
        timeline_start_sec=round(t_start, 4),
        timeline_end_sec=round(t_end, 4),
        clip_order=target_idx + 1,
        bg_mode=target.bg_mode,
        enable_ken_burns=target.enable_ken_burns,
        asset=target.asset
    )

    slices.insert(target_idx + 1, new_slice)
    # Re-index clip order
    for idx, s in enumerate(slices):
        s.clip_order = idx

    db.save_timeline_slices(project_id, slices)
    return db.get_timeline_slices(project_id)

@router.put("/{project_id}/reorder")
def reorder_slices(project_id: str, req: ReorderSlicesRequest):
    slices = db.get_timeline_slices(project_id)
    slice_map = {s.id: s for s in slices}

    new_ordered = []
    for idx, sid in enumerate(req.ordered_slice_ids):
        if sid in slice_map:
            s = slice_map[sid]
            s.clip_order = idx
            new_ordered.append(s)

    db.save_timeline_slices(project_id, new_ordered)
    return db.get_timeline_slices(project_id)

@router.get("/{project_id}/slices/{slice_id}/recommendations", response_model=List[RecommendationResponse])
def get_slice_recommendations(project_id: str, slice_id: str, top_k: int = 5):
    slices = db.get_timeline_slices(project_id)
    target_slice = next((s for s in slices if s.id == slice_id), None)
    if not target_slice:
        raise HTTPException(status_code=404, detail="Timeline slice not found")

    current_asset = db.get_asset(target_slice.asset_id)
    if not current_asset or not current_asset.embedding:
        all_assets = db.get_project_assets(project_id)
        return [
            RecommendationResponse(asset=a, similarity_score=0.75)
            for a in all_assets if a.id != target_slice.asset_id
        ][:top_k]

    results = db.search_similar_assets(
        project_id=project_id,
        target_embedding=current_asset.embedding,
        top_k=top_k,
        exclude_asset_id=current_asset.id
    )

    return [
        RecommendationResponse(asset=asset, similarity_score=round(sim, 4))
        for asset, sim in results
    ]

@router.post("/{project_id}/slices/{slice_id}/swap")
def swap_slice_asset(project_id: str, slice_id: str, req: SwapAssetRequest):
    asset = db.get_asset(req.new_asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="New asset not found")

    db.update_timeline_slice(slice_id, {"asset_id": req.new_asset_id})
    return {"status": "swapped", "slice_id": slice_id, "new_asset_id": req.new_asset_id}

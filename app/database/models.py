from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class ProjectModel(BaseModel):
    id: str
    title: str
    narrative_text: str
    status: str = "created" # created, indexing, music_gen, aligning, solving, ready, rendering, completed, error
    error_message: Optional[str] = None
    config_override: Optional[Dict[str, Any]] = None
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())

class MediaAssetModel(BaseModel):
    id: str
    project_id: str
    file_path: str
    media_type: str # 'image' | 'video'
    capture_time: Optional[str] = None
    duration_sec: float = 0.0
    quality_score: float = 7.0 # 1.0 - 10.0
    relevance_score_daily: float = 0.0 # 0.0 - 1.0 (relevance to matched diary day)
    relevance_score_overall: float = 0.0 # 0.0 - 1.0 (relevance to overall travel narrative)
    caption: str = ""
    tags: List[str] = Field(default_factory=list)
    embedding: Optional[List[float]] = None # 768-dim float vector (SigLIP 2)
    is_active: bool = True
    is_indexed: bool = False
    indexed_by_model: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None

class VideoSegmentModel(BaseModel):
    id: str
    asset_id: str
    start_time: float
    end_time: float
    motion_score: float = 0.5 # Composite score S = 0.7 S_rel + 0.3 S_aes
    relevance_score: float = 0.0 # Visual relevance to travel log
    best_shot_start: float = 0.0 # Best n-sec shot start timestamp
    best_shot_end: float = 0.0 # Best n-sec shot end timestamp
    description: str = ""
    embedding: Optional[List[float]] = None
    frame_scores: Optional[str] = None # JSON string of per-second [{t, s_rel, s_aes, s_comp}]

class AlignedWordModel(BaseModel):
    word: str
    start: float
    end: float
    snapped_start: float
    snapped_end: float
    beat_index: Optional[int] = None

class AudioTrackModel(BaseModel):
    id: str
    project_id: str
    master_path: str
    vocal_stem_path: Optional[str] = None
    accompaniment_stem_path: Optional[str] = None
    prompt: str = ""
    lyrics: str = ""
    is_instrumental: bool = False
    bpm: float = 120.0
    beat_grid: List[float] = Field(default_factory=list)
    downbeats: List[float] = Field(default_factory=list)
    aligned_lyrics: List[AlignedWordModel] = Field(default_factory=list)

class TimelineSliceModel(BaseModel):
    id: str
    project_id: str
    audio_track_id: str
    asset_id: str
    video_segment_id: Optional[str] = None
    start_beat: int
    beat_count: int
    timeline_start_sec: float
    timeline_end_sec: float
    clip_order: int
    bg_mode: str = "blurred_fill" # "blurred_fill", "black_bars", "ken_burns_zoom"
    enable_ken_burns: bool = False
    asset: Optional[MediaAssetModel] = None

class ProjectDetailResponse(BaseModel):
    project: ProjectModel
    assets: List[MediaAssetModel]
    audio_track: Optional[AudioTrackModel] = None
    timeline_slices: List[TimelineSliceModel]
    rendered_video_url: Optional[str] = None

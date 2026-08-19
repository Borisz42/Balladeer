import sqlite3
import json
import logging
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple
import numpy as np

from app.core.config import get_settings
from app.database.models import (
    ProjectModel,
    MediaAssetModel,
    VideoSegmentModel,
    AudioTrackModel,
    TimelineSliceModel,
    AlignedWordModel
)

logger = logging.getLogger(__name__)

def vector_to_blob(vec: List[float]) -> bytes:
    """Converts a float list into a 32-bit float byte blob."""
    return np.array(vec, dtype=np.float32).tobytes()

def blob_to_vector(blob: Optional[bytes]) -> Optional[List[float]]:
    """Converts a byte blob back into a float list."""
    if not blob:
        return None
    return np.frombuffer(blob, dtype=np.float32).tolist()

class Database:
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or get_settings().db_path
        self._init_db()

    def get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    def _init_db(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self.get_connection() as conn:
            conn.executescript("""
            CREATE TABLE IF NOT EXISTS projects (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                narrative_text TEXT NOT NULL,
                status TEXT NOT NULL,
                error_message TEXT,
                config_override TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS media_assets (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                file_path TEXT NOT NULL,
                media_type TEXT CHECK(media_type IN ('image', 'video')),
                capture_time TIMESTAMP,
                duration_sec REAL DEFAULT 0.0,
                quality_score REAL DEFAULT 7.0,
                relevance_score_daily REAL DEFAULT 0.0,
                relevance_score_overall REAL DEFAULT 0.0,
                caption TEXT,
                tags TEXT,
                embedding BLOB,
                is_active INTEGER DEFAULT 1,
                is_indexed INTEGER DEFAULT 0,
                indexed_by_model TEXT,
                width INTEGER,
                height INTEGER
            );

            CREATE TABLE IF NOT EXISTS video_segments (
                id TEXT PRIMARY KEY,
                asset_id TEXT NOT NULL REFERENCES media_assets(id) ON DELETE CASCADE,
                start_time REAL NOT NULL,
                end_time REAL NOT NULL,
                motion_score REAL DEFAULT 0.5,
                relevance_score REAL DEFAULT 0.0,
                best_shot_start REAL DEFAULT 0.0,
                best_shot_end REAL DEFAULT 0.0,
                description TEXT,
                embedding BLOB,
                frame_scores TEXT
            );

            CREATE TABLE IF NOT EXISTS audio_tracks (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                master_path TEXT NOT NULL,
                vocal_stem_path TEXT,
                accompaniment_stem_path TEXT,
                prompt TEXT,
                lyrics TEXT,
                is_instrumental INTEGER DEFAULT 0,
                bpm REAL DEFAULT 120.0,
                beat_grid TEXT,
                downbeats TEXT,
                aligned_lyrics TEXT
            );

            CREATE TABLE IF NOT EXISTS timeline_slices (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                audio_track_id TEXT NOT NULL REFERENCES audio_tracks(id) ON DELETE CASCADE,
                asset_id TEXT NOT NULL REFERENCES media_assets(id) ON DELETE CASCADE,
                video_segment_id TEXT REFERENCES video_segments(id) ON DELETE SET NULL,
                start_beat INTEGER NOT NULL,
                beat_count INTEGER NOT NULL,
                timeline_start_sec REAL NOT NULL,
                timeline_end_sec REAL NOT NULL,
                clip_order INTEGER NOT NULL,
                bg_mode TEXT DEFAULT 'blurred_fill',
                enable_ken_burns INTEGER DEFAULT 0,
                custom_caption TEXT,
                audio_muted INTEGER DEFAULT 1,
                audio_volume REAL DEFAULT 1.0
            );
            """)

            # Migrations: Ensure columns exist if table was already created
            for mig in [
                "ALTER TABLE media_assets ADD COLUMN is_indexed INTEGER DEFAULT 0;",
                "ALTER TABLE media_assets ADD COLUMN indexed_by_model TEXT;",
                "ALTER TABLE media_assets ADD COLUMN relevance_score_daily REAL DEFAULT 0.0;",
                "ALTER TABLE media_assets ADD COLUMN relevance_score_overall REAL DEFAULT 0.0;",
                "ALTER TABLE video_segments ADD COLUMN relevance_score REAL DEFAULT 0.0;",
                "ALTER TABLE video_segments ADD COLUMN best_shot_start REAL DEFAULT 0.0;",
                "ALTER TABLE video_segments ADD COLUMN best_shot_end REAL DEFAULT 0.0;",
                "ALTER TABLE video_segments ADD COLUMN frame_scores TEXT;",
                "ALTER TABLE timeline_slices ADD COLUMN custom_caption TEXT;",
                "ALTER TABLE timeline_slices ADD COLUMN audio_muted INTEGER DEFAULT 1;",
                "ALTER TABLE timeline_slices ADD COLUMN audio_volume REAL DEFAULT 1.0;",
            ]:
                try:
                    conn.execute(mig)
                except Exception:
                    pass

    # Project Operations
    def create_project(self, project: ProjectModel) -> ProjectModel:
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO projects (id, title, narrative_text, status, error_message, config_override, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    project.id,
                    project.title,
                    project.narrative_text,
                    project.status,
                    project.error_message,
                    json.dumps(project.config_override) if project.config_override else None,
                    project.created_at
                )
            )
        return project

    def get_project(self, project_id: str) -> Optional[ProjectModel]:
        with self.get_connection() as conn:
            row = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
            if not row:
                return None
            return ProjectModel(
                id=row["id"],
                title=row["title"],
                narrative_text=row["narrative_text"],
                status=row["status"],
                error_message=row["error_message"],
                config_override=json.loads(row["config_override"]) if row["config_override"] else None,
                created_at=str(row["created_at"])
            )

    def list_projects(self) -> List[ProjectModel]:
        with self.get_connection() as conn:
            rows = conn.execute("SELECT * FROM projects ORDER BY created_at DESC").fetchall()
            return [
                ProjectModel(
                    id=row["id"],
                    title=row["title"],
                    narrative_text=row["narrative_text"],
                    status=row["status"],
                    error_message=row["error_message"],
                    config_override=json.loads(row["config_override"]) if row["config_override"] else None,
                    created_at=str(row["created_at"])
                )
                for row in rows
            ]

    def update_project_status(self, project_id: str, status: str, error_message: Optional[str] = None) -> None:
        with self.get_connection() as conn:
            conn.execute(
                "UPDATE projects SET status = ?, error_message = ? WHERE id = ?",
                (status, error_message, project_id)
            )

    def update_project(
        self,
        project_id: str,
        title: Optional[str] = None,
        narrative_text: Optional[str] = None,
        config_override: Optional[Dict[str, Any]] = None,
        status: Optional[str] = None,
        error_message: Optional[str] = None
    ) -> Optional[ProjectModel]:
        fields = []
        values = []
        if title is not None:
            fields.append("title = ?")
            values.append(title)
        if narrative_text is not None:
            fields.append("narrative_text = ?")
            values.append(narrative_text)
        if config_override is not None:
            fields.append("config_override = ?")
            values.append(json.dumps(config_override))
        if status is not None:
            fields.append("status = ?")
            values.append(status)
        if error_message is not None:
            fields.append("error_message = ?")
            values.append(error_message)

        if fields:
            values.append(project_id)
            with self.get_connection() as conn:
                conn.execute(f"UPDATE projects SET {', '.join(fields)} WHERE id = ?", tuple(values))

        return self.get_project(project_id)

    def delete_project(self, project_id: str) -> None:
        with self.get_connection() as conn:
            conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))

    def update_media_asset(
        self,
        asset_id: str,
        tags: Optional[List[str]] = None,
        caption: Optional[str] = None,
        quality_score: Optional[float] = None,
        relevance_score_daily: Optional[float] = None,
        relevance_score_overall: Optional[float] = None,
        is_active: Optional[bool] = None
    ) -> None:
        fields = []
        values = []
        if tags is not None:
            fields.append("tags = ?")
            values.append(json.dumps(tags))
        if caption is not None:
            fields.append("caption = ?")
            values.append(caption)
        if quality_score is not None:
            fields.append("quality_score = ?")
            values.append(quality_score)
        if relevance_score_daily is not None:
            fields.append("relevance_score_daily = ?")
            values.append(relevance_score_daily)
        if relevance_score_overall is not None:
            fields.append("relevance_score_overall = ?")
            values.append(relevance_score_overall)
        if is_active is not None:
            fields.append("is_active = ?")
            values.append(1 if is_active else 0)

        if fields:
            values.append(asset_id)
            with self.get_connection() as conn:
                conn.execute(f"UPDATE media_assets SET {', '.join(fields)} WHERE id = ?", tuple(values))

    # Media Asset Operations
    def add_media_asset(self, asset: MediaAssetModel) -> MediaAssetModel:
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO media_assets 
                (id, project_id, file_path, media_type, capture_time, duration_sec, quality_score, relevance_score_daily, relevance_score_overall, caption, tags, embedding, is_active, is_indexed, indexed_by_model, width, height)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    project_id=excluded.project_id,
                    file_path=excluded.file_path,
                    media_type=excluded.media_type,
                    capture_time=excluded.capture_time,
                    duration_sec=excluded.duration_sec,
                    quality_score=excluded.quality_score,
                    relevance_score_daily=excluded.relevance_score_daily,
                    relevance_score_overall=excluded.relevance_score_overall,
                    caption=excluded.caption,
                    tags=excluded.tags,
                    embedding=excluded.embedding,
                    is_active=excluded.is_active,
                    is_indexed=excluded.is_indexed,
                    indexed_by_model=excluded.indexed_by_model,
                    width=excluded.width,
                    height=excluded.height
                """,
                (
                    asset.id,
                    asset.project_id,
                    asset.file_path,
                    asset.media_type,
                    asset.capture_time,
                    asset.duration_sec,
                    asset.quality_score,
                    asset.relevance_score_daily,
                    asset.relevance_score_overall,
                    asset.caption,
                    json.dumps(asset.tags),
                    vector_to_blob(asset.embedding) if asset.embedding else None,
                    1 if asset.is_active else 0,
                    1 if asset.is_indexed else 0,
                    asset.indexed_by_model,
                    asset.width,
                    asset.height
                )
            )
        return asset

    def update_media_asset(self, asset_id: str, updates: Dict[str, Any]) -> Optional[MediaAssetModel]:
        asset = self.get_asset(asset_id)
        if not asset:
            return None

        for k, v in updates.items():
            if hasattr(asset, k):
                setattr(asset, k, v)

        return self.add_media_asset(asset)

    def get_project_assets(self, project_id: str) -> List[MediaAssetModel]:
        with self.get_connection() as conn:
            rows = conn.execute("SELECT * FROM media_assets WHERE project_id = ? ORDER BY capture_time ASC", (project_id,)).fetchall()
            return [
                MediaAssetModel(
                    id=row["id"],
                    project_id=row["project_id"],
                    file_path=row["file_path"],
                    media_type=row["media_type"],
                    capture_time=str(row["capture_time"]) if row["capture_time"] else None,
                    duration_sec=row["duration_sec"] or 0.0,
                    quality_score=row["quality_score"] if row["quality_score"] is not None else 7.0,
                    relevance_score_daily=row["relevance_score_daily"] or 0.0 if "relevance_score_daily" in row.keys() else 0.0,
                    relevance_score_overall=row["relevance_score_overall"] or 0.0 if "relevance_score_overall" in row.keys() else 0.0,
                    caption=row["caption"] or "",
                    tags=json.loads(row["tags"]) if row["tags"] else [],
                    embedding=blob_to_vector(row["embedding"]),
                    is_active=bool(row["is_active"]),
                    is_indexed=bool(row["is_indexed"]) if "is_indexed" in row.keys() else True,
                    indexed_by_model=row["indexed_by_model"] if "indexed_by_model" in row.keys() else None,
                    width=row["width"],
                    height=row["height"]
                )
                for row in rows
            ]

    def get_asset(self, asset_id: str) -> Optional[MediaAssetModel]:
        with self.get_connection() as conn:
            row = conn.execute("SELECT * FROM media_assets WHERE id = ?", (asset_id,)).fetchone()
            if not row:
                return None
            return MediaAssetModel(
                id=row["id"],
                project_id=row["project_id"],
                file_path=row["file_path"],
                media_type=row["media_type"],
                capture_time=str(row["capture_time"]) if row["capture_time"] else None,
                duration_sec=row["duration_sec"] or 0.0,
                quality_score=row["quality_score"] if row["quality_score"] is not None else 7.0,
                relevance_score_daily=row["relevance_score_daily"] or 0.0 if "relevance_score_daily" in row.keys() else 0.0,
                relevance_score_overall=row["relevance_score_overall"] or 0.0 if "relevance_score_overall" in row.keys() else 0.0,
                caption=row["caption"] or "",
                tags=json.loads(row["tags"]) if row["tags"] else [],
                embedding=blob_to_vector(row["embedding"]),
                is_active=bool(row["is_active"]),
                is_indexed=bool(row["is_indexed"]) if "is_indexed" in row.keys() else True,
                indexed_by_model=row["indexed_by_model"] if "indexed_by_model" in row.keys() else None,
                width=row["width"],
                height=row["height"]
            )

    # Video Segment Operations
    def save_video_segments(self, segments: List[VideoSegmentModel]) -> None:
        with self.get_connection() as conn:
            for s in segments:
                conn.execute(
                    """
                    INSERT INTO video_segments
                    (id, asset_id, start_time, end_time, motion_score, relevance_score, best_shot_start, best_shot_end, description, embedding, frame_scores)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        asset_id=excluded.asset_id,
                        start_time=excluded.start_time,
                        end_time=excluded.end_time,
                        motion_score=excluded.motion_score,
                        relevance_score=excluded.relevance_score,
                        best_shot_start=excluded.best_shot_start,
                        best_shot_end=excluded.best_shot_end,
                        description=excluded.description,
                        embedding=excluded.embedding,
                        frame_scores=excluded.frame_scores
                    """,
                    (
                        s.id,
                        s.asset_id,
                        s.start_time,
                        s.end_time,
                        s.motion_score,
                        s.relevance_score,
                        s.best_shot_start,
                        s.best_shot_end,
                        s.description,
                        vector_to_blob(s.embedding) if s.embedding else None,
                        s.frame_scores
                    )
                )

    def get_video_segments(self, asset_id: str) -> List[VideoSegmentModel]:
        with self.get_connection() as conn:
            rows = conn.execute("SELECT * FROM video_segments WHERE asset_id = ? ORDER BY start_time ASC", (asset_id,)).fetchall()
            return [
                VideoSegmentModel(
                    id=row["id"],
                    asset_id=row["asset_id"],
                    start_time=row["start_time"],
                    end_time=row["end_time"],
                    motion_score=row["motion_score"] if row["motion_score"] is not None else 0.5,
                    relevance_score=row["relevance_score"] or 0.0 if "relevance_score" in row.keys() else 0.0,
                    best_shot_start=row["best_shot_start"] or row["start_time"] if "best_shot_start" in row.keys() else row["start_time"],
                    best_shot_end=row["best_shot_end"] or row["end_time"] if "best_shot_end" in row.keys() else row["end_time"],
                    description=row["description"] or "",
                    embedding=blob_to_vector(row["embedding"]),
                    frame_scores=row["frame_scores"] if "frame_scores" in row.keys() else None
                )
                for row in rows
            ]

    # Audio Track Operations
    def save_audio_track(self, track: AudioTrackModel) -> AudioTrackModel:
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO audio_tracks
                (id, project_id, master_path, vocal_stem_path, accompaniment_stem_path, prompt, lyrics, is_instrumental, bpm, beat_grid, downbeats, aligned_lyrics)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    track.id,
                    track.project_id,
                    track.master_path,
                    track.vocal_stem_path,
                    track.accompaniment_stem_path,
                    track.prompt,
                    track.lyrics,
                    1 if track.is_instrumental else 0,
                    track.bpm,
                    json.dumps(track.beat_grid),
                    json.dumps(track.downbeats),
                    json.dumps([w.dict() for w in track.aligned_lyrics])
                )
            )
        return track

    def get_audio_track(self, project_id: str) -> Optional[AudioTrackModel]:
        with self.get_connection() as conn:
            row = conn.execute("SELECT * FROM audio_tracks WHERE project_id = ?", (project_id,)).fetchone()
            if not row:
                return None
            return AudioTrackModel(
                id=row["id"],
                project_id=row["project_id"],
                master_path=row["master_path"],
                vocal_stem_path=row["vocal_stem_path"],
                accompaniment_stem_path=row["accompaniment_stem_path"],
                prompt=row["prompt"] or "",
                lyrics=row["lyrics"] or "",
                is_instrumental=bool(row["is_instrumental"]),
                bpm=row["bpm"],
                beat_grid=json.loads(row["beat_grid"]) if row["beat_grid"] else [],
                downbeats=json.loads(row["downbeats"]) if row["downbeats"] else [],
                aligned_lyrics=[AlignedWordModel(**w) for w in json.loads(row["aligned_lyrics"])] if row["aligned_lyrics"] else []
            )

    # Timeline Slice Operations
    def save_timeline_slices(self, project_id: str, slices: List[TimelineSliceModel]) -> List[TimelineSliceModel]:
        with self.get_connection() as conn:
            conn.execute("DELETE FROM timeline_slices WHERE project_id = ?", (project_id,))
            for s in slices:
                conn.execute(
                    """
                    INSERT INTO timeline_slices
                    (id, project_id, audio_track_id, asset_id, video_segment_id, start_beat, beat_count, timeline_start_sec, timeline_end_sec, clip_order, bg_mode, enable_ken_burns, custom_caption, audio_muted, audio_volume)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        s.id,
                        s.project_id,
                        s.audio_track_id,
                        s.asset_id,
                        s.video_segment_id,
                        s.start_beat,
                        s.beat_count,
                        s.timeline_start_sec,
                        s.timeline_end_sec,
                        s.clip_order,
                        s.bg_mode,
                        1 if s.enable_ken_burns else 0,
                        s.custom_caption,
                        1 if s.audio_muted else 0,
                        s.audio_volume
                    )
                )
        return slices

    def get_timeline_slices(self, project_id: str) -> List[TimelineSliceModel]:
        with self.get_connection() as conn:
            rows = conn.execute(
                """
                SELECT ts.*, ma.file_path, ma.media_type, ma.caption, ma.quality_score, ma.width, ma.height
                FROM timeline_slices ts
                LEFT JOIN media_assets ma ON ts.asset_id = ma.id
                WHERE ts.project_id = ?
                ORDER BY ts.clip_order ASC
                """,
                (project_id,)
            ).fetchall()

            slices = []
            for r in rows:
                asset = None
                if r["file_path"]:
                    asset = MediaAssetModel(
                        id=r["asset_id"],
                        project_id=r["project_id"],
                        file_path=r["file_path"],
                        media_type=r["media_type"],
                        quality_score=r["quality_score"] or 7.0,
                        caption=r["caption"] or "",
                        width=r["width"],
                        height=r["height"]
                    )
                slices.append(
                    TimelineSliceModel(
                        id=r["id"],
                        project_id=r["project_id"],
                        audio_track_id=r["audio_track_id"],
                        asset_id=r["asset_id"],
                        video_segment_id=r["video_segment_id"],
                        start_beat=r["start_beat"],
                        beat_count=r["beat_count"],
                        timeline_start_sec=r["timeline_start_sec"],
                        timeline_end_sec=r["timeline_end_sec"],
                        clip_order=r["clip_order"],
                        bg_mode=r["bg_mode"] or "blurred_fill",
                        enable_ken_burns=bool(r["enable_ken_burns"]),
                        custom_caption=r["custom_caption"] if "custom_caption" in r.keys() else None,
                        audio_muted=bool(r["audio_muted"]) if "audio_muted" in r.keys() and r["audio_muted"] is not None else True,
                        audio_volume=r["audio_volume"] if "audio_volume" in r.keys() and r["audio_volume"] is not None else 1.0,
                        asset=asset
                    )
                )
            return slices

    def update_timeline_slice(self, slice_id: str, updates: Dict[str, Any]) -> Optional[TimelineSliceModel]:
        with self.get_connection() as conn:
            row = conn.execute("SELECT * FROM timeline_slices WHERE id = ?", (slice_id,)).fetchone()
            if not row:
                return None
            
            project_id = row["project_id"]
            set_clauses = []
            values = []
            for k, v in updates.items():
                set_clauses.append(f"{k} = ?")
                values.append(v)
            values.append(slice_id)

            conn.execute(f"UPDATE timeline_slices SET {', '.join(set_clauses)} WHERE id = ?", tuple(values))
            
            # Fetch updated slice
            updated_slices = self.get_timeline_slices(project_id)
            return next((s for s in updated_slices if s.id == slice_id), None)

    # Vector Search Operations
    def search_similar_assets(
        self,
        project_id: str,
        target_embedding: List[float],
        top_k: int = 5
    ) -> List[Tuple[MediaAssetModel, float]]:
        assets = self.get_project_assets(project_id)
        scored = []
        target_vec = np.array(target_embedding, dtype=np.float32)
        target_norm = np.linalg.norm(target_vec)
        normed_target = target_vec / target_norm if target_norm > 0 else target_vec

        for a in assets:
            if a.embedding:
                raw_emb = np.array(a.embedding, dtype=np.float32)
                emb_norm = np.linalg.norm(raw_emb)
                normed_emb = raw_emb / emb_norm if emb_norm > 0 else raw_emb
                cos_sim = float(np.dot(normed_target, normed_emb))
                dist = float(np.linalg.norm(target_vec - raw_emb))
                score = cos_sim - (0.0001 * dist)
                scored.append((a, score))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]

db = Database()

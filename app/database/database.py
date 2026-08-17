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
                caption TEXT,
                tags TEXT,
                embedding BLOB,
                is_active INTEGER DEFAULT 1,
                width INTEGER,
                height INTEGER
            );

            CREATE TABLE IF NOT EXISTS video_segments (
                id TEXT PRIMARY KEY,
                asset_id TEXT NOT NULL REFERENCES media_assets(id) ON DELETE CASCADE,
                start_time REAL NOT NULL,
                end_time REAL NOT NULL,
                motion_score REAL DEFAULT 0.5,
                description TEXT,
                embedding BLOB
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
                enable_ken_burns INTEGER DEFAULT 0
            );
            """)

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
                INSERT OR REPLACE INTO media_assets 
                (id, project_id, file_path, media_type, capture_time, duration_sec, quality_score, caption, tags, embedding, is_active, width, height)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    asset.id,
                    asset.project_id,
                    asset.file_path,
                    asset.media_type,
                    asset.capture_time,
                    asset.duration_sec,
                    asset.quality_score,
                    asset.caption,
                    json.dumps(asset.tags),
                    vector_to_blob(asset.embedding) if asset.embedding else None,
                    1 if asset.is_active else 0,
                    asset.width,
                    asset.height
                )
            )
        return asset

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
                    quality_score=row["quality_score"] or 7.0,
                    caption=row["caption"] or "",
                    tags=json.loads(row["tags"]) if row["tags"] else [],
                    embedding=blob_to_vector(row["embedding"]),
                    is_active=bool(row["is_active"]),
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
                quality_score=row["quality_score"] or 7.0,
                caption=row["caption"] or "",
                tags=json.loads(row["tags"]) if row["tags"] else [],
                embedding=blob_to_vector(row["embedding"]),
                is_active=bool(row["is_active"]),
                width=row["width"],
                height=row["height"]
            )

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
                    json.dumps([w.model_dump() for w in track.aligned_lyrics])
                )
            )
        return track

    def get_audio_track(self, project_id: str) -> Optional[AudioTrackModel]:
        with self.get_connection() as conn:
            row = conn.execute("SELECT * FROM audio_tracks WHERE project_id = ? ORDER BY rowid DESC LIMIT 1", (project_id,)).fetchone()
            if not row:
                return None
            aligned_raw = json.loads(row["aligned_lyrics"]) if row["aligned_lyrics"] else []
            return AudioTrackModel(
                id=row["id"],
                project_id=row["project_id"],
                master_path=row["master_path"],
                vocal_stem_path=row["vocal_stem_path"],
                accompaniment_stem_path=row["accompaniment_stem_path"],
                prompt=row["prompt"] or "",
                lyrics=row["lyrics"] or "",
                is_instrumental=bool(row["is_instrumental"]),
                bpm=row["bpm"] or 120.0,
                beat_grid=json.loads(row["beat_grid"]) if row["beat_grid"] else [],
                downbeats=json.loads(row["downbeats"]) if row["downbeats"] else [],
                aligned_lyrics=[AlignedWordModel(**w) for w in aligned_raw]
            )

    # Timeline Slices Operations
    def save_timeline_slices(self, project_id: str, slices: List[TimelineSliceModel]) -> None:
        with self.get_connection() as conn:
            conn.execute("DELETE FROM timeline_slices WHERE project_id = ?", (project_id,))
            for s in slices:
                conn.execute(
                    """
                    INSERT INTO timeline_slices
                    (id, project_id, audio_track_id, asset_id, video_segment_id, start_beat, beat_count, timeline_start_sec, timeline_end_sec, clip_order, bg_mode, enable_ken_burns)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                        1 if s.enable_ken_burns else 0
                    )
                )

    def get_timeline_slices(self, project_id: str) -> List[TimelineSliceModel]:
        with self.get_connection() as conn:
            rows = conn.execute(
                """
                SELECT ts.*, ma.file_path as asset_path, ma.media_type as asset_type, ma.caption as asset_caption, ma.quality_score as asset_quality
                FROM timeline_slices ts
                LEFT JOIN media_assets ma ON ts.asset_id = ma.id
                WHERE ts.project_id = ?
                ORDER BY ts.clip_order ASC
                """,
                (project_id,)
            ).fetchall()

            result = []
            for row in rows:
                asset_obj = None
                if row["asset_id"]:
                    asset_obj = MediaAssetModel(
                        id=row["asset_id"],
                        project_id=project_id,
                        file_path=row["asset_path"] or "",
                        media_type=row["asset_type"] or "image",
                        caption=row["asset_caption"] or "",
                        quality_score=row["asset_quality"] or 7.0
                    )

                result.append(
                    TimelineSliceModel(
                        id=row["id"],
                        project_id=row["project_id"],
                        audio_track_id=row["audio_track_id"],
                        asset_id=row["asset_id"],
                        video_segment_id=row["video_segment_id"],
                        start_beat=row["start_beat"],
                        beat_count=row["beat_count"],
                        timeline_start_sec=row["timeline_start_sec"],
                        timeline_end_sec=row["timeline_end_sec"],
                        clip_order=row["clip_order"],
                        bg_mode=row["bg_mode"] or "blurred_fill",
                        enable_ken_burns=bool(row["enable_ken_burns"]),
                        asset=asset_obj
                    )
                )
            return result

    def update_timeline_slice(self, slice_id: str, updates: Dict[str, Any]) -> None:
        if not updates:
            return
        fields = []
        values = []
        for k, v in updates.items():
            if k in ["asset_id", "bg_mode", "enable_ken_burns", "beat_count", "timeline_start_sec", "timeline_end_sec"]:
                fields.append(f"{k} = ?")
                values.append(1 if v is True else 0 if v is False else v)
        if not fields:
            return
        values.append(slice_id)
        with self.get_connection() as conn:
            conn.execute(f"UPDATE timeline_slices SET {', '.join(fields)} WHERE id = ?", tuple(values))

    # Vector Search
    def search_similar_assets(
        self,
        project_id: str,
        target_embedding: List[float],
        top_k: int = 5,
        exclude_asset_id: Optional[str] = None
    ) -> List[Tuple[MediaAssetModel, float]]:
        """
        Computes cosine similarity against media assets in the project and returns top_k results.
        """
        assets = self.get_project_assets(project_id)
        target = np.array(target_embedding, dtype=np.float32)
        norm_target = np.linalg.norm(target)
        if norm_target == 0:
            return []

        scored: List[Tuple[MediaAssetModel, float]] = []
        for asset in assets:
            if exclude_asset_id and asset.id == exclude_asset_id:
                continue
            if not asset.embedding:
                continue
            emb = np.array(asset.embedding, dtype=np.float32)
            norm_emb = np.linalg.norm(emb)
            if norm_emb == 0:
                continue
            sim = float(np.dot(target, emb) / (norm_target * norm_emb))
            scored.append((asset, sim))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]

db = Database()

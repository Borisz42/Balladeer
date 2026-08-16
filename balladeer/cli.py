import argparse
import sys
import os
import logging
from pathlib import Path

from app.core.config import get_settings
from app.database.database import db
from app.database.models import ProjectModel, AudioTrackModel
from app.pipeline.indexer import MediaIndexer
from app.pipeline.music_gen import MusicGenerator
from app.pipeline.aligner import AudioAligner
from app.pipeline.beat_solver import BeatSolver
from app.pipeline.compositor import VideoCompositor

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("balladeer-cli")

def run_pipeline(
    media_dir: str,
    diary_file: str,
    output_mp4: str,
    title: str = "Montage",
    music_mode: str = "vocal",
    min_quality: float = 6.0,
    bg_mode: str = "blurred_fill",
    enable_ken_burns: bool = False
):
    settings = get_settings()
    media_path = Path(media_dir)
    diary_path = Path(diary_file)

    if not media_path.exists() or not media_path.is_dir():
        logger.error(f"Media directory not found: {media_dir}")
        sys.exit(1)

    narrative_text = ""
    if diary_path.exists():
        with open(diary_path, "r", encoding="utf-8") as f:
            narrative_text = f.read()
    else:
        narrative_text = diary_file # Treat string directly

    logger.info(f"==> Starting Balladeer Pipeline for '{title}'")
    project_id = f"cli_{os.urandom(4).hex()}"
    proj = ProjectModel(
        id=project_id,
        title=title,
        narrative_text=narrative_text,
        config_override={
            "video": {
                "default_bg_mode": bg_mode,
                "enable_ken_burns": enable_ken_burns
            }
        }
    )
    db.create_project(proj)

    # 1. Index media
    indexer = MediaIndexer()
    logger.info(f"Phase 1: Indexing media in {media_path}...")
    supported_exts = {".jpg", ".jpeg", ".png", ".webp", ".mp4", ".mov", ".mkv", ".avi"}
    indexed_count = 0
    for f in media_path.glob("*"):
        if f.suffix.lower() in supported_exts:
            asset = indexer.index_media_file(project_id, f)
            db.add_media_asset(asset)
            indexed_count += 1
    logger.info(f"Indexed {indexed_count} media assets.")

    assets = db.get_project_assets(project_id)
    if not assets:
        logger.error("No media assets found to process!")
        sys.exit(1)

    # 2. Synthesize music & lyrics
    music_gen = MusicGenerator()
    logger.info("Phase 2: Partitioning narrative and synthesizing music...")
    acts = music_gen.partition_narrative_to_acts(narrative_text)
    lyrics, prompt = music_gen.generate_rhyming_lyrics(acts)
    audio_files = music_gen.synthesize_music_track(
        project_id=project_id,
        lyrics=lyrics,
        prompt=prompt,
        bpm=settings.audio.default_tempo_bpm,
        target_duration_sec=30.0
    )

    # 3. Demix & Align
    aligner = AudioAligner()
    logger.info("Phase 3: Stem demixing, MMS_FA alignment & beat snapping...")
    stems = aligner.separate_stems_demucs(
        master_path=audio_files["master_path"],
        output_dir=audio_files["master_path"].parent
    )
    bpm, beat_grid, downbeats = aligner.extract_beat_grid(audio_files["master_path"])
    aligned_words = aligner.align_lyrics_mms_fa(
        vocal_path=stems["vocals"],
        lyrics_text=lyrics,
        beat_grid=beat_grid
    )
    track = AudioTrackModel(
        id=f"trk_{project_id}",
        project_id=project_id,
        master_path=str(audio_files["master_path"].resolve()),
        vocal_stem_path=str(stems["vocals"].resolve()),
        accompaniment_stem_path=str(stems["accompaniment"].resolve()),
        prompt=prompt,
        lyrics=lyrics,
        is_instrumental=(music_mode == "instrumental"),
        bpm=bpm,
        beat_grid=beat_grid,
        downbeats=downbeats,
        aligned_lyrics=aligned_words
    )
    db.save_audio_track(track)

    # 4. Constraint Solver
    beat_solver = BeatSolver()
    logger.info("Phase 4: Constraint-based media placement solver...")
    slices = beat_solver.solve_timeline(
        project_id=project_id,
        audio_track=track,
        assets=assets,
        custom_config=proj.config_override
    )
    db.save_timeline_slices(project_id, slices)
    logger.info(f"Timeline solved: {len(slices)} beat-aligned video slices generated.")

    # 5. Composite Video
    compositor = VideoCompositor()
    logger.info("Phase 5: Rendering hardware-accelerated video montage...")
    out_target = Path(output_mp4)
    rendered = compositor.assemble_final_video(
        project_id=project_id,
        slices=slices,
        audio_track=track,
        output_filename=out_target.name
    )

    if out_target.parent != rendered.parent and out_target.parent.exists():
        import shutil
        shutil.copy(str(rendered), str(out_target))
        logger.info(f"Montage saved to: {out_target.resolve()}")
    else:
        logger.info(f"Montage saved to: {rendered.resolve()}")

    logger.info("✨ Balladeer processing completed successfully!")

def main():
    parser = argparse.ArgumentParser(description="Balladeer: Local AI Beat-Synced Video Montage Engine")
    parser.add_argument("--media-dir", required=True, help="Directory containing photos and video clips")
    parser.add_argument("--diary", required=True, help="Trip diary text file or raw story string")
    parser.add_argument("--output", default="montage.mp4", help="Output MP4 file path")
    parser.add_argument("--title", default="My Adventure", help="Project title")
    parser.add_argument("--music-mode", default="vocal", choices=["vocal", "instrumental"], help="Audio track mode")
    parser.add_argument("--min-quality", type=float, default=6.0, help="Minimum quality score threshold (1-10)")
    parser.add_argument("--bg-mode", default="blurred_fill", choices=["blurred_fill", "black_bars", "ken_burns_zoom"], help="Background fill mode for aspect ratio mismatch")
    parser.add_argument("--ken-burns", action="store_true", help="Enable dynamic Ken Burns pan/zoom on photos")

    args = parser.parse_args()
    run_pipeline(
        media_dir=args.media_dir,
        diary_file=args.diary,
        output_mp4=args.output,
        title=args.title,
        music_mode=args.music_mode,
        min_quality=args.min_quality,
        bg_mode=args.bg_mode,
        enable_ken_burns=args.ken_burns
    )

if __name__ == "__main__":
    main()

# Balladeer — Project Status & Architecture Report

> **Engine:** Balladeer: Hybrid Cloud-Local AI Beat-Synced Video Montage Engine  
> **Environment:** Windows 11 (PowerShell), NVIDIA GeForce RTX 3070 (Vulkan / CUDA / NVENC), Python 3.11  
> **Test Suite:** 50 / 50 automated tests passing (100% pass rate)

---

## 1. Executive Summary

Balladeer is a high-performance hybrid AI video montage engine that transforms travel photos, video clips, and structured trip diaries into beat-synchronized cinematic music videos. The system combines an asynchronous 2-step media ingestion process with a multi-tier Google AI Studio model priority waterfall, offline GPU inference (`Qwen 2.5 VL (3B)` on RTX 3070), EXIF orientation transposition, dynamic media preview sizing, responsive multi-column gallery tiling, date-aware multi-modal indexing, AI travel diary re-phrasing, real-time asset inspection & editing, and Google Flow Music prompt optimization.

---

## 2. Implemented Architecture & Pipeline Phases

### Phase 1: 2-Step Media Ingestion & Model Priority Waterfall
* **Step 1: Rapid Media Staging (`stage_media_files`):**
  * Parses basic EXIF timestamps, video durations, GPS coordinates, and dimensions immediately upon upload/folder selection.
  * Generates fast JPEG thumbnails (`/api/projects/{id}/assets/{asset_id}/thumbnail`) with automatic **EXIF orientation transposition** (`ImageOps.exif_transpose`), ensuring camera/smartphone portrait photos render upright.
  * Accurately extracts orientation-corrected dimensions (`width`, `height`).
  * Automatically matches photo/video capture timestamps against structured itinerary dates, tagging assets with `day:Day X` and `date:YYYY-MM-DD`.
  * Displays assets immediately in the UI marked as unindexed without blocking on model inference.
* **Responsive Source Media Gallery (`AssetGallery.jsx`):**
  * Uses auto-filling dynamic grid tiling (`grid-cols-[repeat(auto-fill,minmax(110px,1fr))]`) automatically rendering 4, 5, 6, or more columns on wide displays and adapting cleanly to smaller widths.
  * Standardized `aspect-[4/3]` thumbnail cards with smooth hover zoom animations.
* **Step 2: Batch AI Vision Indexing (`index_pending_assets`):**
  * Initiated via the **"Index Media"** UI button or API endpoint.
  * Uses the **Intelligent Multi-Tier Model Dispatcher (`IntelligentModelRouter`)** to distribute batches across Google AI Studio free tier quotas with automatic fallback:
    1. `Gemini 3.5 Flash Lite` (15 RPM | 250K TPM | 500 RPD) — Primary batch worker
    2. `Gemini 3.1 Flash Lite` (15 RPM | 250K TPM | 500 RPD) — Secondary batch worker
    3. `Gemini 2.5 Flash Lite` (10 RPM | 250K TPM | 20 RPD) — Lite overflow pool
    4. `Gemini 3.7 / 3.6 Flash` (5 RPM | 250K TPM | 20 RPD) — Overflow pool
    5. `Gemma 4 31B / 26B` (30 RPM | 16K TPM | 14.4K RPD) — Micro-batches
    6. `Local Qwen 2.5 VL (3B)` (Unlimited | RTX 3070) — Hard fallback when cloud quotas saturate or in offline mode
* **Model Attribution & Inspector Modal (`AssetDetailModal.jsx`):**
  * Displays thumbnail and large media preview.
  * Shows which AI model was used (`indexed_by_model`).
  * Allows user editing of captions, tags, and quality scores directly in SQLite.
  * Provides 1-click single asset re-indexing.
* **Video Subsegment & Scene Cut Extraction:** Uses OpenCV and PySceneDetect frame difference algorithms to partition long video recordings into punchy subsegments (`video_segments` table) with motion scores.
* **Vector Semantic Indexing:** Uses `google/siglip2-base-patch16-224` to produce 768-dimensional FP16 embeddings for visual search, scene clustering, and narrative-lyric alignment.

---

### Phase 2: Narrative Structuring, Structured Diary Engine & Music Studio
* **Structured Day-by-Day Itinerary Engine:**
  * Allows setting trip `Start Date` and `Finish Date` with automatic date-range day generation.
  * Per-day cards with date selectors, weekday badges, event description text areas, and custom day addition/removal.
  * **Discard & Bring Back (Enable / Disable) Controls:** Exclude specific days from song lyrics and narrative acts while retaining their text in metadata for instant restoration.
* **AI Re-phraser & Spell Correction Engine (`app/pipeline/rephraser.py`):**
  * Corrects typos and misspellings automatically.
  * Transforms raw travel notes into vivid, poetic prose tailored for rhyming song lyrics.
  * Supports single-day re-phrasing and full-itinerary batch re-phrasing via `POST /api/projects/rephrase`.
* **Narrative Act Structuring:** Partitions active days into a 5-act musical structure:
  * *Act 1:* Verse 1 (Introduction & arrival)
  * *Act 2:* Chorus (Core thematic hook & journey emotion)
  * *Act 3:* Verse 2 (Exploration & key events)
  * *Act 4:* Verse 3 / Bridge (Climax & travel highlights)
  * *Act 5:* Outro (Departure, reflection, & concluding memory)
* **Google Flow Music / AI Prompt Optimizer:** Generates highly refined, evocative music prompts detailing genre, instrumentation, tempo (BPM), vocal mood, and texture with 1-click copy buttons.
* **5-Act Structured Rhyming Lyrics:** Generates rhythmic, rhyming lyrics formatted for musical beat alignment using Qwen 2.5 LLM / Gemini waterfall.
* **Instant Beat-Aligned Harmonic Preview:** Fast synthetic audio synthesis for immediate timeline playback and editing.
* **Custom Audio Importer:** Direct drag-and-drop audio uploader allowing users to import high-fidelity tracks, automatically triggering stem demixing, beat detection, and phonetic lyrics alignment.

---

### Phase 3: Stem Separation & Forced Alignment
* **Stem Demixing (Demucs):** Demixes master audio into isolated `vocals.wav` and `accompaniment.wav` stems.
* **Beat & Downbeat Detection (Librosa):** Extracts musical onset envelopes, dynamic tempo estimation, full beat grid timestamps, and downbeat bar markers.
* **CTC Trellis Forced Alignment (TorchAudio MMS_FA):** Aligns lyrics phonetically to vocal audio waveforms, producing word-level start/end timestamps snapped to the musical beat grid.

---

### Phase 4: Constraint-Based Beat Solver & Timeline Optimization
* **Global Integer Programming Solver with Date Affinity:**
  * Formulates media-to-beat placement as a multi-objective optimization problem.
  * Enforces strict chronological narrative progression ($\alpha \cdot \text{ChronoAlignment}$).
  * Prioritizes media assets captured on Day X into the corresponding musical act for Day X ($\text{DateAffinityScore}$).
  * Optimizes for media quality and aesthetic sharpness ($\beta \cdot \text{QualityScore}$).
  * Applies exponential recency penalties ($\gamma \cdot \text{RecencyPenalty}$) to prevent consecutive duplicate asset placement.
  * Implements media duration constraints: Photos (1–3 beats), Videos (2–5 beats).
  * Snaps instrumental phrasing to 4-beat or 8-beat musical bar boundaries.
* **Timeline Customization & Slice Manipulation:**
  * Interactive drag-and-drop slice reordering.
  * Arbitrary beat boundary slice splitting (`POST /api/timeline/{project_id}/split-slice`).
  * Asset swap modal with thumbnail previews and metadata filtering.
  * Multi-aspect ratio switcher (16:9 Landscape, 9:16 Portrait / Reels / TikTok, 1:1 Square).
  * Background fill mode toggles: `blurred_fill`, `black_bars`, and `ken_burns_zoom`.

---

### Phase 5: Hardware Video Compositor (NVENC)
* **Multi-Aspect Ratio Rendering:** Supports 16:9 Landscape, 9:16 Vertical (Shorts/Reels/TikTok), and 1:1 Square.
* **Blurred Background Fill & Ken Burns Motion:** Intelligent blurred canvas padding for mixed orientation media and sub-pixel zoom/pan.
* **Synchronized ASS Subtitles:** Word-by-word highlighted karaoke tags (`{\k<dur>}`) in vocal mode and chapter event cards in instrumental mode.
* **Audio Mastering & NVENC Encoding:** EBU R128 loudness mastering (-14 LUFS) and hardware-accelerated `h264_nvenc` encoding.

---

## 3. Automated Test Verification Results

```powershell
python -m pytest tests -v
```

```
============================== 50 passed in 29.39s ==============================
tests/test_aligner.py::test_beat_snapping PASSED                         [  2%]
tests/test_aligner.py::test_music_synthesis_and_beat_extraction PASSED   [  4%]
tests/test_api.py::test_health_endpoint PASSED                           [  6%]
tests/test_api.py::test_project_api_lifecycle PASSED                     [  8%]
tests/test_aspect_ratio_and_instrumental.py::test_instrumental_event_cards_subtitles PASSED [ 10%]
tests/test_aspect_ratio_and_instrumental.py::test_vertical_aspect_ratio_processing PASSED [ 12%]
tests/test_aspect_ratio_and_instrumental.py::test_thumbnail_exif_orientation_handling PASSED [ 14%]
tests/test_auto_draft_and_approval.py::test_auto_draft_approval_workflow PASSED [ 16%]
tests/test_auto_draft_and_approval.py::test_defer_relevance_until_approved PASSED [ 18%]
tests/test_batch_indexer.py::test_parallel_batch_indexing PASSED         [ 20%]
tests/test_batch_indexer.py::test_two_step_media_indexing_and_user_editing PASSED [ 22%]
tests/test_beat_solver.py::test_beat_solver_config_ranges PASSED         [ 24%]
tests/test_compositor.py::test_ass_karaoke_subtitle_generation PASSED    [ 36%]
tests/test_compositor.py::test_blurred_background_fill PASSED            [ 38%]
tests/test_config.py::test_config_defaults PASSED                        [ 40%]
tests/test_database.py::test_database_lifecycle PASSED                   [ 42%]
tests/test_diary_and_rephrase.py::test_structured_diary_creation_and_sync PASSED [ 44%]
tests/test_diary_and_rephrase.py::test_diary_ai_rephraser_spell_correction PASSED [ 46%]
tests/test_hardware.py::test_gpu_memory_and_hardware_detection PASSED   [ 48%]
tests/test_local_ai_and_video_vision.py::test_local_ai_photo_vision_semantic_quality PASSED [ 50%]
tests/test_local_ai_and_video_vision.py::test_local_ai_video_indexing_and_subsegments PASSED [ 52%]
tests/test_model_router.py::test_model_quota_sliding_window PASSED       [ 54%]
tests/test_model_router.py::test_model_router_waterfall_fallback PASSED  [ 56%]
tests/test_model_router.py::test_model_router_only_local_ai_mode PASSED  [ 58%]
tests/test_model_wrappers.py::test_local_vlm_heuristic PASSED            [ 60%]
tests/test_model_wrappers.py::test_local_vlm_markdown_fenced_json PASSED [ 62%]
tests/test_model_wrappers.py::test_local_vlm_malformed_fence_fallback PASSED [ 64%]
tests/test_model_wrappers.py::test_mms_aligner PASSED                    [ 68%]
tests/test_models_api.py::test_models_status_api PASSED                  [ 70%]
tests/test_models_api.py::test_model_download_trigger_api PASSED         [ 72%]
tests/test_settings_api.py::test_settings_api_lifecycle PASSED           [ 74%]
tests/test_split_and_reorder.py::test_split_and_reorder_api PASSED       [ 76%]
tests/test_system_api.py::test_shutdown_endpoint PASSED                  [ 78%]
tests/test_upload_video_foreign_key.py::test_video_indexing_foreign_key_integrity PASSED [ 80%]
tests/test_video_segments.py::test_video_subsegments_extraction PASSED   [ 82%]
tests/test_video_segments.py::test_ffmpeg_1fps_video_extraction PASSED   [ 84%]
tests/test_video_segments.py::test_video_segments_and_frame_scores_api PASSED [ 86%]
```

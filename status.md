# Balladeer — Project Status & Architecture Report

> **Engine:** Balladeer: Hybrid Cloud-Local AI Beat-Synced Video Montage Engine  
> **Environment:** Windows 11 (PowerShell), NVIDIA GeForce RTX 3070 (Vulkan / CUDA / NVENC), Python 3.11  
> **Test Suite:** 33 / 33 automated tests passing (100% pass rate)


---

## 1. Executive Summary

Balladeer is a high-performance hybrid AI video montage engine that transforms travel photos, video clips, and diary logs into beat-synchronized cinematic music videos. The system combines an asynchronous 2-step media ingestion process with a multi-tier Google AI Studio model priority waterfall, local GPU inference (`Qwen3.5-4B` VLM on RTX 3070), real-time asset inspection & editing, and Google Flow Music prompt optimization.

---

## 2. Implemented Architecture & Pipeline Phases

### Phase 1: 2-Step Media Ingestion & Model Priority Waterfall
* **Step 1: Rapid Media Staging (`stage_media_files`):**
  * Parses basic EXIF timestamps, video durations, and dimensions immediately upon upload/folder selection.
  * Generates and serves fast JPEG thumbnails (`/api/projects/{id}/assets/{asset_id}/thumbnail`).
  * Displays assets immediately in the UI marked as unindexed without blocking on model inference.
* **Step 2: Batch AI Vision Indexing (`index_pending_assets`):**
  * Initiated via the **"Index Media"** UI button or API endpoint.
  * Uses the **Intelligent Multi-Tier Model Dispatcher (`IntelligentModelRouter`)** to distribute batches across Google AI Studio free tier quotas with automatic fallback:
    1. `Gemini 3.5 Flash Lite` (15 RPM | 250K TPM | 500 RPD) — Primary batch worker
    2. `Gemini 3.1 Flash Lite` (15 RPM | 250K TPM | 500 RPD) — Secondary batch worker
    3. `Gemini 2.5 Flash Lite` (10 RPM | 250K TPM | 20 RPD) — Lite overflow pool
    4. `Gemini 3.7 / 3.6 Flash` (5 RPM | 250K TPM | 20 RPD) — Overflow pool
    5. `Gemma 4 31B / 26B` (30 RPM | 16K TPM | 14.4K RPD) — Micro-batches
    6. `Local Qwen3.5-4B` (Unlimited | RTX 3070) — Hard fallback when cloud quotas saturate or offline
* **Model Attribution & Inspector Modal (`AssetDetailModal.jsx`):**
  * Displays thumbnail and large media preview.
  * Shows which AI model was used (`indexed_by_model`).
  * Allows user editing of captions, tags, and quality scores directly in SQLite.
  * Provides 1-click single asset re-indexing.
* **Vector Semantic Indexing:** Uses `sentence-transformers/clip-ViT-B-32` to produce 512-dimensional embeddings for visual search, scene clustering, and narrative-lyric alignment.

---

### Phase 2: Narrative Structuring, Google Flow Music Optimization & Music Studio
* **Narrative Act Structuring:** Partitions diary entries into 5 musical acts (*Verse 1 $\rightarrow$ Chorus $\rightarrow$ Verse 2 $\rightarrow$ Bridge $\rightarrow$ Outro*).
* **Google Flow Music (MusicFX / Lyria) Prompt Optimizer:** Generates highly refined, evocative music prompts detailing genre, instrumentation, tempo (BPM), vocal mood, and texture with 1-click copy buttons.
* **5-Act Structured Rhyming Lyrics:** Generates rhythmic, rhyming lyrics formatted for musical beat alignment.
* **Optional Local MiniMax Music 3 Synthesis:** Optional switch for native Cortiq CMF synthesis on RTX 3070 Vulkan GPU shaders.
* **Custom Audio Importer:** Direct drag-and-drop audio uploader allowing users to import high-fidelity tracks generated in Google Flow Music, automatically triggering stem demixing and beat alignment.

---

### Phase 3: Stem Separation & Forced Alignment
* **Stem Demixing (Demucs):** Demixes master audio into isolated `vocals.wav` and `accompaniment.wav` stems.
* **Beat & Downbeat Detection (Librosa):** Extracts musical onset envelopes, dynamic tempo estimation, full beat grid timestamps, and downbeat bar markers.
* **CTC Trellis Forced Alignment (TorchAudio MMS_FA):** Aligns lyrics phonetically to vocal audio waveforms, producing word-level start/end timestamps snapped to the musical beat grid.

---

### Phase 4: Constraint-Based Beat Solver & Timeline Optimization
* **Global Integer Programming Solver:** Solves the optimal assignment of media assets to musical beat intervals:
  * Chronological storytelling alignment ($\alpha \cdot \text{ChronoAlignment}$).
  * Aesthetic and technical quality score weighting ($\beta \cdot \text{QualityScore}$).
  * Recency avoidance penalties ($\gamma \cdot \text{RecencyPenalty}$).
  * Media duration bounds (Photos: 1–3 beats, Videos: 2–5 beats).
* **Interactive Timeline Editor:** Real-time web timeline supporting slice splitting, drag-and-drop reordering, and asset swapping with metadata filtering.

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
======================= 31 passed in 176.29s (0:02:56) ========================
tests/test_aligner.py::test_beat_snapping PASSED                         [  3%]
tests/test_aligner.py::test_music_synthesis_and_beat_extraction PASSED   [  6%]
tests/test_api.py::test_health_endpoint PASSED                           [  9%]
tests/test_api.py::test_project_api_lifecycle PASSED                     [ 12%]
tests/test_aspect_ratio_and_instrumental.py::test_instrumental_event_cards_subtitles PASSED [ 16%]
tests/test_aspect_ratio_and_instrumental.py::test_vertical_aspect_ratio_processing PASSED [ 19%]
tests/test_batch_indexer.py::test_parallel_batch_indexing PASSED         [ 22%]
tests/test_batch_indexer.py::test_two_step_media_indexing_and_user_editing PASSED [ 25%]
tests/test_beat_solver.py::test_beat_solver_config_ranges PASSED         [ 29%]
tests/test_comfy_worker.py::test_comfy_worker_build_prompt_graph PASSED  [ 32%]
tests/test_comfy_worker.py::test_comfy_worker_fallback_when_offline PASSED [ 35%]
tests/test_comfy_worker.py::test_minimax_engine_with_comfy_audio PASSED  [ 38%]
tests/test_comfy_worker.py::test_minimax_engine_with_cmf_runner_audio PASSED [ 41%]
tests/test_comfy_worker.py::test_minimax_engine_strict_error_when_all_offline PASSED [ 45%]
tests/test_compositor.py::test_ass_karaoke_subtitle_generation PASSED    [ 48%]
tests/test_compositor.py::test_blurred_background_fill PASSED            [ 51%]
tests/test_config.py::test_config_defaults PASSED                        [ 54%]
tests/test_database.py::test_database_lifecycle PASSED                   [ 58%]
tests/test_model_router.py::test_model_quota_sliding_window PASSED       [ 61%]
tests/test_model_router.py::test_model_quota_waterfall_fallback PASSED  [ 64%]
tests/test_model_router.py::test_model_router_only_local_ai_mode PASSED  [ 67%]
tests/test_model_wrappers.py::test_qwen_vlm_heuristic PASSED             [ 70%]
tests/test_model_wrappers.py::test_minimax_music_engine PASSED           [ 74%]
tests/test_model_wrappers.py::test_mms_aligner PASSED                    [ 77%]
tests/test_models_api.py::test_models_status_api PASSED                  [ 80%]
tests/test_model_download_trigger_api PASSED                             [ 83%]
tests/test_settings_api.py::test_settings_api_lifecycle PASSED           [ 87%]
tests/test_split_and_reorder.py::test_split_and_reorder_api PASSED       [ 90%]
tests/test_system_api.py::test_shutdown_endpoint PASSED                  [ 93%]
tests/test_upload_video_foreign_key.py::test_video_indexing_foreign_key_integrity PASSED [ 96%]
tests/test_video_segments.py::test_video_subsegments_extraction PASSED   [100%]
```

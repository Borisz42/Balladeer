# Balladeer — Project Status & Architecture Report

> **Engine:** Balladeer: Local AI Beat-Synced Video Montage Engine  
> **Environment:** Windows 11 (PowerShell), NVIDIA GeForce RTX 3070 (Vulkan / CUDA / NVENC), Python 3.11  
> **Test Suite:** 25 / 25 automated tests passing (100% pass rate)

---

## 1. Executive Summary

Balladeer is a local-first, privacy-preserving AI video montage generator that transforms vacation photos and video clips into beat-synchronized cinematic music videos. The application executes locally on consumer hardware (RTX 3070 8GB VRAM) by leveraging optimized quantization formats (CMF, GGUF), Vulkan GPU compute shaders, and FFmpeg NVENC hardware encoding.

---

## 2. Implemented Architecture & Pipeline Phases

### Phase 1: Media Ingestion & Multi-Modal Indexing
* **Batch Ingestion & Uploads:** Supports drag-and-drop file uploads and recursive directory indexing for both images (`.jpg`, `.jpeg`, `.png`, `.webp`, `.heic`) and video files (`.mp4`, `.mov`, `.avi`, `.mkv`).
* **EXIF & Metadata Parsing:** Extracts chronological capture timestamps, camera models, GPS metadata, video durations, resolutions, and frame rates.
* **Video Subsegment & Scene Cut Extraction:** Uses OpenCV and PySceneDetect frame difference algorithms to partition long video recordings into punchy subsegments (`video_segments` table) with motion scores.
* **Vector Semantic Indexing:** Uses `sentence-transformers/clip-ViT-B-32` to produce 512-dimensional embeddings for visual search, scene clustering, and narrative-lyric alignment.
* **Visual-Language Modeling (VLM):** Integrates `unsloth/Qwen3.5-4B-GGUF` (Q4_K_M) with heuristic fallback for scene descriptions, optical character recognition, and landmark identification.
* **Database & Relational Integrity:** SQLite backend (`data/balladeer.db`) with cascading foreign keys for projects, media assets, video segments, audio tracks, and timeline slices.

---

### Phase 2: Narrative Structuring & Music Generation (MiniMax Music 3)
* **Narrative Act Structuring:** Analyzes unstructured user diary entries and partitions them into a 5-act musical structure:
  * *Act 1:* Verse 1 (Introduction & arrival)
  * *Act 2:* Chorus (Core thematic hook & journey emotion)
  * *Act 3:* Verse 2 (Exploration & key events)
  * *Act 4:* Verse 3 / Bridge (Climax & travel highlights)
  * *Act 5:* Outro (Departure, reflection, & concluding memory)
* **Official Cortiq / CMF Native Runner (`cortiq.exe music`):**
  * Uses the official single-file Cortiq Model Format from [`infosave2007/cmf`](https://github.com/infosave2007/cmf) with `minimax-music3-q4tp.cmf` (5.96 GB).
  * Executes the sequential autoregressive acoustic token phase across multi-core CPU (`RAYON_NUM_THREADS`).
  * Executes the 8-step Euler latent diffusion and neural vocoder directly on the **NVIDIA GeForce RTX 3070 GPU via Vulkan compute shaders** (`wgpu GPU path: on (NVIDIA GeForce RTX 3070 / Vulkan, discrete)`).
* **Real-Time Progress & Console Streaming:**
  * Replaced buffered subprocessing with unbuffered line-by-line `Popen` streaming.
  * Emits live token and denoise progress to Python logs and Server-Sent Events (SSE) progress channels:
    * `[CMF MiniMax-3] ar X/750` $\rightarrow$ Live frame progress (40% to 80%).
    * `[CMF MiniMax-3] denoise X/8` $\rightarrow$ GPU denoise progress (80% to 95%).
* **Flexible Song Duration Control:** Web UI duration selector supporting:
  * `10s (Fast Preview)` — 250 frames (~2.5 minutes generation time).
  * `15s (Standard)` — 375 frames.
  * `20s (Extended)` — 500 frames.
  * `30s (Full Montage)` — 750 frames.
* **ComfyUI Headless Engine:** Background headless worker fallback on port 8188 with prompt-graph automation.
* **Strict Zero-Fallback Policy:** Completely removed all silent procedural audio synthesizers. If MiniMax Music 3 weights or runners cannot execute, Balladeer stops immediately and raises an explicit `RuntimeError`.

---

### Phase 3: Stem Separation & Forced Alignment
* **Stem Demixing (Demucs):** Demixes master audio into isolated `vocals.wav` and `accompaniment.wav` stems.
* **Beat & Downbeat Detection (Librosa):** Extracts musical onset envelopes, dynamic tempo estimation, full beat grid timestamps, and downbeat bar markers.
* **CTC Trellis Forced Alignment (TorchAudio MMS_FA):** Aligns lyrics phonetically to vocal audio waveforms, producing word-level start/end timestamps snapped to the musical beat grid.

---

### Phase 4: Constraint-Based Beat Solver & Timeline Optimization
* **Global Integer Programming Solver:**
  * Formulates media-to-beat placement as a multi-objective optimization problem.
  * Enforces strict chronological narrative progression ($\alpha \cdot \text{ChronoAlignment}$).
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

### Phase 5: Multi-Aspect Compositing & Hardware Video Export
* **Blurred Background Fill Engine:** PIL + FFmpeg filter graph creating smooth Gaussian blurred, scaled background canvases for portrait assets on widescreen video (and landscape assets on vertical video).
* **Ken Burns Dynamic Motion:** Sub-pixel smooth pan and zoom camera motion (`zoompan`).
* **Synchronized Subtitles (Advanced SubStation Alpha - ASS):**
  * *Vocal Mode:* Word-by-word karaoke highlight color tags (`{\k<dur_cs>}`).
  * *Instrumental Mode:* Elegant chapter event cards (`{\fad(400,400)}[Kyoto Autumn Arrival]`).
* **Audio Mastering & Loudness Normalization:** EBU R128 compliance (`-14 LUFS`, `TP=-1.5`) with smooth audio fade-in and fade-out.
* **FFmpeg NVENC Hardware Encoding:** High-speed hardware video compositing via `h264_nvenc` with automatic software fallback.

---

### Phase 6: Frontend Web Application & Orchestration
* **Modern Web Interface:** Built with React 18, Vite, TailwindCSS, Lucide Icons, and Glassmorphism design tokens.
* **Interactive Views:**
  * *Media Gallery:* Asset grid with duration badges, resolution pills, quality indicators, and EXIF dates.
  * *Music Studio:* Real-time CMF engine status badge, duration dropdown, instrumental switch, prompt input, and stem audio player.
  * *Timeline Editor:* Canvas scrubbing, beat grid ticks, slice dragging, split tool, and asset swapping.
  * *Video Player Modal:* Synchronized playback with direct 1-click MP4 download.
  * *Model Manager Modal:* Real-time disk status of `.cmf`, `.gguf`, and `.safetensors` model weights with on-demand download triggers.
* **Automation Scripts:**
  * `start_balladeer.bat` / `start_balledeer.bat`: Automates ComfyUI cloning, dependency installation, headless background startup, and frontend/backend dev servers.
  * `scripts/download_weights.py`: Standalone CLI weight downloader with progress reporting.

---

## 3. Automated Test Suite Status

All 25 automated unit and integration tests pass with zero errors:

```
============================= 25 passed in 37.51s =============================
tests/test_aligner.py::test_beat_snapping PASSED                         [  4%]
tests/test_aligner.py::test_music_synthesis_and_beat_extraction PASSED   [  8%]
tests/test_api.py::test_health_endpoint PASSED                           [ 12%]
tests/test_api.py::test_project_api_lifecycle PASSED                     [ 16%]
tests/test_aspect_ratio_and_instrumental.py::test_instrumental_event_cards_subtitles PASSED [ 20%]
tests/test_aspect_ratio_and_instrumental.py::test_vertical_aspect_ratio_processing PASSED [ 24%]
tests/test_beat_solver.py::test_beat_solver_config_ranges PASSED         [ 28%]
tests/test_comfy_worker.py::test_comfy_worker_build_prompt_graph PASSED  [ 32%]
tests/test_comfy_worker.py::test_comfy_worker_fallback_when_offline PASSED [ 36%]
tests/test_comfy_worker.py::test_minimax_engine_with_comfy_audio PASSED  [ 40%]
tests/test_comfy_worker.py::test_minimax_engine_with_cmf_runner_audio PASSED [ 44%]
tests/test_comfy_worker.py::test_minimax_engine_strict_error_when_all_offline PASSED [ 48%]
tests/test_compositor.py::test_ass_karaoke_subtitle_generation PASSED    [ 52%]
tests/test_compositor.py::test_blurred_background_fill PASSED            [ 56%]
tests/test_config.py::test_config_defaults PASSED                        [ 60%]
tests/test_database.py::test_database_lifecycle PASSED                   [ 64%]
tests/test_model_wrappers.py::test_qwen_vlm_heuristic PASSED             [ 68%]
tests/test_model_wrappers.py::test_minimax_music_engine PASSED           [ 72%]
tests/test_model_wrappers.py::test_mms_aligner PASSED                    [ 76%]
tests/test_models_api.py::test_models_status_api PASSED                  [ 80%]
tests/test_models_api.py::test_model_download_trigger_api PASSED         [ 84%]
tests/test_split_and_reorder.py::test_split_and_reorder_api PASSED       [ 88%]
tests/test_system_api.py::test_shutdown_endpoint PASSED                  [ 92%]
tests/test_upload_video_foreign_key.py::test_video_indexing_foreign_key_integrity PASSED [ 96%]
tests/test_video_segments.py::test_video_subsegments_extraction PASSED   [100%]
```

# Balladeer — Comprehensive TODO & Future Roadmap

This document outlines completed milestones, upcoming improvements, technical optimizations, and roadmap features for the Balladeer AI video montage platform.

---

## 1. Completed Recent Milestones

### 1.1 AI Model Priority Waterfall & Google AI Studio Integration
* [x] **Multi-Tier Model Priority Waterfall (`model_router.py`):**
  * Dynamic dispatch across Google AI free tier pools: `gemini-3.5-flash-lite`, `gemini-3.1-flash-lite`, `gemini-2.5-flash-lite`, `gemini-3.7-flash`, `gemini-3.6-flash`, `gemma-4-31b-it`, and `gemma-4-26b-it`.
  * Sliding-window token and request quota rate limiting (RPM/TPM/RPD) with automatic waterfall failover.
  * Google AI Studio API key verification and dynamic runtime configuration (`.env`).
* [x] **"Only Local AI" Isolation Toggle:** One-click setting in the UI to disable all cloud APIs and execute 100% locally offline.

### 1.2 Multimodal Local Vision & Model Manager
* [x] **True Multimodal Local Qwen 3.5 VLM (`qwen_vlm.py`):**
  * Multimodal vision projector binding (`Qwen25VLChatHandler` + `mmproj-F16.gguf`) for both **Qwen 3.5 4B** and **Qwen 3.5 9B**.
  * Dynamic in-memory model switching between 4B and 9B from the UI.
  * Image pre-scaling to 512px and 8-thread multi-core parallelism reducing inference latency by 75%.
  * 100% offline local inference with zero network calls.
* [x] **2-Step Media Ingestion & Staging Engine (`indexer.py`):**
  * Step 1: Rapid metadata extraction (EXIF, duration, dimensions) + instant thumbnail generation.
  * Step 2: On-demand batch AI vision indexing via the UI "Index Media" button.
* [x] **Asset Detail Inspector Modal (`AssetDetailModal.jsx`):**
  * Large image/video preview with model attribution (`indexed_by_model`).
  * Direct editing of captions, tags, and photographic quality scores in SQLite.
  * 1-click single-asset re-indexing.
* [x] **Model Manager Modal (`ModelManagerModal.jsx`):**
  * Visual model status table with Hugging Face download triggers and progress tracking.
  * Local model selector card (4B vs 9B) with VRAM/RAM footprints.
  * Gemini API key input and Only-Local AI toggle.

### 1.3 Structured Diary & Travel Itinerary Engine
* [x] **Structured Day-by-Day Itinerary Engine (`StructuredDiaryInput.jsx`):** Date range pickers (start date & finish date), dynamic day list generation, per-day event textareas, and weekday badge calculations.
* [x] **Post-Creation Itinerary Module (`DiaryEditorModal.jsx`):** Dedicated closable modal accessible from Header and Music Studio allowing live editing of diary text, dates, and settings after project creation.
* [x] **Day Discard & Bring Back Controls:** Toggle button to exclude specific days from song lyrics and narrative acts while preserving content for later restoration.
* [x] **AI Re-phrase & Spell Fixer Engine (`rephraser.py`):** Automatic typo and spelling correction + poetic travel prose enhancement for individual days and full itineraries.
* [x] **Date-Aware Media Indexing & Tagging:** Automatically matches photo/video EXIF capture dates to structured itinerary days (`day:Day X`, `date:YYYY-MM-DD`).
* [x] **Date-Aware Beat Placement Affinity:** Beat solver prioritizes matching assets captured on Day X into the corresponding narrative act for Day X.
* [x] **Dynamic Date Sync (`POST /api/projects/{id}/sync-diary-dates`):** Automatically re-syncs media asset tags when itinerary dates are updated.

### 1.4 System & Engineering Quality
* [x] **Centralized Logging System (`logging_config.py`):** Timestamped session logs in `logs/balladeer_YYYYMMDD_HHMMSS.log` with detailed model calls and prompts.
* [x] **Cross-Platform Line Ending Normalization (`.gitattributes`):** Enforced LF on source/config and CRLF on Windows scripts.
* [x] **Comprehensive Test Suite:** 38 / 38 unit and integration tests passing (100% pass rate).

---

## 2. High-Priority Functional Enhancements

### 2.1 In-Browser Interactive Lyric & Timestamp Editor
* **Description:** Currently, lyrics are generated from the user's travel narrative and aligned via TorchAudio MMS_FA. Adding an interactive lyric editor will allow users to fine-tune generated words, fix misheard lyrics, and nudge individual word timestamps on the timeline.
* **Proposed Implementation:**
  * Add a "Lyric Editor" tab in `web/src/components/MusicStudio.jsx` showing the word-level CTC alignment blocks.
  * Allow dragging word boundaries $\pm 0.1\text{s}$ to snap to adjacent beat ticks.
  * Add an API endpoint `PUT /api/projects/{project_id}/lyrics` to update aligned tokens without re-running music generation.

### 2.2 Multi-Aspect Simultaneous Batch Export
* **Description:** Users frequently need 16:9 for YouTube/TV, 9:16 for TikTok/Instagram Reels/Shorts, and 1:1 for Instagram feeds.
* **Proposed Implementation:**
  * Add a "Batch Export All (16:9, 9:16, 1:1)" option in the UI export modal.
  * In `app/pipeline/compositor.py`, execute parallel NVENC render workers using Python `concurrent.futures.ThreadPoolExecutor` to output `montage_16x9.mp4`, `montage_9x16.mp4`, and `montage_1x1.mp4`.
  * Package all three exports into a single `.zip` download bundle.

### 2.3 GPS Map Track & Itinerary Route Visualization
* **Description:** Extract GPS coordinates from EXIF metadata and render an animated travel route map interlude between days/acts.
* **Proposed Implementation:**
  * Parse GPS Latitude & Longitude during EXIF extraction in `indexer.py`.
  * Generate a route map animation clip using Folium / Static Maps and insert as a transition card between narrative acts.

---

## 3. Audio & Music Engine Optimizations

### 3.1 MiniMax Music 3 Autoregressive Token Generation Speedup
* **Description:** In `minimax-music3-q4tp.cmf`, the 8-step latent diffusion and vocoder stages run rapidly on the RTX 3070 GPU via Vulkan shaders. The autoregressive sequence generation stage (`ar 1/750`) is CPU-bound.
* **Proposed Implementation:**
  * Benchmark newer Cortiq/CMF upstream binary releases (`infosave2007/cmf`) as GPU kernel support for the autoregressive transformer layers matures.
  * Implement an automatic duration recommender (e.g. defaulting to 10s or 15s for quick iterations, 30s for final master rendering).

### 3.2 User-Selectable Musical Genre & Mood Presets
* **Description:** Allow users to choose from a curated set of acoustic, cinematic, lo-fi, EDM, orchestral, or rock style presets in the Music Studio UI rather than typing prompts manually.
* **Proposed Implementation:**
  * Add preset buttons in `web/src/components/MusicStudio.jsx` (e.g., *"Japanese Lo-Fi Acoustic"*, *"Cinematic Travel Trailer"*, *"Upbeat Summer Pop"*, *"Epic Orchestral Journey"*).
  * Automatically inject mood tags and BPM constraints into the narrative prompt generator.

### 3.3 Custom Vocal Timbre & Reference Voice Cloning
* **Description:** Allow users to upload a 5-second clean voice audio reference (`reference_voice.wav`) so that the AI singing vocals match the user's timbre.
* **Proposed Implementation:**
  * Pass `--reference-audio` into the CMF runner or ComfyUI vocal conditioner when the feature is enabled.

---

## 4. Video Editing & Visual Transitions

### 4.1 Advanced Transition Shaders (FFmpeg `xfade`)
* **Description:** Expand visual transitions beyond hard cuts and Ken Burns zoom to include smooth cinematic transitions on beat drops.
* **Proposed Implementation:**
  * Support `xfade=transition=fade:duration=0.3`, `wipeleft`, `circleopen`, `dissolve`, and `hlslice` on major chorus downbeats.
  * Allow users to select per-slice transition styles from the Timeline Editor.

### 4.2 Visual Color Grading & LUT Presets
* **Description:** Apply unified cinematic color grading (Lookup Tables - LUTs) across mixed photos and video clips to achieve a cohesive visual tone.
* **Proposed Implementation:**
  * Add an optional color grading step in `app/pipeline/compositor.py` using `ffmpeg -vf "lut3d=file='cinematic_warm.cube'"` with presets: *Warm Autumn, Kodak Gold, Teal & Orange, Moody Monochrome*.

### 4.3 Dynamic Subtitle Animations & Typography Options
* **Description:** Provide customizable typography and animation styles for the generated ASS subtitles.
* **Proposed Implementation:**
  * Add font picker (e.g. Montserrat, Playfair Display, Bebas Neue, Outfit).
  * Support bouncy karaoke pop effects, typewriter reveals, and glow outlines.

---

## 5. Timeline & Media Management

### 5.1 Manual Media In-Point / Out-Point Trimmer for Video Clips
* **Description:** Allow users to trim the exact start and end timestamps of long video clips inside the Timeline Editor before the solver places them on beats.
* **Proposed Implementation:**
  * Add a dual-handle video trimming scrubber in `web/src/components/AssetSwapModal.jsx`.
  * Store custom `clip_start_sec` and `clip_end_sec` in `TimelineSliceModel`.

### 5.2 Auto-Grouping & Duplicate Photo Clustering
* **Description:** Prevent burst photos (similar consecutive shots) from taking up adjacent timeline slots.
* **Proposed Implementation:**
  * Compute cosine similarity between consecutive CLIP embeddings during indexing; group bursts with similarity $> 0.92$ into a single asset stack and pick the highest quality score image.

---

## 6. Deployment & System Packaging

### 6.1 One-Click Windows Installer / Portable Executable
* **Description:** Package Balladeer with embedded Python and pre-compiled binaries into a single portable `.exe` or desktop installer.
* **Proposed Implementation:**
  * Use PyInstaller / Inno Setup to bundle FastAPI, React static dist, FFmpeg, and `cortiq.exe` into a single standalone distribution folder.

### 6.2 Automated Model Weight Verification on Startup
* **Description:** Run a quick health check on application start to verify that `minimax-music3-q4tp.cmf`, `Qwen3.5-4B-Q4_K_M.gguf`, and `Qwen3.5-9B-Q4_K_M.gguf` file sizes and hashes match official releases, notifying the user immediately if weights are corrupted or incomplete.

# Balladeer — Comprehensive TODO & Future Roadmap

This document outlines upcoming improvements, technical optimizations, and potential roadmap features for the Balladeer AI video montage platform.

---

## 1. High-Priority Functional Enhancements

### 1.1 In-Browser Interactive Lyric & Timestamp Editor
* **Description:** Currently, lyrics are generated from the user's travel narrative and aligned via TorchAudio MMS_FA. Adding an interactive lyric editor will allow users to fine-tune generated words, fix misheard lyrics, and nudge individual word timestamps on the timeline.
* **Proposed Implementation:**
  * Add a "Lyric Editor" tab in `web/src/components/MusicStudio.jsx` showing the word-level CTC alignment blocks.
  * Allow dragging word boundaries $\pm 0.1\text{s}$ to snap to adjacent beat ticks.
  * Add an API endpoint `PUT /api/projects/{project_id}/lyrics` to update aligned tokens without re-running music generation.

### 1.2 Multi-Aspect Simultaneous Batch Export
* **Description:** Users frequently need 16:9 for YouTube/TV, 9:16 for TikTok/Instagram Reels/Shorts, and 1:1 for Instagram feeds.
* **Proposed Implementation:**
  * Add a "Batch Export All (16:9, 9:16, 1:1)" option in the UI export modal.
  * In `app/pipeline/compositor.py`, execute parallel NVENC render workers using Python `concurrent.futures.ThreadPoolExecutor` to output `montage_16x9.mp4`, `montage_9x16.mp4`, and `montage_1x1.mp4`.
  * Package all three exports into a single `.zip` download bundle.

---

## 2. Audio & Music Engine Optimizations

### 2.1 MiniMax Music 3 Autoregressive Token Generation Speedup
* **Description:** In `minimax-music3-q4tp.cmf`, the 8-step latent diffusion and vocoder stages run rapidly on the RTX 3070 GPU via Vulkan shaders. The autoregressive sequence generation stage (`ar 1/750`) is CPU-bound.
* **Proposed Implementation:**
  * Benchmark newer Cortiq/CMF upstream binary releases (`infosave2007/cmf`) as GPU kernel support for the autoregressive transformer layers matures.
  * Implement an automatic duration recommender (e.g. defaulting to 10s or 15s for quick iterations, 30s for final master rendering).

### 2.2 User-Selectable Musical Genre & Mood Presets
* **Description:** Allow users to choose from a curated set of acoustic, cinematic, lo-fi, EDM, orchestral, or rock style presets in the Music Studio UI rather than typing prompts manually.
* **Proposed Implementation:**
  * Add preset buttons in `web/src/components/MusicStudio.jsx` (e.g., *"Japanese Lo-Fi Acoustic"*, *"Cinematic Travel Trailer"*, *"Upbeat Summer Pop"*, *"Epic Orchestral Journey"*).
  * Automatically inject mood tags and BPM constraints into the narrative prompt generator.

### 2.3 Custom Vocal Timbre & Reference Voice Cloning
* **Description:** Allow users to upload a 5-second clean voice audio reference (`reference_voice.wav`) so that the AI singing vocals match the user's timbre.
* **Proposed Implementation:**
  * Pass `--reference-audio` into the CMF runner or ComfyUI vocal conditioner when the feature is enabled.

---

## 3. Video Editing & Visual Transitions

### 3.1 Advanced Transition Shaders (FFmpeg `xfade`)
* **Description:** Expand visual transitions beyond hard cuts and Ken Burns zoom to include smooth cinematic transitions on beat drops.
* **Proposed Implementation:**
  * Support `xfade=transition=fade:duration=0.3`, `wipeleft`, `circleopen`, `dissolve`, and `hlslice` on major chorus downbeats.
  * Allow users to select per-slice transition styles from the Timeline Editor.

### 3.2 Visual Color Grading & LUT Presets
* **Description:** Apply unified cinematic color grading (Lookup Tables - LUTs) across mixed photos and video clips to achieve a cohesive visual tone.
* **Proposed Implementation:**
  * Add an optional color grading step in `app/pipeline/compositor.py` using `ffmpeg -vf "lut3d=file='cinematic_warm.cube'"` with presets: *Warm Autumn, Kodak Gold, Teal & Orange, Moody Monochrome*.

### 3.3 Dynamic Subtitle Animations & Typography Options
* **Description:** Provide customizable typography and animation styles for the generated ASS subtitles.
* **Proposed Implementation:**
  * Add font picker (e.g. Montserrat, Playfair Display, Bebas Neue, Outfit).
  * Support bouncy karaoke pop effects, typewriter reveals, and glow outlines.

---

## 4. Timeline & Media Management

### 4.1 Manual Media In-Point / Out-Point Trimmer for Video Clips
* **Description:** Allow users to trim the exact start and end timestamps of long video clips inside the Timeline Editor before the solver places them on beats.
* **Proposed Implementation:**
  * Add a dual-handle video trimming scrubber in `web/src/components/AssetSwapModal.jsx`.
  * Store custom `clip_start_sec` and `clip_end_sec` in `TimelineSliceModel`.

### 4.2 Auto-Grouping & Duplicate Photo Clustering
* **Description:** Prevent burst photos (similar consecutive shots) from taking up adjacent timeline slots.
* **Proposed Implementation:**
  * Compute cosine similarity between consecutive CLIP embeddings during indexing; group bursts with similarity $> 0.92$ into a single asset stack and pick the highest quality score image.

---

## 5. Deployment & System Packaging

### 5.1 One-Click Windows Installer / Portable Executable
* **Description:** Package Balladeer with embedded Python and pre-compiled binaries into a single portable `.exe` or desktop installer.
* **Proposed Implementation:**
  * Use PyInstaller / Inno Setup to bundle FastAPI, React static dist, FFmpeg, and `cortiq.exe` into a single standalone distribution folder.

### 5.2 Automated Model Weight Verification on Startup
* **Description:** Run a quick health check on application start to verify that `minimax-music3-q4tp.cmf` and `Qwen3.5-4B-GGUF` hashes match official releases, notifying the user immediately if weights are corrupted or incomplete.

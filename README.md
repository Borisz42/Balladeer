# Balladeer 🎶🎬

> **Hybrid Cloud-Local AI Beat-Synced Video Montage Engine**  
> Transform your travel logs, photos, and video clips into beat-synchronized cinematic music videos—powered by a high-throughput **Google AI Studio Free-Tier Model Waterfall**, an **Intelligent Multi-Tier Dispatcher**, local **Qwen3.5-4B GPU VLM fallback**, **Google Flow Music (MusicFX / Lyria)** prompt optimization, and hardware-accelerated **FFmpeg NVENC** video compositing.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-brightgreen.svg)](https://www.python.org/)
[![VRAM Budget](https://img.shields.io/badge/VRAM%20Budget-8GB%20RTX%203070-orange.svg)](#hardware-requirements)
[![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688.svg)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/Frontend-React%2018%20%2B%20Vite-61DAFB.svg)](https://vitejs.dev/)
[![Tests](https://img.shields.io/badge/Tests-30%2F30%20Passing-brightgreen.svg)](#automated-test-suite)

---

## 🌟 Overview

**Balladeer** transforms raw vacation photo dumps, video clips, and trip diary logs into cohesive, beat-accurate music video montages with custom AI-composed songs.

Unlike traditional montage generators that randomly splice clips on arbitrary beat ticks, Balladeer:
1. **Parallel Batch Vision Indexing:** Ingests media in parallel chunks (up to 25 items/batch) using a multi-tier Google AI Studio model priority waterfall (`Gemini 3.5 Flash Lite` $\rightarrow$ `3.1 Flash Lite` $\rightarrow$ `2.5 Flash Lite` $\rightarrow$ `Gemma 4` $\rightarrow$ Local `Qwen3.5-4B` fallback).
2. **Google Flow Music & Structured Lyrics:** Optimizes rich musical prompts tailored specifically for **Google Flow Music (MusicFX / Lyria)** and structures 5-act rhyming lyrics (*Verse 1 $\rightarrow$ Chorus $\rightarrow$ Verse 2 $\rightarrow$ Bridge $\rightarrow$ Outro*).
3. **Optional Local MiniMax 3 Engine:** Provides an on-device synthesis switch for **MiniMax Music 3** executed natively via **Cortiq CMF** with **Vulkan RTX 3070 GPU compute shaders**.
4. **Isolates Vocals & Tracks Beats:** Uses **Demucs** 2-stem separation and **Librosa** onset beat tracking on uploaded or synthesized audio.
5. **Phonetic CTC Forced Alignment:** Aligns lyric words to vocals using **TorchAudio MMS_FA** Trellis dynamic programming.
6. **Solves Media-to-Beat Placement:** Global integer programming optimization solver enforces chronological storytelling, photo/video duration constraints, motion score matching, and recency penalties.
7. **Hardware Video Compositing:** Renders full HD/4K videos with **FFmpeg NVENC**, blurred background padding for mixed aspect ratios, Ken Burns zoom motion, EBU R128 loudness mastering, and animated **ASS karaoke subtitles**.

---

## 🌊 Model Priority Waterfalls & Quota Pool Strategy

Your quotas naturally divide into **High-Volume Workhorses** (Flash Lite & Gemma), **High-Reasoning Specialists** (Flash 3.x), and **Local Fallback** (`Qwen3.5-4B` on RTX GPU).

```
VISION INDEXING WATERFALL (Batch Images / Video Frames)
1. Gemini 3.5 Flash Lite  (15 RPM | 250K TPM | 500 RPD)  ──► Primary batch vision worker (up to 25 imgs/batch)
2. Gemini 3.1 Flash Lite  (15 RPM | 250K TPM | 500 RPD)  ──► Secondary batch vision worker
3. Gemini 2.5 Flash Lite  (10 RPM | 250K TPM | 20 RPD)   ──► Lite overflow pool
4. Gemini 3.7 / 3.6 Flash (5 RPM  | 250K TPM | 20 RPD)   ──► Overflow pool
5. Gemma 4 31B / 26B      (30 RPM | 16K TPM  | 14.4K RPD)──► Micro-batches (<15k tokens)
6. Local Qwen3.5-4B       (Unlimited | Local RTX 3070)   ──► Hard fallback if cloud is depleted / offline / local mode

STORY & RHYMING LYRIC WATERFALL (Text Planning & Google Flow Music Prompts)
1. Gemini 3.7 Flash       (Top lyrical quality & Flow Music prompt structuring)
2. Gemma 4 31B / 26B      (30 RPM | 14.4K RPD | 16K TPM — massive daily capacity)
3. Gemini 3.5 Flash Lite  (High speed, structured JSON adherence)
4. Local Qwen3.5-4B       (Offline local fallback)
```

### Quota Pool Strategy

* **Combined Daily Throughput:** Using `3.5 Flash Lite` (500 RPD) + `3.1 Flash Lite` (500 RPD) yields **1,000 multimodal requests per day**. At 25 images per batch, you can index **25,000 photos/frames daily for free**.
* **Combined RPM Headroom:** Alternating across both Flash Lite tiers yields an effective throughput of **30 RPM** and **500K TPM**.
* **Gemma 4 TPM Constraint:** Gemma 4 has a huge 14.4K daily quota, with its 16K TPM limit reserved for text-only tasks or 3-to-5 image micro-batches.
* **Sliding-Window Rate Limiting & Optimistic Locking:** Real-time sliding window (60-second) rate limiter tracks RPM & TPM and claims slots before issuing network calls to prevent 429 errors.
* **Master Local Switch & UI `.env` Storage:** Configure your Google AI Studio API key directly via the UI modal (stored safely in untracked `.env`), or toggle the **"Only Use Local AI"** master switch to run 100% offline.

---

## 🏗 Architecture & Pipeline

```
┌────────────────────────────────────────────────────────────────────────┐
│                        1. MEDIA INDEXING PHASE                         │
│  • Parallel Batch Media Ingestion (up to 25 items / batch)             │
│  • Intelligent Model Dispatcher (Gemini Flash Lite -> Gemma -> Local)  │
│  • Scene Cut & Subsegment Detector (PySceneDetect / OpenCV)            │
│  • Visual Embeddings & Search (SigLIP 2 Base 768-dim FP16)             │
│  • Local Visual-Language Model Fallback (Qwen3.5-4B-GGUF Q4_K_M)       │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
▼
┌────────────────────────────────────────────────────────────────────────┐
│                      2. MUSIC & LYRIC STUDIO                           │
│  • Narrative Act Structuring (5 Acts: Verse 1, Chorus, Verse 2, etc.)  │
│  • Google Flow Music (MusicFX / Lyria) Prompt Optimizer & 1-Click Copy │
│  • Optional Local MiniMax Music 3 Synthesis (cortiq.exe / Vulkan GPU)  │
│  • Direct Custom Audio Dropzone & External Track Importer              │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
▼
┌────────────────────────────────────────────────────────────────────────┐
│                   3. STEM SEPARATION & ALIGNMENT                       │
│  • Demucs 2-Stem Demixing (Master -> Vocals + Accompaniment)           │
│  • Librosa Onset Envelope & Beat Grid Tracker                          │
│  • TorchAudio MMS_FA CTC Trellis Forced Lyric Alignment                │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
▼
┌────────────────────────────────────────────────────────────────────────┐
│                4. GLOBAL CONSTRAINT BEAT SOLVER                        │
│  • Chronological Storytelling & Quality Optimization                   │
│  • Photo (1-3 Beats) & Video (2-5 Beats) Duration Bounds               │
│  • High-Motion Video Matching & Recency Avoidance Penalties            │
│  • Interactive Timeline Editor (Drag/Drop, Split Slice, Asset Swap)    │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
▼
┌────────────────────────────────────────────────────────────────────────┐
│                 5. HARDWARE VIDEO COMPOSITOR (NVENC)                   │
│  • Multi-Aspect Ratios (16:9, 9:16, 1:1) & Blurred Background Fill     │
│  • Ken Burns Dynamic Pan/Zoom (zoompan)                                │
│  • Synchronized Karaoke & Chapter Event Card Subtitles (.ass)          │
│  • EBU R128 Loudness Mastering (-14 LUFS) & Fade In/Out               │
│  • High-Speed Hardware Encoding (FFmpeg h264_nvenc)                    │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 💻 Hardware Requirements

| Component | Minimum Specification | Recommended Specification |
| :--- | :--- | :--- |
| **GPU** | NVIDIA RTX 3070 (8 GB VRAM) | NVIDIA RTX 3080 / 4070 / 4080 (8–16 GB VRAM) |
| **GPU Backend** | Vulkan 1.3 / CUDA 12.x / NVENC | Vulkan 1.3 / CUDA 12.x / NVENC |
| **System RAM** | 16 GB DDR4 | 32 GB DDR4 / DDR5 |
| **Storage** | 20 GB free space on SSD | 50 GB free space on NVMe SSD |
| **OS** | Windows 11 (PowerShell) | Windows 11 (PowerShell) / Linux (Ubuntu 22.04+) |

---

## 📦 Installation & Quickstart

### 1. Prerequisites
Ensure you have **Python 3.11+**, **Node.js 18+**, **FFmpeg** (with `h264_nvenc`), and **Git** installed.

```powershell
# Verify FFmpeg NVENC support
ffmpeg -encoders | Select-String "nvenc"
```

### 2. Clone Repository
```powershell
git clone https://github.com/Borisz42/Balladeer.git
cd Balladeer
```

### 3. One-Click Launch (Recommended)
Simply run the startup batch script. It automatically downloads dependencies, sets up the CMF runner, starts the headless engine, launches the FastAPI backend, and spins up the React frontend:

```powershell
.\start_balladeer.bat
```

Open your browser to **`http://localhost:5173`** (or `http://localhost:8000`).

---

### Manual Setup (Alternative)

#### Backend Setup
```powershell
# 1. Create and activate virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1

# 2. Install PyTorch with CUDA 12.x support
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu128

# 3. Install core dependencies
pip install -r requirements.txt

# 4. Download / Verify model weights
python scripts/download_weights.py

# 5. Start FastAPI Backend
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

#### Frontend Setup
```powershell
cd web
npm install
npm run dev
```

---

## 🧪 Automated Test Suite

Balladeer includes an extensive test suite covering the entire hybrid model dispatcher, batch indexer, and multimedia pipeline:

```powershell
python -m pytest tests -v
```

```
============================= 30 passed in 40.29s =============================
tests/test_aligner.py::test_beat_snapping PASSED                         [  3%]
tests/test_aligner.py::test_music_synthesis_and_beat_extraction PASSED   [  6%]
tests/test_api.py::test_health_endpoint PASSED                           [ 10%]
tests/test_api.py::test_project_api_lifecycle PASSED                     [ 13%]
tests/test_aspect_ratio_and_instrumental.py::test_instrumental_event_cards_subtitles PASSED [ 16%]
tests/test_aspect_ratio_and_instrumental.py::test_vertical_aspect_ratio_processing PASSED [ 20%]
tests/test_batch_indexer.py::test_parallel_batch_indexing PASSED         [ 23%]
tests/test_beat_solver.py::test_beat_solver_config_ranges PASSED         [ 26%]
tests/test_comfy_worker.py::test_comfy_worker_build_prompt_graph PASSED  [ 30%]
tests/test_comfy_worker.py::test_comfy_worker_fallback_when_offline PASSED [ 33%]
tests/test_comfy_worker.py::test_minimax_engine_with_comfy_audio PASSED  [ 36%]
tests/test_comfy_worker.py::test_minimax_engine_with_cmf_runner_audio PASSED [ 40%]
tests/test_comfy_worker.py::test_minimax_engine_strict_error_when_all_offline PASSED [ 43%]
tests/test_compositor.py::test_ass_karaoke_subtitle_generation PASSED    [ 46%]
tests/test_compositor.py::test_blurred_background_fill PASSED            [ 50%]
tests/test_config.py::test_config_defaults PASSED                        [ 53%]
tests/test_database.py::test_database_lifecycle PASSED                   [ 56%]
tests/test_model_router.py::test_model_quota_sliding_window PASSED       [ 60%]
tests/test_model_router.py::test_model_router_waterfall_fallback PASSED  [ 63%]
tests/test_model_router.py::test_model_router_only_local_ai_mode PASSED  [ 66%]
tests/test_model_wrappers.py::test_qwen_vlm_heuristic PASSED             [ 70%]
tests/test_model_wrappers.py::test_minimax_music_engine PASSED           [ 73%]
tests/test_model_wrappers.py::test_mms_aligner PASSED                    [ 76%]
tests/test_models_api.py::test_models_status_api PASSED                  [ 80%]
tests/test_models_api.py::test_model_download_trigger_api PASSED         [ 83%]
tests/test_settings_api.py::test_settings_api_lifecycle PASSED           [ 86%]
tests/test_split_and_reorder.py::test_split_and_reorder_api PASSED       [ 90%]
tests/test_system_api.py::test_shutdown_endpoint PASSED                  [ 93%]
tests/test_upload_video_foreign_key.py::test_video_indexing_foreign_key_integrity PASSED [ 96%]
tests/test_video_segments.py::test_video_subsegments_extraction PASSED   [100%]
```

---

## 📁 Repository Structure

```
Balladeer/
├── app/
│   ├── api/                  # FastAPI REST endpoints (projects, timeline, models, system)
│   ├── core/                 # App configuration & .env settings manager
│   ├── database/             # SQLite ORM models & database manager
│   ├── models/               # Model inference runners & dispatchers
│   │   ├── model_router.py   # Intelligent Multi-Tier Model Dispatcher & Quota Tracker
│   │   ├── gemini_client.py  # Google AI Studio Free Tier API client (Gemini & Gemma)
│   │   ├── qwen_vlm.py       # Qwen3.5-4B-GGUF local VLM runner & heuristic scorer
│   │   ├── minimax_music.py  # MiniMax Music 3 synthesis engine
│   │   ├── cmf_runner.py     # Cortiq CMF MiniMax Music 3 native runner (Vulkan GPU)
│   │   ├── comfy_music_worker.py # Headless ComfyUI worker interface
│   │   ├── siglip_embedder.py # SigLIP 2 Base vector embeddings (768-dim FP16)
│   │   ├── demucs_separator.py # Demucs audio stem separation
│   │   └── mms_aligner.py    # TorchAudio MMS_FA forced alignment & beat snapper
│   ├── pipeline/             # Core processing phases
│   │   ├── indexer.py        # Parallel batch ingestion, EXIF, scene cuts & VLM tagging
│   │   ├── music_gen.py      # Google Flow Music prompt optimization & rhyming lyrics
│   │   ├── aligner.py        # Stem demixing, Librosa beats & phonetic alignment
│   │   ├── beat_solver.py    # Global constraint-based media placement solver
│   │   └── compositor.py     # FFmpeg NVENC compositing, blurred fill & ASS karaoke
│   └── main.py               # FastAPI application entrypoint
├── web/                      # React 18 + Vite frontend application
│   ├── src/
│   │   ├── components/       # UI views (AssetGallery, MusicStudio, TimelineEditor, ModelManagerModal, etc.)
│   │   ├── App.jsx           # Main state orchestrator & SSE progress listener
│   │   └── index.css         # Glassmorphism design system
│   └── package.json
├── tools/                    # Local native binaries (cortiq.exe)
├── scripts/                  # Model downloaders and utility scripts
├── tests/                    # 30 automated unit and integration tests
├── start_balladeer.bat       # One-click Windows startup script
├── status.md                 # Project status & architectural breakdown
├── todo.md                   # Roadmap & optimizations
├── config.yaml               # Application configuration
├── requirements.txt          # Python dependencies
└── README.md                 # Project documentation
```

---

## ⚙️ Configuration (`config.yaml`)

```yaml
hardware:
  device: "cuda:0"
  max_vram_gb: 8.0

indexing:
  vlm_model: "unsloth/Qwen3.5-4B-GGUF"
  quality_threshold: 6.0
  scene_detection_threshold: 0.3
  batch_size: 20

google_ai:
  api_key: ""                 # Can also be set in .env or via the web UI
  only_local_ai: false        # Master switch for 100% offline local execution
  batch_size: 20
  enable_cloud_waterfall: true

audio:
  music_model: "infosave/MiniMax-Music-3-cmf"
  cmf_filename: "minimax-music3-q4tp.cmf"
  sample_rate: 32000
  beat_snap_tolerance_sec: 0.25
  enable_local_synthesis: false # Fast preview & Google Flow Music prompt workflow by default

video:
  resolution: [1920, 1080]
  fps: 30
  photo_beat_range: [1, 3]
  video_beat_range: [2, 5]
  default_bg_mode: "blurred_fill"
  enable_ken_burns: false
  blur_radius: 25
  blur_scale: 1.25
  video_codec: "h264_nvenc"
  nvenc_preset: "p6"
  audio_bitrate: "320k"
```

---

## 📄 License

Distributed under the **MIT License**. See [`LICENSE`](LICENSE) for details.

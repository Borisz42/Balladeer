# Balladeer 🎶🎬

> **Local AI Beat-Synced Video Montage Engine**  
> Transform your travel logs, photos, and video clips into beat-synchronized cinematic music videos—powered entirely by local open-weight models, Vulkan GPU compute, and hardware-accelerated NVENC video compositing.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-brightgreen.svg)](https://www.python.org/)
[![VRAM Budget](https://img.shields.io/badge/VRAM%20Budget-8GB%20RTX%203070-orange.svg)](#hardware-requirements)
[![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688.svg)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/Frontend-React%2018%20%2B%20Vite-61DAFB.svg)](https://vitejs.dev/)
[![Tests](https://img.shields.io/badge/Tests-25%2F25%20Passing-brightgreen.svg)](#automated-test-suite)

---

## 🌟 Overview

**Balladeer** transforms raw vacation photo dumps, video clips, and trip diary logs into cohesive, beat-accurate music video montages with custom AI-composed songs.

Unlike traditional montage generators that randomly splice clips on arbitrary beat ticks, Balladeer:
1. **Structures Narrative Acts:** Partitions your travel diary into a 5-act musical narrative (*Verse 1 $\rightarrow$ Chorus $\rightarrow$ Verse 2 $\rightarrow$ Verse 3 / Bridge $\rightarrow$ Outro*).
2. **Generates High-Fidelity Music:** Uses the 6GB quantized **MiniMax Music 3** model (`minimax-music3-q4tp.cmf`) executed natively via **Cortiq CMF** with **Vulkan RTX 3070 GPU compute shaders**.
3. **Isolates Vocals & Tracks Beats:** Uses **Demucs** 2-stem separation and **Librosa** onset analysis.
4. **Phonetic CTC Forced Alignment:** Aligns lyric words to vocals using **TorchAudio MMS_FA** Trellis dynamic programming.
5. **Solves Media-to-Beat Placement:** Global integer programming optimization solver enforces chronological storytelling, photo/video duration constraints, motion score matching, and recency penalties.
6. **Hardware Video Compositing:** Renders full HD/4K videos with **FFmpeg NVENC**, blurred background padding for mixed aspect ratios, Ken Burns zoom motion, EBU R128 loudness mastering, and animated **ASS karaoke subtitles**.

Everything runs **100% locally** on consumer hardware (e.g. NVIDIA RTX 3070 8GB VRAM) with **zero cloud dependencies** and a strict **no silent fallbacks** policy.

---

## 🚀 Key Features

* **Multi-Modal Asset Ingestion:** Drag-and-drop batch upload or recursive directory scanning. Automatically parses EXIF capture timestamps, GPS data, camera metadata, video resolutions, and frame rates.
* **Scene Change & Subsegment Detection:** PySceneDetect and OpenCV frame difference algorithms partition long video files into punchy subsegment clips (`video_segments` table) with motion intensity scores.
* **Local Vision-Language Indexing (VLM):** Quantized `unsloth/Qwen3.5-4B-GGUF` (Q4_K_M) + `sentence-transformers/clip-ViT-B-32` generates 512-d vector embeddings and scene descriptions for semantic lyric matching.
* **Official MiniMax Music 3 CMF Native Engine:**
  * Uses [`infosave2007/cmf`](https://github.com/infosave2007/cmf) with single-file `minimax-music3-q4tp.cmf` (5.96 GB).
  * Multi-core CPU token sequence generation (`RAYON_NUM_THREADS`).
  * **Vulkan compute shader acceleration on RTX 3070** for 8-step Euler latent diffusion and neural vocoder.
  * Real-time unbuffered progress streaming (`ar X/750` $\rightarrow$ `denoise X/8`).
  * Flexible song durations (**10s Fast Preview**, **15s Standard**, **20s Extended**, **30s Full Montage**).
* **Ground-Truth Lyric Alignment:** Demucs stem separation + TorchAudio `MMS_FA` Trellis CTC forced alignment snapping word-level timestamps to the musical beat grid.
* **Constraint-Based Beat Solver:**
  * Chronological storytelling enforcement ($\alpha \cdot \text{ChronoAlignment}$).
  * Quality and aesthetic weighting ($\beta \cdot \text{QualityScore}$).
  * Recency avoidance penalties ($\gamma \cdot \text{RecencyPenalty}$).
  * Media duration bounds (Photos: 1–3 beats, Videos: 2–5 beats).
  * 4-beat and 8-beat musical bar phrasing for instrumental tracks.
* **Interactive Web Timeline Editor:** Drag-and-drop slice reordering, arbitrary beat slice splitting, asset swap modal with metadata filters, and real-time scrubbing.
* **Multi-Aspect Ratio Compositing:**
  * **16:9 Landscape** (YouTube, Desktop, TV).
  * **9:16 Portrait** (TikTok, Instagram Reels, YouTube Shorts).
  * **1:1 Square** (Social feeds).
* **Blurred Background Fill & Ken Burns Motion:** Intelligent Gaussian blurred padding for vertical media on widescreen canvases (and vice versa) + smooth sub-pixel `zoompan` motion.
* **Synchronized ASS Subtitles & EBU R128 Mastering:** Word-by-word highlighted karaoke tags (`{\k<dur>}`) in vocal mode and chapter event cards in instrumental mode, normalized to `-14 LUFS`.

---

## 🏗 Architecture & Pipeline

```
┌────────────────────────────────────────────────────────────────────────┐
│                        1. MEDIA INDEXING PHASE                         │
│  • Batch Ingestion & EXIF Metadata Parser                              │
│  • Scene Cut & Subsegment Detector (PySceneDetect / OpenCV)            │
│  • Visual Embeddings & Search (CLIP ViT-B-32)                          │
│  • Local Visual-Language Model (Qwen3.5-4B-GGUF Q4_K_M)               │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
▼
┌────────────────────────────────────────────────────────────────────────┐
│                      2. MUSIC & LYRIC STUDIO                           │
│  • Narrative Act Structuring (5 Acts: Verse 1, Chorus, Verse 2, etc.)  │
│  • MiniMax Music 3 CMF Native Engine (cortiq.exe / Vulkan RTX 3070)    │
│  • Unbuffered Real-Time Token & Denoise Progress Streaming             │
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

Balladeer includes an extensive test suite covering the entire pipeline:

```powershell
python -m pytest tests -v
```

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

---

## 📁 Repository Structure

```
Balladeer/
├── app/
│   ├── api/                  # FastAPI REST endpoints (projects, timeline, models, system)
│   ├── core/                 # App configuration & settings manager
│   ├── database/             # SQLite ORM models & database manager
│   ├── models/               # Model inference runners
│   │   ├── cmf_runner.py     # Official Cortiq CMF MiniMax Music 3 native runner
│   │   ├── minimax_music.py  # MiniMax Music 3 synthesis & strict error policy
│   │   ├── comfy_music_worker.py # Headless ComfyUI worker interface
│   │   ├── qwen_vlm.py       # Qwen3.5-4B-GGUF vision-language runner
│   │   ├── clip_embedder.py  # CLIP ViT-B-32 vector embeddings
│   │   ├── demucs_separator.py # Demucs audio stem separation
│   │   └── mms_aligner.py    # TorchAudio MMS_FA forced alignment
│   ├── pipeline/             # Core processing phases
│   │   ├── indexer.py        # Media ingestion, EXIF, scene cuts & VLM captioning
│   │   ├── music_gen.py      # Narrative act structuring & rhyming lyrics
│   │   ├── aligner.py        # Stem demixing, Librosa beats & phonetic alignment
│   │   ├── beat_solver.py    # Global constraint-based media placement solver
│   │   └── compositor.py     # FFmpeg NVENC compositing, blurred fill & ASS karaoke
│   └── main.py               # FastAPI application entrypoint
├── web/                      # React 18 + Vite frontend application
│   ├── src/
│   │   ├── components/       # UI views (MediaGallery, MusicStudio, TimelineEditor, VideoPlayerModal, ModelManagerModal)
│   │   ├── App.jsx           # Main state orchestrator & SSE progress listener
│   │   └── index.css         # Glassmorphism & custom design system
│   └── package.json
├── tools/                    # Local native binaries (cortiq.exe)
├── scripts/                  # Model downloaders and utility scripts
├── tests/                    # 25 automated unit and integration tests
├── start_balladeer.bat       # One-click Windows startup script
├── status.md                 # Detailed project status & architectural breakdown
├── todo.md                   # Roadmap, future enhancements, & optimizations
├── pytest.ini                # Test suite configuration
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

audio:
  music_model: "infosave/MiniMax-Music-3-cmf"
  cmf_filename: "minimax-music3-q4tp.cmf"
  sample_rate: 32000
  beat_snap_tolerance_sec: 0.25

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

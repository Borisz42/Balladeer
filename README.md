# Balladeer 🎶🎬

> **Hybrid Cloud-Local AI Beat-Synced Video Montage Engine**  
> Transform your travel logs, photos, and video clips into beat-synchronized cinematic music videos—powered by a high-throughput **Google AI Studio Free-Tier Model Waterfall**, an **Intelligent Multi-Tier Dispatcher**, local **Qwen 2.5 VL GPU fallback**, **Google Flow Music (MusicFX / Lyria)** prompt optimization, and hardware-accelerated **FFmpeg NVENC** video compositing.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-brightgreen.svg)](https://www.python.org/)
[![VRAM Budget](https://img.shields.io/badge/VRAM%20Budget-8GB%20RTX%203070-orange.svg)](#hardware-requirements)
[![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688.svg)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/Frontend-React%2018%20%2B%20Vite-61DAFB.svg)](https://vitejs.dev/)
[![Tests](https://img.shields.io/badge/Tests-Passing-brightgreen.svg)](#automated-test-suite)

---

## 🌟 Overview

**Balladeer** transforms raw vacation photo dumps, video clips, and trip diary logs into cohesive, beat-accurate music video montages with custom AI-composed songs.

Unlike traditional montage generators that randomly splice clips on arbitrary beat ticks, Balladeer:
1. **Parallel Batch Vision Indexing:** Ingests media in parallel chunks (up to 25 items/batch) using a multi-tier Google AI Studio model priority waterfall (`Gemini 3.5 Flash Lite` $\rightarrow$ `3.1 Flash Lite` $\rightarrow$ `2.5 Flash Lite` $\rightarrow$ `Gemma 4` $\rightarrow$ Local `Qwen3.5-4B` fallback).
2. **Prompt & Structured Lyrics Generation:** Structures 5-act rhyming lyrics (*Verse 1 $\rightarrow$ Chorus $\rightarrow$ Verse 2 $\rightarrow$ Bridge $\rightarrow$ Outro*) and optimized musical prompts with local **Qwen 2.5** / **Gemini** waterfall.
3. **Audio Consumption & Beat Synchronization:** Ingests dropped-in audio files, extracts precise beat and downbeat grids with **Librosa**, and separates vocals/backing with **Demucs**.
4. **Phonetic CTC Forced Alignment:** Aligns lyric words to vocals using **TorchAudio MMS_FA** Trellis dynamic programming.
5. **Solves Media-to-Beat Placement:** Global integer programming optimization solver enforces chronological storytelling, photo/video duration constraints, motion score matching, and recency penalties.
6. **Hardware Video Compositing:** Renders full HD/4K videos with **FFmpeg NVENC**, blurred background padding for mixed aspect ratios, Ken Burns zoom motion, EBU R128 loudness mastering, and animated **ASS karaoke subtitles**.

---

## 🌊 Model Priority Waterfalls & Quota Pool Strategy

Your quotas naturally divide into **High-Volume Workhorses** (Flash Lite & Gemma), **High-Reasoning Specialists** (Flash 3.x), and **Local Fallback** (`Qwen 2.5 VL (3B)` on RTX GPU).

```
VISION INDEXING WATERFALL (Batch Images / Video Frames)
1. Gemini 3.5 Flash Lite  (15 RPM | 250K TPM | 500 RPD)  ──► Primary batch vision worker (up to 25 imgs/batch)
2. Gemini 3.1 Flash Lite  (15 RPM | 250K TPM | 500 RPD)  ──► Secondary batch vision worker
3. Gemini 2.5 Flash Lite  (10 RPM | 250K TPM | 20 RPD)   ──► Lite overflow pool
4. Gemini 3.7 / 3.6 Flash (5 RPM  | 250K TPM | 20 RPD)   ──► Overflow pool
5. Gemma 4 31B / 26B      (30 RPM | 16K TPM  | 14.4K RPD)──► Micro-batches (<15k tokens)
6. Local Qwen 2.5 VL 3B   (Unlimited | Local RTX 3070)   ──► Hard fallback if cloud is depleted / offline / local mode

STORY & RHYMING LYRIC WATERFALL (Text Planning & Google Flow Music Prompts)
1. Gemini 3.7 Flash       (Top lyrical quality & Flow Music prompt structuring)
2. Gemma 4 31B / 26B      (30 RPM | 14.4K RPD | 16K TPM — massive daily capacity)
3. Gemini 3.5 Flash Lite  (High speed, structured JSON adherence)
4. Local Qwen 2.5 VL 3B   (Offline local fallback)
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
│  • Local Visual-Language Model Fallback (Qwen 2.5 VL 3B NF4)           │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
▼
┌────────────────────────────────────────────────────────────────────────┐
│                      2. MUSIC & LYRIC STUDIO                           │
│  • Narrative Act Structuring (5 Acts: Verse 1, Chorus, Verse 2, etc.)  │
│  • Flow Music / AI Prompt Optimizer & 1-Click Copy                     │
│  • Qwen 2.5 Local / Cloud Rhyming Lyrics Generation                    │
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
| **GPU VRAM** | 8 GB  | 8–16 GB |
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
Simply run the startup batch script. It automatically verifies dependencies, launches the FastAPI backend, and spins up the React frontend:

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
│   │   ├── local_vlm.py      # High-throughput unified local VLM runner & text generator
│   │   ├── siglip_embedder.py # SigLIP 2 Base vector embeddings (768-dim FP16)
│   │   ├── demucs_separator.py # Demucs audio stem separation
│   │   └── mms_aligner.py    # TorchAudio MMS_FA forced alignment & beat snapper
│   ├── pipeline/             # Core processing phases
│   │   ├── indexer.py        # Parallel batch ingestion, EXIF, scene cuts & VLM tagging
│   │   ├── music_gen.py      # Music prompt optimization, rhyming lyrics & harmonic preview
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
├── scripts/                  # Model downloaders and utility scripts
├── tests/                    # Automated unit and integration tests
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
<<<<<<< HEAD
  vlm_model: "Qwen/Qwen2.5-VL-3B-Instruct"
=======
  local_model: "qwen2.5-vl-3b"
  vlm_model: "Qwen/Qwen2.5-VL-3B-Instruct"
  vlm_display_name: "Qwen 2.5 VL (3B)"
>>>>>>> remove_qwen3_5_refactor
  quality_threshold: 6.0
  scene_detection_threshold: 0.3
  batch_size: 8

google_ai:
  api_key: ""                 # Can also be set in .env or via the web UI
  only_local_ai: false        # Master switch for 100% offline local execution
  batch_size: 20
  enable_cloud_waterfall: true

audio:
  sample_rate: 32000
  beat_snap_tolerance_sec: 0.25
  default_tempo_bpm: 120.0
  demucs_model: "htdemucs"
  alignment_model: "MMS_FA"

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

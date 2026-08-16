# Balladeer 🎶🎬

> **Local AI Beat-Synced Video Montage Engine**  
> Turn your travel logs, photos, and video clips into custom rhyming music videos—cut precisely to the beat and powered entirely by local open-weight models.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-brightgreen.svg)](https://www.python.org/)
[![VRAM Budget](https://img.shields.io/badge/VRAM%20Budget-8GB%20RTX%203070-orange.svg)](#hardware-requirements)
[![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688.svg)](https://fastapi.tiangolo.com/)

---

## Overview

**Balladeer** transforms unstructured photo dumps, raw video clips, and trip diaries into cohesive, beat-accurate video montages with custom AI-generated songs. 

Unlike conventional montage generators that splice clips at random beat markers, Balladeer uses your written timeline to compose custom, rhyming lyrics, generates a full song via **MiniMax Music 3**, isolates the vocal stem with **Demucs**, aligns lyric phonemes with **TorchAudio MMS_FA**, and snaps scene cuts directly to downbeats and lyric phrases.

Everything runs **100% locally** within an **8GB VRAM / 16GB System RAM** budget using staged PCIe memory offloading.

---

## Key Features

* **Local Vision-Language Indexing:** Ingests photos and keyframed video clips (1 FPS / scene-change detection) using quantized **Qwen3.5-4B** to generate structured scene descriptions, tags, and aesthetic quality scores (1–10).
* **Act & Day Chronological Partitioning:** Divides your narrative and media pool into structured musical sections (e.g., `[Verse 1 / Day 1]`, `[Chorus]`, `[Verse 2 / Day 2]`).
* **RAM-Resident Staged Music Generation:** Runs the 11B+ parameter **MiniMax Music 3** pipeline locally on an 8GB GPU by holding quantized models in pinned host RAM and streaming sub-networks over PCIe.
* **Ground-Truth Lyric Forced Alignment:** Uses **Demucs** stem separation and **TorchAudio MMS_FA** (Trellis CTC dynamic programming) to lock vocal timestamps to ground-truth lyrics—eliminating STT hallucination.
* **Beat-Snapped Timeline Solver:** Calculates tempo and downbeats via **Librosa**, allocating 1–3 beats for photos (with dynamic Ken Burns motion) and 2–5 beats for active video slices.
* **Interactive Web Timeline:** Web-based UI to adjust beat lengths, re-roll musical prompts, and swap clips using top-$k$ **CLIP** semantic recommendations.
* **Hardware-Accelerated Compositing:** Assembles the final video and animated karaoke subtitles using **MoviePy v2.x** and **FFmpeg NVENC**.

---

## Architecture & Memory Staging

Balladeer utilizes non-blocking PCIe DMA transfers (`pin_memory()`) to run complex multimodal pipelines on consumer hardware without Out-Of-Memory (OOM) errors.


```

┌────────────────────────────────────────────────────────────────────────┐
│                        HOST SYSTEM RAM (16 GB)                         │
│  • OS & FastAPI Server (~3.5 GB)                                       │
│  • MiniMax Global 8B 4-bit AWQ (~4.5 GB Pinned)                        │
│  • MiniMax Flow Matching 2.4B INT8 (~2.5 GB Pinned)                    │
│  • Flow-VAE 123M (~0.25 GB Pinned)                                     │
└───────────────────────────────────┬────────────────────────────────────┘
│ Non-blocking PCIe Transfer (~0.3s)
▼
┌────────────────────────────────────────────────────────────────────────┐
│                        GPU VRAM (8 GB RTX 3070)                        │
│                                                                        │
│  PHASE 1: Qwen3.5-4B VLM Indexing & Story Plan  ──► ~3.0 GB VRAM       │
│  PHASE 2a: MiniMax LLM Semantic Token Gen        ──► ~5.7 GB VRAM      │
│  PHASE 2b: MiniMax Flow Matching Latent Diff     ──► ~3.5 GB VRAM      │
│  PHASE 2c: MiniMax Flow-VAE 32kHz WAV Decode     ──► ~0.5 GB VRAM      │
│  PHASE 3: Demucs + MMS_FA Lyric Alignment       ──► ~1.0 GB VRAM/CPU  │
│  PHASE 4: NVENC Hardware-Accelerated Render     ──► ~1.5 GB VRAM      │
└────────────────────────────────────────────────────────────────────────┘

```

---

## Hardware Requirements

* **GPU:** NVIDIA RTX 3070 / RTX 4060 Ti or better (**8 GB VRAM minimum**).
* **System RAM:** 16 GB DDR4/DDR5.
* **Storage:** Fast NVMe SSD with $\ge$ 40 GB free space for weights and cache.
* **OS:** Windows 10/11 (with CUDA 12.x) or Linux (Ubuntu 22.04+).

---

## Installation & Setup

### 1. Prerequisites
Ensure you have **Python 3.11+**, **CUDA Toolkit 12.x**, and **FFmpeg** (compiled with `h264_nvenc` support) installed.

```bash
# Verify FFmpeg NVENC support
ffmpeg -encoders | grep nvenc

```

### 2. Clone Repository & Install Dependencies

```bash
git clone [https://github.com/your-username/balladeer.git](https://github.com/your-username/balladeer.git)
cd balladeer

# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: .\venv\Scripts\activate

# Install PyTorch with CUDA support
pip install torch torchvision torchaudio --index-url [https://download.pytorch.org/whl/cu121](https://download.pytorch.org/whl/cu121)

# Install core dependencies
pip install -r requirements.txt

```

### 3. Download Model Weights

Run the download helper script to fetch and quantize model checkpoints to your local storage:

```bash
python scripts/download_weights.py --models qwen3.5-4b minimax-music3 clip-vit

```

---

## Quickstart

### Launching the Web Server

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

```

Navigate to `http://localhost:8000` to access the interactive web interface.

### Running via CLI

You can also generate montages programmatically using the CLI:

```bash
python -m balladeer.cli \
  --media-dir "./trips/japan_2026" \
  --diary "./trips/japan_2026/diary.txt" \
  --music-mode "vocal" \
  --min-quality 6.5 \
  --output "japan_montage.mp4"

```

---

## Project Structure

```
balladeer/
├── app/
│   ├── api/                  # FastAPI REST routes (projects, assets, timeline)
│   ├── core/                 # Config and hardware memory manager
│   ├── database/             # SQLite & sqlite-vec ORM schemas
│   ├── models/               # PyTorch wrappers for Qwen3.5, MiniMax, Demucs
│   ├── pipeline/
│   │   ├── indexer.py        # Scene detection & VLM batch captioning
│   │   ├── music_gen.py      # RAM-resident staged MiniMax pipeline
│   │   ├── aligner.py        # Demucs separation + MMS_FA forced alignment
│   │   ├── beat_solver.py    # Librosa beat tracker & constraint solver
│   │   └── compositor.py     # MoviePy v2 & FFmpeg NVENC assembly
│   └── main.py               # Application entrypoint
├── web/                      # React / Tailwind frontend application
├── scripts/                  # Model downloaders and utility scripts
├── requirements.txt
└── README.md

```

---

## Pipeline Breakdown

1. **Ingest & Index:** `indexer.py` extracts EXIF timestamps, samples scene-change keyframes, and runs `Qwen3.5-4B` to score media quality and generate semantic tags.
2. **Compose & Synthesize:** `music_gen.py` formats the story into verse-by-verse event lyrics and runs MiniMax Music 3 using staged RAM-to-GPU memory swapping.
3. **Demix & Align:** `aligner.py` isolates vocals via Demucs and uses TorchAudio's `MMS_FA` trellis aligner to calculate exact word start/end timestamps for ground-truth lyrics.
4. **Solve Timeline:** `beat_solver.py` snaps lyric boundaries to the Librosa beat grid and allocates media assets (photos: 1–3 beats, videos: 2–5 beats) based on chronological constraints and CLIP cosine similarity.
5. **Preview & Export:** The interactive UI allows fine-tuning before `compositor.py` renders the final video with synced `.ass` karaoke subtitles and Ken Burns pan/zoom effects.

---

## Configuration (`config.yaml`)

```yaml
hardware:
  device: "cuda:0"
  max_vram_gb: 8.0
  pinned_ram_gb: 12.0

indexing:
  vlm_model: "Qwen/Qwen3.5-4B-Instruct-AWQ"
  quality_threshold: 6.0
  scene_detection_threshold: 0.3

audio:
  music_model: "MiniMaxAI/MiniMax-Music3"
  sample_rate: 32000
  beat_snap_tolerance_sec: 0.25

video:
  resolution: [1920, 1080]
  fps: 30
  photo_beat_range: [1, 3]
  video_beat_range: [2, 5]
  nvenc_preset: "p6"

```

---

## License

Distributed under the **Apache-2.0 license**. See `LICENSE` for details.


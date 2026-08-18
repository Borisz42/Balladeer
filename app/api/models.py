import os
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

from app.core.config import get_settings
from app.core.memory_manager import memory_manager
from scripts.download_weights import download_model, MODELS_INFO

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/models", tags=["models"])

class DownloadModelRequest(BaseModel):
    model_name: str
    token: Optional[str] = None

@router.get("/status")
def get_models_status() -> Dict[str, Any]:
    """
    Returns the real-time cache and readiness status for all pipeline models.
    """
    settings = get_settings()
    torch_hub_dir = Path(os.environ.get("TORCH_HOME", Path.home() / ".cache" / "torch"))
    hf_hub_dir = Path(os.environ.get("HF_HOME", Path.home() / ".cache" / "huggingface" / "hub"))
    local_weights_dir = settings.data_dir / "weights"

    status = {}
    for key, info in MODELS_INFO.items():
        is_cached = False
        cached_path = None

        if key == "mms-fa":
            mms_pts = [
                torch_hub_dir / "hub" / "checkpoints" / "model.pt",
                torch_hub_dir / "checkpoints" / "model.pt",
                local_weights_dir / "mms-fa"
            ]
            for p in mms_pts:
                if p.exists():
                    is_cached = True
                    cached_path = str(p)
                    break
        elif key == "demucs":
            demucs_candidates = [
                hf_hub_dir / "models--adefossez--HTDemucs",
                torch_hub_dir / "hub" / "checkpoints",
                local_weights_dir / "demucs"
            ]
            for p in demucs_candidates:
                if p.exists() and (p.is_dir() and any(p.iterdir())):
                    is_cached = True
                    cached_path = str(p)
                    break
        elif key == "siglip2":
            repo_slug = "models--" + info["repo_id"].replace("/", "--")
            siglip_candidates = [
                hf_hub_dir / repo_slug,
                local_weights_dir / "siglip2"
            ]
            for p in siglip_candidates:
                if p.exists():
                    is_cached = True
                    cached_path = str(p)
                    break
        elif key == "minimax-music3":
            cmf_file = local_weights_dir / "minimax-music3" / "minimax-music3-q4tp.cmf"
            mm_dir = local_weights_dir / "minimax-music3"
            if cmf_file.exists():
                is_cached = True
                cached_path = str(cmf_file)
            elif mm_dir.exists() and any(mm_dir.glob("*.cmf")):
                is_cached = True
                cached_path = str(list(mm_dir.glob("*.cmf"))[0])
            elif mm_dir.exists() and any(mm_dir.glob("*.safetensors")):
                is_cached = True
                cached_path = str(list(mm_dir.glob("*.safetensors"))[0])
        else:
            repo_slug = "models--" + info["repo_id"].replace("/", "--")
            hf_cand = hf_hub_dir / repo_slug
            local_cand = local_weights_dir / key
            if hf_cand.exists() or local_cand.exists():
                is_cached = True
                cached_path = str(hf_cand if hf_cand.exists() else local_cand)

        exec_mode = (
            "ComfyUI CMF Staged (Local ~6GB)" if (key == "minimax-music3" and is_cached)
            else "Local Checkpoint Staged" if is_cached
            else "Hugging Face Free API / Fallback Synthesizer"
        )

        status[key] = {
            "name": key,
            "description": info["description"],
            "repo_id": info["repo_id"],
            "ram_gb": info["ram_gb"],
            "vram_gb": info["vram_gb"],
            "is_cached": is_cached,
            "cached_path": cached_path,
            "execution_mode": exec_mode
        }

    return {
        "models": status,
        "hardware": {
            "device": str(memory_manager.device),
            "is_cuda": memory_manager.is_cuda,
            "vram_stats": memory_manager.get_vram_usage()
        }
    }

@router.post("/download")
def trigger_model_download(req: DownloadModelRequest, background_tasks: BackgroundTasks):
    if req.model_name not in MODELS_INFO and req.model_name != "all":
        raise HTTPException(status_code=400, detail=f"Unknown model {req.model_name}")

    dest_dir = get_settings().data_dir / "weights"

    def do_download():
        targets = list(MODELS_INFO.keys()) if req.model_name == "all" else [req.model_name]
        for t in targets:
            try:
                download_model(t, dest_dir, token=req.token)
            except Exception as e:
                logger.error(f"Download error for {t}: {e}")

    background_tasks.add_task(do_download)
    return {"status": "started", "model": req.model_name}

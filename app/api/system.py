import os
import sys
import signal
import asyncio
import logging
from typing import Optional, Dict, Any
from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

from app.database.database import db
from app.core.memory_manager import memory_manager
from app.core.config import get_settings, reload_settings, save_dotenv_var
from app.models.model_router import model_router

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/system", tags=["system"])

class UpdateSettingsRequest(BaseModel):
    gemini_api_key: Optional[str] = None
    only_local_ai: Optional[bool] = None
    local_model: Optional[str] = None

@router.get("/settings")
def get_system_settings() -> Dict[str, Any]:
    """
    Returns current active system configuration, API key status, local model choice, and real-time model quotas.
    """
    settings = get_settings()
    has_key = bool(settings.google_ai.api_key.strip())
    masked_key = ""
    if has_key:
        key_str = settings.google_ai.api_key.strip()
        masked_key = key_str[:4] + "..." + key_str[-4:] if len(key_str) > 8 else "****"

    return {
        "has_gemini_api_key": has_key,
        "masked_gemini_api_key": masked_key,
        "only_local_ai": settings.google_ai.only_local_ai,
        "local_model": settings.indexing.local_model,
        "batch_size": settings.google_ai.batch_size,
        "quotas": model_router.get_all_quotas_status()
    }

@router.post("/settings")
def update_system_settings(req: UpdateSettingsRequest) -> Dict[str, Any]:
    """
    Updates the Google AI Studio API key, local AI mode toggle, and/or local model choice, persisting to untracked .env file.
    """
    if req.gemini_api_key is not None:
        save_dotenv_var("GEMINI_API_KEY", req.gemini_api_key.strip())
        logger.info("[SYSTEM] Updated GEMINI_API_KEY in .env")

    if req.only_local_ai is not None:
        save_dotenv_var("BALLADEER_ONLY_LOCAL_AI", "true" if req.only_local_ai else "false")
        logger.info(f"[SYSTEM] Updated BALLADEER_ONLY_LOCAL_AI={req.only_local_ai} in .env")

    if req.local_model is not None:
        save_dotenv_var("BALLADEER_LOCAL_MODEL", req.local_model.strip())
        logger.info(f"[SYSTEM] Updated BALLADEER_LOCAL_MODEL={req.local_model} in .env")
        try:
            from app.models.local_vlm import local_vlm
            local_vlm.reload_model()
        except Exception:
            pass

    reload_settings()
    return get_system_settings()


_shutdown_completed = False

def perform_clean_shutdown():
    global _shutdown_completed
    if _shutdown_completed:
        return
    _shutdown_completed = True

    logger.info("================================================================")
    logger.info("   Balladeer: Performing Graceful System Cleanup & Shutdown...  ")
    logger.info("================================================================")
    
    # 1. Flush SQLite WAL and close database connections
    try:
        with db.get_connection() as conn:
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")
            logger.info("✓ SQLite WAL checkpointed and flushed.")
    except Exception as e:
        logger.debug(f"DB checkpoint notice: {e}")

    # 2. Release GPU VRAM and pinned host memory
    try:
        memory_manager.flush_vram()
        logger.info("✓ GPU VRAM and pinned host memory buffers released.")
    except Exception as e:
        logger.debug(f"VRAM cleanup notice: {e}")

    logger.info("✓ System ready for exit. Goodbye!")

async def async_shutdown_process():
    await asyncio.sleep(0.5)
    perform_clean_shutdown()
    # Trigger exit signal to uvicorn/process
    if sys.platform == "win32":
        try:
            os.kill(os.getpid(), signal.SIGINT)
        except Exception:
            pass
        await asyncio.sleep(0.8)
        os._exit(0)
    else:
        try:
            os.kill(os.getpid(), signal.SIGTERM)
        except Exception:
            pass
        await asyncio.sleep(0.8)
        os._exit(0)

@router.post("/shutdown")
async def shutdown_server(background_tasks: BackgroundTasks):
    """
    Cleanly shuts down the Balladeer FastAPI backend and releases all system/GPU resources.
    """
    logger.info("[SYSTEM] Received graceful shutdown request from UI.")
    background_tasks.add_task(async_shutdown_process)
    return {
        "status": "shutting_down",
        "message": "Balladeer server is shutting down cleanly and releasing all GPU resources."
    }

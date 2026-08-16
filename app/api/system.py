import os
import sys
import signal
import asyncio
import logging
from fastapi import APIRouter, BackgroundTasks
from app.database.database import db
from app.core.memory_manager import memory_manager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/system", tags=["system"])

def perform_clean_shutdown():
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

    # 3. Terminate background ComfyUI worker if running
    try:
        from app.models.comfy_music_worker import comfy_music_worker
        comfy_music_worker.shutdown()
    except Exception as e:
        logger.debug(f"ComfyUI cleanup notice: {e}")

    logger.info("✓ System ready for exit. Goodbye!")

async def async_shutdown_process():
    await asyncio.sleep(0.5)
    perform_clean_shutdown()
    # Trigger SIGINT/SIGTERM to uvicorn
    if sys.platform == "win32":
        # Windows graceful exit
        os.kill(os.getpid(), signal.SIGINT)
    else:
        os.kill(os.getpid(), signal.SIGTERM)

@router.post("/shutdown")
async def shutdown_server(background_tasks: BackgroundTasks):
    """
    Cleanly shuts down the Balladeer FastAPI backend and releases all system/GPU resources.
    """
    logger.info("[SYSTEM] Received graceful shutdown request from UI.")
    background_tasks.add_task(async_shutdown_process)
    return {
        "status": "shutting_down",
        "message": "Balladeer server is shutting down cleanly. You may now close this browser tab."
    }

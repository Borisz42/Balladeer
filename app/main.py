import logging
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.core.logging_config import setup_logging
from app.core.config import get_settings
from app.core.memory_manager import memory_manager
from app.api.projects import router as projects_router
from app.api.timeline import router as timeline_router
from app.api.progress import router as progress_router
from app.api.models import router as models_router
from app.api.system import router as system_router, perform_clean_shutdown

# Initialize dual console + timestamped file logging in logs/
setup_logging()
logger = logging.getLogger("balladeer.server")

settings = get_settings()
settings.ensure_directories()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("================================================================")
    logger.info("   Balladeer Server Initialized (Ready on http://localhost:8000)")
    logger.info("================================================================")
    
    # Suppress harmless Windows Proactor socket disconnect errors when clients refresh/disconnect
    import asyncio
    try:
        loop = asyncio.get_running_loop()
        def _asyncio_exception_handler(current_loop, context):
            exc = context.get("exception")
            if isinstance(exc, (ConnectionResetError, BrokenPipeError, ConnectionAbortedError)):
                return
            current_loop.default_exception_handler(context)
        loop.set_exception_handler(_asyncio_exception_handler)
    except Exception:
        pass

    # Asynchronously pre-warm local AI engines in background (SigLIP 2 followed by Local VLM)
    from app.models.siglip_embedder import siglip_embedder
    from app.models.local_vlm import local_vlm

    async def _startup_prewarm():
        try:
            # 1. Prewarm SigLIP 2 (~0.8 GB VRAM)
            await siglip_embedder.prewarm_async()
            # 2. Prewarm Local VLM (~2.2 GB VRAM)
            await local_vlm.prewarm_async()
        except Exception as err:
            logger.warning(f"[Startup] AI prewarming note: {err}")

    asyncio.create_task(_startup_prewarm())

    yield
    # Graceful Shutdown on Ctrl+C or /api/system/shutdown
    perform_clean_shutdown()

app = FastAPI(
    title="Balladeer API",
    description="Local AI Beat-Synced Video Montage Engine Backend",
    version="0.2.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(projects_router)
app.include_router(timeline_router)
app.include_router(progress_router)
app.include_router(models_router)
app.include_router(system_router)

app.mount("/static/uploads", StaticFiles(directory=str(settings.uploads_dir)), name="uploads")
app.mount("/static/output", StaticFiles(directory=str(settings.output_dir)), name="output")

@app.get("/api/health")
def health_check():
    vram = memory_manager.get_vram_usage()
    return {
        "status": "healthy",
        "cuda_available": memory_manager.is_cuda,
        "device": str(memory_manager.device),
        "vram_stats": vram,
        "loading_model": memory_manager.loading_model,
        "loaded_models": memory_manager.loaded_models,
        "config": {
            "resolution": settings.video.resolution,
            "photo_beat_range": settings.video.photo_beat_range,
            "video_beat_range": settings.video.video_beat_range,
            "default_bg_mode": settings.video.default_bg_mode,
            "enable_ken_burns": settings.video.enable_ken_burns
        }
    }

web_dist = settings.project_root / "web" / "dist"
if web_dist.exists():
    app.mount("/", StaticFiles(directory=str(web_dist), html=True), name="frontend")

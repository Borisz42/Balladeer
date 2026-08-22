import asyncio
import json
import logging
from typing import Dict, Set
from fastapi import APIRouter
from fastapi.responses import StreamingResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/progress", tags=["progress"])

class ProgressTracker:
    def __init__(self):
        self._queues: Dict[str, Set[asyncio.Queue]] = {}

    def subscribe(self, project_id: str) -> asyncio.Queue:
        q = asyncio.Queue()
        if project_id not in self._queues:
            self._queues[project_id] = set()
        self._queues[project_id].add(q)
        return q

    def unsubscribe(self, project_id: str, q: asyncio.Queue):
        if project_id in self._queues:
            self._queues[project_id].discard(q)
            if not self._queues[project_id]:
                del self._queues[project_id]

    async def emit(self, project_id: str, phase: str, progress: float, message: str):
        if project_id in self._queues:
            payload = json.dumps({
                "project_id": project_id,
                "phase": phase,
                "progress": round(progress, 1),
                "message": message
            })
            for q in list(self._queues[project_id]):
                await q.put(payload)

progress_tracker = ProgressTracker()

@router.get("/{project_id}")
async def sse_progress(project_id: str):
    """
    Server-Sent Events endpoint streaming real-time pipeline progress updates.
    """
    queue = progress_tracker.subscribe(project_id)

    async def event_generator():
        try:
            # Initial handshake event
            yield f"event: connected\ndata: {json.dumps({'project_id': project_id, 'status': 'connected'})}\n\n"
            while True:
                try:
                    data = await queue.get()
                    yield f"event: progress\ndata: {data}\n\n"
                except (asyncio.CancelledError, ConnectionResetError, BrokenPipeError):
                    break
        except (asyncio.CancelledError, ConnectionResetError, BrokenPipeError):
            pass
        finally:
            progress_tracker.unsubscribe(project_id, queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )

import time
import asyncio
import logging
from typing import Dict, Any, List, Optional, Tuple, Callable, Coroutine
from enum import Enum
from dataclasses import dataclass, field

from app.core.config import get_settings
from app.core.memory_manager import memory_manager

logger = logging.getLogger("balladeer.model_router")

class TaskType(str, Enum):
    VISION_BATCH = "vision_batch"
    STORY_LYRICS = "story_lyrics"

@dataclass
class ModelQuota:
    name: str
    rpm_limit: int
    tpm_limit: int
    rpd_limit: int
    is_local: bool = False
    
    # 60-second sliding window tracking
    request_timestamps: List[float] = field(default_factory=list)
    token_usage_timestamps: List[Tuple[float, int]] = field(default_factory=list)
    
    # Daily counter tracking
    daily_count: int = 0
    daily_reset_time: float = field(default_factory=lambda: time.time() + 86400)

    def _purge_old_windows(self, now: float) -> None:
        cutoff = now - 60.0
        self.request_timestamps = [t for t in self.request_timestamps if t > cutoff]
        self.token_usage_timestamps = [(t, count) for (t, count) in self.token_usage_timestamps if t > cutoff]
        
        if now >= self.daily_reset_time:
            self.daily_count = 0
            self.daily_reset_time = now + 86400

    def is_available(self, estimated_tokens: int = 1000) -> bool:
        if self.is_local:
            return True

        now = time.time()
        self._purge_old_windows(now)

        if self.daily_count >= self.rpd_limit:
            return False

        if len(self.request_timestamps) >= self.rpm_limit:
            return False

        current_tpm = sum(count for (_, count) in self.token_usage_timestamps)
        if current_tpm + estimated_tokens > self.tpm_limit:
            return False

        return True

    def record_usage(self, token_count: int = 1000) -> None:
        if self.is_local:
            return

        now = time.time()
        self.request_timestamps.append(now)
        self.token_usage_timestamps.append((now, token_count))
        self.daily_count += 1

    def get_status(self) -> Dict[str, Any]:
        now = time.time()
        self._purge_old_windows(now)
        current_tpm = sum(count for (_, count) in self.token_usage_timestamps)
        return {
            "name": self.name,
            "current_rpm": len(self.request_timestamps),
            "rpm_limit": self.rpm_limit,
            "current_tpm": current_tpm,
            "tpm_limit": self.tpm_limit,
            "daily_count": self.daily_count,
            "rpd_limit": self.rpd_limit,
            "is_local": self.is_local,
            "is_available": self.is_available(100)
        }

class IntelligentModelRouter:
    """
    Intelligent Multi-Tier Model Dispatcher.
    Dynamically routes tasks across Google AI Studio free tier quotas (Flash Lite, Gemma)
    and falls back smoothly to local quantized Qwen3.5-4B on the RTX 3070.
    """

    def __init__(self):
        self.lock = asyncio.Lock()
        self.local_vlm_fallback: Optional[Callable] = None
        self.local_story_fallback: Optional[Callable] = None

        # Quotas based on official Google AI Studio Free Tier specifications
        self.models: Dict[str, ModelQuota] = {
            "gemini-3.5-flash-lite": ModelQuota("gemini-3.5-flash-lite", rpm_limit=15, tpm_limit=250_000, rpd_limit=500),
            "gemini-3.1-flash-lite": ModelQuota("gemini-3.1-flash-lite", rpm_limit=15, tpm_limit=250_000, rpd_limit=500),
            "gemini-2.5-flash-lite": ModelQuota("gemini-2.5-flash-lite", rpm_limit=10, tpm_limit=250_000, rpd_limit=20),
            "gemini-3.7-flash":      ModelQuota("gemini-3.7-flash",      rpm_limit=5,  tpm_limit=250_000, rpd_limit=20),
            "gemini-3.6-flash":      ModelQuota("gemini-3.6-flash",      rpm_limit=5,  tpm_limit=250_000, rpd_limit=20),
            "gemini-3.5-flash":      ModelQuota("gemini-3.5-flash",      rpm_limit=5,  tpm_limit=250_000, rpd_limit=20),
            "gemma-4-31b":           ModelQuota("gemma-4-31b",           rpm_limit=30, tpm_limit=16_000,  rpd_limit=14_400),
            "gemma-4-26b":           ModelQuota("gemma-4-26b",           rpm_limit=30, tpm_limit=16_000,  rpd_limit=14_400),
            "local-qwen2.5-vl-3b":   ModelQuota("local-qwen2.5-vl-3b",   rpm_limit=999, tpm_limit=999_999, rpd_limit=999_999, is_local=True),
            "local-qwen3.5-4b":      ModelQuota("local-qwen3.5-4b",      rpm_limit=999, tpm_limit=999_999, rpd_limit=999_999, is_local=True),
            "local-qwen3.5-9b":      ModelQuota("local-qwen3.5-9b",      rpm_limit=999, tpm_limit=999_999, rpd_limit=999_999, is_local=True),
        }

        self.waterfalls = {
            TaskType.VISION_BATCH: [
                "gemini-3.5-flash-lite",
                "gemini-3.1-flash-lite",
                "gemini-3.6-flash",
                "gemini-3.5-flash",
                "gemini-3.7-flash",
                "gemma-4-31b",
                "local-qwen2.5-vl-3b",
            ],
            TaskType.STORY_LYRICS: [
                "gemini-3.5-flash-lite",
                "gemini-3.6-flash",
                "gemini-3.5-flash",
                "gemini-3.7-flash",
                "gemma-4-31b",
                "gemma-4-26b",
                "local-qwen3.5-9b",
            ],
        }


    async def _execute_local(self, task_type: TaskType, payload: Any, custom_fallback: Optional[Callable] = None) -> Any:
        func = custom_fallback
        if not func:
            if task_type == TaskType.VISION_BATCH and self.local_vlm_fallback:
                func = self.local_vlm_fallback
            elif task_type == TaskType.STORY_LYRICS and self.local_story_fallback:
                func = self.local_story_fallback

        if func:
            model_display_name = "Qwen 2.5 VL (3B)" if task_type == TaskType.VISION_BATCH else "Qwen 3.5 (9B)"
            memory_manager.set_loading(model_display_name)
            try:
                if asyncio.iscoroutinefunction(func):
                    res = await func(payload)
                else:
                    # Offload heavy synchronous GPU / CPU execution to worker thread
                    res = await asyncio.to_thread(func, payload)
                return res
            finally:
                memory_manager.set_loading(None)

        raise RuntimeError(f"No local fallback registered for task {task_type}")

    async def execute_task(
        self,
        task_type: TaskType,
        prompt_payload: Any,
        estimated_tokens: int = 1000,
        cloud_caller: Optional[Callable[[str, Any], Coroutine]] = None,
        local_fallback: Optional[Callable[[Any], Any]] = None,
    ) -> Tuple[Any, str]:
        """
        Finds the best available model in the waterfall, tracks quota, and executes with fallback.
        Returns a tuple: (result, executing_model_name).
        """
        settings = get_settings()
        api_key = settings.google_ai.api_key.strip()
        only_local = settings.google_ai.only_local_ai or not api_key

        active_local_slug = "local-qwen2.5-vl-3b" if task_type == TaskType.VISION_BATCH else "local-qwen3.5-9b"

        if only_local or cloud_caller is None:
            logger.info(f"[Router] [{task_type.value}] Only-Local mode active (only_local_ai={only_local}). Routing directly to {active_local_slug} engine.")
            res = await self._execute_local(task_type, prompt_payload, local_fallback)
            return res, active_local_slug

        candidate_chain = self.waterfalls.get(task_type, [active_local_slug])

        for model_name in candidate_chain:
            if model_name.startswith("local-"):
                break

            # Check quota availability under lock
            async with self.lock:
                model_quota = self.models.get(model_name)
                is_avail = model_quota.is_available(estimated_tokens) if model_quota else False
                if is_avail:
                    # Optimistically reserve slot to prevent race conditions across parallel workers
                    model_quota.record_usage(estimated_tokens)

            if is_avail:
                try:
                    logger.info(f"[Router] [{task_type.value}] Dispatching request to cloud model '{model_name}' (Est. Tokens: {estimated_tokens})...")
                    res = await cloud_caller(model_name, prompt_payload)
                    logger.info(f"[Router] [{task_type.value}] ✓ Successfully executed task via '{model_name}'")
                    return res, model_name
                except Exception as err:
                    logger.warning(f"[Router] [{task_type.value}] Call to '{model_name}' failed: {err}. Cascading to next tier in waterfall...")
                    continue

        logger.warning(f"[Router] [{task_type.value}] All cloud waterfall models exhausted/unavailable. Executing {active_local_slug} fallback...")
        res = await self._execute_local(task_type, prompt_payload, local_fallback)
        return res, active_local_slug


    def get_all_quotas_status(self) -> Dict[str, Any]:
        return {name: quota.get_status() for name, quota in self.models.items()}

# Global router singleton
model_router = IntelligentModelRouter()

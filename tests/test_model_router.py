import pytest
import asyncio
import time
from unittest.mock import AsyncMock, patch

from app.models.model_router import IntelligentModelRouter, ModelQuota, TaskType
from app.core.config import get_settings, reload_settings

def test_model_quota_sliding_window():
    quota = ModelQuota("test-model", rpm_limit=2, tpm_limit=5000, rpd_limit=10)

    # 1. First request
    assert quota.is_available(estimated_tokens=1000) is True
    quota.record_usage(1000)

    # 2. Second request
    assert quota.is_available(estimated_tokens=1000) is True
    quota.record_usage(1000)

    # 3. Third request within same minute should be rejected (RPM limit = 2)
    assert quota.is_available(estimated_tokens=1000) is False

    # 4. If tokens exceed TPM limit
    quota2 = ModelQuota("test-tpm", rpm_limit=10, tpm_limit=2000, rpd_limit=10)
    assert quota2.is_available(estimated_tokens=1500) is True
    quota2.record_usage(1500)
    assert quota2.is_available(estimated_tokens=1000) is False # 1500 + 1000 > 2000

def test_model_router_waterfall_fallback():
    async def _run():
        async def mock_local_fallback(payload):
            return {"result": "local_executed", "payload": payload}

        router = IntelligentModelRouter()
        router.local_vlm_fallback = mock_local_fallback

        # Mock cloud caller that fails
        mock_cloud = AsyncMock(side_effect=RuntimeError("Cloud API 429 rate limit reached"))

        res, model_used = await router.execute_task(
            task_type=TaskType.VISION_BATCH,
            prompt_payload=["img1.jpg", "img2.jpg"],
            estimated_tokens=1000,
            cloud_caller=mock_cloud,
            local_fallback=mock_local_fallback
        )

        assert res["result"] == "local_executed"
        assert "qwen" in model_used.lower()

    asyncio.run(_run())

def test_model_router_only_local_ai_mode():
    async def _run():
        called_cloud = False

        async def mock_cloud_caller(model_name, payload):
            nonlocal called_cloud
            called_cloud = True
            return {"result": "cloud", "model": model_name}

        async def mock_local(payload):
            return {"result": "local_fallback"}

        router = IntelligentModelRouter()
        router.local_vlm_fallback = mock_local

        settings = get_settings()
        settings.google_ai.only_local_ai = True
        settings.google_ai.api_key = "AIzaFakeKey123"

        try:
            res, model_used = await router.execute_task(
                task_type=TaskType.VISION_BATCH,
                prompt_payload=["img1.jpg"],
                estimated_tokens=500,
                cloud_caller=mock_cloud_caller,
                local_fallback=mock_local
            )
            assert res["result"] == "local_fallback"
            assert "qwen" in model_used.lower()
            assert called_cloud is False
        finally:
            settings.google_ai.only_local_ai = False


    asyncio.run(_run())

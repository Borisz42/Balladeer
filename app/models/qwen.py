"""
Bridge module for backward compatibility with qwen module imports.
Points directly to unified config-driven local_vlm runner.
"""
from app.models.local_vlm import (
    local_vlm,
    LocalVLMRunner,
    qwen_runner,
    qwen_vlm,
    qwen_llm,
    QwenRunner,
    QwenVLMRunner,
    QwenLLMRunner,
)

__all__ = [
    "local_vlm",
    "LocalVLMRunner",
    "qwen_runner",
    "qwen_vlm",
    "qwen_llm",
    "QwenRunner",
    "QwenVLMRunner",
    "QwenLLMRunner",
]

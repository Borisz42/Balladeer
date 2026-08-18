import gc
import logging
from contextlib import contextmanager
from typing import Optional, Dict, Any, List
import torch

logger = logging.getLogger(__name__)

class GPUMemoryManager:
    """
    Manages GPU VRAM allocation, host RAM pinned memory staging, 
    and PCIe DMA transfers to maintain the strict 8GB VRAM / 16GB RAM budget.
    """

    def __init__(self, device: str = "cuda:0", max_vram_gb: float = 8.0):
        self.device_str = device if torch.cuda.is_available() else "cpu"
        self.max_vram_gb = max_vram_gb
        self.device = torch.device(self.device_str)
        self._current_phase: Optional[str] = None
        self._loading_model: Optional[str] = None
        self._loaded_models: Dict[str, str] = {}

    @property
    def is_cuda(self) -> bool:
        return self.device.type == "cuda"

    @property
    def loading_model(self) -> Optional[str]:
        return self._loading_model

    @property
    def loaded_models(self) -> List[str]:
        return list(self._loaded_models.values())

    def set_loading(self, model_name: Optional[str]) -> None:
        self._loading_model = model_name
        if model_name:
            logger.info(f"[GPU-Status] ⏳ Loading model into GPU: {model_name}...")
        else:
            logger.debug("[GPU-Status] Model loading state cleared.")

    def set_loaded(self, key: str, display_name: str) -> None:
        self._loaded_models[key] = display_name
        self._loading_model = None
        logger.info(f"[GPU-Status] ✓ Model loaded in VRAM: {display_name}")

    def remove_loaded(self, key: str) -> None:
        if key in self._loaded_models:
            del self._loaded_models[key]

    def get_vram_usage(self) -> Dict[str, float]:
        """Returns allocated, reserved, and total VRAM in GB."""
        if not self.is_cuda:
            return {"allocated_gb": 0.0, "reserved_gb": 0.0, "total_gb": 0.0, "free_gb": 0.0}
        
        try:
            device_idx = self.device.index if self.device.index is not None else 0
            allocated = torch.cuda.memory_allocated(device_idx) / (1024 ** 3)
            reserved = torch.cuda.memory_reserved(device_idx) / (1024 ** 3)
            total = torch.cuda.get_device_properties(device_idx).total_memory / (1024 ** 3)
            free = total - reserved
            return {
                "allocated_gb": round(allocated, 3),
                "reserved_gb": round(reserved, 3),
                "total_gb": round(total, 3),
                "free_gb": round(free, 3)
            }
        except Exception as e:
            logger.warning(f"Failed to query CUDA memory: {e}")
            return {"allocated_gb": 0.0, "reserved_gb": 0.0, "total_gb": 0.0, "free_gb": 0.0}

    def pin_tensor(self, tensor: torch.Tensor) -> torch.Tensor:
        """Pins a host CPU tensor in page-locked RAM for fast PCIe transfer."""
        if tensor.is_cuda or not self.is_cuda:
            return tensor
        if not tensor.is_pinned():
            try:
                return tensor.pin_memory()
            except Exception as e:
                logger.debug(f"Could not pin tensor: {e}")
                return tensor
        return tensor

    def stage_to_device(self, obj: Any, non_blocking: bool = True) -> Any:
        """Transfers a tensor or PyTorch module to the target device."""
        if hasattr(obj, "to"):
            return obj.to(self.device, non_blocking=non_blocking and self.is_cuda)
        return obj

    def purge_gpu(self) -> None:
        """Forces garbage collection and flushes cached PyTorch CUDA allocations."""
        gc.collect()
        if self.is_cuda:
            torch.cuda.empty_cache()
            torch.cuda.ipc_collect()
            torch.cuda.synchronize()
        logger.debug("GPU VRAM purged and synchronized.")

    @contextmanager
    def phase(self, name: str):
        """Context manager to scope a pipeline phase and auto-purge VRAM on completion."""
        self._current_phase = name
        start_stats = self.get_vram_usage()
        logger.info(f"==> Starting Phase: {name} (VRAM: {start_stats.get('allocated_gb')} GB used)")
        try:
            yield self
        finally:
            logger.info(f"<== Exiting Phase: {name}. Purging VRAM...")
            self.purge_gpu()
            end_stats = self.get_vram_usage()
            logger.info(f"    Purged: {name} (VRAM: {end_stats.get('allocated_gb')} GB used)")
            self._current_phase = None

memory_manager = GPUMemoryManager()

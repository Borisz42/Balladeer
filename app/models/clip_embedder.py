import os
import logging
from pathlib import Path
from typing import Any, List, Union, Optional
import numpy as np
from PIL import Image

# Suppress repetitive HuggingFace Hub network checks & symlink warnings
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

from app.core.config import get_settings
from app.core.memory_manager import memory_manager

logger = logging.getLogger("balladeer.clip")

class CLIPEmbedder:
    """
    High-Performance CLIP ViT-B-32 Vector Embeddings Generator (512-dim).
    Runs on NVIDIA CUDA / RTX 3070 with offline caching to prevent HF Hub network calls.
    """

    def __init__(self):
        self._model = None

    def _get_model(self):
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
                settings = get_settings()
                device = "cuda" if memory_manager.is_cuda else "cpu"
                model_name = settings.indexing.clip_model

                # 1. Attempt offline load first to prevent internet HEAD requests
                try:
                    self._model = SentenceTransformer(model_name, device=device, local_files_only=True)
                    logger.info(f"Loaded CLIP {model_name} from local cache on {device}.")
                except Exception:
                    # 2. Download and cache if not present
                    hf_token = settings.huggingface.api_key or os.environ.get("HF_TOKEN") or None
                    self._model = SentenceTransformer(model_name, device=device, token=hf_token)
                    logger.info(f"Downloaded and cached CLIP {model_name} on {device}.")
            except Exception as e:
                logger.warning(f"CLIP model load note: {e}")
                self._model = None
        return self._model

    def encode(self, text_or_image: Union[str, Path, Image.Image]) -> List[float]:
        model = self._get_model()
        if model is not None:
            try:
                if isinstance(text_or_image, (str, Path)):
                    p_str = str(text_or_image)
                    if p_str.lower().endswith((".jpg", ".jpeg", ".png", ".webp")) and Path(p_str).exists():
                        with Image.open(p_str) as img:
                            emb = model.encode(img, normalize_embeddings=True)
                    else:
                        emb = model.encode(p_str, normalize_embeddings=True)
                elif isinstance(text_or_image, Image.Image):
                    emb = model.encode(text_or_image, normalize_embeddings=True)
                else:
                    emb = model.encode(str(text_or_image), normalize_embeddings=True)
                
                return emb.tolist()
            except Exception as e:
                logger.debug(f"CLIP encoding notice: {e}")

        # Deterministic fallback vector
        seed = abs(hash(str(text_or_image))) % (2**32)
        rng = np.random.RandomState(seed)
        vec = rng.randn(512).astype(np.float32)
        vec /= np.linalg.norm(vec)
        return vec.tolist()

    def encode_batch(self, items: List[Union[str, Path, Image.Image]]) -> List[List[float]]:
        model = self._get_model()
        if model is not None:
            try:
                prepared = []
                for item in items:
                    if isinstance(item, (str, Path)):
                        p_str = str(item)
                        if p_str.lower().endswith((".jpg", ".jpeg", ".png", ".webp")) and Path(p_str).exists():
                            with Image.open(p_str) as img:
                                prepared.append(img.convert("RGB"))
                        else:
                            prepared.append(p_str)
                    elif isinstance(item, Image.Image):
                        prepared.append(item.convert("RGB"))
                    else:
                        prepared.append(str(item))

                embeddings = model.encode(prepared, normalize_embeddings=True)
                return embeddings.tolist()
            except Exception as e:
                logger.debug(f"Batch CLIP encoding note: {e}")

        return [self.encode(item) for item in items]

clip_embedder = CLIPEmbedder()

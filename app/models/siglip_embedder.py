import os
import logging
from pathlib import Path
from typing import Any, List, Union, Optional, Tuple
import numpy as np
from PIL import Image, ImageOps

# Suppress repetitive HuggingFace Hub network checks & symlink warnings
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

from app.core.config import get_settings
from app.core.memory_manager import memory_manager

logger = logging.getLogger("balladeer.siglip")

class SigLIPEmbedder:
    """
    High-Performance SigLIP 2 Vector Embeddings & Aesthetic Scorer (google/siglip2-base-patch16-224).
    Outputs 768-dim L2-normalized embeddings for multi-modal travel indexing.
    Runs on NVIDIA CUDA / RTX 3070 with FP16 precision and offline caching.
    """

    def __init__(self):
        self._processor = None
        self._model = None
        self._device = None
        self._cached_pos_emb = None
        self._cached_neg_emb = None

    def clear_cache(self):
        """Releases SigLIP 2 model weights from memory / GPU VRAM."""
        self._processor = None
        self._model = None
        self._device = None
        self._cached_pos_emb = None
        self._cached_neg_emb = None
        memory_manager.remove_loaded("siglip")
        memory_manager.set_loading(None)

    async def preload_background(self):
        """Asynchronously pre-loads SigLIP 2 model into GPU VRAM in the background at startup."""
        import asyncio
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._get_processor_and_model)

    async def prewarm_async(self):
        """Alias for preload_background."""
        await self.preload_background()

    def _get_processor_and_model(self):
        if self._model is None or self._processor is None:
            try:
                import torch
                from transformers import AutoProcessor, AutoModel
                settings = get_settings()
                device = "cuda" if memory_manager.is_cuda else "cpu"
                self._device = device
                model_name = getattr(settings.indexing, "siglip_model", "google/siglip2-base-patch16-224")

                dtype = torch.float16 if device == "cuda" else torch.float32

                hf_hub_dir = Path(os.environ.get("HF_HOME", Path.home() / ".cache" / "huggingface" / "hub"))
                weights_root = settings.data_dir / "weights"
                repo_slug = "models--" + model_name.replace("/", "--")

                candidate_paths = [
                    hf_hub_dir / repo_slug,
                    hf_hub_dir / "siglip2",
                    weights_root / "siglip2"
                ]

                model_source = model_name
                for cp in candidate_paths:
                    if not cp.exists():
                        continue
                    if (cp / "config.json").exists():
                        model_source = str(cp)
                        break
                    snapshots_dir = cp / "snapshots"
                    if snapshots_dir.exists():
                        snapshot_subs = [p for p in snapshots_dir.iterdir() if p.is_dir() and (p / "config.json").exists()]
                        if snapshot_subs:
                            model_source = str(snapshot_subs[0])
                            break

                memory_manager.set_loading("SigLIP 2", key="siglip")

                # 1. Attempt offline load first
                try:
                    self._processor = AutoProcessor.from_pretrained(model_source, local_files_only=True)
                    self._model = AutoModel.from_pretrained(model_source, torch_dtype=dtype, local_files_only=True).to(device)
                    if device == "cuda":
                        memory_manager.set_loaded("siglip", "SigLIP 2 (CUDA)")
                        logger.info(f"[GPU] ✓ Loaded SigLIP 2 {model_name} from local cache on CUDA (FP16, ~0.8GB VRAM).")
                    else:
                        memory_manager.set_loaded("siglip", "SigLIP 2 (CPU)")
                        logger.warning(f"[CPU] ⚠️ CUDA not available. Loaded SigLIP 2 {model_name} on CPU (FP32).")
                except Exception:
                    # 2. Download and cache if not locally staged
                    hf_token = settings.huggingface.api_key or os.environ.get("HF_TOKEN") or None
                    self._processor = AutoProcessor.from_pretrained(model_name, token=hf_token)
                    self._model = AutoModel.from_pretrained(model_name, torch_dtype=dtype, token=hf_token).to(device)
                    if device == "cuda":
                        memory_manager.set_loaded("siglip", "SigLIP 2 (CUDA)")
                        logger.info(f"[GPU] ✓ Downloaded and initialized SigLIP 2 {model_name} on CUDA (FP16).")
                    else:
                        memory_manager.set_loaded("siglip", "SigLIP 2 (CPU)")
                        logger.warning(f"[CPU] ⚠️ CUDA not available. Initialized SigLIP 2 {model_name} on CPU (FP32).")

                if self._model is not None:
                    self._model.eval()

            except Exception as e:
                logger.warning(f"SigLIP 2 model load note: {e}")
                memory_manager.set_loading(None, key="siglip")
                self._processor = None
                self._model = None
                self._device = None

        return self._processor, self._model

    def encode_text(self, text: str) -> List[float]:
        """Encodes a single text string into a 768-dim normalized embedding."""
        res = self.encode_texts_batch([text])
        return res[0] if res else self._fallback_vector(text)

    def encode_texts_batch(self, texts: List[str]) -> List[List[float]]:
        """Encodes a batch of text strings into normalized embeddings."""
        if not texts:
            return []
        processor, model = self._get_processor_and_model()
        if processor is not None and model is not None:
            try:
                import torch
                inputs = processor(text=texts, padding="max_length", max_length=64, truncation=True, return_tensors="pt")
                inputs = {k: v.to(self._device) for k, v in inputs.items()}
                with torch.no_grad():
                    if hasattr(model, "get_text_features"):
                        text_features = model.get_text_features(**inputs)
                    else:
                        text_outputs = model.text_model(**inputs)
                        text_features = text_outputs.pooler_output if hasattr(text_outputs, "pooler_output") else text_outputs[0][:, 0]
                    # Normalize embeddings
                    text_features = text_features / text_features.norm(dim=-1, keepdim=True)
                return text_features.cpu().float().numpy().tolist()
            except Exception as e:
                logger.debug(f"SigLIP text batch encoding note: {e}")

        return [self._fallback_vector(t) for t in texts]

    def encode_image(self, image: Union[str, Path, Image.Image, np.ndarray]) -> List[float]:
        """Encodes a single image into a 768-dim normalized embedding (downscaled to 224x224)."""
        res = self.encode_images_batch([image])
        return res[0] if res else self._fallback_vector(str(image))

    def encode_images_batch(self, images: List[Union[str, Path, Image.Image, np.ndarray]]) -> List[List[float]]:
        """Encodes a batch of images into normalized embeddings."""
        if not images:
            return []
        processor, model = self._get_processor_and_model()
        if processor is not None and model is not None:
            try:
                import torch
                prepared_pil = []
                for item in images:
                    if isinstance(item, (str, Path)):
                        p = Path(item)
                        if p.exists():
                            with Image.open(p) as img:
                                img = ImageOps.exif_transpose(img) or img
                                prepared_pil.append(img.convert("RGB").resize((224, 224), Image.Resampling.BICUBIC))
                        else:
                            prepared_pil.append(Image.new("RGB", (224, 224), (128, 128, 128)))
                    elif isinstance(item, Image.Image):
                        prepared_pil.append(item.convert("RGB").resize((224, 224), Image.Resampling.BICUBIC))
                    elif isinstance(item, np.ndarray):
                        if len(item.shape) == 3 and item.shape[2] == 3:
                            rgb_arr = item[:, :, ::-1]
                            pil_img = Image.fromarray(rgb_arr).resize((224, 224), Image.Resampling.BICUBIC)
                            prepared_pil.append(pil_img)
                        else:
                            pil_img = Image.fromarray(item).convert("RGB").resize((224, 224), Image.Resampling.BICUBIC)
                            prepared_pil.append(pil_img)
                    else:
                        prepared_pil.append(Image.new("RGB", (224, 224), (128, 128, 128)))

                inputs = processor(images=prepared_pil, return_tensors="pt")
                inputs = {k: v.to(self._device) for k, v in inputs.items()}
                with torch.no_grad():
                    if hasattr(model, "get_image_features"):
                        image_features = model.get_image_features(**inputs)
                    else:
                        vision_outputs = model.vision_model(**inputs)
                        image_features = vision_outputs.pooler_output if hasattr(vision_outputs, "pooler_output") else vision_outputs[0][:, 0]
                    # Normalize embeddings
                    image_features = image_features / image_features.norm(dim=-1, keepdim=True)
                return image_features.cpu().float().numpy().tolist()
            except Exception as e:
                logger.debug(f"SigLIP image batch encoding note: {e}")

        return [self._fallback_vector(str(img)) for img in images]

    def encode(self, text_or_image: Union[str, Path, Image.Image, np.ndarray]) -> List[float]:
        """Universal multi-modal entry point: detects whether input is an image or text."""
        if isinstance(text_or_image, (Image.Image, np.ndarray)):
            return self.encode_image(text_or_image)
        
        if isinstance(text_or_image, (str, Path)):
            p_str = str(text_or_image)
            if p_str.lower().endswith((".jpg", ".jpeg", ".png", ".webp")) and Path(p_str).exists():
                return self.encode_image(p_str)
            return self.encode_text(p_str)

    def encode_batch(self, items: List[Union[str, Path, Image.Image, np.ndarray]]) -> List[List[float]]:
        """Encodes a heterogeneous batch of items (images and/or texts)."""
        if not items:
            return []
        
        all_images = True
        all_texts = True
        for item in items:
            if isinstance(item, (Image.Image, np.ndarray)):
                all_texts = False
            elif isinstance(item, (str, Path)) and str(item).lower().endswith((".jpg", ".jpeg", ".png", ".webp")) and Path(str(item)).exists():
                all_texts = False
            else:
                all_images = False

        if all_images:
            return self.encode_images_batch(items)
        if all_texts:
            return self.encode_texts_batch([str(it) for it in items])

        return [self.encode(it) for it in items]

    def get_aesthetic_anchors(self) -> Tuple[Optional[np.ndarray], Optional[np.ndarray]]:
        """Returns cached normalized positive and negative aesthetic anchor embeddings."""
        if self._cached_pos_emb is not None and self._cached_neg_emb is not None:
            return self._cached_pos_emb, self._cached_neg_emb

        pos_prompt = "a high quality award-winning cinematic photograph, sharp focus, beautiful lighting, stunning professional travel photography"
        neg_prompt = "a low quality blurry noisy dark pixelated poorly lit out of focus photo"

        try:
            pos_emb = np.array(self.encode_text(pos_prompt), dtype=np.float32)
            neg_emb = np.array(self.encode_text(neg_prompt), dtype=np.float32)
            pos_norm = pos_emb / (np.linalg.norm(pos_emb) + 1e-8)
            neg_norm = neg_emb / (np.linalg.norm(neg_emb) + 1e-8)
            self._cached_pos_emb = pos_norm
            self._cached_neg_emb = neg_norm
            return self._cached_pos_emb, self._cached_neg_emb
        except Exception as e:
            logger.debug(f"SigLIP aesthetic anchor init note: {e}")
            return None, None

    def compute_aesthetic_scores_batch(self, images: List[Union[str, Path, Image.Image, np.ndarray]]) -> List[float]:
        """
        Computes local aesthetic quality scores (1.0 to 10.0) using SigLIP 2 zero-shot semantic
        aesthetics against positive and negative photographic anchor prompts.
        """
        if not images:
            return []

        pos_emb, neg_emb = self.get_aesthetic_anchors()

        try:
            img_embs = self.encode_images_batch(images)
            scores = []
            for emb in img_embs:
                if pos_emb is not None and neg_emb is not None:
                    arr = np.array(emb, dtype=np.float32)
                    arr_norm = arr / (np.linalg.norm(arr) + 1e-8)
                    pos_sim = float(np.dot(arr_norm, pos_emb))
                    neg_sim = float(np.dot(arr_norm, neg_emb))

                    # Differential scaling: zero-shot aesthetic score mapped to 1.0 - 10.0 range
                    diff = pos_sim - neg_sim
                    raw_score = 7.0 + (diff * 25.0)
                    calibrated_score = round(float(np.clip(raw_score, 1.0, 10.0)), 1)
                else:
                    calibrated_score = 7.0
                scores.append(calibrated_score)
            return scores
        except Exception as e:
            logger.debug(f"SigLIP aesthetic score batch note: {e}")
            return [7.0 for _ in images]

    def compute_aesthetic_score(self, image: Union[str, Path, Image.Image, np.ndarray]) -> float:
        """Computes a single image aesthetic score (1.0 to 10.0) via SigLIP 2 zero-shot aesthetics."""
        res = self.compute_aesthetic_scores_batch([image])
        return res[0] if res else 7.0

    def _fallback_vector(self, seed_content: Any, dim: int = 768) -> List[float]:
        seed = abs(hash(str(seed_content))) % (2**32)
        rng = np.random.RandomState(seed)
        vec = rng.randn(dim).astype(np.float32)
        vec /= np.linalg.norm(vec)
        return vec.tolist()

siglip_embedder = SigLIPEmbedder()

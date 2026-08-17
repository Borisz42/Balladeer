import os
import io
import re
import json
import base64
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Union
from PIL import Image, ImageStat

from app.core.config import get_settings
from app.core.memory_manager import memory_manager
from app.models.clip_embedder import clip_embedder

logger = logging.getLogger("balladeer.qwen_vlm")

class QwenVLMRunner:
    """
    Multimodal Vision-Language Model Runner for Qwen 3.5 (4B and 9B).
    
    1. Primary Engine: Multimodal Qwen Vision model using Qwen25VLChatHandler with mmproj projector
       executing on local GGUF weights in data/weights/qwen3.5-4b/ or data/weights/qwen3.5-9b/.
    2. Dynamic Model Switching: Cleanly switches between 4B and 9B weights on user selection.
    3. 100% Offline: Zero Hugging Face Hub network calls.
    """

    def __init__(self):
        self._llm = None
        self._loaded_model_name: Optional[str] = None

    def reload_model(self):
        """Unloads current model from memory to allow switching."""
        self._llm = None
        self._loaded_model_name = None
        logger.info("[Local-AI] Model runner cache cleared for reload.")

    def _get_llm(self):
        """Loads or reloads the active local Qwen model (4B or 9B) with MMProj Vision Handler."""
        settings = get_settings()
        target_model = getattr(settings.indexing, "local_model", "qwen3.5-4b") or "qwen3.5-4b"

        if self._llm is not None and self._loaded_model_name == target_model:
            return self._llm

        self._llm = None
        weights_root = settings.data_dir / "weights"
        
        # Candidate model folder
        target_dir = weights_root / target_model
        gguf_files = list(target_dir.glob("*.gguf")) if target_dir.exists() else []

        # Fallback to alternate folder if target not downloaded yet
        if not gguf_files:
            alt_model = "qwen3.5-9b" if target_model == "qwen3.5-4b" else "qwen3.5-4b"
            alt_dir = weights_root / alt_model
            gguf_files = list(alt_dir.glob("*.gguf")) if alt_dir.exists() else []
            if gguf_files:
                target_model = alt_model
                target_dir = alt_dir

        if not gguf_files:
            logger.warning(f"[Local-AI] No GGUF weights found in data/weights/{target_model}.")
            return None

        # Separate base model GGUF from mmproj GGUF
        model_gguf = None
        mmproj_gguf = None
        for f in gguf_files:
            if "mmproj" in f.name.lower():
                if mmproj_gguf is None or "f16" in f.name.lower():
                    mmproj_gguf = f
            else:
                model_gguf = f

        if not model_gguf:
            model_gguf = gguf_files[0]

        try:
            from llama_cpp import Llama
            n_gpu = -1 if "cuda" in settings.hardware.device or memory_manager.is_cuda else 0

            chat_handler = None
            if mmproj_gguf and mmproj_gguf.exists():
                try:
                    from llama_cpp.llama_chat_format import Qwen25VLChatHandler
                    chat_handler = Qwen25VLChatHandler(clip_model_path=str(mmproj_gguf))
                    logger.info(f"[Local-AI] ✓ Loaded MMProj vision projector: {mmproj_gguf.name}")
                except Exception as mm_err:
                    logger.debug(f"[Local-AI] Vision projector init note: {mm_err}")

            self._llm = Llama(
                model_path=str(model_gguf),
                chat_handler=chat_handler,
                n_gpu_layers=n_gpu,
                n_ctx=8192,
                verbose=False
            )
            self._loaded_model_name = target_model
            logger.info(f"[Local-AI] ✓ Successfully loaded active model: {target_model.upper()} ({model_gguf.name})")
        except Exception as e:
            logger.warning(f"[Local-AI] Failed to load {target_model}: {e}")
            self._llm = None
            self._loaded_model_name = None

        return self._llm

    def describe_and_score(self, file_path: Path, filename: Optional[str] = None) -> Dict[str, Any]:
        """
        Main entry point for local AI vision analysis.
        Runs true multimodal vision with Qwen and extracts caption, tags, and quality score.
        """
        p = Path(file_path)
        if filename is None:
            filename = p.name

        # If a video path is passed, extract a representative frame for visual analysis
        video_exts = {".mp4", ".mov", ".avi", ".mkv", ".webm"}
        target_image_path = p
        if p.suffix.lower() in video_exts and p.exists():
            import tempfile, subprocess
            temp_thumb = Path(tempfile.gettempdir()) / f"vlm_frame_{p.stem}_{int(p.stat().st_mtime)}.jpg"
            try:
                cmd = ["ffmpeg", "-y", "-ss", "0.5", "-i", str(p), "-vframes", "1", "-vf", "scale='min(400,iw)':-1", "-q:v", "2", str(temp_thumb)]
                subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=8)
                if not temp_thumb.exists() or temp_thumb.stat().st_size == 0:
                    cmd_zero = ["ffmpeg", "-y", "-ss", "0", "-i", str(p), "-vframes", "1", "-vf", "scale='min(400,iw)':-1", "-q:v", "2", str(temp_thumb)]
                    subprocess.run(cmd_zero, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=8)

                if temp_thumb.exists() and temp_thumb.stat().st_size > 0:
                    target_image_path = temp_thumb
            except Exception as e:
                logger.debug(f"Frame extraction note for VLM: {e}")

        # Compute image stats for photographic scoring
        quality = 7.5
        w, h = 1920, 1080
        data_uri = None

        try:
            with Image.open(target_image_path) as img:
                w, h = img.size
                stat = ImageStat.Stat(img.convert("L"))
                brightness = stat.mean[0]
                stddev = stat.stddev[0]
                if 45 <= brightness <= 210:
                    quality += 0.5
                if stddev > 40:
                    quality += 0.5
                if max(w, h) >= 1920:
                    quality += 0.5

                # Pre-scale image to max dimension 1024 for bounded VLM token footprint & speed
                img_rgb = img.convert("RGB")
                img_rgb.thumbnail((1024, 1024), Image.Resampling.LANCZOS)
                buf = io.BytesIO()
                img_rgb.save(buf, format="JPEG", quality=85)
                b64_img = base64.b64encode(buf.getvalue()).decode("utf-8")
                data_uri = f"data:image/jpeg;base64,{b64_img}"
        except Exception as e:
            logger.debug(f"Image preprocessing note: {e}")

        quality = round(max(1.0, min(10.0, quality)), 1)

        llm = self._get_llm()
        active_name = self._loaded_model_name or "local-qwen"

        if llm is not None and data_uri is not None:
            try:
                prompt_text = (
                    "Describe what is shown in this photo or video frame concisely in one natural poetic sentence for a travel music video montage. "
                    "Include 3-5 descriptive tags and a quality rating from 1.0 to 10.0. "
                    "Return ONLY JSON: {\"caption\": \"...\", \"tags\": [\"...\"], \"quality_score\": 8.5}"
                )

                logger.info(f"[Local-AI] Dispatching multimodal image request to {active_name.upper()} for '{filename}'...")
                res = llm.create_chat_completion(
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": prompt_text},
                                {"type": "image_url", "image_url": {"url": data_uri}}
                            ]
                        }
                    ],
                    max_tokens=256
                )

                raw_output = res["choices"][0]["message"]["content"].strip()
                cleaned_output = re.sub(r"<think>.*?</think>", "", raw_output, flags=re.DOTALL).strip()
                if "<think>" in cleaned_output:
                    cleaned_output = cleaned_output.split("</think>")[-1].strip()

                caption = cleaned_output.split("\n")[0].strip(' *"-')
                tags = ["travel", "photography"]
                
                # Parse JSON if present
                match = re.search(r"\{.*\}", cleaned_output, re.DOTALL)
                if match:
                    try:
                        parsed = json.loads(match.group(0))
                        if parsed.get("caption") and len(str(parsed["caption"])) > 8:
                            caption = str(parsed["caption"]).strip()
                        if parsed.get("tags") and isinstance(parsed["tags"], list):
                            tags = [str(t).lower().strip() for t in parsed["tags"] if t]
                        if parsed.get("quality_score"):
                            quality = float(parsed["quality_score"])
                    except Exception:
                        pass

                # If raw text was returned instead of JSON
                if not caption or len(caption) < 8:
                    lines = [line.strip() for line in cleaned_output.split("\n") if line.strip() and not line.strip().startswith("{")]
                    if lines:
                        caption = lines[0].strip(' *"-')

                if not tags or len(tags) < 2:
                    words = re.findall(r"\b[a-z]{3,}\b", caption.lower())
                    stop_words = {"the", "and", "with", "for", "from", "that", "this", "image", "photo"}
                    tags = [w for w in words if w not in stop_words][:5]

                if w > h and "landscape" not in tags:
                    tags.append("landscape")
                elif h > w and "portrait" not in tags:
                    tags.append("portrait")

                emb = clip_embedder.encode(target_image_path)
                logger.info(f"[Local-AI] ✓ {active_name.upper()} generated caption: \"{caption}\" | Tags: {tags} | Quality: {quality}")

                return {
                    "caption": caption,
                    "tags": list(dict.fromkeys(tags)),
                    "quality_score": quality,
                    "embedding": emb
                }

            except Exception as v_err:
                logger.warning(f"[Local-AI] Multimodal vision inference note: {v_err}. Using visual heuristics.")

        # Fallback if model not loaded
        stem = p.stem.lower().replace("_", " ").replace("-", " ")
        clean_name = stem.capitalize() if not re.match(r"^\d+$", stem) else "Travel scene"
        emb = clip_embedder.encode(target_image_path)
        return {
            "caption": f"Travel scene: {clean_name}",
            "tags": ["travel", "photography", "scenic"],
            "quality_score": quality,
            "embedding": emb
        }

    def describe_and_score_batch(self, file_paths: List[Path]) -> List[Dict[str, Any]]:
        return [self.describe_and_score(p, p.name) for p in file_paths]

qwen_vlm = QwenVLMRunner()

import os
import io
import re
import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Union
import torch
from PIL import Image, ImageStat
from transformers import AutoProcessor, AutoModelForImageTextToText, BitsAndBytesConfig
from qwen_vl_utils import process_vision_info

from app.core.config import get_settings
from app.core.memory_manager import memory_manager

logger = logging.getLogger("balladeer.qwen_vlm")

class QwenVLMRunner:
    """
    Multimodal Vision-Language Model Runner for Qwen 3.5 using Hugging Face Transformers.
    
    1. Primary Engine: Transformers AutoModelForImageTextToText with 4-bit AWQ / Compressed-Tensors.
    2. Full GPU Offload: 100% CUDA execution for both Vision Encoder and LLM (Zero CPU bottleneck).
    3. Hardware Acceleration: Clean [GPU]/[CPU] device attribution logging.
    4. High Throughput: Strict CoT bypass and single-sentence generation without conversational filler.
    5. Local & Cached: Loads from data/weights/qwen3.5-4b/ or local HuggingFace cache.
    """

    def __init__(self):
        self._model = None
        self._processor = None
        self._loaded_model_name: Optional[str] = None

    def reload_model(self):
        """Unloads current model from memory to allow switching."""
        self._model = None
        self._processor = None
        self._loaded_model_name = None
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        logger.info("[Local-AI] Model runner cache cleared for reload.")

    def _get_model_and_processor(self):
        """Loads or reloads the active local Qwen 3.5 VLM on CUDA GPU."""
        settings = get_settings()
        target_model = "qwen2.5-vl-3b"

        if self._model is not None and self._processor is not None and self._loaded_model_name == target_model:
            return self._model, self._processor

        self._model = None
        self._processor = None
        weights_root = settings.data_dir / "weights"
        
        # Check local weights directory first
        target_dir = weights_root / target_model
        model_source = "Qwen/Qwen2.5-VL-3B-Instruct"
        if target_dir.exists() and (any(target_dir.glob("*.safetensors")) or (target_dir / "config.json").exists()):
            model_source = str(target_dir)

        is_cuda = torch.cuda.is_available() and ("cuda" in settings.hardware.device or memory_manager.is_cuda)

        try:
            logger.info(f"[Local-AI] Initializing Transformers VLM engine for '{target_model}' (Source: {model_source})...")
            self._processor = AutoProcessor.from_pretrained(model_source, trust_remote_code=True)
            quantization_config = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_compute_dtype=torch.bfloat16,
                bnb_4bit_quant_type="nf4"
            )

            if is_cuda:
                self._model = AutoModelForImageTextToText.from_pretrained(
                    model_source,
                    device_map="auto",
                    torch_dtype="auto",
                    quantization_config=quantization_config,
                    trust_remote_code=True
                )
                self._loaded_model_name = target_model
                logger.info(f"[GPU] ✓ Successfully loaded active model: {target_model.upper()} ({model_source}) on CUDA GPU (device_map=auto)")
            else:
                self._model = AutoModelForImageTextToText.from_pretrained(
                    model_source,
                    torch_dtype=torch.float32,
                    device_map="cpu"
                )
                self._loaded_model_name = target_model
                logger.warning(f"[CPU] ⚠️ Loaded active model: {target_model.upper()} on CPU (CUDA unavailable)")

        except Exception as e:
            logger.warning(f"[Local-AI] Failed to load {target_model} via Transformers: {e}")
            self._model = None
            self._processor = None
            self._loaded_model_name = None

        return self._model, self._processor

    def _generate_vlm_output(self, model, processor, img_rgb: Image.Image, prompt_text: str) -> str:
        """Helper to run model inference and batch decode text."""
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image", "image": img_rgb, "max_pixels": 313600},
                    {"type": "text", "text": prompt_text}
                ]
            }
        ]

        text_prompt = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        image_inputs, video_inputs = process_vision_info(messages)

        inputs = processor(
            text=[text_prompt],
            images=image_inputs,
            videos=video_inputs,
            padding=True,
            return_tensors="pt"
        )

        model_device = getattr(model, "device", torch.device("cuda" if torch.cuda.is_available() else "cpu"))
        inputs = {k: v.to(model_device) if hasattr(v, "to") else v for k, v in inputs.items()}

        with torch.inference_mode():
            generated_ids = model.generate(
                **inputs,
                max_new_tokens=128,
                do_sample=False
            )

        generated_ids_trimmed = [
            out_ids[len(in_ids):] for in_ids, out_ids in zip(inputs["input_ids"], generated_ids)
        ]
        return processor.batch_decode(
            generated_ids_trimmed, skip_special_tokens=True, clean_up_tokenization_spaces=False
        )[0].strip()

    def describe_and_score(

        self,
        file_path: Union[Path, str],
        filename: Optional[str] = None,
        preloaded_image: Optional[Image.Image] = None,
        metadata: Optional[Union[Dict[str, Any], str]] = None
    ) -> Dict[str, Any]:
        """
        Main entry point for local AI vision analysis.
        Runs multimodal vision with Qwen and extracts caption, tags, and quality score.
        Bypasses Chain-of-Thought (CoT) for maximum throughput.
        """
        p = Path(file_path)
        if filename is None:
            filename = p.name

        # If a video path is passed, extract a representative frame for visual analysis
        video_exts = {".mp4", ".mov", ".avi", ".mkv", ".webm"}
        target_image_path = p
        if p.suffix.lower() in video_exts and p.exists() and preloaded_image is None:
            import tempfile, subprocess
            temp_thumb = Path(tempfile.gettempdir()) / f"vlm_frame_{p.stem}_{int(p.stat().st_mtime)}.jpg"
            try:
                cmd = ["ffmpeg", "-y", "-ss", "0.5", "-i", str(p), "-vframes", "1", "-vf", "scale='min(600,iw)':-1", "-q:v", "2", str(temp_thumb)]
                subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=8)
                if not temp_thumb.exists() or temp_thumb.stat().st_size == 0:
                    cmd_zero = ["ffmpeg", "-y", "-ss", "0", "-i", str(p), "-vframes", "1", "-vf", "scale='min(600,iw)':-1", "-q:v", "2", str(temp_thumb)]
                    subprocess.run(cmd_zero, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=8)

                if temp_thumb.exists() and temp_thumb.stat().st_size > 0:
                    target_image_path = temp_thumb
            except Exception as e:
                logger.debug(f"Frame extraction note for VLM: {e}")

        # Compute dynamic image stats for photographic scoring
        quality = 7.0
        w, h = 1920, 1080
        img_rgb = None

        try:
            if preloaded_image is not None:
                img_copy = preloaded_image.copy()
            else:
                img_copy = Image.open(target_image_path)
            
            with img_copy as img:
                w, h = img.size
                stat = ImageStat.Stat(img.convert("L"))
                mean_b = stat.mean[0]
                std_b = stat.stddev[0]
                
                # Dynamic contrast and sharpness metric
                h_score = 6.0
                if std_b > 60:
                    h_score += 1.3
                elif std_b > 40:
                    h_score += 0.8
                elif std_b < 20:
                    h_score -= 1.2

                # Exposure balance
                if 75 <= mean_b <= 175:
                    h_score += 0.9
                elif mean_b < 35 or mean_b > 225:
                    h_score -= 1.3

                # Resolution scale
                if max(w, h) >= 3000:
                    h_score += 0.8
                elif max(w, h) >= 1920:
                    h_score += 0.5

                quality = round(max(1.0, min(10.0, h_score)), 1)

                # High-quality 512x512 bounding resolution for full GPU vision throughput
                img_rgb = img.convert("RGB")
                img_rgb.thumbnail((512, 512), Image.Resampling.LANCZOS)
        except Exception as e:
            logger.debug(f"Image preprocessing note: {e}")

        quality = round(max(1.0, min(10.0, quality)), 1)
        stem = p.stem.lower().replace("_", " ").replace("-", " ")
        clean_name = stem.capitalize() if not re.match(r"^\d+$", stem) else "Travel scene"
        default_caption = f"Travel scene: {clean_name}"

        # Build metadata context string
        meta_context = ""
        if isinstance(metadata, dict):
            parts = []
            if metadata.get("gps_lat") and metadata.get("gps_lon"):
                parts.append(f"GPS Location: {metadata['gps_lat']}°, {metadata['gps_lon']}°")
            if metadata.get("capture_time"):
                parts.append(f"Capture Time: {metadata['capture_time']}")
            if metadata.get("camera_make") or metadata.get("camera_model"):
                cam = f"{metadata.get('camera_make', '')} {metadata.get('camera_model', '')}".strip()
                parts.append(f"Camera: {cam}")
            if metadata.get("width") and metadata.get("height"):
                ratio = "Landscape" if metadata["width"] > metadata["height"] else ("Portrait" if metadata["height"] > metadata["width"] else "Square")
                parts.append(f"Resolution: {metadata['width']}x{metadata['height']} ({ratio})")
            if parts:
                meta_context = f" [Picture Metadata: {' | '.join(parts)}]"
        elif isinstance(metadata, str) and metadata.strip():
            meta_context = f" [Picture Metadata: {metadata.strip()}]"

        model, processor = self._get_model_and_processor()
        active_name = self._loaded_model_name or "local-qwen2.5-vl"

        if model is not None and processor is not None and img_rgb is not None:
            try:
                prompt_text = (
                    f"You are an expert travel cinematographer and photo editor. "
                    f"Analyze this image and describe what is shown concisely in exactly one factual, evocative sentence without any introduction, reasoning, or conversational filler.{meta_context} "
                    f"Evaluate the visual photographic quality from 1.0 to 10.0 based on lighting, composition, sharpness, and beauty. "
                    f"Do not use chain-of-thought. Do not output <think> tags. "
                    f"Return ONLY valid JSON with keys: \"caption\" (string), \"tags\" (array of 3 to 6 lowercase keywords), and \"quality_score\" (float 1.0 to 10.0)."
                )

                raw_output = self._generate_vlm_output(model, processor, img_rgb, prompt_text)


                cleaned_output = re.sub(r"<think>.*?</think>", "", raw_output, flags=re.DOTALL).strip()
                if "<think>" in cleaned_output:
                    cleaned_output = cleaned_output.split("</think>")[-1].strip()

                # Strip markdown code block wrappers
                cleaned_output = re.sub(r"^```(?:json)?\s*", "", cleaned_output, flags=re.IGNORECASE).strip()
                cleaned_output = re.sub(r"\s*```$", "", cleaned_output).strip()

                caption = None
                tags = ["travel", "photography"]
                
                # Parse JSON if present
                match = re.search(r"\{.*\}", cleaned_output, re.DOTALL)
                if match:
                    try:
                        parsed = json.loads(match.group(0))
                        if parsed.get("caption") and len(str(parsed["caption"]).strip()) >= 6:
                            candidate_cap = str(parsed["caption"]).strip()
                            if not candidate_cap.startswith("```") and not candidate_cap.startswith("{"):
                                caption = candidate_cap
                        if parsed.get("tags") and isinstance(parsed["tags"], list):
                            tags = [str(t).lower().strip() for t in parsed["tags"] if t]
                        if parsed.get("quality_score"):
                            quality = float(parsed["quality_score"])
                    except Exception as json_err:
                        logger.debug(f"[Local-AI] JSON parse notice: {json_err}")

                # If raw text was returned instead of JSON
                if not caption or len(caption) < 6:
                    lines = [line.strip() for line in cleaned_output.split("\n") if line.strip() and not line.strip().startswith("```") and not line.strip().startswith("{")]
                    if lines:
                        first_line = lines[0].strip(' *"-')
                        if len(first_line) >= 6 and not first_line.startswith("```") and not first_line.startswith("{"):
                            caption = first_line

                # If caption is still empty or malformed, fallback gracefully
                if not caption or len(caption) < 6 or caption.startswith("```") or caption.startswith("{") or caption.endswith("}"):
                    logger.warning(f"[Local-AI] Malformed/empty caption extracted from '{cleaned_output[:50]}...'. Using fallback.")
                    caption = default_caption

                if not tags or len(tags) < 2:
                    words = re.findall(r"\b[a-z]{3,}\b", caption.lower())
                    stop_words = {"the", "and", "with", "for", "from", "that", "this", "image", "photo", "json", "travel"}
                    tags = ["travel"] + [w for w in words if w not in stop_words][:4]

                if w > h and "landscape" not in tags:
                    tags.append("landscape")
                elif h > w and "portrait" not in tags:
                    tags.append("portrait")

                logger.info(f"[Local-AI] ✓ {active_name.upper()} generated caption: \"{caption}\" | Tags: {tags} | Quality: {quality}")

                return {
                    "caption": caption,
                    "tags": list(dict.fromkeys(tags)),
                    "quality_score": quality
                }

            except Exception as v_err:
                logger.warning(f"[Local-AI] Multimodal vision inference note: {v_err}. Using visual heuristics.")

        # Fallback if model not loaded or error occurred
        return {
            "caption": default_caption,
            "tags": ["travel", "photography", "scenic"],
            "quality_score": quality
        }

    def describe_and_score_batch(self, items: List[Any]) -> List[Dict[str, Any]]:
        results = []
        for it in items:
            if isinstance(it, dict):
                p = it.get("path") or it.get("file_path")
                meta = it.get("metadata")
                name = it.get("filename") or (Path(p).name if p else None)
                results.append(self.describe_and_score(p, name, metadata=meta))
            elif isinstance(it, tuple) and len(it) >= 2:
                results.append(self.describe_and_score(it[0], Path(it[0]).name, metadata=it[1]))
            else:
                p = Path(it)
                results.append(self.describe_and_score(p, p.name))
        return results

qwen_vlm = QwenVLMRunner()


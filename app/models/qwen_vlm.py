import os
import io
import re
import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Union, Tuple
import torch
from PIL import Image, ImageStat
from transformers import AutoProcessor, AutoModelForImageTextToText, BitsAndBytesConfig
from qwen_vl_utils import process_vision_info

from app.core.config import get_settings
from app.core.memory_manager import memory_manager

logger = logging.getLogger("balladeer.qwen_vlm")

class QwenVLMRunner:
    """
    High-Throughput Vision-Language Model Runner for Qwen 2.5 VL (3B) using Hugging Face Transformers.
    
    1. Dedicated Engine: Dedicated to rapid media captioning and visual indexing.
    2. Sub-Second Throughput: Downscales to 256x256 bounding box, 48 max generated tokens.
    3. No JSON / Aesthetic Overhead: Plain 1-sentence evocative descriptions; aesthetic scoring offloaded to SigLIP 2.
    4. Full GPU Offload & Batching: Batched PyTorch generation with NF4 4-bit quantization on CUDA.
    5. Shared Cache: Looks under ~/.cache/huggingface/hub/ for persistence across worktrees.
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
        memory_manager.remove_loaded("vlm")
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        logger.info("[Local-AI] Model runner cache cleared for reload.")

    def _get_model_and_processor(self):
        """Loads or reloads the active local Qwen 2.5 VL on CUDA GPU."""
        settings = get_settings()
        target_model = "qwen2.5-vl-3b"

        if self._model is not None and self._processor is not None and self._loaded_model_name == target_model:
            return self._model, self._processor

        self._model = None
        self._processor = None
        
        # Resolve model source (local folder, snapshot, or canonical HF hub ID)
        canonical_repo = "Qwen/Qwen2.5-VL-3B-Instruct"
        hf_hub_dir = Path(os.environ.get("HF_HOME", Path.home() / ".cache" / "huggingface" / "hub"))
        weights_root = settings.data_dir / "weights"

        candidate_paths = [
            hf_hub_dir / "qwen2.5-vl-3b",
            hf_hub_dir / "models--Qwen--Qwen2.5-VL-3B-Instruct",
            weights_root / target_model,
        ]

        model_source = canonical_repo
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

        is_cuda = torch.cuda.is_available() and ("cuda" in settings.hardware.device or memory_manager.is_cuda)

        try:
            memory_manager.set_loading("Qwen 2.5 VL (3B)")
            logger.info(f"[Local-AI] Initializing Transformers VLM engine for '{target_model}' (Source: {model_source})...")
            
            try:
                self._processor = AutoProcessor.from_pretrained(model_source, trust_remote_code=True)
            except Exception as proc_err:
                logger.debug(f"[Local-AI] AutoProcessor from {model_source} notice: {proc_err}. Trying canonical {canonical_repo}...")
                model_source = canonical_repo
                self._processor = AutoProcessor.from_pretrained(canonical_repo, trust_remote_code=True)

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
                memory_manager.set_loaded("vlm", "Qwen 2.5 VL (3B)")
                logger.info(f"[GPU] ✓ Successfully loaded active model: {target_model.upper()} ({model_source}) on CUDA GPU")
            else:
                self._model = AutoModelForImageTextToText.from_pretrained(
                    model_source,
                    torch_dtype=torch.float32,
                    device_map="cpu"
                )
                self._loaded_model_name = target_model
                memory_manager.set_loaded("vlm", "Qwen 2.5 VL (3B) [CPU]")
                logger.warning(f"[CPU] ⚠️ Loaded active model: {target_model.upper()} on CPU (CUDA unavailable)")

        except Exception as e:
            logger.warning(f"[Local-AI] Failed to load {target_model} via Transformers: {e}")
            memory_manager.set_loading(None)
            self._model = None
            self._processor = None
            self._loaded_model_name = None

        return self._model, self._processor

    def _prepare_image(self, target_image_path: Path, preloaded_image: Optional[Image.Image] = None) -> Optional[Image.Image]:
        """Preprocesses and downscales image to 256x256 RGB for ultra-fast vision throughput."""
        try:
            if preloaded_image is not None:
                img_copy = preloaded_image.copy()
            else:
                img_copy = Image.open(target_image_path)
            
            with img_copy as img:
                img_rgb = img.convert("RGB")
                img_rgb.thumbnail((256, 256), Image.Resampling.LANCZOS)
                return img_rgb
        except Exception as e:
            logger.debug(f"Image preprocessing note: {e}")
            return None

    def _extract_video_thumb(self, p: Path) -> Path:
        """Extracts a representative frame for video paths."""
        video_exts = {".mp4", ".mov", ".avi", ".mkv", ".webm"}
        if p.suffix.lower() in video_exts and p.exists():
            import tempfile, subprocess
            temp_thumb = Path(tempfile.gettempdir()) / f"vlm_frame_{p.stem}_{int(p.stat().st_mtime)}.jpg"
            try:
                cmd = ["ffmpeg", "-y", "-ss", "0.5", "-i", str(p), "-vframes", "1", "-vf", "scale='min(320,iw)':-1", "-q:v", "2", str(temp_thumb)]
                subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=8)
                if not temp_thumb.exists() or temp_thumb.stat().st_size == 0:
                    cmd_zero = ["ffmpeg", "-y", "-ss", "0", "-i", str(p), "-vframes", "1", "-vf", "scale='min(320,iw)':-1", "-q:v", "2", str(temp_thumb)]
                    subprocess.run(cmd_zero, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=8)
                if temp_thumb.exists() and temp_thumb.stat().st_size > 0:
                    return temp_thumb
            except Exception as e:
                logger.debug(f"Frame extraction note for VLM: {e}")
        return p

    def _build_meta_context(self, metadata: Optional[Union[Dict[str, Any], str]]) -> str:
        if isinstance(metadata, dict):
            parts = []
            if metadata.get("gps_lat") and metadata.get("gps_lon"):
                parts.append(f"Location: {metadata['gps_lat']}°, {metadata['gps_lon']}°")
            if metadata.get("capture_time"):
                parts.append(f"Time: {metadata['capture_time']}")
            if parts:
                return f" [Context: {' | '.join(parts)}]"
        elif isinstance(metadata, str) and metadata.strip():
            return f" [Context: {metadata.strip()}]"
        return ""

    def _parse_vlm_text_or_json(self, raw_text: str, default_caption: str) -> Tuple[str, List[str], float]:
        """Strips think blocks, markdown fencing, and parses caption, tags, and optional quality."""
        cleaned = re.sub(r"<think>.*?</think>", "", raw_text, flags=re.DOTALL).strip()
        if "<think>" in cleaned:
            cleaned = cleaned.split("</think>")[-1].strip()

        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE).strip()
        cleaned = re.sub(r"\s*```$", "", cleaned).strip()

        caption = None
        tags = []
        quality = 7.0

        if cleaned.startswith("{") or "caption" in cleaned:
            match = re.search(r"\{.*\}", cleaned, re.DOTALL)
            if match:
                try:
                    parsed = json.loads(match.group(0))
                    if parsed.get("caption") and len(str(parsed["caption"]).strip()) >= 5:
                        caption = str(parsed["caption"]).strip()
                    if parsed.get("tags") and isinstance(parsed["tags"], list):
                        tags = [str(t).lower().strip() for t in parsed["tags"] if t]
                    if parsed.get("quality_score"):
                        quality = float(parsed["quality_score"])
                except Exception:
                    pass

        if not caption:
            lines = [l.strip() for l in cleaned.split("\n") if l.strip() and not l.strip().startswith("```") and not l.strip().startswith("{")]
            if lines:
                candidate = lines[0].strip(' *"-')
                if len(candidate) >= 5 and not candidate.startswith("{"):
                    caption = candidate

        final_cap = caption if caption else default_caption
        if not tags:
            tags = self._extract_tags(final_cap)
        else:
            tags = list(dict.fromkeys(tags))

        return final_cap, tags, quality

    def _extract_tags(self, caption: str) -> List[str]:
        words = re.findall(r"\b[a-z]{3,}\b", caption.lower())
        stop_words = {"the", "and", "with", "for", "from", "that", "this", "image", "photo", "scene", "view", "travel", "poses", "together"}
        tags = ["travel"] + [w for w in words if w not in stop_words][:4]
        return list(dict.fromkeys(tags))

    def _generate_vlm_output(self, model, processor, img_rgb: Image.Image, prompt_text: str) -> str:
        """Single-item generation helper."""
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image", "image": img_rgb, "max_pixels": 65536, "min_pixels": 16384},
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
                max_new_tokens=48,
                do_sample=False
            )

        generated_ids_trimmed = [
            out_ids[len(in_ids):] for in_ids, out_ids in zip(inputs["input_ids"], generated_ids)
        ]
        return processor.batch_decode(
            generated_ids_trimmed, skip_special_tokens=True, clean_up_tokenization_spaces=False
        )[0].strip()

    def _generate_vlm_output_batch(
        self,
        model,
        processor,
        images: List[Image.Image],
        prompt_texts: List[str]
    ) -> List[str]:
        """True PyTorch batched generation with 256x256 visual bounding and 48 max new tokens."""
        if not images:
            return []

        if len(images) == 1:
            return [self._generate_vlm_output(model, processor, images[0], prompt_texts[0])]

        try:
            # Ensure left padding for batched causal generation
            if hasattr(processor, "tokenizer") and processor.tokenizer is not None:
                processor.tokenizer.padding_side = "left"
                if processor.tokenizer.pad_token is None:
                    processor.tokenizer.pad_token = processor.tokenizer.eos_token

            messages_list = [
                [
                    {
                        "role": "user",
                        "content": [
                            {"type": "image", "image": img, "max_pixels": 65536, "min_pixels": 16384},
                            {"type": "text", "text": prompt}
                        ]
                    }
                ]
                for img, prompt in zip(images, prompt_texts)
            ]

            text_prompts = [
                processor.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
                for msgs in messages_list
            ]
            image_inputs, video_inputs = process_vision_info(messages_list)

            inputs = processor(
                text=text_prompts,
                images=image_inputs,
                videos=video_inputs,
                padding=True,
                return_tensors="pt"
            )

            model_device = getattr(model, "device", torch.device("cuda" if torch.cuda.is_available() else "cpu"))
            inputs = {k: v.to(model_device) if hasattr(v, "to") else v for k, v in inputs.items()}

            input_ids_tensor = inputs.get("input_ids")
            prompt_len = input_ids_tensor.shape[1] if input_ids_tensor is not None and hasattr(input_ids_tensor, "shape") else 0

            with torch.inference_mode():
                generated_ids = model.generate(
                    **inputs,
                    max_new_tokens=48,
                    do_sample=False
                )

            # Extract generated tokens
            if prompt_len > 0:
                generated_ids_trimmed = [
                    out_ids[prompt_len:] for out_ids in generated_ids
                ]
            else:
                generated_ids_trimmed = generated_ids

            decoded = [
                s.strip() for s in processor.batch_decode(
                    generated_ids_trimmed, skip_special_tokens=True, clean_up_tokenization_spaces=False
                )
            ]

            # Verify each item: if any item in the batch produced an empty or too-short string, re-run individually
            final_outputs = []
            for i, text in enumerate(decoded):
                if not text or len(text) < 5 or text.startswith("{") and not '"caption"' in text:
                    logger.debug(f"[Local-AI] Batch item {i} generated empty/short text, executing single fallback.")
                    single_res = self._generate_vlm_output(model, processor, images[i], prompt_texts[i])
                    final_outputs.append(single_res)
                else:
                    final_outputs.append(text)

            return final_outputs

        except Exception as e:
            logger.warning(f"[Local-AI] Batch multimodal inference encountered note ({e}), executing items sequentially.")
            return [
                self._generate_vlm_output(model, processor, img, p)
                for img, p in zip(images, prompt_texts)
            ]

    def describe_and_score(
        self,
        file_path: Union[Path, str],
        filename: Optional[str] = None,
        preloaded_image: Optional[Image.Image] = None,
        metadata: Optional[Union[Dict[str, Any], str]] = None
    ) -> Dict[str, Any]:
        """Single-item description entry point."""
        p = Path(file_path)
        target_img_path = self._extract_video_thumb(p)
        img_rgb = self._prepare_image(target_img_path, preloaded_image=preloaded_image)
        stem = p.stem.lower().replace("_", " ").replace("-", " ")
        clean_name = stem.capitalize() if not re.match(r"^\d+$", stem) else "Travel scene"
        default_caption = f"Travel scene: {clean_name}"
        meta_context = self._build_meta_context(metadata)
        prompt_text = f"Describe what is shown in this travel scene concisely in one factual sentence without introductory filler.{meta_context}"

        model, processor = self._get_model_and_processor()
        if model is not None and processor is not None and img_rgb is not None:
            try:
                raw_output = self._generate_vlm_output(model, processor, img_rgb, prompt_text)
                caption, tags, quality = self._parse_vlm_text_or_json(raw_output, default_caption)
                return {
                    "caption": caption,
                    "tags": tags,
                    "quality_score": quality
                }
            except Exception as e:
                logger.warning(f"[Local-AI] Single VLM inference note: {e}")

        return {
            "caption": default_caption,
            "tags": self._extract_tags(default_caption),
            "quality_score": 7.0
        }

    def describe_and_score_batch(self, items: List[Any]) -> List[Dict[str, Any]]:
        """
        Batched multimodal vision indexing for maximum GPU throughput.
        Processes up to 8 images per batch on RTX 3070 with 256x256 downscaling.
        """
        if not items:
            return []

        prepared_items = []
        for it in items:
            if isinstance(it, dict):
                p = Path(it.get("path") or it.get("file_path"))
                meta = it.get("metadata")
                name = it.get("filename") or p.name
            elif isinstance(it, tuple) and len(it) >= 2:
                p = Path(it[0])
                meta = it[1]
                name = p.name
            else:
                p = Path(it)
                meta = None
                name = p.name

            target_img_path = self._extract_video_thumb(p)
            img_rgb = self._prepare_image(target_img_path)
            stem = p.stem.lower().replace("_", " ").replace("-", " ")
            clean_name = stem.capitalize() if not re.match(r"^\d+$", stem) else "Travel scene"
            default_caption = f"Travel scene: {clean_name}"
            meta_context = self._build_meta_context(meta)
            prompt_text = f"Describe what is shown in this travel scene concisely in one factual sentence without introductory filler.{meta_context}"

            prepared_items.append({
                "path": p,
                "img_rgb": img_rgb,
                "prompt": prompt_text,
                "default_caption": default_caption
            })

        model, processor = self._get_model_and_processor()
        valid_indices = [idx for idx, item in enumerate(prepared_items) if item["img_rgb"] is not None]

        results = [
            {
                "caption": item["default_caption"],
                "tags": self._extract_tags(item["default_caption"]),
                "quality_score": 7.0
            }
            for item in prepared_items
        ]

        if model is not None and processor is not None and valid_indices:
            try:
                valid_images = [prepared_items[idx]["img_rgb"] for idx in valid_indices]
                valid_prompts = [prepared_items[idx]["prompt"] for idx in valid_indices]

                raw_outputs = self._generate_vlm_output_batch(model, processor, valid_images, valid_prompts)

                for val_pos, idx in enumerate(valid_indices):
                    raw = raw_outputs[val_pos] if val_pos < len(raw_outputs) else ""
                    cap, tags, quality = self._parse_vlm_text_or_json(raw, prepared_items[idx]["default_caption"])
                    results[idx] = {
                        "caption": cap,
                        "tags": tags,
                        "quality_score": quality
                    }
                    logger.info(f"[Local-AI] ✓ Generated description: \"{cap}\" | Tags: {tags}")

            except Exception as e:
                logger.warning(f"[Local-AI] Batch multimodal vision inference note: {e}")

        return results

qwen_vlm = QwenVLMRunner()

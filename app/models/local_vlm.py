import os
import io
import re
import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Union, Tuple

import torch
from PIL import Image, ImageOps, ImageStat
from transformers import AutoProcessor, AutoModelForImageTextToText, BitsAndBytesConfig
from qwen_vl_utils import process_vision_info

from app.core.config import get_settings
from app.core.memory_manager import memory_manager

logger = logging.getLogger("balladeer.local_vlm")


class LocalVLMRunner:
    """
    High-Throughput, Config-Driven Local Vision-Language & Text Generation Engine.
    
    1. Single Unified Model: Uses a single loaded model in GPU VRAM for both visual indexing
       (media descriptions, tag extraction, quality estimation) and text synthesis
       (travel log drafting, lyric generation, Google Flow Music prompt optimization).
    2. Config-Driven: Model repository ID, quantization mode, and display metadata are resolved
       dynamically from application settings (IndexingSettings).
    3. Optimized GPU Offload: Batched PyTorch generation with NF4 4-bit quantization on CUDA.
    4. Fast Text Generation: In-memory KV-cached autoregressive text generation with low temperature.
    """

    def __init__(self):
        self._model = None
        self._processor = None
        self._loaded_model_name: Optional[str] = None

    @property
    def is_loaded(self) -> bool:
        """Returns True if the active model and processor are already resident in memory."""
        settings = get_settings()
        return (
            self._model is not None
            and self._processor is not None
            and self._loaded_model_name == settings.indexing.local_model
        )

    def clear_cache(self):
        """Releases model from memory / GPU VRAM."""
        self._model = None
        self._processor = None
        self._loaded_model_name = None
        memory_manager.remove_loaded("vlm")
        memory_manager.remove_loaded("qwen")
        memory_manager.set_loading(None, key="vlm")
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        logger.info("[Local-AI] Model runner cache cleared.")

    def reload_model(self):
        """Unloads current model from memory to allow reconfiguration or model switching."""
        self.clear_cache()
        logger.info("[Local-AI] Model runner cleared for reload.")

    async def preload_background(self):
        """Asynchronously pre-loads model into GPU VRAM in the background at startup."""
        import asyncio
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._get_model_and_processor)

    async def prewarm_async(self):
        """Alias for preload_background."""
        await self.preload_background()

    def _get_model_and_processor(self):
        """Loads or reloads the active local VLM/LLM on CUDA GPU or CPU."""
        settings = get_settings()
        target_model = settings.indexing.local_model
        canonical_repo = settings.indexing.vlm_model
        display_name = settings.indexing.vlm_display_name

        if (
            self._model is not None
            and self._processor is not None
            and self._loaded_model_name == target_model
        ):
            return self._model, self._processor

        self._model = None
        self._processor = None

        hf_hub_dir = Path(os.environ.get("HF_HOME", Path.home() / ".cache" / "huggingface" / "hub"))
        weights_root = settings.data_dir / "weights"
        repo_slug = "models--" + canonical_repo.replace("/", "--")

        candidate_paths = [
            hf_hub_dir / target_model,
            hf_hub_dir / repo_slug,
            weights_root / target_model,
            weights_root / canonical_repo.split("/")[-1],
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
            memory_manager.set_loading(display_name, key="vlm")
            logger.info(f"[Local-AI] Initializing Local VLM engine for '{target_model}' (Source: {model_source})...")

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
                memory_manager.set_loaded("vlm", display_name)
                logger.info(f"[GPU] ✓ Successfully loaded active model: {target_model.upper()} ({model_source}) on CUDA GPU")
            else:
                self._model = AutoModelForImageTextToText.from_pretrained(
                    model_source,
                    torch_dtype=torch.float32,
                    device_map="cpu"
                )
                self._loaded_model_name = target_model
                memory_manager.set_loaded("vlm", f"{display_name} [CPU]")
                logger.warning(f"[CPU] ⚠️ Loaded active model: {target_model.upper()} on CPU (CUDA unavailable)")

        except Exception as e:
            logger.warning(f"[Local-AI] Failed to load {target_model} via Transformers: {e}")
            memory_manager.set_loading(None, key="vlm")
            self._model = None
            self._processor = None
            self._loaded_model_name = None

        return self._model, self._processor

    # -------------------------------------------------------------------------
    # Multimodal Vision Indexing Methods
    # -------------------------------------------------------------------------

    def _prepare_image(self, target_image_path: Path, preloaded_image: Optional[Image.Image] = None) -> Optional[Image.Image]:
        """Preprocesses and downscales image to 256x256 RGB for high vision throughput."""
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
            from app.core.geocoder import format_location_context
            loc = format_location_context(metadata)
            if loc:
                parts.append(f"Location: {loc}")
            if metadata.get("capture_time"):
                parts.append(f"Time: {metadata['capture_time']}")
            if parts:
                return f" [Context: {' | '.join(parts)}]"
        elif isinstance(metadata, str) and metadata.strip():
            return f" [Context: {metadata.strip()}]"
        return ""

    def _parse_vlm_text_or_json(self, raw_text: str, default_caption: str) -> Tuple[str, List[str], float]:
        """Strips think blocks, markdown fencing, cleans coordinates, and parses caption, tags, and optional quality."""
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

        # Clean out any leftover raw coordinates or timestamps
        final_cap = re.sub(r",?\s*(?:at|near)?\s*coordinates?\s*[-+]?\d+\.\d+°?\s*(?:latitude|lat)?\s*(?:and|,)?\s*[-+]?\d+\.\d+°?\s*(?:longitude|lon)?", "", final_cap, flags=re.IGNORECASE)
        final_cap = re.sub(r"\s+at\s+[-+]?\d+\.\d+°?,\s*[-+]?\d+\.\d+°?", "", final_cap, flags=re.IGNORECASE)
        final_cap = re.sub(r"\s*,\s*with a timestamp of.*$", ".", final_cap, flags=re.IGNORECASE)
        final_cap = re.sub(r"\s{2,}", " ", final_cap).strip(" ,.")
        if final_cap and not final_cap.endswith("."):
            final_cap += "."

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
        if filename is None:
            filename = p.name

        target_image_path = self._extract_video_thumb(p) if preloaded_image is None else p

        # Compute dynamic image stats for photographic scoring
        quality = 7.0
        w, h = 1920, 1080
        img_rgb = None

        try:
            if preloaded_image is not None:
                img_copy = ImageOps.exif_transpose(preloaded_image) or preloaded_image.copy()
            else:
                raw_img = Image.open(target_image_path)
                img_copy = ImageOps.exif_transpose(raw_img) or raw_img
            
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
                img_rgb = img.convert("RGB")
                img_rgb.thumbnail((512, 512), Image.Resampling.LANCZOS)
        except Exception as e:
            logger.debug(f"Image preprocessing note: {e}")

        quality = round(max(1.0, min(10.0, quality)), 1)
        stem = p.stem.lower().replace("_", " ").replace("-", " ")
        clean_name = stem.capitalize() if not re.match(r"^\d+$", stem) else "Travel scene"
        default_caption = f"Travel scene: {clean_name}"
        meta_context = self._build_meta_context(metadata)
        prompt_text = f"Describe what is shown in this travel scene concisely in one factual sentence without introductory filler or coordinates.{meta_context}"

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
            prompt_text = f"Describe what is shown in this travel scene concisely in one factual sentence without introductory filler or coordinates.{meta_context}"

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

    # -------------------------------------------------------------------------
    # Text Generation & Synthesis Methods
    # -------------------------------------------------------------------------

    def generate_text(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 280,
        temperature: float = 0.0,
        top_p: float = 0.9
    ) -> str:
        """Generates fast, high-quality text using cached KV states with greedy or sampled decoding."""
        model, processor = self._get_model_and_processor()
        if model is None or processor is None:
            return ""

        try:
            logger.info("=" * 65)
            logger.info(f"[Local-AI] [LLM-Call] Dispatching text generation (max_tokens={max_tokens}, temp={temperature}):")
            if system_prompt:
                logger.info(f"[Local-AI] [System-Prompt]:\n{system_prompt}")
            logger.info(f"[Local-AI] [User-Prompt]:\n{prompt}")
            logger.info("=" * 65)

            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": [{"type": "text", "text": system_prompt}]})
            messages.append({"role": "user", "content": [{"type": "text", "text": prompt}]})

            text_prompt = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
            inputs = processor(text=[text_prompt], padding=True, return_tensors="pt")

            model_device = getattr(model, "device", torch.device("cuda" if torch.cuda.is_available() else "cpu"))
            model_inputs = {k: v.to(model_device) for k, v in inputs.items() if hasattr(v, "to")}
            prompt_len = model_inputs["input_ids"].shape[1] if "input_ids" in model_inputs else 0

            tokenizer_inner = getattr(processor, "tokenizer", processor)
            eos_id = getattr(tokenizer_inner, "eos_token_id", None) or getattr(processor, "eos_token_id", None)

            gen_kwargs = {
                "max_new_tokens": max_tokens,
                "use_cache": True,
                "pad_token_id": eos_id,
                "eos_token_id": eos_id
            }
            if temperature > 0.01:
                gen_kwargs["do_sample"] = True
                gen_kwargs["temperature"] = float(temperature)
                gen_kwargs["top_p"] = float(top_p)
            else:
                gen_kwargs["do_sample"] = False

            with torch.inference_mode():
                generated = model.generate(
                    **model_inputs,
                    **gen_kwargs
                )
            new_ids = generated[0][prompt_len:]
            result = processor.decode(new_ids, skip_special_tokens=True).strip()

            logger.info(f"[Local-AI] [LLM-Response] ({len(new_ids)} new tokens generated):\n{result}")
            logger.debug(f"[Local-AI] [LLM-Debug] Prompt token length: {prompt_len}, Total output tokens: {generated.shape[1]}")
            return result
        except Exception as e:
            logger.warning(f"[Local-AI] Text generation notice: {e}")
            return ""

    def draft_travel_log(self, media_items: List[Dict[str, Any]], project_title: Optional[str] = None) -> Dict[str, Any]:
        """Synthesizes structured travel days and narrative text from media items."""
        title = project_title or "Travel Montage"
        from app.pipeline.rephraser import diary_rephraser
        return diary_rephraser.draft_travel_log_from_media(media_items, title)

    def generate_music_style_and_prompt(
        self,
        acts: List[Dict[str, Any]],
        narrative_text: str = "",
        suggested_bpm: int = 118,
        total_duration_sec: float = 30.0,
        style_vibe: Optional[str] = None
    ) -> Dict[str, Any]:
        """Generates a structured Google Flow Music prompt using local VLM or heuristic fallback."""
        from app.pipeline.music_gen import MusicGenerator
        mg = MusicGenerator()
        heuristic_prompt = mg._generate_heuristic_flow_prompt(acts, suggested_bpm, total_duration_sec, style_vibe or "Acoustic Indie Folk Pop")

        system_prompt = (
            "You are an expert music producer. Create an inspiring 1-2 sentence Google Flow Music prompt "
            "specifying genre, instruments, tempo (BPM), and section breakdown."
        )
        prompt = f"Montage ({int(total_duration_sec)}s, {suggested_bpm} BPM):\n{narrative_text.strip()}"
        out_prompt = self.generate_text(prompt, system_prompt=system_prompt, max_tokens=180)
        final_prompt = out_prompt.strip() if out_prompt and len(out_prompt.strip()) > 20 else heuristic_prompt

        return {
            "flow_prompt": final_prompt,
            "suggested_bpm": suggested_bpm,
            "genre": style_vibe or "Acoustic Indie Folk Pop",
            "mood": "Uplifting & Inspiring",
            "instruments": ["Acoustic Guitar", "Warm Vocals", "Ambient Percussion", "Cello"]
        }

    def generate_story_and_lyrics(
        self,
        acts: List[Dict[str, Any]],
        narrative_text: str = "",
        is_instrumental: bool = False
    ) -> Tuple[str, str]:
        """Generates rhyming song lyrics and a Google Flow Music style prompt in 1-3 seconds."""
        from app.pipeline.music_gen import MusicGenerator
        mg = MusicGenerator()
        heuristic_lyrics, heuristic_prompt = mg._generate_heuristic_lyrics(acts, is_instrumental)

        # Format acts timeline into the prompt
        acts_lines = []
        for a in acts:
            s = int(a.get("start_sec", 0))
            e = int(a.get("end_sec", 0))
            dur = a.get("duration_sec", 0)
            a_type = a.get("act_type", "Verse")
            a_title = a.get("title", "")
            title_suffix = f": {a_title}" if a_title and a_title.lower() != a_type.lower() else ""
            acts_lines.append(f"[{s//60}:{s%60:02d}-{e//60}:{e%60:02d}] [{a_type}{title_suffix}] ({dur:.0f}s)")
        
        timeline_schedule = "\n".join(acts_lines)

        if is_instrumental:
            system_prompt = (
                "You are a cinematic documentary narrator. Write timed spoken narrative voiceover subtitles "
                "for a travel video with background instrumental music.\n\n"
                "CRITICAL RULES:\n"
                "1. For each section, write natural spoken storytelling narration (~2.2 words per second normal speaking tempo) "
                "describing the travel journey and specifically highlighting what is seen in the photos and video scenes.\n"
                "2. Word budgets per section (normal speaking tempo):\n"
                "   - 4s Intro / Outro: EXACTLY ONE short, complete grammatical sentence of 6 to 9 words (e.g. 'Our journey begins as morning light breaks across the horizon.'). Never write partial or cut-off sentences.\n"
                "   - 10s Section: 20 to 25 words (1-2 complete sentences)\n"
                "   - 15s Section: 32 to 38 words (2 complete sentences)\n"
                "   - 24s Section: 48 to 58 words (2-3 complete sentences)\n"
                "3. Follow the section timeline schedule strictly with timestamp headers.\n"
                "4. Do NOT use markdown bolding (**) or hashtags (#). Use plain narrative sentences.\n\n"
                "EXAMPLE OUTPUT FORMAT:\n"
                "[0:00-0:04] [Intro] (4s)\n"
                "Our journey begins as morning light breaks across the horizon.\n\n"
                "[0:04-0:24] [Verse 1: Day 1] (20s)\n"
                "Walking down the cobblestone streets, we take in the historic architecture and lively local markets. "
                "Every corner reveals colorful shopfronts, quiet riverside cafes, and the vibrant spirit of the city as we explore.\n\n"
                "[0:24-0:28] [Outro] (4s)\n"
                "As the sun sets, we hold onto memories from an unforgettable day."
            )
            prompt = (
                f"INSTRUCTIONS:\n"
                f"Write timed spoken documentary narrative voiceover subtitles (~2.2 words per second speaking tempo) "
                f"describing the travel journey and scenes for each section.\n\n"
                f"Travel Story & Scene Captions:\n{narrative_text.strip()}\n\n"
                f"Required Section Timeline:\n{timeline_schedule}\n\n"
                "Write the timed spoken narrative subtitles for each section now:"
            )
            out_subs = self.generate_text(prompt, system_prompt=system_prompt, max_tokens=650, temperature=0.4)
            final_subs = out_subs.strip() if out_subs and "[" in out_subs else heuristic_lyrics
            return final_subs, heuristic_prompt

        system_prompt = (
            "You are an expert songwriter and poet. Write poetic, evocative rhyming song lyrics with strict AABB rhyme schemes "
            "based on the travel story and section timeline.\n\n"
            "CRITICAL RHYMING RULES:\n"
            "1. Every Verse MUST have strict rhyming pairs at the end of each line (AABB rhyme scheme).\n"
            "   - Line 1 and Line 2 MUST rhyme with each other (e.g., light / sight, sun / begun, eyes / skies).\n"
            "   - Line 3 and Line 4 MUST rhyme with each other (e.g., street / meet, way / day, hold / gold).\n"
            "2. For each [Verse] section, write 2 to 4 full poetic rhyming lines (at least 7-10 words per line). Do NOT write unrhymed prose.\n"
            "3. For [Intro] and [Outro] instrumental sections, write [Instrumental - acoustic guitar description].\n"
            "4. Do NOT use markdown bolding (**) or hashtags (#). Use plain text lines.\n\n"
            "EXAMPLE OUTPUT FORMAT:\n"
            "[0:00-0:04] [Intro] (4s)\n"
            "[Instrumental - Gentle acoustic guitar strumming]\n\n"
            "[0:04-0:24] [Verse 1: Morning Journey] (20s)\n"
            "Stepping out into the golden morning light\n"
            "Cobblestone streets stretching out of sight\n"
            "Every single step becomes a memory to make\n"
            "Smiling at the sunrise as the quiet cities wake\n\n"
            "[0:24-0:28] [Outro] (4s)\n"
            "[Instrumental - Warm acoustic fade-out]"
        )
        prompt = (
            f"INSTRUCTIONS:\n"
            f"Write poetic rhyming song lyrics (AABB rhyme scheme where Line 1 rhymes with Line 2, and Line 3 rhymes with Line 4). "
            f"Every line must end with a rhyming word!\n\n"
            f"Travel Story & Captions:\n{narrative_text.strip()}\n\n"
            f"Required Section Timeline:\n{timeline_schedule}\n\n"
            "Write the full rhyming song lyrics with AABB rhyming lines for each section now:"
        )

        out = self.generate_text(prompt, system_prompt=system_prompt, max_tokens=650, temperature=0.7)
        if out and ("[" in out or "verse" in out.lower()):
            if "[music prompt]" in out.lower():
                parts = re.split(r"\[music prompt\]", out, flags=re.IGNORECASE)
                lyrics = parts[0].strip()
                music_p = parts[1].strip() if len(parts) > 1 else heuristic_prompt
                return lyrics, music_p
            return out.strip(), heuristic_prompt

        return heuristic_lyrics, heuristic_prompt


local_vlm = LocalVLMRunner()

# Backward-compatibility aliases
LocalModelRunner = LocalVLMRunner
QwenRunner = LocalVLMRunner
QwenVLMRunner = LocalVLMRunner
QwenLLMRunner = LocalVLMRunner
qwen_runner = local_vlm
qwen_vlm = local_vlm
qwen_llm = local_vlm

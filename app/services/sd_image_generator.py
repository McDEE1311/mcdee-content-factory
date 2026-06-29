"""
Stable Diffusion image generator using ComfyUI venv.
Generates cartoon scenes for documentary videos.
"""
import logging
import os
import subprocess
import sys
from typing import List, Dict, Optional
from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)

COMFY_VENV_PYTHON = os.path.expanduser("~/ComfyUI/.venv_comfy/bin/python3")
MODEL_PATH = os.path.expanduser("~/ComfyUI/models/checkpoints/Deliberate_v6.safetensors")


def generate_scene_image(
    prompt: str,
    negative_prompt: str,
    output_path: str,
    width: int = 1024,
    height: int = 576,
    steps: int = 25,
) -> bool:
    """Generate a single cartoon scene image via subprocess in ComfyUI venv."""
    os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)

    script = f"""
import torch
from diffusers import StableDiffusionPipeline
import warnings
warnings.filterwarnings('ignore')

pipe = StableDiffusionPipeline.from_single_file(
    "{MODEL_PATH}",
    torch_dtype=torch.float16,
)
pipe = pipe.to("cuda")
pipe.enable_attention_slicing()

image = pipe(
    "{prompt.replace('"', "'")[:500]}",
    negative_prompt="{negative_prompt.replace('"', "'")[:200]}",
    width={width}, height={height},
    num_inference_steps={steps},
    guidance_scale=7.5,
).images[0]

image.save("{output_path}")
print("DONE")
"""

    try:
        result = subprocess.run(
            [COMFY_VENV_PYTHON, "-c", script],
            capture_output=True, text=True, timeout=120,
        )
        if result.returncode == 0 and "DONE" in result.stdout:
            logger.info(f"[sd] Generated: {output_path}")
            return True
        else:
            logger.warning(f"[sd] Failed: {result.stderr[-300:]}")
            return False
    except Exception as e:
        logger.error(f"[sd] Error: {e}")
        return False


def generate_all_scenes(
    scenes: List[Dict],
    output_dir: str,
    title_overlay: Optional[str] = None,
) -> List[str]:
    """Generate all scene images. Returns list of image paths."""
    os.makedirs(output_dir, exist_ok=True)
    image_paths = []

    for scene in scenes:
        n = scene['scene_number']
        out_path = os.path.join(output_dir, f"scene_{n:03d}.png")

        if os.path.exists(out_path):
            logger.info(f"[sd] Scene {n} already exists, skipping")
            image_paths.append(out_path)
            continue

        logger.info(f"[sd] Generating scene {n}/{len(scenes)}: {scene['title']}")
        ok = generate_scene_image(
            prompt=scene['sd_prompt'],
            negative_prompt=scene['negative_prompt'],
            output_path=out_path,
        )

        if ok:
            image_paths.append(out_path)
        else:
            logger.warning(f"[sd] Scene {n} failed, skipping")

    logger.info(f"[sd] Generated {len(image_paths)}/{len(scenes)} scenes")
    return image_paths


def add_text_overlay(
    image_path: str,
    output_path: str,
    title: str = "",
    subtitle: str = "",
) -> bool:
    """Add title text overlay to an image using Pillow."""
    try:
        img = Image.open(image_path).convert("RGBA")
        overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        w, h = img.size

        # Dark gradient bar at bottom
        for y in range(h - 120, h):
            alpha = int(180 * (y - (h - 120)) / 120)
            draw.rectangle([(0, y), (w, y)], fill=(0, 0, 0, alpha))

        # Try to load a font, fall back to default
        try:
            font_title = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 36)
            font_sub = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 24)
        except Exception:
            font_title = ImageFont.load_default()
            font_sub = font_title

        if title:
            draw.text((w // 2, h - 80), title, font=font_title, fill=(255, 255, 255, 230), anchor="mm")
        if subtitle:
            draw.text((w // 2, h - 40), subtitle, font=font_sub, fill=(200, 200, 200, 200), anchor="mm")

        combined = Image.alpha_composite(img, overlay).convert("RGB")
        combined.save(output_path)
        return True
    except Exception as e:
        logger.error(f"[sd] Text overlay failed: {e}")
        return False

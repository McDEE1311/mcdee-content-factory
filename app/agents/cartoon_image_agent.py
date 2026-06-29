"""
Cartoon Image Agent
Reads a storyboard JSON and generates one SD image per scene.
Runs in ComfyUI venv to avoid CUDA conflicts with Ollama.
"""
import logging
import os
import subprocess
import json
from typing import List, Dict

logger = logging.getLogger(__name__)

COMFY_PYTHON = os.path.expanduser("~/ComfyUI/.venv_comfy/bin/python3")
MODEL_PATH = os.path.expanduser("~/ComfyUI/models/checkpoints/Deliberate_v6.safetensors")


def unload_ollama():
    """Release Ollama GPU memory before running SD."""
    import httpx
    try:
        httpx.post(
            "http://127.0.0.1:11434/api/generate",
            json={"model": "qwen2.5:32b-instruct-q4_K_M", "prompt": "", "keep_alive": "0s"},
            timeout=10.0,
        )
        import time; time.sleep(3)
        logger.info("[cartoon] Ollama GPU memory released")
    except Exception as e:
        logger.warning(f"[cartoon] Could not unload Ollama: {e}")


def generate_images_from_storyboard(
    storyboard: List[dict],
    output_dir: str,
    width: int = 1024,
    height: int = 576,
    steps: int = 25,
    skip_existing: bool = True,
) -> List[str]:
    """
    Generate images for all storyboard scenes.
    Returns list of image paths in scene order.
    """
    os.makedirs(output_dir, exist_ok=True)
    unload_ollama()

    # Build generation script to run in ComfyUI venv
    scenes_data = json.dumps([{
        "n": s["scene_number"],
        "prompt": s.get("image_prompt", "documentary illustration, cinematic scene"),
        "neg": s.get("negative_prompt", "photo, realistic, blurry, watermark, text"),
        "seed": s.get("seed"),
    } for s in storyboard])

    script = f"""
import torch, json, os
from diffusers import StableDiffusionPipeline

torch.cuda.empty_cache()
os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"

pipe = StableDiffusionPipeline.from_single_file(
    "{MODEL_PATH}", torch_dtype=torch.float16,
)
pipe = pipe.to("cuda")
pipe.enable_attention_slicing()

scenes = json.loads({repr(scenes_data)})
output_dir = {repr(output_dir)}
skip_existing = {skip_existing}
generated = []

for s in scenes:
    out = os.path.join(output_dir, f"scene_{{s['n']:03d}}.png")
    if skip_existing and os.path.exists(out):
        print(f"SKIP {{s['n']}}")
        generated.append(out)
        continue
    
    gen = torch.Generator("cuda").manual_seed(s['seed']) if s.get('seed') else None
    try:
        image = pipe(
            s['prompt'][:400], negative_prompt=s['neg'][:200],
            width={width}, height={height},
            num_inference_steps={steps}, guidance_scale=7.5,
            generator=gen,
        ).images[0]
        image.save(out)
        torch.cuda.empty_cache()
        generated.append(out)
        print(f"DONE {{s['n']}}: {{out}}")
    except Exception as e:
        print(f"FAIL {{s['n']}}: {{e}}")

print(f"TOTAL: {{len(generated)}}")
"""

    result = subprocess.run(
        [COMFY_PYTHON, "-c", script],
        capture_output=True, text=True, timeout=3600,
    )

    paths = []
    for line in result.stdout.split('\n'):
        if line.startswith("DONE ") or line.startswith("SKIP "):
            parts = line.split(": ", 1)
            if len(parts) > 1:
                paths.append(parts[1].strip())

    if result.returncode != 0:
        logger.error(f"[cartoon] Generation errors: {result.stderr[-500:]}")

    logger.info(f"[cartoon] Generated {len(paths)}/{len(storyboard)} images")
    return sorted(paths)

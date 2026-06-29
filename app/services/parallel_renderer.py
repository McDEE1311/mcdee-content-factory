"""
Parallel Renderer
Uses all available GPUs and CPU cores simultaneously.

GPU 0 (3090): Main scene generation (Juggernaut XL, 80 scenes)
GPU 1 (3060A): Whisper + Short scenes
GPU 2 (3060B): Thumbnail generation
CPU: ffmpeg rendering, Ken Burns, audio (parallel workers)
"""
import json
import logging
import os
import subprocess
import glob
import threading
import time
from typing import List, Dict, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

logger = logging.getLogger(__name__)

COMFY_PYTHON = os.path.expanduser("~/ComfyUI/.venv_comfy/bin/python3")
JUGGERNAUT = os.path.expanduser("~/ComfyUI/models/checkpoints/Juggernaut-XL-v9.safetensors")

# GPU assignments
GPU_3090 = "0"   # Main scenes
GPU_3060A = "1"  # Whisper + research
GPU_3060B = "2"  # Thumbnails + shorts


def generate_scenes_gpu(
    scenes_data: List[Dict],
    output_dir: str,
    gpu_id: str = GPU_3090,
    width: int = 1280,
    height: int = 720,
    steps: int = 28,
) -> int:
    """Generate scene images on specified GPU."""
    os.makedirs(output_dir, exist_ok=True)

    sd_script = f"""
import torch, json, os
from diffusers import StableDiffusionXLPipeline

os.environ["CUDA_VISIBLE_DEVICES"] = "{gpu_id}"
os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"
torch.cuda.empty_cache()

pipe = StableDiffusionXLPipeline.from_single_file(
    "{JUGGERNAUT}", torch_dtype=torch.float16, use_safetensors=True
)
pipe = pipe.to("cuda")
pipe.enable_attention_slicing()

scenes = json.loads({repr(json.dumps(scenes_data))})
output_dir = {repr(output_dir)}
done = 0

for s in scenes:
    out = os.path.join(output_dir, f"scene_{{s['n']:03d}}.png")
    if os.path.exists(out):
        done += 1
        continue
    gen = torch.Generator("cuda").manual_seed(s['seed']) if s.get('seed') else None
    try:
        image = pipe(
            s['prompt'][:450], negative_prompt=s.get('neg', '')[:200],
            width={width}, height={height},
            num_inference_steps={steps}, guidance_scale=7.5,
            generator=gen,
        ).images[0]
        image.save(out)
        torch.cuda.empty_cache()
        done += 1
        print(f"DONE {{s['n']}}/{{len(scenes)}}", flush=True)
    except Exception as e:
        print(f"FAIL {{s['n']}}: {{e}}", flush=True)

print(f"TOTAL_DONE: {{done}}")
"""
    env = os.environ.copy()
    env["CUDA_VISIBLE_DEVICES"] = gpu_id

    result = subprocess.run(
        [COMFY_PYTHON, "-c", sd_script],
        capture_output=True, text=True, timeout=7200, env=env,
    )
    done = len(glob.glob(os.path.join(output_dir, "scene_*.png")))
    logger.info(f"[parallel] GPU{gpu_id} scenes: {done} generated")
    return done


def generate_thumbnail_gpu(
    prompt: str,
    output_path: str,
    gpu_id: str = GPU_3060B,
    seed: int = 4242,
) -> bool:
    """Generate thumbnail on a separate GPU simultaneously."""

    thumb_script = f"""
import torch, os
from diffusers import StableDiffusionXLPipeline
from PIL import Image, ImageDraw, ImageFont

os.environ["CUDA_VISIBLE_DEVICES"] = "{gpu_id}"
os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"
torch.cuda.empty_cache()

pipe = StableDiffusionXLPipeline.from_single_file(
    "{JUGGERNAUT}", torch_dtype=torch.float16, use_safetensors=True
)
pipe = pipe.to("cuda")
pipe.enable_attention_slicing()

image = pipe(
    {repr(prompt[:450])},
    negative_prompt="blurry, watermark, text, anime, cartoon, low quality, ugly, deformed",
    width=1280, height=720,
    num_inference_steps=35, guidance_scale=7.5,
    generator=torch.Generator("cuda").manual_seed({seed}),
).images[0]

image.save("{output_path}")
print(f"THUMB_DONE: {{os.path.getsize('{output_path}')//1024}}KB")
"""
    env = os.environ.copy()
    env["CUDA_VISIBLE_DEVICES"] = gpu_id

    result = subprocess.run(
        [COMFY_PYTHON, "-c", thumb_script],
        capture_output=True, text=True, timeout=300, env=env,
    )
    success = os.path.exists(output_path) and os.path.getsize(output_path) > 10000
    logger.info(f"[parallel] Thumbnail GPU{gpu_id}: {'OK' if success else 'FAILED'}")
    return success


def run_whisper_cpu(audio_path: str, timing_path: str) -> List[Dict]:
    """Run Whisper on CPU (saves GPU for image generation)."""
    from app.services.scene_timing import analyze_audio
    logger.info("[parallel] Running Whisper on CPU...")
    return analyze_audio(audio_path, timing_path)


def render_ken_burns_parallel(
    scene_images: List[str],
    clips_dir: str,
    max_workers: int = 4,
) -> List[str]:
    """
    Pre-render Ken Burns clips using parallel CPU ffmpeg workers.
    Uses all 8 CPU cores.
    """
    os.makedirs(clips_dir, exist_ok=True)
    effects = [
        "scale=8000:-1,zoompan=z='min(zoom+0.0004,1.3)':d=125:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1920x1080:fps=25",
        "scale=8000:-1,zoompan=z='if(lte(zoom,1.0),1.3,max(1.001,zoom-0.0004))':d=125:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1920x1080:fps=25",
        "scale=8000:-1,zoompan=z='1.2':d=125:x='iw*0.08*(on/125)':y='ih/2-(ih/zoom/2)':s=1920x1080:fps=25",
        "scale=8000:-1,zoompan=z='1.2':d=125:x='iw*0.08*(1-on/125)':y='ih/2-(ih/zoom/2)':s=1920x1080:fps=25",
        "scale=8000:-1,zoompan=z='min(zoom+0.0004,1.3)':d=125:x='iw*0.05':y='ih*0.05':s=1920x1080:fps=25",
    ]

    def render_one(args):
        i, img = args
        clip_out = os.path.join(clips_dir, f"clip_{i+1:03d}.mp4")
        if os.path.exists(clip_out):
            return clip_out

        effect = effects[i % len(effects)]
        r = subprocess.run([
            "ffmpeg", "-y", "-loop", "1", "-t", "8", "-i", img,
            "-vf", effect, "-c:v", "libx264", "-preset", "fast",
            "-crf", "23", "-pix_fmt", "yuv420p", "-t", "7", clip_out
        ], capture_output=True, timeout=90)

        if r.returncode != 0:
            subprocess.run([
                "ffmpeg", "-y", "-loop", "1", "-t", "7", "-i", img,
                "-vf", "scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,setsar=1,fps=25",
                "-c:v", "libx264", "-preset", "fast", "-pix_fmt", "yuv420p", clip_out
            ], capture_output=True, timeout=30)

        return clip_out if os.path.exists(clip_out) else None

    logger.info(f"[parallel] Ken Burns: {len(scene_images)} clips, {max_workers} workers...")

    clip_paths = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(render_one, (i, img)): i
                   for i, img in enumerate(scene_images)}
        for future in as_completed(futures):
            result = future.result()
            if result:
                clip_paths.append(result)
            if len(clip_paths) % 10 == 0:
                logger.info(f"  Clips done: {len(clip_paths)}/{len(scene_images)}")

    clip_paths = sorted([p for p in clip_paths if p])
    logger.info(f"[parallel] Ken Burns complete: {len(clip_paths)} clips")
    return clip_paths


def parallel_pipeline(
    topic: str,
    category: str,
    output_dir: str,
    script_text: str,
    wav_path: str,
    scene_prompts: List[Dict],
    thumbnail_prompt: str,
    voice: str = "bm_george",
) -> Dict:
    """
    Run all GPU and CPU tasks in parallel where possible.

    Phase 1 (parallel):
      - 3090: Generate 80 video scenes
      - 3060B: Generate thumbnail
      - CPU: Whisper timing

    Phase 2 (parallel after Phase 1):
      - CPU x4: Ken Burns clips (parallel ffmpeg)
      - 3060A: Generate 3 Short scenes

    Phase 3:
      - CPU: Final render + Shorts render
    """
    scenes_dir = os.path.join(output_dir, "scenes")
    clips_dir = os.path.join(output_dir, "clips")
    thumb_base = os.path.join(output_dir, "thumbnail_base.png")
    timing_path = os.path.join(output_dir, "timing.json")

    results = {}

    logger.info("[parallel] PHASE 1: Scenes + Thumbnail + Whisper simultaneously")

    # Start all Phase 1 tasks in parallel threads
    with ThreadPoolExecutor(max_workers=3) as executor:

        # Task A: 3090 — video scenes
        future_scenes = executor.submit(
            generate_scenes_gpu,
            scene_prompts, scenes_dir, GPU_3090
        )

        # Task B: 3060B — thumbnail (runs while 3090 does scenes)
        future_thumb = executor.submit(
            generate_thumbnail_gpu,
            thumbnail_prompt, thumb_base, GPU_3060B
        )

        # Task C: CPU — Whisper timing
        future_timing = executor.submit(
            run_whisper_cpu,
            wav_path, timing_path
        )

        # Wait for all Phase 1 to complete
        results["scenes_done"] = future_scenes.result()
        results["thumb_done"] = future_thumb.result()
        results["scene_list"] = future_timing.result()

    logger.info(f"[parallel] Phase 1 complete: {results['scenes_done']} scenes, "
                f"thumb={'OK' if results['thumb_done'] else 'FAIL'}, "
                f"{len(results['scene_list'])} timing points")

    # Phase 2: Ken Burns with parallel CPU workers
    logger.info("[parallel] PHASE 2: Ken Burns clips (4 parallel workers)")
    scene_images = sorted(glob.glob(os.path.join(scenes_dir, "scene_*.png")))
    results["clips"] = render_ken_burns_parallel(
        scene_images, clips_dir, max_workers=4
    )

    logger.info(f"[parallel] Phase 2 complete: {len(results['clips'])} clips")
    return results

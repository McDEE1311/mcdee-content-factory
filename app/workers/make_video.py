"""
make_video.py V6 — Full Story-First Pipeline
Research → Verified Characters → Visual Bible → Storyboard → Script → Video

Key improvements:
- Automated verified character bible (Wikidata + Wikipedia + Ollama)
- Visual bible (locations, objects, evidence items)
- Story classifier + narrative DNA
- Camera diversity rules (no consecutive repeats)
- Sub-focus variation within repeated storyboard events
- Thumbnail generated from character bible + story type
- Short style prefix (story content dominates prompts)
"""
import argparse
import json
import logging
import os
import re
import subprocess
import glob
from datetime import date
from concurrent.futures import ThreadPoolExecutor, as_completed

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

COMFY_PYTHON = os.path.expanduser("~/ComfyUI/.venv_comfy/bin/python3")
JUGGERNAUT = os.path.expanduser("~/ComfyUI/models/checkpoints/Juggernaut-XL-v9.safetensors")


def slugify(t):
    t = t.lower().strip()
    t = re.sub(r'[^\w\s-]', '', t)
    t = re.sub(r'[\s_-]+', '-', t)
    return t[:70]


def unload_ollama():
    try:
        import httpx
        httpx.post("http://127.0.0.1:11434/api/generate",
                   json={"model":"qwen2.5:32b-instruct-q4_K_M","prompt":"","keep_alive":"0s"},
                   timeout=10.0)
        import time; time.sleep(4)
        logger.info("[GPU] Ollama unloaded")
    except Exception:
        pass


def render_kb_clip(args):
    i, img, clips_dir = args
    clip_out = os.path.join(clips_dir, f"clip_{i+1:03d}.mp4")
    if os.path.exists(clip_out):
        return clip_out
    effects = [
        "scale=8000:-1,zoompan=z='min(zoom+0.0004,1.3)':d=175:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1920x1080:fps=25",
        "scale=8000:-1,zoompan=z='if(lte(zoom,1.0),1.3,max(1.001,zoom-0.0004))':d=175:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1920x1080:fps=25",
        "scale=8000:-1,zoompan=z='1.25':d=175:x='iw*0.08*(on/175)':y='ih/2-(ih/zoom/2)':s=1920x1080:fps=25",
        "scale=8000:-1,zoompan=z='1.25':d=175:x='iw*0.08*(1-on/175)':y='ih/2-(ih/zoom/2)':s=1920x1080:fps=25",
        "scale=8000:-1,zoompan=z='min(zoom+0.0004,1.3)':d=175:x='iw*0.05':y='ih*0.05':s=1920x1080:fps=25",
    ]
    r = subprocess.run([
        "ffmpeg", "-y", "-loop", "1", "-t", "10", "-i", img,
        "-vf", effects[i % len(effects)],
        "-c:v", "libx264", "-preset", "fast", "-crf", "22",
        "-pix_fmt", "yuv420p", "-t", "9", clip_out
    ], capture_output=True, timeout=90)
    if r.returncode != 0:
        subprocess.run([
            "ffmpeg", "-y", "-loop", "1", "-t", "9", "-i", img,
            "-vf", "scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,setsar=1,fps=25",
            "-c:v", "libx264", "-preset", "fast", "-pix_fmt", "yuv420p", clip_out
        ], capture_output=True, timeout=30)
    return clip_out if os.path.exists(clip_out) else None


def generate_thumbnail_gpu(thumb_prompt, output_path, gpu_id="2", seed=4242):
    os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)
    script = f"""
import torch, os
from diffusers import StableDiffusionXLPipeline
os.environ["CUDA_VISIBLE_DEVICES"] = "{gpu_id}"
os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"
torch.cuda.empty_cache()
pipe = StableDiffusionXLPipeline.from_single_file(
    "{JUGGERNAUT}", torch_dtype=torch.float16, use_safetensors=True)
pipe = pipe.to("cuda")
pipe.enable_attention_slicing()
img = pipe({repr(thumb_prompt[:480])},
    negative_prompt="blurry, watermark, text, anime, cartoon, low quality, ugly, deformed",
    width=1280, height=720, num_inference_steps=35, guidance_scale=7.5,
    generator=torch.Generator("cuda").manual_seed({seed})).images[0]
img.save("{output_path}")
print(f"THUMB: {{os.path.getsize('{output_path}')//1024}}KB")
"""
    env = os.environ.copy()
    env["CUDA_VISIBLE_DEVICES"] = gpu_id
    r = subprocess.run([COMFY_PYTHON, "-c", script],
                       capture_output=True, text=True, timeout=300, env=env)
    ok = os.path.exists(output_path) and os.path.getsize(output_path) > 10000
    logger.info(f"[Thumb GPU{gpu_id}] {'OK' if ok else 'FAILED'}")
    return ok


def make_video(topic: str, category: str = "financial_rise_fall", voice: str = "bm_george"):
    today = date.today().strftime("%Y-%m-%d")
    slug = slugify(topic)
    output_dir = os.path.join("outputs", "videos", today, slug)
    scenes_dir = os.path.join(output_dir, "scenes")
    clips_dir = os.path.join(output_dir, "clips")
    shorts_dir = os.path.join(output_dir, "shorts")
    for d in [output_dir, scenes_dir, clips_dir, shorts_dir]:
        os.makedirs(d, exist_ok=True)

    logger.info("=" * 60)
    logger.info("TREND FORGE V6 — VERIFIED STORY-FIRST PIPELINE")
    logger.info(f"Topic:    {topic}")
    logger.info(f"Category: {category} | Voice: {voice}")
    logger.info(f"Output:   {output_dir}")
    logger.info("=" * 60)

    # ── STEP 0: DEEP RESEARCH ────────────────────────────────────────────
    research_path = os.path.join(output_dir, "research.json")
    if os.path.exists(research_path):
        logger.info("STEP 0: Research exists — loading")
        from app.agents.deep_research_agent import load_research
        research = load_research(research_path)
    else:
        logger.info("STEP 0: V6 Deep Research (Wikidata + Wikipedia + Ollama)...")
        from app.agents.deep_research_agent import deep_research, save_research
        research = deep_research(topic, category)
        save_research(research, research_path)
        chars = list(research.get("characters", {}).keys())
        storyboard_count = len(research.get("storyboard", []))
        logger.info(f"STEP 0 DONE: chars={chars} storyboard={storyboard_count} scenes")

    characters = research.get("characters", {})
    locations = research.get("locations", {})
    visual_bible = research.get("visual_bible", {})
    storyboard = research.get("storyboard", [])
    primary_char = list(characters.values())[0] if characters else {}

    if primary_char:
        conf = primary_char.get("confidence", 0)
        logger.info(f"Primary: {primary_char.get('name')} "
                    f"conf={conf:.2f} — {primary_char.get('sd_character_prompt','')[:80]}")

    # ── STEP 0B: STORY CLASSIFICATION ────────────────────────────────────
    story_dna_path = os.path.join(output_dir, "story_dna.json")
    if os.path.exists(story_dna_path):
        story_dna = json.load(open(story_dna_path))
    else:
        from app.agents.story_classifier import classify_and_extract_dna
        story_dna = classify_and_extract_dna(topic, research)
        json.dump(story_dna, open(story_dna_path, "w"), indent=2)
    logger.info(f"Story type: {story_dna.get('story_type')} | "
                f"Q: {story_dna.get('viewer_question','')[:60]}")

    # ── STEP 1: SCRIPT FROM STORYBOARD ───────────────────────────────────
    script_path = os.path.join(output_dir, "script.txt")
    if os.path.exists(script_path):
        logger.info("STEP 1: Script exists — loading")
        script_text = open(script_path).read()
    else:
        logger.info("STEP 1: Generating script from storyboard + story DNA...")
        from app.agents.script_agent_v5 import generate_script_from_storyboard
        # Inject story DNA into research for script agent
        research["story_dna"] = story_dna
        script_text = generate_script_from_storyboard(topic, category, research)
        open(script_path, "w").write(script_text)
        logger.info(f"STEP 1 DONE: {len(script_text.split())} words")

    word_count = len(script_text.split())
    logger.info(f"Script: {word_count} words")

    # ── STEP 2: NARRATION ────────────────────────────────────────────────
    wav_path = os.path.join(output_dir, "narration.wav")
    if os.path.exists(wav_path):
        logger.info("STEP 2: Narration exists — skipping")
    else:
        logger.info(f"STEP 2: Generating narration ({voice})...")
        from app.services.kokoro_tts import generate_wav_chunked
        from app.services.text_normalizer import normalize_for_tts
        clean = re.sub(r'\[.*?\]', '', script_text)
        clean = re.sub(r'#{1,4}\s*', '', clean)
        clean = re.sub(r'\n{3,}', '\n\n', clean).strip()
        clean = normalize_for_tts(clean)
        ok = generate_wav_chunked(clean, wav_path, voice=voice)
        if not ok:
            logger.error("STEP 2 FAILED"); return None
        logger.info(f"STEP 2 DONE: {os.path.getsize(wav_path)//1024//1024}MB")

    # ── STEP 3: WHISPER TIMING ───────────────────────────────────────────
    timing_path = os.path.join(output_dir, "timing.json")
    if os.path.exists(timing_path):
        logger.info("STEP 3: Timing exists — loading")
        scene_list = json.load(open(timing_path))["scenes"]
    else:
        logger.info("STEP 3: Whisper scene timing...")
        from app.services.scene_timing import analyze_audio
        scene_list = analyze_audio(wav_path, timing_path)
        logger.info(f"STEP 3 DONE: {len(scene_list)} natural pause points")

    num_timing_points = len(scene_list)
    logger.info(f"Timing: {num_timing_points} scene cut points")

    # ── STEP 4: EXPAND STORYBOARD WITH VISUAL BIBLE ──────────────────────
    logger.info("STEP 4: Expanding storyboard with visual bible + diversity rules...")
    from app.agents.scene_planner import expand_storyboard_to_match_timing
    expanded_scenes = expand_storyboard_to_match_timing(
        storyboard, scene_list, characters, locations, visual_bible
    )
    num_scenes = len(expanded_scenes)
    logger.info(f"STEP 4 DONE: {num_scenes} unique scene prompts")

    # Log sample to verify quality
    for sp in expanded_scenes[:3]:
        logger.info(f"  Scene {sp['n']}: [{sp['act']}] {sp.get('title','')[:35]} "
                    f"cam={sp.get('camera','')} seed={sp.get('seed')}")
        logger.info(f"    Prompt: {sp['sd_prompt'][:120]}")

    # ── STEP 5: PARALLEL GPU GENERATION ──────────────────────────────────
    existing_scenes = sorted(glob.glob(os.path.join(scenes_dir, "scene_*.png")))
    thumb_base = os.path.join(output_dir, "thumbnail_base.png")

    if len(existing_scenes) >= num_scenes:
        logger.info(f"STEP 5: {len(existing_scenes)} scenes exist — skipping")
    else:
        logger.info(f"STEP 5: Parallel GPU generation...")
        logger.info(f"  GPU 0 (3090): {num_scenes} scenes (Deliberate v6 2D doc)")
        logger.info(f"  GPU 2 (3060B): thumbnail (Juggernaut XL)")
        unload_ollama()

        # Build thumbnail prompt from verified character + story
        char_sd = primary_char.get("sd_character_prompt", "documentary subject")
        story_type = story_dna.get("story_type", "fraud")
        stakes = story_dna.get("stakes", "")
        thumb_prompt = (
            f"cinematic documentary thumbnail, semi-realistic illustration, "
            f"{char_sd}, "
            f"intense expression looking at camera, "
            f"dramatic dark background, {story_type} story atmosphere, "
            f"Netflix documentary poster quality, high detail face, "
            f"strong dramatic shadows"
        )
        logger.info(f"  Thumbnail: {thumb_prompt[:100]}")

        from app.agents.scene_planner import generate_scenes_deliberate
        with ThreadPoolExecutor(max_workers=2) as executor:
            future_scenes = executor.submit(
                generate_scenes_deliberate, expanded_scenes, scenes_dir, "0"
            )
            future_thumb = executor.submit(
                generate_thumbnail_gpu, thumb_prompt, thumb_base, "2",
                primary_char.get("sd_seed", 4242)
            )
            scenes_done = future_scenes.result()
            thumb_ok = future_thumb.result()

        scene_images = sorted(glob.glob(os.path.join(scenes_dir, "scene_*.png")))
        logger.info(f"STEP 5 DONE: {len(scene_images)} scenes, thumb={'OK' if thumb_ok else 'FAIL'}")

    # ── STEP 6: KEN BURNS CLIPS ──────────────────────────────────────────
    scene_images = sorted(glob.glob(os.path.join(scenes_dir, "scene_*.png")))
    existing_clips = sorted(glob.glob(os.path.join(clips_dir, "clip_*.mp4")))

    if len(existing_clips) >= len(scene_images):
        logger.info(f"STEP 6: {len(existing_clips)} clips exist — skipping")
    else:
        logger.info(f"STEP 6: Ken Burns (4 parallel CPU workers)...")
        args = [(i, img, clips_dir) for i, img in enumerate(scene_images)]
        clips_done = []
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = {executor.submit(render_kb_clip, a): a for a in args}
            for f in as_completed(futures):
                r = f.result()
                if r:
                    clips_done.append(r)
        logger.info(f"STEP 6 DONE: {len(clips_done)} clips")

    # ── STEP 7: RENDER VIDEO ─────────────────────────────────────────────
    video_path = os.path.join(output_dir, "video.mp4")
    if os.path.exists(video_path):
        logger.info("STEP 7: Video exists — skipping")
    else:
        logger.info("STEP 7: Rendering with Whisper timing...")
        clips = sorted(glob.glob(os.path.join(clips_dir, "clip_*.mp4")))
        r = subprocess.run(
            ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
             "-of", "csv=p=0", wav_path],
            capture_output=True, text=True)
        duration = float(r.stdout.strip())

        concat_file = os.path.join(clips_dir, "concat_timed.txt")
        with open(concat_file, "w") as f:
            for i, scene in enumerate(scene_list):
                clip_idx = min(i, len(clips) - 1)
                f.write(f"file '{os.path.abspath(clips[clip_idx])}'\n")
                f.write(f"duration {scene['duration']:.3f}\n")

        raw = os.path.join(output_dir, "raw.mp4")
        r2 = subprocess.run([
            "ffmpeg", "-y", "-f", "concat", "-safe", "0",
            "-i", concat_file, "-c:v", "libx264", "-preset", "fast",
            "-crf", "22", "-pix_fmt", "yuv420p", "-vsync", "cfr", "-r", "25", raw
        ], capture_output=True, timeout=600)

        if r2.returncode != 0:
            cycle_file = os.path.join(clips_dir, "concat_cycle.txt")
            needed = int(duration / 7.0) + 2
            with open(cycle_file, "w") as f:
                for i in range(needed):
                    f.write(f"file '{os.path.abspath(clips[i % len(clips)])}'\n")
            subprocess.run([
                "ffmpeg", "-y", "-f", "concat", "-safe", "0",
                "-i", cycle_file, "-c", "copy", "-t", str(duration), raw
            ], capture_output=True, timeout=300)

        subprocess.run([
            "ffmpeg", "-y", "-i", raw, "-i", wav_path,
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
            "-shortest", video_path
        ], capture_output=True, timeout=120)

        if os.path.exists(raw):
            os.remove(raw)

        if os.path.exists(video_path):
            mb = os.path.getsize(video_path) / 1024 / 1024
            logger.info(f"STEP 7 DONE: {mb:.1f}MB")
        else:
            logger.error("STEP 7 FAILED"); return None

    # ── STEP 8: THUMBNAIL WITH SMART TEXT ────────────────────────────────
    thumb_final = os.path.join(output_dir, "thumbnail.png")
    if os.path.exists(thumb_final):
        logger.info("STEP 8: Thumbnail exists")
    elif os.path.exists(thumb_base):
        logger.info("STEP 8: Adding smart text overlay...")
        from PIL import Image, ImageDraw, ImageFont

        # Smart thumbnail text from story DNA
        stakes = story_dna.get("stakes", "")
        story_type_upper = story_dna.get("story_type", "").upper()
        char_name = primary_char.get("name", "")

        # Extract money amount if present
        money_match = re.search(r'\$[\d\.]+ (?:billion|million|trillion)', stakes, re.IGNORECASE)
        money_str = money_match.group(0).upper() if money_match else ""

        # Build thumbnail lines
        if money_str:
            line1 = money_str
            line2 = "LIE"
        elif char_name:
            name_parts = char_name.upper().split()
            line1 = " ".join(name_parts[:2]) if name_parts else "THE LIE"
            line2 = story_type_upper if story_type_upper else "EXPOSED"
        else:
            words = topic.upper().split()
            skip = {"THE","HOW","AND","WHO","THAT","THIS","WHAT","WHY","A","AN","EVERYONE"}
            key_words = [w for w in words if w not in skip]
            line1 = " ".join(key_words[:3])
            line2 = " ".join(key_words[3:5]) if len(key_words) > 3 else ""

        img = Image.open(thumb_base).convert("RGBA")
        overlay = Image.new("RGBA", img.size, (0,0,0,0))
        draw = ImageDraw.Draw(overlay)
        w, h = img.size

        for y in range(int(h*0.5), h):
            alpha = int(215 * (y - int(h*0.5)) / (h*0.5))
            draw.rectangle([(0,y),(w,y)], fill=(0,0,0,alpha))

        try:
            fh = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 110)
            fl = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 72)
            fm = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 38)
        except:
            fh = fl = fm = ImageFont.load_default()

        # Line 1: big red number/name
        draw.text((w//2+4, h-200+4), line1, font=fh, fill=(0,0,0,200), anchor="mm")
        draw.text((w//2, h-200), line1, font=fh, fill=(220,30,30,255), anchor="mm")
        # Line 2: white — same size as line 1 for impact
        if line2:
            draw.text((w//2+3, h-90+3), line2, font=fh, fill=(0,0,0,200), anchor="mm")
            draw.text((w//2, h-90), line2, font=fh, fill=(255,255,255,255), anchor="mm")
        # NO watermark/logo — looks amateur, hurts CTR

        Image.alpha_composite(img, overlay).convert("RGB").save(thumb_final)
        logger.info(f"STEP 8 DONE: '{line1}' / '{line2}'")

    # ── STEP 9: SHORTS ───────────────────────────────────────────────────
    existing_shorts = glob.glob(os.path.join(shorts_dir, "*/short.mp4"))
    if existing_shorts:
        logger.info(f"STEP 9: {len(existing_shorts)} Shorts exist")
    else:
        logger.info("STEP 9: Generating 3 Shorts...")
        try:
            from app.services.shorts_generator import generate_shorts_package
            scene_images_list = sorted(glob.glob(os.path.join(scenes_dir, "scene_*.png")))
            shorts = generate_shorts_package(
                long_video_path=video_path, script_text=script_text,
                title=topic, topic=topic, output_dir=shorts_dir,
                scene_images=scene_images_list, voice=voice,
            )
            logger.info(f"STEP 9 DONE: {len(shorts)} Shorts")
        except Exception as e:
            logger.warning(f"STEP 9 SKIPPED: {e}")

    # ── STEP 10: SEO ─────────────────────────────────────────────────────
    meta_path = os.path.join(output_dir, "metadata.json")
    if not os.path.exists(meta_path):
        from app.services.ollama_client import ollama_client
        try:
            seo = ollama_client.generate_json(
                f"YouTube SEO for: {topic}\n"
                f"Story type: {story_dna.get('story_type','')}\n"
                f"Output JSON: youtube_title (specific, curiosity-driven, under 60 chars), "
                f"description (500+ words), tags (list), chapters, pinned_comment",
                temperature=0.7) or {}
        except Exception:
            seo = {}
        json.dump({
            "topic": topic, "category": category, "voice": voice,
            "word_count": word_count, "scene_count": num_scenes,
            "story_type": story_dna.get("story_type"),
            "characters": {k: v.get("name") for k, v in characters.items()},
            "character_confidence": {k: v.get("confidence", 0) for k, v in characters.items()},
            "seo": seo,
        }, open(meta_path, "w"), indent=2)
        logger.info("STEP 10 DONE: SEO saved")

    logger.info("=" * 60)
    logger.info(f"V6 COMPLETE: {output_dir}")
    logger.info(f"Script: {word_count}w | Scenes: {num_scenes} | Story: {story_dna.get('story_type')}")
    logger.info(f"Characters: {[v.get('name') for v in characters.values()]}")
    logger.info(f"Video: {video_path}")
    logger.info("=" * 60)
    return output_dir


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Trend Forge V6")
    parser.add_argument("--topic", required=True)
    parser.add_argument("--category", default="financial_rise_fall",
                        choices=["dark_history","financial_rise_fall","historical_mystery",
                                 "survival_stories","space_mysteries"])
    parser.add_argument("--voice", default="bm_george",
                        choices=["bm_george","am_onyx","bm_daniel","am_eric"])
    args = parser.parse_args()
    make_video(args.topic, args.category, args.voice)

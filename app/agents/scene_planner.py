"""
Scene Planner V6
Expands storyboard events to match Whisper timing.
Uses visual bible for specific prompts.
Enforces camera/composition diversity — no consecutive repeats.
"""
import json
import logging
import os
import subprocess
import glob
from typing import List, Dict

logger = logging.getLogger(__name__)

COMFY_PYTHON = os.path.expanduser("~/ComfyUI/.venv_comfy/bin/python3")
DELIBERATE_MODEL = os.path.expanduser("~/ComfyUI/models/checkpoints/Deliberate_v6.safetensors")

# SHORT style prefix — story content must dominate
# Cinematic painterly documentary style — rich environments, simplified characters
# Inspired by: MagnatesMedia, James Jani, Johnny Harris visual approach
# Style prefix UNDER 60 chars — story content must dominate the prompt
# MI6 video style: simplified characters, rich detailed environments
DOCUMENTARY_STYLE = "cinematic painterly illustration, dramatic lighting, "

DOCUMENTARY_NEG = (
    "photo, 3d render, blurry, watermark, text, anime, "
    "flat shading, clean linework, generic cartoon, low quality, "
    "ugly, deformed, floating portrait, empty room, "
    "stock photo, suburbs, roads, generic buildings, "
    "photorealistic face, hyperrealistic skin"
)

# Camera rotation — never repeat same angle consecutively
CAMERA_SEQUENCE = [
    "medium shot",
    "close-up portrait shot",
    "wide establishing shot",
    "dutch angle dramatic shot",
    "over shoulder shot",
    "close-up shot",
    "wide shot",
    "medium close-up",
    "overhead bird's eye view",
    "low angle looking up",
]

# Sub-scene types following MI6 documentary style
# Each sub-scene creates genuinely different visual content within same story beat
SUB_FOCUSES = [
    "",  # default: use storyboard sd_scene_prompt directly
    "wide shot: character silhouette small against large detailed architectural environment",
    "evidence close-up: financial documents, account statements, forged papers, court filings",
    "crowd perspective: many ordinary people affected, human scale of the story",
    "symbolic scene: abstract visualization of money flows, charts, scale of fraud",
    "environment only: richly detailed location with no character, atmospheric establishing",
    "consequence scene: aftermath, empty offices, locked doors, news cameras outside",
    "investigation scene: detective, journalist, or regulator examining documents",
]


def build_character_sheet_prompt(character: Dict) -> str:
    name = character.get("name", "subject")
    hair = character.get("hair_color", "") + " " + character.get("hair_style", "")
    eyes = character.get("eye_color", "")
    clothing = character.get("signature_clothing", "professional attire")
    build = character.get("build", "average")
    age = character.get("age_in_story", "adult")
    expression = character.get("typical_expression", "serious expression")

    parts = [p for p in [name, age, build, hair.strip(), eyes, clothing, expression] if p.strip()]
    return ", ".join(parts)


def build_scene_prompt_v6(
    scene: Dict,
    characters: Dict,
    locations: Dict,
    scene_number: int,
    total_scenes: int,
    visual_bible: Dict = None,
    camera_override: str = None,
    sub_focus: str = "",
) -> Dict:
    char_name = scene.get("character", "")
    char_desc = ""
    char_seed = None

    if char_name and characters:
        for key, char in characters.items():
            char_full = char.get("name", "").lower()
            if any(part in char_full for part in char_name.lower().split() if len(part) > 2):
                char_desc = build_character_sheet_prompt(char)
                char_seed = char.get("sd_seed")
                break

    # Get the storyboard's own SD prompt — the story-specific content
    storyboard_sd = str(scene.get("sd_scene_prompt") or "").strip()
    action = scene.get("action", "documentary scene")
    location = scene.get("location", "")
    emotion = scene.get("emotion", "dramatic")
    act = scene.get("act", "EVIDENCE")
    importance = scene.get("importance", "supporting")
    camera = camera_override or CAMERA_SEQUENCE[scene_number % len(CAMERA_SEQUENCE)]

    # Try to find location from visual bible
    location_sd = ""
    if visual_bible and location:
        for loc in visual_bible.get("locations", []):
            if any(w in loc.get("name","").lower() for w in location.lower().split() if len(w) > 3):
                location_sd = loc.get("sd_prompt", "")[:80]
                break

    # Try to find relevant object from visual bible
    obj_sd = ""
    if visual_bible:
        for obj in visual_bible.get("objects", []):
            if any(w in str(obj.get("story_role","")).lower()
                   for w in action.lower().split()[:4]):
                obj_sd = obj.get("sd_prompt", "")[:60]
                break

    # MI6 documentary style: environment tells the story, character is simplified
    # Structure: WHAT IS HAPPENING + WHERE + WHO + HOW IT LOOKS
    
    # Get storyboard scene description — the actual story moment
    storyboard_sd = str(scene.get("sd_scene_prompt") or "").strip()
    
    # Build environment-first prompt
    parts = []
    
    # 1. The specific story moment — cap at 150 chars to leave room for sub_focus
    if storyboard_sd:
        parts.append(storyboard_sd[:150])
    else:
        parts.append(action[:100])
    
    # 2. Location detail from visual bible
    if location_sd:
        parts.append(location_sd)
    elif location:
        parts.append(location)
    
    # 3. Character — simplified, not photorealistic
    if char_desc:
        parts.append(f"simplified character: {char_desc[:80]}")
    
    # 4. Object/evidence from visual bible
    if obj_sd:
        parts.append(obj_sd[:60])
    
    # 5. Sub-focus variation
    if sub_focus:
        parts.append(sub_focus)
    
    # 6. Atmosphere + composition
    parts.append(f"{emotion} atmosphere")
    parts.append(camera)
    parts.append("rich detailed background, no text, no watermark")
    
    story_content = ", ".join(p for p in parts if p.strip())
    prompt = f"{DOCUMENTARY_STYLE}{story_content}"

    return {
        "n": scene_number,
        "sd_prompt": prompt[:480],
        "negative_prompt": DOCUMENTARY_NEG,
        "seed": char_seed,
        "act": act,
        "title": scene.get("title", f"Scene {scene_number}"),
        "character": char_name,
        "location": location,
        "action": action,
        "importance": importance,
        "camera": camera,
    }


def expand_storyboard_to_match_timing(
    storyboard: List[Dict],
    scene_list: List[Dict],
    characters: Dict,
    locations: Dict,
    visual_bible: Dict = None,
) -> List[Dict]:
    """
    Expand storyboard to match Whisper timing segments.
    Each timing segment gets a unique scene — no consecutive repeats.
    Camera angles rotate. Sub-focus varies within same storyboard event.
    """
    num_timing = len(scene_list)
    num_storyboard = len(storyboard)

    if num_storyboard == 0:
        logger.warning("[scene_planner] No storyboard — using fallback")
        return []

    segments_per_event = num_timing / num_storyboard
    logger.info(f"[scene_planner] Expanding {num_storyboard} events → {num_timing} unique scenes "
                f"({segments_per_event:.1f} segments per event)")

    expanded = []
    prev_camera = ""
    prev_location = ""

    for i, timing_segment in enumerate(scene_list):
        storyboard_idx = min(int(i / segments_per_event), num_storyboard - 1)
        base_scene = storyboard[storyboard_idx].copy()

        # Select camera — never same as previous
        available_cameras = [c for c in CAMERA_SEQUENCE if c != prev_camera]
        camera = available_cameras[i % len(available_cameras)]

        # Select sub-focus for variety within same event
        # When same storyboard event repeats, vary the focus
        same_event_count = i - int(storyboard_idx * segments_per_event)
        sub_focus = SUB_FOCUSES[int(same_event_count) % len(SUB_FOCUSES)]

        # Add timing info
        base_scene["timing_start"] = timing_segment.get("start", 0)
        base_scene["timing_end"] = timing_segment.get("end", 5)
        base_scene["timing_duration"] = timing_segment.get("duration", 5)

        prompt_data = build_scene_prompt_v6(
            base_scene, characters, locations,
            i + 1, num_timing,
            visual_bible=visual_bible,
            camera_override=camera,
            sub_focus=sub_focus if same_event_count > 0 else "",
        )

        # Vary seed slightly within same character to avoid exact duplicates
        if prompt_data.get("seed"):
            prompt_data["seed"] = prompt_data["seed"] + (i % 11)

        expanded.append(prompt_data)
        prev_camera = camera
        prev_location = base_scene.get("location", "")

    logger.info(f"[scene_planner] Expanded to {len(expanded)} unique scene prompts")
    return expanded


def generate_scenes_deliberate(
    scene_prompts: List[Dict],
    scenes_dir: str,
    gpu_id: str = "0",
) -> int:
    """Generate 2D documentary illustrations using Deliberate v6."""
    os.makedirs(scenes_dir, exist_ok=True)

    scenes_file = os.path.join(scenes_dir, "_scenes_input.json")
    with open(scenes_file, "w") as f:
        json.dump([{
            "n": s["n"],
            "prompt": s["sd_prompt"][:420],
            "neg": s.get("negative_prompt", DOCUMENTARY_NEG)[:200],
            "seed": s.get("seed"),
        } for s in scene_prompts], f)

    script = f"""
import torch, json, os
from diffusers import StableDiffusionPipeline

os.environ["CUDA_VISIBLE_DEVICES"] = "{gpu_id}"
os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"
torch.cuda.empty_cache()

pipe = StableDiffusionPipeline.from_single_file(
    "{DELIBERATE_MODEL}", torch_dtype=torch.float16)
pipe = pipe.to("cuda")
pipe.enable_attention_slicing()

with open("{scenes_file}") as f:
    scenes = json.load(f)

done = 0
for s in scenes:
    out = os.path.join("{scenes_dir}", f"scene_{{s['n']:03d}}.png")
    if os.path.exists(out):
        done += 1
        continue
    seed = s.get('seed')
    gen = torch.Generator("cuda").manual_seed(int(seed)) if seed else None
    try:
        img = pipe(
            s['prompt'][:420], negative_prompt=s['neg'][:200],
            width=1280, height=720,
            num_inference_steps=28, guidance_scale=7.5,
            generator=gen,
        ).images[0]
        img.save(out)
        torch.cuda.empty_cache()
        done += 1
        print(f"DONE {{s['n']}}/{{len(scenes)}}", flush=True)
    except Exception as e:
        print(f"FAIL {{s['n']}}: {{e}}", flush=True)

print(f"TOTAL: {{done}}")
"""
    env = os.environ.copy()
    env["CUDA_VISIBLE_DEVICES"] = gpu_id
    result = subprocess.run(
        [COMFY_PYTHON, "-c", script],
        capture_output=True, text=True, timeout=7200, env=env,
    )
    done = len(glob.glob(os.path.join(scenes_dir, "scene_*.png")))
    logger.info(f"[scene_planner] Generated {done} scenes on GPU {gpu_id}")
    return done

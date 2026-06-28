"""
Asset Generator
Generates character and background asset packs for each new documentary topic.
Runs once per topic — assets are reused across all scenes.
"""
import json
import logging
import os
import subprocess
from pathlib import Path
from typing import Dict, List

logger = logging.getLogger(__name__)

COMFY_PYTHON = os.path.expanduser("~/ComfyUI/.venv_comfy/bin/python3")
JUGGERNAUT = os.path.expanduser("~/ComfyUI/models/checkpoints/Juggernaut-XL-v9.safetensors")

CHAR_STYLE = (
    "simple 2D vector cartoon character, flat colors, thick black outlines, "
    "full body visible, white background, anime explainer style, "
)
CHAR_NEG = "photo, realistic, background, gradient, detailed background, ugly, deformed, extra limbs"

BG_STYLE = (
    "simple 2D vector cartoon background, flat colors, thick black outlines, "
    "anime explainer style, no people, no characters, clean architectural illustration, "
)
BG_NEG = "photo, realistic, 3d render, characters, people, humans, blurry, watermark, text"

UNIVERSAL_SUPPORTING = [
    ("investor_male", "wealthy male investor 50s, expensive pinstripe suit, grey hair, confident expression, standing neutral"),
    ("investor_female", "wealthy female investor 50s, elegant business suit, pearl necklace, serious expression, standing"),
    ("sec_agent", "federal agent 40s, dark blue suit, badge, serious determined expression, holding documents"),
    ("judge", "federal judge 60s, black judicial robes, grey hair, stern expression, holding gavel"),
    ("reporter", "news reporter 30s, business attire, holding microphone, curious expression, standing"),
    ("lawyer", "defense lawyer 50s, dark suit, briefcase, confident expression, standing"),
    ("victim", "ordinary person 60s, casual clothes, worried distressed expression, holding papers"),
    ("young_employee", "young employee 20s, business casual, nervous expression, holding laptop"),
]

UNIVERSAL_BACKGROUNDS = [
    ("wall_street_office", "luxury Wall Street executive office, mahogany desk, Manhattan skyline window, framed certificates, leather chair, warm lighting"),
    ("trading_floor", "1990s stock market trading floor, rows of desks with monitors, stock ticker boards on walls, overhead fluorescent lights"),
    ("courtroom", "federal courtroom interior, wooden judge bench, American flag, jury box, gallery benches, dark wood paneling"),
    ("conference_room", "corporate boardroom, long mahogany conference table, leather chairs, presentation screen, Manhattan view"),
    ("prison_cell", "federal prison cell, metal bunk bed, small barred window, grey concrete walls, harsh overhead light"),
    ("news_studio", "television news studio, anchor desk, breaking news screen, cameras, blue studio lighting"),
    ("street_exterior", "Wall Street New York exterior, stone building facade, courthouse steps, American flags, city street"),
    ("home_luxury", "wealthy Manhattan apartment living room, expensive furniture, city view windows, art on walls"),
]


def generate_character_pack(
    topic_characters: Dict,
    output_dir: str,
    gpu_id: str = "0",
) -> List[str]:
    """Generate character sprites for all people in this documentary."""
    os.makedirs(output_dir, exist_ok=True)
    
    poses = [
        ("standing_neutral", "standing neutral pose arms at sides facing forward"),
        ("pointing", "pointing finger forward confident expression"),
        ("sitting", "sitting at desk or table upper body visible"),
        ("hands_up", "hands raised defensive or pleading expression"),
        ("shocked", "shocked expression hands on face wide eyes"),
        ("walking", "walking pose mid stride"),
    ]
    
    scripts = []
    
    for char_key, char_data in topic_characters.items():
        char_name = char_data.get("name", char_key)
        char_sd = char_data.get("sd_character_prompt", "")
        char_seed = char_data.get("sd_seed", 1000)
        
        if not char_sd:
            continue
        
        for pose_name, pose_desc in poses:
            out = os.path.join(output_dir, f"{char_key}_{pose_name}.png")
            if os.path.exists(out):
                continue
            scripts.append({
                "out": out,
                "prompt": CHAR_STYLE + f"{char_sd}, {pose_desc}",
                "seed": char_seed,
                "w": 768, "h": 1024,
            })
    
    # Also add universal supporting cast
    supporting_dir = os.path.join(output_dir, "supporting")
    os.makedirs(supporting_dir, exist_ok=True)
    
    for char_name, char_desc in UNIVERSAL_SUPPORTING:
        out = os.path.join(supporting_dir, f"{char_name}.png")
        if os.path.exists(out):
            continue
        scripts.append({
            "out": out,
            "prompt": CHAR_STYLE + char_desc,
            "seed": 7777,
            "w": 768, "h": 1024,
        })
    
    if not scripts:
        logger.info("[assets] All character sprites exist")
        return []
    
    return _run_generation(scripts, gpu_id, "characters")


def generate_background_pack(
    topic_locations: Dict,
    output_dir: str,
    gpu_id: str = "0",
) -> List[str]:
    """Generate background images for all locations in this documentary."""
    os.makedirs(output_dir, exist_ok=True)
    scripts = []
    
    # Topic-specific locations
    for loc_key, loc_data in topic_locations.items():
        out = os.path.join(output_dir, f"{loc_key}.png")
        if os.path.exists(out):
            continue
        loc_sd = loc_data.get("sd_prompt", loc_data.get("name", "office"))
        scripts.append({
            "out": out,
            "prompt": BG_STYLE + loc_sd,
            "seed": 9999,
            "w": 1280, "h": 720,
        })
    
    # Universal backgrounds
    for bg_name, bg_desc in UNIVERSAL_BACKGROUNDS:
        out = os.path.join(output_dir, f"{bg_name}.png")
        if os.path.exists(out):
            continue
        scripts.append({
            "out": out,
            "prompt": BG_STYLE + bg_desc,
            "seed": 9999,
            "w": 1280, "h": 720,
        })
    
    if not scripts:
        logger.info("[assets] All backgrounds exist")
        return []
    
    return _run_generation(scripts, gpu_id, "backgrounds")


def _run_generation(scripts: List[Dict], gpu_id: str, asset_type: str) -> List[str]:
    """Run batch SD generation for asset pack."""
    import tempfile
    
    scripts_file = os.path.join(tempfile.gettempdir(), f"assets_{asset_type}.json")
    with open(scripts_file, "w") as f:
        json.dump(scripts, f)
    
    script = f"""
import torch, json, os
from diffusers import StableDiffusionXLPipeline

os.environ["CUDA_VISIBLE_DEVICES"] = "{gpu_id}"
os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"
torch.cuda.empty_cache()

pipe = StableDiffusionXLPipeline.from_single_file(
    "{JUGGERNAUT}", torch_dtype=torch.float16, use_safetensors=True)
pipe = pipe.to("cuda")
pipe.enable_attention_slicing()

with open("{scripts_file}") as f:
    items = json.load(f)

neg = "{CHAR_NEG}"
done = []
for item in items:
    if os.path.exists(item["out"]):
        done.append(item["out"])
        continue
    os.makedirs(os.path.dirname(item["out"]), exist_ok=True)
    gen = torch.Generator("cuda").manual_seed(item["seed"])
    try:
        img = pipe(item["prompt"][:420], negative_prompt=neg[:200],
            width=item["w"], height=item["h"],
            num_inference_steps=28, guidance_scale=7.5,
            generator=gen).images[0]
        img.save(item["out"])
        torch.cuda.empty_cache()
        done.append(item["out"])
        print(f"DONE {{len(done)}}/{{len(items)}}: {{os.path.basename(item['out'])}}", flush=True)
    except Exception as e:
        print(f"FAIL: {{e}}", flush=True)

print(f"TOTAL: {{len(done)}}")
"""
    
    env = os.environ.copy()
    env["CUDA_VISIBLE_DEVICES"] = gpu_id
    result = subprocess.run(
        [COMFY_PYTHON, "-c", script],
        capture_output=True, text=True, timeout=3600, env=env,
    )
    
    generated = [s["out"] for s in scripts if os.path.exists(s["out"])]
    logger.info(f"[assets] Generated {len(generated)} {asset_type}")
    return generated


def generate_asset_pack(
    topic: str,
    characters: Dict,
    locations: Dict,
    assets_dir: str,
    gpu_id: str = "0",
) -> Dict:
    """Full asset pack generation for a new documentary topic."""
    chars_dir = os.path.join(assets_dir, "characters")
    bgs_dir = os.path.join(assets_dir, "backgrounds")
    
    logger.info(f"[assets] Generating asset pack for: {topic[:40]}")
    logger.info(f"[assets] Characters: {list(characters.keys())}")
    logger.info(f"[assets] Locations: {list(locations.keys())}")
    
    char_files = generate_character_pack(characters, chars_dir, gpu_id)
    logger.info(f"[assets] Characters done: {len(char_files)} sprites")
    
    bg_files = generate_background_pack(locations, bgs_dir, gpu_id)
    logger.info(f"[assets] Backgrounds done: {len(bg_files)} backgrounds")
    
    # Save manifest
    manifest = {
        "topic": topic,
        "characters_dir": chars_dir,
        "backgrounds_dir": bgs_dir,
        "character_count": len(list(Path(chars_dir).glob("*.png"))),
        "background_count": len(list(Path(bgs_dir).glob("*.png"))),
    }
    with open(os.path.join(assets_dir, "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=2)
    
    return manifest

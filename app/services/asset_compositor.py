"""
Asset Compositor
Overlays cartoon character PNGs on top of background PNGs.
Produces final scene images without generating new AI art per scene.
This is how professional explainer channels work.
"""
import json
import logging
import os
import random
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from PIL import Image, ImageFilter

logger = logging.getLogger(__name__)

ASSET_LIBRARY = Path(os.path.expanduser("~/mcdee-content-factory/assets"))


def load_asset_library() -> Dict:
    """Load all available assets from the library."""
    library = {"characters": {}, "backgrounds": {}}
    
    chars_dir = ASSET_LIBRARY / "characters"
    if chars_dir.exists():
        for f in chars_dir.glob("**/*.png"):
            key = f.stem
            library["characters"][key] = str(f)
    
    bgs_dir = ASSET_LIBRARY / "backgrounds"
    if bgs_dir.exists():
        for f in bgs_dir.glob("*.png"):
            key = f.stem
            library["backgrounds"][key] = str(f)
    
    logger.info(f"[compositor] Loaded {len(library['characters'])} chars, "
                f"{len(library['backgrounds'])} backgrounds")
    return library


def remove_white_background(img: Image.Image, threshold: int = 240) -> Image.Image:
    """Convert white background to transparent for character overlaying."""
    img = img.convert("RGBA")
    data = img.getdata()
    new_data = []
    for r, g, b, a in data:
        if r > threshold and g > threshold and b > threshold:
            new_data.append((r, g, b, 0))  # transparent
        else:
            new_data.append((r, g, b, a))
    img.putdata(new_data)
    return img


def composite_scene(
    background_key: str,
    character_key: str,
    pose_key: str,
    position: str = "center",
    scale: float = 0.65,
    output_path: str = None,
    library: Dict = None,
) -> Optional[Image.Image]:
    """
    Composite a character onto a background.
    Position: center, left, right, far_left, far_right
    Scale: character height as fraction of background height
    """
    if library is None:
        library = load_asset_library()
    
    # Find background
    bg_path = library["backgrounds"].get(background_key)
    if not bg_path or not os.path.exists(bg_path):
        # Try fuzzy match
        for k, v in library["backgrounds"].items():
            if background_key in k or k in background_key:
                bg_path = v
                break
    
    # Find character
    char_key = f"{character_key}_{pose_key}"
    char_path = library["characters"].get(char_key)
    if not char_path:
        char_path = library["characters"].get(pose_key)
    if not char_path:
        # Try any pose for this character
        for k, v in library["characters"].items():
            if character_key in k:
                char_path = v
                break
    
    if not bg_path:
        logger.warning(f"[compositor] Background not found: {background_key}")
        return None
    
    # Load background
    bg = Image.open(bg_path).convert("RGBA")
    bg = bg.resize((1920, 1080), Image.LANCZOS)
    
    if not char_path:
        # No character — return background only
        result = bg.convert("RGB")
        if output_path:
            result.save(output_path)
        return result
    
    # Load and process character
    char = Image.open(char_path).convert("RGBA")
    char = remove_white_background(char)
    
    # Scale character
    bg_w, bg_h = bg.size
    target_h = int(bg_h * scale)
    char_ratio = char.width / char.height
    target_w = int(target_h * char_ratio)
    char = char.resize((target_w, target_h), Image.LANCZOS)
    
    # Position character
    positions = {
        "center": (bg_w // 2 - target_w // 2, bg_h - target_h - 20),
        "left": (bg_w // 4 - target_w // 2, bg_h - target_h - 20),
        "right": (3 * bg_w // 4 - target_w // 2, bg_h - target_h - 20),
        "far_left": (50, bg_h - target_h - 20),
        "far_right": (bg_w - target_w - 50, bg_h - target_h - 20),
        "center_small": (bg_w // 2 - target_w // 2, bg_h - int(target_h * 0.7)),
    }
    x, y = positions.get(position, positions["center"])
    
    # Subtle shadow for depth
    shadow = char.copy()
    shadow = shadow.filter(ImageFilter.GaussianBlur(8))
    shadow_layer = Image.new("RGBA", bg.size, (0, 0, 0, 0))
    shadow_layer.paste(shadow, (x + 8, y + 8))
    
    # Compose
    result = bg.copy()
    result = Image.alpha_composite(result, shadow_layer)
    char_layer = Image.new("RGBA", bg.size, (0, 0, 0, 0))
    char_layer.paste(char, (x, y))
    result = Image.alpha_composite(result, char_layer)
    result = result.convert("RGB")
    
    if output_path:
        result.save(output_path)
        logger.debug(f"[compositor] Saved: {output_path}")
    
    return result


def build_scene_from_plan(
    scene_plan: Dict,
    output_path: str,
    library: Dict = None,
) -> bool:
    """
    Build a complete scene from a scene plan dict.
    scene_plan: {character, pose, background, position, scale, supporting_cast}
    """
    if library is None:
        library = load_asset_library()
    
    character = scene_plan.get("character", "")
    pose = scene_plan.get("pose", "standing_neutral")
    background = scene_plan.get("background", "wall_street_office")
    position = scene_plan.get("position", "center")
    scale = scene_plan.get("scale", 0.65)
    supporting = scene_plan.get("supporting_cast", [])
    
    # Build base scene
    result = composite_scene(
        background, character, pose, position, scale,
        library=library,
    )
    
    if result is None:
        return False
    
    # Add supporting cast if specified
    for sc in supporting[:3]:
        sc_char = sc.get("character", "")
        sc_pose = sc.get("pose", "standing_neutral")
        sc_pos = sc.get("position", "right")
        sc_scale = sc.get("scale", 0.5)
        
        sc_char_path = library["characters"].get(f"{sc_char}_{sc_pose}")
        if not sc_char_path:
            for k, v in library["characters"].items():
                if sc_char in k:
                    sc_char_path = v
                    break
        
        if sc_char_path:
            sc_img = Image.open(sc_char_path).convert("RGBA")
            sc_img = remove_white_background(sc_img)
            bg_w, bg_h = result.size
            tgt_h = int(bg_h * sc_scale)
            tgt_w = int(tgt_h * (sc_img.width / sc_img.height))
            sc_img = sc_img.resize((tgt_w, tgt_h), Image.LANCZOS)
            
            pos_map = {
                "right": (bg_w - tgt_w - 80, bg_h - tgt_h - 20),
                "left": (80, bg_h - tgt_h - 20),
                "far_right": (bg_w - tgt_w - 20, bg_h - tgt_h - 20),
            }
            px, py = pos_map.get(sc_pos, (bg_w - tgt_w - 80, bg_h - tgt_h - 20))
            
            result_rgba = result.convert("RGBA")
            sc_layer = Image.new("RGBA", result.size, (0,0,0,0))
            sc_layer.paste(sc_img, (px, py))
            result = Image.alpha_composite(result_rgba, sc_layer).convert("RGB")
    
    result.save(output_path)
    return True

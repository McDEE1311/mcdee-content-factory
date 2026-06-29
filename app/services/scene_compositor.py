"""
Master POV Scene Compositor
Composites characters into backgrounds at proper scale (25-35% frame height)
with soft shadow, camera motion, and parallax.
"""
import os, json, subprocess
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from typing import Dict, List, Optional, Tuple

ASSETS = os.path.expanduser("~/mcdee-content-factory/assets")
CHAR_DIR = f"{ASSETS}/characters/master_pov"
BG_DIR = f"{ASSETS}/backgrounds"
FRAME_W, FRAME_H = 1920, 1080


def load_bg(scene_type: str) -> Image.Image:
    """Load background for scene type."""
    # Try exact match first
    path = f"{BG_DIR}/{scene_type}.png"
    if not os.path.exists(path):
        # Fuzzy match
        for f in os.listdir(BG_DIR):
            if scene_type.split("_")[0] in f:
                path = f"{BG_DIR}/{f}"
                break
    if os.path.exists(path):
        return Image.open(path).convert("RGBA").resize((FRAME_W, FRAME_H), Image.LANCZOS)
    # Fallback solid
    img = Image.new("RGBA", (FRAME_W, FRAME_H), (45, 55, 70, 255))
    return img


def load_character(char_name: str) -> Optional[Image.Image]:
    """Load character PNG with transparent background."""
    path = f"{CHAR_DIR}/{char_name}.png"
    if not os.path.exists(path):
        # Try base name
        base = char_name.split("_")[0] + "_neutral"
        path = f"{CHAR_DIR}/{base}.png"
    if os.path.exists(path):
        return Image.open(path).convert("RGBA")
    return None


def remove_white(img: Image.Image, threshold: int = 228) -> Image.Image:
    """Remove white/near-white background from character."""
    data = np.array(img)
    r, g, b, a = data[:,:,0], data[:,:,1], data[:,:,2], data[:,:,3]
    white = (r > threshold) & (g > threshold) & (b > threshold)
    grey = (r > 200) & (g > 200) & (b > 200) & \
           (np.abs(r.astype(int)-g.astype(int)) < 18) & \
           (np.abs(g.astype(int)-b.astype(int)) < 18)
    data[:,:,3] = np.where(white | grey, 0, 255)
    return Image.fromarray(data)


def add_shadow(canvas: Image.Image, x: int, y: int, 
               char_w: int, char_h: int) -> Image.Image:
    """Add soft ellipse ground shadow beneath character feet."""
    shadow_layer = Image.new("RGBA", canvas.size, (0,0,0,0))
    sd = ImageDraw.Draw(shadow_layer)
    foot_y = y + char_h
    sw = int(char_w * 0.65)
    sh = int(char_h * 0.06)
    cx = x + char_w // 2
    sd.ellipse([cx-sw//2, foot_y-sh, cx+sw//2, foot_y+sh],
               fill=(0, 0, 0, 55))
    shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(radius=12))
    return Image.alpha_composite(canvas, shadow_layer)


def composite_scene(
    scene: Dict,
    output_path: str,
    char_scale: float = 0.30,  # character height as fraction of frame
) -> bool:
    """
    Build a single 1920x1080 scene frame.
    scene = {scene_type, character, position, supporting_cast}
    """
    # Load background
    bg = load_bg(scene.get("scene_type", "executive_office"))

    # Load and place main character
    char_name = scene.get("character", "madoff_neutral")
    char_img = load_character(char_name)

    if char_img is not None:
        char_img = remove_white(char_img)
        # Scale to 25-35% of frame height
        target_h = int(FRAME_H * char_scale)
        ratio = target_h / char_img.height
        target_w = int(char_img.width * ratio)
        char_img = char_img.resize((target_w, target_h), Image.LANCZOS)

        # Position
        positions = {
            "center": (FRAME_W//2 - target_w//2, FRAME_H - target_h - 60),
            "left":   (FRAME_W//4 - target_w//2, FRAME_H - target_h - 60),
            "right":  (3*FRAME_W//4 - target_w//2, FRAME_H - target_h - 60),
            "center_left": (FRAME_W//3 - target_w//2, FRAME_H - target_h - 60),
        }
        pos = scene.get("position", "center")
        x, y = positions.get(pos, positions["center"])

        # Add shadow first
        bg = add_shadow(bg, x, y, target_w, target_h)

        # Paste character
        char_layer = Image.new("RGBA", bg.size, (0,0,0,0))
        char_layer.paste(char_img, (x, y))
        bg = Image.alpha_composite(bg, char_layer)

    # Supporting cast
    for sc in scene.get("supporting_cast", []):
        sc_name = sc.get("character", "investor_male")
        sc_img = load_character(sc_name)
        if sc_img is None:
            continue
        sc_img = remove_white(sc_img)
        sc_scale = sc.get("scale", 0.22)
        sc_h = int(FRAME_H * sc_scale)
        sc_w = int(sc_h * sc_img.width / sc_img.height)
        sc_img = sc_img.resize((sc_w, sc_h), Image.LANCZOS)
        sc_pos = sc.get("position", "right")
        sx, sy = positions.get(sc_pos, positions["right"])
        if sc.get("flip"):
            sc_img = sc_img.transpose(Image.FLIP_LEFT_RIGHT)
        bg = add_shadow(bg, sx, sy, sc_w, sc_h)
        sc_layer = Image.new("RGBA", bg.size, (0,0,0,0))
        sc_layer.paste(sc_img, (sx, sy))
        bg = Image.alpha_composite(bg, sc_layer)

    bg.convert("RGB").save(output_path)
    return True


def render_scene_video(
    scene: Dict,
    output_path: str,
    duration: float = 6.0,
    camera: str = "zoom_in",
) -> bool:
    """
    Render a scene as a video clip with camera motion.
    camera: zoom_in, zoom_out, pan_left, pan_right
    """
    import tempfile
    frame_path = output_path.replace(".mp4", "_frame.png")
    composite_scene(scene, frame_path)

    # Camera motion via ffmpeg zoompan
    zoom_filters = {
        "zoom_in":   f"zoompan=z='min(zoom+0.0008,1.08)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={int(duration*25)}:s=1920x1080:fps=25",
        "zoom_out":  f"zoompan=z='if(lte(zoom,1.0),1.08,max(1.0,zoom-0.0008))':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={int(duration*25)}:s=1920x1080:fps=25",
        "pan_left":  f"zoompan=z=1.04:x='min(iw*0.04*on/{int(duration*25)},iw*0.04)':y='ih/2-(ih/zoom/2)':d={int(duration*25)}:s=1920x1080:fps=25",
        "pan_right": f"zoompan=z=1.04:x='max(0,iw*0.04-iw*0.04*on/{int(duration*25)})':y='ih/2-(ih/zoom/2)':d={int(duration*25)}:s=1920x1080:fps=25",
    }

    vf = zoom_filters.get(camera, zoom_filters["zoom_in"])

    r = subprocess.run([
        "ffmpeg", "-y",
        "-loop", "1", "-i", frame_path,
        "-vf", vf,
        "-t", str(duration),
        "-c:v", "libx264", "-preset", "fast", "-crf", "22",
        "-pix_fmt", "yuv420p",
        output_path
    ], capture_output=True, timeout=120)

    if os.path.exists(frame_path):
        os.remove(frame_path)

    return r.returncode == 0


def build_video_from_scenes(
    scene_list: List[Dict],
    narration_wav: str,
    output_path: str,
    clips_dir: str,
) -> bool:
    """
    Build full video from scene list with narration.
    Each scene has: scene_type, character, position, duration, camera
    """
    os.makedirs(clips_dir, exist_ok=True)
    cameras = ["zoom_in", "zoom_out", "pan_left", "pan_right", "zoom_in"]
    clip_paths = []

    for i, scene in enumerate(scene_list):
        clip = f"{clips_dir}/scene_{i:03d}.mp4"
        if os.path.exists(clip):
            clip_paths.append(clip)
            continue
        dur = scene.get("duration", 6.0)
        cam = cameras[i % len(cameras)]
        ok = render_scene_video(scene, clip, duration=dur, camera=cam)
        if ok:
            clip_paths.append(clip)
            print(f"  Scene {i}: {scene.get('scene_type','?')} [{cam}] {dur:.1f}s")

    if not clip_paths:
        return False

    # Concat clips
    concat = f"{clips_dir}/concat.txt"
    with open(concat, "w") as f:
        for cp in clip_paths:
            f.write(f"file '{os.path.abspath(cp)}'\n")

    raw = output_path.replace(".mp4", "_raw.mp4")
    subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat,
        "-c:v", "libx264", "-preset", "fast", "-crf", "22",
        "-pix_fmt", "yuv420p", raw
    ], capture_output=True, timeout=600)

    # Add narration
    subprocess.run([
        "ffmpeg", "-y", "-i", raw, "-i", narration_wav,
        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
        "-shortest", output_path
    ], capture_output=True, timeout=120)

    if os.path.exists(raw):
        os.remove(raw)

    return os.path.exists(output_path)

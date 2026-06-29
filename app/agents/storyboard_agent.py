"""
Storyboard Agent v2
Converts a documentary script into a structured storyboard JSON.
Each scene includes narration text, visual description, character references,
camera motion, image prompt, and estimated timing.
"""
import json
import logging
import pathlib
import re
import yaml
from typing import List, Dict

logger = logging.getLogger(__name__)

_REPO_ROOT = pathlib.Path(__file__).parent.parent.parent
_STYLE_FILE = _REPO_ROOT / "config" / "visual_style.yaml"
_CHAR_FILE = _REPO_ROOT / "config" / "characters.yaml"

WORDS_PER_SECOND = 2.3


def load_style(category: str = "dark_history") -> dict:
    with open(str(_STYLE_FILE)) as f:
        data = yaml.safe_load(f)
    styles = data.get("styles", {})
    return styles.get(category, styles.get(data.get("default_style", "dark_history"), {}))


def load_characters() -> dict:
    with open(str(_CHAR_FILE)) as f:
        data = yaml.safe_load(f)
    return data.get("characters", {})


def estimate_duration(text: str) -> float:
    return max(3.0, len(text.split()) / WORDS_PER_SECOND)


def split_script_into_segments(script_text: str, target_scene_duration: float = 5.0) -> List[str]:
    clean = re.sub(r'\[.*?\]', '', script_text)
    clean = re.sub(r'#{1,4}.*?\n', '', clean)
    clean = re.sub(r'\n{2,}', ' ', clean).strip()
    sentences = re.split(r'(?<=[.!?])\s+', clean)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 10]

    segments = []
    current = []
    current_words = 0
    target_words = int(target_scene_duration * WORDS_PER_SECOND)

    for sentence in sentences:
        words = len(sentence.split())
        if current_words + words > target_words and current:
            segments.append(' '.join(current))
            current = [sentence]
            current_words = words
        else:
            current.append(sentence)
            current_words += words
    if current:
        segments.append(' '.join(current))
    return segments


def build_storyboard_fast(
    script_text: str,
    title: str,
    category: str = "dark_history",
    target_scene_duration: float = 5.0,
) -> List[dict]:
    """Fast storyboard without LLM — uses script text directly as scene descriptions."""
    style = load_style(category)
    segments = split_script_into_segments(script_text, target_scene_duration)
    total = len(segments)
    logger.info(f"[storyboard] {total} scenes for '{title[:50]}'")

    motions = ["slow zoom in", "slow zoom out", "slow pan left", "slow pan right", "slow push in"]
    base_prompt = style.get("base_prompt", "documentary illustration, cinematic,").replace("\n", " ").strip()
    neg_prompt = style.get("negative_prompt", "photo, realistic, blurry, watermark, text").replace("\n", " ").strip()

    storyboard = []
    elapsed = 0.0

    for i, narration in enumerate(segments):
        duration = estimate_duration(narration)
        # Build image prompt from narration keywords
        keywords = ' '.join(narration.split()[:15])
        image_prompt = f"{base_prompt}, {keywords}, cinematic composition, no text, no watermark"

        scene = {
            "scene_number": i + 1,
            "narration_text": narration,
            "estimated_start": round(elapsed, 2),
            "estimated_end": round(elapsed + duration, 2),
            "duration_seconds": round(duration, 2),
            "word_count": len(narration.split()),
            "camera_motion": motions[i % len(motions)],
            "image_prompt": image_prompt[:400],
            "negative_prompt": neg_prompt[:200],
            "location": "",
            "characters": [],
            "emotion": "",
            "visual_action": narration[:100],
        }
        storyboard.append(scene)
        elapsed += duration

    logger.info(f"[storyboard] Total duration: {elapsed:.1f}s")
    return storyboard


def save_storyboard(storyboard: List[dict], output_path: str) -> str:
    import os
    os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)
    with open(output_path, "w") as f:
        json.dump({"scenes": storyboard, "total_scenes": len(storyboard)}, f, indent=2)
    logger.info(f"[storyboard] Saved {len(storyboard)} scenes to {output_path}")
    return output_path


def load_storyboard(path: str) -> List[dict]:
    with open(path) as f:
        data = json.load(f)
    return data.get("scenes", [])

"""
Scene Planner V2 — Master POV Style
Converts storyboard events to scene JSON with character, background, camera.
"""
import json, logging
from typing import Dict, List

logger = logging.getLogger(__name__)

# Map story beats to scene types and characters
SCENE_MAP = {
    "beginning":      ("executive_office",   "madoff_confident",  "center"),
    "founding":       ("executive_office",   "madoff_confident",  "center"),
    "nasdaq":         ("trading_floor",      "madoff_pointing",   "center"),
    "ponzi":          ("executive_office",   "madoff_thinking",   "center"),
    "chairman":       ("conference_room",    "madoff_confident",  "center"),
    "sec":            ("government_hallway", "sec_agent",         "left"),
    "trouble":        ("executive_office",   "madoff_concerned",  "center"),
    "crisis":         ("trading_floor",      "madoff_angry",      "center"),
    "confession":     ("executive_office",   "madoff_hands_up",   "center"),
    "arrest":         ("street_exterior",    "madoff_hands_up",   "center"),
    "trial":          ("courtroom",          "madoff_neutral",    "center_left"),
    "sentenced":      ("courtroom",          "judge",             "center"),
    "prison":         ("prison_cell",        "madoff_concerned",  "center"),
    "aftermath":      ("retirement_home",    "victim",            "center"),
    "victims":        ("bank_lobby",         "victim",            "center"),
    "news":           ("news_studio",        "reporter",          "center"),
    "investor":       ("conference_room",    "investor_male",     "right"),
    "rise":           ("executive_office",   "madoff_confident",  "center"),
    "collapse":       ("trading_floor",      "madoff_angry",      "center"),
    "investigation":  ("government_hallway", "sec_agent",         "center"),
}

CAMERA_CYCLE = ["zoom_in", "pan_right", "zoom_out", "pan_left", "zoom_in"]

SUPPORTING_CAST = {
    "courtroom": [
        {"character": "judge",    "position": "center",  "scale": 0.20, "flip": False},
        {"character": "lawyer",   "position": "left",    "scale": 0.22, "flip": False},
    ],
    "conference_room": [
        {"character": "investor_male",   "position": "left",  "scale": 0.22, "flip": True},
        {"character": "investor_female", "position": "right", "scale": 0.20, "flip": False},
    ],
    "news_studio": [
        {"character": "investor_male", "position": "right", "scale": 0.18, "flip": True},
    ],
    "trading_floor": [
        {"character": "employee",      "position": "left",  "scale": 0.20, "flip": False},
        {"character": "investor_male", "position": "right", "scale": 0.18, "flip": True},
    ],
}


def storyboard_to_scenes(
    storyboard: List[Dict],
    timing_segments: List[Dict],
) -> List[Dict]:
    """Convert storyboard events + timing to scene list for compositor."""
    scenes = []
    n_segs = len(timing_segments)

    for i, seg in enumerate(timing_segments):
        # Find matching storyboard event
        event_idx = min(int(i * len(storyboard) / n_segs), len(storyboard)-1)
        event = storyboard[event_idx]

        title = (event.get("title") or "").lower()
        act = (event.get("act") or "").lower()
        combined = f"{title} {act}"

        # Find scene type
        scene_type = "executive_office"
        char = "madoff_neutral"
        pos = "center"

        for key, (st, ch, p) in SCENE_MAP.items():
            if key in combined:
                scene_type = st
                char = ch
                pos = p
                break

        # Vary character expression based on act
        if "rise" in act and "madoff" in char:
            char = char.replace("neutral", "confident")
        elif "collapse" in act and "madoff" in char:
            char = "madoff_angry"
        elif "evidence" in act:
            char = "madoff_concerned"

        # Camera
        camera = CAMERA_CYCLE[i % len(CAMERA_CYCLE)]

        scene = {
            "scene_id": i,
            "scene_type": scene_type,
            "character": char,
            "position": pos,
            "duration": seg["duration"],
            "camera": camera,
            "supporting_cast": SUPPORTING_CAST.get(scene_type, []),
        }
        scenes.append(scene)

    logger.info(f"[scene_planner] {len(scenes)} scenes planned")
    return scenes

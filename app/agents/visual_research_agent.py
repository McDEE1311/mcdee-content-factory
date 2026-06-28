"""
Visual Research Agent
Extracts locations, objects, evidence items, and visual moments from research.
These become the source of truth for scene prompts — not generic descriptions.
"""
import json
import logging
import re
import time
from typing import Dict, List
import httpx

logger = logging.getLogger(__name__)
HEADERS = {"User-Agent": "TrendForgeResearch/1.0 (documentary-research; linux)"}


def extract_visual_bible(
    topic: str,
    category: str,
    characters: Dict,
    wiki_text: str,
    timeline: List[Dict],
) -> Dict:
    """
    Extract complete visual bible: locations, objects, evidence, key moments.
    Every scene must reference at least one element from this bible.
    """
    from app.services.ollama_client import ollama_client

    char_names = [v.get("name", k) for k, v in characters.items()]
    timeline_text = "\n".join(
        f"- {e.get('year','')}: {e.get('title','')} — {e.get('description','')[:80]}"
        for e in timeline[:10]
    )

    prompt = f"""Documentary topic: "{topic}"
Category: {category}
Main characters: {', '.join(char_names)}

Wikipedia context:
{wiki_text[:600]}

Timeline:
{timeline_text}

Extract the complete visual world of this documentary.
Every item must be story-specific — NOT generic.

Output ONLY this JSON:
{{
  "locations": [
    {{
      "id": "stanford_campus",
      "name": "Stanford University Campus",
      "period": "2002-2003",
      "visual_description": "Spanish colonial architecture, red tile roofs, palm trees, Hoover Tower visible, sunny California campus",
      "atmosphere": "hopeful ambitious youthful",
      "sd_prompt": "Stanford University campus, Hoover Tower, red tile roofs, Spanish colonial architecture, sunny California, palm trees",
      "story_events": ["Holmes drops out", "early Theranos planning"]
    }}
  ],
  "objects": [
    {{
      "id": "edison_machine",
      "name": "Theranos Edison Blood Testing Machine",
      "description": "small white compact medical device, blood testing cartridge slot, touchscreen display, clinical laboratory setting",
      "sd_prompt": "Theranos Edison blood testing machine, white compact medical device, laboratory equipment, clinical setting",
      "story_role": "the fraud device — central object of deception"
    }}
  ],
  "evidence_items": [
    {{
      "id": "wsj_article",
      "name": "Wall Street Journal Investigation Article",
      "description": "newspaper front page, WSJ masthead, headline about Theranos investigation, reporter at laptop",
      "sd_prompt": "Wall Street Journal newspaper front page, investigative journalism, reporter at desk with documents",
      "story_role": "the moment the fraud was exposed"
    }}
  ],
  "key_visual_moments": [
    {{
      "moment": "Holmes pitching investors",
      "characters": ["Elizabeth Holmes"],
      "location": "investor boardroom",
      "objects": ["presentation slides", "Theranos branding"],
      "emotion": "confident deceptive",
      "sd_prompt": "Elizabeth Holmes presenting to Silicon Valley investors in luxury boardroom, confident presentation, Theranos logo on screen"
    }}
  ]
}}"""

    try:
        result = ollama_client.generate_json(prompt, temperature=0.2)
        if result and (result.get("locations") or result.get("objects")):
            locs = len(result.get("locations", []))
            objs = len(result.get("objects", []))
            moments = len(result.get("key_visual_moments", []))
            logger.info(f"[visual] Bible: {locs} locations, {objs} objects, {moments} moments")
            return result
    except Exception as e:
        logger.warning(f"[visual] Visual bible extraction failed: {e}")

    # Minimal fallback
    return {
        "locations": [],
        "objects": [],
        "evidence_items": [],
        "key_visual_moments": [],
    }


def build_scene_prompt_from_visual_bible(
    scene: Dict,
    character_bible: Dict,
    visual_bible: Dict,
    style_prefix: str,
    camera_angles: List[str],
    scene_index: int,
) -> str:
    """
    Build a complete SD prompt using the visual bible.
    Format: [style], [character], [location], [action], [object/evidence], [emotion], [camera]
    Style prefix must stay under 80 chars so story content dominates.
    """
    char_name = scene.get("character", "")
    location_name = scene.get("location", "")
    action = scene.get("action", "")
    emotion = scene.get("emotion", "dramatic")
    storyboard_sd = scene.get("sd_scene_prompt", "")

    # Lookup character
    char_prompt = ""
    char_seed = None
    if char_name and character_bible:
        for key, char in character_bible.items():
            char_full = char.get("name", "").lower()
            if any(p in char_full for p in char_name.lower().split() if len(p) > 2):
                char_prompt = char.get("sd_character_prompt", "")
                char_seed = char.get("sd_seed")
                break

    # Lookup location from visual bible
    location_sd = ""
    locations = visual_bible.get("locations", [])
    for loc in locations:
        loc_name = loc.get("name", "").lower()
        if any(w in loc_name for w in location_name.lower().split() if len(w) > 3):
            location_sd = loc.get("sd_prompt", "")
            break

    # Lookup relevant object
    obj_sd = ""
    objects = visual_bible.get("objects", [])
    for obj in objects:
        obj_events = str(obj.get("story_role", "")).lower()
        if any(w in obj_events for w in action.lower().split()[:3]):
            obj_sd = obj.get("sd_prompt", "")[:80]
            break

    # Camera diversity
    camera = camera_angles[scene_index % len(camera_angles)]

    # Build prompt — story content first, style second
    parts = []

    # Core story content
    if storyboard_sd:
        parts.append(storyboard_sd)
    elif action:
        parts.append(action)

    if char_prompt and char_prompt not in parts[0] if parts else True:
        parts.append(f"character: {char_prompt}")

    if location_sd:
        parts.append(location_sd)
    elif location_name:
        parts.append(location_name)

    if obj_sd:
        parts.append(obj_sd)

    parts.append(f"{emotion} atmosphere")
    parts.append(camera)
    parts.append("no text, no watermark")

    story_content = ", ".join(parts)

    # Style prefix kept SHORT so story dominates
    final_prompt = f"{style_prefix}{story_content}"
    return final_prompt[:480]

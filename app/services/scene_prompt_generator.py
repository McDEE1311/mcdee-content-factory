"""
Scene Prompt Generator V3
Narration → Visual Event → Cinematic Composition → SD Prompt

Key improvements:
- Event-based descriptions (what is HAPPENING, not just where)
- Foreground / midground / background composition
- Emotion detection → lighting/color/angle modifiers
- Character registry for consistent characters
- Importance scoring for quality prioritization
- Two model profiles: thumbnail vs video
"""
import logging
import re
import yaml
import pathlib
from typing import List, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

# Runtime person descriptions populated from research packet per video
_PERSON_DESCRIPTIONS: dict = {}
_PRIMARY_PERSON: str = ""

_REPO_ROOT = pathlib.Path(__file__).parent.parent.parent
_CHAR_FILE = _REPO_ROOT / "config" / "character_registry.yaml"


def load_characters() -> dict:
    with open(str(_CHAR_FILE)) as f:
        return yaml.safe_load(f).get("characters", {})


# ── STYLE PROFILES ────────────────────────────────────────────────────────────

VIDEO_STYLES = {
    "financial_rise_fall": {
        "prefix": (
            "1990s animated documentary cartoon style, "
            "bold thick black outlines, flat cel shading, vivid colors, "
            "expressive cartoon faces, Archer animated series quality, "
            "dramatic composition, cinematic framing, "
        ),
        "negative": (
            "photo, realistic, 3d render, blurry, watermark, text, "
            "superhero costume, cape, spandex, batman, modern CGI, "
            "low quality, ugly, deformed, extra limbs"
        ),
        "lighting_default": "dramatic side lighting, strong shadows",
    },
    "historical_mystery": {
        "prefix": (
            "cinematic animated historical illustration, "
            "painterly detailed brushwork, warm candlelight palette, "
            "gold burgundy navy colors, mysterious atmospheric, "
            "graphic novel quality, 18th century European aesthetic, "
        ),
        "negative": (
            "photo, realistic, 3d render, modern, blurry, watermark, "
            "anime, stock photo, text, superhero, ugly, deformed"
        ),
        "lighting_default": "warm candlelight, dramatic chiaroscuro",
    },
    "dark_history": {
        "prefix": (
            "cinematic animated historical illustration, "
            "dramatic chiaroscuro lighting, moody dark atmosphere, "
            "painterly graphic novel quality, strong composition, "
        ),
        "negative": (
            "photo, realistic, 3d render, blurry, watermark, "
            "anime, text, superhero, ugly, deformed"
        ),
        "lighting_default": "dramatic shadows, moody lighting",
    },
    "survival_stories": {
        "prefix": (
            "dramatic survival documentary illustration, "
            "high contrast tense atmosphere, painterly cinematic style, "
            "illustrated realism, strong emotional faces, "
        ),
        "negative": (
            "photo, 3d render, blurry, watermark, text, anime, "
            "cartoon, superhero, low quality"
        ),
        "lighting_default": "harsh natural light, tense atmosphere",
    },
    "space_mysteries": {
        "prefix": (
            "cinematic space documentary illustration, "
            "deep cosmic blues purples blacks, star fields nebulae, "
            "dramatic scale, scientific visualization style, "
            "painterly atmospheric, "
        ),
        "negative": (
            "photo, realistic photo, blurry, watermark, text, "
            "anime, superhero, ugly"
        ),
        "lighting_default": "deep space darkness, cosmic light sources",
    },
}

# ── EMOTION DETECTION ─────────────────────────────────────────────────────────

EMOTION_PROFILES = {
    "fear": {
        "keywords": ["terrified", "panic", "afraid", "fear", "scared", "horror", "shock", "alarmed"],
        "lighting": "cold blue lighting, deep shadows, dramatic shadows",
        "camera": "low angle looking up, extreme close-up on face",
        "color": "desaturated cold tones, harsh contrast",
        "expression": "wide terrified eyes, mouth open, hands raised",
    },
    "greed": {
        "keywords": ["billion", "million", "profit", "wealth", "rich", "money", "fortune", "lavish"],
        "lighting": "warm golden lighting, opulent atmosphere",
        "camera": "wide shot showing scale of wealth",
        "color": "rich gold and green tones",
        "expression": "smug satisfied smile, confident posture",
    },
    "collapse": {
        "keywords": ["collapse", "crash", "bankrupt", "ruin", "destroy", "fall", "crisis", "failure"],
        "lighting": "harsh red emergency lighting, chaotic shadows",
        "camera": "dramatic dutch angle, wide chaos shot",
        "color": "red and black dominant, desaturated background",
        "expression": "desperate panic, chaos, running figures",
    },
    "triumph": {
        "keywords": ["success", "billion", "launch", "celebrate", "achieve", "rise", "winning", "peak"],
        "lighting": "warm bright upward lighting, heroic atmosphere",
        "camera": "low angle looking up at subject, triumphant framing",
        "color": "warm golds and whites, vibrant",
        "expression": "confident smile, arms raised, power pose",
    },
    "deception": {
        "keywords": ["fraud", "lie", "hide", "secret", "steal", "deceive", "fake", "manipulate", "misuse"],
        "lighting": "dramatic side lighting, half face in shadow",
        "camera": "slight high angle looking down, shadowy atmosphere",
        "color": "dark greens and shadows, noir atmosphere",
        "expression": "secretive smile, shifty eyes, hunched posture",
    },
    "despair": {
        "keywords": ["lost", "gone", "zero", "empty", "nothing", "hopeless", "devastated", "ruined"],
        "lighting": "dim desaturated lighting, isolated figure",
        "camera": "wide shot showing isolation, small figure in large space",
        "color": "grey and cold blues, drained of color",
        "expression": "head in hands, hunched shoulders, defeated",
    },
    "tension": {
        "keywords": ["warning", "risk", "danger", "threat", "pressure", "deadline", "critical"],
        "lighting": "tense dramatic lighting, shadows closing in",
        "camera": "medium close-up, tight framing",
        "color": "amber and warning tones",
        "expression": "tense jaw, narrowed eyes, leaning forward",
    },
}


def detect_emotion(text: str) -> dict:
    """Detect dominant emotion in narration text."""
    text_lower = text.lower()
    scores = {}
    for emotion, profile in EMOTION_PROFILES.items():
        score = sum(1 for kw in profile["keywords"] if kw in text_lower)
        if score > 0:
            scores[emotion] = score
    if not scores:
        return EMOTION_PROFILES["tension"]
    best = max(scores, key=scores.get)
    return EMOTION_PROFILES[best]


# ── EVENT DETECTION ───────────────────────────────────────────────────────────

def detect_visual_event(text: str, category: str) -> Tuple[str, str, str]:
    """
    Detect what visual EVENT is happening in this narration.
    Returns (foreground, midground, background) scene layers.
    """
    text_lower = text.lower()

    # FTX-specific events
    if "zero" in text_lower and ("balance" in text_lower or "fund" in text_lower):
        return (
            "panicked investor staring at phone showing ZERO balance",
            "crowd of shocked customers outside closed exchange office",
            "FTX logo on dark building with warning lights"
        )
    if "arrest" in text_lower or "handcuff" in text_lower:
        return (
            "federal agents placing handcuffs on shocked young man",
            "police vehicles with flashing lights on city street",
            "news cameras and crowd gathered behind barriers"
        )
    if "sentenc" in text_lower or "verdict" in text_lower or "guilty" in text_lower:
        return (
            "young defendant standing alone at courtroom podium head bowed",
            "stern judge in black robes holding gavel",
            "packed courtroom gallery of shocked onlookers"
        )
    if "trial" in text_lower or "testif" in text_lower or "court" in text_lower:
        return (
            "nervous witness at stand under harsh spotlight",
            "lawyers at wooden tables facing judge bench",
            "American flags and wood-paneled courtroom walls"
        )
    if "billion" in text_lower and ("stole" in text_lower or "missing" in text_lower or "lost" in text_lower):
        return (
            "enormous vault torn open with money flying out in all directions",
            "shadowy figure running with overfilled bag of cash",
            "dark corporate building with alarms flashing"
        )
    if "withdraw" in text_lower or "bank run" in text_lower:
        return (
            "desperate person hammering on locked glass doors",
            "long queue of panicked people stretching around building",
            "closed sign on exchange with police tape"
        )
    if "congress" in text_lower or "senate" in text_lower or "hearing" in text_lower:
        return (
            "young tech CEO looking small at massive congressional witness table",
            "row of stern senators leaning into microphones",
            "packed hearing room with cameras and press"
        )
    if "bahamas" in text_lower or "penthouse" in text_lower or "luxury" in text_lower:
        return (
            "young man relaxing in luxury penthouse overlooking tropical ocean",
            "expensive furnishings computers and screens",
            "bahamas coastline with palm trees at golden hour"
        )
    if "crypto" in text_lower and "exchange" in text_lower:
        return (
            "busy cryptocurrency trading floor with glowing screens everywhere",
            "young traders watching dramatic price charts",
            "large FTX logo illuminated on server room wall"
        )
    if "collapse" in text_lower or "crash" in text_lower:
        return (
            "massive stock chart crashing downward through floor",
            "panicked traders running in chaos",
            "FTX corporate tower with windows shattering and lights going dark"
        )

    # Lehman Brothers events
    if "lehman" in text_lower and "bankrupt" in text_lower:
        return (
            "workers carrying boxes out of Lehman Brothers office in stunned silence",
            "dark empty corporate floors lights going out one by one",
            "Wall Street skyscraper with CLOSED sign on revolving doors"
        )
    if "mortgage" in text_lower or "housing" in text_lower:
        return (
            "suburban family standing outside foreclosed home with removal boxes",
            "FOR SALE and FORECLOSED signs on every house on the street",
            "American suburb street at dusk"
        )

    # Historical mystery events
    if "versailles" in text_lower or "palace" in text_lower or "court" in text_lower:
        return (
            "mysterious nobleman captivating French aristocrats with hand gesture",
            "astonished nobles in powdered wigs and elaborate gowns",
            "grand Versailles ballroom with crystal chandeliers and candlelight"
        )
    if "alchemy" in text_lower or "laboratory" in text_lower:
        return (
            "focused figure examining glowing mysterious substance in flask",
            "bubbling alchemical equipment ancient books and scrolls",
            "stone laboratory chamber lit by fireplace and candles"
        )

    # Generic financial events
    if "rise" in text_lower or "success" in text_lower or "billion" in text_lower:
        return (
            "confident entrepreneur in casual clothes presenting to impressed audience",
            "charts showing dramatic upward growth on screens behind them",
            "modern tech headquarters with company logo"
        )

    # Space events
    if "space" in text_lower or "universe" in text_lower or "galaxy" in text_lower:
        return (
            "astronaut floating in vast cosmic space looking at distant galaxy",
            "swirling nebula with planets and star formations",
            "infinite deep space starfield stretching to horizon"
        )

    # Default — use category context
    category_defaults = {
        "financial_rise_fall": (
            "suited executive at window overlooking city looking troubled",
            "stock market boards showing dramatic changes",
            "Wall Street financial district at dramatic lighting"
        ),
        "historical_mystery": (
            "mysterious cloaked figure in doorway holding candle",
            "candlelit stone chamber with ancient books and maps",
            "European castle corridor with torchlit shadows"
        ),
        "dark_history": (
            "lone figure standing in dramatic spotlight",
            "historical documents and artifacts spread on table",
            "dark dramatic historical backdrop"
        ),
        "survival_stories": (
            "lone survivor pushing forward through harsh environment",
            "dramatic wilderness landscape stretching to horizon",
            "sky showing weather threatening above"
        ),
        "space_mysteries": (
            "scientist pointing at cosmic phenomenon on screen",
            "observatory equipment and star maps",
            "deep space starfield visible through dome window"
        ),
    }
    return category_defaults.get(category, (
        "central figure in dramatic pose",
        "relevant midground scene elements",
        "atmospheric background setting"
    ))


# ── CHARACTER MATCHING ────────────────────────────────────────────────────────

def find_character(text: str) -> Optional[dict]:
    """Find if a known character is mentioned in the narration."""
    chars = load_characters()
    text_lower = text.lower()
    for char_key, char in chars.items():
        aliases = char.get("aliases", [])
        if any(alias in text_lower for alias in aliases):
            return char
    return None


# ── IMPORTANCE SCORING ────────────────────────────────────────────────────────

def score_importance(text: str) -> int:
    """Score scene importance 1-10 for quality prioritization."""
    text_lower = text.lower()
    high_impact = [
        "arrest", "guilty", "sentenced", "billion", "collapse", "fraud",
        "stolen", "zero", "bankrupt", "verdict", "crash", "destroyed",
        "immortal", "mystery", "disappeared", "secret", "revealed"
    ]
    medium_impact = [
        "court", "trial", "million", "exchange", "trading", "fall",
        "rise", "danger", "warning", "shock", "panic"
    ]
    score = 5  # baseline
    score += sum(2 for kw in high_impact if kw in text_lower)
    score += sum(1 for kw in medium_impact if kw in text_lower)
    return min(10, score)


# ── MAIN PROMPT BUILDER ───────────────────────────────────────────────────────

def build_scene_prompt_v3(
    narration: str,
    category: str,
    scene_index: int,
) -> Dict:
    """
    Build a complete cinematic scene prompt from narration text.
    Uses event detection, emotion, character registry, and 3-layer composition.
    """
    style = VIDEO_STYLES.get(category, VIDEO_STYLES["dark_history"])
    emotion = detect_emotion(narration)
    fg, mg, bg = detect_visual_event(narration, category)
    character = find_character(narration)
    importance = score_importance(narration)

    # Build character injection
    char_desc = ""
    char_seed = None
    if character:
        char_desc = f"{character['description']}, {character.get('emotion_default', '')},"
        char_seed = character.get("seed")

    # Camera motion based on importance and emotion
    camera_motions = ["slow zoom in", "slow pan right", "slow zoom out", "slow pan left", "slow push in"]
    if importance >= 8:
        camera = "dramatic slow push in, cinematic"
    elif "collapse" in emotion.get("camera", ""):
        camera = emotion["camera"]
    else:
        camera = camera_motions[scene_index % len(camera_motions)]

    # Build full prompt with 3-layer composition
    prompt = (
        f"{style['prefix']}"
        f"FOREGROUND: {fg}, {char_desc} "
        f"MIDGROUND: {mg}, "
        f"BACKGROUND: {bg}, "
        f"{emotion['lighting']}, {emotion['color']}, "
        f"{camera}, "
        f"no text, no watermark, no letters"
    )

    # Clean up
    prompt = re.sub(r'\s+', ' ', prompt).strip()

    return {
        "sd_prompt": prompt[:500],
        "negative_prompt": style["negative"],
        "seed": char_seed,
        "importance": importance,
        "emotion": list(EMOTION_PROFILES.keys())[
            list(EMOTION_PROFILES.values()).index(emotion)
        ] if emotion in EMOTION_PROFILES.values() else "tension",
        "camera": camera,
        "foreground": fg,
        "midground": mg,
        "background": bg,
        "character": character.get("full_name") if character else None,
    }


def build_scene_prompts(
    scene_list: List[Dict],
    script_text: str,
    category: str,
    research: dict = None,
) -> List[Dict]:
    """
    Build narration-matched cinematic prompts for all scenes.
    """
    # Inject research-based person descriptions
    if research and research.get("people"):
        global _PERSON_DESCRIPTIONS, _PRIMARY_PERSON
        _PERSON_DESCRIPTIONS = {}
        for key, person in research["people"].items():
            sd_desc = person.get("sd_description", "")
            if sd_desc:
                name = person.get("name", key).lower()
                _PERSON_DESCRIPTIONS[name] = sd_desc
                if not _PRIMARY_PERSON:
                    _PRIMARY_PERSON = sd_desc
        logger.info(f"[prompts] Loaded {len(_PERSON_DESCRIPTIONS)} person descriptions from research")

    clean = re.sub(r'\[.*?\]', '', script_text)
    clean = re.sub(r'#{1,4}\s*', '', clean)
    clean = re.sub(r'\n{3,}', ' ', clean).strip()

    total_words = len(clean.split())
    total_duration = scene_list[-1]["end"] if scene_list else 1
    words = clean.split()
    result = []

    for scene in scene_list:
        start_ratio = scene["start"] / total_duration
        end_ratio = scene["end"] / total_duration
        start_word = int(start_ratio * total_words)
        end_word = max(start_word + 5, int(end_ratio * total_words))
        narration_chunk = ' '.join(words[start_word:end_word])

        prompt_data = build_scene_prompt_v3(narration_chunk, category, scene["scene_index"])

        updated = dict(scene)
        updated["narration_chunk"] = narration_chunk[:200]
        updated.update(prompt_data)
        result.append(updated)

    logger.info(f"[prompts_v3] Built {len(result)} cinematic scene prompts")
    return result

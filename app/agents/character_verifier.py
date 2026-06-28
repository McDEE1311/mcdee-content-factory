"""
Character Verifier — Automated verified character bible.
Uses Wikipedia + Wikidata + Ollama cross-verification.
Confidence-scored. Works for ANY person, not just pre-coded ones.
Never silently invents details below confidence threshold.
"""
import json
import logging
import re
import time
from typing import Dict, List, Optional
import httpx

logger = logging.getLogger(__name__)
HEADERS = {"User-Agent": "TrendForgeResearch/1.0 (documentary-research; linux)"}


def wikidata_person(name: str, story_context: str = "") -> Dict:
    """Query Wikidata for structured person data."""
    try:
        # Search for entity
        # Include story context in search to avoid wrong person matches
        search_query = name if len(name.split()) > 1 else name
        if story_context:
            # Add key context word to disambiguate
            context_words = [w for w in story_context.split()[:10]
                           if len(w) > 4 and w[0].isupper()]
            if context_words:
                search_query = f"{name} {context_words[0]}"
        r = httpx.get(
            "https://www.wikidata.org/w/api.php",
            params={"action": "wbsearchentities", "search": search_query,
                    "language": "en", "format": "json", "limit": 3},
            headers=HEADERS, timeout=10.0,
        )
        results = r.json().get("search", [])
        if not results:
            return {}

        # Find best match — prefer one that contains the actual name
        entity_id = None
        for res in results:
            label = res.get("label", "").lower()
            if all(part.lower() in label for part in name.lower().split()):
                entity_id = res["id"]
                break
        if not entity_id:
            entity_id = results[0]["id"]

        # Get entity data
        r2 = httpx.get(
            "https://www.wikidata.org/w/api.php",
            params={"action": "wbgetentities", "ids": entity_id,
                    "languages": "en", "format": "json",
                    "props": "claims|labels|descriptions"},
            headers=HEADERS, timeout=10.0,
        )
        entity = r2.json().get("entities", {}).get(entity_id, {})

        # Extract claims
        claims = entity.get("claims", {})
        data = {
            "wikidata_id": entity_id,
            "label": entity.get("labels", {}).get("en", {}).get("value", name),
            "description": entity.get("descriptions", {}).get("en", {}).get("value", ""),
        }

        # Gender (P21)
        if "P21" in claims:
            gender_id = claims["P21"][0].get("mainsnak", {}).get("datavalue", {}).get("value", {}).get("id", "")
            data["gender_wikidata"] = "woman" if gender_id == "Q6581072" else "man" if gender_id == "Q6581097" else ""

        # Date of birth (P569) for age calculation
        if "P569" in claims:
            dob = claims["P569"][0].get("mainsnak", {}).get("datavalue", {}).get("value", {})
            if dob.get("time"):
                year_match = re.search(r'\+(\d{4})', dob["time"])
                if year_match:
                    data["birth_year"] = int(year_match.group(1))

        # Occupation (P106)
        if "P106" in claims:
            occ_ids = [c.get("mainsnak", {}).get("datavalue", {}).get("value", {}).get("id", "")
                       for c in claims["P106"][:3]]
            data["occupation_ids"] = occ_ids

        logger.info(f"[character] Wikidata: {name} → {data.get('description', '')[:60]}")
        return data

    except Exception as e:
        logger.warning(f"[character] Wikidata failed for {name}: {e}")
        return {}


def wikipedia_person_extract(name: str) -> str:
    """Get Wikipedia extract for appearance clues."""
    try:
        r = httpx.get(
            f"https://en.wikipedia.org/api/rest_v1/page/summary/{name.replace(' ', '_')}",
            headers=HEADERS, timeout=10.0,
        )
        if r.status_code == 200:
            return r.json().get("extract", "")[:1500]
    except Exception as e:
        logger.warning(f"[character] Wikipedia failed for {name}: {e}")
    return ""


def ollama_verify_character(
    name: str,
    wiki_text: str,
    wikidata: Dict,
    story_context: str,
) -> Dict:
    """
    Use Ollama to extract and verify character appearance.
    Cross-references multiple sources. Returns confidence score.
    """
    from app.services.ollama_client import ollama_client

    gender_hint = wikidata.get("gender_wikidata", "")
    birth_year = wikidata.get("birth_year", "")
    description = wikidata.get("description", "")

    prompt = f"""You are building a verified character profile for documentary artwork generation.

PERSON: {name}
STORY CONTEXT: {story_context}

VERIFIED DATA FROM WIKIDATA:
- Description: {description}
- Gender: {gender_hint if gender_hint else "unknown — determine from sources"}
- Birth year: {birth_year if birth_year else "unknown"}

WIKIPEDIA EXTRACT:
{wiki_text[:800] if wiki_text else "Not available — use your training knowledge"}

INSTRUCTIONS:
1. Extract ONLY what is actually documented or widely known
2. For famous public figures, use your training knowledge about their appearance
3. Do NOT invent details — if unsure, use "unknown" and lower the confidence
4. Confidence score: 0.0-1.0 (how certain you are this description is accurate)
5. If confidence < 0.6, use generic stable descriptors only

Output ONLY this JSON:
{{
  "name": "{name}",
  "gender": "woman or man",
  "age_in_story": "approximate age during the key events",
  "hair_color": "specific color or 'unknown'",
  "hair_style": "description or 'unknown'",
  "eye_color": "color or 'unknown'",
  "skin_tone": "description",
  "build": "slim/average/stocky/athletic",
  "signature_clothing": "what they are most known for wearing, or 'professional attire'",
  "typical_expression": "how they typically look in public",
  "public_role": "their role in this story",
  "sd_character_prompt": "FORMAT: [name], [gender], [age], [build], [hair color and style], [eye color], [clothing], [expression]. Example: Bernie Madoff, older man 70s, average build, grey hair slicked back, blue eyes, expensive dark business suit, confident charming expression",
  "confidence": 0.85,
  "source_notes": "what sources confirm this"
}}"""

    try:
        result = ollama_client.generate_json(prompt, temperature=0.1)
        if result and result.get("sd_character_prompt"):
            conf = result.get("confidence", 0.5)
            logger.info(f"[character] {name}: confidence={conf:.2f} → {result['sd_character_prompt'][:80]}")

            # If low confidence, use safer generic prompt
            if conf < 0.6:
                gender = result.get("gender", "person")
                age = result.get("age_in_story", "adult")
                role = result.get("public_role", "professional")
                result["sd_character_prompt"] = (
                    f"{gender} {age} {role}, professional appearance, "
                    f"consistent character design"
                )
                result["confidence_adjusted"] = True
                logger.warning(f"[character] Low confidence for {name} — using generic descriptor")

            return result
    except Exception as e:
        logger.warning(f"[character] Ollama verification failed for {name}: {e}")

    # Fallback
    return {
        "name": name,
        "gender": wikidata.get("gender_wikidata", "person"),
        "sd_character_prompt": f"professional person, consistent character design, documentary portrait",
        "confidence": 0.3,
        "source_notes": "fallback — no reliable data found",
    }


def verify_character(name: str, story_context: str = "") -> Dict:
    """
    Full automated character verification pipeline.
    Wikipedia + Wikidata + Ollama cross-verification.
    Returns verified character profile with confidence score.
    """
    logger.info(f"[character] Verifying: {name}")

    # Step 1: Wikidata structured data
    wikidata = wikidata_person(name, story_context)
    time.sleep(0.3)

    # Step 2: Wikipedia text
    wiki_text = wikipedia_person_extract(name)
    time.sleep(0.3)

    # Step 3: Ollama cross-verification
    profile = ollama_verify_character(name, wiki_text, wikidata, story_context)

    # Merge wikidata facts
    if wikidata.get("birth_year") and not profile.get("birth_year"):
        profile["birth_year"] = wikidata["birth_year"]
    if wikidata.get("gender_wikidata") and profile.get("confidence", 0) < 0.7:
        profile["gender"] = wikidata["gender_wikidata"]

    # Add SD seed based on name hash (consistent across runs)
    name_hash = sum(ord(c) for c in name.lower())
    profile["sd_seed"] = 1000 + (name_hash % 8000)

    return profile


def build_character_bible(names: List[str], story_context: str) -> Dict:
    """Build verified character bible for all named people in the documentary."""
    bible = {}
    for name in names:
        profile = verify_character(name, story_context)
        key = name.lower().replace(" ", "_")
        bible[key] = profile
        logger.info(f"[character] Bible entry: {name} → conf={profile.get('confidence', 0):.2f}")
        time.sleep(0.5)
    return bible

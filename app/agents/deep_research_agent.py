"""
Deep Research Agent V6
Full automated pipeline: Wikipedia + Wikidata + Ollama verification
Produces: character_bible, location_bible, visual_bible, timeline, storyboard
"""
import json
import logging
import re
import time
from typing import Dict, List
import httpx

logger = logging.getLogger(__name__)
HEADERS = {"User-Agent": "TrendForgeResearch/1.0 (documentary-research; linux)"}


def wiki_summary(title: str) -> str:
    try:
        r = httpx.get(
            f"https://en.wikipedia.org/api/rest_v1/page/summary/{title.replace(' ','_')}",
            headers=HEADERS, timeout=10.0,
        )
        if r.status_code == 200:
            return r.json().get("extract", "")[:1200]
    except Exception as e:
        logger.warning(f"[research] Wiki failed '{title}': {e}")
    return ""


def wiki_search(query: str, limit: int = 3) -> List[Dict]:
    try:
        r = httpx.get(
            "https://en.wikipedia.org/w/api.php",
            params={"action":"query","format":"json","list":"search",
                    "srsearch":query,"srlimit":limit,"srprop":"snippet"},
            headers=HEADERS, timeout=10.0,
        )
        if r.status_code == 200:
            results = []
            for item in r.json().get("query",{}).get("search",[]):
                snippet = re.sub(r'<[^>]+>','',item.get("snippet",""))
                if snippet:
                    results.append({"title":item["title"],"text":snippet[:400]})
            return results
    except Exception as e:
        logger.warning(f"[research] Wiki search failed: {e}")
    return []


def ollama_extract(prompt: str, temperature: float = 0.2) -> dict:
    from app.services.ollama_client import ollama_client
    try:
        return ollama_client.generate_json(prompt, temperature=temperature) or {}
    except Exception as e:
        logger.warning(f"[research] Ollama failed: {e}")
        return {}


def build_timeline(topic: str, wiki_text: str) -> List[Dict]:
    prompt = f"""Documentary: "{topic}"
Wikipedia: {wiki_text[:800]}

Extract 8-12 chronological events. Output ONLY JSON array:
[{{"sequence":1,"year":"YYYY","title":"short title","description":"what happened",
"emotional_tone":"triumph/deception/panic/revelation/collapse/justice",
"importance":"high/medium/low","characters_involved":["name1"],
"narrative_purpose":"why this matters"}}]"""
    result = ollama_extract(prompt, 0.2)
    events = result if isinstance(result, list) else result.get("events", [])
    logger.info(f"[research] Timeline: {len(events)} events")
    return events


def build_location_bible(topic: str, wiki_text: str) -> Dict:
    prompt = f"""Documentary: "{topic}"
Wikipedia: {wiki_text[:600]}

List all KEY LOCATIONS in this story. Output ONLY JSON:
{{"locations":[{{"id":"location_id","name":"Full Name","period":"when",
"visual_description":"what it looks like","atmosphere":"mood",
"sd_prompt":"complete SD location description",
"story_events":["what happens here"]}}]}}"""
    result = ollama_extract(prompt, 0.2)
    locations = {}
    for loc in result.get("locations", []):
        if loc.get("id"):
            locations[loc["id"]] = loc
            logger.info(f"[research] Location: {loc['name']}")
    return locations


def build_storyboard(topic: str, characters: Dict, locations: Dict,
                     timeline: List[Dict], wiki_text: str) -> List[Dict]:
    char_ref = "\n".join(
        f"- {v['name']}: {v.get('sd_character_prompt','')[:100]}"
        for v in characters.values()
    )
    loc_ref = "\n".join(
        f"- {v['name']}: {v.get('sd_prompt','')[:80]}"
        for v in locations.values()
    )
    timeline_ref = "\n".join(
        f"- {e.get('year','')}: {e.get('title','')} — {e.get('description','')[:80]}"
        for e in timeline[:10]
    )

    prompt = f"""Documentary storyboard director for: "{topic}"

CHARACTERS (use these EXACT descriptions):
{char_ref}

LOCATIONS:
{loc_ref}

TIMELINE:
{timeline_ref}

Create 35 storyboard scenes. Each scene = specific story moment. NO generic imagery.
Rules:
- Every person scene MUST reference a character from above
- Every location scene MUST reference a location from above
- Follow arc: RISE → CRACKS → EVIDENCE → COLLAPSE → AFTERMATH
- Include: close-ups, wide shots, evidence scenes, reaction scenes
- Each sd_scene_prompt must be 50-100 words and story-specific

Output ONLY JSON array:
[{{"scene_number":1,"act":"RISE","title":"short title",
"character":"character name or null","location":"location name",
"action":"SPECIFIC what is happening — not generic",
"emotion":"triumph/deception/hope/fear/panic/justice",
"camera":"close-up/medium/wide/dutch-angle/overhead",
"importance":"hero/supporting",
"sd_scene_prompt":"detailed specific SD prompt for this exact story moment",
"narrative_purpose":"why this scene matters"}}]"""

    from app.services.ollama_client import ollama_client
    try:
        raw = ollama_client.generate(
            prompt,
            system="You are a documentary storyboard director. Output ONLY valid JSON array.",
            temperature=0.3, max_tokens=6000, timeout=600.0,
        )
        match = re.search(r'\[.*\]', raw, re.DOTALL)
        if match:
            result = json.loads(match.group(0))
        else:
            result = json.loads(raw)
    except Exception as e:
        logger.warning(f"[research] Storyboard failed: {e}")
        result = []

    storyboard = result if isinstance(result, list) else result.get("scenes", [])
    logger.info(f"[research] Storyboard: {len(storyboard)} scenes")
    return storyboard[:40]


def _extract_names(text: str) -> List[str]:
    NOT_NAMES = {
        "The Collapse","Wall Street","Silicon Valley","How Sam","How Elizabeth",
        "United States","New York","San Francisco","The Woman","The Man",
        "Everyone How","Billion Dollar","Nobody Listened","Almost Got",
        "Who Fooled","What Happened","Why Did","The Rise","The Fall",
        "Dark Files","Beyond Earth","The Last","What If","True Story",
        "Breaking News","Full Story","Inside Story","Untold Story","Trend Forge",
    }
    FIRST_NAMES = {
        "elizabeth","sam","richard","jeff","kenneth","ken","caroline",
        "bernie","martin","adam","elon","mark","steve","bill","warren",
        "charles","diana","edward","george","henry","james","john",
        "michael","robert","thomas","william","david","daniel","sunny",
        "nick","ryan","anna","sarah","lisa","mary","jane","karen",
        "tyler","sunny","ramesh","channing","rupert",
    }
    matches = re.findall(r'\b([A-Z][a-z]{1,15} [A-Z][a-z]{1,15})\b', text)
    names = []
    for m in matches:
        if m in NOT_NAMES:
            continue
        first = m.split()[0].lower()
        if first in FIRST_NAMES:
            names.append(m)
    return list(dict.fromkeys(names))[:4]


def _extract_companies(text: str) -> List[str]:
    known = [
        "Theranos","Enron","Lehman Brothers","FTX","WeWork",
        "Alameda Research","Kodak","Blockbuster","Sears","Nokia",
        "WorldCom","Wirecard","Luckin Coffee","Bear Stearns",
        "Silicon Valley Bank","Celsius","Terra Luna",
    ]
    return [c for c in known if c.lower() in text.lower()]


def deep_research(topic: str, category: str) -> Dict:
    """Full V6 research pipeline with verified characters and visual bible."""
    logger.info(f"[research] V6 Deep Research: {topic[:60]}")

    names = _extract_names(topic)
    companies = _extract_companies(topic)
    logger.info(f"[research] Names={names} Companies={companies}")

    # Gather Wikipedia
    wiki_texts = {}
    primary_search = companies[0] if companies else (names[0] if names else topic.split()[0])
    logger.info(f"[research] Primary search: '{primary_search}'")

    results = wiki_search(primary_search, 3)
    main_wiki = ""
    for r in results:
        candidate = wiki_summary(r["title"])
        if candidate and len(candidate) > 100:
            main_wiki = candidate
            wiki_texts["topic"] = main_wiki
            logger.info(f"[research] Wikipedia: '{r['title']}' ({len(main_wiki)} chars)")
            break

    for company in companies[:2]:
        text = wiki_summary(company)
        if not text:
            rs = wiki_search(company, 1)
            if rs:
                text = wiki_summary(rs[0]["title"])
        if text:
            wiki_texts[company] = text
        time.sleep(0.3)

    combined_wiki = "\n\n".join(wiki_texts.values())[:2000]

    # Build timeline
    logger.info("[research] Building Timeline...")
    timeline = build_timeline(topic, combined_wiki)
    time.sleep(0.5)

    # Build verified character bible using character_verifier
    logger.info("[research] Building Verified Character Bible...")
    from app.agents.character_verifier import build_character_bible
    story_context = f"{topic}. {combined_wiki[:300]}"
    characters = build_character_bible(names[:3], story_context)

    # Build location bible
    logger.info("[research] Building Location Bible...")
    locations = build_location_bible(topic, combined_wiki)
    time.sleep(0.5)

    # Build visual bible (objects, evidence, key moments)
    logger.info("[research] Building Visual Bible...")
    from app.agents.visual_research_agent import extract_visual_bible
    visual_bible = extract_visual_bible(
        topic, category, characters, combined_wiki, timeline
    )
    time.sleep(0.5)

    # Build storyboard
    logger.info("[research] Building Storyboard (35 scenes)...")
    storyboard = build_storyboard(topic, characters, locations, timeline, combined_wiki)

    # Key facts
    key_facts = []
    for text in wiki_texts.values():
        sentences = re.split(r'(?<=[.!?])\s+', text)
        key_facts.extend(sentences[:5])

    packet = {
        "topic": topic,
        "category": category,
        "key_facts": key_facts[:15],
        "characters": characters,
        "locations": locations,
        "visual_bible": visual_bible,
        "timeline": timeline,
        "storyboard": storyboard,
        "wiki_summary": combined_wiki[:1000],
        "primary_character": list(characters.values())[0] if characters else {},
    }

    conf_scores = [f"{v.get('confidence',0):.2f}" for v in characters.values()]
    logger.info(
        f"[research] V6 Complete: {len(characters)} chars conf={conf_scores}, "
        f"{len(locations)} locs, {len(timeline)} events, "
        f"{len(storyboard)} storyboard scenes, "
        f"{len(visual_bible.get('objects', []))} objects"
    )
    return packet


def save_research(packet: Dict, path: str):
    import os
    os.makedirs(os.path.dirname(path) if os.path.dirname(path) else ".", exist_ok=True)
    with open(path, "w") as f:
        json.dump(packet, f, indent=2)
    logger.info(f"[research] Saved: {path}")


def load_research(path: str) -> Dict:
    with open(path) as f:
        return json.load(f)

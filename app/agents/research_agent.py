"""
Research Agent V3
Wikipedia + Ollama knowledge for real person/topic research.
Extracts visual descriptions so SD generates matching images.
"""
import json
import logging
import re
import time
from typing import Dict, List
import httpx

logger = logging.getLogger(__name__)

HEADERS = {"User-Agent": "TrendForgeResearch/1.0 (content-research-bot; linux)"}


def wikipedia_summary(title: str) -> str:
    """Get Wikipedia summary for any title."""
    try:
        formatted = title.strip().replace(" ", "_")
        r = httpx.get(
            f"https://en.wikipedia.org/api/rest_v1/page/summary/{formatted}",
            headers=HEADERS, timeout=10.0,
        )
        if r.status_code == 200:
            data = r.json()
            return data.get("extract", "")[:1000]
    except Exception as e:
        logger.warning(f"[research] Wikipedia failed for '{title}': {e}")
    return ""


def wikipedia_search(query: str, limit: int = 3) -> List[Dict]:
    """Search Wikipedia for a query."""
    try:
        r = httpx.get(
            "https://en.wikipedia.org/w/api.php",
            params={"action": "query", "format": "json", "list": "search",
                    "srsearch": query, "srlimit": limit, "srprop": "snippet"},
            headers=HEADERS, timeout=10.0,
        )
        if r.status_code == 200:
            results = []
            for item in r.json().get("query", {}).get("search", []):
                snippet = re.sub(r'<[^>]+>', '', item.get("snippet", ""))
                if snippet:
                    results.append({
                        "title": item.get("title", ""),
                        "text": snippet[:400],
                    })
            return results
    except Exception as e:
        logger.warning(f"[research] Wikipedia search failed: {e}")
    return []


def ollama_describe_person(name: str, wiki_text: str = "") -> Dict:
    """Use Ollama to build a precise visual description from Wikipedia + training data."""
    from app.services.ollama_client import ollama_client

    context = f"Wikipedia information:\n{wiki_text}\n\n" if wiki_text else ""

    prompt = f"""{context}Using your knowledge about {name}, provide a precise visual description for generating artwork.

Output ONLY this JSON:
{{
  "name": "{name}",
  "gender": "woman or man",
  "age_approximate": "20s/30s/40s/50s",
  "hair": "exact color, length, style",
  "eyes": "exact color",
  "build": "slim/athletic/average/heavy",
  "skin": "skin tone description",
  "signature_look": "what they are most famous for wearing or how they look",
  "sd_description": "young woman in her thirties, long straight blonde hair, piercing blue eyes, black turtleneck sweater, intense focused expression, pale complexion",
  "key_visual_facts": ["fact1 about appearance", "fact2"],
  "found": true
}}"""

    try:
        result = ollama_client.generate_json(prompt, temperature=0.1)
        if result and result.get("sd_description"):
            logger.info(f"[research] {name}: {result['sd_description'][:80]}")
            return result
    except Exception as e:
        logger.warning(f"[research] Ollama description failed: {e}")

    return {"name": name, "sd_description": "", "found": False}


def research_person(name: str) -> Dict:
    """Full person research: Wikipedia + Ollama."""
    logger.info(f"[research] Researching person: {name}")

    # Try direct Wikipedia page
    wiki_text = wikipedia_summary(name)

    # If not found directly, search
    if not wiki_text:
        results = wikipedia_search(name, 2)
        if results:
            wiki_text = wikipedia_summary(results[0]["title"])

    if wiki_text:
        logger.info(f"[research] Wikipedia: {len(wiki_text)} chars about {name}")
    else:
        logger.info(f"[research] No Wikipedia, using Ollama training data for {name}")

    # Build visual description
    desc = ollama_describe_person(name, wiki_text)
    return desc


def research_topic(topic: str, category: str) -> Dict:
    """Full research pipeline for a documentary topic."""
    logger.info(f"[research] Researching: {topic[:60]}")

    packet = {
        "topic": topic, "category": category,
        "key_facts": [], "key_events": [],
        "people": {}, "companies": {},
        "visual_context": {},
    }

    # Extract names from topic
    names = _extract_names(topic)
    companies = _extract_companies(topic)

    logger.info(f"[research] Names: {names} | Companies: {companies}")

    # Research each person
    for name in names[:3]:
        data = research_person(name)
        if data.get("sd_description"):
            key = name.lower().replace(" ", "_")
            packet["people"][key] = data
        time.sleep(0.5)

    # Research companies via Wikipedia
    for company in companies[:2]:
        wiki = wikipedia_summary(company)
        if not wiki:
            results = wikipedia_search(company, 1)
            if results:
                wiki = wikipedia_summary(results[0]["title"])
        if wiki:
            packet["companies"][company] = wiki[:400]
            packet["key_facts"].append(wiki[:400])
        time.sleep(0.5)

    # General topic facts via Wikipedia search
    topic_results = wikipedia_search(topic[:60], 3)
    for r in topic_results:
        packet["key_facts"].append(r["text"])

    # Build visual context
    primary_desc = ""
    if packet["people"]:
        first = list(packet["people"].values())[0]
        primary_desc = first.get("sd_description", "")

    packet["visual_context"] = {
        "primary_person": list(packet["people"].keys())[0] if packet["people"] else "",
        "primary_person_description": primary_desc,
        "setting_era": {
            "financial_rise_fall": "modern corporate",
            "historical_mystery": "18th century European",
            "dark_history": "historical",
            "survival_stories": "modern wilderness",
            "space_mysteries": "cosmic deep space",
        }.get(category, "modern"),
    }

    logger.info(
        f"[research] Done: {len(packet['key_facts'])} facts, "
        f"{len(packet['people'])} people: {list(packet['people'].keys())}"
    )
    return packet


# Common words that appear capitalized but are NOT names
_NOT_NAMES = {
    "The Collapse", "Wall Street", "Silicon Valley", "How Sam", "How Elizabeth",
    "United States", "New York", "San Francisco", "The Woman", "The Man",
    "Everyone How", "Billion Dollar", "Nobody Listened", "Almost Got",
    "Who Fooled", "What Happened", "Why Did", "The Rise", "The Fall",
    "Dark Files", "Beyond Earth", "The Last", "What If", "True Story",
    "Breaking News", "Full Story", "Inside Story", "Untold Story",
}

_FIRST_NAME_INDICATORS = {
    "elizabeth", "sam", "richard", "jeff", "kenneth", "ken", "caroline",
    "bernie", "martin", "adam", "elon", "mark", "steve", "bill", "warren",
    "charles", "diana", "edward", "george", "henry", "james", "john",
    "michael", "robert", "thomas", "william", "david", "daniel",
}

def _extract_names(text: str) -> List[str]:
    matches = re.findall(r'\b([A-Z][a-z]{1,15} [A-Z][a-z]{1,15})\b', text)
    names = []
    for m in matches:
        if m in _NOT_NAMES:
            continue
        # Check if first word looks like a real first name
        first_word = m.split()[0].lower()
        if first_word in _FIRST_NAME_INDICATORS:
            names.append(m)
            continue
        # Skip if either word is a common non-name word
        skip_words = {"who", "how", "what", "the", "and", "but", "for",
                      "billion", "million", "dollar", "nobody", "everyone",
                      "almost", "fooled", "listened", "predicted", "stole"}
        words = [w.lower() for w in m.split()]
        if not any(w in skip_words for w in words):
            names.append(m)
    return list(dict.fromkeys(names))[:3]


def _extract_companies(text: str) -> List[str]:
    known = ["Theranos", "Enron", "Lehman Brothers", "FTX", "WeWork",
             "Alameda Research", "Kodak", "Blockbuster", "Sears", "Nokia",
             "WorldCom", "Wirecard", "Luckin Coffee", "Theranos"]
    return [c for c in known if c.lower() in text.lower()]


def save_research_packet(packet: Dict, path: str):
    import os
    os.makedirs(os.path.dirname(path) if os.path.dirname(path) else ".", exist_ok=True)
    with open(path, "w") as f:
        json.dump(packet, f, indent=2)
    logger.info(f"[research] Saved: {path}")


def load_research_packet(path: str) -> Dict:
    with open(path) as f:
        return json.load(f)

"""
Research Agent
Builds research packets for each selected topic.
"""
import pathlib
_REPO_ROOT = pathlib.Path(__file__).parent.parent.parent
import logging
import re
from datetime import datetime
from typing import List, Optional
import httpx
from sqlalchemy.orm import Session

from app.models import Topic, ResearchPacket, RunLog
from app.services.ollama_client import ollama_client

logger = logging.getLogger(__name__)
PROMPT_PATH = _REPO_ROOT / "app" / "prompts" / "research_brief.md"


def fetch_search_snippets(query: str, limit: int = 5) -> List[dict]:
    """
    Fetch search result snippets for a query using DuckDuckGo HTML scraping.
    No API key required.
    """
    try:
        headers = {"User-Agent": "Mozilla/5.0 (compatible; McDEE-ContentFactory/0.1)"}
        url = f"https://html.duckduckgo.com/html/?q={httpx.URL(query).params}"
        r = httpx.get(
            "https://html.duckduckgo.com/html/",
            params={"q": query},
            headers=headers,
            timeout=10.0,
            follow_redirects=True,
        )
        if r.status_code != 200:
            return []

        # Very basic parsing — extract result snippets
        text = r.text
        results = []
        # Find result blocks between <a class="result__snippet"
        import re
        snippets = re.findall(r'class="result__snippet"[^>]*>(.*?)</a>', text, re.DOTALL)
        titles = re.findall(r'class="result__a"[^>]*>(.*?)</a>', text, re.DOTALL)
        urls = re.findall(r'class="result__url"[^>]*>(.*?)</span>', text, re.DOTALL)

        for i in range(min(len(snippets), limit)):
            snippet = re.sub(r'<[^>]+>', '', snippets[i]).strip()
            title = re.sub(r'<[^>]+>', '', titles[i]).strip() if i < len(titles) else ""
            url = urls[i].strip() if i < len(urls) else ""
            if snippet:
                results.append({"title": title, "snippet": snippet, "url": url})

        return results[:limit]

    except Exception as e:
        logger.warning(f"[research] Search snippets failed for '{query}': {e}")
        return []


def build_research_packet(topic: Topic, db: Session) -> Optional[ResearchPacket]:
    """
    Build and store a research packet for a topic.
    """
    # Check if already done
    existing = db.query(ResearchPacket).filter(
        ResearchPacket.topic_id == topic.id
    ).first()
    if existing:
        return existing

    logger.info(f"[research] Researching: {topic.title[:80]}")

    # Fetch search snippets
    sources = fetch_search_snippets(topic.title, limit=6)
    sources_text = "\n".join([
        f"- {s.get('title', '')}: {s.get('snippet', '')}"
        for s in sources
    ])

    if not sources_text:
        sources_text = f"Topic: {topic.title}\nNo external sources available."

    # Load prompt
    try:
        with open(str(PROMPT_PATH)) as f:
            prompt_template = f.read()
    except Exception:
        prompt_template = "Summarize this topic in 3 paragraphs: {{title}}\n\nSources:\n{{sources}}"

    prompt = (prompt_template
              .replace("{{title}}", topic.title)
              .replace("{{niche}}", topic.niche or "ai-tech")
              .replace("{{sources}}", sources_text))

    # Generate with LLM
    research_data = {}
    if ollama_client.is_available():
        research_data = ollama_client.generate_json(prompt, temperature=0.3)

    if not research_data:
        # Fallback: basic packet from title
        research_data = {
            "summary": f"Analysis of: {topic.title}. This topic relates to {topic.niche}. {topic.angle}",
            "facts": [
                f"This is a trending topic in {topic.niche}.",
                f"Angle: {topic.angle}",
                "Further research recommended.",
            ],
            "controversy": "No significant controversy identified.",
            "angle_suggestion": topic.angle or "",
        }

    packet = ResearchPacket(
        topic_id=topic.id,
        sources_json=[s.get("url", "") for s in sources if s.get("url")],
        summary=research_data.get("summary", ""),
        facts_json=research_data.get("facts", []),
        controversy=research_data.get("controversy", ""),
    )
    db.add(packet)
    db.flush()

    logger.info(f"[research] Packet created for topic {topic.id}")
    return packet


def run_research_phase(db: Session, topics: List[Topic], run_date: str = None) -> List[ResearchPacket]:
    """Run research for all selected topics."""
    if not run_date:
        run_date = datetime.now().strftime("%Y-%m-%d")

    log = RunLog(run_date=run_date, phase="research", status="started")
    db.add(log)
    db.flush()

    packets = []
    for topic in topics:
        try:
            packet = build_research_packet(topic, db)
            if packet:
                packets.append(packet)
                topic.status = "researched"
        except Exception as e:
            logger.error(f"[research] Failed for topic {topic.id}: {e}")
            topic.status = "research_failed"

    db.flush()
    log.status = "completed"
    log.items_processed = len(packets)

    logger.info(f"[research] Done: {len(packets)} packets created.")
    return packets

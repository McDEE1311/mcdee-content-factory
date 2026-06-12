"""
Script Agent
Generates video scripts, titles, descriptions, tags, and X posts using Ollama.
"""
import pathlib
_REPO_ROOT = pathlib.Path(__file__).parent.parent.parent
import logging
import re
from datetime import datetime
from typing import List, Optional
from sqlalchemy.orm import Session

from app.models import Topic, ResearchPacket, Script, RunLog
from app.services.ollama_client import ollama_client

logger = logging.getLogger(__name__)
PROMPT_PATH = _REPO_ROOT / "app" / "prompts" / "video_script.md"


def count_words(text: str) -> int:
    return len(re.findall(r'\w+', text))


def generate_script(topic: Topic, packet: Optional[ResearchPacket], db: Session) -> Optional[Script]:
    """Generate a script for a topic."""
    # Check if already generated
    existing = db.query(Script).filter(Script.topic_id == topic.id).first()
    if existing:
        logger.info(f"[script] Script already exists for topic {topic.id}")
        return existing

    logger.info(f"[script] Generating script for: {topic.title[:80]}")

    # Build research context
    summary = ""
    facts_text = ""
    if packet:
        summary = packet.summary or ""
        facts = packet.facts_json or []
        facts_text = "\n".join([f"- {f}" for f in facts])

    if not summary:
        summary = f"Topic: {topic.title}. Niche: {topic.niche}. {topic.angle}"

    # Load prompt
    try:
        with open(str(PROMPT_PATH)) as f:
            prompt_template = f.read()
    except Exception:
        prompt_template = "Write a 5-8 minute YouTube script about: {{title}}"

    prompt = (prompt_template
              .replace("{{title}}", topic.title)
              .replace("{{niche}}", topic.niche or "AI technology")
              .replace("{{angle}}", topic.angle or "")
              .replace("{{research_summary}}", summary[:2000])
              .replace("{{facts}}", facts_text[:1000]))

    script_data = {}

    if ollama_client.is_available():
        try:
            script_data = ollama_client.generate_json(prompt, temperature=0.7, timeout=180.0)
        except Exception as e:
            logger.warning(f"[script] Ollama failed: {e}")

    if not script_data or not script_data.get("script_text"):
        logger.warning(f"[script] Falling back to placeholder for topic {topic.id}")
        script_data = _placeholder_script(topic, summary)
        status = "needs_review"
    else:
        status = "generated"

    script_text = script_data.get("script_text", "")
    wc = count_words(script_text)

    script = Script(
        topic_id=topic.id,
        title=script_data.get("title", topic.title)[:512],
        hook=script_data.get("hook", "")[:2000],
        script_text=script_text,
        description=script_data.get("description", ""),
        tags_json=script_data.get("tags", [])[:30],
        thumbnail_prompt=script_data.get("thumbnail_prompt", ""),
        x_post=script_data.get("x_post", ""),
        word_count=wc,
        status=status,
    )
    db.add(script)
    db.flush()

    topic.status = "scripted"
    logger.info(f"[script] Script created: {wc} words, status={status}")
    return script


def _placeholder_script(topic: Topic, summary: str) -> dict:
    """Generate a basic placeholder script when Ollama is unavailable."""
    title = topic.title
    niche = topic.niche or "AI technology"
    return {
        "title": f"{title[:80]} - What You Need to Know",
        "hook": f"Today we're covering something important in the world of {niche}: {title}.",
        "script_text": f"""[HOOK]
Today we're covering something important in the world of {niche}: {title}.

[WHY IT MATTERS]
{summary[:300]}

[WHAT HAPPENED]
This topic has emerged as a trending subject in the {niche} space. Here's what we know so far.

[BREAKDOWN]
Let's break down the key components of this story and what it means for builders and infrastructure operators.

[RISKS AND REALITY CHECK]
As with any emerging development, there are uncertainties here. We'll need to watch how this develops over the coming days.

[WHAT TO WATCH NEXT]
Keep an eye on developments in {niche} and how the community responds to this.

[CTA]
If you found this useful, subscribe for daily AI infrastructure briefs. Drop your thoughts in the comments below.
""",
        "description": f"Today's brief covers {title}. {summary[:200]}",
        "tags": [niche, "AI", "technology", "infrastructure", "automation"],
        "thumbnail_prompt": f"Dark background with bold text: {title[:30]}",
        "x_post": f"New brief: {title[:120]} Watch: [LINK] #AI #infrastructure",
    }


def run_script_phase(db: Session, topics: List[Topic], run_date: str = None) -> List[Script]:
    """Generate scripts for all researched topics."""
    if not run_date:
        run_date = datetime.now().strftime("%Y-%m-%d")

    log = RunLog(run_date=run_date, phase="script_generation", status="started")
    db.add(log)
    db.flush()

    scripts = []
    for topic in topics:
        packet = db.query(ResearchPacket).filter(
            ResearchPacket.topic_id == topic.id
        ).first()

        try:
            script = generate_script(topic, packet, db)
            if script:
                scripts.append(script)
        except Exception as e:
            logger.error(f"[script] Failed for topic {topic.id}: {e}")
            topic.status = "script_failed"

    db.flush()
    log.status = "completed"
    log.items_processed = len(scripts)

    logger.info(f"[script] Done: {len(scripts)} scripts generated.")
    return scripts

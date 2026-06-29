"""
Script Agent
Generates video scripts using Ollama. Uses a two-call approach:
1. Generate the full script text as plain prose
2. Generate title/tags/description/x_post as structured JSON
"""
import json
import logging
import re
from datetime import datetime
from typing import List, Optional
from sqlalchemy.orm import Session

from app.models import Topic, ResearchPacket, Script, RunLog
from app.services.ollama_client import ollama_client
import pathlib

_REPO_ROOT = pathlib.Path(__file__).parent.parent.parent
_SCRIPT_PROMPT = _REPO_ROOT / "app" / "prompts" / "video_script.md"
_META_PROMPT = _REPO_ROOT / "app" / "prompts" / "script_metadata.md"

logger = logging.getLogger(__name__)


def count_words(text: str) -> int:
    if not isinstance(text, str):
        return 0
    return len(re.findall(r'\w+', text))


def _generate_script_text(topic: Topic, packet: Optional[ResearchPacket]) -> str:
    """Generate just the script prose — plain text, no JSON."""
    summary = ""
    facts_text = ""
    if packet:
        summary = packet.summary or ""
        facts = packet.facts_json or []
        facts_text = "\n".join([f"- {f}" for f in facts])

    if not summary:
        summary = f"Topic: {topic.title}. Niche: {topic.niche}. {topic.angle or ''}"

    system = """You are a YouTube scriptwriter for "AI Infrastructure Daily".
Write direct, technical scripts for builders and developers.
No fake hype. No financial promises. No "Hey guys" or "Welcome back".
Your scripts must be LONG — minimum 800 words of spoken content.
Write every section completely. Do not summarize. Expand each point fully."""

    prompt = f"""Write a complete YouTube script about: {topic.title}

Channel niche: {topic.niche or 'AI infrastructure, GPU compute, automation'}
Angle: {topic.angle or 'technical explainer for builders'}

Research summary:
{summary[:1500]}

Key facts:
{facts_text[:800]}

Write the FULL script using this structure. Each section must be complete — do not abbreviate:

[HOOK]
3-4 sentences. Open with a specific fact or question. No greetings.

[WHY IT MATTERS]
5-7 sentences. Real-world significance. Who is affected. Why today specifically.

[WHAT HAPPENED]
7-10 sentences. Full detail. Specific numbers, names, dates. How it works. What changed.

[BREAKDOWN]
10-14 sentences. Deep technical analysis. Implications for GPU operators, node runners, builders.
Cost implications. Competitive landscape. Who benefits, who loses.

[RISKS AND REALITY CHECK]
5-7 sentences. Honest skepticism. What could go wrong. What remains uncertain.
Use phrases like "reportedly", "according to", "early reports suggest".

[WHAT TO WATCH NEXT]
4-5 sentences. Specific things to track. Next developments. Timeline.

[CTA]
2-3 sentences. Subscribe for daily AI infrastructure briefs. Ask a specific question.

IMPORTANT: Write the complete script now. Every section must be fully written out.
Target: 900-1200 words total. Do not stop early."""

    if not ollama_client.is_available():
        return ""

    # Try up to 2 times — model sometimes stops early on first attempt
    result = ""
    for attempt in range(2):
        try:
            result = ollama_client.generate(
                prompt, system=system, temperature=0.7,
                max_tokens=3500, timeout=300.0
            ).strip()
            if len(result.split()) >= 500:
                return result
            logger.warning(f"[script] Attempt {attempt+1}: only {len(result.split())} words, retrying...")
        except Exception as e:
            logger.warning(f"[script] Attempt {attempt+1} failed: {e}")
    return result


def _generate_metadata(title: str, script_text: str, niche: str) -> dict:
    """Generate title, tags, description, x_post as JSON."""
    system = "You are a YouTube metadata specialist. Return ONLY valid JSON, no markdown, no explanation."

    prompt = f"""Given this YouTube script about "{title}" in the niche "{niche}", generate metadata.

Script excerpt (first 500 words):
{script_text[:2000]}

Return ONLY this JSON structure:
{{
  "title": "Compelling YouTube title, max 90 chars, specific not vague",
  "description": "YouTube description 200-400 words with timestamps at 0:00, 1:00, 2:30, 4:30, 6:00",
  "tags": ["tag1", "tag2", "tag3", "tag4", "tag5", "tag6", "tag7", "tag8"],
  "thumbnail_prompt": "Visual concept for thumbnail: dark background, bold text concept",
  "x_post": "X post max 240 chars promoting this video, end with [LINK]"
}}"""

    if not ollama_client.is_available():
        return {}

    try:
        result = ollama_client.generate_json(prompt, system=system, temperature=0.3, timeout=120.0)
        return result or {}
    except Exception as e:
        logger.warning(f"[script] Metadata generation failed: {e}")
        return {}


def _placeholder_script(topic: Topic, summary: str) -> tuple[str, dict]:
    """Fallback script when LLM is unavailable."""
    niche = topic.niche or "AI technology"
    title = topic.title
    text = f"""[HOOK]
{title} is making waves in the {niche} space today. Here is what you need to know and why it matters for anyone building on AI infrastructure right now.

[WHY IT MATTERS]
This development sits at the intersection of {niche} and practical compute economics. For operators running GPU nodes, validators on decentralized networks, or developers building automation workflows, the implications are direct. Understanding this story early gives you an edge in positioning your infrastructure and workloads.

{summary[:400] if summary else f"The topic of {title} has emerged as a significant development in {niche}."}

[WHAT HAPPENED]
Based on available reporting, {title.lower()} represents a notable shift in how the industry is approaching {niche}. The key developments include changes to how compute resources are allocated, how AI agents interact with infrastructure layers, and what this means for the economics of running nodes and validators at scale.

The technical underpinnings here matter. Whether you are running Bittensor subnet validators, operating GPU rental infrastructure, or building automation pipelines, the specifics of this story affect your cost basis and competitive position.

[BREAKDOWN]
Let us break down what this actually means in practice. First, the direct infrastructure implications: changes in this space typically affect GPU demand, VRAM utilization patterns, and the economics of running AI workloads at scale.

Second, the network effects matter. As more operators respond to developments like this, the competitive landscape shifts. Early movers who understand the technical details have an advantage in positioning their infrastructure before the broader market catches up.

Third, consider the tooling implications. Builders integrating {niche} into their workflows will need to account for this development when making decisions about which infrastructure to prioritize.

The key question is not whether this matters — it clearly does — but how quickly the market will price it in and what the second-order effects look like for smaller operators.

[RISKS AND REALITY CHECK]
As with any emerging development, there are real uncertainties here. Early reports may not capture the full picture. The technology may perform differently at scale than in controlled conditions. Regulatory considerations could affect how this plays out in practice.

Do not make infrastructure decisions based on hype. Wait for independent verification, test at small scale first, and be skeptical of any claims that seem too good to be true. The history of this space is littered with promising announcements that failed to deliver.

[WHAT TO WATCH NEXT]
Track how established infrastructure operators respond over the next two to four weeks. Watch for independent technical assessments and benchmarks. Monitor any regulatory signals that could affect deployment timelines.

The next 30 days will be telling. Set up alerts, follow the technical discussion in the relevant communities, and revisit your infrastructure assumptions as more information becomes available.

[WHAT TO WATCH NEXT]
Track how established infrastructure operators respond over the next two to four weeks. Watch for independent technical assessments and benchmarks. Monitor any regulatory signals that could affect deployment timelines.

The next 30 days will be telling. If you are running nodes or GPU infrastructure, model out two scenarios: one where this development accelerates adoption in your niche, and one where it stalls. Having a plan for both keeps you from being caught flat-footed.

Set up alerts on key terms, follow the technical discussion in the relevant communities, and revisit your infrastructure assumptions as more information becomes available. The builders who move early and thoughtfully tend to capture the best positions.

[CTA]
Subscribe for daily AI infrastructure briefs — we cover the developments that matter for builders and operators, not just the hype. If you found this useful, share it with someone building in the AI or crypto compute space. Drop your thoughts in the comments: how does this affect your current infrastructure setup, and what are you watching next?"""

    meta = {
        "title": f"{title[:80]} — What Builders Need to Know",
        "description": f"Analysis of {title} and its implications for AI infrastructure operators.",
        "tags": [niche, "AI", "infrastructure", "GPU", "automation", "builders"],
        "thumbnail_prompt": f"Dark background, bold text: {title[:30]}",
        "x_post": f"New brief: {title[:100]} — implications for AI infrastructure builders. Watch: [LINK]",
    }
    return text, meta


def generate_script(topic: Topic, packet: Optional[ResearchPacket], db: Session) -> Optional[Script]:
    """Generate a script for a topic using two-call approach."""
    existing = db.query(Script).filter(Script.topic_id == topic.id).first()
    if existing:
        logger.info(f"[script] Script already exists for topic {topic.id}")
        return existing

    logger.info(f"[script] Generating script for: {topic.title[:80]}")

    summary = ""
    if packet:
        summary = packet.summary or ""

    # Step 1: Generate the full script text as plain prose
    script_text = _generate_script_text(topic, packet)
    wc = count_words(script_text)

    if wc < 500:
        logger.warning(f"[script] LLM returned {wc} words, using placeholder for topic {topic.id}")
        script_text, meta = _placeholder_script(topic, summary)
        wc = count_words(script_text)
        status = "needs_review"
        generated_title = meta["title"]
        tags = meta["tags"]
        description = meta["description"]
        thumbnail_prompt = meta["thumbnail_prompt"]
        x_post = meta["x_post"]
    else:
        status = "generated"
        # Step 2: Generate structured metadata separately
        meta = _generate_metadata(topic.title, script_text, topic.niche or "AI infrastructure")
        generated_title = meta.get("title") or f"{topic.title[:80]}"
        tags = meta.get("tags") or []
        description = meta.get("description") or ""
        thumbnail_prompt = meta.get("thumbnail_prompt") or ""
        x_post = meta.get("x_post") or f"New: {generated_title[:100]} [LINK]"

    # Extract hook (first paragraph of script)
    hook = ""
    lines = script_text.strip().split('\n')
    for i, line in enumerate(lines):
        if '[HOOK]' in line.upper():
            # Get next non-empty lines
            for j in range(i+1, min(i+5, len(lines))):
                if lines[j].strip() and '[' not in lines[j]:
                    hook += lines[j].strip() + " "
            break
    if not hook:
        hook = lines[0][:500] if lines else ""

    script = Script(
        topic_id=topic.id,
        title=str(generated_title)[:512],
        hook=hook[:2000],
        script_text=script_text,
        description=str(description),
        tags_json=tags[:30] if isinstance(tags, list) else [],
        thumbnail_prompt=str(thumbnail_prompt),
        x_post=str(x_post),
        word_count=wc,
        status=status,
    )
    db.add(script)
    db.flush()

    topic.status = "scripted"
    logger.info(f"[script] Script created: {wc} words, status={status}")
    return script


def run_script_phase(db: Session, topics: List[Topic], run_date: str = None) -> List[Script]:
    """Generate scripts for all researched topics."""
    if not run_date:
        run_date = datetime.now().strftime("%Y-%m-%d")

    log = RunLog(run_date=run_date, phase="script_generation", status="started")
    db.add(log)
    db.flush()

    scripts = []
    for topic in topics:
        packet = db.query(ResearchPacket).filter(ResearchPacket.topic_id == topic.id).first()
        try:
            script = generate_script(topic, packet, db)
            if script:
                scripts.append(script)
        except Exception as e:
            logger.error(f"[script] Failed for topic {topic.id}: {e}", exc_info=True)
            topic.status = "script_failed"

    db.flush()
    log.status = "completed"
    log.items_processed = len(scripts)

    logger.info(f"[script] Done: {len(scripts)} scripts generated.")
    return scripts

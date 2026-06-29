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
_EVERGREEN_PROMPT = _REPO_ROOT / "app" / "prompts" / "evergreen_script.md"
_SHORTS_PROMPT = _REPO_ROOT / "app" / "prompts" / "shorts_script.md"

EVERGREEN_SOURCES = {"evergreen_financial_rise_fall", "evergreen_dark_forgotten_history",
                     "evergreen_survival_stories", "evergreen_space_mysteries",
                     "evergreen_future_of_work_ai"}
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

    system = """You are a YouTube scriptwriter for "Daily Trend Brief".
Write clear, conflict-aware scripts that explain who benefits, who loses, and why people genuinely disagree. Stay strictly on the story topic — never pivot to AI, tech, or unrelated subjects unless the story is actually about that.

CRITICAL FACTUAL ACCURACY RULE — NEVER VIOLATE THIS:
You will be given a research summary with confirmed facts. You may ONLY use names, numbers, dates, and specific details that appear in that research summary.
You must NEVER invent specific people's names, specific vote counts, specific dates, specific quotes, or specific events that are not explicitly stated in the research provided.
If the research is general (e.g. "candidates in Georgia and Oklahoma"), you must stay general too — say "candidates in these races" or "the Republican contenders" rather than inventing specific politician names.
If you do not know a specific fact, do not state it as if you do. Use phrases like "the candidates involved" or "officials say" instead of fabricated specifics.
Fabricating names or facts is a serious error. When in doubt, stay general and accurate rather than specific and wrong.

No fake hype. No financial promises. No "Hey guys" or "Welcome back".
Your scripts must be LONG — minimum 800 words of spoken content.
Write every section completely. Do not summarize. Expand each point fully."""

    prompt = f"""Write a complete YouTube script about: {topic.title}

Channel niche: {topic.niche or 'conflict and stakeholder debate'}
Angle: {topic.angle or 'who benefits, who loses, and why this is genuinely contested'}

Research summary:
{summary[:1500]}

Key facts:
{facts_text[:800]}

REMINDER: Only use names, numbers, and specific details from the research above. Do not invent specific people, vote counts, dates, or quotes not present in this research. If the research is general, keep your script general too.

Write the FULL script using this structure. Each section must be complete — do not abbreviate:

[HOOK]
3-4 sentences. Open with the specific tension or conflict in this story. No greetings, no "today we're looking at".

[WHAT HAPPENED]
6-9 sentences. Full factual detail. Specific numbers, names, dates, what changed and when.
Stick to confirmed facts. Use "reportedly" or "according to" for anything not fully confirmed.

[WHO BENEFITS]
5-7 sentences. Identify the specific group, person, or side that gains from this situation.
What is their strongest argument? Why do they see this as good or justified?
Present their position as their strongest advocate would — no straw-manning.

[WHO LOSES]
5-7 sentences. Identify the specific group, person, or side that is harmed or disadvantaged.
What is their strongest argument? Why do they see this as unfair or wrong?
Present their position as their strongest advocate would — no straw-manning.

[WHY PEOPLE ARE ARGUING]
6-8 sentences. Explain the real underlying disagreement — not just "some people think X, others think Y"
but WHY the conflict exists. What values, interests, or fears are actually in tension here?
What makes this genuinely hard to resolve, not just two sides being stubborn?

[WHAT HAPPENS NEXT]
4-6 sentences. Concrete next steps, decisions pending, dates to watch, who has power to act next.

[THE QUESTION]
2-3 sentences. End with a specific, real discussion question tied to the actual stakes of this story —
not a generic "what do you think?" The question should force the viewer to take a position.

IMPORTANT: Write the complete script now. Stay on this exact story throughout — no pivoting to unrelated topics.
Every section must be fully written out. Target: 900-1200 words total. Do not stop early."""

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
    """Fallback script when LLM is unavailable or fails — conflict-format, on-topic only."""
    title = topic.title
    niche = topic.niche or "conflict and stakeholder debate"

    text = f"""[HOOK]
{title} is creating real disagreement, and the reasons go deeper than the headline suggests. Here is what actually happened, who comes out ahead, who does not, and why reasonable people are landing on opposite sides.

[WHAT HAPPENED]
{summary[:600] if summary else f'Reports indicate developments around {title.lower()} that have drawn significant public attention.'} The situation has unfolded with several confirmed details, while some aspects remain disputed or still developing. As with most fast-moving stories, the full picture is still coming into focus, and early reporting should be treated with appropriate caution until more sources confirm the key facts.

[WHO BENEFITS]
One side of this story sees a clear win. Whoever initiated or supports this outcome would argue it solves a real problem, corrects an imbalance, or moves things in a necessary direction. Their position is not unreasonable on its face — there is usually a legitimate underlying interest driving their stance, even if not everyone agrees with how it plays out in practice.

[WHO LOSES]
On the other side, there is a real cost being borne by someone. Whoever is disadvantaged by this development has grounds to feel the outcome is unfair, rushed, or poorly considered. Their objections are not simply reflexive opposition — they typically point to a genuine harm, risk, or unintended consequence that the other side may be underweighting.

[WHY PEOPLE ARE ARGUING]
The disagreement here is not really about facts — it is about values and priorities that are fundamentally in tension. Both sides can look at the same set of events and reach different conclusions, because they are weighing different things as most important. That is what makes this a genuine debate rather than a simple case of one side being right and the other being wrong.

[WHAT HAPPENS NEXT]
The situation is still developing, and the next steps will likely come from whoever holds formal authority here — whether that is a court, a regulator, a company, or public pressure itself. Watch for official statements, follow-up reporting, and any formal decisions in the coming days and weeks.

[THE QUESTION]
Given what both sides have at stake here, where do you think the line should be drawn? Is this outcome fair, or does it go too far?"""

    word_count = len(text.split())

    meta = {
        "title": f"{title} — What's Really Going On",
        "description": f"Breaking down {title}: who benefits, who loses, and why people are arguing about it.",
        "tags": ["news", "debate", "explained", "trending", niche.replace(" ", "-")],
        "thumbnail_prompt": f"Bold contrast visual representing the conflict in: {title}",
        "x_post": f"{title} — who actually benefits here, and who loses? [LINK]",
    }

    return text, meta


def generate_script(topic: Topic, packet: Optional[ResearchPacket], db: Session) -> Optional[Script]:
    # Route to evergreen generator for evergreen topics
    try:
        from app.models import TrendItem
        trend = db.query(TrendItem).filter(TrendItem.id == topic.trend_id).first()
        if trend and any(trend.source.startswith("evergreen_") for _ in [1]):
            return generate_evergreen_script(topic, packet, db)
    except Exception:
        pass
    # Default: standard script generator
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
        meta = _generate_metadata(topic.title, script_text, topic.niche or "conflict and stakeholder debate")
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


# ============================================================
# SHORTS SCRIPT GENERATION — 120-220 word vertical format
# ============================================================

def _generate_shorts_script_text(topic: Topic, packet: Optional[ResearchPacket]) -> str:
    """Generate a short-form script (120-220 words) for vertical Shorts."""
    summary = ""
    facts_text = ""
    if packet:
        summary = packet.summary or ""
        facts = packet.facts_json or []
        facts_text = "\n".join([f"- {f}" for f in facts])

    if not summary:
        summary = f"Topic: {topic.title}. {topic.angle or ''}"

    system = """You are a YouTube Shorts scriptwriter. You write tight, fast, hook-driven scripts.

CRITICAL FACTUAL ACCURACY RULE — NEVER VIOLATE THIS:
Only use names, numbers, and specific details present in the research provided.
Never invent specific people, vote counts, dates, or quotes not in the research.
If research is general, stay general — do not fabricate specifics.

CRITICAL LENGTH RULE: Your script MUST be between 120 and 220 words total. Count as you write.
This is a 45-90 second video. Every sentence must be tight. No filler, no repetition, no long setup."""

    prompt = f"""Write a YouTube Shorts script about: {topic.title}

Research summary:
{summary[:1000]}

Key facts:
{facts_text[:500]}

REMINDER: Only use facts from the research above. Stay general if research is general.
Target length: 120-220 words TOTAL across all sections. This is strict.

Structure:

[HOOK]
1-2 sentences. Sharp, specific opening. No "today we're talking about". Start with the most surprising detail.

[SETUP]
2-3 sentences. Fast context — what's happening, assume nothing but waste no words.

[THE CONFLICT]
3-4 sentences. Who benefits, who loses — fastest possible terms.

[PAYOFF]
1-2 sentences. The twist or stakes that make this worth watching.

[CTA]
1 sentence. Sharp, specific question tied to this story's actual stakes.

Write the complete script now. Stay within 120-220 words total."""

    if not ollama_client.is_available():
        return ""

    result = ""
    for attempt in range(2):
        try:
            result = ollama_client.generate(
                prompt, system=system, temperature=0.7,
                max_tokens=600, timeout=120.0
            ).strip()
            wc = len(result.split())
            if 100 <= wc <= 280:
                return result
            logger.warning(f"[shorts] Attempt {attempt+1}: {wc} words (target 120-220), retrying...")
        except Exception as e:
            logger.warning(f"[shorts] Attempt {attempt+1} failed: {e}")
    return result


def generate_shorts_script(topic: Topic, packet: Optional[ResearchPacket], db: Session) -> Optional[Script]:
    """Generate a Shorts-format script and save to DB."""
    script_text = _generate_shorts_script_text(topic, packet)
    wc = count_words(script_text)

    if wc < 80:
        logger.warning(f"[shorts] Script too short ({wc}w) for topic {topic.id}, using placeholder")
        summary = packet.summary if packet else ""
        script_text, meta = _shorts_placeholder(topic, summary)
        status = "needs_review"
    else:
        meta = _generate_metadata(topic.title, script_text, topic.niche or "shorts-viral")
        status = "generated"

    wc = count_words(script_text)
    script = Script(
        topic_id=topic.id,
        title=meta.get("title", topic.title)[:200] if meta else topic.title[:200],
        hook=script_text.split("[SETUP]")[0].replace("[HOOK]", "").strip()[:300] if "[HOOK]" in script_text else "",
        script_text=script_text,
        description=meta.get("description", "") if meta else "",
        tags_json=meta.get("tags", []) if meta else [],
        thumbnail_prompt=meta.get("thumbnail_prompt", "") if meta else "",
        x_post=meta.get("x_post", "") if meta else "",
        word_count=wc,
        status=status,
        format="shorts",
    )
    db.add(script)
    db.flush()
    logger.info(f"[shorts] Script created: {wc} words, status={status}")
    return script


def _shorts_placeholder(topic: Topic, summary: str) -> tuple[str, dict]:
    """Fallback shorts script — tight conflict format, on-topic only."""
    title = topic.title
    text = f"""[HOOK]
{title} — and the two sides of this couldn't disagree more.

[SETUP]
{summary[:200] if summary else f'Heres the quick version of whats happening with {title.lower()}.'}

[THE CONFLICT]
One side sees this as a win, the other sees real cost. Both have a point — that's what makes it worth talking about.

[PAYOFF]
The real question isn't who's right. It's what happens if this becomes the norm.

[CTA]
Where do you land on this?"""

    meta = {
        "title": f"{title[:70]}",
        "description": f"Quick breakdown: {title}",
        "tags": ["shorts", "news", "debate", "trending"],
        "thumbnail_prompt": f"Bold vertical thumbnail for: {title}",
        "x_post": f"{title} — quick take. [LINK]",
    }
    return text, meta


def run_shorts_script_phase(db: Session, topics: List[Topic], run_date: str = None) -> List[Script]:
    """Run shorts script generation for a list of topics."""
    if not run_date:
        run_date = datetime.now().strftime("%Y-%m-%d")

    scripts = []
    for topic in topics:
        packet = db.query(ResearchPacket).filter(ResearchPacket.topic_id == topic.id).first()
        try:
            script = generate_shorts_script(topic, packet, db)
            if script:
                scripts.append(script)
                topic.status = "scripted"
        except Exception as e:
            logger.error(f"[shorts] Failed for topic {topic.id}: {e}")
            topic.status = "script_failed"

    db.commit()
    logger.info(f"[shorts] Done: {len(scripts)} shorts scripts generated.")
    return scripts


# ============================================================
# EVERGREEN DOCUMENTARY SCRIPT GENERATION
# ============================================================

def _generate_evergreen_script_text(topic: Topic, packet=None) -> str:
    """Generate a documentary-style narrative script from Ollama's own knowledge."""
    # For evergreen topics, Ollama's training knowledge is the primary source
    # Supplement with any research packet if available
    research_context = ""
    if packet and packet.summary:
        research_context = f"\nAdditional research context:\n{packet.summary[:800]}"

    system = """You are a documentary scriptwriter for a faceless YouTube channel.
You write high-quality narrative documentary scripts in the style of ColdFusion, MagnatesMedia, or Wendover Productions.

CRITICAL ACCURACY RULE:
Only state facts you know to be true and well-documented.
Use "reportedly", "according to accounts", "sources suggest" for anything uncertain.
Never invent quotes, specific figures, or dialogue you are not certain about.
If you are not sure of an exact number, give a range or say "roughly" — do not fabricate specifics.

Your scripts use narrative structure: protagonist, conflict, turning point, resolution.
Do NOT use Side A / Side B framing. Tell a story."""

    prompt = f"""Write a complete documentary script about: {topic.title}

Category: {topic.niche or 'documentary'}
Angle: {topic.angle or 'narrative documentary — protagonist, conflict, stakes, resolution'}
{research_context}

Use the documentary narrative structure:
[HOOK] — Start mid-story with the most dramatic moment
[THE OFFICIAL STORY] — 300-400 words. The public narrative, protagonist at their peak. Build them up fully.
[THE ANTAGONIST / THE PROBLEM] — 300-400 words. What was working against them. Develop the threat slowly.
[THE EVIDENCE] — 400-500 words. What actually happened. Key decisions, key people, key moments. Be specific.
[THE TURNING POINT] — 200-300 words. The moment everything changed. Make the reader feel it.
[THE STAKES / THE OUTCOME] — 300-400 words. Full consequences. Who won, who lost, what was destroyed.
[LESSONS / WHAT THIS MEANS] — 200-300 words. Deep, grounded takeaway. Not preachy — analytical.
[CTA] — 50-100 words. A real provocative question tied to the actual stakes.

REMINDER: Only use facts you are confident are accurate. Use hedging language for uncertain claims.
Target: 2500-2700 words. This is a full documentary, not a summary. Every section must be deeply developed.
Build tension slowly. Use specific details, dates, names, and context from your knowledge.
Do not rush. Do not summarize. Write every section as if the viewer has 20 minutes and wants the full story.
Do not stop early under any circumstances. If a section feels short, expand it further."""

    if not ollama_client.is_available():
        return ""

    # Section-by-section generation to hit 2500+ words
    sections = [
        ("[HOOK]", "Write ONLY the [HOOK] section. 3-4 sentences. Start mid-story with the most dramatic moment. No greetings."),
        ("[THE OFFICIAL STORY]", "Write ONLY the [THE OFFICIAL STORY] section. 350-450 words. Build the protagonist at their peak. Be specific and detailed."),
        ("[THE ANTAGONIST / THE PROBLEM]", "Write ONLY the [THE ANTAGONIST / THE PROBLEM] section. 350-450 words. What forces worked against them? Build the threat slowly with specific details."),
        ("[THE EVIDENCE]", "Write ONLY the [THE EVIDENCE] section. 450-550 words. Key facts, decisions, moments. Be specific. Use 'reportedly' and 'according to accounts' for uncertain details."),
        ("[THE TURNING POINT]", "Write ONLY the [THE TURNING POINT] section. 250-350 words. The exact moment everything changed. Make the reader feel the weight of it."),
        ("[THE STAKES / THE OUTCOME]", "Write ONLY the [THE STAKES / THE OUTCOME] section. 350-450 words. Full human cost. Who won, who lost, what was permanently destroyed."),
        ("[LESSONS / WHAT THIS MEANS]", "Write ONLY the [LESSONS / WHAT THIS MEANS] section. 250-300 words. Deep analytical takeaway. Not preachy. What does this teach us?"),
        ("[CTA]", "Write ONLY the [CTA] section. 2-3 sentences. One powerful specific question that makes the viewer want to comment."),
    ]

    parts = []
    total_words = 0

    for section_header, section_instruction in sections:
        context = "\n\n".join(parts[-2:]) if parts else ""
        section_prompt = f"""Documentary about: {topic.title}

Previous sections written so far (for context only):
{context[-800:] if context else "None yet."}

{section_instruction}

Write the {section_header} section now. Start with "{section_header}" as the header.
Do not write any other sections. Do not add introductions or conclusions outside this section."""

        try:
            result = ollama_client.generate(
                section_prompt, system=system, temperature=0.75,
                max_tokens=1200, timeout=300.0
            ).strip()
            wc = len(result.split())
            parts.append(result)
            total_words += wc
            logger.info(f"[evergreen] {section_header}: {wc} words (total: {total_words})")
        except Exception as e:
            logger.warning(f"[evergreen] Section {section_header} failed: {e}")
            parts.append(f"{section_header}\nThis section could not be generated.")

    combined = "\n\n".join(parts)
    logger.info(f"[evergreen] Final script: {len(combined.split())} words across {len(parts)} sections")
    return combined


def generate_evergreen_script(topic: Topic, packet, db: Session):
    """Generate and save an evergreen documentary script."""
    script_text = _generate_evergreen_script_text(topic, packet)
    wc = count_words(script_text)

    if wc < 400:
        logger.warning(f"[evergreen] Script too short ({wc}w), using placeholder")
        summary = packet.summary if packet else ""
        script_text = f"""[HOOK]
This is the story of {topic.title}. It is a story about decisions, consequences, and what happens when everything goes wrong at once.

[THE OFFICIAL STORY]
For a long time, the public version of this story looked very different from reality. From the outside, everything appeared to be working. The numbers looked good. The people in charge looked confident. Nobody was asking the hard questions yet.

[THE ANTAGONIST / THE PROBLEM]
But underneath the surface, serious problems were building. The forces working against this story's protagonist were not obvious at first — they rarely are. That is what makes this story worth telling.

[THE EVIDENCE]
What we know now tells a different story from what was presented publicly. The evidence, pieced together over time, reveals a pattern of decisions that led directly to the outcome.

[THE TURNING POINT]
There was a specific moment when everything changed. A decision, a revelation, or an event that made the previous course impossible to continue.

[THE STAKES / THE OUTCOME]
The consequences were real and lasting. Some people came out ahead. Others paid a significant price. That asymmetry is part of what makes this story matter.

[LESSONS / WHAT THIS MEANS]
The lessons here are not complicated. They rarely are in hindsight. The hard part is seeing them clearly when you are inside the story.

[CTA]
If you had been in a position to change the outcome here, what would you have done differently?"""
        status = "needs_review"
    else:
        status = "generated"

    meta = _generate_metadata(topic.title, script_text, topic.niche or "documentary")
    wc = count_words(script_text)

    script = Script(
        topic_id=topic.id,
        title=meta.get("title", topic.title)[:200] if meta else topic.title[:200],
        hook=script_text.split("[THE OFFICIAL STORY]")[0].replace("[HOOK]", "").strip()[:300],
        script_text=script_text,
        description=meta.get("description", "") if meta else "",
        tags_json=meta.get("tags", []) if meta else [],
        thumbnail_prompt=meta.get("thumbnail_prompt", "") if meta else "",
        x_post=meta.get("x_post", "") if meta else "",
        word_count=wc,
        status=status,
        format="longform",
    )
    db.add(script)
    db.flush()
    logger.info(f"[evergreen] Script created: {wc} words, status={status} | {topic.title[:60]}")
    return script

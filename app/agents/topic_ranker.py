"""
Topic Ranker Agent
Scores trend items and selects top N for content production.
"""
import pathlib
_REPO_ROOT = pathlib.Path(__file__).parent.parent.parent
import logging
import re
import yaml
from datetime import datetime
from typing import List, Optional
from sqlalchemy.orm import Session

from app.models import TrendItem, Topic, RunLog
from app.services.ollama_client import ollama_client
from app.settings import settings

logger = logging.getLogger(__name__)

SAFETY_RULES_PATH = _REPO_ROOT / "config" / "safety_rules.yaml"
PROMPT_PATH = _REPO_ROOT / "app" / "prompts" / "rank_topic.md"


def load_safety_rules() -> dict:
    try:
        with open(str(SAFETY_RULES_PATH)) as f:
            return yaml.safe_load(f)
    except Exception:
        return {}


def quick_safety_check(title: str, rules: dict) -> tuple[bool, str]:
    """Fast keyword-based safety check before calling LLM."""
    title_lower = title.lower()

    for banned in rules.get("banned_topics", []):
        if banned.lower() in title_lower:
            return False, f"Banned topic: {banned}"

    for rejected in rules.get("rejected_topics", []):
        if rejected.lower() in title_lower:
            return False, f"Rejected topic category: {rejected}"

    return True, ""


def score_topic_with_llm(title: str, source: str, query: str) -> Optional[dict]:
    """Use Ollama to score a topic."""
    try:
        with open(str(PROMPT_PATH)) as f:
            prompt_template = f.read()
    except Exception:
        prompt_template = "Evaluate this topic: {{title}}"

    prompt = (prompt_template
              .replace("{{title}}", title)
              .replace("{{source}}", source)
              .replace("{{query}}", query))

    if not ollama_client.is_available():
        logger.warning("[ranker] Ollama not available, using heuristic scoring.")
        return _heuristic_score(title, source)

    result = ollama_client.generate_json(prompt, temperature=0.2)
    if not result:
        return _heuristic_score(title, source)
    return result


def _heuristic_score(title: str, source: str) -> dict:
    """
    Score topics using evergreen documentary dimensions.
    Curiosity, conflict, retention, evergreen value, search demand.
    No hard bias toward AI/crypto/tech — those score only if genuinely compelling.
    """
    import re
    rules = load_safety_rules()
    title_lower = title.lower()

    # --- EVERGREEN SIGNALS ---
    # Topics with long-lasting search demand
    evergreen_kw = [
        "rise and fall", "why did", "how did", "what happened to", "the real story",
        "explained", "collapse", "failed", "died", "bankrupt", "scandal",
        "mystery", "unsolved", "disappeared", "forgotten", "abandoned",
        "survival", "rescue", "trapped", "stranded", "disaster",
        "fermi", "paradox", "universe", "galaxy", "aliens", "space",
        "what if", "could have", "secret history", "dark history",
        "the truth about", "nobody talks about", "you never knew",
        "documentary", "untold story", "inside story",
    ]

    # --- CURIOSITY / HOOK SIGNALS ---
    curiosity_kw = [
        "secret", "hidden", "nobody knows", "you won't believe", "shocking",
        "the real reason", "everyone missed", "mystery", "unexplained",
        "surprising", "incredible", "unbelievable", "strange", "bizarre",
        "the story of", "what really happened",
    ]

    # --- CONFLICT / STAKES SIGNALS ---
    conflict_kw = [
        "vs", "versus", "battle", "war", "fight", "collapse", "crash",
        "scandal", "fraud", "corruption", "betrayal", "lawsuit", "investigation",
        "accused", "ousted", "resigned", "fired", "bankrupt", "failed",
        "controversy", "outrage", "backlash", "divided", "dispute",
    ]

    # --- RETENTION SIGNALS ---
    # Topics with clear protagonist/antagonist/resolution — high watch time
    retention_kw = [
        "survivor", "escape", "rescue", "trapped", "missing", "found",
        "died", "born", "built", "destroyed", "saved", "lost",
        "rise", "fall", "journey", "story", "history of",
        "how one", "the man who", "the woman who", "the company that",
        "last days of", "inside the", "behind the",
    ]

    # --- PENALTIES ---
    # Low-value, non-evergreen, or risky content
    penalty_kw = [
        "today", "breaking", "live update", "just happened", "this week",
        "latest", "announces", "earnings report", "quarterly", "press release",
        "weather", "recipe", "horoscope", "birthday", "anniversary",
        "celebrity gossip", "dating", "marriage rumor",
        # Evergreen exceptions: don't penalize if combined with evergreen signals
    ]

    # --- DEPRIORITIZE categories ---
    deprioritize_kw = [
        "gpu benchmark", "model release", "token price", "chart analysis",
        "price prediction", "trading signal", "nft drop", "airdrop",
        "sports score", "game recap", "match result",
    ]

    def has_any(text, keywords):
        return any(k in text for k in keywords)

    def count_matches(text, keywords):
        return sum(1 for k in keywords if k in text)

    # Score each dimension 0.0-1.0
    evergreen_score = min(count_matches(title_lower, evergreen_kw) * 0.25, 1.0)
    curiosity_score = min(count_matches(title_lower, curiosity_kw) * 0.3, 1.0)
    conflict_score = min(count_matches(title_lower, conflict_kw) * 0.25, 1.0)
    retention_score = min(count_matches(title_lower, retention_kw) * 0.25, 1.0)

    # Evergreen source gets a base boost
    if "evergreen_" in source:
        evergreen_score = max(evergreen_score, 0.8)
        curiosity_score = max(curiosity_score, 0.5)
        retention_score = max(retention_score, 0.5)

    # Penalty
    penalty = 0.0
    if has_any(title_lower, penalty_kw) and not has_any(title_lower, evergreen_kw):
        penalty = 0.3
    if has_any(title_lower, deprioritize_kw):
        penalty = max(penalty, 0.4)

    # Monetization — evergreen documentary = high CPM
    monetization = 0.5
    if evergreen_score >= 0.5 or "evergreen_" in source:
        monetization = 0.85
    elif conflict_score >= 0.5:
        monetization = 0.70

    # Channel fit — documentary evergreen = max fit
    channel_fit = 0.3
    total_signal = evergreen_score + curiosity_score + retention_score
    if total_signal >= 1.5 or "evergreen_" in source:
        channel_fit = 0.95
    elif total_signal >= 0.8:
        channel_fit = 0.75
    elif total_signal >= 0.4:
        channel_fit = 0.55

    # Apply penalty
    channel_fit = max(channel_fit - penalty, 0.05)
    monetization = max(monetization - penalty, 0.05)

    # Search volume approximation
    search_kw = ["how", "why", "what", "explained", "story", "history", "real", "truth"]
    search_volume_score = min(count_matches(title_lower, search_kw) * 0.2, 0.9)
    search_volume_score = max(search_volume_score, 0.3 if "evergreen_" in source else 0.2)

    # Combined trend_strength
    trend_strength = (evergreen_score * 0.3 + curiosity_score * 0.3 +
                      conflict_score * 0.2 + retention_score * 0.2)
    trend_strength = max(trend_strength, 0.3 if "evergreen_" in source else 0.2)

    # Identify category
    from app.agents.evergreen_topic_generator import get_category_for_topic
    try:
        niche = get_category_for_topic(title)
    except Exception:
        niche = "general"

    # Safety check
    risk = 0.0
    for banned in rules.get("banned_topics", []):
        if banned.lower() in title_lower:
            risk = 1.0
            break

    return {
        "trend_strength": trend_strength,
        "monetization_score": monetization,
        "channel_fit": channel_fit,
        "low_competition_score": search_volume_score,
        "freshness_score": 0.9 if "evergreen_" in source else 0.5,
        "content_depth_score": 0.85 if channel_fit >= 0.75 else 0.5,
        "risk_score": risk,
        "niche": niche,
        "angle": f"Documentary storytelling: protagonist, conflict, stakes, resolution for: {title}",
        "reject_reason": "",
    }

def calculate_final_score(scores: dict) -> float:
    """Apply weighted scoring formula."""
    return (
        scores.get("trend_strength", 0) * 0.25
        + scores.get("monetization_score", 0) * 0.20
        + scores.get("channel_fit", 0) * 0.20
        + scores.get("low_competition_score", 0) * 0.15
        + scores.get("freshness_score", 0) * 0.10
        + scores.get("content_depth_score", 0) * 0.10
        - scores.get("risk_score", 0) * 0.30
    )


def run_topic_ranking(
    db: Session,
    trend_items: List[TrendItem],
    run_date: str = None,
    limit: int = None,
) -> List[Topic]:
    """
    Score trend items and select top N topics.
    Returns saved Topic objects.
    """
    if not run_date:
        run_date = datetime.now().strftime("%Y-%m-%d")

    if limit is None:
        limit = settings.DAILY_VIDEO_LIMIT

    rules = load_safety_rules()

    log = RunLog(run_date=run_date, phase="topic_ranking", status="started")
    db.add(log)
    db.flush()

    # Check for already-ranked topics today
    existing = db.query(Topic).filter(Topic.run_date == run_date).all()
    existing_trend_ids = {t.trend_id for t in existing if t.trend_id}
    logger.info(f"[ranker] {len(existing)} topics already ranked today.")

    scored_topics = []

    for trend in trend_items:
        if trend.id in existing_trend_ids:
            continue

        # Quick safety check
        safe, reason = quick_safety_check(trend.raw_title, rules)
        if not safe:
            logger.info(f"[ranker] Rejected '{trend.raw_title[:60]}': {reason}")
            # Save as rejected topic
            topic = Topic(
                trend_id=trend.id,
                title=trend.raw_title,
                niche="rejected",
                angle=reason,
                status="rejected",
                risk_score=1.0,
                final_score=0.0,
                run_date=run_date,
            )
            db.add(topic)
            continue

        # LLM scoring
        logger.info(f"[ranker] Scoring: {trend.raw_title[:80]}")
        scores = score_topic_with_llm(trend.raw_title, trend.source, trend.query or "")

        if not scores:
            scores = _heuristic_score(trend.raw_title, trend.source)

        final = calculate_final_score(scores)

        topic = Topic(
            trend_id=trend.id,
            title=trend.raw_title[:512],
            niche=scores.get("niche", "general")[:256],
            angle=scores.get("angle", "")[:512],
            status="scored",
            opportunity_score=scores.get("trend_strength", 0),
            monetization_score=scores.get("monetization_score", 0),
            competition_score=scores.get("low_competition_score", 0),
            risk_score=scores.get("risk_score", 0),
            final_score=final,
            run_date=run_date,
        )
        db.add(topic)
        scored_topics.append((final, topic))

    db.flush()

    # Sort by score and select top N
    scored_topics.sort(key=lambda x: x[0], reverse=True)
    selected = []

    already_selected_count = db.query(Topic).filter(
        Topic.run_date == run_date,
        Topic.status == "selected"
    ).count()

    slots_remaining = limit - already_selected_count
    logger.info(f"[ranker] Slots remaining today: {slots_remaining}")

    for final_score, topic in scored_topics[:slots_remaining]:
        if final_score > 0.1 and topic.risk_score < 0.7:
            topic.status = "selected"
            selected.append(topic)
            logger.info(f"[ranker] Selected: '{topic.title[:60]}' score={final_score:.3f}")

    db.flush()

    log.status = "completed"
    log.items_processed = len(selected)
    log.message = f"Ranked {len(scored_topics)} topics, selected {len(selected)}"

    logger.info(f"[ranker] Done. Selected {len(selected)} topics for today.")
    return selected


def get_selected_topics(db: Session, run_date: str = None) -> List[Topic]:
    """Get today's selected topics."""
    if not run_date:
        run_date = datetime.now().strftime("%Y-%m-%d")
    return db.query(Topic).filter(
        Topic.run_date == run_date,
        Topic.status == "selected"
    ).all()

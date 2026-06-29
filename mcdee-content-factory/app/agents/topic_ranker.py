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
    """Score a topic without LLM using keyword matching."""
    rules = load_safety_rules()
    title_lower = title.lower()

    preferred = rules.get("preferred_topics", [])
    # Tiered scoring — Tier 1 gets maximum boost
    tier1 = ["ai", "openai", "nvidia", "spacex", "elon musk", "elon", "tesla",
             "robotics", "bittensor", "crypto", "bitcoin", "btc", "xrp", "ethereum",
             "eth", "gpt", "chatgpt", "claude", "gemini", "llm", "chatgpt",
             "artificial intelligence", "chip", "semiconductor", "markets", "investing",
             "stock market", "fed ", "interest rate", "wall street"]
    tier2 = ["apple", "google", "microsoft", "amazon", "meta", "startup", "ipo",
             "earnings", "revenue", "acquisition", "merger", "launch", "breakthrough",
             "technology", "tech", "software", "hardware", "science", "discovery"]
    tier3 = ["nfl", "nba", "mlb", "ufc", "world cup", "super bowl", "championship",
             "celebrity", "movie", "film", "music", "album", "box office", "netflix"]
    penalty = ["diplomatic", "bilateral", "envoy", "migrant", "refugee", "shrine",
               "procession", "provincial", "municipal", "prefecture", "kidnapping",
               "sentenced", "verdict", "niche government", "regional dispute"]

    channel_fit = 0.3
    monetization = 0.4

    if any(k in title_lower for k in tier1):
        channel_fit = 0.95
        monetization = 0.90
    elif any(k in title_lower for k in tier2):
        channel_fit = 0.75
        monetization = 0.70
    elif any(k in title_lower for k in tier3):
        channel_fit = 0.55
        monetization = 0.55
    
    for k in penalty:
        if k in title_lower:
            channel_fit = max(channel_fit - 0.3, 0.05)
            monetization = max(monetization - 0.2, 0.05)
            break

    freshness = 0.7 if "reddit" in source or "rss" in source else 0.5
    risk = 0.0

    for banned in rules.get("banned_topics", []):
        if banned.lower() in title_lower:
            risk = 1.0
            break

    return {
        "trend_strength": 0.6,
        "monetization_score": monetization,
        "channel_fit": channel_fit,
        "low_competition_score": 0.5,
        "freshness_score": freshness,
        "content_depth_score": 0.6,
        "risk_score": risk,
        "niche": "ai-tech",
        "angle": f"Explaining {title} for infrastructure builders",
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

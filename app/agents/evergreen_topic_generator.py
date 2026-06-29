"""
Evergreen Topic Generator
Generates documentary-style topic ideas from Ollama's own knowledge.
Does NOT rely on news feeds — works even when feeds are quiet.
"""
import logging
import pathlib
import random
import yaml
from datetime import datetime
from typing import List, Dict
from sqlalchemy.orm import Session

from app.models import TrendItem
from app.services.ollama_client import ollama_client

logger = logging.getLogger(__name__)

_REPO_ROOT = pathlib.Path(__file__).parent.parent.parent
_CATEGORIES_FILE = _REPO_ROOT / "config" / "evergreen_categories.yaml"


def load_categories() -> dict:
    with open(str(_CATEGORIES_FILE)) as f:
        return yaml.safe_load(f)


def generate_topics_for_category(category_key: str, category: dict, count: int = 4) -> List[str]:
    """Ask Ollama to generate original evergreen topic ideas for a category."""
    examples = category.get("examples", [])[:6]
    description = category.get("description", "")
    keywords = category.get("keywords", [])[:6]

    examples_str = "\n".join(f"- {e}" for e in examples)
    keywords_str = ", ".join(keywords)

    system = """You are a documentary content strategist generating evergreen YouTube video topics.
Generate original topic ideas that would make compelling 8-12 minute documentary-style videos.
Each topic should have a built-in protagonist, conflict, and clear stakes.
Output ONLY a numbered list of topic titles — no explanations, no markdown, just the titles."""

    prompt = f"""Category: {category.get('display_name', category_key)}
Description: {description}
Keywords: {keywords_str}

Example topics already used (do NOT repeat these):
{examples_str}

Generate {count} NEW original topic ideas for this category that:
1. Have strong storytelling potential (protagonist, conflict, resolution)
2. Have evergreen search demand (people will search this for years)
3. Are factually grounded — based on real events or real scientific concepts
4. Would appeal to a general audience aged 18-45

Output exactly {count} numbered topic titles, nothing else:"""

    try:
        result = ollama_client.generate(prompt, system=system, temperature=0.8, max_tokens=400, timeout=180.0)
        if not result:
            return []

        lines = result.strip().split('\n')
        topics = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            # Remove numbering like "1. " or "1) "
            import re
            line = re.sub(r'^\d+[\.\)]\s*', '', line).strip()
            if len(line) > 10:
                topics.append(line)

        logger.info(f"[evergreen] Generated {len(topics)} topics for {category_key}")
        return topics[:count]

    except Exception as e:
        logger.warning(f"[evergreen] Generation failed for {category_key}: {e}")
        return []


def generate_all_evergreen_topics(db: Session, run_date: str = None, topics_per_category: int = 3) -> List[TrendItem]:
    """
    Generate evergreen topic ideas across all categories and save as TrendItems.
    These supplement (not replace) RSS feed items.
    """
    if not run_date:
        run_date = datetime.now().strftime("%Y-%m-%d")

    if not ollama_client.is_available():
        logger.warning("[evergreen] Ollama not available, skipping evergreen generation")
        return []

    cats = load_categories()
    categories = cats.get("categories", {})

    saved = []
    for cat_key, cat in categories.items():
        logger.info(f"[evergreen] Generating topics for: {cat.get('display_name', cat_key)}")
        topic_titles = generate_topics_for_category(cat_key, cat, count=topics_per_category)

        for title in topic_titles:
            # Check for duplicate
            existing = db.query(TrendItem).filter(
                TrendItem.raw_title == title,
                TrendItem.run_date == run_date,
            ).first()
            if existing:
                continue

            item = TrendItem(
                source=f"evergreen_{cat_key}",
                raw_title=title,
                query=cat_key,
                url="",
                score_raw=0.8,  # Evergreen topics start with a high base score
                run_date=run_date,
            )
            db.add(item)
            db.flush()
            saved.append(item)

    db.commit()
    logger.info(f"[evergreen] Total evergreen topics generated: {len(saved)}")
    return saved


def get_category_for_topic(title: str) -> str:
    """Identify which evergreen category a topic belongs to."""
    cats = load_categories()
    categories = cats.get("categories", {})
    title_lower = title.lower()

    best_cat = "general"
    best_score = 0

    for cat_key, cat in categories.items():
        score = 0
        for kw in cat.get("keywords", []):
            if kw.lower() in title_lower:
                score += 2
        for ex in cat.get("examples", []):
            # Check similarity by shared words
            ex_words = set(ex.lower().split())
            title_words = set(title_lower.split())
            overlap = len(ex_words & title_words)
            score += overlap

        if score > best_score:
            best_score = score
            best_cat = cat_key

    return best_cat

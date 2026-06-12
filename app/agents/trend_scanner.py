"""
Trend Scanner Agent
Pulls trends from Google Trends, Reddit, and RSS feeds.
Normalizes and stores to trend_items table.
"""
import logging
from datetime import datetime, timezone
from typing import List, Dict
from sqlalchemy.orm import Session

from app.models import TrendItem, RunLog
from app.db import get_db
from app.services.rss_client import fetch_all_rss
from app.services.pytrends_client import fetch_google_trends
from app.services.reddit_client import fetch_reddit_trends

logger = logging.getLogger(__name__)


def run_trend_scan(db: Session, run_date: str = None) -> List[TrendItem]:
    """
    Collect trends from all sources and store in DB.
    Skips duplicates by raw_title + run_date.
    Returns list of saved TrendItem objects.
    """
    if not run_date:
        run_date = datetime.now().strftime("%Y-%m-%d")

    log = RunLog(run_date=run_date, phase="trend_scan", status="started")
    db.add(log)
    db.flush()

    all_raw: List[Dict] = []

    # 1. RSS feeds (always available, no auth required)
    logger.info("[trend_scanner] Fetching RSS feeds...")
    rss_items = fetch_all_rss()
    all_raw.extend(rss_items)

    # 2. Google Trends
    logger.info("[trend_scanner] Fetching Google Trends...")
    try:
        gt_items = fetch_google_trends()
        all_raw.extend(gt_items)
    except Exception as e:
        logger.warning(f"[trend_scanner] Google Trends failed: {e}")

    # 3. Reddit
    logger.info("[trend_scanner] Fetching Reddit...")
    try:
        reddit_items = fetch_reddit_trends()
        all_raw.extend(reddit_items)
    except Exception as e:
        logger.warning(f"[trend_scanner] Reddit failed: {e}")

    # Deduplicate by title
    seen_titles = set()
    unique_raw = []
    for item in all_raw:
        title_key = item["raw_title"].lower().strip()[:100]
        if title_key not in seen_titles:
            seen_titles.add(title_key)
            unique_raw.append(item)

    # Check existing items for today
    existing = db.query(TrendItem).filter(TrendItem.run_date == run_date).all()
    existing_titles = {t.raw_title.lower()[:100] for t in existing}

    saved = []
    for item in unique_raw:
        title_key = item["raw_title"].lower().strip()[:100]
        if title_key in existing_titles:
            continue  # Skip duplicate

        trend = TrendItem(
            source=item.get("source", "unknown"),
            raw_title=item["raw_title"][:512],
            query=item.get("query", item["raw_title"])[:256],
            url=item.get("url", "")[:1024],
            score_raw=float(item.get("score_raw", 0.5)),
            run_date=run_date,
        )
        db.add(trend)
        saved.append(trend)

    db.flush()

    log.status = "completed"
    log.items_processed = len(saved)
    log.message = f"Saved {len(saved)} new trend items from {len(all_raw)} raw"

    logger.info(f"[trend_scanner] Done: {len(saved)} new items saved.")
    return saved


def get_todays_trends(db: Session, run_date: str = None) -> List[TrendItem]:
    """Fetch today's trend items from DB."""
    if not run_date:
        run_date = datetime.now().strftime("%Y-%m-%d")
    return db.query(TrendItem).filter(TrendItem.run_date == run_date).all()

"""
RSS feed client - pulls headlines from configured feeds.
"""
import pathlib
import logging
from typing import List, Dict
import feedparser
import yaml

_REPO_ROOT = pathlib.Path(__file__).parent.parent.parent
_DEFAULT_CONFIG = str(_REPO_ROOT / "config" / "trend_sources.yaml")

logger = logging.getLogger(__name__)


def load_rss_sources(config_path: str = None) -> List[Dict]:
    path = config_path or _DEFAULT_CONFIG
    with open(path, "r") as f:
        config = yaml.safe_load(f)
    return config.get("rss_feeds", [])


def fetch_rss_feed(url: str, name: str = "", weight: float = 1.0, limit: int = 20) -> List[Dict]:
    """Fetch entries from a single RSS feed."""
    try:
        feed = feedparser.parse(url)
        items = []
        for entry in feed.entries[:limit]:
            title = entry.get("title", "").strip()
            link = entry.get("link", "")
            published = entry.get("published", "")
            summary = entry.get("summary", "")[:500]
            if not title:
                continue
            items.append({
                "source": f"rss_{name.lower().replace(' ', '_')}",
                "raw_title": title,
                "query": title,
                "url": link,
                "summary": summary,
                "published": published,
                "score_raw": weight,
            })
        logger.info(f"[rss] {name}: {len(items)} items")
        return items
    except Exception as e:
        logger.warning(f"[rss] Failed to fetch {name} ({url}): {e}")
        return []


def fetch_all_rss(config_path: str = None) -> List[Dict]:
    """Fetch all configured RSS feeds."""
    sources = load_rss_sources(config_path)
    all_items = []
    for source in sources:
        items = fetch_rss_feed(
            url=source["url"],
            name=source.get("name", ""),
            weight=source.get("weight", 1.0),
        )
        all_items.extend(items)
    logger.info(f"[rss] Total RSS items: {len(all_items)}")
    return all_items

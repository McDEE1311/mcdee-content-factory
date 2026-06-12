"""
Google Trends client via pytrends.
Falls back gracefully if rate-limited or blocked.
"""
import pathlib
import logging
import time
from typing import List, Dict
import yaml

_REPO_ROOT = pathlib.Path(__file__).parent.parent.parent
_DEFAULT_CONFIG = str(_REPO_ROOT / "config" / "trend_sources.yaml")

logger = logging.getLogger(__name__)


def fetch_google_trends(config_path: str = None) -> List[Dict]:
    try:
        from pytrends.request import TrendReq
    except ImportError:
        logger.warning("[pytrends] pytrends not installed, skipping.")
        return []

    path = config_path or _DEFAULT_CONFIG
    with open(path) as f:
        config = yaml.safe_load(f)

    gt_config = config.get("google_trends", {})
    if not gt_config.get("enabled", True):
        return []

    geo = gt_config.get("geo", "US")
    items = []

    try:
        pytrends = TrendReq(hl="en-US", tz=360, timeout=(10, 25))
        try:
            trending = pytrends.trending_searches(pn="united_states")
            for title in trending[0].tolist()[:30]:
                items.append({
                    "source": "google_trends_daily",
                    "raw_title": str(title),
                    "query": str(title),
                    "url": f"https://trends.google.com/trends/explore?q={title}&geo={geo}",
                    "score_raw": 1.0,
                })
            logger.info(f"[pytrends] Daily trending: {len(items)} items")
            time.sleep(2)
        except Exception as e:
            logger.warning(f"[pytrends] Daily trending failed: {e}")

        for kw in gt_config.get("categories", [])[:5]:
            try:
                pytrends.build_payload([kw], timeframe="now 1-d", geo=geo)
                related = pytrends.related_queries()
                if kw in related and related[kw].get("top") is not None:
                    for _, row in related[kw]["top"].head(5).iterrows():
                        query = str(row.get("query", ""))
                        if query:
                            items.append({
                                "source": "google_trends_related",
                                "raw_title": query,
                                "query": query,
                                "url": f"https://trends.google.com/trends/explore?q={query}&geo={geo}",
                                "score_raw": float(row.get("value", 50)) / 100.0,
                            })
                time.sleep(1.5)
            except Exception as e:
                logger.warning(f"[pytrends] Related for '{kw}' failed: {e}")
                time.sleep(3)
    except Exception as e:
        logger.warning(f"[pytrends] General error: {e}")

    logger.info(f"[pytrends] Total items: {len(items)}")
    return items

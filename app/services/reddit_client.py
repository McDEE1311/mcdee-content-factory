"""
Reddit client via PRAW.
Skips cleanly if credentials are not configured.
"""
import pathlib
import logging
from typing import List, Dict
import yaml

_REPO_ROOT = pathlib.Path(__file__).parent.parent.parent
_DEFAULT_CONFIG = str(_REPO_ROOT / "config" / "trend_sources.yaml")

logger = logging.getLogger(__name__)


def fetch_reddit_trends(config_path: str = None) -> List[Dict]:
    from app.settings import settings
    if not settings.reddit_enabled:
        logger.info("[reddit] Reddit credentials not configured, skipping.")
        return []
    try:
        import praw
    except ImportError:
        logger.warning("[reddit] praw not installed, skipping.")
        return []

    path = config_path or _DEFAULT_CONFIG
    with open(path) as f:
        config = yaml.safe_load(f)

    try:
        reddit = praw.Reddit(
            client_id=settings.REDDIT_CLIENT_ID,
            client_secret=settings.REDDIT_CLIENT_SECRET,
            user_agent=settings.REDDIT_USER_AGENT,
        )
        reddit.read_only = True
    except Exception as e:
        logger.warning(f"[reddit] Auth failed: {e}")
        return []

    items = []
    for sub_config in config.get("reddit_subreddits", []):
        sub_name = sub_config["name"]
        weight = sub_config.get("weight", 1.0)
        limit = sub_config.get("limit", 20)
        try:
            posts = list(reddit.subreddit(sub_name).hot(limit=limit))
            for post in posts:
                if post.stickied or post.score < 10:
                    continue
                items.append({
                    "source": f"reddit_{sub_name.lower()}",
                    "raw_title": post.title,
                    "query": post.title,
                    "url": f"https://reddit.com{post.permalink}",
                    "score_raw": min(post.score / 1000.0, 1.0) * weight,
                })
            logger.info(f"[reddit] r/{sub_name}: {len(posts)} posts")
        except Exception as e:
            logger.warning(f"[reddit] r/{sub_name} failed: {e}")

    logger.info(f"[reddit] Total items: {len(items)}")
    return items

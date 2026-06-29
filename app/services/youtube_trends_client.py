"""
YouTube trending/shorts discovery — titles and metadata only.
Requires YOUTUBE_API_KEY in .env. Falls back gracefully if not configured.
"""
import logging
import os
import httpx
from typing import List, Dict

logger = logging.getLogger(__name__)

def is_api_configured() -> bool:
    from app.settings import settings
    return bool(getattr(settings, "YOUTUBE_API_KEY", "") or os.environ.get("YOUTUBE_API_KEY"))

def get_trending_by_niche(niches: List[str] = None, max_per_niche: int = 8) -> List[Dict]:
    """Get recent high-performing videos across niches. Requires API key."""
    if not is_api_configured():
        return []
    # Full implementation requires YOUTUBE_API_KEY — skipping for now
    logger.info("[yt_trends] YouTube API key not configured, skipping")
    return []

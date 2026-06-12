"""
X (Twitter) API client stub.
Full implementation in Phase 4.
"""
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class XClient:
    def is_available(self) -> bool:
        from app.settings import settings
        return settings.x_api_enabled

    def post_tweet(self, text: str) -> Optional[str]:
        """STUB: log post, do not actually post."""
        logger.info(f"[x] STUB: Would post tweet: {text[:100]}...")
        return None

    def post_thread(self, tweets: list[str]) -> list[Optional[str]]:
        """STUB: log thread."""
        logger.info(f"[x] STUB: Would post thread ({len(tweets)} posts)")
        return [None] * len(tweets)


x_client = XClient()

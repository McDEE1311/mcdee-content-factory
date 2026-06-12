"""
YouTube API client stub.
Full implementation in Phase 4 after manual review period.
"""
import json
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)


class YouTubeClient:
    def __init__(self):
        self.initialized = False

    def is_available(self) -> bool:
        from app.settings import settings
        return settings.youtube_api_enabled

    def upload_video(
        self,
        video_path: str,
        title: str,
        description: str,
        tags: list,
        thumbnail_path: Optional[str] = None,
        scheduled_time: Optional[str] = None,
        category_id: str = "28",  # Science & Technology
    ) -> Optional[str]:
        """
        Upload a video to YouTube.
        STUB: prints upload package info, does not actually upload.
        Returns a fake video ID for now.
        """
        logger.info(f"[youtube] STUB: Would upload '{title}'")
        logger.info(f"[youtube]   file: {video_path}")
        logger.info(f"[youtube]   tags: {tags[:5]}")
        if scheduled_time:
            logger.info(f"[youtube]   scheduled: {scheduled_time}")
        return None  # No actual upload yet


youtube_client = YouTubeClient()

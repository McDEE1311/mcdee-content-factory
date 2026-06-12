"""
YouTube Publisher Agent (STUB)
Reads upload packages and simulates what would be posted.
Real YouTube OAuth upload is Phase 4.
"""
import json
import logging
import os
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.orm import Session

from app.models import PublishQueue, Video, Script, Topic
from app.settings import settings

logger = logging.getLogger(__name__)


def publish_video(queue_entry: PublishQueue, db: Session) -> bool:
    """
    Publish a video to YouTube.
    STUB: prints package info. Does not upload.
    """
    video = db.query(Video).filter(Video.id == queue_entry.video_id).first()
    if not video:
        logger.error(f"[youtube] No video found for queue entry {queue_entry.id}")
        return False

    script = db.query(Script).filter(Script.topic_id == video.topic_id).first()

    # Read metadata from upload package
    metadata_path = os.path.join(video.package_path or "", "metadata.json")
    metadata = {}
    if metadata_path and os.path.exists(metadata_path):
        with open(metadata_path) as f:
            metadata = json.load(f)

    title = metadata.get("title") or (script.title if script else "Untitled")
    video_file = os.path.join(video.package_path or "", "video.mp4") if video.package_path else video.video_path

    if not settings.AUTO_APPROVE:
        logger.info(f"[youtube] MANUAL MODE: Would upload '{title}'")
        logger.info(f"[youtube]   package: {video.package_path}")
        logger.info(f"[youtube]   scheduled: {queue_entry.scheduled_at}")
        # Mark as ready for manual action
        queue_entry.status = "awaiting_manual_upload"
        db.flush()
        return True

    # AUTO mode (Phase 4 — not yet implemented)
    logger.warning("[youtube] AUTO_APPROVE=true but YouTube API not yet configured. Skipping.")
    queue_entry.status = "failed"
    queue_entry.error = "YouTube API not configured"
    db.flush()
    return False


def run_publish_queue(db: Session) -> dict:
    """Process all scheduled YouTube publish queue entries."""
    now = datetime.now(timezone.utc)
    due_entries = db.query(PublishQueue).filter(
        PublishQueue.platform == "youtube",
        PublishQueue.status.in_(["approved", "scheduled"]),
        PublishQueue.scheduled_at <= now,
    ).all()

    results = {"attempted": 0, "success": 0, "failed": 0}
    for entry in due_entries:
        results["attempted"] += 1
        try:
            ok = publish_video(entry, db)
            if ok:
                results["success"] += 1
            else:
                results["failed"] += 1
        except Exception as e:
            logger.error(f"[youtube] Error for queue {entry.id}: {e}")
            entry.status = "failed"
            entry.error = str(e)
            results["failed"] += 1

    db.commit()
    return results

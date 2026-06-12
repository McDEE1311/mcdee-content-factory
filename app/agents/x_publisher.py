"""
X (Twitter) Publisher Agent (STUB)
Posts matching content to X after YouTube publish.
Phase 4 full implementation.
"""
import logging
import os
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from app.models import PublishQueue, Video, Script
from app.settings import settings

logger = logging.getLogger(__name__)


def publish_x_post(queue_entry: PublishQueue, youtube_url: str, db: Session) -> bool:
    """Post to X. STUB: logs only."""
    video = db.query(Video).filter(Video.id == queue_entry.video_id).first()
    if not video:
        return False

    # Read x_post.txt from package
    x_post_path = os.path.join(video.package_path or "", "x_post.txt")
    x_text = ""
    if x_post_path and os.path.exists(x_post_path):
        with open(x_post_path) as f:
            x_text = f.read().strip()

    if not x_text:
        script = db.query(Script).filter(Script.topic_id == video.topic_id).first()
        x_text = f"New video: {script.title if script else 'Latest brief'} {youtube_url}"

    # Replace placeholder URL
    x_text = x_text.replace("[LINK]", youtube_url)

    if not settings.AUTO_APPROVE:
        logger.info(f"[x] MANUAL MODE: Would post:\n{x_text}")
        queue_entry.status = "awaiting_manual_post"
        db.flush()
        return True

    logger.warning("[x] AUTO_APPROVE=true but X API not configured. Skipping.")
    queue_entry.status = "failed"
    queue_entry.error = "X API not configured"
    db.flush()
    return False


def run_x_publish_queue(db: Session) -> dict:
    """Process scheduled X posts."""
    now = datetime.now(timezone.utc)
    due_entries = db.query(PublishQueue).filter(
        PublishQueue.platform == "x",
        PublishQueue.status.in_(["approved", "scheduled"]),
        PublishQueue.scheduled_at <= now,
    ).all()

    results = {"attempted": 0, "success": 0, "failed": 0}
    for entry in due_entries:
        results["attempted"] += 1
        try:
            video = db.query(Video).filter(Video.id == entry.video_id).first()
            yt_post = db.query(PublishQueue).filter(
                PublishQueue.video_id == entry.video_id,
                PublishQueue.platform == "youtube",
                PublishQueue.platform_post_id.isnot(None),
            ).first()
            youtube_url = f"https://youtube.com/watch?v={yt_post.platform_post_id}" if yt_post else "[LINK]"
            ok = publish_x_post(entry, youtube_url, db)
            if ok:
                results["success"] += 1
            else:
                results["failed"] += 1
        except Exception as e:
            logger.error(f"[x] Error for queue {entry.id}: {e}")
            results["failed"] += 1

    db.commit()
    return results

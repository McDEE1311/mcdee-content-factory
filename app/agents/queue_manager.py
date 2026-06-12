"""
Queue Manager
Schedules approved videos for publishing with even spacing.
"""
import logging
import pytz
from datetime import datetime, timedelta
from typing import List
from sqlalchemy.orm import Session

from app.models import Video, PublishQueue, Topic
from app.settings import settings

logger = logging.getLogger(__name__)


def calculate_schedule(
    n_videos: int,
    run_date: str = None,
    start_hour: int = None,
    end_hour: int = None,
    tz_name: str = None,
) -> List[datetime]:
    """
    Calculate evenly-spaced publish times for N videos.
    Returns list of UTC datetimes.
    """
    if start_hour is None:
        start_hour = settings.UPLOAD_START_HOUR
    if end_hour is None:
        end_hour = settings.UPLOAD_END_HOUR
    if tz_name is None:
        tz_name = settings.LOCAL_TIMEZONE
    if run_date is None:
        run_date = datetime.now().strftime("%Y-%m-%d")

    tz = pytz.timezone(tz_name)
    date = datetime.strptime(run_date, "%Y-%m-%d")

    window_minutes = (end_hour - start_hour) * 60
    if n_videos <= 0:
        return []
    if n_videos == 1:
        gap = 0
    else:
        gap = window_minutes // (n_videos - 1)

    times = []
    for i in range(n_videos):
        minutes_offset = i * gap
        local_dt = tz.localize(datetime(
            date.year, date.month, date.day,
            start_hour, 0, 0
        ) + timedelta(minutes=minutes_offset))
        utc_dt = local_dt.astimezone(pytz.utc)
        times.append(utc_dt)

    return times


def queue_approved_videos(
    db: Session,
    topics: List[Topic],
    run_date: str = None,
) -> List[PublishQueue]:
    """
    Create PublishQueue entries for approved videos.
    Respects AUTO_APPROVE setting.
    """
    if not run_date:
        run_date = datetime.now().strftime("%Y-%m-%d")

    # Find approved videos not yet queued
    approved_videos = []
    for topic in topics:
        video = db.query(Video).filter(
            Video.topic_id == topic.id,
            Video.status == "approved",
        ).first()
        if not video:
            continue

        already_queued = db.query(PublishQueue).filter(
            PublishQueue.video_id == video.id,
        ).first()
        if not already_queued:
            approved_videos.append(video)

    if not approved_videos:
        logger.info("[queue] No new approved videos to queue.")
        return []

    # Enforce daily limit
    already_scheduled = db.query(PublishQueue).join(Video).filter(
        Video.run_date == run_date,
    ).count()

    slots = min(
        settings.DAILY_VIDEO_LIMIT - already_scheduled,
        len(approved_videos)
    )

    if slots <= 0:
        logger.warning("[queue] Daily limit already reached.")
        return []

    videos_to_queue = approved_videos[:slots]
    schedule_times = calculate_schedule(len(videos_to_queue), run_date=run_date)

    initial_status = "approved" if settings.AUTO_APPROVE else "scheduled"

    queued = []
    for video, scheduled_at in zip(videos_to_queue, schedule_times):
        entry = PublishQueue(
            video_id=video.id,
            platform="youtube",
            scheduled_at=scheduled_at,
            status=initial_status,
        )
        db.add(entry)
        queued.append(entry)

        # Also queue X post
        x_entry = PublishQueue(
            video_id=video.id,
            platform="x",
            scheduled_at=scheduled_at + timedelta(minutes=5),
            status=initial_status,
        )
        db.add(x_entry)

        video.status = "queued"
        logger.info(f"[queue] Queued video {video.id} for {scheduled_at.strftime('%H:%M UTC')}")

    db.flush()

    if not settings.AUTO_APPROVE:
        logger.info(f"[queue] {len(queued)} videos queued. AUTO_APPROVE=false — manual approval required.")
    else:
        logger.info(f"[queue] {len(queued)} videos queued for auto-publish.")

    return queued

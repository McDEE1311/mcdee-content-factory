"""
Render Queue Worker
Processes any topics that have scripts but no rendered video yet.
Run continuously under PM2 or as a cron job.
"""
import logging
import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler("logs/render_queue.log")],
)
logger = logging.getLogger("render_queue")

POLL_INTERVAL = 60  # seconds


def process_render_queue():
    from app.db import get_db, init_db
    from app.models import Topic, Script, Video
    from app.agents.thumbnail_agent import run_thumbnail_phase
    from app.agents.voice_agent import run_voice_phase
    from app.agents.video_agent import run_video_phase
    from app.agents.quality_agent import run_quality_phase
    from app.agents.queue_manager import queue_approved_videos
    from datetime import datetime

    init_db()

    while True:
        try:
            run_date = datetime.now().strftime("%Y-%m-%d")
            logger.info(f"[render_queue] Checking for pending topics...")

            with get_db() as db:
                pending = db.query(Topic).filter(
                    Topic.run_date == run_date,
                    Topic.status.in_(["scripted", "researched"]),
                ).all()

                if pending:
                    logger.info(f"[render_queue] {len(pending)} topics to process.")
                    run_thumbnail_phase(db, pending, run_date=run_date)
                    run_voice_phase(db, pending, run_date=run_date)
                    run_video_phase(db, pending, run_date=run_date, render_video=True)
                    run_quality_phase(db, pending)
                    queue_approved_videos(db, pending, run_date=run_date)
                else:
                    logger.info("[render_queue] Nothing pending.")

        except Exception as e:
            logger.error(f"[render_queue] Error: {e}")

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    os.makedirs("logs", exist_ok=True)
    process_render_queue()

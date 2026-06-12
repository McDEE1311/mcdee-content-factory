"""
Publish Queue Worker
Monitors the publish queue and fires uploads when scheduled time arrives.
"""
import logging
import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler("logs/publish_queue.log")],
)
logger = logging.getLogger("publish_queue")

POLL_INTERVAL = 120  # seconds


def run_publish_loop():
    from app.db import get_db, init_db
    from app.agents.youtube_publisher import run_publish_queue
    from app.agents.x_publisher import run_x_publish_queue

    init_db()

    while True:
        try:
            with get_db() as db:
                yt_results = run_publish_queue(db)
                x_results = run_x_publish_queue(db)
                if yt_results["attempted"] > 0:
                    logger.info(f"[publish_queue] YouTube: {yt_results}")
                if x_results["attempted"] > 0:
                    logger.info(f"[publish_queue] X: {x_results}")
        except Exception as e:
            logger.error(f"[publish_queue] Error: {e}")

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    os.makedirs("logs", exist_ok=True)
    run_publish_loop()

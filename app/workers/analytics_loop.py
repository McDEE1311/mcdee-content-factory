"""
Analytics Loop Worker
Runs every few hours to collect analytics from published videos.
"""
import logging
import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler("logs/analytics_loop.log")],
)
logger = logging.getLogger("analytics_loop")

POLL_INTERVAL = 3600 * 4  # every 4 hours


def run_analytics_loop():
    from app.db import get_db, init_db
    from app.agents.analytics_agent import collect_analytics

    init_db()

    while True:
        try:
            with get_db() as db:
                results = collect_analytics(db)
                logger.info(f"[analytics_loop] Collected: {results}")
        except Exception as e:
            logger.error(f"[analytics_loop] Error: {e}")

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    os.makedirs("logs", exist_ok=True)
    run_analytics_loop()

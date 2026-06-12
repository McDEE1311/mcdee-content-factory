"""
Daily Run Worker
Orchestrates the full daily pipeline:
Trend Scan → Rank → Research → Script → Thumbnail → Voice → Video → Quality → Queue

Usage:
  python3 -m app.workers.daily_run              # Full run
  python3 -m app.workers.daily_run --dry-run    # Script generation only, no render
  python3 -m app.workers.daily_run --phase scan # Run specific phase
"""
import argparse
import logging
import sys
import os
from datetime import datetime

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(f"logs/daily_run_{datetime.now().strftime('%Y%m%d')}.log"),
    ],
)
logger = logging.getLogger("daily_run")


def run_pipeline(dry_run: bool = False, run_date: str = None, phases: list = None):
    from app.db import get_db, init_db
    from app.agents.trend_scanner import run_trend_scan, get_todays_trends
    from app.agents.topic_ranker import run_topic_ranking, get_selected_topics
    from app.agents.research_agent import run_research_phase
    from app.agents.script_agent import run_script_phase
    from app.agents.thumbnail_agent import run_thumbnail_phase
    from app.agents.voice_agent import run_voice_phase
    from app.agents.video_agent import run_video_phase
    from app.agents.quality_agent import run_quality_phase
    from app.agents.queue_manager import queue_approved_videos
    from app.settings import settings

    init_db()

    if not run_date:
        run_date = datetime.now().strftime("%Y-%m-%d")

    all_phases = phases or ["scan", "rank", "research", "script", "assets", "video", "quality", "queue"]
    render_video = not dry_run

    logger.info(f"=== McDEE Daily Run | {run_date} | dry_run={dry_run} ===")
    logger.info(f"Phases: {all_phases}")
    logger.info(f"Daily limit: {settings.DAILY_VIDEO_LIMIT} | AUTO_APPROVE: {settings.AUTO_APPROVE}")

    with get_db() as db:

        # PHASE 1: Trend Scan
        if "scan" in all_phases:
            logger.info("--- Phase: Trend Scan ---")
            trend_items = run_trend_scan(db, run_date=run_date)
            logger.info(f"Trends collected: {len(trend_items)}")
        else:
            from app.agents.trend_scanner import get_todays_trends
            trend_items = get_todays_trends(db, run_date=run_date)

        if not trend_items:
            logger.warning("No trend items found. Check sources.")
            # Still proceed with existing trends from today
            from app.models import TrendItem
            trend_items = db.query(TrendItem).filter(TrendItem.run_date == run_date).all()

        # PHASE 2: Topic Ranking
        if "rank" in all_phases:
            logger.info("--- Phase: Topic Ranking ---")
            selected_topics = run_topic_ranking(db, trend_items, run_date=run_date)
            logger.info(f"Topics selected: {len(selected_topics)}")
        else:
            selected_topics = get_selected_topics(db, run_date=run_date)

        if not selected_topics:
            logger.warning("No topics selected. Exiting.")
            return

        # PHASE 3: Research
        if "research" in all_phases:
            logger.info("--- Phase: Research ---")
            packets = run_research_phase(db, selected_topics, run_date=run_date)
            logger.info(f"Research packets: {len(packets)}")

        # PHASE 4: Script Generation
        if "script" in all_phases:
            logger.info("--- Phase: Script Generation ---")
            scripts = run_script_phase(db, selected_topics, run_date=run_date)
            logger.info(f"Scripts generated: {len(scripts)}")

            # Print summary for dry run
            if dry_run:
                for s in scripts:
                    logger.info(f"  Script: {s.title[:80]} ({s.word_count} words, status={s.status})")

        # PHASE 5: Assets (thumbnail + voice)
        if "assets" in all_phases and not dry_run:
            logger.info("--- Phase: Assets (Thumbnail + Voice) ---")
            thumb_results = run_thumbnail_phase(db, selected_topics, run_date=run_date)
            voice_results = run_voice_phase(db, selected_topics, run_date=run_date)
            logger.info(f"Thumbnails: {sum(1 for v in thumb_results.values() if v)}")
            logger.info(f"Voiceovers: {sum(1 for v in voice_results.values() if v.get('real_audio'))}")

        # PHASE 6: Video / Upload Packages
        if "video" in all_phases:
            logger.info(f"--- Phase: Video / Package (render={render_video}) ---")
            packages = run_video_phase(
                db, selected_topics,
                run_date=run_date,
                render_video=render_video,
            )
            logger.info(f"Upload packages: {len(packages)}")
            for p in packages:
                logger.info(f"  Package: {p}")

        # PHASE 7: Quality Check
        if "quality" in all_phases:
            logger.info("--- Phase: Quality Check ---")
            quality_results = run_quality_phase(db, selected_topics)
            logger.info(f"Quality: approved={quality_results['approved']} rejected={quality_results['rejected']}")

        # PHASE 8: Queue
        if "queue" in all_phases and not dry_run:
            logger.info("--- Phase: Queue Manager ---")
            queued = queue_approved_videos(db, selected_topics, run_date=run_date)
            logger.info(f"Queued: {len(queued)} entries")

    logger.info(f"=== Daily Run Complete | {run_date} ===")
    logger.info(f"Output packages: outputs/upload_packages/{run_date}/")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="McDEE Content Factory Daily Run")
    parser.add_argument("--dry-run", action="store_true", help="Run script phase only, no render/queue")
    parser.add_argument("--date", type=str, help="Override run date YYYY-MM-DD")
    parser.add_argument("--phase", type=str, nargs="+", help="Run specific phases only")
    args = parser.parse_args()

    os.makedirs("logs", exist_ok=True)

    run_pipeline(
        dry_run=args.dry_run,
        run_date=args.date,
        phases=args.phase,
    )

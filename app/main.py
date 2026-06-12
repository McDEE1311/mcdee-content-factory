"""
McDEE Content Factory - Main FastAPI Application
"""
import os
import platform
from datetime import datetime, timezone
from fastapi import FastAPI, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.db import get_db_dependency, init_db
from app.settings import settings

# Initialize DB on startup
init_db()

app = FastAPI(
    title="McDEE Content Factory",
    description="Autonomous trend-to-video content pipeline",
    version="0.1.0",
)


@app.get("/health")
def health_check(db: Session = Depends(get_db_dependency)):
    """System health check endpoint."""
    db_ok = False
    try:
        db.execute(text("SELECT 1"))
        db_ok = True
    except Exception as e:
        db_status = str(e)

    ollama_ok = False
    try:
        import httpx
        r = httpx.get(f"{settings.OLLAMA_BASE_URL}/api/tags", timeout=3.0)
        ollama_ok = r.status_code == 200
    except Exception:
        pass

    return JSONResponse({
        "status": "ok",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "0.1.0",
        "env": settings.APP_ENV,
        "db": "ok" if db_ok else "error",
        "ollama": "ok" if ollama_ok else "unavailable",
        "ollama_model": settings.OLLAMA_MODEL,
        "auto_approve": settings.AUTO_APPROVE,
        "daily_limit": settings.DAILY_VIDEO_LIMIT,
        "upload_window": f"{settings.UPLOAD_START_HOUR}:00 - {settings.UPLOAD_END_HOUR}:00 {settings.LOCAL_TIMEZONE}",
        "features": {
            "reddit": settings.reddit_enabled,
            "youtube_api": settings.youtube_api_enabled,
            "x_api": settings.x_api_enabled,
        }
    })


@app.get("/status")
def pipeline_status(db: Session = Depends(get_db_dependency)):
    """Today's pipeline status."""
    today = datetime.now().strftime("%Y-%m-%d")
    from app.models import TrendItem, Topic, Script, Video, PublishQueue

    trends_today = db.query(TrendItem).filter(TrendItem.run_date == today).count()
    topics_today = db.query(Topic).filter(Topic.run_date == today).count()
    scripts_today = db.query(Script).join(Topic).filter(Topic.run_date == today).count()
    videos_today = db.query(Video).filter(Video.run_date == today).count()
    queued_today = db.query(PublishQueue).join(Video).filter(
        Video.run_date == today,
        PublishQueue.status == "scheduled"
    ).count()

    return JSONResponse({
        "date": today,
        "trends_collected": trends_today,
        "topics_ranked": topics_today,
        "scripts_generated": scripts_today,
        "videos_rendered": videos_today,
        "queued_for_publish": queued_today,
        "daily_limit": settings.DAILY_VIDEO_LIMIT,
    })


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.APP_HOST,
        port=settings.APP_PORT,
        reload=settings.is_dev,
    )

"""
SQLAlchemy ORM models for all database tables.
"""
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, Text,
    DateTime, ForeignKey, JSON
)
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime, timezone

Base = declarative_base()


def now_utc():
    return datetime.now(timezone.utc)


class TrendItem(Base):
    __tablename__ = "trend_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source = Column(String(64), nullable=False)       # google_trends, reddit, rss
    raw_title = Column(String(512), nullable=False)
    query = Column(String(256))
    url = Column(String(1024))
    score_raw = Column(Float, default=0.0)
    run_date = Column(String(16))                     # YYYY-MM-DD
    created_at = Column(DateTime, default=now_utc)

    topics = relationship("Topic", back_populates="trend_item")


class Topic(Base):
    __tablename__ = "topics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    trend_id = Column(Integer, ForeignKey("trend_items.id"), nullable=True)
    title = Column(String(512), nullable=False)
    niche = Column(String(256))
    angle = Column(String(512))
    status = Column(String(64), default="pending")
    # scoring
    opportunity_score = Column(Float, default=0.0)
    monetization_score = Column(Float, default=0.0)
    competition_score = Column(Float, default=0.0)
    risk_score = Column(Float, default=0.0)
    final_score = Column(Float, default=0.0)
    run_date = Column(String(16))
    created_at = Column(DateTime, default=now_utc)

    trend_item = relationship("TrendItem", back_populates="topics")
    research_packets = relationship("ResearchPacket", back_populates="topic")
    scripts = relationship("Script", back_populates="topic")
    assets = relationship("Asset", back_populates="topic")
    videos = relationship("Video", back_populates="topic")


class ResearchPacket(Base):
    __tablename__ = "research_packets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    topic_id = Column(Integer, ForeignKey("topics.id"), nullable=False)
    sources_json = Column(JSON, default=list)
    summary = Column(Text)
    facts_json = Column(JSON, default=list)
    controversy = Column(Text)
    created_at = Column(DateTime, default=now_utc)

    topic = relationship("Topic", back_populates="research_packets")


class Script(Base):
    __tablename__ = "scripts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    topic_id = Column(Integer, ForeignKey("topics.id"), nullable=False)
    title = Column(String(512))
    hook = Column(Text)
    script_text = Column(Text)
    description = Column(Text)
    tags_json = Column(JSON, default=list)
    thumbnail_prompt = Column(Text)
    x_post = Column(Text)
    word_count = Column(Integer, default=0)
    status = Column(String(64), default="generated")
    format = Column(String(32), default="longform")  # generated, needs_review, approved, rejected
    created_at = Column(DateTime, default=now_utc)

    topic = relationship("Topic", back_populates="scripts")
    videos = relationship("Video", back_populates="script")


class Asset(Base):
    __tablename__ = "assets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    topic_id = Column(Integer, ForeignKey("topics.id"), nullable=False)
    asset_type = Column(String(64))   # thumbnail, voiceover, background_image, subtitle
    path = Column(String(1024))
    metadata_json = Column(JSON, default=dict)
    created_at = Column(DateTime, default=now_utc)

    topic = relationship("Topic", back_populates="assets")


class Video(Base):
    __tablename__ = "videos"

    id = Column(Integer, primary_key=True, autoincrement=True)
    topic_id = Column(Integer, ForeignKey("topics.id"), nullable=False)
    script_id = Column(Integer, ForeignKey("scripts.id"), nullable=True)
    video_path = Column(String(1024))
    package_path = Column(String(1024))
    duration_seconds = Column(Float, default=0.0)
    status = Column(String(64), default="pending")
    # pending → rendering → rendered → quality_check → approved → queued → published / rejected
    quality_score = Column(Float, default=0.0)
    rejection_reason = Column(Text)
    run_date = Column(String(16))
    created_at = Column(DateTime, default=now_utc)

    topic = relationship("Topic", back_populates="videos")
    script = relationship("Script", back_populates="videos")
    publish_queue = relationship("PublishQueue", back_populates="video")


class PublishQueue(Base):
    __tablename__ = "publish_queue"

    id = Column(Integer, primary_key=True, autoincrement=True)
    video_id = Column(Integer, ForeignKey("videos.id"), nullable=False)
    platform = Column(String(32))          # youtube, x
    scheduled_at = Column(DateTime)
    published_at = Column(DateTime)
    status = Column(String(32), default="scheduled")
    # scheduled → approved → publishing → published / failed
    platform_post_id = Column(String(256))
    error = Column(Text)
    created_at = Column(DateTime, default=now_utc)

    video = relationship("Video", back_populates="publish_queue")


class Analytics(Base):
    __tablename__ = "analytics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    video_id = Column(Integer, ForeignKey("videos.id"), nullable=False)
    platform = Column(String(32))
    views = Column(Integer, default=0)
    impressions = Column(Integer, default=0)
    ctr = Column(Float, default=0.0)
    watch_time = Column(Float, default=0.0)
    likes = Column(Integer, default=0)
    comments = Column(Integer, default=0)
    shares = Column(Integer, default=0)
    subscribers_gained = Column(Integer, default=0)
    collected_at = Column(DateTime, default=now_utc)


class RunLog(Base):
    __tablename__ = "run_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_date = Column(String(16))
    phase = Column(String(64))
    status = Column(String(32))       # started, completed, failed
    message = Column(Text)
    items_processed = Column(Integer, default=0)
    created_at = Column(DateTime, default=now_utc)

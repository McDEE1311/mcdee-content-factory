"""
Test database initialization and basic CRUD.
"""
import os
import pytest
import tempfile
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base, TrendItem, Topic, Script, Video, PublishQueue


@pytest.fixture
def test_db():
    """Create a fresh in-memory test database."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    yield db
    db.close()


def test_create_tables(test_db):
    """All tables should be created."""
    from sqlalchemy import inspect
    engine = test_db.bind
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    assert "trend_items" in tables
    assert "topics" in tables
    assert "scripts" in tables
    assert "videos" in tables
    assert "publish_queue" in tables
    assert "analytics" in tables
    assert "run_logs" in tables


def test_trend_item_crud(test_db):
    """Test TrendItem creation and retrieval."""
    trend = TrendItem(
        source="rss_test",
        raw_title="Test AI Trend",
        query="test ai trend",
        url="https://example.com",
        score_raw=0.8,
        run_date="2024-01-01",
    )
    test_db.add(trend)
    test_db.commit()

    retrieved = test_db.query(TrendItem).filter(TrendItem.raw_title == "Test AI Trend").first()
    assert retrieved is not None
    assert retrieved.source == "rss_test"
    assert retrieved.score_raw == 0.8


def test_topic_with_foreign_key(test_db):
    """Test Topic linked to TrendItem."""
    trend = TrendItem(
        source="test", raw_title="AI Infrastructure", run_date="2024-01-01"
    )
    test_db.add(trend)
    test_db.flush()

    topic = Topic(
        trend_id=trend.id,
        title="AI Infrastructure Deep Dive",
        niche="ai-infra",
        status="selected",
        final_score=0.75,
        run_date="2024-01-01",
    )
    test_db.add(topic)
    test_db.commit()

    retrieved = test_db.query(Topic).filter(Topic.trend_id == trend.id).first()
    assert retrieved is not None
    assert retrieved.final_score == 0.75


def test_script_creation(test_db):
    """Test Script creation."""
    trend = TrendItem(source="test", raw_title="GPU Prices", run_date="2024-01-01")
    test_db.add(trend)
    test_db.flush()

    topic = Topic(title="GPU Price Crash", run_date="2024-01-01")
    test_db.add(topic)
    test_db.flush()

    script = Script(
        topic_id=topic.id,
        title="GPU Prices Are Crashing: What It Means",
        hook="GPU prices just dropped 40% in a week.",
        script_text="[HOOK]\nGPU prices just dropped 40% in a week. Here's what's driving it...",
        word_count=150,
        status="generated",
    )
    test_db.add(script)
    test_db.commit()

    retrieved = test_db.query(Script).filter(Script.topic_id == topic.id).first()
    assert retrieved is not None
    assert retrieved.word_count == 150
    assert retrieved.status == "generated"

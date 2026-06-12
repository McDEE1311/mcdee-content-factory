"""
Test topic ranker scoring logic.
"""
import pytest
from app.agents.topic_ranker import (
    calculate_final_score,
    quick_safety_check,
    _heuristic_score,
)


def test_final_score_formula():
    """Score formula should work correctly."""
    scores = {
        "trend_strength": 0.8,
        "monetization_score": 0.7,
        "channel_fit": 0.9,
        "low_competition_score": 0.6,
        "freshness_score": 0.8,
        "content_depth_score": 0.7,
        "risk_score": 0.1,
    }
    score = calculate_final_score(scores)
    assert 0 < score < 1
    # Manually: 0.8*0.25 + 0.7*0.2 + 0.9*0.2 + 0.6*0.15 + 0.8*0.1 + 0.7*0.1 - 0.1*0.3
    expected = 0.2 + 0.14 + 0.18 + 0.09 + 0.08 + 0.07 - 0.03
    assert abs(score - expected) < 0.001


def test_high_risk_kills_score():
    """High risk should significantly reduce score."""
    scores = {
        "trend_strength": 1.0,
        "monetization_score": 1.0,
        "channel_fit": 1.0,
        "low_competition_score": 1.0,
        "freshness_score": 1.0,
        "content_depth_score": 1.0,
        "risk_score": 1.0,
    }
    score = calculate_final_score(scores)
    # Even with all 1.0 except risk=1.0, score should be penalized
    # Max without penalty: 0.25+0.2+0.2+0.15+0.1+0.1 = 1.0 - 0.3 = 0.70
    assert score < 0.75


def test_safety_check_banned():
    """Banned topics should be rejected."""
    rules = {
        "banned_topics": ["adult content", "hate speech", "malware"],
        "rejected_topics": ["celebrity gossip"],
    }
    safe, reason = quick_safety_check("How to create adult content for profit", rules)
    assert not safe
    assert "adult content" in reason.lower()


def test_safety_check_passes():
    """Clean topic should pass safety check."""
    rules = {
        "banned_topics": ["adult content", "hate speech"],
        "rejected_topics": ["celebrity gossip"],
    }
    safe, reason = quick_safety_check("Bittensor subnet validator setup guide 2024", rules)
    assert safe
    assert reason == ""


def test_heuristic_score_ai_topic():
    """AI topic should get good channel fit."""
    scores = _heuristic_score("New Bittensor subnet launches with GPU marketplace", "rss_test")
    assert scores["channel_fit"] > 0.3
    assert scores["monetization_score"] >= 0.5
    assert scores["risk_score"] == 0.0


def test_heuristic_score_banned_topic():
    """Banned topic should get risk_score = 1.0."""
    rules_content = {
        "banned_topics": ["jailbreak", "malware"],
    }
    # Since heuristic uses loaded rules, test the safety check path
    scores = _heuristic_score("How to jailbreak GPT-4 for illegal use", "reddit_test")
    # The heuristic checks banned topics
    assert scores["risk_score"] == 1.0


def test_schedule_spacing():
    """Queue schedule should produce evenly spaced times."""
    from app.agents.queue_manager import calculate_schedule
    times = calculate_schedule(10, run_date="2024-06-01", start_hour=8, end_hour=20)
    assert len(times) == 10
    # First should be 8 AM, last should be 8 PM
    import pytz
    ct = pytz.timezone("America/Chicago")
    local_times = [t.astimezone(ct) for t in times]
    assert local_times[0].hour == 8
    assert local_times[-1].hour == 20


def test_schedule_single_video():
    """Single video should be at start of window."""
    from app.agents.queue_manager import calculate_schedule
    times = calculate_schedule(1, run_date="2024-06-01", start_hour=8, end_hour=20)
    assert len(times) == 1

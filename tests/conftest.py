"""
pytest configuration — sets up a test .env so settings load without a real .env file.
"""
import os
import sys

# Ensure project root on path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# Set minimal env vars before any app import
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("DB_PATH", ":memory:")
os.environ.setdefault("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
os.environ.setdefault("OLLAMA_MODEL", "qwen2.5:7b-instruct")
os.environ.setdefault("AUTO_APPROVE", "false")
os.environ.setdefault("DAILY_VIDEO_LIMIT", "10")
os.environ.setdefault("LOCAL_TIMEZONE", "America/Chicago")

#!/usr/bin/env python3
"""
Initialize the SQLite database.
Run once before first use: python3 scripts/init_db.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.db import init_db
from app.settings import settings

if __name__ == "__main__":
    os.makedirs(os.path.dirname(settings.DB_PATH), exist_ok=True)
    os.makedirs("logs", exist_ok=True)
    os.makedirs("outputs/upload_packages", exist_ok=True)
    init_db()
    print(f"[init_db] Database ready at {settings.DB_PATH}")
